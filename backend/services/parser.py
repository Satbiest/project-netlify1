"""Validate PDFs locally, then extract document elements with Unstructured."""
from dataclasses import dataclass
from io import BytesIO
import logging
import os
import re
from pypdf import PdfReader
from config import BASE_DIR, Settings
from services.errors import AppError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedResume:
    text: str
    pages: int


def validate_upload(filename: str, content_type: str, data: bytes, settings: Settings) -> None:
    if not filename.lower().endswith('.pdf'):
        raise AppError(415, 'pdf_required', 'Please upload a resume in PDF format.')
    if content_type not in {'application/pdf', 'application/octet-stream'}:
        raise AppError(415, 'pdf_required', 'The uploaded file must be a PDF.')
    if len(data) > settings.max_upload_bytes:
        raise AppError(413, 'file_too_large', f'Your PDF must be no larger than {settings.max_upload_mb} MB.')
    if not data or not data[:1024].lstrip().startswith(b'%PDF-'):
        raise AppError(422, 'invalid_pdf', 'This file is empty or is not a valid PDF.')


def extract_resume(data: bytes, settings: Settings) -> ParsedResume:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise AppError(422, 'encrypted_pdf', 'Remove the PDF password before uploading it.')
        pages = len(reader.pages)
        if not 1 <= pages <= settings.max_pdf_pages:
            raise AppError(422, 'page_limit', f'Please use a PDF with 1 to {settings.max_pdf_pages} pages.')
        # Avoid silently falling back to OCR or downloading layout models.
        if not any((page.extract_text() or '').strip() for page in reader.pages):
            raise AppError(422, 'scanned_pdf', 'No selectable text was found. Export a text-based PDF or run OCR on your scanned resume first.')
    except AppError:
        raise
    except Exception as exc:
        log.warning('PDF preflight failed (%s)', type(exc).__name__)
        raise AppError(422, 'invalid_pdf', 'The PDF could not be read. Try exporting it again.') from None

    try:
        os.environ.setdefault('NLTK_DATA', str(BASE_DIR / '.cache' / 'nltk_data'))
        from unstructured.partition.pdf import partition_pdf
    except ImportError:
        raise AppError(503, 'parser_unavailable', 'PDF extraction is not installed on the server. Install requirements.txt and restart CVBoost.') from None
    try:
        elements = partition_pdf(file=BytesIO(data), strategy='fast', infer_table_structure=False)
        text = '\n'.join(str(element) for element in elements)
        text = re.sub(r'[^\S\n]+', ' ', text.replace('\x00', '')).strip()
    except Exception as exc:
        log.warning('Unstructured extraction failed (%s)', type(exc).__name__)
        raise AppError(422, 'extraction_failed', 'Text extraction failed. Try a simpler, text-based PDF with selectable text.') from None
    if len(text) < 80:
        raise AppError(422, 'insufficient_text', 'Not enough resume text was found. Please upload a complete, text-based resume.')
    if len(text) > settings.max_resume_chars:
        raise AppError(422, 'resume_too_long', f'The extracted resume exceeds {settings.max_resume_chars:,} characters. Please use a shorter resume.')
    return ParsedResume(text=text, pages=pages)

