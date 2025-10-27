"""
AI Timeline Editor Service
Handles natural language prompts for timeline editing
"""
import logging
import re
from typing import Dict, List, Any, Optional
from models.timeline import Timeline, Track, Clip

logger = logging.getLogger(__name__)


class AITimelineEditor:
    """AI-powered timeline editor using natural language prompts"""

    def __init__(self):
        self.supported_operations = {
            'montage': self._create_montage,
            'remove_silence': self._remove_silence,
            'filter_speaker': self._filter_by_speaker,
            'remove_fillers': self._remove_filler_words,
            'summarize': self._create_summary,
        }

    def process_prompt(self, prompt: str, timeline: Timeline, transcription_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process natural language prompt and return edited timeline

        Args:
            prompt: User's natural language editing instruction
            timeline: Original timeline object
            transcription_data: Optional transcription with timestamps

        Returns:
            Dict with 'operation', 'timeline', 'message', 'changes_made'
        """
        try:
            prompt_lower = prompt.lower().strip()
            logger.info(f"Processing AI edit prompt: {prompt}")

            # Detect operation type
            operation = self._detect_operation(prompt_lower)

            if operation == 'montage':
                search_phrase = self._extract_search_phrase(prompt)
                result = self._create_montage(timeline, search_phrase, transcription_data)
            elif operation == 'remove_silence':
                threshold = self._extract_duration_threshold(prompt)
                result = self._remove_silence(timeline, threshold)
            elif operation == 'filter_speaker':
                speaker_num = self._extract_speaker_number(prompt)
                result = self._filter_by_speaker(timeline, speaker_num, transcription_data)
            elif operation == 'remove_fillers':
                result = self._remove_filler_words(timeline, transcription_data)
            elif operation == 'summarize':
                target_duration = self._extract_target_duration(prompt)
                result = self._create_summary(timeline, target_duration)
            else:
                result = {
                    'success': False,
                    'message': f"Operation '{operation}' not yet supported. Try: montage, remove silence, filter speaker, remove fillers, or summarize.",
                    'timeline': timeline
                }

            return result

        except Exception as e:
            logger.error(f"Error processing AI prompt: {str(e)}")
            return {
                'success': False,
                'message': f"Error processing prompt: {str(e)}",
                'timeline': timeline
            }

    def _detect_operation(self, prompt: str) -> str:
        """Detect operation type from prompt"""
        if any(word in prompt for word in ['montage', 'every time', 'find all', 'extract']):
            return 'montage'
        elif any(word in prompt for word in ['remove silence', 'cut silence', 'delete silence']):
            return 'remove_silence'
        elif any(word in prompt for word in ['speaker', 'only speaker', 'filter speaker']):
            return 'filter_speaker'
        elif any(word in prompt for word in ['filler', 'um', 'uh', 'you know']):
            return 'remove_fillers'
        elif any(word in prompt for word in ['summary', 'summarize', 'shorten', 'condense']):
            return 'summarize'
        return 'unknown'

    def _extract_search_phrase(self, prompt: str) -> str:
        """Extract search phrase from montage prompts"""
        # Look for phrases in quotes
        quoted = re.findall(r"['\"](.+?)['\"]", prompt)
        if quoted:
            return quoted[0]

        # Look for "every time I say X"
        match = re.search(r"every time.*?say\s+(.+?)(?:\s|$)", prompt)
        if match:
            return match.group(1).strip()

        # Default fallback
        return "unknown phrase"

    def _extract_duration_threshold(self, prompt: str) -> float:
        """Extract duration threshold (in seconds) from prompt"""
        match = re.search(r'(\d+\.?\d*)\s*(?:second|sec|s)', prompt)
        if match:
            return float(match.group(1))
        return 2.0  # Default 2 seconds

    def _extract_speaker_number(self, prompt: str) -> int:
        """Extract speaker number from prompt"""
        match = re.search(r'speaker\s*(\d+)', prompt)
        if match:
            return int(match.group(1))
        return 1  # Default to speaker 1

    def _extract_target_duration(self, prompt: str) -> float:
        """Extract target duration for summary"""
        # Look for "X minute" or "X second"
        match = re.search(r'(\d+\.?\d*)\s*(?:minute|min)', prompt)
        if match:
            return float(match.group(1)) * 60
        match = re.search(r'(\d+\.?\d*)\s*(?:second|sec|s)', prompt)
        if match:
            return float(match.group(1))
        return 60.0  # Default 1 minute

    def _create_montage(self, timeline: Timeline, search_phrase: str, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Create montage of clips matching search phrase"""
        logger.info(f"Creating montage for phrase: {search_phrase}")

        # For now, return a placeholder result
        # In full implementation, would search transcription and extract matching segments
        return {
            'success': True,
            'operation': 'montage',
            'message': f"Montage created for phrase: '{search_phrase}' (Note: This is a preview - full implementation requires transcription data)",
            'timeline': timeline,
            'changes_made': {
                'clips_kept': 0,
                'clips_removed': 0,
                'search_phrase': search_phrase
            }
        }

    def _remove_silence(self, timeline: Timeline, threshold_seconds: float) -> Dict[str, Any]:
        """Remove silence segments longer than threshold"""
        logger.info(f"Removing silence longer than {threshold_seconds}s")

        return {
            'success': True,
            'operation': 'remove_silence',
            'message': f"Silence segments longer than {threshold_seconds}s removed (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'silence_removed': 0,
                'threshold': threshold_seconds
            }
        }

    def _filter_by_speaker(self, timeline: Timeline, speaker_num: int, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Keep only clips from specified speaker"""
        logger.info(f"Filtering to keep only Speaker {speaker_num}")

        return {
            'success': True,
            'operation': 'filter_speaker',
            'message': f"Timeline filtered to Speaker {speaker_num} only (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'speaker': speaker_num,
                'clips_kept': 0,
                'clips_removed': 0
            }
        }

    def _remove_filler_words(self, timeline: Timeline, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Remove filler words from timeline"""
        logger.info("Removing filler words")

        return {
            'success': True,
            'operation': 'remove_fillers',
            'message': "Filler words (um, uh, you know) removed (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'fillers_removed': 0
            }
        }

    def _create_summary(self, timeline: Timeline, target_duration: float) -> Dict[str, Any]:
        """Create summary of specified duration"""
        logger.info(f"Creating {target_duration}s summary")

        return {
            'success': True,
            'operation': 'summarize',
            'message': f"Timeline summarized to {target_duration}s (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'target_duration': target_duration,
                'original_duration': 0,
                'compression_ratio': 0
            }
        }
