# Go client sample

Minimal example of a Dockerized Go app connecting to the shared PostgreSQL instance from [`../../postgres`](../../postgres).

## Prerequisites

The PostgreSQL stack must be running:

```bash
cd ../../postgres
cp .env.example .env   # set POSTGRES_PASSWORD
docker compose up -d
```

## Run

```bash
cp .env.example .env   # use the same POSTGRES_PASSWORD as postgres/.env
docker compose up --build
```

Expected output:

```
connected to database "weather"
```

## Connection

The app joins the `infra` Docker network and connects to the `postgresql` container by name:

```
postgresql://postgres:<POSTGRES_PASSWORD>@postgresql:5432/weather
```

See [Connecting applications](../../postgres/README.md#connecting-applications) in the PostgreSQL README for other deployment patterns.
