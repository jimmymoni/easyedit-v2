from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Clip:
    """Represents a single clip in the timeline"""
    name: str
    start_time: float  # In seconds
    end_time: float    # In seconds
    duration: float    # In seconds
    track_index: int
    media_start: Optional[float] = None  # Source media start time
    media_end: Optional[float] = None    # Source media end time
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def timecode_start(self) -> str:
        """Convert start time to timecode format (HH:MM:SS:FF)"""
        return self._seconds_to_timecode(self.start_time)

    @property
    def timecode_end(self) -> str:
        """Convert end time to timecode format (HH:MM:SS:FF)"""
        return self._seconds_to_timecode(self.end_time)

    def _seconds_to_timecode(self, seconds: float, fps: int = 25) -> str:
        """Convert seconds to timecode format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

@dataclass
class Track:
    """Represents a timeline track"""
    index: int
    name: str
    track_type: str  # 'video', 'audio', 'subtitle'
    clips: List[Clip] = field(default_factory=list)
    enabled: bool = True
    locked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_clip(self, clip: Clip) -> None:
        """Add a clip to this track"""
        clip.track_index = self.index
        self.clips.append(clip)
        # Sort clips by start time
        self.clips.sort(key=lambda c: c.start_time)

    def remove_clip(self, clip: Clip) -> bool:
        """Remove a clip from this track"""
        if clip in self.clips:
            self.clips.remove(clip)
            return True
        return False

    def get_clips_in_range(self, start_time: float, end_time: float) -> List[Clip]:
        """Get all clips that overlap with the given time range"""
        return [
            clip for clip in self.clips
            if not (clip.end_time <= start_time or clip.start_time >= end_time)
        ]

@dataclass
class Timeline:
    """Represents the complete timeline structure"""
    name: str
    frame_rate: float = 25.0
    sample_rate: int = 48000
    duration: float = 0.0  # Total timeline duration in seconds
    tracks: List[Track] = field(default_factory=list)
    markers: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def add_track(self, track: Track) -> None:
        """Add a track to the timeline"""
        if not any(t.index == track.index for t in self.tracks):
            self.tracks.append(track)
            self.tracks.sort(key=lambda t: t.index)
        else:
            raise ValueError(f"Track with index {track.index} already exists")

    def get_track_by_index(self, index: int) -> Optional[Track]:
        """Get track by index"""
        return next((track for track in self.tracks if track.index == index), None)

    def get_tracks_by_type(self, track_type: str) -> List[Track]:
        """Get all tracks of a specific type"""
        return [track for track in self.tracks if track.track_type == track_type]

    def add_marker(self, time: float, name: str, color: str = "Red") -> None:
        """Add a marker to the timeline"""
        marker = {
            "time": time,
            "name": name,
            "color": color,
            "timecode": self._seconds_to_timecode(time)
        }
        self.markers.append(marker)
        self.markers.sort(key=lambda m: m["time"])

    def calculate_duration(self) -> float:
        """Calculate total timeline duration based on clips"""
        max_end_time = 0.0
        for track in self.tracks:
            for clip in track.clips:
                max_end_time = max(max_end_time, clip.end_time)
        self.duration = max_end_time
        return self.duration

    def _seconds_to_timecode(self, seconds: float) -> str:
        """Convert seconds to timecode format"""
        fps = int(self.frame_rate)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

    def get_timeline_stats(self) -> Dict[str, Any]:
        """Get statistics about the timeline"""
        total_clips = sum(len(track.clips) for track in self.tracks)
        audio_tracks = len(self.get_tracks_by_type('audio'))
        video_tracks = len(self.get_tracks_by_type('video'))

        return {
            "total_duration": self.duration,
            "total_clips": total_clips,
            "total_tracks": len(self.tracks),
            "audio_tracks": audio_tracks,
            "video_tracks": video_tracks,
            "markers": len(self.markers),
            "frame_rate": self.frame_rate,
            "sample_rate": self.sample_rate
        }