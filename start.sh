#!/bin/bash
set -e

echo "========================================"
echo "Job Application Automation Platform"
echo "========================================"

# Start infrastructure
echo "Starting PostgreSQL, Redis, MinIO..."
podman-compose up -d postgres redis minio

echo "Waiting for services..."
sleep 15

# Run migrations
echo "Running database migrations..."
podman-compose run --rm api alembic upgrade head

# Start application
echo "Starting API, Mock ATS..."
podman-compose up -d api mock-ats

echo ""
echo "Services started!"
echo "  API:      http://localhost:8001"
echo "  Mock ATS: http://localhost:8080"
echo ""
echo "Run './test_system.sh' to verify"
