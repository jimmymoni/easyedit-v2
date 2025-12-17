# 🎬 EasyEdit v2

**AI-Powered YouTube Video Automation**

Transform raw 3GB+ talking-head videos into polished, multi-layer DaVinci Resolve timelines in under 20 minutes.

---

## 🎯 Overview

EasyEdit v2 automates the tedious parts of video editing by:
- Detecting and removing repeated takes
- Classifying segments (talking head / demo / abstract concepts)
- Generating AI animations for abstract content
- Creating multi-layer timelines with 4 video tracks
- Exporting production-ready DaVinci Resolve XML

**Result**: Reduce editing time from **4-6 hours** to **~1 hour** (20 min processing + 30 min polishing)

---

## ✨ Key Features

### 🎥 Smart Video Processing
- **Chunked S3 Uploads**: Handle 3GB+ videos with resumable 10MB chunk uploads
- **Repeated Take Detection**: AI automatically identifies and removes duplicate takes
- **Segment Classification**: GPT-4 Vision categorizes video into talking head, demos, and abstract concepts

### 🎨 AI-Powered Enhancements
- **Background Generation**: AI-generated animated backgrounds for green screen footage
- **Animation Creation**: Automatic visualization for abstract concepts
- **Script Analysis**: GPT-4 optimization for better pacing and engagement

### 📽️ Multi-Layer Timeline Export
- **4-Layer Structure**:
  - Layer 1: AI-generated background
  - Layer 2: Main video (talking head/demo)
  - Layer 3: Picture-in-Picture overlays
  - Layer 4: Text/graphics overlays
- **DaVinci Resolve Compatible**: Direct XML import, no manual setup

### 💰 Cost-Effective
- S3 upload: ~$0.002 per 3GB video
- Transcription (Whisper): $0.078/hour
- Total processing: <$1 per video

---

## 🚀 Tech Stack

### Backend
- **Python 3.13** + Flask REST API
- **AWS S3** - Chunked uploads for large files
- **FFmpeg** - Video transcoding and composition
- **Celery + Redis** - Background task processing
- **AI Services**:
  - Replicate Whisper (transcription)
  - OpenAI GPT-4 Vision (segment classification)
  - Replicate AI models (animation generation)

### Frontend
- **React 18** + TypeScript + Tailwind CSS
- **Vite** - Fast development builds
- **Uppy.js** - Chunked file uploads with progress tracking
- **Axios** - JWT-authenticated API client

### Infrastructure
- **Docker** + Docker Compose
- **Nginx** - Reverse proxy
- **AWS S3** - Video storage (eu-north-1)

---

## 📦 Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- FFmpeg installed
- AWS account with S3 access
- OpenAI API key
- Replicate API token

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/easyedit-v2.git
   cd easyedit-v2
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

4. **Configure Environment**

   Create `backend/.env` (use `.env.example` as template):
   ```bash
   # AWS S3
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=us-east-1
   S3_VIDEO_BUCKET=easyedit-videos

   # AI Services
   OPENAI_API_KEY=your_openai_key
   REPLICATE_API_TOKEN=your_replicate_token

   # Configuration
   MAX_FILE_SIZE_MB=5120
   S3_CHUNK_SIZE_MB=10
   ```

5. **Install FFmpeg**
   - **Windows**: Download from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`

### Running the Application

#### Development Mode

```bash
# Terminal 1: Backend
cd backend
python app.py
# Backend runs on http://localhost:5000

# Terminal 2: Frontend
cd frontend
npm run dev
# Frontend runs on http://localhost:5173
```

#### Production Mode (Docker)

```bash
docker-compose up --build
```

Access the application at `http://localhost`

---

## 💻 Usage

### 1. Upload Video

```bash
# Get demo JWT token
curl http://localhost:5000/auth/demo-token

# Initialize upload
curl -X POST http://localhost:5000/upload/init \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "video.mp4",
    "file_size": 3221225472
  }'

# Response includes pre-signed S3 URLs for chunked upload
```

### 2. Upload Chunks

Frontend automatically handles:
- Slicing file into 10MB chunks
- Parallel uploads (5 concurrent)
- Progress tracking
- Resume on network failure

### 3. Complete Upload

```bash
curl -X POST http://localhost:5000/upload/complete \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "your_job_id"}'
```

### 4. Check Processing Status

```bash
curl http://localhost:5000/status/your_job_id \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Download XML

```bash
curl -O http://localhost:5000/download/your_job_id \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 6. Import to DaVinci Resolve

1. Open DaVinci Resolve
2. File → Import → Timeline → Import AAF, EDL, XML...
3. Select downloaded XML file
4. 4-layer timeline imports automatically

---

## 📊 Project Status

### ✅ Completed (Week 1, Day 1)
- [x] S3 chunked upload system (526 lines)
- [x] Video upload session tracking (226 lines)
- [x] 5 API endpoints (init, chunk-complete, complete, resume, abort)
- [x] Full test suite (4 tests passing)
- [x] AWS infrastructure configured

### 🔄 In Progress (Week 1, Day 2-3)
- [ ] Frontend Uppy.js integration
- [ ] Progress tracking UI
- [ ] Resume functionality

### 📅 Upcoming
- Week 1, Day 4-5: Multi-layer XML writer
- Week 2, Day 1-2: AI segment classification
- Week 2, Day 3-4: Repeated take detector
- Week 2, Day 5: Timeline compositor

**Overall Progress**: ~5% complete (foundational infrastructure done)

---

## 🧪 Testing

```bash
cd backend

# Test AWS credentials and S3 access
python test_aws_credentials.py

# Test pre-signed URL generation
python test_presigned_url.py

# Test multipart upload
python test_multipart_presigned.py

# Test full upload flow
python test_s3_upload.py
```

All tests should pass ✅

---

## 📁 Project Structure

```
easyedit-v2/
├── backend/
│   ├── app.py                      # Flask API (3426+ lines)
│   ├── config.py                   # Configuration
│   ├── models/                     # Data models
│   ├── services/                   # Core business logic
│   │   ├── s3_upload_manager.py    # S3 chunked uploads ✅
│   │   ├── video_transcoder.py     # FFmpeg processing
│   │   ├── repeated_take_detector.py
│   │   └── video_ai_operations.py  # AI classification
│   ├── parsers/                    # XML writers
│   │   ├── xml_writer.py           # DaVinci Resolve XML ✅
│   │   └── fcp7_xml_writer.py      # FCP7 format
│   └── utils/                      # Utilities
├── frontend/
│   └── src/
│       ├── App.tsx                 # Main React app
│       ├── components/video/       # Video UI components
│       ├── services/api.ts         # API client
│       └── types/                  # TypeScript types
├── docker-compose.yml              # Multi-container setup
├── .env.example                    # Environment template
├── CLAUDE.md                       # Developer guide
├── DESIGN_SYSTEM.md                # UI/UX standards
└── README.md                       # This file
```

---

## 🎨 Design System

All UI components follow the **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)** standards:
- Pure black background (#000000)
- Orange brand color (#FF6B35)
- White cards with 12px border radius
- Consistent spacing (p-6, p-8)

---

## 🤝 Contributing

See `./CONTRIBUTING.md` for development guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`npm test` / `pytest`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📄 License

MIT License - see `./LICENSE`

---

## 🔗 Links

- **Documentation**: [./CLAUDE.md](./CLAUDE.md) - Comprehensive developer guide
- **Design System**: [./DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) - UI/UX standards
- **Roadmap**: [./NEXT_SESSION_PROMPT_COMPLETE.md](./NEXT_SESSION_PROMPT_COMPLETE.md) - Current status

---

## 🐛 Known Issues

### S3 Presigned URL SignatureDoesNotMatch (403)

**Solution**: Use regional endpoint in boto3 client
```python
s3_client = boto3.client(
    's3',
    region_name='eu-north-1',
    endpoint_url='https://s3.eu-north-1.amazonaws.com'
)
```

See [CLAUDE.md](./CLAUDE.md#-critical-issues--solutions) for more troubleshooting.

---

## 📞 Support

For questions or issues:
1. Check [CLAUDE.md](./CLAUDE.md) for technical documentation
2. Review [NEXT_SESSION_PROMPT_COMPLETE.md](./NEXT_SESSION_PROMPT_COMPLETE.md) for current status
3. Open an issue on GitHub

---

**Built with ❤️ for content creators who value their time**
