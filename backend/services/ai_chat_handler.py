"""
AI Chat Handler for God Mode
Detects user intent from natural language prompts using Replicate GPT-4o
"""
import logging
import replicate
import json
import re
import os
from config import Config

logger = logging.getLogger(__name__)


class AIChatHandler:
    """Handles natural language intent detection for AI editing"""

    def __init__(self):
        """Initialize with system prompt"""
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load God Mode system prompt from file"""
        try:
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'system_prompts',
                'godmode_adaptive.txt'
            )
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            return "You are a video editing AI assistant. Detect user intent from their editing requests."

    def _detect_intent_keywords(self, message: str, transcription: dict = None) -> dict:
        """
        Detect editing intent from user message using Replicate GPT-4o

        Args:
            message: User's natural language editing request
            transcription: Video transcription data for context (optional)

        Returns:
            {
                'intent': str,  # short_form, highlight, montage, remove_repeated_takes, etc.
                'confidence': float,  # 0.0-1.0
                'duration': int or None,  # target duration in seconds
                'platform': str or None,  # instagram, tiktok, etc.
                'content_type': str,  # engaging, informative, etc.
                'reasoning': str,  # why this intent was chosen
                'clarification_needed': bool,
                'clarification_question': str or None,
                'params': dict  # operation-specific parameters
            }
        """
        try:
            # Build context for GPT
            context_info = ""
            if transcription:
                duration = transcription.get('duration', 0)
                segment_count = len(transcription.get('segments', []))
                context_info = f"\n\nVideo context: {duration:.1f}s duration, {segment_count} segments"

            # Call Replicate GPT-4o for intent detection
            prompt = f"""{self.system_prompt}

User request: "{message}"{context_info}

Analyze this request and return ONLY a JSON object following the Intent Detection Output Format specified in your system prompt.
Do not include any text before or after the JSON. Return only valid JSON.
"""

            logger.info(f"Calling Replicate GPT-4o for intent detection: '{message}'")

            output = replicate.run(
                "openai/gpt-4o",
                input={
                    "prompt": prompt,
                    "max_tokens": 500,
                    "temperature": 0.3,  # Low temperature for consistent intent detection
                }
            )

            # Parse GPT output
            response_text = "".join(output)
            logger.debug(f"GPT-4o response: {response_text}")

            # Extract JSON from response
            # Try to find JSON object in response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Try without code block
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    # Fallback to keyword-based detection
                    logger.warning("GPT didn't return valid JSON, using keyword fallback")
                    result = self._keyword_fallback_detection(message)

            # Ensure all required fields exist
            if 'intent' not in result:
                logger.warning("GPT response missing 'intent' field, using fallback")
                result = self._keyword_fallback_detection(message)

            # Add operation-specific parameters
            result['params'] = self._extract_params(result.get('intent', ''), message)

            logger.info(f"Detected intent: {result.get('intent')} (confidence: {result.get('confidence', 0.0):.2f})")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Response was: {response_text if 'response_text' in locals() else 'N/A'}")
            return self._keyword_fallback_detection(message)
        except Exception as e:
            logger.error(f"Error in intent detection: {e}", exc_info=True)
            # Fallback to keyword-based detection
            return self._keyword_fallback_detection(message)

    def _keyword_fallback_detection(self, message: str) -> dict:
        """Simple keyword-based fallback for intent detection when GPT fails"""
        message_lower = message.lower()

        # Check for highlight keywords FIRST (before short-form to avoid false positives)
        if any(kw in message_lower for kw in ['highlight', 'best', 'important', 'key', 'summary']):
            # Extract duration if mentioned
            duration_match = re.search(r'(\d+)\s*(?:s|sec|second)', message_lower)
            duration = int(duration_match.group(1)) if duration_match else 60
            return {
                'intent': 'highlight',
                'confidence': 0.8,
                'duration': duration,
                'content_type': 'engaging',
                'reasoning': 'Detected highlight/summary keywords',
                'clarification_needed': False,
                'clarification_question': None,
                'params': {'target_duration': duration}
            }

        # Check for short-form keywords
        if any(kw in message_lower for kw in ['instagram', 'reel', 'tiktok', 'short', 'viral', 'compact', 'punchy']):
            duration = 60 if 'instagram' in message_lower else 30
            return {
                'intent': 'short_form',
                'confidence': 0.7,
                'duration': duration,
                'platform': 'instagram' if 'instagram' in message_lower else 'tiktok',
                'content_type': 'engaging',
                'reasoning': 'Detected short-form social media keywords',
                'clarification_needed': False,
                'clarification_question': None,
                'params': {'target_duration': duration}
            }

        # Check for silence removal
        if any(kw in message_lower for kw in ['silence', 'pause', 'tighten', 'cut silence', 'remove silence']):
            return {
                'intent': 'remove_silence',
                'confidence': 0.9,
                'reasoning': 'Detected silence removal keywords',
                'clarification_needed': False,
                'clarification_question': None,
                'params': {'silence_threshold': 2.0}
            }

        # Check for repeated takes
        if any(kw in message_lower for kw in ['repeat', 'duplicate', 'takes', 'false start', 'repeated']):
            return {
                'intent': 'remove_repeated_takes',
                'confidence': 0.9,
                'reasoning': 'Detected repeated take removal keywords',
                'clarification_needed': False,
                'clarification_question': None,
                'params': {}
            }

        # Check for speaker filtering
        if any(kw in message_lower for kw in ['speaker', 'only', 'filter', 'just']):
            # Check if speaker ID is mentioned
            speaker_match = re.search(r'speaker\s*(\d+)', message_lower)
            if speaker_match:
                return {
                    'intent': 'filter_speaker',
                    'confidence': 0.9,
                    'reasoning': f'Detected speaker filter for Speaker {speaker_match.group(1)}',
                    'clarification_needed': False,
                    'clarification_question': None,
                    'params': {'speaker_id': int(speaker_match.group(1))}
                }
            else:
                return {
                    'intent': 'filter_speaker',
                    'confidence': 0.7,
                    'reasoning': 'Detected speaker filtering keywords',
                    'clarification_needed': True,
                    'clarification_question': 'Which speaker would you like to keep? (e.g., Speaker 0, Speaker 1)',
                    'params': {}
                }

        # Default: assume highlight
        return {
            'intent': 'highlight',
            'confidence': 0.5,
            'reasoning': 'Could not determine specific intent, defaulting to highlight reel',
            'clarification_needed': True,
            'clarification_question': 'What would you like me to do with this video? (e.g., create a highlight reel, remove silence, filter by speaker)',
            'params': {}
        }

    def _extract_params(self, intent: str, message: str) -> dict:
        """Extract operation-specific parameters from message"""
        params = {}

        if intent == 'short_form' or intent == 'highlight':
            # Extract target duration if mentioned
            duration_match = re.search(r'(\d+)\s*(?:s|sec|second)', message.lower())
            if duration_match:
                params['target_duration'] = int(duration_match.group(1))
            elif intent == 'short_form':
                # Default durations for platforms
                if 'instagram' in message.lower():
                    params['target_duration'] = 60
                elif 'tiktok' in message.lower():
                    params['target_duration'] = 30
                else:
                    params['target_duration'] = 60

        elif intent == 'remove_silence':
            # Extract silence threshold if mentioned
            threshold_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:s|sec|second)', message.lower())
            if threshold_match:
                params['silence_threshold'] = float(threshold_match.group(1))
            else:
                params['silence_threshold'] = 2.0  # Default 2 seconds

        elif intent == 'filter_speaker':
            # Extract speaker ID if mentioned
            speaker_match = re.search(r'speaker\s*(\d+)', message.lower())
            if speaker_match:
                params['speaker_id'] = int(speaker_match.group(1))

        return params
