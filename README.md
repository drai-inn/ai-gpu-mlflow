# MLflow

Create secret first:

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

## TODO

- switch to postgres and rdc object storage
- default user permissions
- build image automatically and push to registry, or install mlflow during entrypoint...
