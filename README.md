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

## TODO

- build image automatically and push to registry
