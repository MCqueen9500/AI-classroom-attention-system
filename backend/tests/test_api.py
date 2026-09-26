"""
backend/tests/test_api.py
===========================
Phase 5 API unit tests using FastAPI TestClient (no real DB required).
Tests all REST endpoints and WebSocket connection.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from api.app import app


# ---------------------------------------------------------------------------
# Sync client (for non-async tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_docs_reachable(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------
class TestSessionEndpoints:

    def test_list_sessions_returns_list(self, client):
        with patch("db.crud.list_sessions", new_callable=AsyncMock) as mock:
            mock.return_value = []
            r = client.get("/api/sessions")
            assert r.status_code == 200
            assert isinstance(r.json(), list)

    def test_get_active_session_404_when_none(self, client):
        with patch("db.crud.get_active_session", new_callable=AsyncMock) as mock:
            mock.return_value = None
            r = client.get("/api/sessions/active")
            assert r.status_code == 404

    def test_get_session_404_for_unknown_id(self, client):
        with patch("db.crud.get_session_by_id", new_callable=AsyncMock) as mock:
            mock.return_value = None
            r = client.get("/api/sessions/nonexistent-id")
            assert r.status_code == 404

    def test_create_session_201(self, client):
        fake_session = MagicMock()
        fake_session.session_id = "test-uuid-1234"
        fake_session.subject_name = "Computer Vision"
        fake_session.scheduled_start = "2026-09-26T09:00:00"
        fake_session.scheduled_end   = "2026-09-26T10:00:00"
        fake_session.is_active = True

        with patch("db.crud.create_session", new_callable=AsyncMock) as mock:
            mock.return_value = fake_session
            r = client.post("/api/sessions", json={
                "subject_name":    "Computer Vision",
                "scheduled_start": "2026-09-26T09:00:00",
                "scheduled_end":   "2026-09-26T10:00:00",
            })
            assert r.status_code == 201

    def test_pause_nonexistent_session_404(self, client):
        with patch("db.crud.get_session_by_id", new_callable=AsyncMock) as mock:
            mock.return_value = None
            r = client.patch("/api/sessions/bad-id/pause")
            assert r.status_code == 404

    def test_resume_nonexistent_session_404(self, client):
        with patch("db.crud.get_session_by_id", new_callable=AsyncMock) as mock:
            mock.return_value = None
            r = client.patch("/api/sessions/bad-id/resume")
            assert r.status_code == 404


# ---------------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------------
class TestStudentEndpoints:

    def test_list_students_returns_list(self, client):
        with patch("db.crud.list_students", new_callable=AsyncMock) as mock:
            mock.return_value = []
            r = client.get("/api/students")
            assert r.status_code == 200
            assert isinstance(r.json(), list)

    def test_get_student_404(self, client):
        with patch("db.crud.get_student", new_callable=AsyncMock) as mock:
            mock.return_value = None
            r = client.get("/api/students/9999")
            assert r.status_code == 404

    def test_search_students_404_when_no_results(self, client):
        with patch("db.crud.search_students", new_callable=AsyncMock) as mock:
            mock.return_value = []
            r = client.get("/api/students/search?q=xyznonexistent")
            assert r.status_code == 404

    def test_search_students_200_with_results(self, client):
        fake = MagicMock()
        fake.roll_no = 14
        fake.name = "Krushna"
        fake.class_div = "A"
        with patch("db.crud.search_students", new_callable=AsyncMock) as mock:
            mock.return_value = [fake]
            r = client.get("/api/students/search?q=Krushna")
            assert r.status_code == 200

    def test_student_score_404_when_student_missing(self, client):
        with patch("db.crud.get_student", new_callable=AsyncMock) as mock:
            mock.return_value = None
            r = client.get("/api/students/9999/score?session_id=abc")
            assert r.status_code == 404

    def test_student_score_404_when_no_active_session(self, client):
        fake_student = MagicMock()
        fake_student.roll_no = 14
        fake_student.name = "Krushna"
        with patch("db.crud.get_student", new_callable=AsyncMock) as ms:
            ms.return_value = fake_student
            with patch("db.crud.get_active_session", new_callable=AsyncMock) as ma:
                ma.return_value = None
                r = client.get("/api/students/14/score")
                assert r.status_code == 404


# ---------------------------------------------------------------------------
# Pipeline State
# ---------------------------------------------------------------------------
class TestPipelineState:
    def test_snapshot_returns_required_keys(self):
        from api.pipeline_state import PipelineState
        state = PipelineState()
        state.set_session("test-123")
        snap = state.snapshot()
        assert "session_id" in snap
        assert "class_attention_pct" in snap
        assert "faces" in snap
        assert "qa_window" in snap
        assert "alerts" in snap

    def test_alerts_cleared_after_snapshot(self):
        from api.pipeline_state import PipelineState
        state = PipelineState()
        state.add_alert("WRONG_STUDENT: Roll 7 vs Roll 14")
        snap = state.snapshot()
        assert len(snap["alerts"]) == 1
        snap2 = state.snapshot()
        assert len(snap2["alerts"]) == 0   # consumed

    def test_pause_reflected_in_snapshot(self):
        from api.pipeline_state import PipelineState
        state = PipelineState()
        state.set_paused(True)
        assert state.snapshot()["is_paused"] is True

    def test_face_update_reflected_in_snapshot(self):
        from api.pipeline_state import PipelineState, LiveFaceState
        state = PipelineState()
        faces = [LiveFaceState(roll_no=14, slot=0, h_i=0.8, g_i=1.0, p_i=0.9, a_i=0.92)]
        state.update_faces(faces, class_attention_pct=92.0)
        snap = state.snapshot()
        assert snap["face_count"] == 1
        assert snap["class_attention_pct"] == 92.0
        assert snap["faces"][0]["roll_no"] == 14

    def test_qa_window_state_in_snapshot(self):
        from api.pipeline_state import PipelineState, LiveQAState
        state = PipelineState()
        state.update_qa_window(LiveQAState(
            active=True, asked_roll=14, question_text="what is EAR?",
            seconds_remaining=8.3, speaker_roll=7, wrong_student=True
        ))
        snap = state.snapshot()
        qa = snap["qa_window"]
        assert qa["active"] is True
        assert qa["asked_roll"] == 14
        assert qa["wrong_student"] is True
        assert qa["speaker_roll"] == 7


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
class TestWebSocket:
    def test_ws_connects_successfully(self, client):
        with client.websocket_connect("/ws/test-session-id") as ws:
            # Just verify we can connect without error
            assert ws is not None
