from __future__ import annotations

import shutil

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, run

pytestmark = [pytest.mark.static_web]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "static-web")


@pytest.mark.integration
def test_static_web_local_and_docker_network(docker, ci_env) -> None:
    static_web_dir = REPO_ROOT / "static-web"
    index_html = static_web_dir / "public/index.html"
    index_example = static_web_dir / "public/index.html.example"
    port = ci_env["STATIC_WEB_PORT"]

    try:
        ensure_infra_network()
        shutil.copy(index_example, index_html)
        docker_compose("up", "-d", "--wait", cwd=static_web_dir)

        local_response = requests.get(f"http://127.0.0.1:{port}/", timeout=30)
        local_response.raise_for_status()
        assert "Static Web" in local_response.text

        container_result = run(
            "docker",
            "run",
            "--rm",
            "--network",
            "infra",
            "curlimages/curl:8.12.1",
            "-fsS",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--retry-all-errors",
            "http://static-web:80/",
        )
        assert "Static Web" in container_result.stdout
    finally:
        docker_compose("down", cwd=static_web_dir, check=False)
