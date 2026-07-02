from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CI_ENV: dict[str, str] = {
    "PROXY_USER": "proxy",
    "PROXY_PASSWORD": "ci-test-password",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "ci-test-password",
    "POSTGRES_PORT": "5432",
    "INIT_HOST": "127.0.0.1",
    "INIT_USERNAME": "admin",
    "INIT_PASSWORD": "ci-test-password",
    "WG_EASY_WEB_PORT": "51821",
    "WG_EASY_WG_PORT": "51820",
    "STATIC_WEB_PORT": "8080",
    "CADDY_BIND_ADDRESS": "127.0.0.1",
}


def run(
    *args: str,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.update(CI_ENV)
    if env:
        merged_env.update(env)
    return subprocess.run(
        list(args),
        cwd=cwd or REPO_ROOT,
        env=merged_env,
        check=check,
        capture_output=True,
        text=True,
    )


def docker_compose(
    *args: str,
    compose_file: Path | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose"]
    if compose_file is not None:
        cmd.extend(["-f", str(compose_file)])
    cmd.extend(args)
    return run(*cmd, cwd=cwd, env=env, check=check)


def ensure_infra_network() -> None:
    run("docker", "network", "create", "infra", check=False)


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except PermissionError:
        run("sudo", "rm", "-rf", str(path), check=False)
