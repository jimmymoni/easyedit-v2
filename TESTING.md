# Testing Guide for EasyEdit-v2

This document provides comprehensive information about testing in the EasyEdit-v2 project.

## Overview

The project uses a comprehensive testing strategy covering:
- **Backend**: Python with pytest, covering unit tests, integration tests, and API tests
- **Frontend**: React with Vitest and Testing Library for component and integration tests
- **End-to-End**: Docker-based testing for complete workflow validation
- **Performance**: Benchmark testing for processing pipelines
- **Security**: Automated security scanning and vulnerability checks

## Quick Start

### Running All Tests
```bash
# Using Make (recommended)
make test

# Or manually
make test-backend
make test-frontend
```

### Running Specific Test Categories
```bash
# Backend only
make test-backend

# Frontend only
make test-frontend

# Integration tests only
make test-backend-integration

# Performance tests
make test-performance
```

## Backend Testing

### Test Structure
```
backend/tests/
├── conftest.py                 # Shared fixtures
├── test_models.py             # Data model tests
├── test_drt_parser.py         # DRT file parsing tests
├── test_audio_analyzer.py     # Audio processing tests
├── test_edit_rules.py         # Editing logic tests
├── test_ai_services.py        # AI integration tests
├── test_integration.py        # End-to-end workflow tests
├── test_api.py               # Flask API endpoint tests
├── test_real_drt_files.py    # Real file compatibility tests
├── test_audio_formats.py     # Audio format support tests
├── test_api_upload_formats.py # Upload format tests
├── sample_data/              # Test data files
└── requirements-test.txt     # Test dependencies
```

### Running Backend Tests
```bash
cd backend

# All tests with coverage
python -m pytest tests/ -v --cov=. --cov-report=html

# Specific test file
python -m pytest tests/test_models.py -v

# Specific test function
python -m pytest tests/test_models.py::TestTimeline::test_add_track -v

# Tests with specific markers
python -m pytest -m "unit" -v          # Unit tests only
python -m pytest -m "integration" -v   # Integration tests only
python -m pytest -m "not slow" -v      # Skip slow tests
```

### Test Categories and Markers
- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests across components
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.requires_ai` - Tests requiring AI API keys
- `@pytest.mark.performance` - Performance and benchmark tests

### Example Backend Test
```python
import pytest
from models.timeline import Timeline

class TestTimeline:
    def test_create_timeline(self):
        timeline = Timeline("Test", duration=60.0)
        assert timeline.name == "Test"
        assert timeline.duration == 60.0

    def test_add_track(self, sample_timeline):
        # Uses fixture from conftest.py
        assert len(sample_timeline.tracks) > 0
```

## Frontend Testing

### Test Structure
```
frontend/src/tests/
├── setup.ts                    # Test configuration
├── components/                 # Component tests
│   ├── FileDropzone.test.tsx
│   ├── ProcessingOptions.test.tsx
│   ├── ProcessingStatus.test.tsx
│   └── JobHistory.test.tsx
├── services/
│   └── api.test.ts            # API service tests
├── App.test.tsx               # Main app integration tests
└── README.md                  # Frontend testing guide
```

### Running Frontend Tests
```bash
cd frontend

# All tests
npm test

# Watch mode (development)
npm run test:watch

# Coverage report
npm run test:coverage

# Specific test file
npm test -- FileDropzone.test.tsx

# Tests matching pattern
npm test -- --testNamePattern="upload"
```

### Example Frontend Test
```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FileDropzone from '../FileDropzone'

test('handles file drop correctly', async () => {
  const mockOnFilesSelected = vi.fn()
  const user = userEvent.setup()

  render(<FileDropzone onFilesSelected={mockOnFilesSelected} />)

  const file = new File(['audio'], 'test.wav', { type: 'audio/wav' })
  const dropzone = screen.getByTestId('dropzone')

  await user.upload(dropzone, file)

  expect(mockOnFilesSelected).toHaveBeenCalledWith(file, null)
})
```

## Integration Testing

### Docker-based Integration Tests
```bash
# Start services
docker-compose up -d

# Run integration tests
make docker-test

# Manual testing against services
curl http://localhost:5000/health
curl http://localhost:3000
```

### End-to-End Workflow Tests
The integration tests in `backend/tests/test_integration.py` cover complete workflows:
- File upload → Audio analysis → Timeline processing → DRT generation
- Multiple processing options and parameter combinations
- Error handling and edge cases
- Performance with larger files

## Test Data and Fixtures

### Backend Fixtures (conftest.py)
- `sample_timeline` - Pre-configured timeline with tracks and clips
- `sample_audio_data` - Generated audio with speech and silence patterns
- `sample_transcription_data` - Mock transcription with speaker segments
- `temp_dir` - Temporary directory for test files
- `create_audio_file` - Factory for creating test audio files

### Sample DRT Files
Real DaVinci Resolve timeline files for compatibility testing:
- `interview_timeline_v17.drt` - DaVinci Resolve 17 format
- `podcast_timeline_v18.drt` - DaVinci Resolve 18 format
- `music_production_timeline.drt` - Multi-track music project
- `webinar_timeline_simple.drt` - Simple single-track recording

### Audio Format Testing
Tests cover various audio formats and configurations:
- **Formats**: WAV, FLAC, MP3 (simulated), AIFF, OGG
- **Sample Rates**: 8kHz, 16kHz, 22kHz, 44.1kHz, 48kHz, 96kHz
- **Bit Depths**: 16-bit, 24-bit, 32-bit, 32-bit float
- **Channels**: Mono and stereo

## Performance Testing

### Backend Performance Tests
```bash
# Run performance tests
make test-performance

# With benchmarking
python -m pytest tests/ --benchmark-only

# Profile specific functions
python -m pytest tests/test_integration.py --profile
```

### Performance Metrics Tracked
- Audio processing time vs file duration
- Memory usage during processing
- Timeline parsing/writing speed
- API response times
- Concurrent request handling

### Example Performance Test
```python
@pytest.mark.performance
def test_large_file_processing_time(self, large_audio_data):
    """Test processing time scales reasonably with file size"""
    start_time = time.time()

    analyzer = AudioAnalyzer()
    analyzer.load_audio(large_audio_file)
    result = analyzer.detect_silence()

    processing_time = time.time() - start_time

    # Should process at faster than real-time
    assert processing_time < audio_duration * 0.1
```

## Continuous Integration

### GitHub Actions Workflow
The `.github/workflows/test.yml` workflow runs:
1. **Backend Tests**: Multiple Python versions (3.9, 3.10, 3.11)
2. **Frontend Tests**: Multiple Node.js versions (18.x, 20.x)
3. **Docker Integration**: Service health checks and integration tests
4. **Security Scanning**: Dependency vulnerabilities and code analysis
5. **Performance Testing**: Benchmark regression detection

### Coverage Requirements
- **Backend**: Minimum 80% coverage
- **Frontend**: Minimum 75% coverage
- **Overall**: Target 85%+ coverage

Coverage reports are uploaded to Codecov and displayed in pull requests.

## Mocking and Test Doubles

### Backend Mocking
```python
# Mock external APIs
@patch('services.soniox_client.SonioxClient.transcribe_audio')
def test_with_mock_transcription(self, mock_transcribe):
    mock_transcribe.return_value = {"transcript": "test"}
    # Test implementation
```

### Frontend Mocking
```typescript
// Mock API calls
vi.mock('../services/api', () => ({
  uploadFiles: vi.fn(),
  getJobStatus: vi.fn()
}))

// Mock file objects
const mockFile = new File(['content'], 'test.wav', { type: 'audio/wav' })
```

## Debugging Tests

### Backend Debugging
```bash
# Run with debugging output
python -m pytest tests/test_models.py -v -s --pdb

# Show print statements
python -m pytest tests/ -v -s

# Run single test with full output
python -m pytest tests/test_models.py::test_function -v -s --tb=long
```

### Frontend Debugging
```bash
# Debug with UI
npm run test:ui

# Verbose output
npm test -- --reporter=verbose

# Debug specific test
npm test -- --testNamePattern="specific test" --verbose
```

## Best Practices

### General Testing Principles
1. **Arrange, Act, Assert**: Clear test structure
2. **Independent Tests**: Tests don't depend on each other
3. **Descriptive Names**: Test names explain what they verify
4. **Realistic Data**: Test with data similar to production
5. **Error Cases**: Test both success and failure scenarios

### Backend Best Practices
```python
# Good: Descriptive test name
def test_silence_detection_with_quiet_audio_returns_appropriate_segments(self):

# Good: Use fixtures for common setup
def test_timeline_processing(self, sample_timeline, sample_audio_data):

# Good: Test edge cases
def test_empty_audio_file_handling(self):
```

### Frontend Best Practices
```typescript
// Good: Test user interactions
test('shows error when upload fails', async () => {
  const user = userEvent.setup()
  // Test implementation
})

// Good: Test accessibility
test('provides proper ARIA labels', () => {
  render(<Component />)
  expect(screen.getByRole('button', { name: /upload/i })).toBeInTheDocument()
})

// Good: Test component states
test('disables button during upload', () => {
  render(<Component isUploading={true} />)
  expect(screen.getByRole('button')).toBeDisabled()
})
```

## Troubleshooting

### Common Issues

#### Backend Tests
```bash
# Import errors
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Missing audio libraries
sudo apt-get install libsndfile1-dev  # Ubuntu
brew install libsndfile              # macOS

# Memory issues with large tests
python -m pytest tests/ -x --maxfail=1
```

#### Frontend Tests
```bash
# Module resolution issues
rm -rf node_modules package-lock.json
npm install

# Timeout issues
npm test -- --testTimeout=10000

# Mock issues
vi.clearAllMocks()  # In beforeEach
```

#### Docker Tests
```bash
# Services not starting
docker-compose logs
docker-compose down -v  # Reset volumes

# Port conflicts
docker-compose down
lsof -i :5000  # Check port usage
```

### Getting Help
1. Check test output for specific error messages
2. Review similar tests in the codebase
3. Consult testing framework documentation:
   - [pytest](https://docs.pytest.org/)
   - [Vitest](https://vitest.dev/)
   - [Testing Library](https://testing-library.com/)
4. Use debugging tools and breakpoints
5. Check CI logs for environment-specific issues

## Environment Variables

### Test Configuration
```bash
# Backend
export EASYEDIT_TEST_MODE=true
export EASYEDIT_LOG_LEVEL=DEBUG
export PYTHONPATH=backend

# Disable external APIs during testing
export DISABLE_EXTERNAL_APIS=true

# AI API keys for integration tests (optional)
export SONIOX_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here

# Frontend
export VITE_API_BASE_URL=http://localhost:5000
export VITE_TEST_MODE=true
```

## Contributing

### Adding New Tests
1. Follow existing naming conventions
2. Add appropriate markers (`@pytest.mark.unit`, etc.)
3. Include docstrings explaining test purpose
4. Add to appropriate test category
5. Update test documentation if needed

### Test Coverage Goals
- New code should include comprehensive tests
- Aim for >90% line coverage on new features
- Include both positive and negative test cases
- Test edge cases and error conditions
- Consider performance implications

### Pre-commit Testing
The pre-commit hooks will run:
- Linting (flake8, eslint)
- Formatting (black, prettier)
- Security checks (bandit, audit)
- Fast test subset

Use `git commit --no-verify` to skip hooks only when necessary.