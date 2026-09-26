"""
scripts/register_face.py
========================
Tool to capture a student's face from the webcam, extract their 128-d SFace embedding,
and save it to the database for real facial recognition.

Usage:
  python scripts/register_face.py <roll_no>
"""

import sys, os, time, json
import cv2
import asyncio
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from core.logging_config import setup_logging
from core.config import settings
from db.session import AsyncSessionLocal
from db.models import Student
from sqlalchemy import select

from pipelines.vision.face_detector import build_face_detector
from pipelines.vision.face_recognizer import FaceRecognizer

async def save_embedding(roll_no: int, embedding: np.ndarray):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Student).where(Student.roll_no == roll_no))
        student = result.scalars().first()
        if not student:
            print(f"Error: Student with roll {roll_no} not found in DB.")
            return False
            
        # Store as standard python list
        student.face_embedding = embedding.tolist()
        await db.commit()
        print(f"Success! Face registered for Roll {roll_no} ({student.name}).")
        return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python register_face.py <roll_no>")
        sys.exit(1)
        
    try:
        roll_no = int(sys.argv[1])
    except ValueError:
        print("Error: roll_no must be an integer.")
        sys.exit(1)
        
    print("Loading models...")
    detector = build_face_detector(prefer="mediapipe", min_detection_confidence=0.5)
    recognizer = FaceRecognizer()
    
    cap = cv2.VideoCapture(settings.webcam_device_index)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        sys.exit(1)
        
    print("\n" + "="*50)
    print(f" Registering Face for Roll No: {roll_no}")
    print("="*50)
    print("1. Look directly at the camera.")
    print("2. Ensure good lighting.")
    print("3. Press 'SPACE' to capture, or 'Q' to quit.\n")
    
    embedding = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        display = frame.copy()
        
        # Detect face
        detections = detector.detect(frame)
        
        if len(detections) == 0:
            color = (0, 0, 255)
            text = "No face detected"
        elif len(detections) > 1:
            color = (0, 0, 255)
            text = "Multiple faces detected!"
        else:
            color = (0, 255, 0)
            text = "Face found. Press SPACE to capture."
            det = detections[0]
            x, y, w, h = det.bbox
            cv2.rectangle(display, (x, y), (x+w, y+h), color, 2)
            
        cv2.putText(display, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.imshow("Face Registration", display)
        
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
        elif key == 32: # SPACE
            if len(detections) == 1:
                det = detections[0]
                if hasattr(det, 'yunet_face_row'):
                    print("Extracting embedding...")
                    embedding = recognizer.extract_embedding(frame, det.yunet_face_row)
                    break
                else:
                    print("Error: Detector must be YuNet for SFace alignment.")
                    break
            else:
                print("Cannot capture. Ensure exactly ONE face is visible.")

    cap.release()
    cv2.destroyAllWindows()
    
    if embedding is not None:
        asyncio.run(save_embedding(roll_no, embedding))

if __name__ == "__main__":
    main()
