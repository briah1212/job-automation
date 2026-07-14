#!/bin/bash
set -e

echo "=========================================="
echo "Job Automation - Portable Setup"
echo "=========================================="

# Detect Docker/Podman
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v podman-compose &> /dev/null; then
    COMPOSE="podman-compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "Error: Need docker compose or podman-compose"
    exit 1
fi

echo "Using: $COMPOSE"

# Create .env if missing
[ ! -f backend/.env ] && cp backend/.env.example backend/.env 2>/dev/null || true
[ ! -f apps/web/.env.local ] && cp apps/web/.env.example apps/web/.env.local 2>/dev/null || true

# Start services
echo "Starting services..."
$COMPOSE up -d postgres redis minio

echo "Waiting for database..."
sleep 15

echo "Running migrations..."
$COMPOSE run --rm api alembic upgrade head

echo "Starting API..."
$COMPOSE up -d api mock-ats

echo ""
echo "✓ Setup complete!"
echo "  API: http://localhost:8001"
echo "  Mock ATS: http://localhost:8080"
echo ""
echo "Test with: ./test_system.sh"
