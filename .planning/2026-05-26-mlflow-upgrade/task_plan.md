# Task Plan: Upgrade mlflow and mlflow-oidc-auth

## Goal
Upgrade the deployed MLflow stack from `mlflow 3.10.1` / `mlflow-oidc-auth 6.7.1` to `mlflow 3.12.0` / `mlflow-oidc-auth 7.3.1`, rebuild and push a new container image, roll out to the `mlflow` namespace with both alembic migrations applied cleanly, and verify auth + tracking still work.

## Current Phase
Complete (Phases 1, 2, 3, 5, 6, 7 complete; Phase 4 skipped)

## Scope and Non-Goals
- IN SCOPE: Dockerfile pins, image rebuild, deployment manifest update, DB backups, rollout, smoke tests.
- OUT OF SCOPE: Fix for the duplicate-group autoflush bug affecting users whose IdP claim contains duplicate group leaf names (tracked separately in issue drai-inn/ai-gpu-mlflow#1). Keycloak `Full group path` change. Workspace feature enablement. Postgres major-version upgrade.

## Target Versions
| Component | Current | Target |
|-----------|---------|--------|
| mlflow | 3.10.1 | 3.12.0 |
| mlflow-oidc-auth | 6.7.1 | 7.3.1 |
| Image | cdjs/mlflow-oidc:v0.3.1 (Docker Hub) | ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0 (GHCR via CI) |

## Phases

### Phase 1: Pre-flight checks and inventory
- [x] Confirm latest stable versions on PyPI (`mlflow==3.12.0`, `mlflow-oidc-auth==7.3.1`). Re-confirmed 2026-05-26.
- [x] Read full release notes from current to target for both packages; record any new breaking items in findings.md. No new breaking items beyond what was already known.
- [x] Inspect the alembic migration files added in `mlflow-oidc-auth 7.0.0` (workspace tables) and `mlflow 3.11/3.12` (issues, model-version index, metrics index, guardrails, jobs.status_details, budget policies). All additive. See `findings.md` → "Phase 1 results" → "Alembic migration diff".
- [x] Check whether any custom env vars in `mlflow-deployment.yaml` need renaming. Nothing removed or renamed between 6.7.1 and 7.3.1 config.py. Existing env vars still read. See `findings.md` → "Env var changes".
- [x] Keycloak access-token lifespan: confirmed 5 minutes. v7.2.0 default would bounce users every ~5 min; mitigation chosen: set `OIDC_USE_REFRESH_TOKEN=true` in deployment env. See `findings.md` → "Re-auth UX impact".
- [x] Staging strategy: SKIP. Rely on DB snapshots from Phase 2 as the rollback anchor. Phase 4 is now optional/skipped.
- [x] GHCR package visibility: PUBLIC after first publish.
- **Status:** complete

### Phase 2: Backups and rollback anchors
- [x] `pg_dump` the `mlflow` tracking DB. File: `backups/mlflow-tracking-20260526T010019Z.sql` (855K, complete marker present, 44 COPY blocks).
- [x] `pg_dump` the `mlflow_auth` plugin DB. File: `backups/mlflow-auth-20260526T010049Z.sql` (61K, complete marker present, 28 COPY blocks).
- [x] Old image `cdjs/mlflow-oidc:v0.3.1` confirmed still on Docker Hub via `docker manifest inspect`. Running pod is pinned to digest `sha256:abbe2311317964530bc3221d795abe677ff356c0052ffd7b3ebeb7f4dd3f2f93`.
- [x] Current deployment revision: **8**. Image: `cdjs/mlflow-oidc:v0.3.1`. Rollback path: `kubectl rollout undo deploy/mlflow -n mlflow` (to previous revision) or set image back to `cdjs/mlflow-oidc:v0.3.1` explicitly.
- **Status:** complete

### Phase 3: Build and publish new image via CI
- [x] Reviewed `.github/workflows/build_container.yml`. Triggers: `push` + `workflow_dispatch`. Build context: `docker/`. Registry: `ghcr.io/drai-inn/ai-gpu-mlflow`. `docker/metadata-action@v6` defaults: produces `:<branch>`, `:<tag>`, and `:latest` for a semver tag. Does NOT produce `:sha-<short>` (would need `type=sha`) nor `:0.4.0`/`:0.4` short forms (would need `type=semver,pattern={{version}}`).
- [x] In `docker/Dockerfile`, bumped `MLFLOW_VERSION=3.12.0` and `MLFLOW_OIDC_VERSION=7.3.1`. Branch `upgrade-mlflow-3.12.0`, commit `07fe896`.
- [x] CI run 26426658814 succeeded in 1m44s. Image: `ghcr.io/drai-inn/ai-gpu-mlflow:upgrade-mlflow-3.12.0@sha256:84f0e405004dca08602040f59f11e998602412f34a756b9957061531e471fd56`.
- [x] Fast-forwarded `main` to `07fe896` and pushed. CI run 26426817335 succeeded in 2m1s. Produced `:main`.
- [x] Tagged `v0.4.0` (annotated) on `07fe896` and pushed. CI run 26427038739 succeeded in 1m53s. Produced `:v0.4.0` and `:latest`, both → digest `sha256:1c2e5a0a68213faf07f142f454b5bc189f3c1b55acd1c72041b63f3e8af22a5b`.
- [x] GHCR package `ai-gpu-mlflow` already public. Anonymous `docker pull ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0` succeeded; digest matches CI push.
- [x] Smoke test: `docker run --rm ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0 mlflow server --help` returned normal help text. `importlib.metadata` reports `mlflow==3.12.0` and `mlflow-oidc-auth==7.3.1` inside the image. Note: `mlflow_oidc_auth.__version__` attribute still reads `7.0.0.dev0` (upstream `__init__.py` never updated); install metadata is what matters.
- **Status:** complete

### Phase 4: Staging dry-run (SKIPPED by decision)
- Skipped per Phase 1 decision. Rollback path is the DB snapshots taken in Phase 2 + reverting the deployment image tag to `cdjs/mlflow-oidc:v0.3.1`.
- **Status:** skipped

### Phase 5: Production rollout
- [x] Verify the Keycloak client (`mlflow-test`) has `offline_access` scope assigned. Confirmed 2026-05-26: present as Optional, which is sufficient.
- [x] Update `mlflow-deployment.yaml`:
  - [x] Set `image:` to `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0`.
  - [x] Add `OIDC_USE_REFRESH_TOKEN: "true"`, `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS: "30"`, `EXTEND_MLFLOW_REAUTH: "true"`.
  - [x] Bump `resources.limits.memory` from `2Gi` to `4Gi` (first rollout OOMKilled on steady-state ~2.1 GiB resident set under v0.4.0).
- [x] `kubectl apply -f mlflow-deployment.yaml`. Initial apply caused crashloop (OOMKilled 137); second apply (with 4Gi limit) rolled cleanly.
- [x] mlflow tracking DB at alembic head `7d34483879f0`. New objects present: `issues`, `guardrails`, `guardrail_configs`, `budget_policies` tables, `jobs.status_details` JSON column, `index_metrics_run_uuid_key_step` index.
- [x] mlflow_auth DB at alembic head `8a9b0c1de234`. New tables present: `workspace_permissions`, `workspace_group_permissions`, `workspace_regex_permissions`, `workspace_group_regex_permissions`.
- [x] Pod `mlflow-7f8c98458-gvzjf` Running 1/1, 0 restarts after 120s steady-state. Ingress `https://mlflow.test.drai.auckland.ac.nz/` returns 401 (expected OIDC challenge).
- **Status:** complete

### Phase 6: Verification and smoke tests
- [x] Browser-driven verification by user: admin login, non-admin login, experiment list, run view, write paths, S3 artifact resolution, and re-auth flow past the 5-min access-token lifespan all working. No silent-refresh failure observed.
- **Status:** complete

### Phase 7: Commit and document
- [x] Dockerfile pin bumps committed in `07fe896` (Phase 3). Deployment manifest committed in `e357b84` with image tag, OIDC re-auth env vars, and 4Gi memory limit.
- [x] `README.md` reviewed — does not cite version numbers, no edit needed. Stale TODO ("build image automatically and push to registry") is now obsolete; left untouched (out of scope for this plan).
- [x] Plan closed out in `progress.md` with final outcome and follow-ups.
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Target 3.12.0 / 7.3.1 (latest stable each) | Avoid mid-version pins. 7.3.1 includes the reauth.html packaging fix required by 7.2.0's re-auth flow. |
| Keep autoflush bug fix out of this plan | Independent change. Tracked in drai-inn/ai-gpu-mlflow#1. Bundling increases blast radius of the upgrade rollback. |
| New image tag v0.4.0 (not overwrite v0.3.1) | Keeps rollback to v0.3.1 trivial. |
| Build via GitHub Actions, publish to GHCR | Reproducible, CI-controlled builds. Tag-driven semver tagging via `docker/metadata-action` defaults. Replaces ad-hoc local `docker build` + Docker Hub push. |
| Workspace support stays dormant | No env vars set, default behaviour preserved. Adopt later as a separate decision if needed. |
| `OIDC_USE_REFRESH_TOKEN=true` in deployment | Keycloak access-token lifespan is 5 min; v7.2.0 default would bounce users every 5 min. Silent refresh via refresh tokens avoids that. Requires `offline_access` on the Keycloak client. |
| Skip Phase 4 staging dry-run | Migrations are additive only; DB snapshots + image-tag revert provide rollback. Staging would slow us down without proportional risk reduction. |
| GHCR package public | Cluster pulls anonymously; no imagePullSecret needed; simpler deployment manifest. |

## Risks
| Risk | Mitigation |
|------|------------|
| Alembic migration fails on one of the two DBs | DB snapshot taken in Phase 2; rollback by reverting image tag and (if needed) restoring snapshot. |
| Forced re-auth (v7.2.0) bouncing users every 5 min | Mitigated by `OIDC_USE_REFRESH_TOKEN=true`; verifies that the Keycloak client has `offline_access` assigned. |
| Hidden behaviour change in a 7.0.x → 7.3.x release we missed | Accepted, since staging is skipped. DB snapshot + image revert keeps the blast radius bounded. |
| Pod crashloop blocks all logins for everyone | Rolling-update strategy keeps the old pod up until the new one is healthy. Old image tag still available. |
| GHCR package private by default; cluster pull fails with `ImagePullBackOff` | Phase 3 explicitly makes the package public or creates an `imagePullSecret`. Verify with a `kubectl run` smoke pull before Phase 5. |
| `on: push` workflow trigger builds an image for every commit on every branch | Acceptable for now (only adds tags, doesn't promote). Tag-based semver tagging is what the deployment pulls. Can later tighten to `tags: ['v*']` + `pull_request` if noise becomes a problem. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Phase 5 first apply: pod crashlooped with OOMKilled (exit 137) within ~30s of startup. uvicorn started, parent process spawned, then SIGKILL. Logs showed only `AuthlibDeprecationWarning` at tail (red herring). | `kubectl get pod -o jsonpath='{...containerStatuses[0].lastState}'` revealed `OOMKilled` and the in-cluster `top pod` showed steady-state RSS of ~2148 MiB under v0.4.0 — over the existing 2Gi limit. Bumped `limits.memory` to 4Gi and re-applied. Old image v0.3.1 had been running at the same 2Gi limit with 7 restarts over 14d, suggesting it was already brushing the limit; v0.4.0 brings more loaded routers (GenAI gateway, jobs scheduler, workspace plugin) and crossed it consistently. |

## Out-of-Band Notes
- New image registry: `ghcr.io/drai-inn/ai-gpu-mlflow` (GitHub Packages), built by `.github/workflows/build_container.yml`.
- Previous image registry: `cdjs/mlflow-oidc` (Docker Hub). Keep `v0.3.1` there as a rollback anchor.
- CI build context is the `docker/` subdirectory (set via `context: docker` in the workflow).
- Tag-driven releases: pushing a git tag like `v0.4.0` triggers a build tagged `:v0.4.0` (plus `:0.4.0` and `:0.4` from `docker/metadata-action` defaults). A push to `main` also produces a `:main` floating tag.
- Namespace: `mlflow`. Deployment: `mlflow`. Postgres: `mlflow-postgres-postgresql-0`.
- Two databases on the same Postgres instance: `mlflow` (tracking, via `MLFLOW_BACKEND_STORE_URI`) and `mlflow_auth` (plugin, via `OIDC_USERS_DB_URI`).
