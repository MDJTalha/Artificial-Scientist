from __future__ import annotations

import json
import subprocess

import pytest

from artificial_scientist.lab.engine import _execute_step_direct
from artificial_scientist.lab.execution_adapter import (
    DockerSandboxExecutionAdapter,
    ExecutionAdapterUnavailable,
)



def test_docker_adapter_rejects_non_allowlisted_callable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/docker")
    adapter = DockerSandboxExecutionAdapter("example/asds-sandbox:latest")
    with pytest.raises(ExecutionAdapterUnavailable, match="fixed lab worker"):
        adapter.execute(lambda *_: {}, ("statistics", {}), timeout_seconds=1)


def test_docker_adapter_builds_restricted_command(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/docker")
    captured = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            captured["input"] = input
            captured["timeout"] = timeout
            return json.dumps({"ok": True, "result": {"mean": 2}}).encode(), b""

        def poll(self):
            return self.returncode

        def kill(self):
            pass

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    adapter = DockerSandboxExecutionAdapter("example/asds-sandbox:latest")
    result = adapter.execute(
        _execute_step_direct,
        ("statistics", {"values": [1, 2, 3], "variance_mode": "population"}),
        timeout_seconds=3,
    )

    assert result == {"mean": 2}
    command = captured["command"]
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in command
    assert "no-new-privileges" in command
    assert "--pids-limit" in command
    assert "--memory" in command
    assert "--cpus" in command
    assert "--tmpfs" in command
    assert "--user" in command
    assert captured["timeout"] == 3
    payload = json.loads(captured["input"])
    assert payload["operation"] == "statistics"
    assert payload["inputs"]["values"] == [1, 2, 3]
