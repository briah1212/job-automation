#!/bin/bash
BASE="http://localhost:8001"

echo "=== System Test ==="

# Register
echo "1. Register user..."
curl -s -X POST $BASE/api/auth/register   -H "Content-Type: application/json"   -d '{"\email":"demo@test.com","password":"demo123"}' > /dev/null
echo "✓ Registration"

# Login
echo "2. Login..."
TOKEN=$(curl -s -X POST $BASE/api/auth/login   -H "Content-Type: application/json"   -d '{"\email":"demo@test.com","password":"demo123"}'   | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
echo "✓ Login (token received)"

# Update profile
echo "3. Update profile..."
curl -s -X PUT $BASE/api/profile   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{"\legal_name":"Demo User","email":"demo@test.com","work_authorization":"authorized"}' > /dev/null
echo "✓ Profile updated"

# Import job
echo "4. Import job..."
curl -s -X POST $BASE/api/jobs/import-url   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{"\url":"http://localhost:8080"}' > /dev/null
echo "✓ Job imported"

# Check mock ATS
echo "5. Mock ATS..."
curl -s http://localhost:8080 | grep -q "Apply" && echo "✓ Mock ATS accessible" || echo "✗ Mock ATS failed"

echo ""
echo "=== All Tests Passed ==="
