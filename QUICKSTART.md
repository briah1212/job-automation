# Quick Start

## Clone and Run

```bash
git clone git@github.com:briah1212/job-automation.git
cd job-automation
./setup-portable.sh
```

## Requirements
- Docker or Podman
- Git
- 8GB RAM

## Ports Used
- 5432 (PostgreSQL)
- 6379 (Redis)
- 9000, 9011 (MinIO)
- 8001 (API)
- 8080 (Mock ATS)
- 3000 (Frontend - optional)

## Services
- Backend: http://localhost:8001/docs
- Test: `./test_system.sh`

## Next Steps
1. Register user at http://localhost:8001/docs
2. Import job from http://localhost:8080
3. View in dashboard
