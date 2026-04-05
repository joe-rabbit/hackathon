import cv2
import numpy as np
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import threading
import time
import os

app = FastAPI(title="Object Detection Node")

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
# Using Haar Cascades as a robust, built-in fallback for detection
HAAR_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'

# -----------------------------------------------------------------------------
# Camera & Detection Logic
# -----------------------------------------------------------------------------
class CameraManager:
    def __init__(self):
        # Use index 0 for the first USB camera
        # cv2.CAP_V4L2 forces the Linux video driver which is more stable for Logitech/Pi 5
        self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        
        if not self.cap.isOpened():
            print("Warning: Could not open camera with CAP_V4L2. Trying default backend...")
            self.cap = cv2.VideoCapture(0)
            
        if not self.cap.isOpened():
            print("Error: Could not open any camera backend.")
        else:
            print("Camera is live and stabilized!")

        self.lock = threading.Lock()
        self.output_frame = None
        self.is_running = True
        self.detection_count = 0
        
        # Load Detection Model (Built-in Haar Cascade for Faces)
        self.face_cascade = cv2.CascadeClassifier(HAAR_PATH)
        if self.face_cascade.empty():
            print("Error: Could not load Haar Cascade.")
            self.face_cascade = None

        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            # Simple Processing: Resize for performance
            frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Run Inference
            if self.face_cascade is not None:
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                self.detection_count = len(faces)
                
                for (x, y, w, h) in faces:
                    # Draw Bounding Box (Green)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Draw label BELOW the box
                    label = "Person/Face"
                    cv_y = y + h + 20 if y + h + 20 < 480 else y + h - 10
                    cv2.putText(frame, label, (x, cv_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                # Fallback: Just draw a timestamp if no model
                cv2.putText(frame, f"Live Stream: {time.ctime()}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            with self.lock:
                self.output_frame = frame.copy()

    def generate(self):
        while self.is_running:
            with self.lock:
                if self.output_frame is None:
                    continue
                (flag, encodedImage) = cv2.imencode(".jpg", self.output_frame)
                if not flag:
                    continue
            
            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                  bytearray(encodedImage) + b'\r\n')

    def stop(self):
        self.is_running = False
        self.cap.release()

camera = CameraManager()

# -----------------------------------------------------------------------------
# FastAPI Endpoints
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head>
            <title>Object Detection Node</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; text-align: center; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
                .container { max-width: 800px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
                h1 { color: #38bdf8; margin-bottom: 20px; font-weight: 700; }
                .video-wrapper { position: relative; display: inline-block; border: 4px solid #334155; border-radius: 12px; overflow: hidden; background: #000; }
                img { max-width: 100%; display: block; }
                .status { margin-top: 20px; display: flex; justify-content: space-around; font-weight: 500; }
                .badge { padding: 4px 12px; border-radius: 9999px; background: #0ea5e9; color: white; font-size: 0.875rem; }
                .live-dot { height: 10px; width: 10px; background-color: #ef4444; border-radius: 50%; display: inline-block; margin-right: 5px; animation: blink 1s infinite; }
                @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
            </style>
            <script>
                setInterval(async () => {
                    const res = await fetch('/metrics');
                    const data = await res.json();
                    document.getElementById('count').innerText = data.detections;
                }, 1000);
            </script>
        </head>
        <body>
            <div class="container">
                <h1><span class="live-dot"></span>Real-time Object Detection</h1>
                <div class="video-wrapper">
                    <img src="/video_feed">
                </div>
                <div class="status">
                    <div>Status: <span class="badge">Active</span></div>
                    <div>Detections: <span id="count" class="badge">0</span></div>
                    <div>Node: <span class="badge">Raspberry Pi</span></div>
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(camera.generate(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/metrics")
async def get_vision_metrics():
    return {
        "detections": camera.detection_count,
        "active": camera.is_running,
        "timestamp": time.time()
    }

@app.on_event("shutdown")
def shutdown_event():
    camera.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="10.42.0.11", port=8001)
