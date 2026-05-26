# Task Plan: Switch Keycloak Group Claim to Full Group Path

## Goal
Eliminate duplicate-leaf-name group collisions in `mlflow-oidc-auth` by having Keycloak emit full group paths (e.g. `/projectA/admins`) in the `groups` OIDC claim, and align the MLflow deployment + auth DB so the new format is recognised end to end.

## Context
- Symptom (confirmed): two Keycloak groups with the same leaf name under different parents collapse into a single MLflow group row.
- Scope (confirmed): Keycloak mapper config + `OIDC_*` env vars on the MLflow deployment.
- Migration: investigate first; the deployment is on `test.drai.auckland.ac.nz` so a wipe is acceptable if no real permissions are tied to existing rows.
- Key code refs: see `findings.md` (auth.py:552-569, config.py:99). Groups are persisted verbatim, allowlist matched with literal `in`.

## Current Phase
Complete

## Phases

### Phase 1: Audit current Keycloak + DB state
- [x] Full-path group names confirmed by user: top-level `/mlflow` (access) and `/mlflow-admin` (admin)
- [x] Current `full.path` mapper value: inferred `false` from DB (bare `mlflow` / `mlflow-admin` leaves in `mlflow_auth.groups`)
- [x] Keycloak server version: redacted; running in its own namespace
- [x] Sample userinfo capture deferred to Phase 6 verification (bump `LOG_LEVEL=DEBUG` post-rollout)
- [x] DB audit: 14 groups, 5 users, 39 user_group rows, only 1 group-permission row (in `experiment_group_permissions`)
- [x] Migration decision: **wipe-and-rebuild**. Single downstream permission row makes a SQL rename unjustified
- **Status:** complete

### Phase 2: Decide allowlist values and group naming scheme
- [x] Access-grant group full path: `/mlflow` (top-level, user-confirmed)
- [x] Admin group full path: `/mlflow-admin` (top-level, user-confirmed)
- [x] Set `OIDC_GROUPS_ATTRIBUTE` explicitly to `"groups"` for documentation
- [x] Decisions recorded in findings.md
- **Status:** complete

### Phase 3: Keycloak configuration change
- [x] Added a dedicated Group Membership mapper `groups-full-path` to `mlflow-test-dedicated`: `full.path = ON`, token claim name `groups`, userinfo + ID token enabled
- [x] Detached the shared client scope from `mlflow-test` (other clients using that scope unaffected). The scope's other mappers (a `name` user-attribute mapper, two audience mappers) were not needed for mlflow
- [x] Verified via Evaluate -> Generated user info: `groups` claim now full-path (includes `/mlflow`, `/mlflow-admin`, plus at least one nested sub-group entry), and `name` claim still populated by the built-in `profile` scope
- **Status:** complete

### Phase 4: MLflow deployment env vars
- [x] Confirmed list serialisation: `config_providers/manager.py:265 get_list` is comma-separated with whitespace strip
- [x] Edited `mlflow-deployment.yaml` to add `OIDC_GROUPS_ATTRIBUTE=groups`, `OIDC_GROUP_NAME=/mlflow`, `OIDC_ADMIN_GROUP_NAME=/mlflow-admin` (not yet applied)
- [x] Image version unchanged at `v0.4.0`
- **Status:** complete (pending apply in Phase 6)

### Phase 5: Data wipe (decided in Phase 1: only 1 permission row, wipe is safer than rename)
- [x] Captured the existing `experiment_group_permissions` row: experiment_id=0 (Default), group=`mlflow`, permission=`READ` -> needs re-granting against `/mlflow` post-rollout
- [x] Backup: `backups/mlflow-auth-pre-fullpath-20260526T081641Z.sql` (73K, verified to contain `groups`, `user_groups`, `experiment_group_permissions` COPY statements)
- [x] Wipe inside a transaction: `experiment_group_permissions` 1->0, `user_groups` 39->0, `groups` 14->0. Users (5 rows incl. is_admin flags) and user-level `experiment_permissions` (14 rows) untouched.
- **Status:** complete

### Phase 6: Roll out and verify
- [x] `kubectl apply -f mlflow-deployment.yaml` succeeded, new pod healthy, env vars confirmed inside container
- [x] Pod startup clean, OIDC client registered, no errors
- [x] Test admin login succeeded (audit log: `event=auth.login status=success method=oidc`)
- [x] Full-path verification: `groups` table now contains `/mlflow`, `/mlflow-admin`, and the other realm groups as full-path entries. A previously-collapsed nested sub-group is now distinct from its parent (validates the fix)
- [x] Admin retained: `is_admin = t` for the test admin; `OIDC_ADMIN_GROUP_NAME=/mlflow-admin` matched correctly
- [ ] Confirm non-allowlisted user is still rejected — deferred to organic future event (not blocking)
- [ ] Re-grant the one wiped permission row (`/mlflow` READ on experiment_id=0) — pending user decision
- **Status:** complete (verification passed; two follow-ups noted)

### Phase 7: Document
- [x] Added comment block in `mlflow-deployment.yaml` above the three new env vars
- [x] Added `## Keycloak group claim` section to `README.md` covering required mapper settings, the env-var contract, and rollback guidance
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use Keycloak's built-in `full.path` toggle, not a custom `OIDC_GROUP_DETECTION_PLUGIN` | Zero code change; upstream supports full paths verbatim since group names are persisted as-is. A plugin would only be needed if we wanted to transform/strip paths, which we don't. |
| Update `OIDC_GROUP_NAME` / `OIDC_ADMIN_GROUP_NAME` to full-path form rather than building transformation logic | `routers/auth.py:561-562` matches via literal `in`, so the simplest correct fix is to align the allowlist values with the new claim format. |
| Wipe `groups`/`user_groups` rather than rewriting names in-place | Audit found only 1 permission row tied to a group (`experiment_group_permissions`). Cost of recreating it manually is lower than the risk and complexity of a string-rename migration. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
