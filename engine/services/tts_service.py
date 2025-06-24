import os
import tempfile
from gtts import gTTS
from django.conf import settings
import hashlib
import time
import logging

logger = logging.getLogger(__name__)

class TTSService:
    """Service for converting text to speech using gTTS"""
    
    def __init__(self):
        self.default_lang = 'en'
        self.default_tld = 'com'  # US English accent
        self.cache_dir = os.path.join(settings.MEDIA_ROOT, settings.TTS_AUDIO_PATH)
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _generate_cache_key(self, text, lang='en', tld='com'):
        """Generate a cache key for the given text and settings"""
        cache_string = f"{text}_{lang}_{tld}"
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _get_cached_audio_path(self, cache_key):
        """Get the path for cached audio file"""
        return os.path.join(self.cache_dir, f"{cache_key}.mp3")
    
    def validate_text_for_tts(self, text):
        """Validate text for text-to-speech conversion"""
        try:
            if not text or not text.strip():
                return False, "Text cannot be empty"
            
            # Check text length (gTTS has limits)
            if len(text) > 5000:
                return False, "Text is too long. Maximum 5000 characters allowed"
            
            # Check for valid characters (basic check)
            if not any(c.isalnum() for c in text):
                return False, "Text must contain alphanumeric characters"
            
            return True, "Text is valid for TTS"
        
        except Exception as e:
            return False, f"Error validating text: {e}"
    
    def preprocess_text_for_speech(self, text):
        """Preprocess text to make it more suitable for speech synthesis"""
        try:
            # Remove excessive whitespace
            text = ' '.join(text.split())
            
            # Add pauses for better speech flow
            text = text.replace('.', '. ')
            text = text.replace(',', ', ')
            text = text.replace(';', '; ')
            text = text.replace(':', ': ')
            
            # Handle abbreviations that should be spelled out
            abbreviations = {
                'AI': 'A I',
                'API': 'A P I',
                'URL': 'U R L',
                'HTTP': 'H T T P',
                'PDF': 'P D F',
                'FAQ': 'F A Q'
            }
            
            for abbr, pronunciation in abbreviations.items():
                text = text.replace(abbr, pronunciation)
            
            # Ensure sentences end properly
            if text and not text.endswith(('.', '!', '?')):
                text += '.'
            
            return text.strip()
        
        except Exception as e:
            logger.warning(f"Warning: Text preprocessing failed: {e}")
            return text
    
    def text_to_speech(self, text, lang='en', tld='com', use_cache=True):
        """Convert text to speech and return file path"""
        try:
            # Validate text
            is_valid, message = self.validate_text_for_tts(text)
            if not is_valid:
                raise Exception(message)
            
            # Preprocess text
            processed_text = self.preprocess_text_for_speech(text)
            
            # Check cache first
            if use_cache:
                cache_key = self._generate_cache_key(processed_text, lang, tld)
                cached_path = self._get_cached_audio_path(cache_key)
                
                if os.path.exists(cached_path):
                    return {
                        'file_path': cached_path,
                        'file_url': f"{settings.MEDIA_URL}{settings.TTS_AUDIO_PATH}{cache_key}.mp3",
                        'cached': True,
                        'text_length': len(processed_text)
                    }
            
            # Generate speech
            tts = gTTS(
                text=processed_text,
                lang=lang,
                tld=tld,
                slow=False
            )
            
            # Save to cache or temporary file
            if use_cache:
                output_path = cached_path
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix='.mp3',
                    dir=self.cache_dir
                )
                output_path = temp_file.name
            
            tts.save(output_path)
            
            # Generate file URL
            if use_cache:
                file_url = f"{settings.MEDIA_URL}{settings.TTS_AUDIO_PATH}{cache_key}.mp3"
            else:
                filename = os.path.basename(output_path)
                file_url = f"{settings.MEDIA_URL}{settings.TTS_AUDIO_PATH}{filename}"
            
            return {
                'file_path': output_path,
                'file_url': file_url,
                'cached': False,
                'text_length': len(processed_text)
            }
        
        except Exception as e:
            raise Exception(f"Error converting text to speech: {e}")
    
    def generate_speech_for_question(self, question_text, explanation=None):
        """Generate speech for a question and optional explanation"""
        try:
            # Combine question and explanation
            full_text = question_text
            
            if explanation:
                full_text += f" ... {explanation}"
            
            return self.text_to_speech(full_text)
        
        except Exception as e:
            raise Exception(f"Error generating speech for question: {e}")
    
    def generate_speech_for_feedback(self, feedback_text, is_correct=True):
        """Generate speech for feedback with appropriate tone"""
        try:
            # Add encouraging prefix based on correctness
            if is_correct:
                prefixes = ["Great job!", "Excellent!", "That's right!", "Well done!"]
            else:
                prefixes = ["Not quite.", "Let me help you.", "Here's the correct answer.", "Let's try again."]
            
            # Use a simple prefix for now (could be randomized)
            prefix = prefixes[0]
            full_text = f"{prefix} {feedback_text}"
            
            return self.text_to_speech(full_text)
        
        except Exception as e:
            raise Exception(f"Error generating speech for feedback: {e}")
    
    def cleanup_old_cache_files(self, max_age_hours=24):
        """Clean up old cached TTS files"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    
                    if file_age > max_age_seconds:
                        try:
                            os.unlink(file_path)
                            print(f"Deleted old TTS cache file: {filename}")
                        except Exception as e:
                            print(f"Error deleting file {filename}: {e}")
        
        except Exception as e:
            logger.warning(f"Error cleaning up cache files: {e}")
    
    def get_supported_languages(self):
        """Get list of supported languages for TTS"""
        return {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese'
        }
    
    def get_english_accents(self):
        """Get available English accents (TLDs)"""
        return {
            'com': 'US English',
            'co.uk': 'British English',
            'com.au': 'Australian English',
            'ca': 'Canadian English'
        }


# Singleton instance
tts_service = TTSService()