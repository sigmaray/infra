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
    "FRESHRSS_PORT": "8081",
    "FRESHRSS_ADMIN_PASSWORD": "ci-test-password",
    "REDIS_PASSWORD": "ci-test-password",
    "REDIS_PORT": "6380",
    "UPTIME_KUMA_PORT": "18083",
    "BESZEL_PORT": "18090",
    "BESZEL_APP_URL": "http://127.0.0.1:18090",
    "PORTAINER_HTTPS_PORT": "19443",
    "BUGSINK_PORT": "18000",
    "BUGSINK_SECRET_KEY": "ci-test-secret-key-at-least-fifty-characters-long-here",
    "BUGSINK_CREATE_SUPERUSER": "admin@example.org:ci-test-password",
    "BUGSINK_DATABASE_URL": "postgresql://postgres:ci-test-password@postgresql:5432/bugsink",
    "BUGSINK_BASE_URL": "http://127.0.0.1:18000",
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
        parent = path.parent
        run(
            "docker",
            "run",
            "--rm",
            "-v",
            f"{parent}:/target",
            "alpine:3.21",
            "sh",
            "-c",
            f"rm -rf /target/{path.name}",
            check=False,
        )
