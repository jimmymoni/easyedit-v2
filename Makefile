# EasyEdit-v2 Development Commands
# Use: make <command>

.PHONY: help install test test-backend test-frontend lint format clean docker-build docker-up docker-down

# Default target
help:
	@echo "Available commands:"
	@echo "  install        - Install all dependencies"
	@echo "  test           - Run all tests"
	@echo "  test-backend   - Run backend tests only"
	@echo "  test-frontend  - Run frontend tests only"
	@echo "  lint           - Run linting for all code"
	@echo "  format         - Format all code"
	@echo "  clean          - Clean build artifacts and caches"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-up      - Start services with Docker Compose"
	@echo "  docker-down    - Stop Docker services"
	@echo "  docker-logs    - Show Docker logs"
	@echo "  setup-dev      - Set up development environment"
	@echo "  setup-hooks    - Install pre-commit hooks"

# Installation
install: install-backend install-frontend

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && python -m pip install --upgrade pip
	cd backend && pip install -r requirements.txt
	cd backend && pip install -r tests/requirements-test.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Testing
test: test-backend test-frontend

test-backend:
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v --cov=. --cov-report=term-missing

test-backend-fast:
	@echo "Running backend tests (fast mode)..."
	cd backend && python -m pytest tests/ -v -x --ff

test-backend-integration:
	@echo "Running backend integration tests..."
	cd backend && python -m pytest tests/test_integration.py tests/test_api.py -v

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --run

test-frontend-watch:
	@echo "Running frontend tests in watch mode..."
	cd frontend && npm test

test-frontend-coverage:
	@echo "Running frontend tests with coverage..."
	cd frontend && npm test -- --coverage

test-performance:
	@echo "Running performance tests..."
	cd backend && python -m pytest tests/ -k "performance or benchmark" -v

# Linting and Formatting
lint: lint-backend lint-frontend

lint-backend:
	@echo "Linting backend code..."
	cd backend && flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	cd backend && flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

lint-frontend:
	@echo "Linting frontend code..."
	cd frontend && npm run lint

format: format-backend format-frontend

format-backend:
	@echo "Formatting backend code..."
	cd backend && black .
	cd backend && isort .

format-frontend:
	@echo "Formatting frontend code..."
	cd frontend && npx prettier --write "src/**/*.{js,jsx,ts,tsx,json,css,md}"

# Build and Development
build-backend:
	@echo "Building backend..."
	cd backend && python -m pip install -e .

build-frontend:
	@echo "Building frontend..."
	cd frontend && npm run build

build: build-backend build-frontend

dev-backend:
	@echo "Starting backend development server..."
	cd backend && python app.py

dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

# Docker operations
docker-build:
	@echo "Building Docker images..."
	docker-compose build --no-cache

docker-up:
	@echo "Starting Docker services..."
	docker-compose up -d

docker-down:
	@echo "Stopping Docker services..."
	docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f

docker-test:
	@echo "Running tests in Docker..."
	docker-compose up -d
	sleep 10
	docker-compose exec backend python -m pytest tests/test_api.py -v
	docker-compose down

# Environment setup
setup-dev: install setup-hooks
	@echo "Setting up development environment..."
	@echo "Creating backend virtual environment..."
	cd backend && python -m venv venv || true
	@echo "Development environment ready!"
	@echo "Activate backend venv with: source backend/venv/bin/activate (Unix) or backend\\venv\\Scripts\\activate (Windows)"

setup-hooks:
	@echo "Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install
	@echo "Pre-commit hooks installed!"

# Cleanup
clean:
	@echo "Cleaning build artifacts and caches..."
	# Python
	find . -type d -name "__pycache__" -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete || true
	find . -type f -name "*.pyo" -delete || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + || true
	rm -rf backend/htmlcov/ || true
	rm -rf backend/coverage.xml || true
	rm -rf backend/.coverage || true
	rm -rf backend/.pytest_cache/ || true
	# Node.js
	rm -rf frontend/node_modules/ || true
	rm -rf frontend/dist/ || true
	rm -rf frontend/build/ || true
	rm -rf frontend/coverage/ || true
	# Docker
	docker system prune -f || true
	@echo "Cleanup completed!"

clean-all: clean
	@echo "Deep cleaning (including dependencies)..."
	rm -rf backend/venv/ || true
	rm -rf frontend/node_modules/ || true
	docker-compose down -v || true
	docker system prune -af || true

# Database operations (if needed later)
db-migrate:
	@echo "Running database migrations..."
	cd backend && python -m flask db upgrade

db-reset:
	@echo "Resetting database..."
	cd backend && python -m flask db downgrade base
	cd backend && python -m flask db upgrade

# Security and quality checks
security-check:
	@echo "Running security checks..."
	cd backend && bandit -r . -f json -o bandit-report.json || true
	cd frontend && npm audit --audit-level moderate || true

quality-check:
	@echo "Running quality checks..."
	cd backend && python -m pip check
	cd frontend && npm doctor || true

# CI simulation
ci-test: lint test security-check
	@echo "CI tests completed successfully!"

ci-build: clean install build test
	@echo "CI build completed successfully!"

# Deployment helpers
deploy-staging:
	@echo "Deploying to staging..."
	# Add staging deployment commands here

deploy-prod:
	@echo "Deploying to production..."
	# Add production deployment commands here

# Monitoring and logs
logs-backend:
	@echo "Showing backend logs..."
	tail -f backend/logs/*.log || echo "No log files found"

logs-frontend:
	@echo "Showing frontend logs..."
	# Frontend logs would be browser-based

# Performance profiling
profile-backend:
	@echo "Profiling backend performance..."
	cd backend && python -m cProfile -s cumtime app.py

benchmark:
	@echo "Running benchmarks..."
	cd backend && python -m pytest tests/ --benchmark-only

# Documentation
docs-build:
	@echo "Building documentation..."
	# Add documentation build commands if needed

docs-serve:
	@echo "Serving documentation..."
	# Add documentation serve commands if needed

# Version management
version:
	@echo "Current version information:"
	@echo "Backend:"
	cd backend && python --version
	@echo "Frontend:"
	cd frontend && node --version && npm --version
	@echo "Docker:"
	docker --version
	docker-compose --version