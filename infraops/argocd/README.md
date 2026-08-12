# ArgoCD (GitOps CD)

Before: you SSH'd to the box and ran `kubectl apply`.
After: you push to `main` and the cluster changes itself.

ArgoCD runs *inside* the cluster, watches `infraops/k8s/` on the repo, and
continuously reconciles the `tack` namespace to match it. Nothing else needs
cluster credentials — which is the actual security win, and why CI never gets
a kubeconfig in this design.

## Install

```bash
# on the k3s box
bash infraops/argocd/install.sh
```

Takes a few minutes on a t2.medium. It prints the generated admin password —
save it.

## Opening the UI

The app's Ingress already owns port 80 with a hostless rule, so ArgoCD is not
exposed publicly. Reach it over an SSH tunnel instead — no extra attack
surface, no second Ingress to secure:

```bash
# on the box
kubectl port-forward -n argocd svc/argocd-server 8080:443

# on your laptop
ssh -i key.pem -L 8080:localhost:8080 ubuntu@<elastic-ip>
```

Then browse <https://localhost:8080> (self-signed cert warning is expected),
user `admin`.

## The demo

```bash
# on your laptop
# edit infraops/k8s/05-frontend.yml — say replicas: 1 -> 2
git commit -am "scale frontend to 2"
git push
```

Within ~3 minutes (ArgoCD's default poll interval) the second pod appears. No
SSH, no kubectl. Watch it on the box with `kubectl get pods -n tack -w`, or in
the UI.

Try the other half too — change something by hand:

```bash
kubectl scale deploy/frontend -n tack --replicas=5
```

ArgoCD puts it back. That's `selfHeal: true`: the cluster is not allowed to
drift from git, even when you're the one drifting it.

## Why the Secret isn't in git

`infraops/k8s/02-secret.yml` was deleted when ArgoCD came in. With
`selfHeal: true`, ArgoCD would have overwritten your real `SECRET_KEY` with the
placeholder from the file every few minutes, breaking every JWT the app had
issued.

So `backend-secret` is created out-of-band and ArgoCD leaves it alone (it only
manages objects it finds in git):

```bash
kubectl create secret generic backend-secret -n tack \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --dry-run=client -o yaml | kubectl apply -f -
```

This is the gap **Sealed Secrets** closes: it encrypts the value with a key
only this cluster holds, so the encrypted file *is* safe to commit and the
secret rejoins the GitOps flow. That's the next thing to add here.

## Known gaps

- **`:latest` image tags.** ArgoCD reconciles *manifests*, and the manifest
  doesn't change when you push a new image with the same tag — so app code
  changes still won't deploy themselves. The fix is CI writing an immutable
  `:<git-sha>` tag into the manifest, which makes the commit itself the deploy.
  That lands with the CI stage.
- **Polling, not push.** Default reconcile is every 3 minutes. A repo webhook
  makes it instant.
- **UI is tunnel-only.** Fine for one operator; a team would need an Ingress
  with real auth and TLS.
