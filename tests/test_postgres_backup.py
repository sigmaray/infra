from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.postgres]

MINIO_NAME = "infra-test-minio"
MINIO_IMAGE = "minio/minio:RELEASE.2025-04-22T22-12-26Z"
MC_IMAGE = "minio/mc:RELEASE.2025-04-16T18-13-26Z"
MINIO_USER = "minioadmin"
MINIO_PASSWORD = "minioadmin"
MINIO_BUCKET = "pg-backups"
S3_PREFIX = "postgres"


def _s3_env(**overrides: str) -> dict[str, str]:
    env = {
        "BACKUP_LOCAL": "true",
        "BACKUP_S3": "true",
        "S3_BUCKET": MINIO_BUCKET,
        "S3_PREFIX": S3_PREFIX,
        "AWS_ACCESS_KEY_ID": MINIO_USER,
        "AWS_SECRET_ACCESS_KEY": MINIO_PASSWORD,
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": f"http://{MINIO_NAME}:9000",
        "BACKUP_DATABASES": "weather",
    }
    env.update(overrides)
    return env


def _docker(*args: str, check: bool = True):
    return run("docker", *args, check=check)


def _mc(*args: str, check: bool = True):
    return _docker(
        "run",
        "--rm",
        "--network",
        "infra",
        "-e",
        f"MC_HOST_local=http://{MINIO_USER}:{MINIO_PASSWORD}@{MINIO_NAME}:9000",
        MC_IMAGE,
        *args,
        check=check,
    )


def _wait_minio_ready(timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    result = None
    while time.time() < deadline:
        result = _mc("ready", "local", check=False)
        if result.returncode == 0:
            return
        time.sleep(1)
    stderr = result.stderr if result is not None else ""
    stdout = result.stdout if result is not None else ""
    raise AssertionError(f"MinIO did not become ready:\n{stderr}\n{stdout}")


def _start_minio() -> None:
    _docker("rm", "-f", MINIO_NAME, check=False)
    _docker(
        "run",
        "-d",
        "--name",
        MINIO_NAME,
        "--network",
        "infra",
        "-e",
        f"MINIO_ROOT_USER={MINIO_USER}",
        "-e",
        f"MINIO_ROOT_PASSWORD={MINIO_PASSWORD}",
        MINIO_IMAGE,
        "server",
        "/data",
        "--address",
        ":9000",
    )
    _wait_minio_ready()
    _mc("mb", "--ignore-existing", f"local/{MINIO_BUCKET}")


def _stop_minio() -> None:
    _docker("rm", "-f", MINIO_NAME, check=False)


def _list_s3_keys(prefix: str) -> list[str]:
    result = _mc("ls", "--recursive", f"local/{MINIO_BUCKET}/{prefix}")
    keys: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        keys.append(line.split()[-1])
    return keys


@pytest.fixture
def postgres_for_backup(docker, ci_env) -> Iterator[tuple[Path, Path]]:
    postgres_compose = REPO_ROOT / "postgres/docker-compose.yml"
    postgres_dir = REPO_ROOT / "postgres"
    backup_dir = REPO_ROOT / "postgres-backup"
    ensure_infra_network()
    remove_path(postgres_dir / "data")
    remove_path(backup_dir / "backups")
    docker_compose("up", "-d", "--wait", compose_file=postgres_compose)
    try:
        yield postgres_compose, backup_dir
    finally:
        docker_compose(
            "down",
            compose_file=REPO_ROOT / "postgres-backup/docker-compose.yml",
            check=False,
        )
        docker_compose("down", compose_file=postgres_compose, check=False)
        remove_path(postgres_dir / "data")
        remove_path(backup_dir / "backups")


def test_docker_compose_config(docker) -> None:
    docker_compose(
        "config",
        "--quiet",
        cwd=REPO_ROOT / "postgres-backup",
        env={"POSTGRES_PASSWORD": "ci-test-password"},
    )


def test_compose_passes_s3_settings() -> None:
    text = (REPO_ROOT / "postgres-backup/docker-compose.yml").read_text()
    for key in (
        "BACKUP_LOCAL",
        "BACKUP_S3",
        "S3_BUCKET",
        "S3_PREFIX",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_ENDPOINT_URL",
    ):
        assert f"{key}:" in text


def test_env_example_documents_s3() -> None:
    text = (REPO_ROOT / "postgres-backup/.env.example").read_text()
    assert "BACKUP_LOCAL=" in text
    assert "BACKUP_S3=" in text
    assert "S3_BUCKET=" in text
    assert "AWS_ENDPOINT_URL=" in text


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
    assert "aws-cli" in text


def test_backup_script_mentions_destinations() -> None:
    text = (REPO_ROOT / "postgres-backup/backup.sh").read_text()
    assert "BACKUP_LOCAL" in text
    assert "BACKUP_S3" in text
    assert "S3_BUCKET" in text
    assert "addressing_style = path" in text


@pytest.mark.integration
def test_backup_rejects_both_destinations_disabled(docker) -> None:
    backup_compose = REPO_ROOT / "postgres-backup/docker-compose.yml"
    result = docker_compose(
        "run",
        "--rm",
        "--build",
        "-e",
        "BACKUP_LOCAL=false",
        "-e",
        "BACKUP_S3=false",
        "backup",
        "/usr/local/bin/backup.sh",
        compose_file=backup_compose,
        check=False,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Enable at least one destination" in combined


@pytest.mark.integration
def test_backup_rejects_s3_without_bucket(docker) -> None:
    backup_compose = REPO_ROOT / "postgres-backup/docker-compose.yml"
    result = docker_compose(
        "run",
        "--rm",
        "--build",
        "-e",
        "BACKUP_LOCAL=false",
        "-e",
        "BACKUP_S3=true",
        "-e",
        "S3_BUCKET=",
        "-e",
        "AWS_ACCESS_KEY_ID=test",
        "-e",
        "AWS_SECRET_ACCESS_KEY=test",
        "backup",
        "/usr/local/bin/backup.sh",
        compose_file=backup_compose,
        check=False,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "S3_BUCKET" in combined


@pytest.mark.integration
def test_backup_dumps_weather(docker, ci_env, postgres_for_backup) -> None:
    _postgres_compose, backup_dir = postgres_for_backup
    backup_compose = REPO_ROOT / "postgres-backup/docker-compose.yml"

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


@pytest.mark.integration
def test_backup_local_and_s3(docker, ci_env, postgres_for_backup) -> None:
    _postgres_compose, backup_dir = postgres_for_backup
    backup_compose = REPO_ROOT / "postgres-backup/docker-compose.yml"

    try:
        _start_minio()
        result = docker_compose(
            "run",
            "--rm",
            "--build",
            "backup",
            "/usr/local/bin/backup.sh",
            compose_file=backup_compose,
            env=_s3_env(BACKUP_LOCAL="true", BACKUP_S3="true"),
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        dumps = list((backup_dir / "backups" / "weather").glob("weather_*.dump"))
        assert dumps, "expected local weather dump"

        keys = _list_s3_keys(f"{S3_PREFIX}/weather/")
        assert any(k.endswith(".dump") for k in keys), f"expected S3 dump, got: {keys}"
        assert any("weather_" in k for k in keys)
    finally:
        _stop_minio()


@pytest.mark.integration
def test_backup_s3_only(docker, ci_env, postgres_for_backup) -> None:
    _postgres_compose, backup_dir = postgres_for_backup
    backup_compose = REPO_ROOT / "postgres-backup/docker-compose.yml"

    try:
        _start_minio()
        result = docker_compose(
            "run",
            "--rm",
            "--build",
            "backup",
            "/usr/local/bin/backup.sh",
            compose_file=backup_compose,
            env=_s3_env(BACKUP_LOCAL="false", BACKUP_S3="true"),
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        weather_dir = backup_dir / "backups" / "weather"
        local_dumps = list(weather_dir.glob("weather_*.dump")) if weather_dir.exists() else []
        assert not local_dumps, f"S3-only mode must not keep local dumps: {local_dumps}"

        keys = _list_s3_keys(f"{S3_PREFIX}/weather/")
        assert any(k.endswith(".dump") for k in keys), f"expected S3 dump, got: {keys}"
        assert (backup_dir / "backups" / "backup.log").is_file()
    finally:
        _stop_minio()
