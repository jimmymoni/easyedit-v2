"""
AI Chat Handler Service
Provides conversational interface for God Mode AI editing
"""
import logging
import re
from typing import Dict, List, Any, Optional
from models.timeline import Timeline

logger = logging.getLogger(__name__)


class AIChatHandler:
    """Handles conversational AI interactions for timeline editing"""

    def __init__(self):
        self.conversation_history = []

    def analyze_message(self, message: str, timeline: Timeline, transcription_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze user message and determine intent

        Args:
            message: User's message
            timeline: Current timeline object
            transcription_data: Optional transcription with timestamps

        Returns:
            Dict with conversation response including options if needed
        """
        try:
            message_lower = message.lower().strip()
            logger.info(f"Analyzing chat message: {message}")

            # Detect intent
            intent = self._detect_intent(message_lower)

            if intent == 'montage':
                return self._handle_montage_request(message, message_lower, timeline, transcription_data)
            elif intent == 'remove_silence':
                return self._handle_silence_request(message_lower, timeline)
            elif intent == 'filter_speaker':
                return self._handle_speaker_request(message_lower, timeline, transcription_data)
            elif intent == 'unclear':
                return self._ask_for_clarification(message)
            else:
                return {
                    'needs_confirmation': False,
                    'message': f"I understand you want to {intent}, but I need more information. Can you be more specific?",
                    'options': []
                }

        except Exception as e:
            logger.error(f"Error analyzing message: {str(e)}")
            return {
                'needs_confirmation': False,
                'message': f"Sorry, I encountered an error: {str(e)}",
                'options': []
            }

    def _detect_intent(self, message: str) -> str:
        """Detect user intent from message"""
        # Montage/compilation keywords
        if any(word in message for word in ['montage', 'stack', 'compile', 'gather', 'collect', 'every time', 'find all']):
            return 'montage'

        # Silence removal keywords
        if any(phrase in message for phrase in ['remove silence', 'cut silence', 'delete silence', 'silence']):
            return 'remove_silence'

        # Speaker filter keywords
        if any(word in message for word in ['speaker', 'only speaker', 'filter speaker']):
            return 'filter_speaker'

        # If message is very short or unclear
        if len(message.split()) < 3:
            return 'unclear'

        return 'unknown'

    def _handle_montage_request(self, original_message: str, message_lower: str, timeline: Timeline, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Handle montage creation request"""
        # Extract search phrase
        search_phrase = self._extract_search_phrase(original_message)

        if search_phrase == "unknown phrase":
            return {
                'needs_confirmation': False,
                'message': "I want to create a montage, but I couldn't identify the phrase. Could you put it in quotes? For example: \"money in the bank\"",
                'options': []
            }

        # Search for phrase in transcription
        if not transcription_data:
            return {
                'needs_confirmation': False,
                'message': "I need transcription data to create a montage. Make sure your job has transcription enabled.",
                'options': []
            }

        # Find instances
        instances = self._find_phrase_instances(search_phrase, transcription_data)

        if len(instances) == 0:
            return {
                'needs_confirmation': False,
                'message': f"I couldn't find any instances of \"{search_phrase}\" in the transcription. Try a different phrase?",
                'options': []
            }

        # Calculate durations for each cut mode
        tight_duration = sum(inst['duration'] for inst in instances)
        normal_duration = tight_duration + (len(instances) * 0.2)  # 0.1s before + 0.1s after
        loose_duration = tight_duration + (len(instances) * 1.0)   # 0.5s before + 0.5s after

        # Create response with options
        return {
            'needs_confirmation': True,
            'message': f"I found **{len(instances)} instances** of \"{search_phrase}\" in your timeline.\n\nHow would you like me to cut this montage?",
            'options': [
                {
                    'id': 'tight',
                    'label': '🎯 Tight Cut',
                    'description': f'{tight_duration:.1f}s total - Only the exact phrase, no padding',
                    'params': {
                        'operation': 'montage',
                        'phrase': search_phrase,
                        'mode': 'tight',
                        'prompt': f'tight montage "{search_phrase}"'
                    }
                },
                {
                    'id': 'normal',
                    'label': '📐 Normal Cut',
                    'description': f'{normal_duration:.1f}s total - 0.1s padding for breathing room',
                    'params': {
                        'operation': 'montage',
                        'phrase': search_phrase,
                        'mode': 'normal',
                        'prompt': f'montage "{search_phrase}"'
                    }
                },
                {
                    'id': 'loose',
                    'label': '🎬 Loose Cut',
                    'description': f'{loose_duration:.1f}s total - 0.5s padding for natural flow',
                    'params': {
                        'operation': 'montage',
                        'phrase': search_phrase,
                        'mode': 'loose',
                        'prompt': f'loose montage "{search_phrase}"'
                    }
                }
            ],
            'preview_data': {
                'instances': instances,
                'phrase': search_phrase
            }
        }

    def _handle_silence_request(self, message: str, timeline: Timeline) -> Dict[str, Any]:
        """Handle silence removal request"""
        # Extract threshold if specified
        threshold = self._extract_duration_threshold(message)

        return {
            'needs_confirmation': True,
            'message': f"I'll remove silence gaps longer than {threshold}s. Is this correct?",
            'options': [
                {
                    'id': 'confirm',
                    'label': '✅ Yes, remove silence',
                    'description': f'Remove pauses longer than {threshold} seconds',
                    'params': {
                        'operation': 'remove_silence',
                        'threshold': threshold,
                        'prompt': f'remove silence longer than {threshold}s'
                    }
                },
                {
                    'id': 'change_threshold',
                    'label': '🔧 Different threshold',
                    'description': 'Specify a different duration',
                    'params': None
                }
            ]
        }

    def _handle_speaker_request(self, message: str, timeline: Timeline, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Handle speaker filter request"""
        if not transcription_data:
            return {
                'needs_confirmation': False,
                'message': "I need transcription with speaker diarization to filter by speaker.",
                'options': []
            }

        # Extract speaker number
        speaker_match = re.search(r'speaker\s*(\d+)', message)
        if speaker_match:
            speaker_num = int(speaker_match.group(1))
            return {
                'needs_confirmation': True,
                'message': f"Keep only Speaker {speaker_num} and remove all others?",
                'options': [
                    {
                        'id': 'confirm',
                        'label': f'✅ Yes, keep only Speaker {speaker_num}',
                        'description': 'Remove all other speakers',
                        'params': {
                            'operation': 'filter_speaker',
                            'speaker': speaker_num,
                            'prompt': f'keep only speaker {speaker_num}'
                        }
                    }
                ]
            }

        return {
            'needs_confirmation': False,
            'message': "Which speaker do you want to keep? (e.g., 'Speaker 1', 'Speaker 2')",
            'options': []
        }

    def _ask_for_clarification(self, message: str) -> Dict[str, Any]:
        """Ask user for clarification when intent is unclear"""
        return {
            'needs_confirmation': False,
            'message': "I'm not sure what you want me to do. Here are some things I can help with:\n\n• **Montage** - Compile all instances of a phrase\n• **Remove Silence** - Cut out long pauses\n• **Filter Speaker** - Keep only one speaker\n• **Summarize** - Shorten to a target duration\n\nWhat would you like to do?",
            'options': []
        }

    def _extract_search_phrase(self, message: str) -> str:
        """Extract search phrase from message"""
        # Look for phrases in quotes
        quoted = re.findall(r'["\'](.+?)["\']', message)
        if quoted:
            return quoted[0]

        # Look for common patterns
        patterns = [
            r'(?:stack|compile|gather|collect)\s+(.+?)(?:\s+leave|\s+remove|$)',
            r'montage\s+(?:of\s+)?(.+?)(?:\s+leave|\s+remove|$)',
            r'every time.*?(?:say|says)\s+(.+?)(?:\s|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "unknown phrase"

    def _extract_duration_threshold(self, message: str) -> float:
        """Extract duration threshold from message"""
        match = re.search(r'(\d+\.?\d*)\s*(?:second|sec|s)', message)
        if match:
            return float(match.group(1))
        return 2.0  # Default

    def _find_phrase_instances(self, search_phrase: str, transcription_data: Dict) -> List[Dict]:
        """Find all instances of phrase in transcription"""
        instances = []
        search_phrase_lower = search_phrase.lower().strip()
        segments = transcription_data.get('segments', [])

        for segment in segments:
            segment_text = segment.get('text', '').lower()

            if search_phrase_lower in segment_text:
                # Try to get word-level timing
                words = segment.get('words', [])
                phrase_words = search_phrase_lower.split()

                if words and len(words) >= len(phrase_words):
                    # Word-level search
                    for i in range(len(words) - len(phrase_words) + 1):
                        word_sequence = ' '.join([w.get('word', '').strip().lower().strip('.,!?;:')
                                                 for w in words[i:i+len(phrase_words)]])

                        if search_phrase_lower in word_sequence or word_sequence in search_phrase_lower:
                            start_time = words[i].get('start', 0)
                            end_time = words[i + len(phrase_words) - 1].get('end', 0)

                            instances.append({
                                'start': start_time,
                                'end': end_time,
                                'duration': end_time - start_time,
                                'text': ' '.join([w.get('word', '') for w in words[i:i+len(phrase_words)]]),
                                'speaker': segment.get('speaker', 'UNKNOWN')
                            })
                else:
                    # Segment-level fallback
                    instances.append({
                        'start': segment.get('start_time', 0),
                        'end': segment.get('end_time', 0),
                        'duration': segment.get('end_time', 0) - segment.get('start_time', 0),
                        'text': segment.get('text', ''),
                        'speaker': segment.get('speaker', 'UNKNOWN')
                    })

        return instances

    def generate_preview(self, params: Dict, timeline: Timeline, transcription_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate preview of what will happen

        Args:
            params: Operation parameters
            timeline: Current timeline
            transcription_data: Optional transcription

        Returns:
            Preview data with clip list, duration, etc.
        """
        operation = params.get('operation')

        if operation == 'montage':
            phrase = params.get('phrase')
            instances = self._find_phrase_instances(phrase, transcription_data)

            mode = params.get('mode', 'normal')
            padding_before = 0.0 if mode == 'tight' else (0.1 if mode == 'normal' else 0.5)
            padding_after = 0.0 if mode == 'tight' else (0.1 if mode == 'normal' else 0.5)

            total_duration = sum(inst['duration'] + padding_before + padding_after for inst in instances)

            return {
                'operation': 'montage',
                'phrase': phrase,
                'mode': mode,
                'clips': [
                    {
                        'index': i + 1,
                        'start': inst['start'] - padding_before,
                        'end': inst['end'] + padding_after,
                        'duration': inst['duration'] + padding_before + padding_after,
                        'text': inst['text'],
                        'speaker': inst['speaker']
                    }
                    for i, inst in enumerate(instances)
                ],
                'total_clips': len(instances),
                'total_duration': total_duration,
                'compression': (1 - (total_duration / (timeline.duration or 1))) * 100
            }

        return {
            'operation': operation,
            'message': 'Preview not available for this operation'
        }
