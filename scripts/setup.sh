#!/usr/bin/env bash
# MyClaw Setup Script (Linux / macOS)
# Usage: bash scripts/setup.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== MyClaw Setup ==="

# --- Backend ---
echo ""
echo "[1/4] Creating Python virtual environment..."
if [ -d "$ROOT/backend/.venv" ]; then
    echo "  Virtual environment already exists, skipping."
else
    python3 -m venv "$ROOT/backend/.venv"
    echo "  Created at backend/.venv"
fi

echo ""
echo "[2/4] Installing Python dependencies..."
"$ROOT/backend/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt" --quiet
echo "  Core dependencies installed."
"$ROOT/backend/.venv/bin/pip" install -r "$ROOT/backend/requirements-skills.txt" --quiet
echo "  Skill dependencies installed."

# --- Frontend ---
echo ""
echo "[3/4] Installing frontend dependencies..."
cd "$ROOT/frontend"
npm install --silent
cd "$ROOT"
echo "  Frontend dependencies installed."

# --- Verify ---
echo ""
echo "[4/4] Verifying installation..."
"$ROOT/backend/.venv/bin/python" -c "import langchain, duckdb, pandas; print(f'  langchain={langchain.__version__}, duckdb={duckdb.__version__}, pandas={pandas.__version__}')"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the services:"
echo ""
echo "  Backend:"
echo "    cd backend"
echo "    .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "  Frontend:"
echo "    cd frontend"
echo "    npm run dev"
echo ""
echo "Then open http://localhost:5173 in your browser."
