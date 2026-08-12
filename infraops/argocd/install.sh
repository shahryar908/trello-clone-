#!/usr/bin/env bash
# Installs ArgoCD and points it at this repo. Run on the k3s box.
#
#   bash infraops/argocd/install.sh
#
# Safe to re-run.
set -euo pipefail

export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}

# Pinned, not "stable" — that branch is a moving target and would silently
# change what you install between runs.
ARGOCD_VERSION=v3.5.0

echo "==> installing ArgoCD ${ARGOCD_VERSION}"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f \
  "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

echo "==> waiting for the API server (a few minutes on a small box)"
kubectl wait -n argocd --for=condition=available deploy/argocd-server --timeout=600s

echo "==> registering the tack application"
kubectl apply -f "$(dirname "$0")/application.yml"

echo
echo "admin password:"
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
echo
echo
echo "To open the UI, from your LAPTOP:"
echo "  ssh -i key.pem -L 8080:localhost:8080 ubuntu@<elastic-ip>"
echo "  # then on the box:"
echo "  kubectl port-forward -n argocd svc/argocd-server 8080:443 --address 0.0.0.0"
echo "  # browse https://localhost:8080  (user: admin)"
