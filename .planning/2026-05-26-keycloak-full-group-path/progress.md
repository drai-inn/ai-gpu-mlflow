# Progress Log

## Session: 2026-05-26

### Current Status
- **Phase:** 1 - Requirements & Discovery
- **Started:** 2026-05-26

### Actions Taken
- Clarified problem with user: duplicated leaf group names across different Keycloak parent groups collapsing into one MLflow group row.
- Cloned `data-platform-hq/mlflow-oidc-auth` `main` to `/tmp/mlflow-oidc-auth-clone` and traced the group-claim path: `config.py:99` reads `OIDC_GROUPS_ATTRIBUTE` (default `groups`); `routers/auth.py:552-569` reads the claim verbatim, gate-checks against `OIDC_GROUP_NAME` / `OIDC_ADMIN_GROUP_NAME` with literal `in`, then persists via `populate_groups` / `update_user`. No string transformation, no prefix-strip, no built-in path handling.
- Reviewed `mlflow-deployment.yaml`: no group env vars set, so defaults (`["mlflow"]`, `["mlflow-admin"]`) apply.
- Wrote findings.md and task_plan.md (7-phase plan: audit -> decide naming -> Keycloak mapper change -> deployment env vars -> conditional DB migration -> roll out -> document).
- Phase 1 audit: fetched OIDC discovery doc, queried `mlflow_auth` DB: 14 groups, 5 users, 39 user_group rows, only 1 group-permission row exists (`experiment_group_permissions`). Decision: wipe rather than rename in Phase 5.
- Confirmed Keycloak version via cluster pod inspection (recorded out-of-band; not stored in these files). User confirmed full-path values are top-level `/mlflow` and `/mlflow-admin`. Phase 1 + Phase 2 closed; current phase advanced to Phase 3.
- Phase 3 complete: a shared client scope carried the Group Membership mapper plus a `name` user-attribute mapper and two unrelated audience mappers. User added a dedicated `groups-full-path` mapper to `mlflow-test-dedicated` and detached the shared scope. Evaluate tab confirms full-path emission and `name` still present from the built-in `profile` scope. At least one nested group exists in the realm, confirming nesting is in active use. Advancing to Phase 4.
- Verified env-var list parsing: `config_providers/manager.py:265 get_list` splits on `,` and strips. Single-element lists can be written as plain strings (the leading `/` does not interact with the separator).
- Phase 4 complete: edited `mlflow-deployment.yaml` adding three env vars (`OIDC_GROUPS_ATTRIBUTE=groups`, `OIDC_GROUP_NAME=/mlflow`, `OIDC_ADMIN_GROUP_NAME=/mlflow-admin`). Not applied yet — Phase 5 (DB wipe + backup) happens before the rollout to avoid mixed bare-name / full-path rows during the transition.
- Phase 5 complete: backup at `backups/mlflow-auth-pre-fullpath-20260526T081641Z.sql`. Wipe transaction succeeded (`groups` 14->0, `user_groups` 39->0, `experiment_group_permissions` 1->0). Users + user-level experiment_permissions untouched. Single permission to re-grant post-rollout: `/mlflow` READ on experiment_id=0 (Default).
- Phase 6 complete: rollout clean, env vars confirmed in container. Test admin logged in, `groups` table now full-path; a nested sub-group is now distinct from its parent (was the actual symptom of the bug). Admin flag retained via `/mlflow-admin` match.
- Phase 7 complete: README has a `## Keycloak group claim` section; `mlflow-deployment.yaml` has a comment block above the new env vars. All 7 phases closed.

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|

### Errors
| Error | Resolution |
|-------|------------|
