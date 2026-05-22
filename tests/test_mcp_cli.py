from __future__ import annotations

from typing import Any

import pytest

from design_research_problems import MissingOptionalDependencyError
from design_research_problems import mcp as mcp_cli


class _FakeServer:
    def __init__(self) -> None:
        self.transport: str | None = None

    def run(self, *, transport: str) -> None:
        self.transport = transport


class _FakeProblem:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def to_mcp_server(self, *, server_name: str | None = None, include_citation: bool = True) -> _FakeServer:
        self.calls.append({"server_name": server_name, "include_citation": include_citation})
        return _FakeServer()


def test_build_parser_accepts_notebook_friendly_options() -> None:
    args = mcp_cli.build_parser().parse_args(("pill_capsule_min_area", "--server-name", "drp_problem", "--no-citation"))

    assert args.problem_id == "pill_capsule_min_area"
    assert args.server_name == "drp_problem"
    assert args.no_citation is True
    assert args.transport == "stdio"


def test_create_problem_server_loads_problem_and_forwards_server_options(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_problem = _FakeProblem()
    monkeypatch.setattr(mcp_cli, "get_problem", lambda problem_id: fake_problem)

    server = mcp_cli.create_problem_server(
        "pill_capsule_min_area",
        server_name="drp_problem",
        include_citation=False,
    )

    assert isinstance(server, _FakeServer)
    assert fake_problem.calls == [{"server_name": "drp_problem", "include_citation": False}]


def test_main_runs_created_server(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = _FakeServer()

    def create_problem_server(problem_id: str, **kwargs: Any) -> _FakeServer:
        assert problem_id == "pill_capsule_min_area"
        assert kwargs == {"server_name": None, "include_citation": False}
        return fake_server

    monkeypatch.setattr(mcp_cli, "create_problem_server", create_problem_server)

    assert mcp_cli.main(("pill_capsule_min_area", "--no-citation")) == 0
    assert fake_server.transport == "stdio"


def test_main_reports_missing_mcp_extra(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def create_problem_server(problem_id: str, **kwargs: Any) -> _FakeServer:
        raise MissingOptionalDependencyError("missing mcp")

    monkeypatch.setattr(mcp_cli, "create_problem_server", create_problem_server)

    with pytest.raises(SystemExit) as exc_info:
        mcp_cli.main(("pill_capsule_min_area",))

    assert exc_info.value.code == 2
    assert "design-research-problems[mcp]" in capsys.readouterr().err
