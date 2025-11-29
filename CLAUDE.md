# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **easyedit-v2**, a platform that automates timeline edits based on source audio and timing XML (.drt) files. The goal is to ingest an audio file plus its accompanying XML timing file, apply cuts and edits programmatically, and generate a new .drt for DaVinci Resolve import.

## Architecture

### Backend (Flask + Python 3.13)
- **API**: Flask REST API with JWT authentication
- **Transcription**: Replicate Whisper (incredibly-fast-whisper + pyannote diarization) - $0.078/hour
- **AI Enhancement**: OpenAI GPT-4 (transcript improvement, highlights, summaries, chapters)
- **Audio Processing**: Scipy-based SimpleAudioAnalyzer (energy detection, silence removal, optimal cut points)
- **Task Queue**: Celery with Redis (async job processing)
- **Audio Formats**: FFmpeg for multi-format support (WAV, MP3, M4A, AAC, FLAC)
- **Security**: XXE protection (defusedxml), path traversal prevention, rate limiting, resource controls

### Frontend (React + TypeScript)
- **Framework**: React 18 + TypeScript + Tailwind CSS
- **Build Tool**: Vite (fast development builds)
- **API Client**: Axios with automatic JWT token refresh
- **Waveform Visualization**: WaveSurfer.js for interactive audio editing
- **Design System**: Professional dark UI with orange brand identity (#FF6B35)

### Key Workflow

**REQUIRED INPUTS:**
- ⚠️ **Audio file** (WAV, MP3, M4A, AAC, or FLAC) - **MANDATORY**
- ⚠️ **DaVinci Resolve timeline file** (.drt or .xml) - **MANDATORY**

**Both files must be uploaded together.** This application **edits existing timelines**, it does **not** generate new timelines from audio alone.

**Processing Steps:**
  1. Receive `POST /upload` with **both** `audio` and `drt` files (BOTH REQUIRED)
  2. Transcribe audio with Replicate Whisper (speaker diarization)
  3. Parse `.drt` XML to extract existing timeline structure and segment timings
  4. Analyze audio for silence, speech segments, optimal cut points
  5. Apply AI enhancement (OpenAI) for highlights, summaries, chapters
  6. Apply intelligent editing rules to timeline data
  7. Generate new `.drt` XML reflecting edits
  8. Return edited `.drt` for DaVinci Resolve import

## Development Commands

### Environment Setup
```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Unix/Mac)
source venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install

# Install ffmpeg (required for MP3/M4A/AAC support)
# Windows: Download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH
# macOS: brew install ffmpeg
# Linux: sudo apt-get install ffmpeg
```

### Audio Format Support

The application supports multiple audio formats:
- **WAV** (always supported, no dependencies required)
- **MP3** (requires ffmpeg)
- **M4A/AAC** (requires ffmpeg)
- **FLAC** (requires ffmpeg)

**Installing ffmpeg:**

- **Windows**:
  1. Download from https://www.gyan.dev/ffmpeg/builds/
  2. Extract the archive
  3. Add the `bin` folder to your system PATH
  4. Restart your terminal/IDE

- **macOS**:
  ```bash
  brew install ffmpeg
  ```

- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt-get update
  sudo apt-get install ffmpeg
  ```

- **Linux (RHEL/CentOS)**:
  ```bash
  sudo yum install ffmpeg
  ```

**Verifying ffmpeg installation:**
```bash
ffmpeg -version
```

If ffmpeg is not installed, the application will:
- Start successfully but display a warning
- Only support WAV files
- Reject MP3/M4A/AAC uploads with a clear error message

### Running the Application

#### Development Mode
```bash
# Terminal 1 - Backend
cd backend
python app.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

#### Production Mode with Docker
```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Variables

Create a `.env` file in the project root:
```bash
# Required API Keys
SONIOX_API_KEY=your_soniox_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional Configuration
MAX_FILE_SIZE_MB=500
TEMP_FILE_RETENTION_HOURS=24
MIN_CLIP_LENGTH_SECONDS=5
SILENCE_THRESHOLD_DB=-40
LOG_LEVEL=INFO
```

### API Endpoints

#### Core Endpoints
- `POST /upload` - Upload audio and DRT files for processing
- `POST /process/<job_id>` - Start timeline processing with options
- `GET /status/<job_id>` - Get processing status and progress
- `GET /download/<job_id>` - Download processed .drt file

#### Management Endpoints
- `GET /health` - Comprehensive health check with system metrics
- `GET /metrics` - System performance and usage metrics
- `GET /jobs` - List recent processing jobs
- `GET /ai-enhancements/<job_id>` - Get AI enhancement details
- `GET /preview/<job_id>` - Preview processing without executing
- `POST /cleanup` - Manually trigger file cleanup

#### Rate Limits
- General API: 60 requests/minute, 1000 requests/hour
- Upload: 5 requests/minute, 50 requests/hour
- Processing: 2 requests/minute, 20 requests/hour
- Download: 10 requests/minute, 100 requests/hour

## Project Structure

### Backend (`backend/`)
- `app.py` - Main Flask application with comprehensive error handling
- `config.py` - Configuration management with environment variables
- `models/` - Data models for Timeline, Track, and Clip objects
- `parsers/` - DRT file parsing and writing utilities
  - **CRITICAL XML STRUCTURE RULES** (DaVinci Resolve compatibility):
    1. **Root Structure**: `<xmeml><sequence>` (NO `<project><children>` wrappers)
    2. **Canonical File Block**: Defined ONCE in `<media>` section (after all tracks)
    3. **Clipitem References**: ALL clips reference file by ID (`<file id="file-1"/>` self-closing)
    4. **Audio Tracks**: Must exist with matching clipitems for each video clip
    5. **In/Out Values**: Must reflect actual source media positions (not all zeros)
  - **Fixed 2025-11-29**: Canonical file block now correctly placed in `<media>` (not in first clipitem)
  - **Validation**: Run `backend/test_xml_structure_fix.py` to verify XML structure
  - Repair script available: `scripts/repair_xml_structure.py` for fixing old broken XMLs
- `services/` - Core business logic (audio analysis, AI, editing rules)
- `utils/` - Production utilities (logging, monitoring, rate limiting)
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration

### Frontend (`frontend/`)
- `src/App.tsx` - Main React application
- `src/components/` - React components for UI
- `src/services/api.ts` - API client with axios
- `src/types/` - TypeScript type definitions
- `package.json` - Node.js dependencies
- `Dockerfile` - Container configuration

### Infrastructure
- `docker-compose.yml` - Multi-container deployment
- `nginx.conf` - Reverse proxy and load balancing
- `.env.example` - Environment variable template

## Production Features

### Monitoring & Health Checks
- System resource monitoring (CPU, memory, disk)
- API request metrics and error tracking
- Processing job success/failure rates
- External dependency health checks (Soniox, OpenAI APIs)
- Comprehensive logging with rotation

### Security & Reliability
- Rate limiting per endpoint and client
- File validation and size limits
- Circuit breakers for external API calls
- Input validation and sanitization
- Error handling with detailed logging
- CORS configuration for frontend integration

### Performance Optimization
- Request/response compression
- Static asset caching
- Background job processing
- Automatic file cleanup
- Performance logging and metrics

### Deployment
- Docker containerization
- Multi-stage builds for optimization
- Health checks and restart policies
- Nginx reverse proxy with rate limiting
- Environment-based configuration

## 🎯 Current System Status

**Backend: ✅ PRODUCTION READY**
- Flask REST API with JWT auth (Python 3.13)
- **Transcription**: Replicate Whisper (PRIMARY $0.078/hr) + Google Cloud STT V1 (BACKUP $1.62/hr)
- **AI Enhancement**: OpenAI GPT-4 (transcript, highlights, summaries, chapters)
- **Audio**: scipy-based SimpleAudioAnalyzer + FFmpeg (WAV/MP3/M4A/AAC/FLAC)
- **God Mode**: AI conversational editor with real audio extraction
- **Security**: XXE protection, path validation, rate limiting, resource controls

**Frontend: ✅ PRODUCTION READY**
- React 18 + TypeScript + Tailwind CSS
- JWT auth with auto-refresh
- WaveSurfer.js waveform visualization (original vs edited)
- God Mode chat interface
- Professional dark UI (#FF6B35 brand)

**Key Features**:
- Natural language editing ("make a montage of 'best moments'")
- Real audio extraction/concatenation (FFmpeg)
- Timeline preview (tight/normal/loose cuts)
- DRT XML generation
- Interactive waveform viewer

**Development History**: See [SESSION_HISTORY.md](./SESSION_HISTORY.md) for detailed session logs

**Next Priorities**:
1. **UI/UX**: Processing time estimates, Shadcn UI, Playwright testing
2. **Testing**: Real data validation with Malayalam/English content
3. **Deploy**: Docker Compose, Redis, Nginx, cloud deployment

## 🎨 Design System

**IMPORTANT**: All UI development MUST follow **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)**

**Key Rules**:
- Background: `#000000` (pure black)
- Brand: `#FF6B35` (orange) for ALL interactive elements (NEVER blue/green)
- White cards: `bg-card` | Dark surfaces: `bg-[#181818]`
- Cards: `rounded-xl` (12px) | Spacing: `p-6` or `p-8`

**Reference Components**: `UploadProgress.tsx`, `ProcessingOptionsTable.tsx`, `AudioUploadZone.tsx`

## 🔍 Tech Stack Quick Reference

### Transcription
1. **Replicate Whisper** (PRIMARY) - `backend/services/replicate_whisper_client.py`
   - Cost: $0.078/hr | Model: incredibly-fast-whisper + pyannote diarization
   - **CRITICAL**: Custom `httpx.Timeout(write=600.0)` to prevent upload timeouts

2. **Google Cloud STT V1** (BACKUP) - `backend/services/google_stt_v1_client.py`
   - Cost: $1.62/hr | 125+ languages, Indian English optimization

### AI Enhancement
- **OpenAI GPT-4** - `backend/services/openai_client.py`
- Transcript improvement, highlights, summaries, chapters

### Audio Processing
- **SimpleAudioAnalyzer** - `backend/services/simple_audio_analyzer.py`
- Scipy-based (Python 3.13), energy detection, silence removal, cut points

### God Mode AI Editor

**Components**:
- `backend/services/ai_chat_handler.py` - GPT-4 intent detection
- `backend/services/ai_editor.py` - Timeline transformation
- `backend/services/audio_extractor.py` - FFmpeg audio extraction
- `backend/system_prompts/godmode_adaptive.txt` - AI behavior rules (119 lines)

**Supported Commands**:
1. **Short-form** (Instagram/TikTok/Shorts): "make a 60s reel" → 30-90s clips
2. **Montage**: "compile all 'money in the bank'" → phrase compilation (tight/normal/loose)
3. **Filler removal**: "remove um and uh" → detects um, uh, like, you know, etc.
4. **Silence**: "remove silence >2s" → cuts long pauses
5. **Speaker filter**: "keep only Speaker 1" → speaker-based filtering

**API Endpoints**:
- `POST /ai-chat` - Natural language message → options
- `POST /ai-preview` - Preview cuts before execution
- `POST /ai-edit` - Execute edit (timeline + audio)
- `GET /timeline-comparison/<job_id>` - Original vs edited diff
- `GET /audio/<job_id>/edited` - Edited audio file

**Workflow**: Message → GPT-4 intent → Options → Preview → Execute → Timeline + Audio + DRT

**Requirements**: Completed job + transcription (for montage/speaker), OpenAI API key (for short-form)

**Limitations**: 4000 char transcript limit, English-only fillers, number-based speakers only