from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("mcp.server.fastmcp")

from design_research_problems.problems._domains import build123d_mcp_server as backend


def _ctx_with_state(state: backend._BackendState) -> Any:
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state))


def test_backend_status_reports_backend_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend, "build123d_available", lambda: False)
    monkeypatch.setattr(backend, "build123d_version", lambda: None)

    payload = backend.backend_status()
    assert payload == {
        "backend": "build123d",
        "available": False,
        "version": None,
        "install_hint": "pip install design-research-problems[cad]",
    }

    no_hint = backend.backend_status(include_install_hint=False)
    assert "install_hint" not in no_hint


def test_backend_state_accessor_returns_lifespan_state() -> None:
    state = backend._BackendState(last_script_result={"a": 1})
    assert backend._backend_state(_ctx_with_state(state)) is state


def test_evaluate_and_describe_last_script_result_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    state = backend._BackendState()
    ctx = _ctx_with_state(state)

    monkeypatch.setattr(
        backend,
        "evaluate_scripted_part",
        lambda script, result_name="result": {
            "backend": "build123d",
            "result_name": result_name,
            "script": script,
            "volume_mm3": 42.0,
        },
    )

    payload = backend.evaluate_scripted_part_tool(
        ctx,
        script="result = shape",
        result_name="final_shape",
        include_script=False,
    )
    assert payload["result_name"] == "final_shape"
    assert "script" not in payload
    assert state.last_script_result is not None

    with_script = backend.describe_last_script_result(ctx, include_script=True)
    assert with_script["script"] == "result = shape"

    without_script = backend.describe_last_script_result(ctx, include_script=False)
    assert "script" not in without_script


def test_describe_last_script_result_requires_prior_evaluation() -> None:
    ctx = _ctx_with_state(backend._BackendState())
    with pytest.raises(ValueError, match="No script has been evaluated yet"):
        backend.describe_last_script_result(ctx)


def test_main_runs_server_over_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def _fake_run(*, transport: str) -> None:
        called["transport"] = transport

    monkeypatch.setattr(backend.SERVER, "run", _fake_run)
    backend.main()
    assert called["transport"] == "stdio"
