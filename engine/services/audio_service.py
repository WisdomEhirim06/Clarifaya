import os
from uuid import uuid4
import tempfile
import whisper
from django.conf import settings
from django.core.files.storage import default_storage
from pydub import AudioSegment
import librosa
import soundfile as sf
import logging

logger = logging.getLogger(__name__)
class AudioService:
    """Service for handling audio processing and speech-to-text conversion"""
    
    def __init__(self):
        self.whisper_model = None
        self._load_whisper_model()
    
    def _load_whisper_model(self):
        """Load Whisper model for speech-to-text"""
        try:
            # Use base model for balance between speed and accuracy
            self.whisper_model = whisper.load_model("base")
        except Exception as e:
            logger.warning(f"Error loading Whisper model: {e}")
            self.whisper_model = None
    
    def convert_audio_format(self, audio_file_path, target_format='wav'):
        """Convert audio file to target format"""
        try:
            # Load audio file
            audio = AudioSegment.from_file(audio_file_path)
            
            # Convert to target format
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=f'.{target_format}'
            )
            
            if target_format == 'wav':
                audio.export(temp_file.name, format='wav')
            elif target_format == 'mp3':
                audio.export(temp_file.name, format='mp3')
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
            
            return temp_file.name
        except Exception as e:
            raise Exception(f"Error converting audio format: {e}")
    
    def preprocess_audio(self, audio_file_path):
        """Preprocess audio for better transcription"""
        try:
            # Load audio with librosa
            y, sr = librosa.load(audio_file_path, sr=16000)
            
            # Normalize audio
            y = librosa.util.normalize(y)
            
            # Remove silence
            y_trimmed, _ = librosa.effects.trim(y, top_db=20)
            
            # Save preprocessed audio
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.wav'
            )
            sf.write(temp_file.name, y_trimmed, sr)
            
            return temp_file.name
        except Exception as e:
            logger.warning(f"Warning: Audio preprocessing failed: {e}")
            return audio_file_path
    
    def transcribe_audio(self, audio_file_path):
        """Convert audio to text using Whisper"""
        if not self.whisper_model:
            raise Exception("Whisper model not loaded")
        
        try:
            # Preprocess audio
            processed_audio_path = self.preprocess_audio(audio_file_path)
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(processed_audio_path)
            
            # Clean up temporary files
            if processed_audio_path != audio_file_path:
                os.unlink(processed_audio_path)
            
            return {
                'text': result['text'].strip(),
                'language': result.get('language', 'en')
            }
        
        except Exception as e:
            raise Exception(f"Error transcribing audio: {e}")
    
    def get_audio_duration(self, audio_file_path):
        """Get audio duration in seconds"""
        try:
            audio = AudioSegment.from_file(audio_file_path)
            return len(audio) / 1000.0  # Convert to seconds
        except Exception as e:
            logger.warning(f"Error getting audio duration: {e}")
            return None
    
    def validate_audio_file(self, audio_file):
        """Validate uploaded audio file"""
        try:
            # Check file size (max 10MB)
            if audio_file.size > 10 * 1024 * 1024:
                return False, "Audio file size must be less than 10MB"
            
            # Check file format
            allowed_formats = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']
            file_extension = os.path.splitext(audio_file.name)[1].lower()
            
            if file_extension not in allowed_formats:
                return False, f"Unsupported audio format. Allowed: {', '.join(allowed_formats)}"
            
            return True, "Valid audio file"
        
        except Exception as e:
            return False, f"Error validating audio file: {e}"
    
    def save_uploaded_audio(self, audio_file):
        """Save uploaded audio file and return path"""
        try:
            # Validate file
            is_valid, message = self.validate_audio_file(audio_file)
            if not is_valid:
                raise Exception(message)
            
            # Save file
            filename = f"{uuid4()}_{audio_file.name}"
            file_path = default_storage.save(
                f"{settings.AUDIO_UPLOAD_PATH}{filename}",
                audio_file
            )
            
            return os.path.join(settings.MEDIA_ROOT, file_path)
        
        except Exception as e:
            raise Exception(f"Error saving audio file: {e}")
    
    def cleanup_temp_files(self, file_paths):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Warning: Could not delete temp file {file_path}: {e}")


# Singleton instance
audio_service = AudioService()