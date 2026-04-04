#!/bin/bash
# Start Mochi Dashboard - Convenience script

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source .venv/bin/activate

echo "🍡 Starting Mochi Dashboard..."

# Check if already running
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo "✅ Dashboard already running at: http://localhost:8501"
    # Try to open in browser
    if command -v xdg-open > /dev/null 2>&1; then
        xdg-open http://localhost:8501
    elif command -v open > /dev/null 2>&1; then
        open http://localhost:8501
    else
        echo "Open http://localhost:8501 in your browser"
    fi
    exit 0
fi

echo "Starting Streamlit server..."
echo "Dashboard will be available at: http://localhost:8501"
echo ""
echo "To stop: Press Ctrl+C or run: pkill -f 'streamlit run'"
echo ""

# Start streamlit
streamlit run dashboard/app.py --server.headless false