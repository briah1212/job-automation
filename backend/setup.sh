#!/bin/bash
set -e

echo "Setting up Job Automation Backend..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please update with your configuration."
fi

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your database URL and secret key"
echo "2. Run migrations: alembic upgrade head"
echo "3. Start the server: uvicorn main:app --reload"
