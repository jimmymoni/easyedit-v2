# EasyEdit-v2 Testing Suite

This directory contains comprehensive tests for the easyedit-v2 backend services.

## Test Structure

### Core Service Tests
- `test_models.py` - Timeline, Track, and Clip model tests
- `test_drt_parser.py` - DRT XML parsing and writing tests
- `test_audio_analyzer.py` - Audio analysis service tests
- `test_edit_rules.py` - Editing rules engine tests
- `test_ai_services.py` - AI services integration tests

### Integration Tests
- `test_integration.py` - End-to-end processing pipeline tests
- `test_api.py` - Flask API endpoint tests
- `test_real_drt_files.py` - Real DaVinci Resolve file compatibility tests

### Format Compatibility Tests
- `test_audio_formats.py` - Various audio format support tests
- `test_api_upload_formats.py` - API upload tests with different formats

### Test Data
- `sample_data/` - Sample DRT files for different DaVinci Resolve versions
- `conftest.py` - Shared test fixtures and utilities

## Running Tests

### Setup Test Environment

1. Install test dependencies:
```bash
pip install -r requirements-test.txt
```

2. Activate virtual environment:
```bash
# Windows
venv\Scripts\activate

# Unix/Mac
source venv/bin/activate
```

### Run All Tests
```bash
cd backend
python -m pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Core service tests
python -m pytest tests/test_models.py tests/test_drt_parser.py tests/test_audio_analyzer.py -v

# Integration tests
python -m pytest tests/test_integration.py tests/test_api.py -v

# Format compatibility tests
python -m pytest tests/test_audio_formats.py tests/test_api_upload_formats.py -v

# Real file compatibility
python -m pytest tests/test_real_drt_files.py -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=. --cov-report=html
```

### Run Performance Tests
```bash
python -m pytest tests/ -k "performance or benchmark" -v
```

## Test Categories

### Unit Tests
Test individual components in isolation:
- Model validation and operations
- Audio analysis algorithms
- Parsing and writing functionality
- Business logic rules

### Integration Tests
Test complete workflows:
- Audio file processing pipelines
- DRT parsing → processing → writing roundtrips
- API request/response cycles
- Cross-service communication

### Compatibility Tests
Test with real-world scenarios:
- Different DaVinci Resolve versions (17, 18, etc.)
- Various audio formats (WAV, FLAC, MP3, etc.)
- Different sample rates and bit depths
- Professional vs consumer content

### Performance Tests
Test system performance:
- Large file processing
- Concurrent request handling
- Memory usage optimization
- Processing time benchmarks

## Sample Data

### DRT Timeline Files
- `interview_timeline_v17.drt` - DaVinci Resolve 17 interview format
- `podcast_timeline_v18.drt` - DaVinci Resolve 18 podcast format
- `music_production_timeline.drt` - Multi-track music production
- `webinar_timeline_simple.drt` - Simple webinar recording

### Test Audio Generation
Tests generate realistic audio data including:
- Speech segments with natural variation
- Silence periods for detection testing
- Multiple speakers for diarization
- Professional quality samples

## Continuous Integration

### GitHub Actions (Recommended)
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r tests/requirements-test.txt
    - name: Run tests
      run: |
        cd backend
        python -m pytest tests/ --cov=. --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Local Pre-commit Testing
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run all checks
pre-commit run --all-files
```

## Environment Variables

Set these for comprehensive testing:

```bash
# AI Services (for integration tests)
export SONIOX_API_KEY="your_soniox_key"
export OPENAI_API_KEY="your_openai_key"

# Test configuration
export EASYEDIT_TEST_MODE=true
export EASYEDIT_LOG_LEVEL=DEBUG
```

## Troubleshooting

### Common Issues

1. **Audio library not found**
   ```bash
   # Install system audio libraries
   # Ubuntu/Debian:
   sudo apt-get install libsndfile1-dev

   # macOS:
   brew install libsndfile
   ```

2. **Memory issues with large test files**
   ```bash
   # Run tests with memory limits
   python -m pytest tests/ -x --maxfail=1
   ```

3. **Missing AI service keys**
   ```bash
   # Skip AI integration tests
   python -m pytest tests/ -k "not ai_services"
   ```

### Test Data Generation

If sample audio files are too large for git:
```bash
# Generate test audio locally
cd backend
python -c "
import numpy as np
import soundfile as sf
duration = 60
sr = 44100
t = np.linspace(0, duration, int(duration * sr))
audio = 0.3 * np.sin(2 * np.pi * 200 * t)
sf.write('tests/sample_data/test_audio.wav', audio, sr)
"
```

## Contributing to Tests

### Adding New Tests
1. Follow naming convention: `test_*.py`
2. Use descriptive test names: `test_feature_with_specific_scenario`
3. Include docstrings explaining test purpose
4. Add to appropriate category (unit/integration/compatibility)

### Test Quality Guidelines
- Each test should be independent
- Use fixtures for common setup
- Mock external dependencies
- Assert meaningful properties
- Include edge cases and error conditions

### Performance Considerations
- Generate test data efficiently
- Use appropriate file sizes for CI
- Skip expensive tests when appropriate
- Profile test execution time