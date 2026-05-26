# Findings: Keycloak Full Group Path

## Problem

Keycloak's default Group Membership protocol mapper emits only the leaf group name in the `groups` claim. Two groups with the same leaf in different parents (e.g. `/projectA/admins` and `/projectB/admins`) both collapse to `"admins"`, so `mlflow-oidc-auth` cannot distinguish them. A user in `/projectA/admins` ends up in the same MLflow group row as a user in `/projectB/admins`, and permissions leak across projects.

## How mlflow-oidc-auth reads groups today

Source: `data-platform-hq/mlflow-oidc-auth` (cloned at `/tmp/mlflow-oidc-auth-clone`, branch `main`).

- `mlflow_oidc_auth/config.py:99`
  ```python
  self.OIDC_GROUPS_ATTRIBUTE = config_manager.get("OIDC_GROUPS_ATTRIBUTE", "groups")
  ```
  Default claim name is `groups`.

- `mlflow_oidc_auth/routers/auth.py:552-562`
  ```python
  if config.OIDC_GROUP_DETECTION_PLUGIN:
      user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(access_token)
  else:
      user_groups = userinfo.get(config.OIDC_GROUPS_ATTRIBUTE, [])
  ...
  is_admin = any(group in user_groups for group in config.OIDC_ADMIN_GROUP_NAME)
  if not is_admin and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
      errors.append("User is not allowed to login")
  ```

- `mlflow_oidc_auth/routers/auth.py:568-569`
  ```python
  user_module.populate_groups(group_names=user_groups)
  user_module.update_user(username=email.lower(), group_names=user_groups)
  ```

### Implications

1. The list from the `groups` claim is persisted verbatim into the auth DB as `group_name`. No stripping, splitting on `/`, dedup beyond the DB unique constraint, or transformation.
2. Group authorisation uses Python `in` against `OIDC_GROUP_NAME` / `OIDC_ADMIN_GROUP_NAME`. The configured allowlist values MUST match the emitted format exactly. Switching Keycloak to full-path means the allowlists also need to switch to full-path (e.g. `mlflow-admin` -> `/mlflow-admin`).
3. There is no `OIDC_GROUP_FILTER_REGEX`, prefix stripping, or post-processing toggle in the upstream code. If we want any transformation (e.g. strip leading `/`), we either fork or implement an `OIDC_GROUP_DETECTION_PLUGIN`.

## Keycloak side

The Group Membership protocol mapper has a boolean **Full group path** option (config key `full.path`). With it enabled, the token's `groups` claim contains paths like:

```json
"groups": ["/projectA/admins", "/projectB/admins", "/mlflow"]
```

With it disabled:

```json
"groups": ["admins", "admins", "mlflow"]
```

Configuration location: realm -> Client scopes (or directly on the `mlflow-test` client) -> Mappers -> the Group Membership mapper -> "Full group path" toggle.

## Current deployment state

`mlflow-deployment.yaml`:
- Realm: `drai`, client: `mlflow-test`.
- No `OIDC_GROUPS_ATTRIBUTE` set => uses default `"groups"`.
- No `OIDC_GROUP_NAME` set => uses default `["mlflow"]`.
- No `OIDC_ADMIN_GROUP_NAME` set => uses default `["mlflow-admin"]`.
- No `OIDC_GROUP_DETECTION_PLUGIN`.

So today, whatever Keycloak emits in `groups` is taken as truth, and only the literal strings `mlflow` / `mlflow-admin` count for access.

## Migration considerations

mlflow_auth DB lives in postgres at `mlflow-postgres-postgresql.mlflow.svc.cluster.local:5432/mlflow_auth`. Key tables (from `sqlalchemy_store.py`): `SqlGroup(group_name)` plus join tables for group-experiment / group-model / group-prompt / group-regex permissions. Renaming a group means updating `SqlGroup.group_name` and every FK reference (the schema appears to FK on `group_id`, so a single UPDATE to `group_name` should propagate, but this needs verification before touching prod data).

## Phase 1 audit (2026-05-26)

### Discovery endpoint
- Issuer: `https://keycloak.test.drai.auckland.ac.nz/realms/drai`
- Scopes supported (relevant): the standard set plus a few custom ones (names redacted). The presence of custom scopes signalled that this realm is shared with other workloads, which factored into the Phase 3 decision to use a dedicated mapper instead of editing the shared scope.
- Claims advertised: standard set (no `groups` listed). `claims_supported` in Keycloak is not exhaustive; group claims still flow via mappers.
- Keycloak version: not exposed by discovery doc; admin console serves resources via a hashed resource path (no version leak). **Needs confirmation from user via admin console "Server info" page or by inspecting the Keycloak pod image.**

### mlflow pod
- Image: `ghcr.io/drai-inn/ai-gpu-mlflow:v0.4.0`, running 99m, no restarts.
- `LOG_LEVEL=INFO` so the `User groups:` DEBUG line (auth.py:557) is not in logs. To capture a live groups claim sample we either bump `LOG_LEVEL=DEBUG` and re-roll, or call `userinfo_endpoint` directly with a test token.

### mlflow_auth DB snapshot

Groups table: 14 rows. Includes `mlflow` and `mlflow-admin` (the two relevant to this work). Other rows redacted.

Users: 5 total (4 admins, 1 standard). Identities redacted.

Collision smell: several rows had bare leaf names that looked like they could plausibly be either top-level groups or sub-group leaves whose parent path was stripped by `full.path = false`. This left it ambiguous whether the duplicate-collapse issue was already firing or merely anticipated. **User to confirm: does Keycloak actually have nested groups today, or is this preventative?**

Group-permission row counts:
| Table | Rows |
|-------|-----:|
| experiment_group_permissions | 1 |
| experiment_group_regex_permissions | 0 |
| registered_model_group_permissions | 0 |
| registered_model_group_regex_permissions | 0 |
| scorer_group_permissions | 0 |
| scorer_group_regex_permissions | 0 |
| gateway_endpoint_group_permissions | 0 |
| gateway_secret_group_permissions | 0 |
| gateway_model_definition_group_permissions | 0 |
| workspace_group_permissions | 0 |
| workspace_group_regex_permissions | 0 |

Total non-trivial permission rows tied to groups: **1**. Migration impact is essentially nil; wipe-and-rebuild is safe modulo recreating that single experiment permission.

### Phase 1 resolution
- Keycloak: version redacted; running in its own namespace.
- Access group full path (user-confirmed): `/mlflow`
- Admin group full path (user-confirmed): `/mlflow-admin`
- Current `full.path` value: inferred `false`, because rows in `mlflow_auth.groups` are bare leaf names (`mlflow`, `mlflow-admin`, ...) rather than slash-prefixed paths. To be visually confirmed in the admin console at the same time the toggle is flipped in Phase 3.
- Token Claim Name: `groups` (default `OIDC_GROUPS_ATTRIBUTE` is in use and group population already works -> the claim is named `groups`).
- Token channel: the mapper is attached at least to userinfo, since `mlflow-oidc-auth` reads userinfo and populate is succeeding.

### Decision: full-path values

| Env var | Old value (default) | New value |
|---------|---------------------|-----------|
| `OIDC_GROUP_NAME` | `["mlflow"]` | `["/mlflow"]` |
| `OIDC_ADMIN_GROUP_NAME` | `["mlflow-admin"]` | `["/mlflow-admin"]` |
| `OIDC_GROUPS_ATTRIBUTE` | `"groups"` (default) | set explicitly to `"groups"` so the contract is documented in the manifest |

Top-level groups, so the leading `/` is the entirety of the prefix. No transformation logic needed on the MLflow side.

## Sources

- mlflow-oidc-auth source: https://github.com/data-platform-hq/mlflow-oidc-auth (`main` as of 2026-05-26)
- Keycloak Group Membership Mapper docs: https://www.pulumi.com/registry/packages/keycloak/api-docs/openid/groupmembershipprotocolmapper/
- Keycloak OIDC group mapping reference: https://infisical.com/docs/documentation/platform/sso/keycloak-oidc/group-membership-mapping
