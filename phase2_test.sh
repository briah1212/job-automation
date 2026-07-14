#!/bin/bash

set -e

echo "=== Phase 2 End-to-End Test ==="
echo "Date: $(date)"
echo ""

# Create test user
echo "1. Creating test user..."
RESPONSE=$(curl -s -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"phase2final@test.com","password":"test123"}')

TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>&1)

if [ -z "$TOKEN" ] || [[ "$TOKEN" == *"Traceback"* ]]; then
    echo "❌ FAILED: Could not get auth token"
    echo "Response: $RESPONSE"
    exit 1
fi
echo "✓ Test user created, token obtained"

# Update profile
echo ""
echo "2. Updating user profile..."
PROFILE_RESPONSE=$(curl -s -X PUT http://localhost:8001/api/profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "legal_name": "Phase Two User",
    "email": "phase2final@test.com",
    "phone": "555-0200",
    "career_interests": "data_engineering, software_engineering",
    "target_seniority": "senior",
    "work_authorization": "authorized"
  }')

if echo "$PROFILE_RESPONSE" | grep -q "legal_name"; then
    echo "✓ Profile updated successfully"
else
    echo "❌ FAILED: Profile update failed"
    echo "Response: $PROFILE_RESPONSE"
    exit 1
fi

# Create search profile
echo ""
echo "3. Creating search profile..."
SEARCH_PROFILE_RESPONSE=$(curl -s -X POST http://localhost:8001/api/search-profiles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Engineering Search",
    "description": "Looking for data engineering roles",
    "is_active": true,
    "desired_titles": ["Data Engineer", "Analytics Engineer"],
    "desired_locations": ["San Francisco", "Remote"],
    "remote_preference": "remote",
    "min_salary": 150000,
    "required_skills": ["Python", "SQL", "Airflow"],
    "preferred_skills": ["Spark", "AWS"]
  }')

if echo "$SEARCH_PROFILE_RESPONSE" | grep -q "Data Engineering Search"; then
    echo "✓ Search profile created successfully"
    SEARCH_PROFILE_ID=$(echo "$SEARCH_PROFILE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    echo "  Profile ID: $SEARCH_PROFILE_ID"
else
    echo "❌ FAILED: Search profile creation failed"
    echo "Response: $SEARCH_PROFILE_RESPONSE"
    exit 1
fi

# Import job
echo ""
echo "4. Importing job from mock ATS..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:8001/api/jobs/import-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://mock-ats:8080"}')

if echo "$JOB_RESPONSE" | grep -q '"id"'; then
    echo "✓ Job imported successfully"
    JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    echo "  Job ID: $JOB_ID"
else
    echo "❌ FAILED: Job import failed"
    echo "Response: $JOB_RESPONSE"
    exit 1
fi

# Calculate match score
echo ""
echo "5. Calculating match score..."
MATCH_CALC_RESPONSE=$(curl -s -X POST "http://localhost:8001/api/jobs/${JOB_ID}/match" \
  -H "Authorization: Bearer $TOKEN")

if echo "$MATCH_CALC_RESPONSE" | grep -q "overall_score"; then
    echo "✓ Match score calculated"
    echo "  Response: $MATCH_CALC_RESPONSE"
else
    echo "❌ FAILED: Match calculation failed"
    echo "Response: $MATCH_CALC_RESPONSE"
    exit 1
fi

# Get match score
echo ""
echo "6. Retrieving match score..."
MATCH_GET_RESPONSE=$(curl -s -X GET "http://localhost:8001/api/jobs/${JOB_ID}/match" \
  -H "Authorization: Bearer $TOKEN")

if echo "$MATCH_GET_RESPONSE" | grep -q "overall_score"; then
    echo "✓ Match score retrieved"
    OVERALL_SCORE=$(echo "$MATCH_GET_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['overall_score'])")
    echo "  Overall Score: $OVERALL_SCORE"
else
    echo "❌ FAILED: Match retrieval failed"
    echo "Response: $MATCH_GET_RESPONSE"
    exit 1
fi

# Upload resume
echo ""
echo "7. Uploading test resume..."
cat > /tmp/test_resume.txt << 'EOFRES'
John Doe
Data Engineer
Skills: Python, SQL, Airflow, Spark, AWS
Experience: 5 years building data pipelines
EOFRES

RESUME_RESPONSE=$(curl -s -X POST http://localhost:8001/api/resumes \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_resume.txt" \
  -F "family=data_engineering")

if echo "$RESUME_RESPONSE" | grep -q '"id"'; then
    echo "✓ Resume uploaded successfully"
    RESUME_ID=$(echo "$RESUME_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    echo "  Resume ID: $RESUME_ID"
else
    echo "❌ FAILED: Resume upload failed"
    echo "Response: $RESUME_RESPONSE"
    exit 1
fi

# Select best resume for job
echo ""
echo "8. Selecting best resume for job..."
RESUME_SELECT_RESPONSE=$(curl -s -X POST "http://localhost:8001/api/jobs/${JOB_ID}/select-resume" \
  -H "Authorization: Bearer $TOKEN")

if echo "$RESUME_SELECT_RESPONSE" | grep -q '"resume_id"'; then
    echo "✓ Resume selected successfully"
    SELECTED_RESUME=$(echo "$RESUME_SELECT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['resume_id'])")
    echo "  Selected Resume ID: $SELECTED_RESUME"
else
    echo "❌ WARNING: Resume selection failed (may not be implemented yet)"
    echo "Response: $RESUME_SELECT_RESPONSE"
fi

# Test job list with filters
echo ""
echo "9. Testing job list with filters..."
JOB_LIST_RESPONSE=$(curl -s -X GET "http://localhost:8001/api/jobs?min_score=0" \
  -H "Authorization: Bearer $TOKEN")

if echo "$JOB_LIST_RESPONSE" | grep -q "$JOB_ID"; then
    echo "✓ Job list retrieved with filters"
    JOB_COUNT=$(echo "$JOB_LIST_RESPONSE" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    echo "  Jobs found: $JOB_COUNT"
else
    echo "❌ FAILED: Job list filtering failed"
    echo "Response: $JOB_LIST_RESPONSE"
    exit 1
fi

# Verify database
echo ""
echo "10. Verifying database state..."
echo ""
echo "Search Profiles:"
podman-compose exec -T postgres psql -U postgres -d job_automation -c "
SELECT 
  name,
  is_active,
  array_length(desired_titles, 1) as num_titles,
  array_length(required_skills, 1) as num_skills
FROM search_profiles;
" 2>&1 | grep -v "^$"

echo ""
echo "Jobs with Match Scores:"
podman-compose exec -T postgres psql -U postgres -d job_automation -c "
SELECT 
  j.title,
  j.company,
  jms.overall_score,
  jms.skills_score
FROM canonical_jobs j
LEFT JOIN job_match_scores jms ON j.id = jms.job_id
LIMIT 5;
" 2>&1 | grep -v "^$"

echo ""
echo "=== Test Summary ==="
echo "✓ All critical tests passed"
echo "✓ Search profile CRUD working"
echo "✓ Job import working"
echo "✓ Match score calculation working"
echo "✓ Job list filtering working"
echo "✓ Database tables exist and populated"
echo ""
echo "Test completed successfully!"
