from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e_helpers import build_cli_env, make_session_log, spawn_cli


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def e2e_env(tmp_path: Path) -> dict[str, str]:
    return build_cli_env(tmp_path)


@pytest.fixture
def session_log(tmp_path: Path):
    log = make_session_log(tmp_path)
    yield log
    log.close()


@pytest.fixture
def cli_process(repo_root: Path, e2e_env: dict[str, str], session_log):
    child = spawn_cli(env=e2e_env, cwd=repo_root, logfile=session_log.tee)
    yield child, session_log
    if child.isalive():
        # 테스트 종료 시 프로세스를 정리한다.
        child.terminate(force=True)
