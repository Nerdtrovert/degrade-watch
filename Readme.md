# DegradeWatch

Merchant-side Payment Incident Response System for detecting, investigating, and safely recovering from localized payment degradation.

## Current Status

Day 1 — Checkpoint 1: Repository and environment foundation.

## Architecture

For now, only describe the intended high-level flow:

Payment Events
→ Detection
→ Investigation
→ Forensic Incident Report
→ Policy
→ Bounded Recovery
→ Measurement
→ Audit

Implementation will happen incrementally through checkpoints.

## Tech Stack

**Backend:**
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL

**Data Processing:**
- NumPy
- Pandas
- SciPy

**Frontend:**
- React
- TypeScript
- Tailwind CSS
- Recharts

**Testing:**
- pytest

**Infrastructure:**
- Docker
- Docker Compose

## Development

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)

### Backend Setup
1. Create Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Start services with Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Apply database migrations (when implemented):
   ```bash
   # To be implemented in later checkpoints
   ```

### Testing
Run the test suite:
```bash
pytest
```

### API Documentation
When the backend is running, API docs will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc


  Run the following commands from the root directory /Users/prajwalnavadagp/Engineering/Projects/degrade-watch:

    # 1. Activate the virtual environment
    source venv/bin/activate

    # 2. Run the test suite to verify tests and backend package importing
    pytest

    # 3. Check the status of your running PostgreSQL container
    docker compose ps