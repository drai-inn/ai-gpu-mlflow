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
