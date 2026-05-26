# MLflow

Create the namespace first:

```
kubectl apply -f mlflow-namespace.yaml
```

Install postgres - go to postgres sub directory and follow instructions there.

Create the secret:

```
cp mlflow-secret.yaml.example mlflow-secret.yaml
# edit mlflow-secret.yaml
kubectl apply -f mlflow-secret.yaml
```

Create the deployment and ingress:

```
kubectl apply -f mlflow-deployment.yaml
kubectl apply -f mlflow-certificate.yaml
kubectl apply -f mlflow-ingress.yaml
```

## Keycloak group claim

The `mlflow-test` client must emit groups as **full paths** (leading slash) so two groups with the same leaf name under different parents (e.g. `/projectA/admins` and `/projectB/admins`) do not collapse into a single MLflow group row.

Required Keycloak config (realm `drai`, client `mlflow-test`):

- A Group Membership protocol mapper on the client's dedicated scope with:
  - `Token Claim Name = groups`
  - `Full group path = ON`
  - `Add to userinfo = ON` (mlflow-oidc-auth reads userinfo)
- Do not also attach a shared client scope that emits a bare-name `groups` claim. If both fire, the userinfo `groups` list ends up with both forms and the auth DB persists duplicates.

The deployment's `OIDC_GROUP_NAME` and `OIDC_ADMIN_GROUP_NAME` env vars must match the emitted format. Current values are `/mlflow` (access) and `/mlflow-admin` (admin). They are matched against the claim with a literal `in`, so bare-name values will not authorise users when full paths are emitted.

If the mapper is reconfigured to drop the leading slash, also strip the slash from those env vars and wipe the `groups`, `user_groups`, and `*_group_permissions` tables in `mlflow_auth` so existing rows do not coexist with newly-written ones.

## Container image

Built by `.github/workflows/build_container.yml` and published to `ghcr.io/drai-inn/ai-gpu-mlflow`. Pushing a `v*` git tag produces a versioned image tag plus `:latest`; pushes to `main` produce a `:main` floating tag.
