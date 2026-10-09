"""
pipelines/audio/llm_scorer.py
================================
Local LLM answer quality scorer using Ollama.

Sends question + student answer + teacher reaction to a locally running
LLM (via Ollama HTTP API at http://localhost:11434) and gets back a
quality score Q_i from 0.0 to 1.0.

Requires Ollama installed separately:
  https://ollama.ai/download  (Windows installer)
  Then: ollama pull phi3.5:mini

Falls back to keyword-based scoring if Ollama is unavailable.
"""

import json
import logging
import time
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt: Intent Classification â€” Is teacher asking a question?
# ---------------------------------------------------------------------------
INTENT_PROMPT = """You are a classroom AI assistant. A teacher spoke to a specific student.

TEACHER SAID (after addressing the student by roll number or name):
"{utterance}"

Classify whether the teacher is:
  A) Asking an academic QUESTION that expects a detailed answer (e.g., "what is EAR?", "explain head pose", "define yaw angle")
  B) CASUAL interaction that does NOT require an academic answer (e.g., "sit properly", "are you okay", "good morning", "come to the board", "pay attention", "be quiet")

Reply ONLY with valid JSON, nothing else:
{{"intent": "question", "confidence": 0.95, "reason": "teacher is asking for explanation"}}
OR
{{"intent": "casual", "confidence": 0.92, "reason": "teacher is giving an instruction"}}"""

# Keyword-based fallback for when LLM is unavailable
QUESTION_KEYWORDS = [
    "what", "how", "why", "explain", "define", "describe",
    "calculate", "tell me", "state", "give", "list", "derive",
    "prove", "show", "solve", "find", "which", "who", "where",
    "when", "difference between", "compare", "elaborate", "formula",
]

CASUAL_KEYWORDS = [
    "sit", "stand", "come", "go", "stop", "be quiet", "pay attention",
    "are you", "good morning", "good afternoon", "hello", "hi",
    "alright", "thank you", "write", "open",
    "close", "read", "look at", "listen", "watch", "turn",
]


def _keyword_classify_intent_fn(utterance: str) -> dict:
    """
    Module-level keyword intent classifier.
    Used by AudioPipeline when Ollama is unavailable â€” avoids
    instantiating a dummy LLMAnswerScorer.

    Priority: question keywords checked FIRST to avoid false casual hits.
    Returns dict with intent, confidence, reason, method.
    """
    utterance = utterance.strip().lower()

    if not utterance or len(utterance.split()) < 2:
        return {"intent": "casual", "confidence": 0.9,
                "reason": "too short to be a question", "method": "keyword"}

    # Question keywords checked FIRST â€” higher specificity
    for kw in QUESTION_KEYWORDS:
        if kw in utterance:
            return {
                "intent":     "question",
                "confidence": 0.85,
                "reason":     f"question keyword '{kw}' detected",
                "method":     "keyword",
            }

    # Ends with question mark?
    if utterance.rstrip().endswith("?"):
        return {
            "intent":     "question",
            "confidence": 0.90,
            "reason":     "utterance ends with question mark",
            "method":     "keyword",
        }

    # Casual keywords second â€” only if no question keyword found
    for kw in CASUAL_KEYWORDS:
        if kw in utterance:
            return {
                "intent":     "casual",
                "confidence": 0.75,
                "reason":     f"casual keyword '{kw}' detected",
                "method":     "keyword",
            }

    # Default: treat as question â€” give student benefit of the doubt
    return {
        "intent":     "question",
        "confidence": 0.50,
        "reason":     "no clear signal â€” defaulting to question",
        "method":     "keyword",
    }



# ---------------------------------------------------------------------------
# Prompt: Answer Quality Scoring
# ---------------------------------------------------------------------------

SCORING_PROMPT = """You are an AI assistant evaluating a student's answer in a classroom.

TEACHER QUESTION: {question}
STUDENT ANSWER: {answer}
TEACHER REACTION (after student spoke): {reaction}

Score the student's answer quality from 0.0 to 1.0 using these guidelines:
  1.0 = Perfect, complete, teacher satisfied
  0.8 = Good answer, minor gaps
  0.6 = Partially correct, main concept right
  0.4 = Some relevant content but largely incorrect
  0.2 = Attempted but mostly wrong
  0.0 = No answer, completely irrelevant, or "I don't know"

Consider the teacher's reaction as the strongest signal.
If the teacher interrupted early or said "okay/stop", lean toward 0.9-1.0.

Reply ONLY with valid JSON, nothing else:
{{"score": 0.7, "reason": "brief explanation in one sentence"}}"""


class LLMAnswerScorer:
    """
    Evaluates student answer quality using a locally running Ollama LLM.
    Falls back to keyword scoring if Ollama is unreachable.
    """

    def __init__(
        self,
        ollama_url:  str = "http://localhost:11434",
        model:       str = "phi3.5:mini",
        timeout_s:   int = 15,
    ):
        self._url     = ollama_url
        self._model   = model
        self._timeout = timeout_s
        self._available = self._check_ollama()

    def _check_ollama(self) -> bool:
        """Check if Ollama server is running."""
        try:
            r = requests.get(f"{self._url}/api/tags", timeout=3)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                if any(self._model in m for m in models):
                    logger.info("LLMScorer: Ollama ready with model '%s'", self._model)
                    return True
                logger.warning(
                    "LLMScorer: Ollama running but model '%s' not found. "
                    "Run: ollama pull %s", self._model, self._model
                )
            return False
        except Exception:
            logger.warning(
                "LLMScorer: Ollama not reachable at %s. "
                "Using keyword fallback. To enable: install Ollama + run 'ollama pull %s'",
                self._url, self._model
            )
            return False

    # ------------------------------------------------------------------
    # STEP 1 â€” Intent Classification
    # ------------------------------------------------------------------

    def classify_intent(self, utterance: str) -> dict:
        """
        Determine if teacher's utterance is a QUESTION or CASUAL TALK.

        This runs BEFORE opening the 15-second QA window.
        Only if intent == "question" should the window open.

        Args:
            utterance: text spoken by teacher AFTER the roll number/name
                       e.g. "what is the EAR formula"
                            "sit properly"
                            "are you feeling okay"

        Returns:
            {
                "intent":     "question" | "casual",
                "confidence": float,
                "reason":     str,
                "method":     "llm" | "keyword"
            }
        """
        utterance = utterance.strip().lower()

        if not utterance or len(utterance.split()) < 2:
            # Too short to be an academic question
            return {"intent": "casual", "confidence": 0.9,
                    "reason": "too short", "method": "keyword"}

        # Try LLM first
        if self._available:
            result = self._llm_classify_intent(utterance)
            if result:
                return result

        # Keyword fallback
        return self._keyword_classify_intent(utterance)

    def _llm_classify_intent(self, utterance: str) -> Optional[dict]:
        """Ask Ollama to classify intent."""
        prompt = INTENT_PROMPT.format(utterance=utterance)
        try:
            t0 = time.time()
            response = requests.post(
                f"{self._url}/api/generate",
                json={
                    "model":  self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.0, "num_predict": 60},
                },
                timeout=8,   # shorter timeout for intent check
            )
            latency = round(time.time() - t0, 2)

            if response.status_code != 200:
                return None

            raw  = response.json().get("response", "{}")
            data = json.loads(raw)

            intent     = str(data.get("intent", "question")).lower()
            confidence = float(data.get("confidence", 0.7))
            reason     = str(data.get("reason", ""))

            # Normalize to "question" or "casual"
            if intent not in ("question", "casual"):
                intent = "question"   # default to question on ambiguity

            logger.info(
                "LLMIntent: '%s' â†’ %s (conf=%.2f) | %s | %.2fs",
                utterance[:50], intent, confidence, reason, latency
            )
            return {
                "intent": intent, "confidence": confidence,
                "reason": reason, "method": "llm"
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("LLMIntent: JSON parse error: %s", e)
            return None
        except Exception as e:
            logger.warning("LLMIntent: Error: %s", e)
            return None

    def _keyword_classify_intent(self, utterance: str) -> dict:
        """
        Keyword-based intent classification fallback.

        Logic:
          1. If ANY casual keyword found â†’ casual
          2. If ANY question keyword found â†’ question
          3. If utterance ends with '?' â†’ question
          4. Default â†’ question (give student benefit of doubt)
        """
        # Check casual FIRST â€” more specific, avoids false positives
        for kw in CASUAL_KEYWORDS:
            if kw in utterance:
                return {
                    "intent":     "casual",
                    "confidence": 0.75,
                    "reason":     f"casual keyword '{kw}' detected",
                    "method":     "keyword",
                }

        # Check question keywords
        for kw in QUESTION_KEYWORDS:
            if kw in utterance:
                return {
                    "intent":     "question",
                    "confidence": 0.80,
                    "reason":     f"question keyword '{kw}' detected",
                    "method":     "keyword",
                }

        # Ends with question mark?
        if utterance.rstrip().endswith("?"):
            return {
                "intent":     "question",
                "confidence": 0.85,
                "reason":     "utterance ends with question mark",
                "method":     "keyword",
            }

        # Default: treat as question (student gets benefit of doubt)
        return {
            "intent":     "question",
            "confidence": 0.50,
            "reason":     "no clear signal â€” defaulting to question",
            "method":     "keyword",
        }

    def score(
        self,
        question:        str,
        student_answer:  str,
        teacher_reaction: str = "",
    ) -> tuple:
        """
        Score student answer quality.

        Args:
            question         : what the teacher asked
            student_answer   : what the student said
            teacher_reaction : teacher's verbal response after student spoke

        Returns:
            (Q_i: float, reason: str, method: str)
        """
        if not student_answer or student_answer.strip() == "":
            return 0.0, "no answer given", "empty"

        if self._available:
            result = self._llm_score(question, student_answer, teacher_reaction)
            if result is not None:
                return result

        # Fallback: keyword heuristic
        return self._keyword_score(student_answer, teacher_reaction)

    def _llm_score(
        self,
        question: str,
        answer:   str,
        reaction: str,
    ) -> Optional[tuple]:
        """Send to Ollama and parse JSON response."""
        prompt = SCORING_PROMPT.format(
            question=question or "unknown question",
            answer=answer,
            reaction=reaction or "no reaction recorded",
        )

        try:
            t0 = time.time()
            response = requests.post(
                f"{self._url}/api/generate",
                json={
                    "model":  self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,   # near-deterministic for scoring
                        "num_predict": 80,
                    },
                },
                timeout=self._timeout,
            )
            latency = round(time.time() - t0, 2)

            if response.status_code != 200:
                logger.warning("LLMScorer: Ollama returned %d", response.status_code)
                return None

            raw = response.json().get("response", "{}")
            data = json.loads(raw)
            score  = float(data.get("score", 0.5))
            reason = str(data.get("reason", ""))
            score  = max(0.0, min(1.0, score))   # clamp

            logger.info(
                "LLMScorer: Q_i=%.2f | '%s' | LLM latency=%.2fs",
                score, reason, latency
            )
            return round(score, 3), reason, "llm"

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("LLMScorer: JSON parse error: %s", e)
            return None
        except requests.Timeout:
            logger.warning("LLMScorer: Ollama timeout after %ds", self._timeout)
            return None
        except Exception as e:
            logger.warning("LLMScorer: Unexpected error: %s", e)
            return None

    def _keyword_score(
        self,
        answer:   str,
        reaction: str,
    ) -> tuple:
        """
        Fallback keyword-based heuristic when LLM unavailable.
        Uses teacher reaction as primary signal.
        """
        answer_lower   = answer.lower()
        reaction_lower = reaction.lower()

        # Teacher reaction is the ground truth
        if any(w in reaction_lower for w in ["excellent", "perfect", "exactly", "very good"]):
            return 1.0, "teacher reaction: very positive", "keyword"
        if any(w in reaction_lower for w in ["good", "correct", "right", "yes"]):
            return 0.85, "teacher reaction: positive", "keyword"
        if any(w in reaction_lower for w in ["almost", "partially", "close", "nearly"]):
            return 0.6, "teacher reaction: partial credit", "keyword"
        if any(w in reaction_lower for w in ["wrong", "incorrect", "no", "not right"]):
            return 0.1, "teacher reaction: negative", "keyword"

        # Fallback: check if student gave any substantive answer
        word_count = len(answer_lower.split())
        if word_count >= 10:
            return 0.6, "substantive answer given", "keyword"
        if word_count >= 4:
            return 0.4, "brief answer given", "keyword"
        if "don't know" in answer_lower or "no idea" in answer_lower:
            return 0.0, "student admitted no knowledge", "keyword"

        return 0.3, "minimal response", "keyword"
