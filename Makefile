# Claude Code API - Simple & Working

# Python targets
install:
	pip install -e .
	pip install requests

test:
	python -m pytest tests/ -v

test-real:
	python tests/test_real_api.py

test-patcher:
	@echo "Testing Claude CLI patcher..."
	python tests/test_claude_patcher.py

start:
	@echo "Starting Claude Code API Gateway in development mode..."
	@echo "Press Ctrl+C to stop the server"
	uvicorn claude_code_api.main:app --host 0.0.0.0 --port 8000 --reload --reload-exclude="*.db*" --reload-exclude="*.log"

start-prod:
	uvicorn claude_code_api.main:app --host 0.0.0.0 --port 8000

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	find . -name "*.db" -delete
	find . -name "*.log" -delete
	rm -rf logs/ projects/ sessions/ data/

kill:
	@if [ -z "$(PORT)" ]; then \
		echo "Error: PORT parameter is required. Usage: make kill PORT=8001"; \
	else \
		echo "Looking for processes on port $(PORT)..."; \
		if [ "$$(uname)" = "Darwin" ] || [ "$$(uname)" = "Linux" ]; then \
			PID=$$(lsof -iTCP:$(PORT) -sTCP:LISTEN -t); \
			if [ -n "$$PID" ]; then \
				echo "Found process(es) with PID(s): $$PID"; \
				kill -9 $$PID && echo "Process(es) killed successfully."; \
			else \
				echo "No process found listening on port $(PORT)."; \
			fi; \
		else \
			echo "This command is only supported on Unix-like systems (Linux/macOS)."; \
		fi; \
	fi

# Docker targets
docker-build:
	@echo "Building Docker image..."
	docker-compose build

docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d

docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-restart:
	@echo "Restarting Docker containers..."
	docker-compose restart

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f

docker-ps:
	@echo "Showing Docker container status..."
	docker-compose ps

docker-shell:
	@echo "Opening shell in Docker container..."
	docker-compose exec claude-code-api bash

docker-clean:
	@echo "Cleaning Docker resources..."
	docker-compose down -v
	docker image prune -f

docker-rebuild:
	@echo "Rebuilding and starting Docker containers..."
	docker-compose up -d --build

docker-health:
	@echo "Checking Docker container health..."
	curl -f http://localhost:8091/health || echo "Health check failed"

docker-test:
	@echo "Running tests in Docker container..."
	docker-compose exec claude-code-api python -m pytest tests/ -v

# Environment setup
env-setup:
	@if [ ! -f .env ]; then \
		echo "Creating .env file from .env.example..."; \
		cp .env.example .env; \
		echo "Please edit .env file and add your ANTHROPIC_API_KEY"; \
	else \
		echo ".env file already exists"; \
	fi

help:
	@echo "Claude Code API Commands:"
	@echo ""
	@echo "Python API:"
	@echo "  make install        - Install Python dependencies"
	@echo "  make test           - Run Python unit tests with real Claude integration"
	@echo "  make test-real      - Run REAL end-to-end tests (curls actual API)"
	@echo "  make test-patcher   - Test Claude CLI root permission patcher"
	@echo "  make start          - Start Python API server (development with reload)"
	@echo "  make start-prod     - Start Python API server (production)"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make env-setup      - Create .env file from .env.example"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-up      - Start Docker containers in background"
	@echo "  make docker-down    - Stop Docker containers"
	@echo "  make docker-restart - Restart Docker containers"
	@echo "  make docker-logs    - Show Docker logs (follow)"
	@echo "  make docker-ps      - Show Docker container status"
	@echo "  make docker-shell   - Open shell in Docker container"
	@echo "  make docker-clean   - Clean Docker resources (containers, volumes, images)"
	@echo "  make docker-rebuild - Rebuild and restart Docker containers"
	@echo "  make docker-health  - Check Docker container health"
	@echo "  make docker-test    - Run tests in Docker container"
	@echo ""
	@echo "General:"
	@echo "  make clean          - Clean up Python cache files and data"
	@echo "  make kill PORT=X    - Kill process on specific port"
	@echo ""
	@echo "Quick Start with Docker:"
	@echo "  1. make env-setup      # Create and edit .env file"
	@echo "  2. make docker-build   # Build the image"
	@echo "  3. make docker-up      # Start the service"
	@echo "  4. make docker-logs    # View logs"