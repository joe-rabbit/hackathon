#!/bin/bash
# Start Mochi Dashboard in background

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found"
    exit 1
fi

source .venv/bin/activate

# Check if already running
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo "✅ Dashboard already running at: http://localhost:8501"
    exit 0
fi

echo "🍡 Starting Mochi Dashboard in background..."

# Start streamlit in background
nohup streamlit run dashboard/app.py --server.headless true --server.port 8501 > dashboard.log 2>&1 &
STREAMLIT_PID=$!

echo "Started with PID: $STREAMLIT_PID"
echo "Log file: dashboard.log"

# Wait for it to start up
echo "Waiting for dashboard to start..."
for i in {1..10}; do
    sleep 1
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        echo "✅ Dashboard ready at: http://localhost:8501"
        # Try to open in browser
        if command -v xdg-open > /dev/null 2>&1; then
            xdg-open http://localhost:8501 2>/dev/null &
        elif command -v open > /dev/null 2>&1; then
            open http://localhost:8501 2>/dev/null &
        fi
        exit 0
    fi
    echo "Still starting... ($i/10)"
done

echo "❌ Dashboard failed to start within 10 seconds"
echo "Check dashboard.log for errors"
exit 1