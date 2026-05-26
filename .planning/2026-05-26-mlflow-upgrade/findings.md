# Findings

## Current deployed state (confirmed from pod `mlflow-6bcdd5bf89-vldbh` in namespace `mlflow`)
- Image: `cdjs/mlflow-oidc:v0.3.1`
- `mlflow == 3.10.1`
- `mlflow-oidc-auth == 6.7.1`
- `/usr/local/lib/python3.12/site-packages/mlflow_oidc_auth/repository/group.py:129` contains the unfixed `set_groups_for_user` (autoflush/duplicate-group bug, tracked separately).

## Pinned in `docker/Dockerfile`
- `ARG MLFLOW_VERSION=3.10.1`
- `ARG MLFLOW_OIDC_VERSION=6.7.1`
- Base: `python:3.12`
- Installs: `mlflow-oidc-auth[full]`, `mlflow[genai]`, `boto3`, `psycopg2-binary`.

## Deployment env vars relevant to OIDC (from `mlflow-deployment.yaml`)
- `OIDC_DISCOVERY_URL=https://keycloak.test.drai.auckland.ac.nz/realms/drai/.well-known/openid-configuration`
- `OIDC_CLIENT_ID=mlflow-test`
- `OIDC_SCOPE=openid email profile`
- `OIDC_REDIRECT_URI=https://mlflow.test.drai.auckland.ac.nz/callback`
- `DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS`
- `MLFLOW_BACKEND_STORE_URI` points at Postgres `mlflow` DB.
- `OIDC_USERS_DB_URI` points at Postgres `mlflow_auth` DB.
- `OIDC_GROUP_NAME` and `OIDC_ADMIN_GROUP_NAME` are NOT set; defaults `["mlflow"]` and `["mlflow-admin"]` apply.

## mlflow 3.10.1 → 3.12.0 release deltas
- **3.11.0**: breaking change is TypeScript SDK package renaming only (irrelevant here). Adds `SqlIssue` table, gateway budget policy tables. Adds automatic issue identification, gateway budget alerts, trace graph view, OTel GenAI semconv export, pickle-free model serialisation.
- **3.11.1**: bug fixes only.
- **3.12.0**: deprecates `enable_mlserver` in pyfunc serving backend (irrelevant). Adds gateway guardrail tables. Pandas 3.x compatibility fixes.
- Net schema change: additive tables only. All migrations run by alembic on startup.

## mlflow-oidc-auth 6.7.1 → 7.3.1 release deltas
- **7.0.0** (BREAKING): adds workspace support (PR #230). Adds workspace_permissions tables and middleware plumbing. Default behaviour matches pre-7.0 unless workspaces are explicitly enabled.
- **7.0.1**: fix permission denied for non-admins (PR #235).
- **7.0.2**: restore missing API doc setting.
- **7.0.3**: fix experiment-id resolution for workspace-enabled paths.
- **7.1.0**: extend Starlette `SessionMiddleware` config (PR #232). Lets you tune session cookie attributes; default unchanged.
- **7.1.1**: better auth-failure log diagnostics (PR #243).
- **7.2.0** (BEHAVIOUR CHANGE): re-authenticate sessions against IdP token expiry (PR #249, closes #242). Users get bounced to Keycloak when their IdP access/refresh token expires.
- **7.3.0**: menu/permission UI fixes (PR #254), gateway creation path support, polish.
- **7.3.1**: packaging fix, include `hack/reauth.html` in wheel (PR #255). Required by 7.2.0's re-auth flow. Pin to 7.3.1 (or higher), not 7.2.0 directly.
- Net schema change: additive (workspace tables), no destructive operations.

## Carryover from earlier investigation (the autoflush bug)
- `set_groups_for_user` is byte-identical between 6.7.1 and 7.3.1. The upgrade does NOT fix the duplicate-group autoflush bug.
- For at least one affected user, the Keycloak userinfo contains the same group leaf name (`"admin"`) three times, because three groups share that leaf name and the Keycloak `Group Membership` mapper has `Full group path = OFF`.
- Plugin grants admin via literal string match: `OIDC_ADMIN_GROUP_NAME=["mlflow-admin"]` against the `groups` claim. If `Full group path` is ever turned ON, simultaneously set `OIDC_GROUP_NAME=/mlflow` and `OIDC_ADMIN_GROUP_NAME=/mlflow-admin` (or actual paths) in the deployment manifest.
- Issue filed: https://github.com/drai-inn/ai-gpu-mlflow/issues/1
- No matching upstream issue in `mlflow-oidc/mlflow-oidc-auth` at search time.

## CI / image build (new)
- Workflow at `.github/workflows/build_container.yml` builds the container in GitHub Actions and pushes to GHCR.
  - Registry: `ghcr.io/${{ github.repository }}` = `ghcr.io/drai-inn/ai-gpu-mlflow`.
  - Build context: `docker/` (so the Dockerfile sees only files in that directory; no project root files are available at build time).
  - Triggers: `push` (any branch) + `workflow_dispatch`.
  - Tag strategy: `docker/metadata-action@v6` defaults, which yield `:<branch>`, `:pr-N`, `:sha-<short>`, and semver tags (`:v0.4.0`, `:0.4.0`, `:0.4`) when a git tag matching `v*` is pushed.
  - Auth: `${{ secrets.GITHUB_TOKEN }}` with `packages: write`. No extra secrets required for GHCR.
- Implication for the deployment manifest: change `image:` from `cdjs/mlflow-oidc:v0.3.1` to `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0`.
- GHCR packages default to private when first created. Either flip to public after the first publish, or attach an `imagePullSecret` referencing a PAT with `read:packages` to the `mlflow` namespace.

## Phase 1 results

### Latest stable versions on PyPI (confirmed 2026-05-26)
- `mlflow` latest: `3.12.0`
- `mlflow-oidc-auth` latest: `7.3.1`

### Alembic migration diff (additive only, both packages)

mlflow tracking DB, new since 3.10.1 (six migrations):
- `76601a5f987d_add_issues_table.py` — creates `issues` table (FKs to experiments, runs; indexes on experiment_id, source_run_id, status).
- `7d34483879f0_add_model_version_tags_workspace_index.py` — adds composite indexes on existing `model_version_tags`/`registered_model_tags` (workspace, name[, version]).
- `a5b4c3d2e1f0_add_metrics_run_key_step_index.py` — adds `index_metrics_run_uuid_key_step` composite index on `metrics(run_uuid, key, step)`.
- `ae8bbe7743c9_add_guardrails_tables.py` — creates `guardrails` and `guardrail_configs` tables.
- `c3d6457b6d8a_add_status_details_column_to_jobs_table.py` — adds nullable JSON column `jobs.status_details`.
- `e1f2a3b4c5d6_add_budget_policies_table.py` — creates `budget_policies` table.

mlflow-oidc-auth plugin DB, new since 6.7.1 (two migrations):
- `7b8c9d0ef123_add_workspace_permissions.py` — creates `workspace_permissions` (PK: workspace,user_id; FK users.id) and `workspace_group_permissions` (PK: workspace,group_id; FK groups.id).
- `8a9b0c1de234_add_workspace_regex_permissions.py` — creates `workspace_regex_permissions` and `workspace_group_regex_permissions` (each id PK, unique(regex, user_id|group_id), FK).

Net: 4 new tables + 1 new nullable column + 4 new indexes on the tracking DB; 4 new tables on the plugin DB. No `alter_column`, no `drop_column`, no `drop_table`. Migrations are safe to run online and reversible per their downgrade paths.

### Env var changes (config.py diff 6.7.1 → 7.3.1)
**Nothing removed or renamed.** All existing env vars (`OIDC_*`, `DEFAULT_MLFLOW_PERMISSION`, `SECRET_KEY`, `AUTOMATIC_LOGIN_REDIRECT`, `EXTEND_MLFLOW_MENU`, `OIDC_GEN_AI_GATEWAY_ENABLED`, `PERMISSION_SOURCE_ORDER`, `OIDC_ALEMBIC_VERSION_TABLE`, `DEFAULT_LANDING_PAGE_IS_PERMISSIONS`) still read.

New env vars worth knowing (all have plugin-side defaults so unset = pre-upgrade behaviour):
- `MLFLOW_ENABLE_WORKSPACES` (bool): gates workspace feature. Leave unset.
- `OIDC_USE_REFRESH_TOKEN`, `EXTEND_MLFLOW_REAUTH`, `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS`: relate to 7.2.0 re-auth flow.
- `SESSION_COOKIE_NAME`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_MAX_AGE_SECONDS`: surface Starlette `SessionMiddleware` config (7.1.0).
- `OIDC_DB_POOL_SIZE`, `OIDC_DB_POOL_MAX_OVERFLOW`, `OIDC_DB_POOL_RECYCLE_SECONDS`: SQLAlchemy pool tuning.
- `OIDC_JWKS_CACHE_TTL_SECONDS`, `PERMISSION_CACHE_TTL_SECONDS`, `WORKSPACE_CACHE_TTL_SECONDS`, `WORKSPACE_CACHE_MAX_SIZE`: caching.
- `CACHE_BACKEND`, `CACHE_REDIS_URL`, `CACHE_KEY_PREFIX`: cache backend selection.
- `AUDIT_LOG_ENABLED`, `AUDIT_LOG_LEVEL`: new audit log.
- `OIDC_AUDIENCE`, `TRUSTED_PROXIES`, `ENABLE_API_DOCS`: misc.
- `OIDC_WORKSPACE_*`: workspace claim mapping (only when workspaces enabled).

## Phase 1 decisions (recorded 2026-05-26)
- **Keycloak access-token lifespan: 5 minutes.** With default v7.2.0 behaviour, users would be bounced to Keycloak every ~5 min after upgrade. Mitigation chosen for the upgrade plan: enable silent refresh via `OIDC_USE_REFRESH_TOKEN=true` (new env var, default `false`). See "Re-auth UX impact" below.
- **Staging: skipped.** Rely on the DB snapshots taken in Phase 2 as the rollback anchor. Phase 4 in the plan becomes optional/skipped.
- **GHCR package visibility: public.** No imagePullSecret needed; the cluster pulls anonymously. Flip to public in GitHub Packages settings after the first successful CI publish.

## Re-auth UX impact (PR #249 in mlflow-oidc-auth v7.2.0)
- **Default after upgrade (no opt-in)**: `AuthMiddleware._authenticate_session` rejects a session once `now >= expires_at - OIDC_SESSION_EXPIRY_LEEWAY_SECONDS` (default leeway 30s). With a 5-minute access token, a user gets redirected through the full OIDC flow every ~4.5 minutes. Unacceptable UX.
- **Opt-in `OIDC_USE_REFRESH_TOKEN=true`**: plugin appends `offline_access` to the OIDC scope, persists the refresh token in the (signed) session cookie, and silently refreshes against the IdP via `oauth.oidc.fetch_access_token(grant_type="refresh_token", ...)`. Default is `false` because some orgs disallow `offline_access`. Keycloak client must allow the `offline_access` scope.
- **Other new flags**:
  - `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS` (default `30`).
  - `EXTEND_MLFLOW_REAUTH` (default `true`). Injects a fetch/XHR 401-handler into the MLflow UI so subresource requests trigger a single `window.location.reload()` instead of breaking SPA chunk loading.
- **Sessions that predate the upgrade keep working** until their cookie expires (no forced logout at deploy time, per PR #249 description).
- Decision for our rollout: set `OIDC_USE_REFRESH_TOKEN=true` in the deployment env. Pre-flight: verify the Keycloak client has the `offline_access` scope assigned. (Realm-level `offline_access` is enabled by default in Keycloak.)
- **Confirmed 2026-05-26**: `offline_access` is in the Keycloak `mlflow-test` client's assigned scopes list as **Optional**. The plugin requests it explicitly at login when `OIDC_USE_REFRESH_TOKEN=true`, so Optional is sufficient (Default would also work). No further Keycloak change needed.

## References
- mlflow releases: https://github.com/mlflow/mlflow/releases
- mlflow-oidc-auth releases: https://github.com/mlflow-oidc/mlflow-oidc-auth/releases
- This repo's deployment manifest: `mlflow-deployment.yaml`
- Dockerfile: `docker/Dockerfile`
