"""
run_server.py
=============
Master API server launcher for ClassMon.

REPAIR 1: Kills any zombie process holding port 8000 BEFORE starting
uvicorn. Runs uvicorn synchronously on the MAIN thread so that
Ctrl+C and SIGTERM trigger a graceful shutdown and the OS socket
is released cleanly — eliminating the zombie port 8000 problem.

Usage:
    python run_server.py
    CLASSMON_API_URL=https://your-render-url.onrender.com python run_server.py
"""

import logging
import os
import sys
import time

# ── Ensure backend is importable ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_server")


# ── REPAIR 1: Zombie port killer ──────────────────────────────────────────────

def kill_port(port: int) -> None:
    """
    Scan all listening TCP sockets and terminate any process
    that is occupying the given port.  Wraps psutil safely so
    a missing psutil or already-dead process never crashes startup.
    """
    try:
        import psutil
    except ImportError:
        logger.warning("psutil not installed — skipping zombie port check. "
                       "Run: pip install psutil")
        return

    killed = False
    try:
        for conn in psutil.net_connections(kind="inet"):
            if (
                conn.laddr
                and conn.laddr.port == port
                and conn.status == psutil.CONN_LISTEN
                and conn.pid
            ):
                try:
                    proc = psutil.Process(conn.pid)
                    logger.warning(
                        "🧹 Killing zombie PID %d (%s) holding port %d",
                        conn.pid, proc.name(), port,
                    )
                    proc.terminate()
                    killed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug("Could not kill PID %d: %s", conn.pid, e)
    except Exception as e:
        logger.warning("Port scan failed (non-fatal): %s", e)

    if killed:
        logger.info("Waiting 1.5s for socket to be released...")
        time.sleep(1.5)
    else:
        logger.info("Port %d is clear — no zombie processes found.", port)


# ── Main entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    import uvicorn

    port = int(os.getenv("PORT", 8000))

    print("=" * 62)
    print("  ClassMon API Server")
    print("=" * 62)
    print(f"  Port     : {port}")
    print(f"  API Base : {os.getenv('CLASSMON_API_URL', f'http://localhost:{port}')}")
    print("=" * 62)

    # Kill zombie before binding
    kill_port(port)

    # Run synchronously on main thread — clean shutdown on Ctrl+C / SIGTERM
    logger.info("Starting uvicorn on 0.0.0.0:%d (synchronous / main thread)", port)
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        app_dir=os.path.join(ROOT, "backend"),
    )


if __name__ == "__main__":
    main()
