import requests
import json
import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class AIService:
    """Service for handling AI interactions with OpenRouter API using Llama"""
    
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = "meta-llama/llama-3.3-8b-instruct:free"
        self.fallback_model = "google/gemini-2.0-flash-exp:free"
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.timeout = 30  # seconds
    
    def _make_request(self, messages, temperature=0.7, max_tokens=500):
        """Make a request to OpenRouter API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                url=self.base_url,
                headers=headers,
                data=json.dumps(data),
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")
        except KeyError as e:
            raise Exception(f"Unexpected API response format: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")


    def generate_voice_questions(self, content, num_questions=1):
        """Generate informal voice-based questions from content"""
        try:
            prompt = f"""
            Based on the following content, generate {num_questions} informal, conversational questions that would help someone learn and understand the material better.
            
            Content: "{content}"
            
            Requirements:
            - Questions should be informal and conversational (like a friendly tutor)
            - Focus on key concepts and understanding
            - Make questions engaging and thought-provoking
            - Include the expected answer for each question
            - Questions should be suitable for voice conversation
            
            Return your response as JSON in this exact format:
            {{
                "questions": [
                    {{
                        "question": "Your question here?",
                        "expected_answer": "Key points the student should mention",
                        "explanation": "Brief explanation of why this is important"
                    }}
                ]
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are a friendly AI tutor who creates engaging learning questions."},
                {"role": "user", "content": prompt}
            ]
            
            response_content = self._make_request(messages, temperature=0.7, max_tokens=500)
            
            # Parse the JSON response
            content = response_content.strip()
            
            # Extract JSON from response (handle potential markdown formatting)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return result.get('questions', [])
            else:
                raise Exception("Could not parse AI response as JSON")
        
        except Exception as e:
            raise Exception(f"Error generating voice questions: {e}")
    

    def generate_objective_quiz(self, content, num_questions=3):
        """Generate objective multiple-choice questions from content"""
        try:
            prompt = f"""
            Based on the following content, create {num_questions} multiple-choice questions to test understanding.
            
            Content: "{content}"
            
            Requirements:
            - Create challenging but fair questions
            - Each question should have 4 options (A, B, C, D)
            - Include one correct answer and three plausible but incorrect options
            - Focus on key concepts and important details
            - Include brief explanations for the correct answers
            
            Return your response as JSON in this exact format:
            {{
                "quiz": [
                    {{
                        "question": "Your multiple choice question?",
                        "options": {{
                            "A": "Option A text",
                            "B": "Option B text", 
                            "C": "Option C text",
                            "D": "Option D text"
                        }},
                        "correct_answer": "A",
                        "explanation": "Brief explanation of why this answer is correct"
                    }}
                ]
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are an expert quiz creator who designs fair and educational multiple-choice questions."},
                {"role": "user", "content": prompt}
            ]
            
            response_content = self._make_request(messages, temperature=0.7, max_tokens=500)
            
            # Parse the JSON response
            content = response_content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return result.get('quiz', [])
            else:
                raise Exception("Could not parse AI response as JSON")
        
        except Exception as e:
            raise Exception(f"Error generating objective quiz: {e}")
    

    def evaluate_voice_answer(self, question, expected_answer, user_answer):
        """Evaluate user's voice answer against expected answer"""
        try:
            prompt = f"""
            Evaluate if the user's answer demonstrates understanding of the concept.
            
            Question: "{question}"
            Expected Answer: "{expected_answer}"
            User's Answer: "{user_answer}"
            
            Consider:
            - Does the user show understanding of key concepts?
            - Are the main points covered (even if not perfectly)?
            - Is the answer substantially correct?
            - Don't be overly strict on exact wording
            
            Special cases:
            - If user says "I understand" or similar, mark as correct
            - If user asks for clarification, provide help but mark as incorrect
            - Focus on conceptual understanding rather than exact wording
            
            Return your response as JSON in this exact format:
            {{
                "is_correct": true,
                "feedback": "Your encouraging feedback here",
                "explanation": "Brief explanation or clarification if needed",
                "confidence": 0.85
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are a patient and encouraging AI tutor who evaluates student answers fairly."},
                {"role": "user", "content": prompt}
            ]
            
            response_content = self._make_request(messages, temperature=0.3, max_tokens=500)
            
            # Parse the JSON response
            content = response_content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return result
            else:
                raise Exception("Could not parse AI response as JSON")
        
        except Exception as e:
            raise Exception(f"Error evaluating voice answer: {e}")
    

    def generate_follow_up_question(self, content, previous_questions=None):
        """Generate a follow-up question based on content and previous questions"""
        try:
            prev_q_text = ""
            if previous_questions:
                prev_q_text = f"Previous questions asked: {', '.join(previous_questions)}"
            
            prompt = f"""
            Based on the following content, generate ONE new conversational question that hasn't been asked before.
            
            Content: "{content}"
            {prev_q_text}
            
            Requirements:
            - Don't repeat previous questions
            - Focus on different aspects of the content
            - Keep it conversational and engaging
            - Make it appropriate for voice conversation
            
            Return your response as JSON in this exact format:
            {{
                "question": "Your new question here?",
                "expected_answer": "Key points the student should mention",
                "explanation": "Brief explanation of the concept"
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are a creative AI tutor who asks diverse and engaging questions."},
                {"role": "user", "content": prompt}
            ]
            
            response_content = self._make_request(messages, temperature=0.8, max_tokens=400)
            
            # Parse the JSON response
            content = response_content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return result
            else:
                raise Exception("Could not parse AI response as JSON")
        
        except Exception as e:
            raise Exception(f"Error generating follow-up question: {e}")
    

    def summarize_content(self, content, max_words=150):
        """Summarize content for question generation"""
        try:
            prompt = f"""
            Summarize the following content in {max_words} words or less, focusing on the key concepts and main points:
            
            Content: "{content}"
            
            Make the summary clear and comprehensive while staying within the word limit.
            """
            
            messages = [
                {"role": "system", "content": "You are an expert at creating clear, concise summaries."},
                {"role": "user", "content": prompt}
            ]
            
            response_content = self._make_request(messages, temperature=0.3, max_tokens=300)
            
            return response_content.strip()
        
        except Exception as e:
            raise Exception(f"Error summarizing content: {e}")
    

    def check_content_suitability(self, content):
        """Check if content is suitable for learning questions"""
        try:
            # Basic checks
            word_count = len(content.split())
            
            if word_count < 3:
                return False, "Content is too short to generate meaningful questions"
            
            if word_count > 5000:
                return False, "Content is too long. Please provide a shorter excerpt"
            
           
        
        except Exception as e:
            return False, f"Error checking content suitability: {e}"


# Singleton instance
ai_service = AIService()