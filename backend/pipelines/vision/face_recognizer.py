"""
backend/pipelines/vision/face_recognizer.py
============================================
Wraps OpenCV's FaceRecognizerSF (SFace) model to extract 128-d face embeddings
and match them against known student embeddings using Cosine Similarity.
"""
import os
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FaceRecognizer:
    def __init__(self, model_path: str = "models/face_recognition_sface_2021dec.onnx"):
        self.model_path = os.path.abspath(model_path)
        if not os.path.exists(self.model_path):
            logger.error(f"SFace model not found at {self.model_path}. Run download_models.py")
            self._recognizer = None
            return
            
        try:
            self._recognizer = cv2.FaceRecognizerSF.create(self.model_path, "")
        except AttributeError:
            self._recognizer = cv2.FaceRecognizerSF_create(self.model_path, "")
        logger.info("FaceRecognizer: SFace model loaded successfully.")

    def extract_embedding(self, bgr_frame: np.ndarray, yunet_face_row: np.ndarray) -> np.ndarray:
        """
        Aligns the face using YuNet landmarks and extracts a 128-d normalized embedding.
        yunet_face_row is the 15-element array returned by OpenCV YuNet.
        """
        if self._recognizer is None:
            return np.zeros(128, dtype=np.float32)
            
        # 1. Align face crop
        aligned_face = self._recognizer.alignCrop(bgr_frame, yunet_face_row)
        
        # 2. Extract feature
        feature = self._recognizer.feature(aligned_face)
        return feature[0] # Returns shape (128,)

    def match(self, embedding: np.ndarray, known_dict: dict, threshold: float = 0.363) -> int:
        """
        known_dict is { roll_no: np.ndarray(128,) }
        Returns roll_no if matched, else None.
        Threshold 0.363 is standard for SFace Cosine Distance.
        """
        if self._recognizer is None or not known_dict:
            return None
            
        best_match = None
        min_dist = float('inf')
        
        for roll_no, known_emb in known_dict.items():
            # cv2.FaceRecognizerSF.match uses:
            # 0: Cosine Similarity, 1: L2 Distance.
            # SFace recommends Cosine distance threshold 0.363.
            # Actually match() returns a score, but we can compute cosine distance manually for clarity:
            
            # Compute true cosine distance
            norm_a = np.linalg.norm(embedding)
            norm_b = np.linalg.norm(known_emb)
            if norm_a == 0 or norm_b == 0:
                dist = 1.0
            else:
                score = np.dot(embedding, known_emb) / (norm_a * norm_b)
                dist = 1.0 - score
            
            if dist < min_dist:
                min_dist = dist
                best_match = roll_no
                
        if min_dist <= threshold:
            return best_match
            
        return None
