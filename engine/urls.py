from django.urls import path
from . import views

urlpatterns = [
    # Audio processing endpoints
    path('audio/transcribe/', views.audio_to_text, name='audio_to_text'),
    path('audio/text-to-speech/', views.text_to_speech, name='text_to_speech'),
    
    # Document processing endpoints
    path('documents/parse/', views.parse_document, name='parse_document'),
    
    # Question generation and management endpoints
    path('questions/generate/', views.generate_question, name='generate_question'),
    path('questions/next/<uuid:session_id>/', views.get_next_question, name='get_next_question'),
    path('questions/evaluate/', views.evaluate_answer, name='evaluate_answer'),
    
    # Session management endpoints
    path('sessions/<uuid:session_id>/', views.get_session_details, name='get_session_details'),
    path('sessions/<uuid:session_id>/delete/', views.delete_session, name='delete_session'),
    
    # Utility endpoints
    path('languages/supported/', views.get_supported_languages, name='get_supported_languages'),
    path('cache/cleanup/', views.cleanup_cache, name='cleanup_cache'),
]