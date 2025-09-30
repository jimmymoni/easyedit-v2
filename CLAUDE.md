# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **easyedit-v2**, a platform that automates timeline edits based on source audio and timing XML (.drt) files. The goal is to ingest an audio file plus its accompanying XML timing file, apply cuts and edits programmatically, and generate a new .drt for DaVinci Resolve import.

## Architecture

- **Backend**: Flask web server in `backend/app.py` exposing REST endpoints
- **Frontend**: (to be built) React UI for uploading audio + XML and downloading edited .drt
- **Virtual Environment**: Python venv in `venv/`
- **Key Workflow**:
  1. Receive `POST /upload` with `audio` and `drt` files
  2. Parse `.drt` XML to extract segment timings
  3. Apply cut/edit rules to the audio and timing data
  4. Produce a new `.drt` XML reflecting edits
  5. Return edited `.drt` for DaVinci Resolve import

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
```

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

## 🎯 Current Progress & Status

### Development Status (Updated: September 30, 2024)

**Backend: ✅ COMPLETE (Production Ready)**
- ✅ Flask application with JWT authentication
- ✅ Rate limiting with multi-tier user support
- ✅ WebSocket real-time job status updates
- ✅ Celery async processing with Redis
- ✅ Audio analysis and AI-powered editing
- ✅ Secure DRT XML parsing with XXE protection
- ✅ Comprehensive test suite and monitoring
- ✅ Docker containerization ready

**Frontend: 🔄 IN PROGRESS (20% Complete)**
- ✅ React + TypeScript + Tailwind CSS scaffolding
- ✅ Basic component structure (FileDropzone, ProcessingStatus, etc.)
- ✅ API client configured
- ❌ Authentication integration (NEXT PRIORITY)
- ❌ WebSocket real-time updates
- ❌ Modern UI polish and user experience

**Next Immediate Tasks:**
1. 🎯 **Frontend Authentication Integration** - Add React Auth Context with JWT
2. 🎯 **Login/Register UI Components** - Build clean auth forms
3. 🎯 **Protected Routes & API Headers** - Secure frontend-backend communication
4. 🎯 **WebSocket Frontend Integration** - Real-time progress updates
5. 🎯 **UI/UX Polish** - Professional drag-drop interface

### Last Session Summary
- **Completed**: JWT authentication system, rate limiting, WebSocket implementation
- **Git Status**: All changes committed and pushed to repository
- **Ready For**: Frontend development and authentication integration

### Session Handoff Protocol
**To start new session**: Ask Claude to "Check current progress and tell me what to work on next"
**To end session**: Ask Claude to "Update progress and commit everything to git"

## Development Notes

- Full-stack application with React frontend and Flask backend
- AI-powered timeline editing using Soniox and OpenAI APIs
- Production-ready with monitoring, logging, and error handling
- Containerized deployment with Docker Compose
- Comprehensive API with rate limiting and validation
- Real-time job status tracking and progress updates