from __future__ import annotations

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.freshrss]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "freshrss")


@pytest.mark.integration
def test_freshrss_local_and_docker_network(docker, ci_env) -> None:
    freshrss_dir = REPO_ROOT / "freshrss"
    port = ci_env["FRESHRSS_PORT"]
    base_url = f"http://127.0.0.1:{port}"

    try:
        ensure_infra_network()
        remove_path(freshrss_dir / "data")
        remove_path(freshrss_dir / "extensions")
        docker_compose("up", "-d", cwd=freshrss_dir)

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
        assert "FreshRSS" in local_response.text

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
            "http://freshrss:80/",
        )
        assert "FreshRSS" in container_result.stdout

        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "freshrss",
            "cli/do-install.php",
            f"--base-url={base_url}",
            "--default-user",
            "admin",
            "--language",
            "en",
            cwd=freshrss_dir,
        )
        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "--user",
            "www-data",
            "freshrss",
            "cli/create-user.php",
            "--user",
            "admin",
            f"--password={ci_env['FRESHRSS_ADMIN_PASSWORD']}",
            "--language",
            "en",
            cwd=freshrss_dir,
        )

        health = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "freshrss",
            "cli/health.php",
            cwd=freshrss_dir,
        )
        assert health.returncode == 0
    finally:
        docker_compose("down", cwd=freshrss_dir, check=False)
        remove_path(freshrss_dir / "data")
        remove_path(freshrss_dir / "extensions")
