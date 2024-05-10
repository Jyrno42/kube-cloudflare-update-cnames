# Kube cloudflare update cnames sidecart container

This container subscribes to kube events and listens on update/creation of ingressroute objects. When one is found
it will check if the ingressroute exists in the cloudflare dns and makes sure it points to the correct host.

Deploy it to your kube cluster with:

1. Create the kube secret with the cloudflare api key based on `kube-secret.yaml`.

2. apply the deployment with:

```
kubectl apply -f kube-secret-real.yaml
```

3. Deploy the sidecart with:

```
kubectl apply -f kubernetes.yaml
```
