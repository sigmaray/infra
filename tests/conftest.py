from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from helpers import CI_ENV, REPO_ROOT, run

pytestmark: list[pytest.MarkDecorator] = []


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def ci_env() -> dict[str, str]:
    return CI_ENV.copy()


@pytest.fixture(scope="session")
def docker() -> None:
    try:
        run("docker", "info")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("Docker is not available")


@pytest.fixture(scope="session")
def shellcheck() -> None:
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck is not installed")
