# Backup image: pg_dump via supercronic (same major as ../postgres/).
# Optional S3 upload via aws-cli. https://github.com/aptible/supercronic
FROM postgres:16.14-alpine

ARG TARGETARCH=amd64
ARG SUPERCRONIC_VERSION=v0.2.47

RUN set -eux; \
  apk add --no-cache ca-certificates curl tzdata aws-cli; \
  case "${TARGETARCH}" in \
    amd64) SUPERCRONIC_SHA1SUM=712d2ece75da6f6e530192a151488578153e4e96 ;; \
    arm64) SUPERCRONIC_SHA1SUM=93323899ddca3f1198f1796a4bf4418ed1e7982e ;; \
    *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
  esac; \
  SUPERCRONIC="supercronic-linux-${TARGETARCH}"; \
  curl -fsSLO "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/${SUPERCRONIC}"; \
  echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c -; \
  chmod +x "${SUPERCRONIC}"; \
  mv "${SUPERCRONIC}" "/usr/local/bin/${SUPERCRONIC}"; \
  ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic; \
  apk del curl; \
  aws --version

COPY backup.sh /usr/local/bin/backup.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/entrypoint.sh

ENV BACKUP_DIR=/backups \
    BACKUP_RETENTION_DAYS=14 \
    BACKUP_CRON="0 3 * * *" \
    BACKUP_LOCAL=true \
    BACKUP_S3=false \
    PGHOST=postgresql \
    PGPORT=5432

VOLUME ["/backups"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
