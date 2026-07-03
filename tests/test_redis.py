from __future__ import annotations

import pytest

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.redis]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "redis")


@pytest.mark.integration
def test_redis_local_and_docker_network(docker, ci_env) -> None:
    redis_dir = REPO_ROOT / "redis"
    password = ci_env["REDIS_PASSWORD"]
    port = ci_env["REDIS_PORT"]

    try:
        ensure_infra_network()
        remove_path(redis_dir / "data")
        docker_compose("up", "-d", "--wait", cwd=redis_dir)

        local_ping = run(
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "redis:7.4.2-alpine",
            "redis-cli",
            "-h",
            "127.0.0.1",
            "-p",
            port,
            "-a",
            password,
            "ping",
        )
        assert local_ping.stdout.strip() == "PONG"

        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "redis",
            "redis-cli",
            "-a",
            password,
            "SET",
            "infra:test",
            "ok",
            cwd=redis_dir,
        )

        network_get = run(
            "docker",
            "run",
            "--rm",
            "--network",
            "infra",
            "redis:7.4.2-alpine",
            "redis-cli",
            "-h",
            "redis",
            "-a",
            password,
            "GET",
            "infra:test",
        )
        assert network_get.stdout.strip() == "ok"

        info = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "redis",
            "redis-cli",
            "-a",
            password,
            "INFO",
            "persistence",
            cwd=redis_dir,
        )
        assert "aof_enabled:1" in info.stdout
    finally:
        docker_compose("down", cwd=redis_dir, check=False)
        remove_path(redis_dir / "data")
