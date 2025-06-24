from django.db import models
import uuid

class LearningSession(models.Model):
    """Model to track learning sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=500, blank=True, null=True)
    document_content = models.TextField(blank=True, null=True)
    session_type = models.CharField(
        max_length=20,
        choices=[
            ('voice_conversation', 'Voice Conversation'),
            ('objective_quiz', 'Objective Quiz'),
        ],
        default='voice_conversation'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.id} - {self.topic or 'Document'}"


class Question(models.Model):
    """Model to store generated questions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LearningSession, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=[
            ('voice', 'Voice Question'),
            ('multiple_choice', 'Multiple Choice'),
        ],
        default='voice'
    )
    expected_answer = models.TextField(blank=True, null=True)
    options = models.JSONField(blank=True, null=True)  # For multiple choice questions
    explanation = models.TextField(blank=True, null=True)
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order_index', 'created_at']

    def __str__(self):
        return f"Question {self.order_index + 1} - {self.session.topic or 'Document'}"


class UserResponse(models.Model):
    """Model to track user responses"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='responses')
    user_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    ai_feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Response to {self.question} - {'Correct' if self.is_correct else 'Incorrect'}"


class AudioFile(models.Model):
    """Model to track audio files"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='uploads/audio/')
    file_type = models.CharField(
        max_length=20,
        choices=[
            ('user_input', 'User Input'),
            ('ai_response', 'AI Response'),
        ]
    )

    session = models.ForeignKey(LearningSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='audio_files')
    question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name='audio_files')
    response = models.ForeignKey(UserResponse, on_delete=models.SET_NULL, null=True, blank=True, related_name='audio_files')
    
    transcription = models.TextField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Audio {self.id} - {self.file_type}"


class Document(models.Model):
    """Model to track uploaded documents"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='uploads/documents/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)
    extracted_text = models.TextField(blank=True, null=True)
    word_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document: {self.file_name}"
