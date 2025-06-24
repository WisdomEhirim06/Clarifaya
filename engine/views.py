from uuid import UUID
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.conf import settings
import logging
import os

from .models import LearningSession, Question, UserResponse, AudioFile, Document
from .serializers import (
    LearningSessionSerializer, QuestionSerializer,
    UserResponseSerializer, AudioTranscriptionRequestSerializer,
    AudioTranscriptionResponseSerializer, DocumentParseRequestSerializer,
    DocumentParseResponseSerializer, QuestionGenerationRequestSerializer,
    VoiceQuestionResponseSerializer, ObjectiveQuizResponseSerializer,
    AnswerEvaluationRequestSerializer, AnswerEvaluationResponseSerializer,
    TextToSpeechRequestSerializer, TextToSpeechResponseSerializer,
)

from .services.ai_service import ai_service
from .services.tts_service import tts_service
from .services.audio_service import audio_service
from .services.document_parser import document_parser

logger = logging.getLogger(__name__)

# Helper function for error responses
def error_response(message, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """Create standardized error response"""
    error_data = {
        'error': 'Request failed',
        'message': message
    }
    if details:
        error_data['details'] = details
    
    return Response(error_data, status=status_code)


@api_view(['POST'])
def audio_to_text(request):
    """Convert audio to text using Whisper"""
    try:
        serializer = AudioTranscriptionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid audio file", serializer.errors)
        
        audio_file = serializer.validated_data['audio_file']
        
        # Save uploaded audio file
        try:
            audio_path = audio_service.save_uploaded_audio(audio_file)
        except Exception as e:
            return error_response(f"Failed to save audio file: {str(e)}")
        
        # Transcribe audio
        try:
            transcription_result = audio_service.transcribe_audio(audio_path)
            duration = audio_service.get_audio_duration(audio_path)
        except Exception as e:
            # Clean up uploaded file
            if os.path.exists(audio_path):
                os.unlink(audio_path)
            return error_response(f"Failed to transcribe audio: {str(e)}")
        
        # Create AudioFile record
        try:
            with transaction.atomic():
                audio_record = AudioFile.objects.create(
                    file=audio_file,
                    file_type='user_input',
                    transcription=transcription_result['text'],
                    duration=duration,
                    session_id=None  # Will be set later if part of a session
                )
        except Exception as e:
            logger.error(f"Failed to create audio record: {e}")
            # Continue anyway, transcription was successful
            audio_record = None
        
        # Clean up temporary file
        if os.path.exists(audio_path):
            os.unlink(audio_path)
        
        response_data = {
            'transcription': transcription_result['text'],
            'confidence': None,  # Whisper doesn't provide confidence scores directly
            'language': transcription_result.get('language', 'en'),
            'duration': duration,
            'audio_id': audio_record.id if audio_record else None
        }
        
        response_serializer = AudioTranscriptionResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in audio_to_text: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def parse_document(request):
    """Parse uploaded document and extract text"""
    try:
        serializer = DocumentParseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid document file", serializer.errors)
        
        document_file = serializer.validated_data['document_file']
        
        # Extract text from document
        try:
            extraction_result = document_parser.extract_text_from_document(document_file)
        except Exception as e:
            return error_response(f"Failed to parse document: {str(e)}")
        
        # Create Document record
        try:
            with transaction.atomic():
                document_record = Document.objects.create(
                    file=document_file,
                    file_name=extraction_result['file_name'],
                    file_type=extraction_result['file_type'],
                    extracted_text=extraction_result['text'],
                    word_count=extraction_result['statistics']['word_count']
                )
        except Exception as e:
            logger.error(f"Failed to create document record: {e}")
            return error_response("Failed to save document record")
        
        response_data = {
            'extracted_text': extraction_result['text'],
            'word_count': extraction_result['statistics']['word_count'],
            'file_name': extraction_result['file_name'],
            'file_type': extraction_result['file_type'],
            'document_id': document_record.id
        }
        
        response_serializer = DocumentParseResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in parse_document: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def generate_question(request):
    """Generate voice-based questions from topic or document content"""
    try:
        serializer = QuestionGenerationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid request data", serializer.errors)
        
        validated_data = serializer.validated_data
        topic = validated_data.get('topic', '')
        document_content = validated_data.get('document_content', '')
        session_type = validated_data.get('session_type', 'voice_conversation')
        num_questions = validated_data.get('num_questions', 1)
        
        # Determine content for question generation
        content = document_content if document_content else topic
        
        # Check content suitability
        try:
            is_suitable, message = ai_service.check_content_suitability(content)
            if not is_suitable:
                return error_response(message)
        except Exception as e:
            logger.warning(f"Content suitability check failed: {e}")
            # Continue anyway
        
        # Create learning session
        try:
            with transaction.atomic():
                session = LearningSession.objects.create(
                    topic=topic if topic else "Document Content",
                    document_content=document_content,
                    session_type=session_type
                )
        except Exception as e:
            return error_response(f"Failed to create learning session: {str(e)}")
        
        # Generate questions based on session type
        try:
            if session_type == 'voice_conversation':
                ai_questions = ai_service.generate_voice_questions(content, num_questions)
                question_type = 'voice'
            else:
                ai_questions = ai_service.generate_objective_quiz(content, num_questions)
                question_type = 'multiple_choice'
        except Exception as e:
            # Clean up session if question generation fails
            session.delete()
            return error_response(f"Failed to generate questions: {str(e)}")
        
        # Save questions to database
        try:
            with transaction.atomic():
                questions = []
                for i, ai_question in enumerate(ai_questions):
                    if session_type == 'voice_conversation':
                        question = Question.objects.create(
                            session=session,
                            question_text=ai_question['question'],
                            question_type=question_type,
                            expected_answer=ai_question['expected_answer'],
                            explanation=ai_question.get('explanation', ''),
                            order_index=i
                        )
                    else:  # objective_quiz
                        question = Question.objects.create(
                            session=session,
                            question_text=ai_question['question'],
                            question_type=question_type,
                            expected_answer=ai_question['correct_answer'],
                            options=ai_question['options'],
                            explanation=ai_question.get('explanation', ''),
                            order_index=i
                        )
                    questions.append(question)
        except Exception as e:
            # Clean up session if saving questions fails
            session.delete()
            return error_response(f"Failed to save questions: {str(e)}")
        
        # For voice conversations, return first question with audio
        if session_type == 'voice_conversation':
            first_question = questions[0]
            
            # Generate audio for the question
            audio_url = None
            try:
                audio_result = tts_service.generate_speech_for_question(
                    first_question.question_text,
                    first_question.explanation
                )
                audio_url = audio_result['file_url']
            except Exception as e:
                logger.warning(f"Failed to generate TTS for question: {e}")
            
            response_data = {
                'session_id': session.id,
                'question_id': first_question.id,
                'question_text': first_question.question_text,
                'expected_answer': first_question.expected_answer,
                'explanation': first_question.explanation,
                'audio_url': audio_url
            }
            
            response_serializer = VoiceQuestionResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        else:  # objective_quiz
            # Return all questions for quiz mode
            quiz_questions = []
            for question in questions:
                quiz_questions.append({
                    'question_id': question.id,
                    'question_text': question.question_text,
                    'options': question.options,
                    'correct_answer': question.expected_answer,
                    'explanation': question.explanation
                })
            
            response_data = {
                'session_id': session.id,
                'questions': quiz_questions
            }
            
            response_serializer = ObjectiveQuizResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Unexpected error in generate_question: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def evaluate_answer(request):
    """Evaluate user's answer against expected answer"""
    try:
        serializer = AnswerEvaluationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid request data", serializer.errors)
        
        validated_data = serializer.validated_data
        question_id = validated_data['question_id']
        user_answer = validated_data['user_answer']
        session_id = validated_data['session_id']
        
        # Get question and validate session
        try:
            question = get_object_or_404(Question, id=question_id, session_id=session_id)
        except:
            return error_response("Question not found or invalid session")
        
        # Evaluate answer using AI
        try:
            evaluation_result = ai_service.evaluate_voice_answer(
                question.question_text,
                question.expected_answer,
                user_answer
            )
        except Exception as e:
            return error_response(f"Failed to evaluate answer: {str(e)}")
        
        # Save user response
        try:
            with transaction.atomic():
                user_response = UserResponse.objects.create(
                    question=question,
                    user_answer=user_answer,
                    is_correct=evaluation_result['is_correct'],
                    ai_feedback=evaluation_result['feedback']
                )
        except Exception as e:
            logger.error(f"Failed to save user response: {e}")
            return error_response("Failed to save response")
        
        # Generate audio feedback
        audio_url = None
        try:
            audio_result = tts_service.generate_speech_for_feedback(
                evaluation_result['feedback'],
                evaluation_result['is_correct']
            )
            audio_url = audio_result['file_url']
        except Exception as e:
            logger.warning(f"Failed to generate TTS for feedback: {e}")
        
        response_data = {
            'is_correct': evaluation_result['is_correct'],
            'feedback': evaluation_result['feedback'],
            'explanation': evaluation_result.get('explanation', ''),
            'confidence': evaluation_result.get('confidence', 0.0),
            'audio_url': audio_url,
            'response_id': user_response.id
        }
        
        response_serializer = AnswerEvaluationResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in evaluate_answer: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_next_question(request, session_id):
    """Get the next question in a learning session"""
    try:
        # session_id is already a UUID object from URL converter, no need to re-convert
        # Just validate it exists
        try:
            session = LearningSession.objects.get(id=session_id)
        except LearningSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "message": f"No session exists with ID: {session_id}"
            }, status=status.HTTP_404_NOT_FOUND)

        # Get current question ID from query params
        current_question_id = request.query_params.get('current_question_id')
        
        # Get next question
        if current_question_id:
            try:
                # Validate current_question_id is a valid UUID
                current_question_uuid = UUID(current_question_id)
                current_question = Question.objects.get(id=current_question_uuid, session=session)
                next_question = Question.objects.filter(
                    session=session,
                    order_index__gt=current_question.order_index
                ).order_by('order_index').first()
            except (ValueError, Question.DoesNotExist):
                return Response({
                    "error": "Question not found",
                    "message": "The specified current question does not exist or is invalid"
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Get first question if no current question specified
            next_question = Question.objects.filter(session=session).order_by('order_index').first()

        if not next_question:
            return Response({
                "session_complete": True,
                "message": "All questions have been answered",
                "session_id": str(session.id)
            }, status=status.HTTP_200_OK)

        # For voice conversations, include audio URL if available
        audio_url = None
        if session.session_type == 'voice_conversation':
            try:
                audio_result = tts_service.generate_speech_for_question(
                    next_question.question_text,
                    next_question.explanation or ""
                )
                audio_url = audio_result['file_url']
            except Exception as e:
                logger.warning(f"Failed to generate TTS for question: {e}")

        response_data = {
            "session_id": str(session.id),
            "session_type": session.session_type,
            "question": {
                "id": str(next_question.id),
                "text": next_question.question_text,
                "type": next_question.question_type,
                "expected_answer": next_question.expected_answer,
                "explanation": next_question.explanation,
                "options": next_question.options,  # Include for multiple choice
                "order_index": next_question.order_index
            },
            "audio_url": audio_url
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in get_next_question: {str(e)}")
        return Response({
            "error": "Internal server error",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_session_details(request, session_id):
    """Get details of a learning session"""
    try:
        # session_id is already a UUID object from URL converter
        try:
            session = LearningSession.objects.get(id=session_id)
        except LearningSession.DoesNotExist:
            return Response({
                "error": "Session not found",
                "message": f"No session exists with ID: {session_id}"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get questions with responses - use select_related and prefetch_related for optimization
        questions = Question.objects.filter(session=session).prefetch_related(
            'responses'
        ).order_by('order_index')

        # Calculate session statistics
        total_questions = questions.count()
        answered_questions = sum(1 for q in questions if q.responses.exists())
        correct_answers = sum(1 for q in questions 
                            for r in q.responses.all() if r.is_correct)

        # Prepare response data
        session_data = {
            "id": str(session.id),
            "topic": session.topic,
            "session_type": session.session_type,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "statistics": {
                "total_questions": total_questions,
                "answered_questions": answered_questions,
                "correct_answers": correct_answers,
                "accuracy": (correct_answers / answered_questions * 100) if answered_questions > 0 else 0
            },
            "questions": [{
                "id": str(q.id),
                "text": q.question_text,
                "type": q.question_type,
                "expected_answer": q.expected_answer,
                "options": q.options,
                "explanation": q.explanation,
                "order_index": q.order_index,
                "responses": [{
                    "id": str(r.id),
                    "answer": r.user_answer,
                    "is_correct": r.is_correct,
                    "ai_feedback": r.ai_feedback,
                    "created_at": r.created_at.isoformat()
                } for r in q.responses.all()]
            } for q in questions]
        }

        return Response(session_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in get_session_details: {str(e)}")
        return Response({
            "error": "Internal server error", 
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def text_to_speech(request):
    """Convert text to speech using gTTS"""
    try:
        serializer = TextToSpeechRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid request data", serializer.errors)
        
        validated_data = serializer.validated_data
        text = validated_data['text']
        language = validated_data.get('language', 'en')
        accent = validated_data.get('accent', 'com')
        
        # Generate speech
        try:
            audio_result = tts_service.text_to_speech(text, language, accent)
        except Exception as e:
            return error_response(f"Failed to generate speech: {str(e)}")
        
        response_data = {
            'audio_url': audio_result['file_url'],
            'text_length': audio_result['text_length'],
            'cached': audio_result['cached']
        }
        
        response_serializer = TextToSpeechResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in text_to_speech: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def delete_session(request, session_id):
    """Delete a learning session and all related data"""
    try:
        session = get_object_or_404(LearningSession, id=session_id)
        session.delete()
        
        return Response({
            'message': 'Session deleted successfully',
            "session_id": str(session_id)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in delete_session: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_supported_languages(request):
    """Get supported languages for TTS"""
    try:
        languages = tts_service.get_supported_languages()
        accents = tts_service.get_english_accents()
        
        return Response({
            'languages': languages,
            'english_accents': accents
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_supported_languages: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cleanup_cache(request):
    """Manually trigger cleanup of old cache files"""
    try:
        max_age_hours = request.data.get('max_age_hours', 24)
        tts_service.cleanup_old_cache_files(max_age_hours)
        
        return Response({
            'message': f'Cache cleanup completed for files older than {max_age_hours} hours'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in cleanup_cache: {e}")
        return error_response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
