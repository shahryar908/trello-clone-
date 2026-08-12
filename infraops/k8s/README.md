# tack — Kubernetes manifests

Local-first: everything below runs on a [kind](https://kind.sigs.k8s.io/) cluster.
Files are numbered because `kubectl apply -f .` applies them alphabetically, and
the Namespace has to exist before anything that lives in it.

| File               | Object                | Why it exists                                        |
| ------------------ | --------------------- | ---------------------------------------------------- |
| `00-namespace.yml` | Namespace             | one blast radius for the whole app                    |
| `01-config.yml`    | ConfigMap             | non-secret env (DB path, token lifetime)              |
| `02-secret.yml`    | Secret                | `SECRET_KEY` — placeholder, create the real one by CLI |
| `03-pvc.yml`       | PersistentVolumeClaim | disk that outlives the pod, holds `trello.db`         |
| `04-backend.yml`   | Deployment + Service  | API pod (1 replica — SQLite), stable in-cluster name  |
| `05-frontend.yml`  | Deployment + Service  | SPA pod                                              |
| `06-ingress.yml`   | 2× Ingress            | front door: `/api/*` → backend, everything else → SPA |
| `kind-cluster.yml` | kind config           | maps host ports 80/443 into the cluster               |

## One-time setup

```bash
kind create cluster --name tack --config infraops/k8s/kind-cluster.yml

# ingress controller (the thing that actually reads Ingress objects)
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait -n ingress-nginx --for=condition=ready pod \
  -l app.kubernetes.io/component=controller --timeout=180s
```

Add to `C:\Windows\System32\drivers\etc\hosts` (needs an admin editor):

```
127.0.0.1 tack.local
```

## Every deploy

```bash
# 1. build and publish images (the cluster pulls them from Docker Hub)
docker build -t shahryar371/trello-backend:latest ./backend
docker build -t shahryar371/trello-frontend:latest ./frontend
docker push shahryar371/trello-backend:latest
docker push shahryar371/trello-frontend:latest

# offline alternative — hand the images straight to the kind node instead:
#   kind load docker-image shahryar371/trello-backend:latest --name tack

# 2. apply
kubectl apply -f infraops/k8s/

# 3. real secret (do this once; overwrites the committed placeholder)
kubectl create secret generic backend-secret -n tack \
  --from-literal=SECRET_KEY=<64-hex key from backend/.env> \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deploy/backend -n tack
```

Open <http://tack.local>.

## Checking on it

```bash
kubectl get pods,svc,ingress,pvc -n tack
kubectl logs -n tack deploy/backend -f
kubectl describe pod -n tack -l app=backend   # why a pod is stuck/crashing
kubectl exec -n tack deploy/backend -- ls -l /data   # is the DB file on the volume?
```

Delete everything: `kubectl delete namespace tack` (the PVC goes with it — that
deletes the database).

## Known constraints

- **`replicas: 1` on the backend is not a placeholder.** SQLite allows one
  writer; a second pod on the same volume corrupts the file. Scaling out is
  what would force a move to Postgres.
- **The Secret is base64, not encrypted.** Anyone with repo or cluster read
  access can decode it. Sealed Secrets (stage 6) is the fix.
- **The frontend's API URL is baked in at build time**, not read from the
  environment. Vite inlines `import.meta.env` during `bun run build`, so
  pointing the SPA somewhere else means rebuilding the image, not editing a
  ConfigMap.
