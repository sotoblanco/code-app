"""Shared sandbox code execution.

Single source of truth for the Docker/Modal commands that run learner code. Both
``POST /run`` (``main.run_code``) and internal course verification
(``course_import``) go through this module so the resource caps, network
isolation, and timed-out-container cleanup stay identical between the two
callers.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import uuid

from run_exec import write_submission


class SandboxUnavailableError(RuntimeError):
    """Raised when no code-execution backend can be reached at all.

    This is distinct from a code run that executed but *failed*: verification
    uses it to tell "the sandbox is down / Docker is missing / Modal is not
    deployed" apart from "the lesson did not pass its tests".
    """


def execute_docker(
    code: str,
    language: str = "python",
    test_code: str | None = None,
    timeout: int = 5,
) -> dict:
    """Run ``code`` in an isolated local Docker container (``sandbox-runner``).

    Mirrors the historical ``POST /run`` docker branch: resource caps, no
    network, and an explicit timed-out-container kill/remove so no container is
    ever left running on the daemon.

    Returns ``{"stdout", "stderr", "exit_code"}``. Raises
    :class:`SandboxUnavailableError` only when Docker itself cannot be started.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = write_submission(temp_dir, code, language, test_code)

            # Ensure temp dir is writable by container processes
            try:
                os.chmod(temp_dir, 0o777)
            except Exception:
                pass

            container_name = f"baselayer-run-{uuid.uuid4().hex[:12]}"
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--stop-timeout",
                "1",
                "--network",
                "none",
                "--memory",
                "512m",
                "--cpus",
                "1.0",
                "--pids-limit",
                "64",
                "--security-opt",
                "no-new-privileges",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                "-v",
                f"{temp_dir}:/app",
                "-w",
                "/app",
                "sandbox-runner",
            ] + cmd

            try:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                }
            except subprocess.TimeoutExpired:
                # SIGKILLing the `docker run` client does not stop the container
                # it started, so stop it explicitly. Fall back to a force-remove
                # so a timed-out or orphaned container is never left running.
                for cleanup_cmd in (
                    ["docker", "kill", container_name],
                    ["docker", "rm", "-f", container_name],
                ):
                    try:
                        cleanup_result = subprocess.run(
                            cleanup_cmd,
                            capture_output=True,
                            timeout=5,
                        )
                    except Exception:
                        continue
                    if cleanup_result.returncode == 0:
                        break
                return {"stdout": "", "stderr": "Execution timed out", "exit_code": 124}
            except FileNotFoundError as exc:
                raise SandboxUnavailableError(f"Executable not found: {exc}") from exc
            except Exception as exc:
                return {"stdout": "", "stderr": str(exc), "exit_code": -1}
    except Exception as exc:
        return {"stdout": "", "stderr": str(exc), "exit_code": -1}


def execute_in_sandbox(
    code: str,
    language: str = "python",
    test_code: str | None = None,
    timeout: int = 5,
) -> dict:
    """Run code through whatever backend ``POST /run`` would use.

    Honors ``EXECUTION_ENV`` (``docker`` default, ``modal`` for the remote
    sandbox used in Compose/production). Raises :class:`SandboxUnavailableError`
    when the configured backend cannot run at all.
    """
    execution_env = os.environ.get("EXECUTION_ENV", "docker")
    if execution_env == "modal":
        try:
            from modal_app import run_in_sandbox
        except ImportError as exc:
            raise SandboxUnavailableError("Modal backend not found") from exc
        try:
            return run_in_sandbox.remote(code, language, test_code or "")
        except Exception as exc:
            raise SandboxUnavailableError(str(exc)) from exc
    return execute_docker(code, language, test_code, timeout=timeout)
