"""E2B sandbox execution for test_runner agent."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from models.platform import PlatformService
from services.secrets import decrypt_secrets


def _get_e2b_api_key(db: Session) -> str | None:
    service = db.query(PlatformService).filter(PlatformService.service_key == "e2b").first()
    if not service or not service.is_enabled or not service.encrypted_config_ref:
        return None
    return decrypt_secrets(service.encrypted_config_ref).get("api_key")


def run_tests_in_sandbox(
    db: Session,
    *,
    test_files: list[dict[str, str]],
    stack_hint: str,
) -> dict[str, Any]:
    api_key = _get_e2b_api_key(db)
    if not api_key:
        return {
            "passed": False,
            "total": 0,
            "passed_count": 0,
            "failed_count": 0,
            "failures": [],
            "summary": "E2B sandbox not configured. Enable E2B under Admin → AI Services.",
            "sandbox": False,
        }

    try:
        from e2b_code_interpreter import Sandbox
    except ImportError:
        return {
            "passed": False,
            "summary": "e2b-code-interpreter package not installed",
            "sandbox": False,
        }

    code_parts = [
        "import json, subprocess, os, sys",
        "os.makedirs('/workspace', exist_ok=True)",
    ]
    for tf in test_files:
        path = tf.get("path", "test_sample.py").lstrip("/")
        content = tf.get("content", "def test_placeholder():\n    assert True")
        safe = json.dumps(content)
        code_parts.append(f"open('/workspace/{path}', 'w').write({safe})")

    if "python" in stack_hint.lower() or "fastapi" in stack_hint.lower():
        code_parts.append(
            "result = subprocess.run(['python', '-m', 'pytest', '/workspace', '-q'], "
            "capture_output=True, text=True, timeout=120)"
        )
    else:
        code_parts.append(
            "result = subprocess.run(['node', '--test'], cwd='/workspace', "
            "capture_output=True, text=True, timeout=120)"
        )
    code_parts.append(
        "print(json.dumps({'stdout': result.stdout[-4000:], 'stderr': result.stderr[-2000:], "
        "'returncode': result.returncode}))"
    )

    with Sandbox(api_key=api_key) as sandbox:
        execution = sandbox.run_code("\n".join(code_parts))
        output = ""
        if execution.logs.stdout:
            output = "\n".join(execution.logs.stdout)
        try:
            payload = json.loads(output.strip().splitlines()[-1])
            passed = int(payload.get("returncode", 1)) == 0
            return {
                "passed": passed,
                "total": len(test_files) or 1,
                "passed_count": len(test_files) if passed else 0,
                "failed_count": 0 if passed else len(test_files) or 1,
                "failures": [] if passed else [{"detail": payload.get("stderr", "tests failed")}],
                "summary": "E2B sandbox tests passed" if passed else "E2B sandbox tests failed",
                "sandbox": True,
                "stdout": payload.get("stdout", "")[:2000],
            }
        except Exception:
            return {
                "passed": False,
                "summary": f"E2B execution completed with output: {output[:500]}",
                "sandbox": True,
            }
