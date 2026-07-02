from __future__ import annotations

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.wg_easy]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "wg-easy")


@pytest.mark.integration
def test_wg_easy_web_ui_and_wireguard(docker, ci_env) -> None:
    wg_easy_dir = REPO_ROOT / "wg-easy"
    web_port = ci_env["WG_EASY_WEB_PORT"]
    base_url = f"http://127.0.0.1:{web_port}"

    try:
        ensure_infra_network()
        docker_compose("up", "-d", "--wait", cwd=wg_easy_dir)

        response = requests.get(
            f"{base_url}/",
            timeout=30,
        )
        response.raise_for_status()

        session_response = requests.post(
            f"{base_url}/api/session",
            headers={"Content-Type": "application/json"},
            json={
                "username": ci_env["INIT_USERNAME"],
                "password": ci_env["INIT_PASSWORD"],
                "remember": False,
            },
            timeout=30,
        )
        session_response.raise_for_status()
        assert session_response.json()["status"] == "success"

        wg_show = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "wg-easy",
            "wg",
            "show",
            cwd=wg_easy_dir,
        )
        assert "interface: wg0" in wg_show.stdout
        assert "listening port:" in wg_show.stdout

        inspect = run(
            "docker",
            "inspect",
            "--format",
            '{{range .Mounts}}{{if eq .Destination "/etc/wireguard"}}{{.Source}}{{end}}{{end}}',
            "wg-easy",
        )
        data_dir = inspect.stdout.strip()
        assert data_dir
        assert "wg-easy/data" in data_dir
    finally:
        docker_compose("down", cwd=wg_easy_dir, check=False)
        remove_path(wg_easy_dir / "data")
