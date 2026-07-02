# Shared Redis

Shared Redis 7 for a production VPS. A single instance serves multiple projects: each project uses its own logical database number (0–15) or a distinct key prefix.

## Quick start

```bash
docker network create infra 2>/dev/null || true
cd redis
cp .env.example .env
# set a strong REDIS_PASSWORD
docker compose up -d
```

Verify:

```bash
docker compose ps
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

## Connecting applications

The host port is bound to `127.0.0.1` only — Redis is not exposed to the public internet. How you connect depends on where the app runs.

### Docker apps on the same host (recommended)

Join the `infra` network and connect to the `redis` container by name. This is the reliable pattern on Linux VPS.

In the app's `docker-compose.yml`:

```yaml
services:
  app:
    environment:
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    networks:
      - infra

networks:
  infra:
    external: true
    name: infra
```

Connection URL (database `0` in this example):

```
redis://:<REDIS_PASSWORD>@redis:6379/0
```

### Apps on the host (not in Docker)

Connect via the loopback address and the published host port:

```
redis://:<REDIS_PASSWORD>@127.0.0.1:<REDIS_PORT>/0
```

### Do not use `host.docker.internal` on Linux

On Linux, `host.docker.internal` does not reach Redis when the port is published on `127.0.0.1` only. Use the Docker network pattern above for containerized apps, or `127.0.0.1` for host-native apps.

Set `REDIS_URL` in the project's `.env` file.

## Sharing between projects

Redis provides 16 logical databases (`0`–`15`) on a single instance. Assign each project its own database number to keep keys separate:

| Project   | Database | URL suffix |
|-----------|----------|------------|
| `myapp`   | `0`      | `/0`       |
| `worker`  | `1`      | `/1`       |
| `cache`   | `2`      | `/2`       |

Alternatively, use a key prefix inside one database (e.g. `myapp:session:abc`). Database numbers are simpler when each project owns a whole DB.

`FLUSHDB` and `FLUSHALL` are disabled in `redis.conf` to reduce the risk of wiping another project's data.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_PASSWORD` | — | Password (required) |
| `REDIS_PORT` | `6379` | Host port |

The port is bound to `127.0.0.1` — Redis is not exposed to the public internet.

## Layout

```
redis/
├── docker-compose.yml
├── redis.conf
└── .env.example
```

## Operations

```bash
# logs
docker compose logs -f redis

# stop
docker compose down

# stop and delete data (destructive!)
docker compose down -v

# redis-cli shell
docker compose exec redis redis-cli -a "$REDIS_PASSWORD"
```

## VPS deployment

1. Copy `redis/` to the server (e.g. `~/r/d/redis`).
2. Create `.env` with a production password.
3. Adjust `maxmemory` in `redis.conf` if needed for your workload.
4. Run `docker compose up -d`.

Deploy containerized applications on the `infra` network with `REDIS_URL` pointing at `redis:6379`. Host-native apps use `127.0.0.1:<REDIS_PORT>`.

## Backups

Trigger a background save and copy the AOF/RDB files from the volume:

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" BGSAVE
docker compose exec redis ls -la /data
```

For a point-in-time dump of one logical database:

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" -n 0 --rdb /data/backup-db0.rdb
docker cp redis:/data/backup-db0.rdb ./backup-db0.rdb
```
