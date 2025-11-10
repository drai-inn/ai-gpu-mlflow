#!/usr/bin/env bash
set -euo pipefail

# ensure directories exist and are owned by user
mkdir -p /mlflow/db /mlflow/artifacts
chown -R "$(id -u):$(id -g)" /mlflow || true

echo "Listing /mlflow"
ls -l /mlflow
echo "Listing /mlflow/db"
ls -l /mlflow/db
echo "Listing /mlflow/artifacts"
ls -l /mlflow/artifacts

echo "OIDC_DISCOVERY_URL=${OIDC_DISCOVERY_URL}"
echo "OIDC_CLIENT_ID=${OIDC_CLIENT_ID}"
echo "OIDC_PROVIDER_DISPLAY_NAME=${OIDC_PROVIDER_DISPLAY_NAME}"

echo Arguments: "$@"

exec "$@"
