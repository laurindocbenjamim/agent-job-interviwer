# AI-Monitored Job Interview System

Real-time AI-powered interview monitoring system that uses computer vision (MediaPipe Face Landmarker) and WebSocket communication to detect candidate misconduct during remote job interviews. It analyzes gaze direction, lighting quality, and audio volume, enforcing a 4-strike rules engine — after 4 violations, the interview is terminated.

## Architecture

```
src/
├── main.py                          # FastAPI entry point with lifespan
├── config/
│   ├── __init__.py
│   └── settings.py                  # Pydantic Settings (reads .env)
├── domains/
│   └── interviews/                  # Bounded context
│       ├── __init__.py
│       ├── router.py                # HTTP + WebSocket routes
│       ├── service.py               # Business logic / rules engine
│       ├── schemas.py               # Pydantic models
│       ├── video_analyzer.py        # MediaPipe Face Landmarker integration
│       ├── audio_analyzer.py        # Audio volume evaluation (unused server-side)
│       └── face_landmarker.task     # MediaPipe model (auto-downloaded)
└── shared/
    ├── __init__.py
    ├── database.py                  # MongoDB (Motor) async client
    ├── redis_client.py              # Redis async client (strike tracking)
    ├── sentry.py                    # Sentry initialization
    └── templates/
        └── interview.html           # Frontend dashboard
```

## Functional Requirements

| ID | Requirement |
|----|------------|
| FR1 | Capture webcam frames via WebSocket every 400ms |
| FR2 | Analyze gaze using MediaPipe Face Landmarker |
| FR3 | Detect "Looking Away" based on iris-to-corner geometric distance (< 0.02 or > 0.06) |
| FR4 | Check video brightness; classify as "Good" (>40) or "Too Dark" (<=40) |
| FR5 | Enforce 4-strike rules: warn on 1-3, terminate on 4 |
| FR6 | Log telemetry to MongoDB asynchronously |
| FR7 | Log strike events to MongoDB |
| FR8 | Track strike counts in Redis with 2-hour TTL |
| FR9 | Serve a dashboard HTML page for each candidate |
| FR10 | On termination, stop camera, close WebSocket, close browser window |
| FR11 | Check audio volume client-side; warn if between 2-15 |
| FR12 | Auto-download MediaPipe model if missing |

## Non-Functional Requirements

| ID | Requirement |
|----|------------|
| NFR1 | Asynchronous database writes (Motor) to avoid blocking video pipeline |
| NFR2 | Frame analysis runs in a thread pool to avoid blocking async loop |
| NFR3 | Strikes expire after 2 hours (Redis TTL) |
| NFR4 | Error tracking via Sentry with full trace sampling |
| NFR5 | Graceful shutdown — close Redis and MongoDB connections |
| NFR6 | JWT secret and secure cookie flag available for security |
| NFR7 | Stress-tested for 10 concurrent users |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Face Tracking | MediaPipe Face Landmarker |
| Computer Vision | OpenCV |
| Database | MongoDB (Motor async driver) |
| Cache/State | Redis (redis.asyncio) |
| WebSockets | FastAPI native WebSocket |
| Error Tracking | Sentry |
| Validation | Pydantic v2 + Pydantic Settings |
| Templating | Jinja2 |
| Testing | Pytest, pytest-asyncio, httpx |

## Endpoints

### `GET /interview/{candidate_id}`

Serves the interactive interview dashboard HTML page.

**Response:** `text/html` — the interview console with webcam feed, strike tracker, and indicators.

### `WebSocket /ws/interview/{candidate_id}`

Bidirectional real-time stream for video frames and compliance directives.

#### Client → Server (every 400ms)

```json
{
  "image": "data:image/jpeg;base64,<base64_encoded_frame>"
}
```

#### Server → Client

```json
{
  "action": "continue | warn | terminate",
  "video_quality": "Good | Too Dark",
  "current_strikes": 0
}
```

**Actions:**
- `continue` — no violation, all clear
- `warn` — gaze deviation detected (strikes 1-3)
- `terminate` — 4th strike reached; frontend stops camera, closes WebSocket, and closes the window

## Data Flow

```
[Browser Webcam] --(400ms)--> Canvas capture --> base64 JPEG
       |
       v  (WebSocket send)
[FastAPI Server] --> MediaPipe Face Landmarker
       |
       +--> Brightness check
       +--> Gaze estimation (iris vs eye corner distance)
       |
       v  (evaluate_candidate_frame)
[Rules Engine]
       |
       +--> Log telemetry to MongoDB
       +--> Get/increment strikes in Redis
       +--> "continue" | "warn" | "terminate"
       |
       v  (WebSocket send_json)
[Browser Dashboard] --> Update UI
```

## Schemas

```python
class GazeMetrics(BaseModel):
    gaze_metric: float    # Geometric distance between left iris and eye corner
    brightness: float     # Average frame brightness
    status: Literal["Focused", "Looking Away"]

class InterviewResponse(BaseModel):
    action: Literal["continue", "warn", "terminate"]
    video_quality: Literal["Good", "Too Dark"]
    current_strikes: int
```

## Dependencies

```
fastapi>=0.100.0
uvicorn>=0.22.0
websockets>=11.0
motor>=3.2.0
pymongo>=4.4.0
redis>=4.6.0
sentry-sdk[fastapi]>=1.28.0
pydantic>=2.0
pydantic-settings>=2.0
mediapipe>=0.10.0
opencv-python-headless>=4.8.0
jinja2>=3.1.2
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
httpx>=0.24.1
```

## Configuration

Set environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | — | MongoDB connection string |
| `MONGODB_DB_NAME` | `nutrisentinel_agent_ai` | Database name |
| `MONGODB_COLLECTION` | `analysis` | Collection name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `SENTRY_DSN` | `None` | Sentry DSN |
| `JWT_SECRET` | — | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `SECURE_COOKIE` | `False` | Secure cookie flag |
| `LLM_PROVIDER` | `groq` | LLM provider (reserved) |
| `LLM_MODEL` | `llama-3.1-8b-instant` | LLM model (reserved) |
| `GROQ_API_KEY` | `None` | Groq API key for STT |
| `GROQ_STT_MODEL` | `None` | Groq STT model |

## How to Run

### Prerequisites

- Python 3.10+
- MongoDB instance (local or Atlas)
- Redis instance (local or remote)

### Setup

```bash
# Clone and enter the project
cd agent-job-interviwer

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure .env (edit with your credentials)
# Ensure MONGODB_URI, REDIS_URL, and JWT_SECRET are set
```

### Run with Uvicorn

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run with Python directly

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Open the dashboard

Navigate to `http://localhost:8000/interview/{candidate_id}` (e.g. `http://localhost:8000/interview/candidate_123`).

Allow camera and microphone access when prompted.

### Run tests

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=src --cov-report=term-missing
```
