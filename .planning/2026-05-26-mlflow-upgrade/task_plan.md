# Task Plan: Upgrade mlflow and mlflow-oidc-auth

## Goal
Upgrade the deployed MLflow stack from `mlflow 3.10.1` / `mlflow-oidc-auth 6.7.1` to `mlflow 3.12.0` / `mlflow-oidc-auth 7.3.1`, rebuild and push a new container image, roll out to the `mlflow` namespace with both alembic migrations applied cleanly, and verify auth + tracking still work.

## Current Phase
Phase 5 (Phases 1, 2, 3 complete; Phase 4 skipped)

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
- [ ] Update `mlflow-deployment.yaml`:
  - Set `image:` to `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0`.
  - Add env var `OIDC_USE_REFRESH_TOKEN: "true"` so silent refresh kicks in and users are not bounced to Keycloak every 5 minutes.
  - (Optional but tidy) Add `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS: "30"` and `EXTEND_MLFLOW_REAUTH: "true"` explicitly; both are the defaults but pinning them documents intent.
- [ ] `kubectl apply -f mlflow-deployment.yaml`.
- [ ] Watch the new pod: ensure both alembic migrations complete; pod reaches Running 1/1; serves `/` with HTTP 200/302.
- [ ] Do NOT delete the old pod manually; let the rolling-update strategy handle it once the new pod is healthy.
- **Status:** pending

### Phase 6: Verification and smoke tests
- [ ] Admin login (you) via Keycloak: succeeds, lands on UI.
- [ ] Non-admin login (pick a user known not to trigger the duplicate-group bug, i.e. not one of the affected users until that issue is separately fixed): succeeds.
- [ ] List experiments via UI and via `mlflow` CLI against the endpoint.
- [ ] View an existing run with metrics/artifacts.
- [ ] Create a tiny throwaway experiment + run + log_metric to confirm write paths.
- [ ] Check that S3 artifact paths still resolve.
- [ ] Re-auth flow: stay logged in past the 5-minute access-token lifespan, then perform a UI/API action. Expected with `OIDC_USE_REFRESH_TOKEN=true`: silent refresh, no redirect. Confirm pod log contains `Session for ... refreshed against IdP` (or equivalent).
- [ ] If silent refresh fails (e.g. `offline_access` scope not assigned), pod logs will show a 401/redirect and the user will be sent back to Keycloak. Fix the Keycloak client scope, no rollback needed.
- **Status:** pending

### Phase 7: Commit and document
- [ ] Commit Dockerfile pin bumps and deployment manifest tag bump together with a clear message.
- [ ] Update `README.md` if it cites version numbers.
- [ ] Close out this plan in `progress.md` with the final outcome and any follow-ups.
- **Status:** pending

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

## Out-of-Band Notes
- New image registry: `ghcr.io/drai-inn/ai-gpu-mlflow` (GitHub Packages), built by `.github/workflows/build_container.yml`.
- Previous image registry: `cdjs/mlflow-oidc` (Docker Hub). Keep `v0.3.1` there as a rollback anchor.
- CI build context is the `docker/` subdirectory (set via `context: docker` in the workflow).
- Tag-driven releases: pushing a git tag like `v0.4.0` triggers a build tagged `:v0.4.0` (plus `:0.4.0` and `:0.4` from `docker/metadata-action` defaults). A push to `main` also produces a `:main` floating tag.
- Namespace: `mlflow`. Deployment: `mlflow`. Postgres: `mlflow-postgres-postgresql-0`.
- Two databases on the same Postgres instance: `mlflow` (tracking, via `MLFLOW_BACKEND_STORE_URI`) and `mlflow_auth` (plugin, via `OIDC_USERS_DB_URI`).
