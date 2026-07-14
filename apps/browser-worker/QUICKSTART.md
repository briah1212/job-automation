# Browser Worker - Quick Start Guide

## Setup

```bash
# SSH to server
ssh bhead
sudo su
cd /home/brian/job_automation/apps/browser-worker

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

## Running Mock ATS Server

```bash
# Terminal 1
cd /home/brian/job_automation/fixtures/ats-sites/mock-ats
python server.py
# Server runs at http://localhost:8080
```

## Testing Browser Worker

### Option 1: Run Demo Script
```bash
# Terminal 2
cd /home/brian/job_automation/apps/browser-worker
./run_demo.sh
```

### Option 2: Run Tests
```bash
cd /home/brian/job_automation/apps/browser-worker
pytest tests/ -v
```

### Option 3: Run Manually
```bash
cd /home/brian/job_automation/apps/browser-worker

# Create test resume
python create_test_resume.py

# Run worker (edit worker.py main() first if needed)
python -m browser_worker.worker
```

## Files Created

### Browser Worker (`apps/browser-worker/`)
- `browser_worker/worker.py` - Main worker with process_application() and resume_from_checkpoint()
- `browser_worker/models.py` - Pydantic schemas
- `browser_worker/adapters/base.py` - ATSAdapter base class
- `browser_worker/adapters/mock_ats_adapter.py` - Mock ATS implementation
- `browser_worker/adapters/generic_adapter.py` - Fallback adapter
- `browser_worker/services/form_inspector.py` - Extract form fields
- `browser_worker/services/field_mapper.py` - Map fields to canonical names
- `browser_worker/services/checkpoint_manager.py` - Save/load checkpoints
- `tests/test_adapters.py` - Test suite
- `Dockerfile` - Container image
- `requirements.txt` - Python dependencies

### Mock ATS Site (`fixtures/ats-sites/mock-ats/`)
- `index.html` - Multi-page application form (3 pages)
- `app.js` - Form navigation and validation
- `styles.css` - Styling
- `confirmation.html` - Success page
- `server.py` - HTTP server

## Key Features

1. **Multi-page forms**: Handles 3-page mock ATS form with navigation
2. **Field mapping**: Maps form fields to canonical names (first_name, email, etc.)
3. **File uploads**: Handles resume PDF upload
4. **Checkpoints**: Saves state at each step with screenshots
5. **Assisted mode**: Pauses before submit for human approval
6. **Adapter pattern**: Easy to add new ATS adapters

## Example Usage

```python
from browser_worker import BrowserWorker, ApplicationData

# Initialize worker
worker = BrowserWorker(
    headless=False,          # Show browser
    assisted_mode=True       # Pause before submit
)

# Prepare application data
app_data = ApplicationData(
    application_id="test_001",
    first_name="John",
    last_name="Doe",
    email="john.doe@example.com",
    phone="555-0123",
    linkedin="https://linkedin.com/in/johndoe",
    work_authorization="yes",
    resume_path="/tmp/test_resume.pdf",
    interest="I am excited about this opportunity."
)

# Process application (fills form, stops at review page)
result = await worker.process_application(
    application_id="test_001",
    application_url="http://localhost:8080",
    application_data=app_data
)

# result = {
#     "success": True,
#     "status": "awaiting_approval",
#     "session_id": "app_test_001"
# }

# Resume and submit after human review
result = await worker.resume_from_checkpoint(
    session_id="app_test_001",
    application_url="http://localhost:8080",
    application_data=app_data
)

# result = {
#     "success": True,
#     "confirmed": True,
#     "application_id": "MOCK-12345"
# }
```

## Checkpoints

Checkpoints are saved to `/tmp/checkpoints/{session_id}/`:
- `latest.json` - Latest checkpoint metadata
- `{step}_{timestamp}.json` - All checkpoints
- `{step}_{timestamp}.png` - Screenshots

## Next Steps

1. Add more ATS adapters (Workday, Greenhouse, Lever)
2. Integrate with backend API
3. Add support for more field types
4. Implement CAPTCHA detection (pause for human)
5. Add retry logic for network errors
