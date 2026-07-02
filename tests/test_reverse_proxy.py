from __future__ import annotations

import shutil

import pytest
import requests

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.reverse_proxy]


def test_docker_compose_config(docker) -> None:
    reverse_proxy_dir = REPO_ROOT / "reverse-proxy"
    env_file = reverse_proxy_dir / ".env"
    env_example = reverse_proxy_dir / ".env.example"

    shutil.copy(env_example, env_file)
    try:
        docker_compose("config", "--quiet", cwd=reverse_proxy_dir)
    finally:
        env_file.unlink(missing_ok=True)


def test_docker_compose_config_local_bind(docker) -> None:
    reverse_proxy_dir = REPO_ROOT / "reverse-proxy"
    env_file = reverse_proxy_dir / ".env"
    env_example = reverse_proxy_dir / ".env.example"

    shutil.copy(env_example, env_file)
    try:
        docker_compose(
            "config",
            "--quiet",
            cwd=reverse_proxy_dir,
            env={"CADDY_BIND_ADDRESS": "127.0.0.1"},
        )
    finally:
        env_file.unlink(missing_ok=True)


def test_caddyfile_validation(docker) -> None:
    reverse_proxy_dir = REPO_ROOT / "reverse-proxy"
    env_file = reverse_proxy_dir / ".env"
    caddyfile = reverse_proxy_dir / "Caddyfile"

    shutil.copy(reverse_proxy_dir / ".env.example", env_file)
    shutil.copy(reverse_proxy_dir / "Caddyfile.example", caddyfile)
    try:
        run(
            "docker",
            "run",
            "--rm",
            "-v",
            f"{caddyfile}:/etc/caddy/Caddyfile:ro",
            "--env-file",
            str(env_file),
            "caddy:2.10.0-alpine",
            "caddy",
            "validate",
            "--config",
            "/etc/caddy/Caddyfile",
        )
    finally:
        env_file.unlink(missing_ok=True)
        caddyfile.unlink(missing_ok=True)


@pytest.mark.integration
def test_reverse_proxy_routing_and_upstream_proxy(docker, ci_env) -> None:
    proxy_compose = REPO_ROOT / "3proxy/docker-compose.yml"
    wg_easy_compose = REPO_ROOT / "wg-easy/docker-compose.yml"
    static_web_compose = REPO_ROOT / "static-web/docker-compose.yml"
    reverse_proxy_compose = REPO_ROOT / "reverse-proxy/docker-compose.yml"
    reverse_proxy_dir = REPO_ROOT / "reverse-proxy"
    static_web_dir = REPO_ROOT / "static-web"
    wg_easy_dir = REPO_ROOT / "wg-easy"

    proxy_user = ci_env["PROXY_USER"]
    proxy_password = ci_env["PROXY_PASSWORD"]
    http_proxy = f"http://{proxy_user}:{proxy_password}@127.0.0.1:3128"
    socks_proxy = f"{proxy_user}:{proxy_password}@127.0.0.1:1080"

    try:
        ensure_infra_network()

        run("./scripts/generate-3proxy-cfg.sh", cwd=REPO_ROOT / "3proxy")
        docker_compose("up", "-d", "--wait", compose_file=proxy_compose)
        docker_compose("up", "-d", "--wait", compose_file=wg_easy_compose)

        shutil.copy(
            static_web_dir / "public/index.html.example",
            static_web_dir / "public/index.html",
        )
        docker_compose("up", "-d", "--wait", compose_file=static_web_compose)

        shutil.copy(reverse_proxy_dir / ".env.example", reverse_proxy_dir / ".env")
        shutil.copy(reverse_proxy_dir / "Caddyfile.example", reverse_proxy_dir / "Caddyfile")
        docker_compose("up", "-d", "--wait", compose_file=reverse_proxy_compose)

        wg_response = requests.get(
            "http://127.0.0.1/",
            headers={"Host": "wg.infra.local"},
            timeout=30,
        )
        wg_response.raise_for_status()

        static_response = requests.get(
            "http://127.0.0.1/",
            headers={"Host": "static.infra.local"},
            timeout=30,
        )
        static_response.raise_for_status()
        assert "Static Web" in static_response.text

        session_response = requests.post(
            "http://127.0.0.1/api/session",
            headers={
                "Host": "wg.infra.local",
                "Content-Type": "application/json",
            },
            json={
                "username": ci_env["INIT_USERNAME"],
                "password": ci_env["INIT_PASSWORD"],
                "remember": False,
            },
            timeout=30,
        )
        session_response.raise_for_status()
        assert session_response.json()["status"] == "success"

        curl_retry = ["--retry", "5", "--retry-delay", "2", "--retry-all-errors"]
        for proxy_args in (
            ["-x", http_proxy],
            ["--socks5", socks_proxy],
        ):
            result = run("curl", "-fsS", *curl_retry, *proxy_args, "https://example.com/")
            assert "Example Domain" in result.stdout
    finally:
        docker_compose("down", compose_file=reverse_proxy_compose, check=False)
        docker_compose("down", compose_file=static_web_compose, check=False)
        docker_compose("down", compose_file=wg_easy_compose, check=False)
        docker_compose("down", compose_file=proxy_compose, check=False)
        remove_path(wg_easy_dir / "data")
