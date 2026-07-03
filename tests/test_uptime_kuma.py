from __future__ import annotations

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.uptime_kuma]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "uptime-kuma")


@pytest.mark.integration
def test_uptime_kuma_local_and_docker_network(docker, ci_env) -> None:
    uptime_kuma_dir = REPO_ROOT / "uptime-kuma"
    port = ci_env["UPTIME_KUMA_PORT"]
    base_url = f"http://127.0.0.1:{port}"

    try:
        ensure_infra_network()
        remove_path(uptime_kuma_dir / "data")
        docker_compose("up", "-d", "--wait", cwd=uptime_kuma_dir)

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
        assert "Uptime Kuma" in local_response.text

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
            "http://uptime-kuma:3001/",
        )
        assert "Uptime Kuma" in container_result.stdout

        health = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "uptime-kuma",
            "extra/healthcheck",
            cwd=uptime_kuma_dir,
        )
        assert health.returncode == 0
    finally:
        docker_compose("down", cwd=uptime_kuma_dir, check=False)
        remove_path(uptime_kuma_dir / "data")
