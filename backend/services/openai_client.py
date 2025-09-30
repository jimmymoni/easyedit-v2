from openai import OpenAI
from typing import Dict, Any, List, Optional
from config import Config
import logging

logger = logging.getLogger(__name__)

class OpenAIClient:
    """Client for OpenAI API integration for AI-powered enhancements"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.OPENAI_API_KEY
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OpenAI API key not configured")

    def enhance_transcription(self, transcription: str, context: str = "") -> Dict[str, Any]:
        """
        Use GPT to enhance and clean up transcription text
        """
        if not self.client:
            return {'success': False, 'error': 'OpenAI API key not configured'}

        try:
            prompt = f"""
            Clean up and enhance the following transcription text. Fix any obvious errors,
            add proper punctuation, and maintain the original meaning. If context is provided,
            use it to improve accuracy.

            Context: {context}

            Original transcription:
            {transcription}

            Enhanced transcription:
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that cleans up transcription text while maintaining accuracy and original meaning."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )

            enhanced_text = response.choices[0].message.content.strip()

            return {
                'success': True,
                'original': transcription,
                'enhanced': enhanced_text,
                'improvement_score': self._calculate_improvement_score(transcription, enhanced_text)
            }

        except Exception as e:
            logger.error(f"Error enhancing transcription: {str(e)}")
            return {'success': False, 'error': str(e)}

    def extract_highlights(self, transcription_data: Dict[str, Any], duration_limit: float = 300) -> Dict[str, Any]:
        """
        Use AI to identify and extract the most important/interesting segments
        """
        if not self.client:
            return {'success': False, 'error': 'OpenAI API key not configured'}

        try:
            transcript = transcription_data.get('transcript', '')
            segments = transcription_data.get('segments', [])

            if not transcript:
                return {'success': False, 'error': 'No transcript available'}

            prompt = f"""
            Analyze the following transcript and identify the most important, interesting, or valuable segments
            that would be worth keeping in an edited version. Consider:
            - Key information or insights
            - Emotional moments
            - Important decisions or conclusions
            - Engaging or entertaining content
            - Educational value

            Target total duration: {duration_limit} seconds

            Transcript:
            {transcript[:3000]}  # Truncate for token limits

            Please respond with a JSON array of time ranges in this format:
            [
                {{"start_time": 45.2, "end_time": 120.8, "reason": "Key insight about the topic", "priority": "high"}},
                {{"start_time": 180.5, "end_time": 245.3, "reason": "Emotional climax of story", "priority": "medium"}}
            ]
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert video editor who identifies the most valuable segments in content for creating highlight reels."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.2
            )

            # Parse AI response
            ai_response = response.choices[0].message.content.strip()

            # Try to extract JSON from the response
            import json
            import re

            json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
            if json_match:
                highlights = json.loads(json_match.group())
            else:
                # Fallback: use timestamp detection
                highlights = self._extract_highlights_fallback(segments, duration_limit)

            return {
                'success': True,
                'highlights': highlights,
                'total_suggested_duration': sum(h.get('end_time', 0) - h.get('start_time', 0) for h in highlights),
                'ai_reasoning': ai_response
            }

        except Exception as e:
            logger.error(f"Error extracting highlights: {str(e)}")
            # Fallback to basic highlight extraction
            return self._extract_highlights_fallback(segments, duration_limit)

    def generate_summary(self, transcription: str, max_length: int = 200) -> Dict[str, Any]:
        """
        Generate a concise summary of the transcription content
        """
        if not self.client:
            return {'success': False, 'error': 'OpenAI API key not configured'}

        try:
            prompt = f"""
            Create a concise summary of the following transcript in approximately {max_length} words.
            Focus on the main topics, key insights, and important information discussed.

            Transcript:
            {transcription[:4000]}  # Truncate for token limits

            Summary:
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional content summarizer who creates clear, concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.1
            )

            summary = response.choices[0].message.content.strip()

            return {
                'success': True,
                'summary': summary,
                'original_length': len(transcription.split()),
                'summary_length': len(summary.split()),
                'compression_ratio': len(summary.split()) / len(transcription.split()) if transcription else 0
            }

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return {'success': False, 'error': str(e)}

    def suggest_editing_improvements(self, timeline_stats: Dict[str, Any], transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest editing improvements based on timeline analysis and content
        """
        if not self.client:
            return {'success': False, 'error': 'OpenAI API key not configured'}

        try:
            # Prepare analysis data
            analysis_text = f"""
            Timeline Statistics:
            - Original duration: {timeline_stats.get('original_duration', 0)} seconds
            - Current clips: {timeline_stats.get('edited_clips', 0)}
            - Tracks: {timeline_stats.get('tracks_processed', 0)}

            Content Analysis:
            - Speakers: {len(transcription_data.get('speakers', []))} detected
            - Segments: {len(transcription_data.get('segments', []))}
            - Average confidence: {transcription_data.get('confidence', 0):.2f}
            """

            prompt = f"""
            Based on the following timeline and content analysis, suggest specific editing improvements
            that could make this content more engaging and professional. Consider:
            - Pacing and flow
            - Content structure
            - Audience engagement
            - Technical quality

            {analysis_text}

            Please provide 3-5 specific, actionable suggestions for improving this edit.
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert video editor and content strategist who provides actionable editing advice."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )

            suggestions = response.choices[0].message.content.strip()

            return {
                'success': True,
                'suggestions': suggestions,
                'analysis_data': analysis_text
            }

        except Exception as e:
            logger.error(f"Error generating editing suggestions: {str(e)}")
            return {'success': False, 'error': str(e)}

    def generate_markers_and_chapters(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate intelligent markers and chapter breaks based on content analysis
        """
        if not self.client:
            return {'success': False, 'error': 'OpenAI API key not configured'}

        try:
            segments = transcription_data.get('segments', [])
            transcript = transcription_data.get('transcript', '')

            # Create a condensed transcript for analysis
            condensed_segments = []
            for i, segment in enumerate(segments):
                if i % 10 == 0:  # Sample every 10th segment to reduce token usage
                    condensed_segments.append({
                        'time': segment['start_time'],
                        'text': segment['text'][:100]  # Truncate long segments
                    })

            prompt = f"""
            Based on the following transcript segments, suggest logical chapter breaks and important markers.
            Consider topic changes, speaker changes, and natural breaks in the content.

            Segments:
            {str(condensed_segments[:20])}  # Limit for token usage

            Please respond with JSON format:
            {{
                "chapters": [
                    {{"start_time": 0, "title": "Introduction", "description": "Opening remarks"}},
                    {{"start_time": 120, "title": "Main Topic", "description": "Discussion of key points"}}
                ],
                "markers": [
                    {{"time": 45, "name": "Important Quote", "type": "highlight"}},
                    {{"time": 180, "name": "Action Item", "type": "note"}}
                ]
            }}
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert content organizer who creates logical chapter breaks and meaningful markers for video content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.2
            )

            # Parse AI response
            ai_response = response.choices[0].message.content.strip()

            try:
                import json
                markers_data = json.loads(ai_response)
            except json.JSONDecodeError:
                # Fallback to basic marker generation
                markers_data = self._generate_basic_markers(segments)

            return {
                'success': True,
                'chapters': markers_data.get('chapters', []),
                'markers': markers_data.get('markers', []),
                'ai_response': ai_response
            }

        except Exception as e:
            logger.error(f"Error generating markers and chapters: {str(e)}")
            return self._generate_basic_markers(transcription_data.get('segments', []))

    def _calculate_improvement_score(self, original: str, enhanced: str) -> float:
        """Calculate a simple improvement score based on text changes"""
        try:
            # Simple heuristics for improvement
            original_sentences = len([s for s in original.split('.') if s.strip()])
            enhanced_sentences = len([s for s in enhanced.split('.') if s.strip()])

            # Assume better punctuation = improvement
            punctuation_improvement = enhanced.count('.') + enhanced.count(',') - original.count('.') - original.count(',')

            # Normalize score between 0 and 1
            score = min(1.0, max(0.0, 0.5 + (punctuation_improvement / 100)))
            return score
        except:
            return 0.5

    def _extract_highlights_fallback(self, segments: List[Dict[str, Any]], duration_limit: float) -> Dict[str, Any]:
        """Fallback method for highlight extraction when AI fails"""
        try:
            # Simple fallback: select segments with higher confidence and longer duration
            scored_segments = []
            for segment in segments:
                score = segment.get('confidence', 0.5) * (segment.get('end_time', 0) - segment.get('start_time', 0))
                scored_segments.append((score, segment))

            # Sort by score and select top segments within duration limit
            scored_segments.sort(reverse=True, key=lambda x: x[0])

            selected_highlights = []
            total_duration = 0

            for score, segment in scored_segments:
                segment_duration = segment.get('end_time', 0) - segment.get('start_time', 0)
                if total_duration + segment_duration <= duration_limit:
                    selected_highlights.append({
                        'start_time': segment.get('start_time', 0),
                        'end_time': segment.get('end_time', 0),
                        'reason': 'High confidence segment',
                        'priority': 'medium'
                    })
                    total_duration += segment_duration

            return {
                'success': True,
                'highlights': selected_highlights,
                'total_suggested_duration': total_duration,
                'method': 'fallback'
            }
        except Exception as e:
            logger.error(f"Fallback highlight extraction failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _generate_basic_markers(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate basic markers when AI analysis fails"""
        try:
            markers = []
            chapters = []

            if segments:
                # Create chapter at start
                chapters.append({
                    'start_time': 0,
                    'title': 'Beginning',
                    'description': 'Content starts'
                })

                # Add markers at regular intervals
                total_duration = segments[-1].get('end_time', 0) if segments else 0
                interval = max(60, total_duration / 10)  # Marker every minute or 10% of content

                for i in range(1, int(total_duration / interval) + 1):
                    time = i * interval
                    markers.append({
                        'time': time,
                        'name': f'Marker {i}',
                        'type': 'auto'
                    })

                    if i % 3 == 0:  # Chapter every 3 markers
                        chapters.append({
                            'start_time': time,
                            'title': f'Section {i//3 + 1}',
                            'description': 'Auto-generated chapter'
                        })

            return {
                'success': True,
                'chapters': chapters,
                'markers': markers,
                'method': 'basic'
            }
        except Exception as e:
            logger.error(f"Basic marker generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}