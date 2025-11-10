FROM python:3.12

# metadata
LABEL maintainer="you@example.com"
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off

# create a non-root user and dirs
RUN groupadd --gid 1000 mlgroup \
    && useradd --uid 1000 --gid mlgroup --create-home --no-log-init mluser \
    && mkdir -p /mlflow/db /mlflow/artifacts /app \
    && chown -R mluser:mlgroup /mlflow /app

WORKDIR /mlflow

ARG MLFLOW_VERSION=3.6.0
ARG MLFLOW_OIDC_VERSION=5.6.1

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install \
    mlflow-oidc-auth[full]==${MLFLOW_OIDC_VERSION} \
    mlflow==${MLFLOW_VERSION} \
    boto3 \
    psycopg2-binary \
    && rm -rf /root/.cache/pip

# small entrypoint script (ensures directories exist)
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# drop privileges - run as non-root user from here on
USER mluser

EXPOSE 5000
ENTRYPOINT [ "/app/docker-entrypoint.sh" ]
CMD ["mlflow", "server", \
    "--app-name", "oidc-auth", \
    "--host", "0.0.0.0", \
    "--port", "5000", \
    "--backend-store-uri", "sqlite:////mlflow/db/mlflow.db", \
    "--default-artifact-root", "/mlflow/artifacts", \
    "--disable-security-middleware"]
