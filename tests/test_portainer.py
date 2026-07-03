from __future__ import annotations

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [
    pytest.mark.portainer,
    pytest.mark.filterwarnings("ignore::urllib3.exceptions.InsecureRequestWarning"),
]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "portainer")


@pytest.mark.integration
def test_portainer_local_and_docker_network(docker, ci_env) -> None:
    portainer_dir = REPO_ROOT / "portainer"
    https_port = ci_env["PORTAINER_HTTPS_PORT"]
    https_url = f"https://127.0.0.1:{https_port}"

    try:
        ensure_infra_network()
        remove_path(portainer_dir / "data")
        docker_compose("up", "-d", cwd=portainer_dir)

        run(
            "curl",
            "-kfsS",
            "--retry",
            "15",
            "--retry-delay",
            "2",
            "--retry-all-errors",
            f"{https_url}/api/status",
        )

        status_response = requests.get(f"{https_url}/api/status", verify=False, timeout=30)
        status_response.raise_for_status()
        status = status_response.json()
        assert status["Version"]
        assert status["InstanceID"]

        ui_response = requests.get(f"{https_url}/", verify=False, timeout=30)
        ui_response.raise_for_status()
        assert "Portainer" in ui_response.text

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
            "http://portainer:9000/api/status",
        )
        assert '"Version"' in container_result.stdout
    finally:
        docker_compose("down", cwd=portainer_dir, check=False)
        remove_path(portainer_dir / "data")
