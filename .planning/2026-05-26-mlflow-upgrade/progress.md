# Progress Log

## Session: 2026-05-26

### Current Status
- **Phase:** 1 - Pre-flight checks and inventory
- **Started:** 2026-05-26

### Actions Taken
- Created plan directory `.planning/2026-05-26-mlflow-upgrade/`.
- Populated `task_plan.md` with seven phases scoped to the upgrade (excludes the duplicate-group autoflush login bug fix and the Keycloak `Full group path` change).
- Populated `findings.md` with confirmed current state of the running pod, deployment env vars, and release-note deltas for both packages.
- Filed bug report for the autoflush/duplicate-group issue separately: drai-inn/ai-gpu-mlflow#1.

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|

### Errors
| Error | Resolution |
|-------|------------|

### Next Up
- Phase 1 open questions: decide staging strategy for Phase 4, check Keycloak realm access-token TTL, decide GHCR package visibility (public vs private + imagePullSecret).

### Update 2026-05-26 (later in session)
- Plan revised to use the new CI workflow `.github/workflows/build_container.yml` which builds in GitHub Actions and pushes to `ghcr.io/drai-inn/ai-gpu-mlflow`. Image registry switched from Docker Hub (`cdjs/mlflow-oidc`) to GHCR. Phase 3 rewritten as a CI-driven build; Phase 5 image reference updated; risks and out-of-band notes updated.

### Update 2026-05-26 (Phase 1 execution)
- Re-confirmed PyPI latest: `mlflow==3.12.0`, `mlflow-oidc-auth==7.3.1`.
- Pulled alembic migration deltas via `gh api`. mlflow tracking DB: 6 new migrations (4 new tables, 1 new nullable column on `jobs`, 2 index-only). Plugin DB: 2 new migrations (4 new workspace-related tables). All additive, no destructive ops.
- Diffed `config.py` between 6.7.1 and 7.3.1: no env vars removed or renamed. Many added (workspace, cache, session cookie, DB pool, re-auth tuning), all with internal defaults that preserve pre-upgrade behaviour.
- Read PR #249 in detail. Default v7.2.0 behaviour with a 5-min access token would bounce users every 5 min; mitigation is `OIDC_USE_REFRESH_TOKEN=true` for silent refresh.

### Update 2026-05-26 (Phase 2 execution and completion)
- Confirmed kube context `uoa-drai-gpu-test-admin@uoa-drai-gpu-test`. Pods in `mlflow` ns: `mlflow-6bcdd5bf89-vldbh` (Running 1/1, 7 restarts in 14d) and `mlflow-postgres-postgresql-0`.
- DB creds: `DB_PASSWORD`/`POSTGRES_PASSWORD` both bound to secret `mlflow-postgres-secret` key `password`.
- Created `backups/` (added to `.gitignore`).
- `pg_dump` executed inside the postgres pod, streamed via `kubectl exec` to local files:
  - `backups/mlflow-tracking-20260526T010019Z.sql` (855K, ends with `-- PostgreSQL database dump complete`).
  - `backups/mlflow-auth-20260526T010049Z.sql` (61K, ends with `-- PostgreSQL database dump complete`).
- Note: modern pg_dump (>=17) brackets the dump with `\restrict TOKEN` / `\unrestrict TOKEN` (psql restore safety). Both files balanced.
- Rollback anchors recorded: deployment revision **8**, image `cdjs/mlflow-oidc:v0.3.1`, running container imageID digest `sha256:abbe2311317964530bc3221d795abe677ff356c0052ffd7b3ebeb7f4dd3f2f93`.
- Old image manifest still resolvable on Docker Hub (`docker manifest inspect cdjs/mlflow-oidc:v0.3.1` returned a valid v2 manifest).
- Phase 2 marked complete. Current phase advanced to 3.

### Update 2026-05-26 (Phase 3 execution and completion)
- Created branch `upgrade-mlflow-3.12.0` from local `main` (which already had the unpushed workflow + plan commits).
- Bumped `docker/Dockerfile` to `MLFLOW_VERSION=3.12.0` / `MLFLOW_OIDC_VERSION=7.3.1`. Single commit `07fe896`.
- Pushed branch. CI run 26426658814 succeeded in 1m44s. Image `:upgrade-mlflow-3.12.0@sha256:84f0e405004dca08602040f59f11e998602412f34a756b9957061531e471fd56`.
- Per user decision: fast-forwarded `main` to `07fe896` and pushed directly (no PR). CI run 26426817335 succeeded in 2m1s. Image `:main`.
- Tagged `v0.4.0` annotated on `07fe896`, pushed. CI run 26427038739 succeeded in 1m53s. Image `:v0.4.0` and `:latest` → digest `sha256:1c2e5a0a68213faf07f142f454b5bc189f3c1b55acd1c72041b63f3e8af22a5b`.
- Observation: workflow's default `docker/metadata-action` config only produces `:<branch>`, `:<tag>`, and `:latest`. No `:sha-<short>`, no `:0.4.0`/`:0.4` short semver forms. Not blocking, just noting.
- GHCR package confirmed already public. Anonymous `docker pull` succeeded with matching digest.
- Smoke test: `mlflow server --help` works. `importlib.metadata` shows `mlflow==3.12.0` and `mlflow-oidc-auth==7.3.1`. `mlflow_oidc_auth.__version__` reads `7.0.0.dev0` due to an upstream cosmetic bug; the wheel install version is the source of truth.
- Phase 3 marked complete. Current Phase advanced to 5 (Phase 4 was already skipped).

### Update 2026-05-26 (Phase 5 execution and completion)
- Edited `mlflow-deployment.yaml`: bumped `image:` to `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0` and added env vars `OIDC_USE_REFRESH_TOKEN=true`, `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS=30`, `EXTEND_MLFLOW_REAUTH=true`.
- First `kubectl apply`: rolled out, then pod entered crashloop (4 restarts in <4 min). Log tail showed only the harmless `authlib.jose` deprecation warning, no traceback. `containerStatuses[0].lastState` revealed `OOMKilled` with exit code 137.
- Root cause: v0.4.0 steady-state resident set is ~2148 MiB (per `kubectl top pod`), exceeds the existing 2Gi limit. Old v0.3.1 had been running at the same limit with 7 restarts over 14d, already brushing the ceiling.
- Edited the manifest again to bump `limits.memory` from 2Gi to 4Gi (node has ~200GB allocatable, plenty of headroom). Re-applied.
- Second rollout clean. Pod `mlflow-7f8c98458-gvzjf` Running 1/1, 0 restarts after a 120s stability watch.
- Verified migrations via direct psql into the postgres pod:
  - `mlflow.alembic_version` = `7d34483879f0`; new objects (`issues`, `guardrails`, `guardrail_configs`, `budget_policies`, `jobs.status_details`, `index_metrics_run_uuid_key_step`) all present.
  - `mlflow_auth.alembic_version` = `8a9b0c1de234`; all four workspace tables present.
- Verified ingress: `curl https://mlflow.test.drai.auckland.ac.nz/` → HTTP 401 (expected OIDC challenge, not 5xx).
- Current Phase advanced to 6.

### Update 2026-05-26 (Phase 6 + Phase 7 close-out)
- Deployment manifest committed in `e357b84`: image tag `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0`, env vars `OIDC_USE_REFRESH_TOKEN=true` / `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS=30` / `EXTEND_MLFLOW_REAUTH=true`, memory limit 2Gi→4Gi. Dockerfile pin bumps already shipped in `07fe896` (Phase 3).
- Phase 6 verification driven by user in the browser: admin + non-admin login, experiment list, run view, write paths, S3 artifact resolution, and the 5-min re-auth flow all confirmed working. Silent refresh held; no fallback redirect observed.
- README has no version pins; left as-is. Stale TODO line ("build image automatically and push to registry") is now superseded by the GHCR CI workflow but left untouched (out of scope).
- Local commits ahead of `origin/main`: `7ada11d` (.gitignore for backups/), `5090897` (Phase 2/3 progress), `e357b84` (deployment manifest). Push at the user's discretion.

### Final outcome
- Production runs on `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0` (`mlflow==3.12.0`, `mlflow-oidc-auth==7.3.1`).
- Both alembic heads applied: tracking DB → `7d34483879f0`, plugin DB → `8a9b0c1de234`.
- Memory limit raised to 4Gi; no further OOMKills observed.
- DB snapshots retained under `backups/` as rollback anchor (`.gitignore`d).
- Previous image `cdjs/mlflow-oidc:v0.3.1` still resolvable on Docker Hub for image-tag revert.

### Follow-ups (not in scope of this plan)
- Duplicate-group autoflush bug for users whose IdP claim contains repeated group leaf names. Still unfixed in 7.3.1. Tracked separately in drai-inn/ai-gpu-mlflow#1.
- README TODO line is now obsolete; consider a small cleanup PR.
- Optionally tighten `.github/workflows/build_container.yml` triggers to `tags: ['v*'] + pull_request` if per-commit build noise becomes a problem.
- Workspace feature in `mlflow-oidc-auth` 7.x is dormant; revisit if multi-tenant boundaries are needed.

### Update 2026-05-26 (Phase 1 close-out)
User decisions recorded:
- Keycloak access-token lifespan = 5 min. Decision: enable `OIDC_USE_REFRESH_TOKEN=true` in deployment (added to Phase 5 checklist).
- Staging = skipped. Phase 4 marked skipped in plan.
- GHCR visibility = public. Decision noted; pull-secret path removed from Phase 5.

Plan updates:
- Phase 1 marked complete.
- Phase 4 marked skipped.
- Phase 5 expanded with: verify `offline_access` on the Keycloak client, set `OIDC_USE_REFRESH_TOKEN=true`, optional explicit pinning of `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS` and `EXTEND_MLFLOW_REAUTH`.
- Phase 6 verification expanded with re-auth flow check.
- Decisions Made and Risks tables updated.
- Current Phase advanced to 2.
