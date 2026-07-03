from __future__ import annotations

import pytest

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.postgres]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "postgres")


def test_go_client_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "docs/go-client")


def test_shellcheck(shellcheck) -> None:
    run(
        "shellcheck",
        "postgres/init/01-flask-weather.sh",
        "postgres/scripts/create-database.sh",
    )


def test_bash_syntax() -> None:
    for script in (
        "postgres/init/01-flask-weather.sh",
        "postgres/scripts/create-database.sh",
    ):
        run("bash", "-n", script)


def test_script_permissions() -> None:
    for script in (
        REPO_ROOT / "postgres/init/01-flask-weather.sh",
        REPO_ROOT / "postgres/scripts/create-database.sh",
    ):
        assert script.exists()
        assert script.stat().st_mode & 0o111


@pytest.mark.integration
def test_postgres_and_go_client(docker, ci_env) -> None:
    postgres_compose = REPO_ROOT / "postgres/docker-compose.yml"
    go_client_compose = REPO_ROOT / "docs/go-client/docker-compose.yml"
    postgres_user = ci_env["POSTGRES_USER"]

    postgres_dir = REPO_ROOT / "postgres"
    try:
        ensure_infra_network()
        remove_path(postgres_dir / "data")
        docker_compose("up", "-d", "--wait", compose_file=postgres_compose)

        run(
            "docker",
            "compose",
            "-f",
            str(postgres_compose),
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            postgres_user,
        )

        result = run(
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
            "-tAc",
            "SELECT 1 FROM pg_database WHERE datname = 'weather'",
        )
        assert result.stdout.strip() == "1"

        docker_compose(
            "up",
            "--build",
            "--abort-on-container-exit",
            "--exit-code-from",
            "app",
            compose_file=go_client_compose,
        )
    finally:
        docker_compose("down", "--rmi", "local", compose_file=go_client_compose, check=False)
        docker_compose("down", compose_file=postgres_compose, check=False)
        remove_path(postgres_dir / "data")
