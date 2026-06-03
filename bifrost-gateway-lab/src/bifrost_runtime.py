"""Start, probe, and stop the local Bifrost gateway.

Bifrost ships as a Go binary. The fastest way to launch it locally is
`npx -y @maximhq/bifrost`, which downloads the binary on first run and
caches it for subsequent runs. This module wraps that lifecycle behind
a tiny API so the Streamlit app can treat Bifrost as just another
service to wait for.
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import time
from typing import Optional

import httpx

from . import config
from .models import BifrostStatus

_proc: Optional[subprocess.Popen] = None

LOG_PATH = config.PROJECT_ROOT / "bifrost.log"


def _log_tail(max_lines: int = 40) -> Optional[str]:
    """Return the last few lines of bifrost.log, if it exists."""
    try:
        lines = LOG_PATH.read_text(errors="replace").splitlines()
    except OSError:
        return None
    if not lines:
        return None
    return "\n".join(lines[-max_lines:])


def _tool_version(tool: str) -> str:
    """Best-effort `<tool> --version`, for diagnostics."""
    path = shutil.which(tool)
    if path is None:
        return f"{tool}: not found on PATH"
    try:
        out = subprocess.run(
            [tool, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return f"{tool}: {(out.stdout or out.stderr).strip()} ({path})"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{tool}: found at {path} but `--version` failed: {exc}"


def diagnostics() -> str:
    """A human-readable snapshot of why autostart might be failing.

    Gathers the things you'd otherwise have to SSH in to check: the Node
    toolchain, the child process state, and the log file. Rendered in the
    UI when Bifrost is unreachable so hosted deploys are debuggable.
    """
    lines = [
        f"autostart: {config.BIFROST_AUTOSTART}",
        f"spawn cmd: npx -y @maximhq/bifrost --app-dir {config.PROJECT_ROOT} "
        f"--host {config.BIFROST_HOST} --port {config.BIFROST_PORT}",
        _tool_version("node"),
        _tool_version("npx"),
    ]

    if _proc is None:
        lines.append("child process: never spawned this session")
    elif _proc.poll() is None:
        lines.append(f"child process: running (pid {_proc.pid})")
    else:
        lines.append(f"child process: exited with code {_proc.returncode}")

    if not LOG_PATH.exists():
        lines.append("bifrost.log: not created (Bifrost was never launched)")
    else:
        size = LOG_PATH.stat().st_size
        if size == 0:
            lines.append("bifrost.log: exists but empty (no output yet)")
        else:
            lines.append(f"bifrost.log ({size} bytes), last lines:")
            lines.append(_log_tail() or "")

    return "\n".join(lines)


def status() -> BifrostStatus:
    """Probe the gateway and return a small status snapshot."""
    try:
        resp = httpx.get(config.BIFROST_BASE_URL + "/", timeout=2.0)
        return BifrostStatus(
            reachable=resp.status_code < 500,
            base_url=config.BIFROST_BASE_URL,
            detail=f"HTTP {resp.status_code}",
        )
    except httpx.HTTPError as exc:
        return BifrostStatus(
            reachable=False,
            base_url=config.BIFROST_BASE_URL,
            detail=str(exc),
            log_tail=_log_tail(),
        )


def _wait_until_ready(timeout_s: float = 60.0) -> bool:
    """Poll the gateway until it answers, or until we time out."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if status().reachable:
            return True
        time.sleep(1.0)
    return False


def ensure_running() -> BifrostStatus:
    """Make sure Bifrost is up. Start it as a subprocess if not.

    Returns the resulting status. Caller decides what to render.
    """
    current = status()
    if current.reachable:
        return current
    if not config.BIFROST_AUTOSTART:
        return current
    if shutil.which("npx") is None:
        return BifrostStatus(
            reachable=False,
            base_url=config.BIFROST_BASE_URL,
            detail="`npx` not found on PATH — install Node.js to autostart Bifrost.",
        )
    try:
        _spawn()
    except OSError as exc:
        return BifrostStatus(
            reachable=False,
            base_url=config.BIFROST_BASE_URL,
            detail=f"Failed to start Bifrost: {exc}",
        )
    if _wait_until_ready():
        return status()
    # Started but never answered. Surface why: if the child already
    # exited, report its code; otherwise it's still not listening.
    exited = _proc is not None and _proc.poll() is not None
    detail = (
        f"Bifrost process exited early (code {_proc.returncode})."
        if exited
        else "Bifrost did not become ready within 60s."
    )
    return BifrostStatus(
        reachable=False,
        base_url=config.BIFROST_BASE_URL,
        detail=detail,
        log_tail=_log_tail(),
    )


def _spawn() -> None:
    """Start `bifrost-http` as a child process if we haven't already."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        return
    # Bifrost reads config.json from --app-dir, so we point it at the
    # project root where we ship config.json. The provider keys come
    # from the parent process env (loaded from .env).
    cmd = [
        "npx",
        "-y",
        "@maximhq/bifrost",
        "--app-dir",
        str(config.PROJECT_ROOT),
        "--host",
        config.BIFROST_HOST,
        "--port",
        str(config.BIFROST_PORT),
    ]
    log_file = open(LOG_PATH, "ab", buffering=0)
    _proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        cwd=str(config.PROJECT_ROOT),
    )
    atexit.register(stop)


def stop() -> None:
    """Terminate the Bifrost subprocess, if we started one."""
    global _proc
    if _proc is None:
        return
    if _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None
