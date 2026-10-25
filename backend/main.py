"""Run with: python -m uvicorn main:app --host 127.0.0.1 --port 8000."""
import asyncio
import importlib.util
import json
import logging
from contextlib import asynccontextmanager
from pathlib import PurePosixPath
from typing import Annotated
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from config import BASE_DIR, Settings
from schemas import AnalysisResponse
from services.ai_engine import AIEngine
from services.errors import AppError
from services.parser import extract_resume, validate_upload

log = logging.getLogger('cvboost')


class BodyLimitMiddleware:
    """Bound the full multipart body BEFORE Starlette spools any uploaded files."""
    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            content_length = int(headers.get(b'content-length', b'0'))
            if content_length < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({'error': {'code': 'invalid_length', 'message': 'Invalid request body length.'}}, 400)(scope, receive, send)
        if content_length > self.max_bytes:
            return await self._too_large(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > self.max_bytes:
                return await self._too_large(scope, receive, send)
            chunks.append(body)
            if not message.get('more_body', False):
                break
        replayed = False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)

    async def _too_large(self, scope, receive, send):
        await JSONResponse({'error': {'code': 'request_too_large', 'message': 'This upload exceeds the server size limit.'}}, 413)(scope, receive, send)


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or Settings()
    engine = engine or AIEngine(settings)
    @asynccontextmanager
    async def lifespan(app):
        yield
        await engine.aclose()
    app = FastAPI(title='CVBoost API', version='1.0.0', lifespan=lifespan)
    app.state.engine = engine
    limiter = asyncio.Semaphore(settings.max_concurrent_analyses)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes + settings.max_job_chars * 4 + 65536)
    if settings.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                           allow_methods=['GET', 'POST'], allow_headers=['Content-Type'],
                           allow_credentials=False)
    app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
    templates = Jinja2Templates(directory=BASE_DIR / 'templates')

    @app.middleware('http')
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo submitted CV contents or raw input values in validation responses.
        return JSONResponse({'error': {'code': 'validation_error', 'message': 'Provide a PDF resume, a job description of at least 80 characters, and consent for AI analysis.'}}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.error('Unhandled request error (%s)', type(exc).__name__)
        return JSONResponse({'error': {'code': 'server_error', 'message': 'Something went wrong on the server. Please try again.'}}, status_code=500)

    @app.get('/')
    async def home(request: Request):
        return templates.TemplateResponse(request=request, name='index.html', context={
            'max_upload_mb': settings.max_upload_mb, 'max_job_chars': settings.max_job_chars,
            'demo_enabled': settings.enable_demo})

    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'analysis_configured': engine.configured,
                'demo_enabled': settings.enable_demo, 'max_upload_mb': settings.max_upload_mb,
                'max_job_chars': settings.max_job_chars, 'gemini_model': settings.gemini_model,
                'embedding_model': settings.embedding_model,
                'parser_installed': importlib.util.find_spec('unstructured') is not None,
                'encoder_installed': importlib.util.find_spec('sentence_transformers') is not None}

    @app.get('/api/demo', response_model=AnalysisResponse)
    async def demo():
        if not settings.enable_demo:
            raise AppError(404, 'demo_disabled', 'Sample analysis is disabled.')
        return AnalysisResponse.model_validate_json((BASE_DIR / 'data' / 'demo.json').read_text(encoding='utf-8'))

    @app.post('/api/analyze', response_model=AnalysisResponse)
    async def analyze(resume: Annotated[UploadFile, File(description='Text-based PDF resume')],
                      job_description: Annotated[str, Form(min_length=80, max_length=30000)],
                      consent: Annotated[bool, Form()]):
        acquired = False
        try:
            job = job_description.strip()
            if not consent:
                raise AppError(422, 'consent_required', 'Please allow sending the extracted text to Google Gemini before processing.')
            if not 80 <= len(job) <= settings.max_job_chars:
                raise AppError(422, 'invalid_job_description', f'Use a job description between 80 and {settings.max_job_chars:,} characters.')
            data = await resume.read(settings.max_upload_bytes + 1)
            filename = PurePosixPath((resume.filename or 'resume.pdf').replace('\\', '/')).name[:180]
            validate_upload(filename, resume.content_type or '', data, settings)
            engine.require_configuration()
            try:
                await asyncio.wait_for(limiter.acquire(), timeout=.5)
                acquired = True
            except asyncio.TimeoutError:
                raise AppError(429, 'server_busy', 'CVBoost is processing other resumes. Please try again shortly.') from None
            try:
                async with asyncio.timeout(settings.analysis_timeout_seconds):
                    parsed = await run_in_threadpool(extract_resume, data, settings)
                    return await engine.analyze(parsed.text, job, filename, parsed.pages)
            except TimeoutError:
                raise AppError(504, 'analysis_timeout', 'Analysis took too long. Try a shorter resume or retry after the model finishes loading.') from None
        finally:
            await resume.close()
            if acquired:
                limiter.release()

    return app


app = create_app()
