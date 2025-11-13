"""
AI Chat Handler Service
Provides conversational interface for God Mode AI editing
"""
import logging
import re
import json
import os
from typing import Dict, List, Any, Optional
from models.timeline import Timeline
import replicate
from config import Config

logger = logging.getLogger(__name__)


class AIChatHandler:
    """Handles conversational AI interactions for timeline editing"""

    def __init__(self):
        self.conversation_history = []
        # Use DeepSeek-R1 for reliable JSON output and better reasoning
        self.replicate_token = Config.REPLICATE_API_TOKEN
        # DeepSeek-R1 has native JSON mode support
        self.llm_model = "deepseek-ai/deepseek-r1"

        if not self.replicate_token:
            logger.warning("No REPLICATE_API_TOKEN found - AI features will be limited")

        # Load God Mode system prompt
        system_prompt_path = os.path.join(os.path.dirname(__file__), '..', 'system_prompts', 'godmode_adaptive.txt')
        try:
            with open(system_prompt_path, 'r', encoding='utf-8') as f:
                self.god_mode_prompt = f.read()
        except Exception as e:
            logger.warning(f"Could not load God Mode system prompt: {e}")
            self.god_mode_prompt = "You are a helpful AI assistant for video editing."

    def get_intelligent_greeting(self, content_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate intelligent greeting based on content analysis

        Args:
            content_analysis: Content analysis data from ContentAnalyzer

        Returns:
            Dict with greeting message and repurposing options
        """
        try:
            if not content_analysis:
                # No analysis available - generic greeting
                return {
                    'needs_confirmation': False,
                    'message': "👋 How can I help you edit this timeline?\n\nI can help you:\n• Create **Instagram Reels / TikTok** videos\n• Make **montages** of specific phrases\n• Remove **silence** and long pauses\n• Filter by **speaker**\n\nWhat would you like to do?",
                    'options': []
                }

            # Extract analysis data from new knowledge base structure
            content_type = content_analysis.get('content_type', 'unknown')
            main_topic = content_analysis.get('main_topic', 'your content')
            features_discussed = content_analysis.get('features_discussed', [])
            key_moments = content_analysis.get('key_moments', [])

            # Build intelligent greeting
            greeting_parts = []

            if content_type and content_type != 'unknown':
                greeting_parts.append(f"🎯 I've analyzed your **{content_type}** content about **{main_topic}**.")
            else:
                greeting_parts.append(f"🎯 I've analyzed your content about **{main_topic}**.")

            # Show features if available
            if features_discussed:
                greeting_parts.append(f"\n\nI found **{len(features_discussed)} main features/topics** you discussed:")
                for feature in features_discussed[:3]:  # Show first 3
                    duration_min = feature.get('duration', 0) / 60
                    greeting_parts.append(f"\n• **{feature.get('name')}** ({duration_min:.1f}min)")

                if len(features_discussed) > 3:
                    greeting_parts.append(f"\n... and {len(features_discussed) - 3} more")

                greeting_parts.append("\n\n**Click a feature to extract it, or describe what you want!**")
            else:
                greeting_parts.append("\n\nWhat would you like to do with this timeline?")

            greeting_message = "".join(greeting_parts)

            # Create clickable options for each feature
            formatted_options = []
            for feature in features_discussed:
                duration_min = feature.get('duration', 0) / 60
                formatted_options.append({
                    'id': f"extract_feature_{feature.get('id', 'unknown')}",
                    'label': f"Extract: {feature.get('name')}",
                    'description': f"{duration_min:.1f}min - {feature.get('description', 'No description')}",
                    'params': {
                        'operation': 'feature_extraction',
                        'feature_id': feature.get('id'),
                        'feature_name': feature.get('name'),
                        'start_time': feature.get('start_time'),
                        'end_time': feature.get('end_time'),
                        'prompt': f"Extract {feature.get('name')} feature"
                    }
                })

            return {
                'needs_confirmation': True if features_discussed else False,
                'message': greeting_message,
                'options': formatted_options,
                'content_analysis': content_analysis  # Pass through for reference
            }

        except Exception as e:
            logger.error(f"Error generating intelligent greeting: {str(e)}")
            # Fallback to generic greeting
            return {
                'needs_confirmation': False,
                'message': "👋 How can I help you edit this timeline?",
                'options': []
            }

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

            # Detect intent using GPT-4
            intent_data = self._detect_intent(message, transcription_data)
            intent = intent_data.get('intent')

            logger.info(f"Detected intent: {intent} ({intent_data.get('reasoning', 'No reasoning provided')})")

            # Route to appropriate handler based on intent
            if intent == 'short_form':
                return self._handle_short_form_request(message, intent_data, timeline, transcription_data)
            elif intent == 'montage':
                return self._handle_montage_request(message, message_lower, timeline, transcription_data)
            elif intent == 'remove_silence':
                return self._handle_silence_request(message_lower, timeline)
            elif intent == 'filter_speaker':
                return self._handle_speaker_request(message_lower, timeline, transcription_data)
            elif intent == 'unclear' or intent_data.get('clarification_needed'):
                return self._ask_for_clarification(message, intent_data)
            else:
                # Unknown intent
                return {
                    'needs_confirmation': False,
                    'message': f"I understand you want to {intent}, but I need more information. Can you be more specific?\n\nHere are some things I can help with:\n• **Instagram Reel / TikTok** - Create engaging short-form content\n• **Montage** - Compile all instances of a phrase\n• **Remove Silence** - Cut out long pauses\n• **Filter Speaker** - Keep only one speaker",
                    'options': []
                }

        except Exception as e:
            logger.error(f"Error analyzing message: {str(e)}")
            return {
                'needs_confirmation': False,
                'message': f"Sorry, I encountered an error: {str(e)}",
                'options': []
            }

    def _detect_intent(self, message: str, transcription_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Use GPT-4 to detect user intent semantically

        Returns:
            Dict with intent, confidence, duration, content_type, platform, reasoning, etc.
        """
        # Fallback to keyword matching if Replicate token not available
        if not self.replicate_token:
            logger.warning("Replicate token not available, using keyword-based intent detection")
            return self._detect_intent_keywords(message)

        try:
            # Build context for GPT-4
            context = f"Audio duration: {transcription_data.get('duration', 'unknown')}s" if transcription_data else "No transcription available"

            # Call GPT-4 to analyze intent
            # Use Replicate LLaMA 3.1 70B for intent detection
            prompt = f"{self.god_mode_prompt}\n\nContext: {context}\n\nUser request: {message}\n\nAnalyze the user's intent and respond with ONLY a JSON object (no markdown, no explanation)."

            output = replicate.run(
                self.llm_model,
                input={
                    "prompt": prompt,
                    "max_tokens": 2048,
                    "temperature": 0.1,
                    "top_p": 1.0
                }
            )

            # Replicate returns an iterator, concatenate all chunks
            response_text = "".join(output).strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            intent_data = json.loads(response_text)

            logger.info(f"LLaMA 3.1 70B detected intent: {intent_data.get('intent')} (confidence: {intent_data.get('confidence', 0)})")

            return intent_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLaMA response as JSON: {e}. Response: {response_text}")
            return self._detect_intent_keywords(message)
        except Exception as e:
            logger.error(f"Error in LLaMA intent detection: {e}")
            return self._detect_intent_keywords(message)

    def _detect_intent_keywords(self, message: str) -> Dict[str, Any]:
        """Fallback keyword-based intent detection"""
        message_lower = message.lower()

        # Social media / short-form keywords
        if any(word in message_lower for word in ['instagram', 'reel', 'reels', 'tiktok', 'short', 'shorts', 'viral', 'social', 'compact', 'punchy']):
            return {
                'intent': 'short_form',
                'confidence': 0.7,
                'duration': 60,
                'content_type': 'engaging',
                'platform': 'instagram' if 'instagram' in message_lower else 'tiktok' if 'tiktok' in message_lower else 'social_media',
                'reasoning': 'Detected social media keywords'
            }

        # Montage/compilation keywords
        if any(word in message_lower for word in ['montage', 'stack', 'compile', 'gather', 'collect', 'every time', 'find all']):
            return {
                'intent': 'montage',
                'confidence': 0.8,
                'reasoning': 'Detected montage keywords'
            }

        # Silence removal keywords
        if any(phrase in message_lower for phrase in ['remove silence', 'cut silence', 'delete silence', 'silence']):
            return {
                'intent': 'remove_silence',
                'confidence': 0.8,
                'reasoning': 'Detected silence removal keywords'
            }

        # Speaker filter keywords
        if any(word in message_lower for word in ['speaker', 'only speaker', 'filter speaker']):
            return {
                'intent': 'filter_speaker',
                'confidence': 0.8,
                'reasoning': 'Detected speaker filter keywords'
            }

        # If message is very short or unclear
        if len(message.split()) < 3:
            return {
                'intent': 'unclear',
                'confidence': 0.5,
                'clarification_needed': True,
                'clarification_question': 'Could you provide more details about what you want me to do?'
            }

        return {
            'intent': 'unknown',
            'confidence': 0.3,
            'clarification_needed': True,
            'clarification_question': 'I\'m not sure what you want me to do. Can you be more specific?'
        }

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

    def _handle_short_form_request(self, message: str, intent_data: Dict, timeline: Timeline, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Handle short-form content creation (Instagram Reels, TikTok, etc.)"""
        if not transcription_data:
            return {
                'needs_confirmation': False,
                'message': "I need transcription data to create short-form content. Make sure your job has transcription enabled.",
                'options': []
            }

        if not self.replicate_token:
            return {
                'needs_confirmation': False,
                'message': "Replicate API is required for short-form content creation. Please configure your REPLICATE_API_TOKEN.",
                'options': []
            }

        # Extract parameters from intent
        duration = intent_data.get('duration', 60)
        content_type = intent_data.get('content_type', 'engaging')
        platform = intent_data.get('platform', 'instagram')

        logger.info(f"Creating short-form content: {duration}s {content_type} for {platform}")

        # Build transcript for analysis
        transcript = self._build_transcript_from_data(transcription_data)

        if len(transcript) < 50:
            return {
                'needs_confirmation': False,
                'message': "Transcript is too short to analyze. Please ensure transcription completed successfully.",
                'options': []
            }

        # Use GPT-4 to analyze transcript and find best segments
        try:
            segments = self._analyze_transcript_for_short_form(
                transcript,
                duration,
                content_type,
                transcription_data
            )

            if not segments or len(segments) == 0:
                return {
                    'needs_confirmation': False,
                    'message': f"I couldn't identify engaging segments for a {duration}s {content_type} {platform} reel. The transcript might be too short or lack clear highlights.",
                    'options': []
                }

            # Calculate total duration
            total_duration = sum(seg['duration'] for seg in segments)

            # Build segment preview text to show user what was selected
            segment_preview = "\n\n**Segments identified:**\n"
            for i, seg in enumerate(segments[:5], 1):  # Show first 5 segments
                start_time = seg.get('start', 0)
                end_time = seg.get('end', 0)
                reason = seg.get('reason', 'N/A')
                segment_preview += f"{i}. `{start_time:.1f}s - {end_time:.1f}s` - {reason}\n"

            if len(segments) > 5:
                segment_preview += f"... and {len(segments) - 5} more segment(s)\n"

            # Create response with options
            return {
                'needs_confirmation': True,
                'message': f"I've identified **{len(segments)} engaging segments** for a {duration}s {platform} reel ({content_type} style).\n\nTotal duration: {total_duration:.1f}s{segment_preview}\nWould you like to create this cut?",
                'options': [
                    {
                        'id': 'create',
                        'label': f'✨ Create {duration}s {platform.title()} Reel',
                        'description': f'{len(segments)} segments, {content_type} style, {total_duration:.1f}s total',
                        'params': {
                            'operation': 'short_form',
                            'duration': duration,
                            'content_type': content_type,
                            'platform': platform,
                            'segments': segments,
                            'prompt': f'{duration}s {content_type} reel for {platform}'
                        }
                    }
                ],
                'preview_data': {
                    'segments': segments,
                    'duration': duration,
                    'content_type': content_type,
                    'platform': platform
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing transcript for short-form: {e}")
            return {
                'needs_confirmation': False,
                'message': f"Sorry, I encountered an error analyzing your content: {str(e)}",
                'options': []
            }

    def _build_transcript_from_data(self, transcription_data: Dict) -> str:
        """Build full transcript from transcription data"""
        segments = transcription_data.get('segments', [])
        if not segments:
            # Fallback to full transcript if no segments
            return transcription_data.get('transcript', '')

        transcript_parts = []
        for segment in segments:
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            text = segment.get('text', '')
            speaker = segment.get('speaker', 'SPEAKER')

            transcript_parts.append(f"[{start:.1f}s - {end:.1f}s] {speaker}: {text}")

        return "\n".join(transcript_parts)

    def _analyze_transcript_for_short_form(
        self,
        transcript: str,
        target_duration: int,
        content_type: str,
        transcription_data: Dict
    ) -> List[Dict]:
        """Use GPT-4 to analyze transcript and extract best segments for short-form content"""

        # Calculate transcript time coverage
        segments = transcription_data.get('segments', [])
        if segments:
            first_segment_start = segments[0].get('start', 0)
            last_segment_end = segments[-1].get('end', 0)
            logger.info(f"Full transcript: {len(transcript)} chars, covering {first_segment_start:.1f}s - {last_segment_end:.1f}s ({last_segment_end:.1f}s total)")
        else:
            logger.warning("No segments available for transcript time calculation")

        # Calculate total video duration from transcript segments
        segments_list = transcription_data.get('segments', [])
        total_duration = max(s.get('end', 0) for s in segments_list) if segments_list else 60
        logger.info(f"Total video duration: {total_duration:.1f}s")

        # Smart transcript handling: use sampling for very long videos (increased limit to 100,000)
        if len(transcript) > 100000:
            logger.info(f"Transcript is {len(transcript)} chars, using smart sampling")
            transcript_for_analysis = self._sample_transcript_evenly(transcript, transcription_data, 100000)
        else:
            transcript_for_analysis = transcript
            logger.info(f"Using full transcript: {len(transcript_for_analysis)} chars")

        prompt = f"""You are an expert video editor specializing in short-form social media content.

Analyze this transcript and identify the BEST segments for a {target_duration}-second {content_type} video.

TRANSCRIPT (Total video duration: {total_duration:.1f}s):
{transcript_for_analysis}

CONTENT PHILOSOPHY:
- **For tutorial/explainer videos: PREFER ONE CONTINUOUS {target_duration}s SEGMENT with complete narrative**
- Continuous segments tell better stories than scattered clips
- Look for complete micro-stories: hook → value demonstration → benefit/CTA
- Avoid jumping between unrelated parts of the video
- Find natural "reel endpoints" (strong closing lines, NOT mid-explanation)
- **STOP BEFORE pricing, advanced settings, tier comparisons, or complex technical details**

SELECTION CRITERIA (In Priority Order):
1. ✅ Does this segment tell a complete micro-story? (REQUIRED - highest priority)
2. ✅ Does it start with a strong hook in first 5s? (REQUIRED)
3. ✅ Does it have clear value proposition/demonstration? (REQUIRED)
4. ✅ Does it end cleanly, not mid-sentence or mid-concept? (REQUIRED)
5. ✅ Does it avoid boring content (pricing/technical details)? (PREFERRED)
6. ✅ Does it maintain narrative flow without gaps? (PREFERRED)

TASK:
1. **FIRST**: Try to find ONE continuous {target_duration}s segment (start to end without gaps)
2. **ONLY IF** no good continuous segment exists: Select 3-5 scattered segments
3. Each segment should be 5-20 seconds long
4. Total duration should be close to {target_duration} seconds
5. Focus on: hooks, value demonstrations, clear outcomes, emotional engagement

CRITICAL REQUIREMENTS:
- **IF using scattered segments, SELECT FROM THROUGHOUT THE ENTIRE {total_duration:.1f}s VIDEO**
- **Distribute evenly across video duration:**
  - At least one from 0-30% (0-{total_duration*0.3:.0f}s)
  - At least one from 30-70% ({total_duration*0.3:.0f}-{total_duration*0.7:.0f}s)
  - At least one from 70-100% ({total_duration*0.7:.0f}-{total_duration:.0f}s)
- **DO NOT cluster all segments in the first 30% of the video**
- **ENSURE the latest segment ends after 50% of total duration**
- Use EXACT timestamps from the transcript
- Prioritize segments that work standalone without context

Respond with ONLY a JSON array (no markdown, no explanation):
[
  {{
    "start": 12.3,
    "end": 28.1,
    "text": "Hook example from early in video",
    "reason": "Strong hook - curiosity builder",
    "engagement_score": 0.95,
    "is_hook": true
  }},
  {{
    "start": 145.7,
    "end": 160.5,
    "text": "Mid-video punchline or demonstration",
    "reason": "Emotional peak - high engagement",
    "engagement_score": 0.88,
    "is_hook": false
  }},
  {{
    "start": 230.2,
    "end": 245.0,
    "text": "Late video value proposition or CTA",
    "reason": "Clear call-to-action with proof",
    "engagement_score": 0.92,
    "is_hook": false
  }}
]

Return ONLY valid JSON array (no markdown code blocks, no explanations).
"""

        try:
            # Use Replicate LLaMA 3.1 70B for segment analysis
            system_message = "You are an expert video editor. Respond ONLY with valid JSON, no markdown formatting."
            full_prompt = f"{system_message}\n\n{prompt}"

            output = replicate.run(
                self.llm_model,
                input={
                    "prompt": full_prompt,
                    "max_tokens": 2048,
                    "temperature": 0.1,
                    "top_p": 1.0
                }
            )

            # Replicate returns an iterator, concatenate all chunks
            response_text = "".join(output).strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            segments = json.loads(response_text)

            # Add duration to each segment
            for seg in segments:
                seg['duration'] = seg['end'] - seg['start']

            logger.info(f"LLaMA 3.1 70B identified {len(segments)} segments for short-form content")

            # === VALIDATION: Check if segments are well-distributed ===
            segments_list = transcription_data.get('segments', [])
            total_dur = max(s.get('end', 0) for s in segments_list) if segments_list else 60

            if segments and total_dur > 0:
                latest_end = max(seg['end'] for seg in segments)

                # Dynamic threshold: 40% for short videos, 50% for longer ones
                threshold = 0.4 if total_dur < 120 else 0.5

                if latest_end < (total_dur * threshold):
                    logger.warning(f"⚠️ SEGMENTS CLUSTERED IN FIRST {threshold*100:.0f}%!")
                    logger.warning(f"Latest segment ends at {latest_end:.1f}s / {total_dur:.1f}s total")
                    logger.warning(f"Retrying with stronger constraint...")

                    # RETRY ONCE with stronger prompt
                    retry_prompt = prompt + f"\n\n⚠️ RETRY: Previous response clustered segments too early. FORCE at least one segment to start AFTER {total_dur*threshold:.0f}s. Distribute across full {total_dur:.0f}s timeline!"

                    try:
                        retry_output = replicate.run(
                            self.llm_model,
                            input={
                                "prompt": retry_prompt,
                                "max_tokens": 1500,
                                "temperature": 0.4,
                                "top_p": 0.9
                            }
                        )

                        retry_response_text = "".join(retry_output).strip()

                        # Remove markdown code blocks if present
                        if retry_response_text.startswith('```'):
                            retry_response_text = retry_response_text.split('```')[1]
                            if retry_response_text.startswith('json'):
                                retry_response_text = retry_response_text[4:]
                            retry_response_text = retry_response_text.strip()

                        retry_segments = json.loads(retry_response_text)

                        # Add duration to retry segments
                        for seg in retry_segments:
                            seg['duration'] = seg['end'] - seg['start']

                        # Check if retry improved distribution
                        retry_latest = max(seg['end'] for seg in retry_segments)
                        if retry_latest >= (total_dur * threshold):
                            logger.info(f"✅ Retry succeeded! Latest segment now at {retry_latest:.1f}s")
                            segments = retry_segments
                        else:
                            logger.warning(f"Retry still clustered ({retry_latest:.1f}s), using fallback")
                            return self._fallback_segment_extraction(transcription_data, target_duration)

                    except Exception as e:
                        logger.error(f"Retry failed: {e}, using fallback")
                        return self._fallback_segment_extraction(transcription_data, target_duration)

            # Log segment details for debugging
            segment_summary = [
                {
                    'start': s['start'],
                    'end': s['end'],
                    'duration': s['duration'],
                    'reason': s.get('reason', 'N/A')[:50]  # Truncate reason to 50 chars
                }
                for s in segments
            ]
            logger.debug(f"Selected segments: {json.dumps(segment_summary, indent=2)}")

            return segments

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLaMA segments response: {e}. Response: {response_text}")
            # Fallback: extract first N seconds
            return self._fallback_segment_extraction(transcription_data, target_duration)
        except Exception as e:
            logger.error(f"Error in LLaMA segment analysis: {e}")
            return self._fallback_segment_extraction(transcription_data, target_duration)

    def _fallback_segment_extraction(self, transcription_data: Dict, target_duration: int) -> List[Dict]:
        """Fallback: extract first N seconds if GPT-4 fails"""
        logger.warning("Using fallback segment extraction")

        segments_data = transcription_data.get('segments', [])
        if not segments_data:
            return []

        # Extract segments until we reach target duration
        selected_segments = []
        cumulative_duration = 0

        for segment in segments_data:
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            duration = end - start

            if cumulative_duration + duration > target_duration:
                # Add partial segment to reach target
                remaining = target_duration - cumulative_duration
                selected_segments.append({
                    'start': start,
                    'end': start + remaining,
                    'duration': remaining,
                    'text': segment.get('text', ''),
                    'reason': 'Fallback extraction',
                    'engagement_score': 0.5
                })
                break

            selected_segments.append({
                'start': start,
                'end': end,
                'duration': duration,
                'text': segment.get('text', ''),
                'reason': 'Fallback extraction',
                'engagement_score': 0.5
            })

            cumulative_duration += duration

            if cumulative_duration >= target_duration:
                break

        return selected_segments

    def _sample_transcript_evenly(self, transcript: str, transcription_data: Dict, max_chars: int) -> str:
        """
        Sample transcript evenly throughout the video when it's too long

        Instead of truncating to first N chars, this samples segments from
        beginning, middle, and end to give GPT-4 a full picture of the content.

        Args:
            transcript: Full formatted transcript text
            transcription_data: Full transcription data with segments
            max_chars: Maximum characters to return

        Returns:
            Sampled transcript string with content from throughout the video
        """
        segments = transcription_data.get('segments', [])
        if not segments:
            logger.warning("No segments available for transcript sampling, using truncation")
            return transcript[:max_chars]

        # Sample strategy: first 30%, middle 30%, last 30% (leave 10% gaps for readability)
        total_segments = len(segments)
        sample_size = max_chars // 3

        logger.info(f"Transcript too long ({len(transcript)} chars), sampling evenly from {total_segments} segments")

        # Beginning segments (0-30%)
        start_segments = segments[:int(total_segments * 0.3)]
        start_text = "\n".join([
            f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('speaker', 'SPEAKER')}: {s.get('text', '')}"
            for s in start_segments
        ])[:sample_size]

        # Middle segments (35-65%)
        mid_start = int(total_segments * 0.35)
        mid_end = int(total_segments * 0.65)
        mid_segments = segments[mid_start:mid_end]
        mid_text = "\n".join([
            f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('speaker', 'SPEAKER')}: {s.get('text', '')}"
            for s in mid_segments
        ])[:sample_size]

        # End segments (70-100%)
        end_start = int(total_segments * 0.7)
        end_segments = segments[end_start:]
        end_text = "\n".join([
            f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('speaker', 'SPEAKER')}: {s.get('text', '')}"
            for s in end_segments
        ])[:sample_size]

        sampled_transcript = f"{start_text}\n\n[... middle content ...]\n\n{mid_text}\n\n[... more content ...]\n\n{end_text}"

        logger.info(f"Sampled transcript: {len(sampled_transcript)} chars from beginning, middle, and end")

        return sampled_transcript

    def _ask_for_clarification(self, message: str, intent_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Ask user for clarification when intent is unclear"""
        clarification_question = intent_data.get('clarification_question') if intent_data else None

        if clarification_question:
            return {
                'needs_confirmation': False,
                'message': clarification_question,
                'options': []
            }

        return {
            'needs_confirmation': False,
            'message': "I'm not sure what you want me to do. Here are some things I can help with:\n\n• **Instagram Reel / TikTok** - Create engaging short-form content\n• **Montage** - Compile all instances of a phrase\n• **Remove Silence** - Cut out long pauses\n• **Filter Speaker** - Keep only one speaker\n\nWhat would you like to do?",
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
                        'start': segment.get('start', 0),
                        'end': segment.get('end', 0),
                        'duration': segment.get('end', 0) - segment.get('start', 0),
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

        elif operation == 'short_form':
            # Preview for short-form content (Instagram reels, TikTok, etc.)
            segments = params.get('segments', [])
            duration = params.get('duration', 60)
            platform = params.get('platform', 'instagram')
            content_type = params.get('content_type', 'engaging')

            total_duration = sum(seg.get('duration', seg.get('end', 0) - seg.get('start', 0)) for seg in segments)

            return {
                'operation': 'short_form',
                'platform': platform,
                'content_type': content_type,
                'target_duration': duration,
                'segments': [
                    {
                        'index': i + 1,
                        'start': seg.get('start', 0),
                        'end': seg.get('end', 0),
                        'duration': seg.get('duration', seg.get('end', 0) - seg.get('start', 0)),
                        'text': seg.get('text', ''),
                        'reason': seg.get('reason', ''),
                        'engagement_score': seg.get('engagement_score', 0),
                        'is_hook': seg.get('is_hook', False)
                    }
                    for i, seg in enumerate(segments)
                ],
                'total_segments': len(segments),
                'total_duration': total_duration,
                'compression': (1 - (total_duration / (timeline.duration or 1))) * 100
            }

        return {
            'operation': operation,
            'message': 'Preview not available for this operation'
        }
