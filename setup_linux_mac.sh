#!/usr/bin/env bash
set -e

echo "Setting up NexaPark..."

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "Python 3 was not found. Install Python 3.10+ and try again." >&2
    exit 1
fi

"$PYTHON" -m venv .venv
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install -r requirements.txt

echo
echo "NexaPark dependencies are installed."
echo "Activate the environment with: source .venv/bin/activate"
echo "Then create an admin account with: flask --app app.py create-admin"
echo "Then start the application with: python app.py"
