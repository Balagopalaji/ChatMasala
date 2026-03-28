"""Browser-level smoke coverage for the workspace-first UI."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e


def _free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    except PermissionError:
        pytest.skip("Loopback sockets are not available in this environment")
    finally:
        sock.close()
    return port


def _wait_for_server(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Timed out waiting for uvicorn server")


def test_create_workspace_and_send_human_message(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")

    repo_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "e2e.db"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env.pop("CHATMASALA_RESET_DB_ON_STARTUP", None)

    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_server(base_url)

        try:
            with sync_api.sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(base_url)

                page.get_by_role("button", name="New Workspace").first.click()
                page.wait_for_url("**/workspaces/*")

                panel = page.locator(".chat-panel").first
                panel.get_by_role("button", name="Human input").click()
                panel.locator("textarea[name='content']").fill("hello from e2e")
                panel.get_by_role("button", name="Send").click()

                panel.locator(".chat-msg-bubble").filter(has_text="hello from e2e").wait_for(timeout=5000)
                browser.close()
        except Exception as exc:
            if "Executable doesn't exist" in str(exc):
                pytest.skip("Playwright browser is not installed; run `python -m playwright install chromium`")
            raise
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
