"""Boundary and orchestration tests; Gemini calls are isolated with explicit fakes."""
import asyncio
from io import BytesIO
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
import main
from config import BASE_DIR, Settings
from schemas import AnalysisResponse, ParsedContext, Recommendations
from services.ai_engine import AIEngine, generation_schema
from services.errors import AppError
from services.parser import ParsedResume, extract_resume
from services.scoring import assess_skills, calculate_scores

JOB = 'Required: Python and SQL for data analysis and reliable business reporting. Preferred: Power BI dashboards.'
RESUME = 'I use Python for data analysis. I write SQL for business reporting. I completed a BSc in Statistics.'


def context(requirements=None):
    return ParsedContext.model_validate({'job_title':'Data Analyst','enriched_description':JOB,
        'requirements':requirements or [
            {'name':'Python','category':'Programming Languages','priority':'required','job_evidence':'Python and SQL','resume_evidence':'Python for data analysis'},
            {'name':'SQL','category':'Databases','priority':'required','job_evidence':'Python and SQL','resume_evidence':'SQL for business reporting'},
            {'name':'Power BI','category':'Tools','priority':'preferred','job_evidence':'Power BI dashboards','resume_evidence':'I am an expert in Power BI'}],
        'profile':{'name':'Test Candidate','headline':'Data analyst','summary':'Works with Python and SQL.'},
        'education':[],'experience':[],'achievements':[]})


@pytest.fixture
def demo():
    return AnalysisResponse.model_validate_json((BASE_DIR/'data'/'demo.json').read_text(encoding='utf-8'))


@pytest.fixture
def settings():
    return Settings(_env_file=None,gemini_api_key='',max_upload_mb=1)


def test_home_demo_and_health(settings):
    with TestClient(main.create_app(settings)) as client:
        home=client.get('/')
        assert home.status_code==200 and 'Your next move' in home.text
        assert client.get('/static/css/app.css').status_code==200
        result=client.get('/api/demo').json()
        assert result['metadata']['mode']=='demo'
        assert result['scores']['required']['matched']==5
        assert client.get('/api/health').json()['analysis_configured'] is False
        assert client.get('/api/demo').headers['cache-control']=='no-store'


@pytest.mark.parametrize('filename,mime,data,consent,status,code',[
    ('resume.txt','text/plain',b'%PDF-1.7','true',415,'pdf_required'),
    ('resume.pdf','application/pdf',b'not pdf','true',422,'invalid_pdf'),
    ('resume.pdf','application/pdf',b'','true',422,'invalid_pdf'),
    ('resume.pdf','application/pdf',b'%PDF-1.7','false',422,'consent_required'),
    ('resume.pdf','application/pdf',b'%PDF-1.7','true',503,'ai_not_configured'),
    ('resume.pdf','application/pdf',b'%PDF-'+b'x'*1048576,'true',413,'file_too_large')],
    ids=['wrong-extension','invalid-signature','empty-file','consent-required','missing-key','oversized-file'])
def test_upload_boundaries(settings,filename,mime,data,consent,status,code):
    with TestClient(main.create_app(settings)) as client:
        response=client.post('/api/analyze',files={'resume':(filename,data,mime)},data={'job_description':JOB,'consent':consent})
        assert response.status_code==status,response.text
        assert response.json()['error']['code']==code


def test_missing_fields_do_not_echo_private_inputs(settings):
    with TestClient(main.create_app(settings)) as client:
        response=client.post('/api/analyze',data={'job_description':'PRIVATE-RESUME-CONTENTS'})
        assert response.status_code==422
        assert 'PRIVATE-RESUME-CONTENTS' not in response.text


def test_whitespace_job_rejected(settings):
    with TestClient(main.create_app(settings)) as client:
        response=client.post('/api/analyze',files={'resume':('cv.pdf',b'%PDF-1.7','application/pdf')},
                             data={'job_description':' '*90,'consent':'true'})
        assert response.status_code==422
        assert response.json()['error']['code']=='invalid_job_description'


def test_body_limit_without_content_length(settings):
    with TestClient(main.create_app(settings)) as client:
        response=client.post('/api/analyze',content=iter([b'x'*700000]*2),headers={'content-type':'application/octet-stream'})
        assert response.status_code==413
        assert response.json()['error']['code']=='request_too_large'


@pytest.mark.parametrize('encrypted',[False,True])
def test_scanned_and_encrypted_pdfs_are_actionable(settings,encrypted):
    writer=PdfWriter();writer.add_blank_page(width=600,height=800)
    if encrypted:writer.encrypt('password')
    buffer=BytesIO();writer.write(buffer)
    with pytest.raises(AppError) as caught:extract_resume(buffer.getvalue(),settings)
    assert caught.value.code==('encrypted_pdf' if encrypted else 'scanned_pdf')


def test_quotes_and_no_requirements_are_not_false_matches():
    rows,notes=assess_skills(context(),RESUME,JOB)
    assert [r.name for r in rows if r.status=='matched']==['Python','SQL']
    scores=calculate_scores(rows,80)
    assert scores.required.score==100
    assert scores.preferred.score==0
    assert scores.total==74
    empty=calculate_scores([],80)
    assert empty.required.score is None and empty.preferred.score is None
    assert empty.total==80 and empty.weights=={'semantic':1.0}


def test_invented_requirements_removed_and_duplicates_not_double_counted():
    parsed=context();duplicate=parsed.requirements[0].model_copy(update={'priority':'preferred'})
    fabricated=parsed.requirements[0].model_copy(update={'name':'Kubernetes','job_evidence':'Requires Kubernetes'})
    parsed.requirements.extend([duplicate,fabricated])
    rows,notes=assess_skills(parsed,RESUME,JOB)
    assert len(rows)==3
    assert rows[0].priority=='required'
    assert notes and all(r.name!='Kubernetes' for r in rows)


def test_complete_endpoint_with_injected_services(settings,demo,monkeypatch):
    class FakeEngine:
        configured=True
        def require_configuration(self):pass
        async def analyze(self,text,job,filename,pages):
            assert text==RESUME and job==JOB and filename=='test.pdf' and pages==2
            return demo
        async def aclose(self):pass
    monkeypatch.setattr(main,'extract_resume',lambda data,settings:ParsedResume(RESUME,2))
    with TestClient(main.create_app(settings,FakeEngine())) as client:
        response=client.post('/api/analyze',files={'resume':('../../test.pdf',b'%PDF-1.7 test','application/pdf')},data={'job_description':JOB,'consent':'true'})
        assert response.status_code==200,response.text
        assert response.json()['job_title']=='Data Analyst'


def test_ai_orchestration_uses_checked_evidence(settings,demo):
    engine=AIEngine(settings)
    async def fake_generate(schema,instructions,payload):
        return context() if schema is ParsedContext else demo.recommendations
    engine._generate=fake_generate
    engine.encoder.score=lambda resume,job:80
    result=asyncio.run(engine.analyze(RESUME,JOB,'test.pdf',1))
    assert result.scores.total==74 and result.skills[-1].status=='missing'
    assert result.metadata.mode=='live'


def test_invalid_gemini_json_is_handled(settings):
    engine=AIEngine(settings.model_copy(update={'gemini_api_key':__import__('pydantic').SecretStr('test-key')}))
    async def generate_content(**kwargs):return SimpleNamespace(text='{"invalid":true}')
    engine._client=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    with pytest.raises(AppError) as caught:
        asyncio.run(engine._generate(ParsedContext,'Instructions',{}))
    assert caught.value.code=='invalid_ai_response'


def test_generation_schema_keeps_shape_and_local_validation_limits():
    schema=generation_schema(ParsedContext)
    assert 'maxLength' not in json.dumps(schema)
    assert 'minLength' not in json.dumps(schema)
    assert 'maxItems' not in json.dumps(schema)
    assert 'minItems' not in json.dumps(schema)
    assert schema['$defs']['Requirement']['properties']['priority']['enum']==['required','preferred']
    assert schema['required']==ParsedContext.model_json_schema()['required']
    assert ParsedContext.model_json_schema()['$defs']['Profile']['properties']['name']['maxLength']==150
    assert ParsedContext.model_json_schema()['properties']['requirements']['maxItems']==60


def test_generate_uses_compact_schema_and_still_rejects_long_values(settings):
    from pydantic import SecretStr
    engine=AIEngine(settings.model_copy(update={'gemini_api_key':SecretStr('test-key')}))
    invalid=context().model_dump()
    invalid['profile']['name']='x'*151
    async def generate_content(**kwargs):
        assert 'maxLength' not in json.dumps(kwargs['config'].response_json_schema)
        return SimpleNamespace(text=json.dumps(invalid))
    engine._client=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    with pytest.raises(AppError) as caught:
        asyncio.run(engine._generate(ParsedContext,'Instructions',{}))
    assert caught.value.code=='invalid_ai_response'


@pytest.mark.parametrize('upstream_status,status,code',[
    (400,502,'ai_request_rejected'),
    (504,504,'ai_timeout')])
def test_provider_errors_are_specific_and_do_not_echo_input(settings,upstream_status,status,code):
    from google.genai import errors
    from pydantic import SecretStr
    engine=AIEngine(settings.model_copy(update={'gemini_api_key':SecretStr('test-key')}))
    calls=[]
    async def generate_content(**kwargs):
        calls.append(kwargs)
        raise errors.APIError(upstream_status,{'error':{'message':'PRIVATE-CV-TEXT test-key','status':'INVALID_ARGUMENT'}})
    engine._client=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    with pytest.raises(AppError) as caught:
        asyncio.run(engine._generate(ParsedContext,'Instructions',{}))
    assert (caught.value.status,caught.value.code)==(status,code)
    assert 'PRIVATE-CV-TEXT' not in caught.value.message and 'test-key' not in caught.value.message
    assert len(calls)==1


def test_demo_can_be_disabled(settings):
    with TestClient(main.create_app(settings.model_copy(update={'enable_demo':False}))) as client:
        assert client.get('/api/demo').status_code==404
        assert 'id="sample-button"' not in client.get('/').text


def test_long_document_is_chunked_and_overlap_is_not_double_counted():
    import numpy as np
    from services.embeddings import SemanticEncoder
    class Tokenizer:
        def encode(self,text,add_special_tokens,**kwargs):
            tokens=list(range(600)) if text=='long document' else [int(token) for token in text.split()]
            return [-1,*tokens,-2] if add_special_tokens else tokens
        def decode(self,tokens,skip_special_tokens):return ' '.join(map(str,tokens))
    class Model:
        max_seq_length=256
        tokenizer=Tokenizer()
        def encode(self,chunks,**kwargs):
            assert [len(chunk.split()) for chunk in chunks]==[254,254,156]
            assert chunks[-1].split()[-1]=='599'
            return np.array([[1.,0.],[0.,1.],[1.,0.]])
    vector=SemanticEncoder('test')._document_vector(Model(),'long document')
    expected=np.array([378.,222.]);expected/=np.linalg.norm(expected)
    assert np.allclose(vector,expected)


def test_chunk_roundtrip_expansion_fits_model_and_preserves_tail():
    import numpy as np
    from services.embeddings import SemanticEncoder
    covered=[]
    class Tokenizer:
        def encode(self,text,add_special_tokens,**kwargs):
            tokens=list(range(600)) if text=='long document' else [0]*(len(text.split())+5)
            return [-1,*tokens,-2] if add_special_tokens else tokens
        def decode(self,tokens,skip_special_tokens):return ' '.join(map(str,tokens))
    class Model:
        max_seq_length=256
        tokenizer=Tokenizer()
        def encode(self,chunks,**kwargs):
            for chunk in chunks:
                assert len(self.tokenizer.encode(chunk,add_special_tokens=True))<=self.max_seq_length
                covered.extend(int(token) for token in chunk.split())
            return np.array([[1.,0.],[0.,1.],[1.,0.]])
    vector=SemanticEncoder('test')._document_vector(Model(),'long document')
    assert set(covered)==set(range(600))
    assert covered[-1]==599
    expected=np.array([383.,217.]);expected/=np.linalg.norm(expected)
    assert np.allclose(vector,expected)


def test_unrepresentable_token_returns_error_instead_of_looping():
    from services.embeddings import SemanticEncoder
    class Tokenizer:
        def encode(self,text,add_special_tokens,**kwargs):
            return list(range(10)) if add_special_tokens else [1]
        def decode(self,tokens,skip_special_tokens):return 'expanded token'
    model=SimpleNamespace(max_seq_length=4,tokenizer=Tokenizer())
    with pytest.raises(AppError) as caught:
        SemanticEncoder('test')._document_vector(model,'text')
    assert caught.value.code=='embedding_failed'
