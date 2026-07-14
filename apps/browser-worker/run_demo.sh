#!/bin/bash
# Quick demo script

set -e

echo "=== Browser Worker Demo ==="
echo ""

# Create test resume
echo "1. Creating test resume..."
python create_test_resume.py

# Check if mock ATS is running
echo ""
echo "2. Checking if Mock ATS server is running..."
if ! curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "   Mock ATS is not running!"
    echo "   Please start it in another terminal:"
    echo "   cd /home/brian/job_automation/fixtures/ats-sites/mock-ats && python server.py"
    echo ""
    read -p "Press Enter once the server is running..."
fi

echo ""
echo "3. Running browser worker..."
python -m browser_worker.worker

echo ""
echo "Demo complete!"
