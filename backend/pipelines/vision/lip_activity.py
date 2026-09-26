"""
pipelines/vision/lip_activity.py
===================================
Lip Activity Detector — identifies WHICH face is speaking
by measuring lip aperture variance over a rolling frame window.

How it works:
  1. For each face, extract 4 key lip landmarks from MediaPipe (478 pts)
  2. Compute Lip Aperture Ratio (LAR) = vertical opening / face height
  3. Maintain rolling window of LAR values per face slot
  4. Compute variance of LAR → Lip Activity Score
  5. Face with highest score = current speaker

Usage in QA pipeline:
  - During 15-second response window, call update() every frame
  - Call get_speaker() to find which face is most likely speaking
  - Cross-check with expected roll number to detect wrong-student responses

LAR Landmark indices (MediaPipe 478-point model):
  13  → upper inner lip center
  14  → lower inner lip center
  0   → top of upper lip (outer)
  17  → bottom of lower lip (outer)
  61  → left mouth corner
  291 → right mouth corner
"""

import logging
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# MediaPipe landmark indices for lip measurement
UPPER_LIP_IDX = 13    # inner upper lip center
LOWER_LIP_IDX = 14    # inner lower lip center
MOUTH_LEFT_IDX = 61   # left mouth corner
MOUTH_RIGHT_IDX = 291 # right mouth corner
UPPER_OUTER_IDX = 0   # top of upper lip
LOWER_OUTER_IDX = 17  # bottom of lower lip

# Nose tip for face size normalization
NOSE_TIP_IDX = 1
CHIN_IDX = 152


@dataclass
class LipActivityResult:
    """Lip activity measurement for one face in one frame."""
    face_slot:       int    # which face in the frame (0, 1, 2, ...)
    lip_aperture:    float  # current opening distance (normalized)
    activity_score:  float  # variance over rolling window → is this face speaking?
    is_speaking:     bool   # True if this face has the highest activity score


class LipActivityTracker:
    """
    Tracks lip movement for multiple faces simultaneously.
    Identifies which face is currently speaking.

    Args:
        window_frames    : how many frames to keep in rolling window (default 15 = ~1s at 15fps)
        speaking_threshold : minimum activity score to consider someone speaking
        min_frames       : minimum frames collected before making a speaker decision
    """

    def __init__(
        self,
        window_frames:      int   = 15,
        speaking_threshold: float = 0.0003,  # variance threshold
        min_frames:         int   = 5,
    ):
        self._window     = window_frames
        self._threshold  = speaking_threshold
        self._min_frames = min_frames

        # Per-face rolling windows: {face_slot: deque([lar values])}
        self._windows: Dict[int, deque] = {}

    def update(self, face_slot: int, landmarks_px: np.ndarray, frame_h: int) -> float:
        """
        Feed one frame's landmarks for one face.
        Returns current Lip Aperture Ratio for this face.

        Args:
            face_slot     : face index in current frame (0, 1, 2, ...)
            landmarks_px  : (N, 2) pixel landmark array from LandmarkExtractor
            frame_h       : frame height in pixels (for normalization)
        Returns:
            lip_aperture_ratio: float [0, 1]
        """
        if len(landmarks_px) <= max(UPPER_LIP_IDX, LOWER_LIP_IDX, CHIN_IDX):
            return 0.0

        # Lip aperture = vertical distance between inner upper and lower lip
        upper = landmarks_px[UPPER_LIP_IDX].astype(float)
        lower = landmarks_px[LOWER_LIP_IDX].astype(float)
        aperture_px = float(np.linalg.norm(upper - lower))

        # Normalize by face height (nose to chin distance) for scale invariance
        nose  = landmarks_px[NOSE_TIP_IDX].astype(float)
        chin  = landmarks_px[CHIN_IDX].astype(float)
        face_height = float(np.linalg.norm(nose - chin))

        if face_height < 1.0:
            return 0.0

        lar = aperture_px / face_height   # Lip Aperture Ratio [0, ~0.5]

        # Push into rolling window
        if face_slot not in self._windows:
            self._windows[face_slot] = deque(maxlen=self._window)
        self._windows[face_slot].append(lar)

        return lar

    def get_activity_scores(self) -> Dict[int, float]:
        """
        Compute lip activity score (variance) for each tracked face.
        Higher variance = more lip movement = more likely speaking.

        Returns:
            {face_slot: activity_score}
        """
        scores = {}
        for slot, window in self._windows.items():
            if len(window) >= self._min_frames:
                scores[slot] = float(np.var(list(window)))
            else:
                scores[slot] = 0.0
        return scores

    def get_speaker(self) -> Optional[int]:
        """
        Returns the face_slot of the most likely current speaker.
        Returns None if no face has activity above threshold.
        """
        scores = self.get_activity_scores()
        if not scores:
            return None

        best_slot  = max(scores, key=scores.get)
        best_score = scores[best_slot]

        if best_score >= self._threshold:
            logger.debug(
                "LipTracker: Speaker = slot %d (score=%.5f)", best_slot, best_score
            )
            return best_slot

        return None

    def get_all_results(self, speaking_slot: Optional[int] = None) -> List[LipActivityResult]:
        """
        Get full activity results for all tracked faces.
        Useful for overlay visualization (show who is speaking).
        """
        scores = self.get_activity_scores()
        speaker = speaking_slot if speaking_slot is not None else self.get_speaker()
        results = []

        for slot, score in scores.items():
            window = self._windows.get(slot, deque())
            lar = list(window)[-1] if window else 0.0
            results.append(LipActivityResult(
                face_slot=slot,
                lip_aperture=round(lar, 4),
                activity_score=round(score, 6),
                is_speaking=(slot == speaker and score >= self._threshold),
            ))

        return results

    def reset_slot(self, face_slot: int):
        """Clear history for a specific face (call when face disappears)."""
        self._windows.pop(face_slot, None)

    def reset_all(self):
        """Clear all face histories (call on session pause/resume)."""
        self._windows.clear()


# ---------------------------------------------------------------------------
# QA Cross-Checker — connects lip tracker to QA pipeline
# ---------------------------------------------------------------------------

@dataclass
class SpeakerCheckResult:
    """Result of checking whether the correct student answered."""
    asked_roll:       int
    asked_face_slot:  Optional[int]   # which slot corresponds to Roll X
    speaker_slot:     Optional[int]   # which slot is actually speaking
    speaker_roll:     Optional[int]   # roll number of the actual speaker
    is_correct:       bool            # True if speaker == asked student
    confidence:       float           # how confident we are in the detection
    activity_scores:  Dict[int, float]


class QASpeakerChecker:
    """
    During a QA window, continuously checks whether the CORRECT student
    is answering using lip activity tracking.

    Usage:
        checker = QASpeakerChecker(lip_tracker, roll_to_slot_map)
        checker.start(asked_roll=14)

        # in vision loop:
        for det in detections:
            lip_tracker.update(idx, landmarks.landmarks_px, frame_h)
        result = checker.check(roll_to_slot_map)

        checker.stop()
        final = checker.get_final_verdict()
    """

    def __init__(
        self,
        lip_tracker:    LipActivityTracker,
        wrong_penalty:  float = 0.0,   # Q_i for asked student if wrong person answers
    ):
        self._tracker      = lip_tracker
        self._wrong_penalty = wrong_penalty
        self._active        = False
        self._asked_roll    = None

        # Voting buffer: collect speaker detections over window
        self._speaker_votes: List[Optional[int]] = []

    def start(self, asked_roll: int):
        """Begin monitoring — called when QA window opens."""
        self._asked_roll   = asked_roll
        self._active       = True
        self._speaker_votes = []
        logger.info("QASpeakerChecker: Monitoring started for Roll %d", asked_roll)

    def stop(self):
        """Stop monitoring — called when QA window closes."""
        self._active = False

    def tick(self, slot_to_roll: Dict[int, int]) -> Optional[SpeakerCheckResult]:
        """
        Call every frame during QA window.
        Returns SpeakerCheckResult if a speaker is confidently detected.

        Args:
            slot_to_roll: mapping of {face_slot: roll_no} for current frame
                          e.g. {0: 14, 1: 7, 2: 22}
        """
        if not self._active or self._asked_roll is None:
            return None

        speaker_slot = self._tracker.get_speaker()
        self._speaker_votes.append(speaker_slot)

        # Need at least 5 votes before making a decision
        if len(self._speaker_votes) < 5:
            return None

        # Majority vote over last 10 frames
        recent = self._speaker_votes[-10:]
        valid  = [v for v in recent if v is not None]
        if not valid:
            return None

        # Most common speaker slot
        from collections import Counter
        most_common_slot, count = Counter(valid).most_common(1)[0]
        confidence = count / len(recent)

        if confidence < 0.4:
            return None   # not confident enough yet

        # Find asked student's slot
        asked_slot = next(
            (slot for slot, roll in slot_to_roll.items() if roll == self._asked_roll),
            None
        )

        # Find speaker's roll number
        speaker_roll = slot_to_roll.get(most_common_slot)

        is_correct = (most_common_slot == asked_slot) and (asked_slot is not None)

        scores = self._tracker.get_activity_scores()

        result = SpeakerCheckResult(
            asked_roll=self._asked_roll,
            asked_face_slot=asked_slot,
            speaker_slot=most_common_slot,
            speaker_roll=speaker_roll,
            is_correct=is_correct,
            confidence=round(confidence, 2),
            activity_scores=scores,
        )

        if not is_correct and speaker_roll is not None:
            logger.warning(
                "QASpeakerChecker: ⚠️  WRONG STUDENT — Asked Roll %d | "
                "Actual Speaker Roll %d (slot %d, conf=%.0f%%)",
                self._asked_roll, speaker_roll, most_common_slot, confidence * 100
            )

        return result

    def get_final_verdict(self, slot_to_roll: Dict[int, int]) -> SpeakerCheckResult:
        """
        Call when QA window closes to get the overall verdict.
        Uses majority vote across ALL collected frames.
        """
        valid = [v for v in self._speaker_votes if v is not None]

        if not valid:
            return SpeakerCheckResult(
                asked_roll=self._asked_roll or 0,
                asked_face_slot=None,
                speaker_slot=None,
                speaker_roll=None,
                is_correct=False,
                confidence=0.0,
                activity_scores={},
            )

        from collections import Counter
        most_common_slot, count = Counter(valid).most_common(1)[0]
        confidence   = count / len(self._speaker_votes)
        speaker_roll = slot_to_roll.get(most_common_slot)
        asked_slot   = next(
            (s for s, r in slot_to_roll.items() if r == self._asked_roll), None
        )
        is_correct = (most_common_slot == asked_slot) and (asked_slot is not None)

        return SpeakerCheckResult(
            asked_roll=self._asked_roll or 0,
            asked_face_slot=asked_slot,
            speaker_slot=most_common_slot,
            speaker_roll=speaker_roll,
            is_correct=is_correct,
            confidence=round(confidence, 2),
            activity_scores=self._tracker.get_activity_scores(),
        )
