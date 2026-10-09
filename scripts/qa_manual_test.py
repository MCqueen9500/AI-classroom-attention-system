"""
qa_manual_test.py
==================
Manually triggers the Q&A window on the dashboard and logs it to DB.
Bypasses mic + Ollama entirely — pure API calls.

Usage:
    .\.venv\Scripts\python.exe scripts\qa_manual_test.py
    .\.venv\Scripts\python.exe scripts\qa_manual_test.py --roll 56 --timeout
"""

import argparse
import requests
import time
import sys

API = "http://localhost:8000/api"


def check_server():
    try:
        r = requests.get(f"{API}/sessions/active", timeout=3)
        if r.status_code == 200:
            return r.json()["session_id"]
        print("ERROR: No active session. Create one on the dashboard first.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Server not reachable — {e}")
        print("Run: .\\run_app.bat")
        sys.exit(1)


def push_qa_state(active, roll, question, seconds, speaker=None, wrong=False):
    """Push Q&A state to pipeline_state → dashboard sees it immediately via WS."""
    r = requests.post(f"{API}/telemetry/audio", json={
        "qa_active":      active,
        "qa_asked_roll":  roll,
        "qa_question":    question,
        "qa_seconds":     seconds,
        "qa_speaker":     speaker,
        "qa_wrong":       wrong,
    }, timeout=3)
    return r.status_code


def log_qa_to_db(session_id, roll, question, score, responded, interrupted=False):
    """Write final Q&A result to database via a dedicated endpoint."""
    r = requests.post(f"{API}/telemetry/qa_log", json={
        "session_id":         session_id,
        "roll_no":            roll,
        "question_text":      question,
        "qa_score":           score,
        "student_responded":  responded,
        "teacher_interrupted": interrupted,
    }, timeout=3)
    return r.status_code, r.text


def check_db(session_id, roll):
    r = requests.get(f"{API}/sessions/{session_id}/qa", timeout=3)
    if r.status_code == 200:
        all_qa = r.json()
        mine = [i for i in all_qa if i["roll_no"] == roll]
        if mine:
            latest = mine[-1]
            print(f"  DB record: Q_i={latest['qa_score']} | responded={latest['student_responded']}")
        else:
            print(f"  No DB record for Roll {roll} yet.")
    else:
        print(f"  DB check failed: {r.status_code}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--roll",     type=int,   default=56)
    p.add_argument("--question", type=str,   default="What is the formula for instantaneous attention score?")
    p.add_argument("--score",    type=float, default=0.9,  help="Answer quality 0.0-1.0")
    p.add_argument("--timeout",  action="store_true",      help="Simulate student NOT answering")
    args = p.parse_args()

    print("=" * 55)
    print("  ClassMon Q&A Pipeline Test")
    print("=" * 55)
    session_id = check_server()
    print(f"  Session : {session_id[:8]}...")
    print(f"  Asking  : Roll {args.roll}")
    print(f"  Question: {args.question[:60]}...")
    print()

    # Step 1: Open Q&A window on dashboard
    print("[1/3] Opening Q&A window on dashboard...")
    code = push_qa_state(True, args.roll, args.question, 15.0)
    print(f"      Status {code} — check right sidebar on dashboard NOW!")
    print()

    # Step 2: Countdown (simulated)
    wait = 15 if args.timeout else 5
    print(f"[2/3] {'Simulating NO answer (15s timeout)' if args.timeout else 'Simulating answer in 5 seconds'}...")
    for i in range(wait, 0, -1):
        print(f"      {i}s remaining...", end="\r")
        # Update countdown on dashboard
        push_qa_state(True, args.roll, args.question, float(i))
        time.sleep(1)

    # Close Q&A window on dashboard
    push_qa_state(False, None, None, 0.0)
    print()

    # Step 3: Log to DB
    score      = 0.0 if args.timeout else args.score
    responded  = not args.timeout
    print(f"[3/3] Logging result to DB — Q_i={score}, responded={responded}")
    code, body = log_qa_to_db(session_id, args.roll, args.question, score, responded)
    if code == 200:
        print(f"      Logged OK!")
    else:
        print(f"      Endpoint returned {code}: {body[:150]}")
        print("      (Q&A log endpoint may need to be added — see output)")

    print()
    check_db(session_id, args.roll)
    print()
    print("  Done! Check Analytics page to see updated Q_i score.")
    print("=" * 55)
