from __future__ import annotations

import pytest

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.postgres]


def test_docker_compose_config(docker) -> None:
    docker_compose(
        "config",
        "--quiet",
        cwd=REPO_ROOT / "postgres-backup",
        env={"POSTGRES_PASSWORD": "ci-test-password"},
    )


def test_shellcheck(shellcheck) -> None:
    run(
        "shellcheck",
        "postgres-backup/backup.sh",
        "postgres-backup/entrypoint.sh",
    )


def test_bash_syntax() -> None:
    for script in (
        "postgres-backup/backup.sh",
        "postgres-backup/entrypoint.sh",
    ):
        run("bash", "-n", script)


def test_script_permissions() -> None:
    for script in (
        REPO_ROOT / "postgres-backup/backup.sh",
        REPO_ROOT / "postgres-backup/entrypoint.sh",
    ):
        assert script.exists()
        assert script.stat().st_mode & 0o111


def test_dockerfile() -> None:
    dockerfile = REPO_ROOT / "postgres-backup/Dockerfile"
    assert dockerfile.is_file()
    text = dockerfile.read_text()
    assert "supercronic" in text
    assert "postgres:16.14-alpine" in text


@pytest.mark.integration
def test_backup_dumps_weather(docker, ci_env) -> None:
    postgres_compose = REPO_ROOT / "postgres/docker-compose.yml"
    backup_compose = REPO_ROOT / "postgres-backup/docker-compose.yml"
    postgres_dir = REPO_ROOT / "postgres"
    backup_dir = REPO_ROOT / "postgres-backup"
    postgres_user = ci_env["POSTGRES_USER"]

    try:
        ensure_infra_network()
        remove_path(postgres_dir / "data")
        remove_path(backup_dir / "backups")
        docker_compose("up", "-d", "--wait", compose_file=postgres_compose)

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
            "run",
            "--rm",
            "--build",
            "backup",
            "/usr/local/bin/backup.sh",
            compose_file=backup_compose,
        )
        dumps = list((backup_dir / "backups" / "weather").glob("weather_*.dump"))
        assert dumps, "expected a weather dump under postgres-backup/backups/weather/"
        assert (backup_dir / "backups" / "backup.log").is_file()
    finally:
        docker_compose("down", compose_file=backup_compose, check=False)
        docker_compose("down", compose_file=postgres_compose, check=False)
        remove_path(postgres_dir / "data")
        remove_path(backup_dir / "backups")
