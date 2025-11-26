"""
Content Analyzer Service
Automatically analyzes transcript to build intelligent knowledge base
for God Mode conversational editing
"""
import logging
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import replicate
from config import Config

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """
    Analyzes video content after transcription to build structured knowledge base

    This enables God Mode to understand what the video is about BEFORE the user types,
    making conversations intelligent and context-aware.
    """

    def __init__(self):
        self.replicate_token = Config.REPLICATE_API_TOKEN
        # Use OpenAI GPT-4o via Replicate for analysis
        self.llm_model = "openai/gpt-4o"

        if not self.replicate_token:
            logger.warning("No REPLICATE_API_TOKEN found - content analysis will be limited")

    def analyze_content(self, transcription_data: Dict) -> Dict[str, Any]:
        """
        Analyze transcript and build knowledge base

        Args:
            transcription_data: Full transcription with segments, words, speakers

        Returns:
            Structured knowledge base with:
            - content_type: tutorial/demo/interview/vlog/podcast
            - main_topic: Brief description
            - features_discussed: List of features with timestamps
            - chapters: Natural content chapters
            - key_moments: Highlights
        """
        try:
            logger.info("🧠 Starting content analysis...")

            # Build formatted transcript
            transcript = self._build_transcript_from_data(transcription_data)

            if not transcript or len(transcript) < 50:
                logger.warning("Transcript too short for analysis")
                return self._empty_knowledge_base("Transcript too short to analyze")

            # Use LLM to analyze if available
            if not self.replicate_token:
                logger.warning("Replicate API token not available, returning basic analysis")
                return self._basic_analysis(transcription_data)

            # Call OpenAI GPT-4o via Replicate for intelligent analysis
            knowledge_base = self._analyze_with_llm(transcript, transcription_data)

            logger.info(f"✅ Content analysis complete: {knowledge_base.get('main_topic', 'Unknown topic')}")
            logger.info(f"   Found {len(knowledge_base.get('features_discussed', []))} features")

            return knowledge_base

        except Exception as e:
            logger.error(f"Error in content analysis: {str(e)}")
            return self._empty_knowledge_base(f"Analysis failed: {str(e)}")

    def _build_transcript_from_data(self, transcription_data: Dict) -> str:
        """Build formatted transcript from transcription data"""
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

    def _analyze_with_llm(self, transcript: str, transcription_data: Dict) -> Dict[str, Any]:
        """Use OpenAI GPT-4o via Replicate to analyze content structure"""

        # Calculate video duration
        segments = transcription_data.get('segments', [])
        total_duration = max(s.get('end', 0) for s in segments) if segments else 0

        # Limit transcript length for analysis (GPT-4 context limit)
        if len(transcript) > 50000:
            logger.info(f"Transcript too long ({len(transcript)} chars), sampling evenly")
            transcript = self._sample_transcript_evenly(transcript, transcription_data, 50000)

        analysis_prompt = f"""You are an expert video content analyst. Analyze this transcript and provide a structured knowledge base.

TRANSCRIPT (Total Duration: {total_duration:.1f}s):
{transcript}

TASK:
Analyze the content and respond with ONLY a JSON object (no markdown, no explanations) with this structure:

{{
  "content_type": "tutorial|demo|interview|vlog|podcast|presentation|review",
  "main_topic": "Brief 1-2 sentence description of what this video is about",
  "features_discussed": [
    {{
      "name": "Feature/Topic Name",
      "description": "What this feature/section covers",
      "start_time": 150.5,
      "end_time": 450.2,
      "key_points": ["Point 1", "Point 2"],
      "confidence": 0.85
    }}
  ],
  "chapters": [
    {{"title": "Chapter Name", "start": 0.0, "end": 120.5}}
  ],
  "key_moments": [
    {{"description": "Important moment", "timestamp": 180.5, "engagement": "high|medium|low"}}
  ]
}}

REQUIREMENTS:
- Identify ALL major features/topics discussed (minimum 1, usually 2-5)
- Use EXACT timestamps from the transcript
- Features should be substantial (30s+ duration)
- Confidence: 1.0 = certain, 0.5 = uncertain
- Key moments: Demos, punchlines, important reveals
- Chapters: Natural content divisions

Respond with ONLY valid JSON (no markdown code blocks, no explanations).
"""

        try:
            logger.info("Calling OpenAI GPT-4o via Replicate for content analysis...")

            output = replicate.run(
                self.llm_model,
                input={
                    "prompt": f"You are an expert video content analyst. Return ONLY valid JSON with no markdown formatting.\n\n{analysis_prompt}",
                    "max_tokens": 4096,
                    "temperature": 0.2,
                    "top_p": 1.0
                }
            )

            # Get response text
            response_text = "".join(output).strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            # Extract JSON from response (in case of any wrapper text)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end]

            # Parse JSON
            knowledge_base = json.loads(response_text)

            # Add metadata
            knowledge_base['metadata'] = {
                'analyzed_at': datetime.utcnow().isoformat(),
                'analyzer_version': '1.0',
                'user_modified': False,
                'llm_model': self.llm_model
            }

            # Calculate durations and add IDs for features
            for idx, feature in enumerate(knowledge_base.get('features_discussed', [])):
                if 'start_time' in feature and 'end_time' in feature:
                    feature['duration'] = feature['end_time'] - feature['start_time']
                    feature['user_edited'] = False
                    feature['id'] = f"feature_{idx + 1}"

            return knowledge_base

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response: {response_text[:500]}")
            return self._basic_analysis(transcription_data)
        except Exception as e:
            logger.error(f"Error calling LLM for analysis: {e}")
            return self._basic_analysis(transcription_data)

    def _sample_transcript_evenly(self, transcript: str, transcription_data: Dict, max_chars: int) -> str:
        """
        Sample transcript evenly throughout video when too long

        Takes segments from beginning, middle, and end to give complete picture
        """
        segments = transcription_data.get('segments', [])
        if not segments:
            return transcript[:max_chars]

        total_segments = len(segments)
        sample_size = max_chars // 3

        # Beginning (0-30%)
        start_segments = segments[:int(total_segments * 0.3)]
        start_text = "\n".join([
            f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('speaker', 'SPEAKER')}: {s.get('text', '')}"
            for s in start_segments
        ])[:sample_size]

        # Middle (35-65%)
        mid_start = int(total_segments * 0.35)
        mid_end = int(total_segments * 0.65)
        mid_segments = segments[mid_start:mid_end]
        mid_text = "\n".join([
            f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('speaker', 'SPEAKER')}: {s.get('text', '')}"
            for s in mid_segments
        ])[:sample_size]

        # End (70-100%)
        end_start = int(total_segments * 0.7)
        end_segments = segments[end_start:]
        end_text = "\n".join([
            f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('speaker', 'SPEAKER')}: {s.get('text', '')}"
            for s in end_segments
        ])[:sample_size]

        sampled = f"{start_text}\n\n[... middle content ...]\n\n{mid_text}\n\n[... more content ...]\n\n{end_text}"

        logger.info(f"Sampled transcript: {len(sampled)} chars from full video")
        return sampled

    def _basic_analysis(self, transcription_data: Dict) -> Dict[str, Any]:
        """
        Fallback: Basic analysis without LLM

        Creates simple knowledge base by detecting topic changes based on
        speaker transitions or time gaps
        """
        logger.info("Using basic analysis (no LLM available)")

        segments = transcription_data.get('segments', [])
        if not segments:
            return self._empty_knowledge_base("No segments available")

        # Extract first few words as topic hint
        first_segment_text = segments[0].get('text', '') if segments else ''
        main_topic = first_segment_text[:100] + "..." if len(first_segment_text) > 100 else first_segment_text

        # Simple chapter detection: split by long pauses or speaker changes
        chapters = []
        current_chapter_start = 0
        last_speaker = None

        for i, segment in enumerate(segments):
            speaker = segment.get('speaker', 'SPEAKER')
            start = segment.get('start', 0)

            # Detect chapter boundary (speaker change or 5s+ gap)
            if last_speaker and speaker != last_speaker:
                chapters.append({
                    'title': f"Section {len(chapters) + 1}",
                    'start': current_chapter_start,
                    'end': start
                })
                current_chapter_start = start

            last_speaker = speaker

        # Final chapter
        if segments:
            chapters.append({
                'title': f"Section {len(chapters) + 1}",
                'start': current_chapter_start,
                'end': segments[-1].get('end', 0)
            })

        return {
            'content_type': 'unknown',
            'main_topic': main_topic or 'Video content',
            'features_discussed': [],  # Cannot detect without LLM
            'chapters': chapters,
            'key_moments': [],
            'metadata': {
                'analyzed_at': datetime.utcnow().isoformat(),
                'analyzer_version': '1.0',
                'user_modified': False,
                'analysis_method': 'basic'
            }
        }

    def _empty_knowledge_base(self, reason: str) -> Dict[str, Any]:
        """Return empty knowledge base with error reason"""
        return {
            'content_type': 'unknown',
            'main_topic': 'Analysis unavailable',
            'features_discussed': [],
            'chapters': [],
            'key_moments': [],
            'metadata': {
                'analyzed_at': datetime.utcnow().isoformat(),
                'analyzer_version': '1.0',
                'user_modified': False,
                'analysis_error': reason
            }
        }
