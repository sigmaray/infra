from __future__ import annotations

import pytest

from helpers import REPO_ROOT, docker_compose, run

pytestmark = [pytest.mark.proxy]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "3proxy")


def test_shellcheck(shellcheck) -> None:
    run("shellcheck", "3proxy/scripts/generate-3proxy-cfg.sh")


@pytest.mark.integration
def test_proxy_http_and_socks(docker, ci_env) -> None:
    proxy_dir = REPO_ROOT / "3proxy"
    proxy_user = ci_env["PROXY_USER"]
    proxy_password = ci_env["PROXY_PASSWORD"]

    try:
        run("./scripts/generate-3proxy-cfg.sh", cwd=proxy_dir)
        docker_compose("up", "-d", "--wait", cwd=proxy_dir)

        http_proxy = f"http://{proxy_user}:{proxy_password}@3proxy:3128"
        socks_proxy = f"{proxy_user}:{proxy_password}@3proxy:1080"
        curl_retry = ["--retry", "3", "--retry-delay", "2", "--retry-all-errors"]

        for proxy_args in (
            ["-x", http_proxy],
            ["--socks5", socks_proxy],
        ):
            result = run(
                "docker",
                "run",
                "--rm",
                "--network",
                "3proxy_default",
                "curlimages/curl:8.12.1",
                "-fsS",
                *curl_retry,
                *proxy_args,
                "https://example.com/",
            )
            assert "Example Domain" in result.stdout
    finally:
        docker_compose("down", cwd=proxy_dir, check=False)
