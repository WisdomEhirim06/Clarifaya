import os
import fitz  # PyMuPDF
import logging
import re

from docx import Document
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DocumentParser:
    """Service for parsing and extracting text from uploaded documents."""

    def __init__(self):
        self.supported_formats = ['.pdf', '.docx']  # Removed '.doc'
        self.max_size_mb = getattr(settings, 'DOCUMENT_MAX_SIZE_MB', 10)
        self.upload_path = getattr(settings, 'DOCUMENT_UPLOAD_PATH', 'documents/')
        self.chunk_size = getattr(settings, 'DOCUMENT_CHUNK_SIZE', 3000)

    def validate_document(self, document_file):
        """Validate uploaded document."""
        try:
            if document_file.size > self.max_size_mb * 1024 * 1024:
                return False, f"Document size must be less than {self.max_size_mb}MB"

            ext = os.path.splitext(document_file.name)[1].lower()
            
            if ext not in self.supported_formats:
                return False, f"Unsupported format. Allowed formats: {', '.join(self.supported_formats)}"

            return True, "Valid document"
        except Exception as e:
            logger.exception("Validation failed.")
            return False, f"Error validating document: {e}"

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using PyMuPDF."""
        try:
            with fitz.open(pdf_path) as doc:
                return " ".join(page.get_text() for page in doc).strip()
        except Exception as e:
            logger.exception("PDF extraction failed.")
            raise Exception(f"Error extracting text from PDF: {e}")

    def extract_text_from_docx(self, docx_path):
        """Extract text from DOCX using python-docx."""
        try:
            doc = Document(docx_path)
            text = []

            for para in doc.paragraphs:
                text.append(para.text)

            for table in doc.tables:
                for row in table.rows:
                    text.append(" ".join(cell.text for cell in row.cells))

            return "\n".join(text).strip()
        except Exception as e:
            logger.exception("DOCX extraction failed.")
            raise Exception(f"Error extracting text from DOCX: {e}")

    def clean_extracted_text(self, text):
        """Clean and normalize extracted text."""
        try:
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'[^\w\s.,!?;:()\-"\']', ' ', text)
            text = re.sub(r'\.{3,}', '...', text)
            text = re.sub(r'\s{2,}', ' ', text)
            text = re.sub(r'\.([A-Z])', r'. \1', text)
            return text.strip()
        except Exception as e:
            logger.warning(f"Text cleaning failed: {e}")
            return text

    def get_text_statistics(self, text):
        """Get basic statistics about the extracted text."""
        try:
            return {
                'word_count': len(text.split()),
                'sentence_count': len([s for s in text.split('.') if s.strip()]),
                'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
                'character_count': len(text),
                'character_count_no_spaces': len(text.replace(' ', ''))
            }
        except Exception as e:
            logger.warning(f"Failed to compute text statistics: {e}")
            return {
                'word_count': 0,
                'sentence_count': 0,
                'paragraph_count': 0,
                'character_count': 0,
                'character_count_no_spaces': 0
            }

    def chunk_text_for_processing(self, text, max_chunk_size=None):
        """Split text into chunks for AI or batch processing."""
        max_chunk_size = max_chunk_size or self.chunk_size
        try:
            words = text.split()
            chunks, current_chunk, current_size = [], [], 0

            for word in words:
                word_len = len(word) + 1
                if current_size + word_len > max_chunk_size and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [word]
                    current_size = word_len
                else:
                    current_chunk.append(word)
                    current_size += word_len

            if current_chunk:
                chunks.append(' '.join(current_chunk))

            return chunks
        except Exception as e:
            logger.warning(f"Text chunking failed: {e}")
            return [text]

    def extract_text_from_document(self, document_file):
        """Main method to validate, extract, and clean text from a document."""
        is_valid, message = self.validate_document(document_file)
        if not is_valid:
            raise ValidationError(message)

        file_path = None
        try:
            file_path = default_storage.save(
                os.path.join(self.upload_path, document_file.name),
                document_file
            )
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            ext = os.path.splitext(document_file.name)[1].lower()

            if ext == '.pdf':
                raw_text = self.extract_text_from_pdf(full_path)
            elif ext == '.docx':
                raw_text = self.extract_text_from_docx(full_path)
            else:
                raise ValidationError(f"Unsupported file format: {ext}")

            cleaned_text = self.clean_extracted_text(raw_text)
            stats = self.get_text_statistics(cleaned_text)

            if stats['word_count'] < 10:
                raise ValidationError("Document appears to be empty or unreadable.")

            return {
                'text': cleaned_text,
                'statistics': stats,
                'file_path': file_path,
                'file_name': document_file.name,
                'file_type': ext[1:].upper()
            }

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise Exception(f"Error processing document: {e}")
        finally:
            # Clean up if needed (optional)
            pass


# Singleton instance for reuse
document_parser = DocumentParser()
