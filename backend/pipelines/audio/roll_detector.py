"""
pipelines/audio/roll_detector.py
===================================
Detects which student the teacher is addressing from transcribed text.

Handles patterns like:
  "roll number 14 explain the EAR formula"   → roll=14, q="explain the EAR formula"
  "roll 7 what is solvePnP"                  → roll=7,  q="what is solvePnP"
  "krushna tell me formula 3"                → looks up name in student DB → roll
  "student number 22 what is yaw"            → roll=22, q="what is yaw"

Returns: (roll_no, question_text) or (None, None) if no student addressed.
"""

import re
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns for roll number detection (order = priority)
# ---------------------------------------------------------------------------
ROLL_PATTERNS = [
    r"roll\s*(?:number|no|num|#)?\s*(\d{1,3})",   # roll 14, roll number 14
    r"student\s*(?:number|no)?\s*(\d{1,3})",        # student 14, student number 14
    r"number\s*(\d{1,3})\s",                         # number 14 [question]
    r"r\.?\s*n\.?\s*o?\.?\s*(\d{1,3})",             # r.n.o 14, rno 14
]

# Teacher question keywords — if these follow the roll number, it's a question
QUESTION_KEYWORDS = [
    "what", "how", "why", "explain", "tell", "define",
    "describe", "calculate", "give", "state", "list",
    "who", "where", "when", "which", "can you",
]


class RollDetector:
    """
    Identifies the target student and extracts the question
    from a teacher's transcribed utterance.
    """

    def __init__(self, known_students: List[dict] = None):
        """
        Args:
            known_students: list of {"roll_no": int, "name": str}
                            loaded from DB at pipeline start
        """
        self._students = known_students or []
        # Build name → roll_no lookup (lowercase)
        self._name_map = {
            s["name"].lower(): s["roll_no"]
            for s in self._students
            if s.get("name")
        }

    def update_students(self, students: List[dict]):
        """Refresh student list from DB (call when roster changes)."""
        self._students = students
        self._name_map = {
            s["name"].lower(): s["roll_no"]
            for s in students if s.get("name")
        }

    def detect(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Parse transcribed text to find addressed student + question.

        Args:
            text: lowercase transcribed text from Whisper
        Returns:
            (roll_no, question_text) or (None, None)
        """
        text = text.lower().strip()

        # 1. Try regex roll number patterns
        roll_no, question = self._detect_by_roll_pattern(text)
        if roll_no is not None:
            return roll_no, question

        # 2. Try student name matching
        roll_no, question = self._detect_by_name(text)
        if roll_no is not None:
            return roll_no, question

        return None, None

    def _detect_by_roll_pattern(
        self, text: str
    ) -> Tuple[Optional[int], Optional[str]]:
        for pattern in ROLL_PATTERNS:
            match = re.search(pattern, text)
            if match:
                roll_no = int(match.group(1))
                # Extract question part = text AFTER the roll number mention
                question = text[match.end():].strip()
                question = self._clean_question(question)
                logger.info(
                    "RollDetector: Roll %d detected | Q: '%s'",
                    roll_no, question
                )
                return roll_no, question
        return None, None

    def _detect_by_name(
        self, text: str
    ) -> Tuple[Optional[int], Optional[str]]:
        for name, roll_no in self._name_map.items():
            if name in text:
                idx = text.index(name) + len(name)
                question = text[idx:].strip()
                question = self._clean_question(question)
                logger.info(
                    "RollDetector: Name '%s' → Roll %d | Q: '%s'",
                    name, roll_no, question
                )
                return roll_no, question
        return None, None

    def _clean_question(self, text: str) -> str:
        """Remove filler words from start of question text."""
        fillers = [",", ".", "please", "can you", "now", "quickly", "tell me"]
        for f in fillers:
            if text.startswith(f):
                text = text[len(f):].strip()
        return text.strip() or "question"

    def is_teacher_interruption(self, text: str) -> bool:
        """
        Detect if teacher is interrupting the student mid-answer.
        Looks for patterns like "okay", "stop", "yes that's right", etc.
        """
        interruption_signals = [
            "okay", "ok", "stop", "alright", "yes", "no", "correct",
            "wrong", "good", "enough", "next", "anyone else",
            "let me explain", "actually", "never mind",
        ]
        text_lower = text.lower()
        return any(s in text_lower for s in interruption_signals)

    def score_teacher_reaction(self, reaction: str) -> Optional[float]:
        """
        Quick keyword-based pre-score from teacher's verbal reaction.
        Used as a hint/override when LLM is unavailable.

        Returns a float [0,1] or None if no clear signal.
        """
        r = reaction.lower()

        positive = ["excellent", "perfect", "exactly", "very good",
                    "well done", "great", "right", "good"]
        partial  = ["almost", "partially", "not quite", "close", "nearly",
                    "incomplete", "partly", "sort of", "yes", "correct"]
        negative = ["no", "wrong", "incorrect", "that's not", "not right",
                    "completely wrong", "no idea"]

        # Check partial FIRST to avoid 'correct' inside 'not correct' matching positive
        for p in partial:
            if p in r: return 0.55
        for p in positive:
            if p in r: return 1.0
        for p in negative:
            if p in r: return 0.1

        return None
