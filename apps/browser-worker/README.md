# Browser Worker

Playwright-based browser automation worker for job application automation.

## Features

- Multi-page form handling
- ATS detection and adapter system
- Field mapping and inspection
- Checkpoint management for human-in-the-loop workflow
- Mock ATS site for testing

## Installation

```bash
cd /home/brian/job_automation/apps/browser-worker
pip install -r requirements.txt
playwright install chromium
```

## Running Mock ATS Server

```bash
cd /home/brian/job_automation/fixtures/ats-sites/mock-ats
python server.py
```

Access at: http://localhost:8080

## Testing Browser Worker

```bash
# Terminal 1: Start mock ATS server
cd /home/brian/job_automation/fixtures/ats-sites/mock-ats
python server.py

# Terminal 2: Run tests
cd /home/brian/job_automation/apps/browser-worker
pytest tests/ -v

# Or run the example
python -m browser_worker.worker
```

## Docker

```bash
cd /home/brian/job_automation/apps/browser-worker
docker build -t browser-worker .
docker run -it browser-worker
```

## Architecture

- `worker.py`: Main BrowserWorker class
- `adapters/`: ATS-specific adapters (MockATS, Generic)
- `services/`: Form inspector, field mapper, checkpoint manager
- `models.py`: Pydantic schemas
- `tests/`: Test suite

## Usage

```python
from browser_worker import BrowserWorker, ApplicationData

worker = BrowserWorker(headless=False, assisted_mode=True)

app_data = ApplicationData(
    application_id="001",
    first_name="John",
    last_name="Doe",
    email="john@example.com",
    work_authorization="yes",
    resume_path="/path/to/resume.pdf"
)

result = await worker.process_application(
    application_id="001",
    application_url="http://localhost:8080",
    application_data=app_data
)

# Resume from checkpoint
result = await worker.resume_from_checkpoint(
    session_id=result["session_id"],
    application_url="http://localhost:8080",
    application_data=app_data
)
```
