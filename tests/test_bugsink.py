from __future__ import annotations

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.bugsink]


def test_docker_compose_config(docker, ci_env) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "bugsink")


@pytest.mark.integration
def test_bugsink_local_and_docker_network(docker, ci_env) -> None:
    postgres_compose = REPO_ROOT / "postgres/docker-compose.yml"
    bugsink_dir = REPO_ROOT / "bugsink"
    postgres_dir = REPO_ROOT / "postgres"
    port = ci_env["BUGSINK_PORT"]
    base_url = f"http://127.0.0.1:{port}"
    postgres_user = ci_env["POSTGRES_USER"]

    try:
        ensure_infra_network()
        remove_path(postgres_dir / "data")
        docker_compose(
            "up",
            "-d",
            "--wait",
            compose_file=postgres_compose,
            env={"POSTGRES_PORT": "15432"},
        )

        run(
            "docker",
            "compose",
            "-f",
            str(postgres_compose),
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            postgres_user,
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            "postgres",
            "-c",
            "CREATE DATABASE bugsink",
        )

        docker_compose("up", "-d", "--wait", cwd=bugsink_dir)

        run(
            "curl",
            "-fsS",
            "--retry",
            "15",
            "--retry-delay",
            "2",
            "--retry-all-errors",
            f"{base_url}/health/ready",
        )

        ready_response = requests.get(f"{base_url}/health/ready", timeout=30)
        ready_response.raise_for_status()

        local_response = requests.get(f"{base_url}/", timeout=30)
        local_response.raise_for_status()
        assert "Bugsink" in local_response.text

        container_result = run(
            "docker",
            "run",
            "--rm",
            "--network",
            "infra",
            "curlimages/curl:8.12.1",
            "-fsSL",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--retry-all-errors",
            "http://bugsink:8000/health/ready",
        )
        assert container_result.returncode == 0
    finally:
        docker_compose("down", cwd=bugsink_dir, check=False)
        docker_compose("down", compose_file=postgres_compose, check=False)
        remove_path(postgres_dir / "data")
