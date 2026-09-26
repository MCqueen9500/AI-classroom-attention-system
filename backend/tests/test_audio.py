"""
backend/tests/test_audio.py
==============================
Unit tests for Phase 4 Audio Q&A Pipeline.
No microphone, no Whisper model, no Ollama required.
All tests use synthetic data.
"""

import sys, os, time
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipelines.audio.vad          import EnergyVAD, SpeechSegment
from pipelines.audio.roll_detector import RollDetector
from pipelines.audio.llm_scorer   import LLMAnswerScorer
from pipelines.audio.qa_window    import QAWindowManager, QAInteractionRecord, WindowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SR = 16000   # 16 kHz

def make_silence(duration_s=0.5) -> np.ndarray:
    """Generate silent audio (int16 zeros)."""
    return np.zeros(int(SR * duration_s), dtype=np.int16)

def make_speech(duration_s=1.0, amplitude=8000) -> np.ndarray:
    """Generate synthetic speech-like audio (sine wave at 440 Hz)."""
    t = np.linspace(0, duration_s, int(SR * duration_s))
    return (np.sin(2 * np.pi * 440 * t) * amplitude).astype(np.int16)

def chunk_audio(audio: np.ndarray, chunk_size=1600):
    """Split audio array into chunks of chunk_size samples."""
    for i in range(0, len(audio), chunk_size):
        yield audio[i:i+chunk_size]


# ---------------------------------------------------------------------------
# EnergyVAD Tests
# ---------------------------------------------------------------------------

class TestEnergyVAD:
    def test_silence_produces_no_segment(self):
        vad = EnergyVAD(energy_threshold=0.01)
        silence = make_silence(2.0)
        result = None
        for chunk in chunk_audio(silence):
            result = vad.process_chunk(chunk, time.time())
        assert result is None, "Silence should produce no segment"

    def test_speech_then_silence_produces_segment(self):
        vad = EnergyVAD(energy_threshold=0.01, min_speech_frames=2, silence_pad_frames=3)
        speech  = make_speech(1.5, amplitude=10000)
        silence = make_silence(1.0)
        audio   = np.concatenate([speech, silence])

        segments = []
        for chunk in chunk_audio(audio, chunk_size=1600):
            seg = vad.process_chunk(chunk, time.time())
            if seg:
                segments.append(seg)

        assert len(segments) >= 1, "Should have detected at least one speech segment"
        seg = segments[0]
        assert isinstance(seg, SpeechSegment)
        assert seg.duration_s > 0
        assert len(seg.audio) > 0

    def test_segment_has_correct_sample_rate(self):
        vad = EnergyVAD(energy_threshold=0.01, min_speech_frames=2, silence_pad_frames=3)
        audio = np.concatenate([make_speech(1.0, 10000), make_silence(1.0)])
        for chunk in chunk_audio(audio):
            seg = vad.process_chunk(chunk, time.time())
            if seg:
                assert seg.sample_rate == 16000

    def test_reset_clears_buffer(self):
        vad = EnergyVAD(energy_threshold=0.01, min_speech_frames=2)
        speech = make_speech(0.5, 10000)
        for chunk in chunk_audio(speech):
            vad.process_chunk(chunk, time.time())
        vad.reset()
        assert vad._buffer == []
        assert not vad._in_speech


# ---------------------------------------------------------------------------
# RollDetector Tests
# ---------------------------------------------------------------------------

class TestRollDetector:
    def setup_method(self):
        self.students = [
            {"roll_no": 1,  "name": "Krushna"},
            {"roll_no": 7,  "name": "Ananya"},
            {"roll_no": 14, "name": "Rohan"},
        ]
        self.det = RollDetector(self.students)

    def test_detect_roll_number_basic(self):
        roll, q = self.det.detect("roll 14 what is ear formula")
        assert roll == 14
        assert "ear" in q

    def test_detect_roll_number_keyword(self):
        roll, q = self.det.detect("roll number 7 explain head pose")
        assert roll == 7

    def test_detect_roll_no_abbreviation(self):
        roll, q = self.det.detect("roll no 1 tell me formula one")
        assert roll == 1

    def test_detect_student_keyword(self):
        roll, q = self.det.detect("student 14 what is solvepnp")
        assert roll == 14

    def test_detect_by_name(self):
        roll, q = self.det.detect("krushna explain the ear formula")
        assert roll == 1

    def test_no_student_returns_none(self):
        roll, q = self.det.detect("the formula is a times b plus c")
        assert roll is None
        assert q is None

    def test_teacher_interruption_detected(self):
        assert self.det.is_teacher_interruption("okay that's enough") is True
        assert self.det.is_teacher_interruption("yes correct") is True
        assert self.det.is_teacher_interruption("the student said something") is False

    def test_teacher_reaction_positive(self):
        score = self.det.score_teacher_reaction("excellent answer")
        assert score == 1.0

    def test_teacher_reaction_partial(self):
        score = self.det.score_teacher_reaction("almost there, not quite")
        assert 0.3 < score < 0.9   # partial credit range

    def test_teacher_reaction_negative(self):
        score = self.det.score_teacher_reaction("no that is wrong")
        assert score < 0.3


# ---------------------------------------------------------------------------
# LLMAnswerScorer Tests (keyword fallback only — no Ollama needed)
# ---------------------------------------------------------------------------

class TestLLMScorerKeywordFallback:
    def setup_method(self):
        # Force keyword fallback (Ollama not running in test env)
        self.scorer = LLMAnswerScorer(ollama_url="http://localhost:1", model="test")
        assert not self.scorer._available   # Ollama won't be reachable

    def test_positive_reaction_gives_high_score(self):
        score, reason, method = self.scorer.score("what is EAR?", "ratio of eye height to width", "excellent")
        assert score >= 0.8
        assert method == "keyword"

    def test_negative_reaction_gives_low_score(self):
        score, reason, method = self.scorer.score("what is EAR?", "i dont know", "wrong answer")
        assert score <= 0.3

    def test_no_answer_gives_zero(self):
        score, _, _ = self.scorer.score("what is solvePnP?", "", "")
        assert score == 0.0

    def test_i_dont_know_gives_zero(self):
        score, reason, _ = self.scorer.score("define yaw", "i don't know", "")
        assert score == 0.0

    def test_long_answer_gets_credit(self):
        long_answer = "the ear formula is the ratio of the sum of two vertical distances to twice the horizontal eye width"
        score, _, _ = self.scorer.score("define EAR", long_answer, "")
        assert score >= 0.5


# ---------------------------------------------------------------------------
# Intent Classifier Tests (keyword fallback — no Ollama needed)
# ---------------------------------------------------------------------------

class TestIntentClassifier:
    def setup_method(self):
        # Force keyword fallback
        self.scorer = LLMAnswerScorer(ollama_url="http://localhost:1", model="test")

    def _classify(self, text):
        return self.scorer.classify_intent(text)

    # -- Should be classified as QUESTION --
    def test_what_is_question(self):
        r = self._classify("what is the EAR formula")
        assert r["intent"] == "question"

    def test_explain_is_question(self):
        r = self._classify("explain head pose estimation")
        assert r["intent"] == "question"

    def test_define_is_question(self):
        r = self._classify("define yaw pitch and roll")
        assert r["intent"] == "question"

    def test_how_is_question(self):
        r = self._classify("how does solvePnP work")
        assert r["intent"] == "question"

    def test_calculate_is_question(self):
        r = self._classify("calculate the attention score given H 0.8 G 0.9 P 0.7")
        assert r["intent"] == "question"

    def test_question_mark_is_question(self):
        r = self._classify("tell me the formula?")
        assert r["intent"] == "question"

    # -- Should be classified as CASUAL --
    def test_sit_properly_is_casual(self):
        r = self._classify("sit properly please")
        assert r["intent"] == "casual"

    def test_are_you_okay_is_casual(self):
        r = self._classify("are you feeling okay today")
        assert r["intent"] == "casual"

    def test_good_morning_is_casual(self):
        r = self._classify("good morning how are you")
        assert r["intent"] == "casual"

    def test_come_to_board_is_casual(self):
        r = self._classify("come to the board please")
        assert r["intent"] == "casual"

    def test_pay_attention_is_casual(self):
        r = self._classify("pay attention to what I am saying")
        assert r["intent"] == "casual"

    def test_too_short_is_casual(self):
        r = self._classify("hi")
        assert r["intent"] == "casual"

    # -- Method should always be 'keyword' in fallback mode --
    def test_method_is_keyword(self):
        r = self._classify("what is formula one")
        assert r["method"] == "keyword"

    def test_result_has_all_keys(self):
        r = self._classify("explain the posture scorer")
        assert "intent" in r
        assert "confidence" in r
        assert "reason" in r
        assert "method" in r


# ---------------------------------------------------------------------------
# QAWindowManager Tests
# ---------------------------------------------------------------------------

class TestQAWindowManager:
    def test_initial_state_is_idle(self):
        mgr = QAWindowManager(window_duration=15.0)
        assert mgr.state == WindowState.IDLE

    def test_open_window_transitions_to_waiting(self):
        mgr = QAWindowManager(window_duration=15.0)
        mgr.on_question_detected(roll_no=14, question="what is EAR?")
        assert mgr.state == WindowState.WAITING
        assert mgr.is_waiting is True

    def test_student_response_closes_window(self):
        completed = []
        mgr = QAWindowManager(
            window_duration=15.0,
            on_complete=lambda r: completed.append(r),
        )
        mgr.on_question_detected(14, "what is EAR?")
        mgr.on_speech_segment("ear is the ratio of eye height to width", is_teacher=False)
        assert mgr.state == WindowState.IDLE
        assert len(completed) == 1
        assert completed[0].roll_no == 14
        assert completed[0].Q_i >= 0.0

    def test_teacher_interruption_gives_full_score(self):
        completed = []
        mgr = QAWindowManager(
            window_duration=15.0,
            on_complete=lambda r: completed.append(r),
        )
        mgr.on_question_detected(7, "explain head pose")
        mgr.on_speech_segment("okay let me explain it", is_teacher=True)
        assert len(completed) == 1
        assert completed[0].Q_i == 1.0
        assert completed[0].score_method == "interrupted"

    def test_timeout_gives_zero_score(self):
        completed = []
        mgr = QAWindowManager(
            window_duration=0.1,   # 100ms timeout for testing
            on_complete=lambda r: completed.append(r),
        )
        mgr.on_question_detected(3, "what is posture score?")
        time.sleep(0.15)
        mgr.tick()   # trigger timeout check
        assert len(completed) == 1
        assert completed[0].Q_i == 0.0
        assert completed[0].score_method == "timeout"

    def test_seconds_remaining_counts_down(self):
        mgr = QAWindowManager(window_duration=5.0)
        mgr.on_question_detected(1, "test question")
        remaining = mgr.seconds_remaining
        assert 4.0 < remaining <= 5.0

    def test_record_has_response_latency(self):
        completed = []
        mgr = QAWindowManager(
            window_duration=5.0,
            on_complete=lambda r: completed.append(r),
        )
        mgr.on_question_detected(5, "what is formula 3?")
        time.sleep(0.05)
        mgr.on_speech_segment("formula 3 combines punctuality attention and qa", is_teacher=False)
        assert completed[0].response_latency_s > 0
