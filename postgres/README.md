# mlflow postgres



```
cp mlflow-postgres-secret.yaml.example mlflow-postgres-secret.yaml

# edit mlflow-postgres-secret.yaml adding base64 encoded passwords

kubectl apply -f mlflow-postgres-secret.yaml

helm upgrade -i mlflow-postgres ./local-chart/postgresql-15.5.38.tgz -f mlflow-postgres-values.yaml -n mlflow
```
