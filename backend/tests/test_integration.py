import pytest
import os
import tempfile
import numpy as np
import soundfile as sf
from unittest.mock import Mock, patch

from services.timeline_editor import TimelineEditingEngine
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter
from services.audio_analyzer import AudioAnalyzer
from services.edit_rules import EditRulesEngine

class TestTimelineProcessingIntegration:
    """Integration tests for complete timeline processing pipeline"""

    @pytest.fixture
    def timeline_editor(self):
        """Create timeline editing engine"""
        return TimelineEditingEngine()

    @pytest.fixture
    def real_audio_file(self, temp_dir):
        """Create a realistic test audio file with speech patterns"""
        # Create more realistic audio data
        duration = 60.0  # 1 minute
        sample_rate = 22050
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Create segments with different characteristics
        audio = np.zeros_like(t)

        # Speech segment 1 (0-15s) - Higher frequency, moderate volume
        mask1 = (t >= 0) & (t < 15)
        speech1 = 0.3 * np.sin(2 * np.pi * 200 * t[mask1])
        speech1 += 0.1 * np.sin(2 * np.pi * 400 * t[mask1])  # Harmonics
        speech1 *= (1 + 0.3 * np.random.random(len(speech1)))  # Speech-like variation
        audio[mask1] = speech1

        # Silence segment (15-18s)
        mask2 = (t >= 15) & (t < 18)
        audio[mask2] = 0.01 * np.random.random(np.sum(mask2))

        # Speech segment 2 (18-35s) - Different speaker characteristics
        mask3 = (t >= 18) & (t < 35)
        speech2 = 0.25 * np.sin(2 * np.pi * 150 * t[mask3])
        speech2 += 0.08 * np.sin(2 * np.pi * 300 * t[mask3])
        speech2 *= (1 + 0.4 * np.random.random(len(speech2)))
        audio[mask3] = speech2

        # Another silence (35-37s)
        mask4 = (t >= 35) & (t < 37)
        audio[mask4] = 0.005 * np.random.random(np.sum(mask4))

        # Final speech segment (37-55s)
        mask5 = (t >= 37) & (t < 55)
        speech3 = 0.35 * np.sin(2 * np.pi * 180 * t[mask5])
        speech3 += 0.12 * np.sin(2 * np.pi * 360 * t[mask5])
        speech3 *= (1 + 0.2 * np.random.random(len(speech3)))
        audio[mask5] = speech3

        # Final silence (55-60s)
        mask6 = (t >= 55) & (t < 60)
        audio[mask6] = 0.003 * np.random.random(np.sum(mask6))

        # Save to file
        audio_file = os.path.join(temp_dir, 'realistic_audio.wav')
        sf.write(audio_file, audio, sample_rate)

        return audio_file

    @pytest.fixture
    def realistic_drt_file(self, temp_dir):
        """Create a realistic DRT file for testing"""
        drt_content = """<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE xmeml>
        <xmeml version="5">
            <project>
                <name>Realistic Test Timeline</name>
                <children>
                    <sequence id="sequence-1">
                        <name>Interview Timeline</name>
                        <duration>1500</duration>
                        <rate>
                            <timebase>25</timebase>
                            <ntsc>FALSE</ntsc>
                        </rate>
                        <format>
                            <samplecharacteristics>
                                <rate>
                                    <timebase>25</timebase>
                                    <ntsc>FALSE</ntsc>
                                </rate>
                                <audio>
                                    <samplerate>48000</samplerate>
                                    <depth>16</depth>
                                </audio>
                            </samplecharacteristics>
                        </format>
                        <media>
                            <audio>
                                <format>
                                    <samplecharacteristics>
                                        <depth>16</depth>
                                        <samplerate>48000</samplerate>
                                    </samplecharacteristics>
                                </format>
                                <track>
                                    <clipitem id="clipitem-main">
                                        <name>Interview Audio</name>
                                        <enabled>TRUE</enabled>
                                        <duration>1500</duration>
                                        <rate>
                                            <timebase>25</timebase>
                                            <ntsc>FALSE</ntsc>
                                        </rate>
                                        <start>0</start>
                                        <end>1500</end>
                                        <in>0</in>
                                        <out>1500</out>
                                        <file id="file-main">
                                            <name>interview.wav</name>
                                            <pathurl>file://localhost/interview.wav</pathurl>
                                            <rate>
                                                <timebase>25</timebase>
                                                <ntsc>FALSE</ntsc>
                                            </rate>
                                            <duration>1500</duration>
                                        </file>
                                    </clipitem>
                                </track>
                            </audio>
                        </media>
                        <timecode>
                            <rate>
                                <timebase>25</timebase>
                                <ntsc>FALSE</ntsc>
                            </rate>
                            <string>01:00:00:00</string>
                            <frame>90000</frame>
                        </timecode>
                    </sequence>
                </children>
            </project>
        </xmeml>"""

        drt_file = os.path.join(temp_dir, 'realistic_timeline.drt')
        with open(drt_file, 'w', encoding='utf-8') as f:
            f.write(drt_content)

        return drt_file

    def test_complete_processing_pipeline_without_ai(self, timeline_editor, real_audio_file, realistic_drt_file):
        """Test complete processing pipeline without AI features"""
        processing_options = {
            'enable_transcription': False,
            'enable_ai_enhancements': False,
            'remove_silence': True,
            'min_clip_length': 3.0,
            'silence_threshold_db': -35
        }

        result = timeline_editor.process_timeline(
            real_audio_file,
            realistic_drt_file,
            processing_options
        )

        assert result['success'] == True
        assert 'output_file' in result
        assert 'timeline_comparison' in result
        assert 'insights' in result
        assert 'processing_stats' in result

        # Check timeline comparison
        comparison = result['timeline_comparison']
        assert comparison['original']['duration'] > 0
        assert comparison['edited']['duration'] > 0
        assert comparison['reduction']['duration_seconds'] >= 0

        # Output file should exist and be valid DRT
        assert os.path.exists(result['output_file'])

        # Parse the output to verify it's valid
        parser = DRTParser()
        output_timeline = parser.parse_file(result['output_file'])
        assert output_timeline is not None
        assert len(output_timeline.tracks) > 0

    @patch('services.soniox_client.SonioxClient.transcribe_audio')
    def test_processing_with_mock_transcription(self, mock_transcribe, timeline_editor, real_audio_file, realistic_drt_file):
        """Test processing pipeline with mocked transcription"""
        # Mock transcription response
        mock_transcription = {
            'transcript': 'This is a mock transcription of the interview content.',
            'segments': [
                {
                    'speaker': 'Speaker1',
                    'start_time': 2.0,
                    'end_time': 15.0,
                    'text': 'Welcome to our interview today.',
                    'confidence': 0.94,
                    'words': [
                        {'text': 'Welcome', 'start_time': 2.0, 'end_time': 2.8, 'confidence': 0.96},
                        {'text': 'to', 'start_time': 2.9, 'end_time': 3.1, 'confidence': 0.92}
                    ]
                },
                {
                    'speaker': 'Speaker2',
                    'start_time': 18.0,
                    'end_time': 35.0,
                    'text': 'Thank you for having me here.',
                    'confidence': 0.89,
                    'words': [
                        {'text': 'Thank', 'start_time': 18.0, 'end_time': 18.5, 'confidence': 0.91},
                        {'text': 'you', 'start_time': 18.6, 'end_time': 18.9, 'confidence': 0.87}
                    ]
                }
            ],
            'speakers': ['Speaker1', 'Speaker2'],
            'duration': 35.0,
            'confidence': 0.915,
            'word_count': 10
        }
        mock_transcribe.return_value = mock_transcription

        processing_options = {
            'enable_transcription': True,
            'enable_speaker_diarization': True,
            'enable_ai_enhancements': False,
            'remove_silence': True,
            'split_on_speaker_change': True
        }

        result = timeline_editor.process_timeline(
            real_audio_file,
            realistic_drt_file,
            processing_options
        )

        assert result['success'] == True

        # Should have transcription insights
        insights = result['insights']
        if 'transcription' in insights:
            assert insights['transcription']['speakers_detected'] == 2
            assert insights['transcription']['words_transcribed'] == 10

        # Verify transcription was called
        mock_transcribe.assert_called_once()

    def test_processing_preview(self, timeline_editor, real_audio_file, realistic_drt_file):
        """Test processing preview functionality"""
        preview = timeline_editor.get_processing_preview(real_audio_file, realistic_drt_file)

        assert preview['success'] == True
        assert 'preview' in preview

        preview_data = preview['preview']
        assert 'original_timeline' in preview_data
        assert 'audio_analysis' in preview_data
        assert 'estimated_changes' in preview_data

        # Check estimated changes
        estimated = preview_data['estimated_changes']
        assert 'silence_segments_to_remove' in estimated
        assert 'estimated_duration_reduction_seconds' in estimated
        assert 'estimated_compression_ratio' in estimated

    def test_audio_analysis_integration(self, real_audio_file):
        """Test audio analysis integration in isolation"""
        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(real_audio_file)

        assert success == True

        # Test all analysis methods work together
        silence_segments = analyzer.detect_silence()
        speech_segments = analyzer.detect_speech_segments()
        features = analyzer.analyze_audio_features()
        cut_points = analyzer.find_optimal_cut_points()
        summary = analyzer.get_audio_summary()

        # Basic validation
        assert len(silence_segments) >= 2  # Should detect silence segments we created
        assert len(speech_segments) >= 3   # Should detect speech segments
        assert len(features) > 10         # Should have comprehensive features
        assert isinstance(cut_points, list)
        assert summary['basic_info']['duration'] > 50  # ~60 seconds

        # Silence and speech should complement each other
        total_silence = sum(seg['duration'] for seg in silence_segments)
        total_speech = sum(seg['duration'] for seg in speech_segments)
        total_covered = total_silence + total_speech

        # Should cover most of the audio (allowing for detection margins)
        assert total_covered >= analyzer.duration * 0.85

    def test_drt_roundtrip_with_processing(self, realistic_drt_file, temp_dir):
        """Test DRT parsing, processing, and writing roundtrip"""
        # Parse original
        parser = DRTParser()
        original_timeline = parser.parse_file(realistic_drt_file)

        # Apply some basic processing
        edit_engine = EditRulesEngine()
        edit_engine.set_rule('min_clip_length', 2.0)

        # Process the timeline (without audio analysis for simplicity)
        processed_timeline = edit_engine.apply_editing_rules(
            original_timeline,
            None,  # No transcription
            None   # No audio analysis
        )

        # Write processed timeline
        writer = DRTWriter()
        output_file = os.path.join(temp_dir, 'processed_timeline.drt')
        success = writer.write_timeline(processed_timeline, output_file)

        assert success == True
        assert os.path.exists(output_file)

        # Parse the result
        final_timeline = parser.parse_file(output_file)

        # Verify roundtrip maintained key properties
        assert final_timeline.frame_rate == original_timeline.frame_rate
        assert final_timeline.sample_rate == original_timeline.sample_rate
        assert len(final_timeline.tracks) == len(original_timeline.tracks)

    @patch('services.timeline_editor.TimelineEditingEngine._perform_transcription')
    def test_error_handling_in_pipeline(self, mock_transcription, timeline_editor, real_audio_file, realistic_drt_file):
        """Test error handling throughout the pipeline"""
        # Mock transcription to raise an error
        mock_transcription.side_effect = Exception("Transcription service unavailable")

        processing_options = {
            'enable_transcription': True,
            'enable_ai_enhancements': False,
            'remove_silence': True
        }

        result = timeline_editor.process_timeline(
            real_audio_file,
            realistic_drt_file,
            processing_options
        )

        # Should handle transcription errors gracefully
        assert result['success'] == False
        assert 'error' in result
        assert 'processing_stats' in result

    def test_processing_with_different_parameters(self, timeline_editor, real_audio_file, realistic_drt_file):
        """Test processing with various parameter combinations"""
        test_cases = [
            # Conservative settings
            {
                'enable_transcription': False,
                'remove_silence': False,
                'min_clip_length': 10.0,
                'silence_threshold_db': -50
            },
            # Aggressive settings
            {
                'enable_transcription': False,
                'remove_silence': True,
                'min_clip_length': 1.0,
                'silence_threshold_db': -20
            },
            # Moderate settings
            {
                'enable_transcription': False,
                'remove_silence': True,
                'min_clip_length': 5.0,
                'silence_threshold_db': -35
            }
        ]

        results = []
        for i, options in enumerate(test_cases):
            result = timeline_editor.process_timeline(
                real_audio_file,
                realistic_drt_file,
                options
            )

            assert result['success'] == True, f"Test case {i} failed"
            results.append(result)

            # Verify output file exists and is valid
            assert os.path.exists(result['output_file'])

            # Clean up
            os.remove(result['output_file'])

        # Different settings should potentially produce different results
        durations = [r['timeline_comparison']['edited']['duration'] for r in results]

        # At least one should be different (aggressive vs conservative)
        assert not all(d == durations[0] for d in durations), "Different settings should produce different results"

    def test_processing_empty_audio(self, timeline_editor, realistic_drt_file, temp_dir):
        """Test processing with minimal/silent audio"""
        # Create very quiet audio file
        duration = 30.0
        sample_rate = 22050
        quiet_audio = 0.001 * np.random.random(int(duration * sample_rate))

        quiet_audio_file = os.path.join(temp_dir, 'quiet_audio.wav')
        sf.write(quiet_audio_file, quiet_audio, sample_rate)

        processing_options = {
            'enable_transcription': False,
            'remove_silence': True,
            'min_clip_length': 2.0
        }

        result = timeline_editor.process_timeline(
            quiet_audio_file,
            realistic_drt_file,
            processing_options
        )

        # Should handle quiet audio gracefully
        assert result['success'] == True
        assert result['timeline_comparison']['edited']['duration'] >= 0

    def test_large_file_processing_simulation(self, timeline_editor, realistic_drt_file, temp_dir):
        """Test processing simulation with larger file parameters"""
        # Create longer audio (simulate large file processing)
        duration = 300.0  # 5 minutes
        sample_rate = 22050

        # Create segments that simulate a longer interview
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = np.zeros_like(t)

        # Add multiple speech segments with silence
        segment_length = 45.0  # 45 second segments
        silence_length = 5.0   # 5 second silence between

        for i in range(int(duration / (segment_length + silence_length))):
            start_time = i * (segment_length + silence_length)
            end_time = start_time + segment_length

            if end_time > duration:
                break

            mask = (t >= start_time) & (t < end_time)
            freq = 150 + (i * 25)  # Different frequency per segment
            speech = 0.2 * np.sin(2 * np.pi * freq * t[mask])
            speech *= (1 + 0.3 * np.random.random(len(speech)))
            audio[mask] = speech

        large_audio_file = os.path.join(temp_dir, 'large_audio.wav')
        sf.write(large_audio_file, audio, sample_rate)

        processing_options = {
            'enable_transcription': False,
            'remove_silence': True,
            'min_clip_length': 3.0
        }

        result = timeline_editor.process_timeline(
            large_audio_file,
            realistic_drt_file,
            processing_options
        )

        assert result['success'] == True

        # Should have meaningful reduction for a file with structured silence
        comparison = result['timeline_comparison']
        reduction_percentage = (comparison['reduction']['duration_seconds'] / comparison['original']['duration']) * 100

        # Should have some reduction due to silence removal
        assert reduction_percentage > 5.0  # At least 5% reduction

        # Processing should complete in reasonable time (check via processing stats)
        processing_stats = result['processing_stats']
        assert processing_stats['total_duration'] < 60.0  # Should complete in under 1 minute