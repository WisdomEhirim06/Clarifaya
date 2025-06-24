from rest_framework import serializers
from django.conf import settings
from .models import LearningSession, Question, UserResponse, AudioFile, Document


class LearningSessionSerializer(serializers.ModelSerializer):
    """Serializer for LearningSession model"""
    
    class Meta:
        model = LearningSession
        fields = [
            'id', 'topic', 'document_content', 'session_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for Question model"""
    
    class Meta:
        model = Question
        fields = [
            'id', 'session', 'question_text', 'question_type',
            'expected_answer', 'options', 'explanation', 'order_index',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UserResponseSerializer(serializers.ModelSerializer):
    """Serializer for UserResponse model"""
    
    class Meta:
        model = UserResponse
        fields = [
            'id', 'question', 'user_answer', 'is_correct',
            'ai_feedback', 'response_time', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AudioFileSerializer(serializers.ModelSerializer):
    """Serializer for AudioFile model"""
    
    class Meta:
        model = AudioFile
        fields = [
            'id', 'file', 'file_type', 'transcription',
            'duration', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model"""
    
    class Meta:
        model = Document
        fields = [
            'id', 'file', 'file_name', 'file_type',
            'extracted_text', 'word_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# Request/Response Serializers for API endpoints

class AudioTranscriptionRequestSerializer(serializers.Serializer):
    """Serializer for audio transcription requests"""
    audio_file = serializers.FileField()
    
    def validate_audio_file(self, value):
        """Validate uploaded audio file"""
        # Check file size (10MB limit)
        max_file_size_mb = getattr(settings, 'MAX_FILE_SIZE_MB', 10)

        if value.size > max_file_size_mb * 1024 * 1024:
            raise serializers.ValidationError("Audio file size cannot exceed {max_file_size_mb}MB")
        
        # Check file format
        allowed_formats = ['wav', 'mp3', 'm4a', 'ogg', 'flac']
        file_extension = value.name.split('.')[-1].lower()
        
        if file_extension not in allowed_formats:
            raise serializers.ValidationError(
                f"Unsupported audio format. Allowed formats: {', '.join(allowed_formats)}"
            )
        
        return value


class AudioTranscriptionResponseSerializer(serializers.Serializer):
    """Serializer for audio transcription responses"""
    transcription = serializers.CharField()
    confidence = serializers.FloatField(allow_null=True)
    language = serializers.CharField()
    duration = serializers.FloatField(allow_null=True)
    audio_id = serializers.UUIDField()


class DocumentParseRequestSerializer(serializers.Serializer):
    """Serializer for document parsing requests"""
    document_file = serializers.FileField()
    
    def validate_document_file(self, value):
        """Validate uploaded document file"""
        max_file_size_mb = getattr(settings, 'DOCUMENT_MAX_SIZE_MB', 10)
        
        # Check file size (10MB limit)
        if value.size > max_file_size_mb * 1024 * 1024:
            raise serializers.ValidationError("Document file size cannot exceed {max_file_size_mb}MB")
        
        # Check file format
        allowed_formats = ['pdf', 'docx']
        file_extension = value.name.split('.')[-1].lower()
        
        if file_extension not in allowed_formats:
            raise serializers.ValidationError(
                f"Unsupported document format. Allowed formats: {', '.join(allowed_formats)}"
            )
        
        return value


class DocumentParseResponseSerializer(serializers.Serializer):
    """Serializer for document parsing responses"""
    extracted_text = serializers.CharField()
    word_count = serializers.IntegerField()
    file_name = serializers.CharField()
    file_type = serializers.CharField()
    document_id = serializers.UUIDField()


class QuestionGenerationRequestSerializer(serializers.Serializer):
    """Serializer for question generation requests"""
    topic = serializers.CharField(max_length=500, required=False, allow_blank=True)
    document_content = serializers.CharField(required=False, allow_blank=True)
    session_type = serializers.ChoiceField(
        choices=[('voice_conversation', 'Voice Conversation'), ('objective_quiz', 'Objective Quiz')],
        default='voice_conversation'
    )
    num_questions = serializers.IntegerField(min_value=1, max_value=10, default=1)
    
    def validate(self, data):
        """Validate that either topic or document_content is provided"""
        if not data.get('topic') and not data.get('document_content'):
            raise serializers.ValidationError(
                "Either 'topic' or 'document_content' must be provided"
            )
        return data


class VoiceQuestionResponseSerializer(serializers.Serializer):
    """Serializer for voice question responses"""
    session_id = serializers.UUIDField()
    question_id = serializers.UUIDField()
    question_text = serializers.CharField()
    expected_answer = serializers.CharField()
    explanation = serializers.CharField()
    audio_url = serializers.URLField(allow_null=True)


class ObjectiveQuestionSerializer(serializers.Serializer):
    """Serializer for objective quiz questions"""
    question_id = serializers.UUIDField()
    question_text = serializers.CharField()
    options = serializers.DictField()
    correct_answer = serializers.CharField()
    explanation = serializers.CharField()


class ObjectiveQuizResponseSerializer(serializers.Serializer):
    """Serializer for objective quiz responses"""
    session_id = serializers.UUIDField()
    questions = ObjectiveQuestionSerializer(many=True)


class AnswerEvaluationRequestSerializer(serializers.Serializer):
    """Serializer for answer evaluation requests"""
    question_id = serializers.UUIDField()
    user_answer = serializers.CharField()
    session_id = serializers.UUIDField()


class AnswerEvaluationResponseSerializer(serializers.Serializer):
    """Serializer for answer evaluation responses"""
    is_correct = serializers.BooleanField()
    feedback = serializers.CharField()
    explanation = serializers.CharField()
    confidence = serializers.FloatField()
    audio_url = serializers.URLField(allow_null=True)
    response_id = serializers.UUIDField()


class TextToSpeechRequestSerializer(serializers.Serializer):
    """Serializer for text-to-speech requests"""
    text = serializers.CharField(max_length=5000)
    language = serializers.CharField(max_length=5, default='en')
    accent = serializers.CharField(max_length=10, default='com')
    
    def validate_text(self, value):
        """Validate text for TTS"""
        if not value.strip():
            raise serializers.ValidationError("Text cannot be empty")
        return value


class TextToSpeechResponseSerializer(serializers.Serializer):
    """Serializer for text-to-speech responses"""
    audio_url = serializers.URLField()
    text_length = serializers.IntegerField()
    cached = serializers.BooleanField()


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    error = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField(required=False)