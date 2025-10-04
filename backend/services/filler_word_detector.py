"""
Filler Word Detection Service
Detects and marks filler words in transcriptions for removal
"""

import logging
import re
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)

class FillerWordDetector:
    """
    Detects filler words in transcriptions and provides removal recommendations
    """

    # Common filler words in English
    ENGLISH_FILLER_WORDS = {
        'um', 'uh', 'hmm', 'mhm', 'mm', 'mmm',
        'er', 'ah', 'uhh', 'umm', 'ehh',
        'like', 'you know', 'i mean', 'sort of', 'kind of',
        'basically', 'literally', 'actually', 'right',
        'okay', 'ok', 'so', 'well', 'yeah', 'yes',
        'no', 'nah', 'yep', 'yup', 'uh huh', 'mm hmm'
    }

    # Common filler words in Malayalam (if needed)
    MALAYALAM_FILLER_WORDS = {
        'അതെ', 'ഹോ', 'ഓ', 'എടോ', 'എടി'
    }

    # Context-sensitive phrases that might be filler words
    CONTEXT_SENSITIVE_WORDS = {'like', 'so', 'right', 'okay', 'ok', 'well', 'yeah', 'yes', 'no'}

    def __init__(self, custom_filler_words: Optional[Set[str]] = None, language: str = 'en'):
        """
        Initialize filler word detector

        Args:
            custom_filler_words: Additional filler words to detect
            language: Language code ('en' for English, 'ml' for Malayalam)
        """
        self.language = language

        # Build filler word set based on language
        if language == 'en':
            self.filler_words = self.ENGLISH_FILLER_WORDS.copy()
        elif language == 'ml':
            self.filler_words = self.MALAYALAM_FILLER_WORDS.copy()
        else:
            # Default to English
            self.filler_words = self.ENGLISH_FILLER_WORDS.copy()

        # Add custom filler words if provided
        if custom_filler_words:
            self.filler_words.update(custom_filler_words)

    def detect_filler_words(self, transcription_data: Dict[str, Any],
                           aggressive: bool = False) -> Dict[str, Any]:
        """
        Detect filler words in transcription data

        Args:
            transcription_data: Transcription with segments and words
            aggressive: If True, detect context-sensitive words more aggressively

        Returns:
            Dictionary with detected filler words and removal recommendations
        """
        try:
            segments = transcription_data.get('segments', [])
            if not segments:
                return {'success': False, 'error': 'No segments in transcription'}

            filler_word_instances = []
            total_filler_duration = 0.0
            filler_word_counts = {}

            for segment in segments:
                words = segment.get('words', [])

                for word_data in words:
                    text = word_data.get('text', '').lower().strip()
                    start_time = word_data.get('start_time', 0)
                    end_time = word_data.get('end_time', 0)
                    duration = end_time - start_time

                    # Check if word is a filler word
                    is_filler = self._is_filler_word(text, aggressive)

                    if is_filler:
                        filler_word_instances.append({
                            'text': text,
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': duration,
                            'speaker': segment.get('speaker', 'Unknown'),
                            'confidence': word_data.get('confidence', 0.0),
                            'context_sensitive': text in self.CONTEXT_SENSITIVE_WORDS
                        })

                        total_filler_duration += duration

                        # Track counts
                        if text in filler_word_counts:
                            filler_word_counts[text] += 1
                        else:
                            filler_word_counts[text] = 1

            # Calculate statistics
            total_duration = transcription_data.get('duration', 0)
            filler_percentage = (total_filler_duration / total_duration * 100) if total_duration > 0 else 0

            result = {
                'success': True,
                'filler_word_instances': filler_word_instances,
                'total_filler_words': len(filler_word_instances),
                'total_filler_duration': total_filler_duration,
                'filler_percentage': filler_percentage,
                'filler_word_counts': filler_word_counts,
                'most_common_fillers': self._get_most_common_fillers(filler_word_counts, top_n=5),
                'removal_recommendations': self._generate_removal_recommendations(
                    filler_word_instances,
                    transcription_data,
                    aggressive
                )
            }

            logger.info(f"Detected {len(filler_word_instances)} filler words ({filler_percentage:.1f}% of total duration)")
            return result

        except Exception as e:
            logger.error(f"Error detecting filler words: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _is_filler_word(self, text: str, aggressive: bool = False) -> bool:
        """
        Check if a word is a filler word

        Args:
            text: Word text (lowercased)
            aggressive: If True, also detect context-sensitive words

        Returns:
            True if word is a filler word
        """
        # Direct match in filler words set
        if text in self.filler_words:
            # If aggressive mode, always mark as filler
            if aggressive:
                return True
            # Otherwise, skip context-sensitive words
            if text not in self.CONTEXT_SENSITIVE_WORDS:
                return True

        # Check for variations (e.g., "ummm" should match "um")
        for filler in self.filler_words:
            if text.startswith(filler) and len(text) <= len(filler) + 2:
                # Allow small variations like "ummm" for "um"
                if all(c == filler[-1] for c in text[len(filler):]):
                    return True

        return False

    def _get_most_common_fillers(self, filler_word_counts: Dict[str, int], top_n: int = 5) -> List[Dict[str, Any]]:
        """Get the most common filler words"""
        sorted_fillers = sorted(filler_word_counts.items(), key=lambda x: x[1], reverse=True)
        return [{'word': word, 'count': count} for word, count in sorted_fillers[:top_n]]

    def _generate_removal_recommendations(self,
                                         filler_word_instances: List[Dict[str, Any]],
                                         transcription_data: Dict[str, Any],
                                         aggressive: bool = False) -> List[Dict[str, Any]]:
        """
        Generate recommendations for which filler words to remove

        Args:
            filler_word_instances: List of detected filler words
            transcription_data: Full transcription data
            aggressive: If True, recommend removing more filler words

        Returns:
            List of removal recommendations with time ranges
        """
        recommendations = []

        # Group filler words by proximity (remove clusters together)
        clusters = self._cluster_filler_words(filler_word_instances)

        for cluster in clusters:
            # Determine if this cluster should be removed
            should_remove = True
            removal_confidence = 'high'

            # Check if any words in cluster are context-sensitive
            has_context_sensitive = any(fw['context_sensitive'] for fw in cluster)

            if has_context_sensitive and not aggressive:
                removal_confidence = 'medium'
                # Don't remove context-sensitive words unless aggressive mode
                should_remove = False

            # Check confidence scores
            avg_confidence = sum(fw['confidence'] for fw in cluster) / len(cluster) if cluster else 0
            if avg_confidence < 0.5:
                removal_confidence = 'low'

            # Create recommendation
            if should_remove or removal_confidence != 'low':
                start_time = min(fw['start_time'] for fw in cluster)
                end_time = max(fw['end_time'] for fw in cluster)

                recommendations.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'filler_words': [fw['text'] for fw in cluster],
                    'should_remove': should_remove,
                    'confidence': removal_confidence,
                    'reason': self._generate_removal_reason(cluster, aggressive)
                })

        return recommendations

    def _cluster_filler_words(self,
                             filler_word_instances: List[Dict[str, Any]],
                             max_gap: float = 0.5) -> List[List[Dict[str, Any]]]:
        """
        Cluster filler words that are close together in time

        Args:
            filler_word_instances: List of filler words
            max_gap: Maximum time gap (seconds) to consider words in same cluster

        Returns:
            List of clusters (each cluster is a list of filler words)
        """
        if not filler_word_instances:
            return []

        # Sort by start time
        sorted_fillers = sorted(filler_word_instances, key=lambda x: x['start_time'])

        clusters = []
        current_cluster = [sorted_fillers[0]]

        for i in range(1, len(sorted_fillers)):
            prev_end = current_cluster[-1]['end_time']
            curr_start = sorted_fillers[i]['start_time']

            if curr_start - prev_end <= max_gap:
                # Add to current cluster
                current_cluster.append(sorted_fillers[i])
            else:
                # Start new cluster
                clusters.append(current_cluster)
                current_cluster = [sorted_fillers[i]]

        # Add final cluster
        if current_cluster:
            clusters.append(current_cluster)

        return clusters

    def _generate_removal_reason(self, cluster: List[Dict[str, Any]], aggressive: bool) -> str:
        """Generate human-readable reason for removal recommendation"""
        if len(cluster) == 1:
            return f"Single filler word: '{cluster[0]['text']}'"
        elif len(cluster) > 3:
            return f"Cluster of {len(cluster)} filler words"
        else:
            words = ', '.join([f"'{fw['text']}'" for fw in cluster])
            return f"Filler words: {words}"

    def apply_filler_word_removal(self,
                                  timeline: Any,
                                  removal_recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply filler word removal to timeline by cutting recommended segments

        Args:
            timeline: Timeline object to modify
            removal_recommendations: List of segments to remove

        Returns:
            Summary of applied removals
        """
        try:
            segments_removed = 0
            total_duration_removed = 0.0

            for recommendation in removal_recommendations:
                if recommendation['should_remove']:
                    # Apply cut to timeline
                    # Note: This would integrate with the timeline editing logic
                    start_time = recommendation['start_time']
                    end_time = recommendation['end_time']

                    # For now, just log the removal
                    # In actual implementation, this would call timeline.remove_segment()
                    logger.info(f"Removing filler word segment: {start_time:.2f}s - {end_time:.2f}s")

                    segments_removed += 1
                    total_duration_removed += recommendation['duration']

            return {
                'success': True,
                'segments_removed': segments_removed,
                'total_duration_removed': total_duration_removed,
                'method': 'filler_word_removal'
            }

        except Exception as e:
            logger.error(f"Error applying filler word removal: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_filler_word_statistics(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive statistics about filler word usage

        Args:
            transcription_data: Full transcription data

        Returns:
            Dictionary with detailed statistics
        """
        detection_result = self.detect_filler_words(transcription_data, aggressive=False)

        if not detection_result['success']:
            return detection_result

        # Calculate per-speaker statistics
        speaker_stats = {}
        for fw in detection_result['filler_word_instances']:
            speaker = fw['speaker']
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    'count': 0,
                    'duration': 0.0,
                    'words': {}
                }

            speaker_stats[speaker]['count'] += 1
            speaker_stats[speaker]['duration'] += fw['duration']

            word = fw['text']
            if word in speaker_stats[speaker]['words']:
                speaker_stats[speaker]['words'][word] += 1
            else:
                speaker_stats[speaker]['words'][word] = 1

        return {
            'success': True,
            'total_filler_words': detection_result['total_filler_words'],
            'total_filler_duration': detection_result['total_filler_duration'],
            'filler_percentage': detection_result['filler_percentage'],
            'most_common_fillers': detection_result['most_common_fillers'],
            'speaker_statistics': speaker_stats,
            'filler_word_counts': detection_result['filler_word_counts']
        }
