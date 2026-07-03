from __future__ import annotations

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.beszel]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "beszel")


@pytest.mark.integration
def test_beszel_local_and_docker_network(docker, ci_env) -> None:
    beszel_dir = REPO_ROOT / "beszel"
    port = ci_env["BESZEL_PORT"]
    base_url = f"http://127.0.0.1:{port}"

    try:
        ensure_infra_network()
        remove_path(beszel_dir / "data")
        docker_compose("up", "-d", "--wait", cwd=beszel_dir)

        run(
            "curl",
            "-fsS",
            "--retry",
            "15",
            "--retry-delay",
            "2",
            "--retry-all-errors",
            f"{base_url}/",
        )

        local_response = requests.get(f"{base_url}/", timeout=30)
        local_response.raise_for_status()
        assert "Beszel" in local_response.text

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
            "http://beszel:8090/",
        )
        assert "Beszel" in container_result.stdout

        health = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "beszel",
            "/beszel",
            "health",
            "--url",
            "http://localhost:8090",
            cwd=beszel_dir,
        )
        assert health.returncode == 0
    finally:
        docker_compose("down", cwd=beszel_dir, check=False)
        remove_path(beszel_dir / "data")
        remove_path(beszel_dir / "beszel_socket")
        remove_path(beszel_dir / "beszel_agent_data")
