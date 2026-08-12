# Running tack on EC2 (k3s)

Same manifests as the kind cluster — `infraops/k8s/` is deliberately portable.
The only environment-specific thing is the Ingress, and it has no `host:` rule,
so it answers on whatever hostname the instance has.

## Instance settings

| Setting  | Value                          | Why                                                                 |
| -------- | ------------------------------ | ------------------------------------------------------------------- |
| Type     | t2.medium (2 vCPU, 4GB)        | k3s + ingress + app ≈ 1.1GB; leaves room for Prometheus and ArgoCD    |
| OS       | Ubuntu 22.04 or 24.04 LTS      | what `bootstrap.sh` assumes                                          |
| Storage  | 30GB gp3                       | 8GB is not enough once images accumulate; 30GB is the free-tier cap   |
| Elastic IP | allocate and associate       | without one the public IP changes every stop/start                    |

### Security group

| Port | Source        | Why                                    |
| ---- | ------------- | -------------------------------------- |
| 22   | **your IP only** | SSH. Never `0.0.0.0/0`.             |
| 80   | 0.0.0.0/0     | the Ingress                            |
| 443  | 0.0.0.0/0     | for later, once TLS is set up          |

Do **not** open 8000 or 8080. Everything enters through the Ingress — that's
the point of having one.

## Deploy

```bash
# from your laptop
scp -i key.pem -r infraops/ec2/bootstrap.sh infraops/k8s ubuntu@<ip>:~

# on the box
bash bootstrap.sh
kubectl apply -f k8s/
kubectl create secret generic backend-secret -n tack \
  --from-literal=SECRET_KEY=<64-hex key from backend/.env> \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deploy/backend -n tack

kubectl get pods,svc,ingress,pvc -n tack
```

Then open `http://<elastic-ip>` in a browser.

Images are pulled from Docker Hub (`shahryar371/trello-backend:latest`,
`shahryar371/trello-frontend:latest`), so nothing needs to be copied up.

## Driving it from your laptop

```bash
scp -i key.pem ubuntu@<ip>:/etc/rancher/k3s/k3s.yaml ~/.kube/tack-ec2.yaml
# edit that file: replace 127.0.0.1 with the Elastic IP
export KUBECONFIG=~/.kube/tack-ec2.yaml
```

The k3s API server listens on 6443. Either open it to your IP only in the
security group, or tunnel it: `ssh -i key.pem -L 6443:localhost:6443 ubuntu@<ip>`.

## Cost

**t2.medium is not free tier** (free tier is t2/t3.micro only) — roughly
**$30–35/month** if left running, plus ~$3.60/month for the public IPv4 address,
which AWS charges for whether or not the instance is running. `Stop` the
instance when you're not using it: you keep the disk and the Elastic IP, and
pay only for storage.

## Known gaps

- **HTTP only.** JWTs travel in the clear. Real TLS needs a domain —
  Let's Encrypt will not issue certs for `*.amazonaws.com` hostnames. A ~$2/yr
  domain plus cert-manager closes this.
- **Single node.** No high availability; the box is the cluster.
- **SQLite on a local-path PVC** lives on this instance's EBS volume. Terminate
  the instance and the database goes with it.
