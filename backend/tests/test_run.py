import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from run_exec import write_submission
from run_limits import (
    MAX_CODE_CHARS,
    enforce_run_limits,
    reset_hits,
)


@pytest.fixture(autouse=True)
def _clear_run_quota():
    reset_hits()
    yield
    reset_hits()


class TestEnforceRunLimits:
    def test_rejects_unsupported_language(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            enforce_run_limits("alice", "print(1)", "bash")
        assert exc.value.status_code == 400

    def test_rejects_oversized_code(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            enforce_run_limits("alice", "x" * (MAX_CODE_CHARS + 1), "python")
        assert exc.value.status_code == 413

    def test_rate_limits_after_quota(self, monkeypatch):
        from fastapi import HTTPException

        import run_limits

        monkeypatch.setattr(run_limits, "RUN_RATE_LIMIT", 2)
        enforce_run_limits("alice", "print(1)", "python")
        enforce_run_limits("alice", "print(1)", "python")
        with pytest.raises(HTTPException) as exc:
            enforce_run_limits("alice", "print(1)", "python")
        assert exc.value.status_code == 429

    def test_quota_is_per_user(self, monkeypatch):
        import run_limits

        monkeypatch.setattr(run_limits, "RUN_RATE_LIMIT", 1)
        enforce_run_limits("alice", "print(1)", "python")
        enforce_run_limits("bob", "print(1)", "python")


class TestWriteSubmission:
    def test_python_without_tests_runs_main(self, tmp_path: Path):
        cmd = write_submission(str(tmp_path), "class Tensor: pass\n", "python")
        assert cmd == ["python", "-B", "main.py"]
        assert (tmp_path / "main.py").read_text() == "class Tensor: pass\n"
        assert not (tmp_path / "test.py").exists()

    def test_python_with_tests_runs_test_file(self, tmp_path: Path):
        cmd = write_submission(
            str(tmp_path),
            "class Tensor: pass\n",
            "python",
            "from main import Tensor\n\ndef test_ok():\n    assert Tensor\ntest_ok()\n",
        )
        assert cmd == ["python", "-B", "test.py"]
        assert "class Tensor" in (tmp_path / "main.py").read_text()
        assert "from main import Tensor" in (tmp_path / "test.py").read_text()

    def test_rust_concatenates_tests_into_main(self, tmp_path: Path):
        cmd = write_submission(str(tmp_path), "fn main() {}", "rust", "fn extra() {}")
        assert cmd[0] == "sh"
        source = (tmp_path / "main.rs").read_text()
        assert "fn main()" in source
        assert "fn extra()" in source


class TestRunEndpoint:
    def test_run_requires_auth(self, client: TestClient):
        response = client.post("/run", json={"code": "print(1)", "language": "python"})
        assert response.status_code == 401

    def test_run_rejects_large_payload(self, client: TestClient, auth_headers):
        response = client.post(
            "/run",
            json={"code": "x" * (MAX_CODE_CHARS + 1), "language": "python"},
            headers=auth_headers,
        )
        assert response.status_code == 413

    def test_run_rejects_unsupported_language(self, client: TestClient, auth_headers):
        response = client.post(
            "/run",
            json={"code": "echo hi", "language": "bash"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_run_rate_limit(self, client: TestClient, auth_headers, monkeypatch):
        import run_limits

        monkeypatch.setattr(run_limits, "RUN_RATE_LIMIT", 2)
        payload = {"code": "print(1)", "language": "python"}
        assert client.post("/run", json=payload, headers=auth_headers).status_code != 429
        assert client.post("/run", json=payload, headers=auth_headers).status_code != 429
        third = client.post("/run", json=payload, headers=auth_headers)
        assert third.status_code == 429

    def test_authenticated_run_reaches_executor(self, client: TestClient, auth_headers):
        response = client.post(
            "/run",
            json={"code": "print(1)", "language": "python"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "stdout" in body
        assert "stderr" in body
        assert "exit_code" in body

    def test_run_accepts_separate_test_code(self, client: TestClient, auth_headers):
        response = client.post(
            "/run",
            json={
                "code": "class Tensor:\n    pass\n",
                "test_code": "from main import Tensor\n",
                "language": "python",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_run_docker_security_and_resource_limits(
        self, client: TestClient, auth_headers, monkeypatch
    ):
        captured_cmd = []

        def fake_run(cmd, *args, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        response = client.post(
            "/run",
            json={"code": "print('secure')", "language": "python"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["exit_code"] == 0
        assert response.json()["stdout"] == "ok"

        # Check required isolation and resource flags
        assert "--network" in captured_cmd
        assert "none" in captured_cmd
        assert "--memory" in captured_cmd
        assert "512m" in captured_cmd
        assert "--cpus" in captured_cmd
        assert "1.0" in captured_cmd
        assert "--pids-limit" in captured_cmd
        assert "64" in captured_cmd
        assert "--security-opt" in captured_cmd
        assert "no-new-privileges" in captured_cmd
        assert "--stop-timeout" in captured_cmd
        assert "1" in captured_cmd
        assert "--name" in captured_cmd
        name_idx = captured_cmd.index("--name")
        container_name = captured_cmd[name_idx + 1]
        assert container_name.startswith("baselayer-run-")

    def test_run_timeout_kills_container(self, client: TestClient, auth_headers, monkeypatch):
        killed_containers = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[0] == "docker" and cmd[1] == "kill":
                killed_containers.append(cmd[2])
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

        monkeypatch.setattr(subprocess, "run", fake_run)
        response = client.post(
            "/run",
            json={"code": "while True: pass", "language": "python"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["exit_code"] == 124
        assert body["stderr"] == "Execution timed out"
        assert len(killed_containers) == 1
        assert killed_containers[0].startswith("baselayer-run-")

    def test_run_timeout_force_removes_container_when_kill_fails(
        self, client: TestClient, auth_headers, monkeypatch
    ):
        cleanup_calls = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[0] == "docker" and cmd[1] == "kill":
                cleanup_calls.append(("kill", cmd[2]))
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)
            if cmd[0] == "docker" and cmd[1] == "rm":
                cleanup_calls.append(("rm", cmd[-1]))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

        monkeypatch.setattr(subprocess, "run", fake_run)
        response = client.post(
            "/run",
            json={"code": "while True: pass", "language": "python"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["exit_code"] == 124
        assert body["stderr"] == "Execution timed out"
        assert [kind for kind, _ in cleanup_calls] == ["kill", "rm"]
        assert cleanup_calls[0][1] == cleanup_calls[1][1]
        assert cleanup_calls[0][1].startswith("baselayer-run-")

    def test_run_docker_daemon_failure_returns_exit_code_minus_one(
        self, client: TestClient, auth_headers, monkeypatch
    ):
        def fake_run(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="failed to connect to the docker API at unix:///Users/soto/.docker/run/docker.sock; check if the path is correct",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        response = client.post(
            "/run",
            json={"code": "print(1)", "language": "python"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["exit_code"] == -1
        assert "Docker sandbox is unavailable" in body["stderr"]
        assert "docker.sock" in body["stderr"]


def test_is_docker_daemon_failure():
    from sandbox_exec import is_docker_daemon_failure

    assert is_docker_daemon_failure(
        "failed to connect to the docker API at unix:///Users/soto/.docker/run/docker.sock"
    )
    assert is_docker_daemon_failure(
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
    )
    assert is_docker_daemon_failure("Is the docker daemon running?")
    assert is_docker_daemon_failure("Unable to find image 'sandbox-runner:latest' locally")
    assert not is_docker_daemon_failure("AssertionError: 2 != 3")
    assert not is_docker_daemon_failure("")
