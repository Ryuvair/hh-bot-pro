"""
Извлечение текста из PDF, DOCX, TXT
"""
import io
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
from docx import Document
from core.logger import logger

def extract_text_from_pdf(file_bytes: bytes) -> Optional[str]:
    """Извлекает текст из PDF-файла"""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip() if text else None
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из PDF: {e}")
        return None

def extract_text_from_docx(file_bytes: bytes) -> Optional[str]:
    """Извлекает текст из DOCX-файла"""
    try:
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        return text.strip() if text else None
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из DOCX: {e}")
        return None

def extract_text_from_txt(file_bytes: bytes) -> Optional[str]:
    """Извлекает текст из TXT-файла"""
    try:
        return file_bytes.decode('utf-8').strip()
    except UnicodeDecodeError:
        try:
            return file_bytes.decode('cp1251').strip()
        except Exception as e:
            logger.error(f"Ошибка декодирования TXT: {e}")
            return None

def extract_text_from_file(file_bytes: bytes, file_name: str) -> Optional[str]:
    """Определяет тип файла по расширению и извлекает текст"""
    ext = Path(file_name).suffix.lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_bytes)
    elif ext == '.docx':
        return extract_text_from_docx(file_bytes)
    elif ext == '.txt':
        return extract_text_from_txt(file_bytes)
    else:
        logger.warning(f"Неподдерживаемый формат файла: {ext}")
        return None
        