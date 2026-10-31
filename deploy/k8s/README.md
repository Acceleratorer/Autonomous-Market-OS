# Kubernetes runtime

This manifest is a private, single-replica development shape. It keeps the
Python gateway and Next.js operator in the same Pod so Python can remain bound
to `127.0.0.1:8787`. The only Kubernetes Service is an internal `ClusterIP`
for Next.js on port `3000`; there is no Ingress, LoadBalancer, NodePort,
provider credential, or mutation route.

Build the local images from the repository root:

```bash
docker build -f deploy/docker/python.Dockerfile -t autonomous-market-os/python:local .
docker build -f deploy/docker/next.Dockerfile -t autonomous-market-os/next:local .
```

For kind or Minikube, load both images into the cluster before applying:

```bash
kubectl apply -f deploy/k8s/market-os.yaml
kubectl -n market-os port-forward service/market-os 3000:3000
```

The `emptyDir` runtime volume is intentionally non-durable for local use.
Replace it with an encrypted, access-controlled persistent volume and add the
approved Tailscale/private ingress controls before treating this as a
promotion candidate. The owner-approved U5.5 production path remains the
Linux VM + systemd + Tailscale Serve package under `deploy/u5-5/`.
