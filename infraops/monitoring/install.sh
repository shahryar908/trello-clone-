#!/usr/bin/env bash
# Installs the monitoring stack. Run once, on the EC2 box, after ArgoCD is up.
#
#   ./infraops/monitoring/install.sh
#
# Safe to re-run: it creates nothing that already exists and never overwrites
# the Grafana password.
set -euo pipefail

# -e  exit on the first failing command
# -u  a typo'd variable name is an error, not an empty string
# -o pipefail  a failure anywhere in a pipe fails the whole pipe

export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> namespace"
# The idempotent apply pattern: render the object, then apply it. `kubectl
# create` alone fails the second time and takes the script down with -e.
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

echo "==> Grafana admin password"
if kubectl get secret grafana-admin -n monitoring >/dev/null 2>&1; then
  echo "    secret already exists — leaving it alone"
else
  # Not in git, for the same reason backend-secret isn't: ArgoCD's selfHeal
  # would keep resetting a real password back to the committed placeholder.
  GRAFANA_PASSWORD="$(openssl rand -base64 24)"
  kubectl create secret generic grafana-admin \
    --namespace monitoring \
    --from-literal=admin-user=admin \
    --from-literal=admin-password="$GRAFANA_PASSWORD"
  echo "    generated a new password"
fi

echo "==> Applications"
kubectl apply -f "${HERE}/00-stack.yml"
kubectl apply -f "${HERE}/01-rules.yml"

echo "==> waiting for the operator (this pulls ~1GB of images, be patient)"
# `kubectl wait` fails if the resource does not exist yet, so poll for it first.
until kubectl get deploy -n monitoring -l app=kube-prometheus-stack-operator 2>/dev/null | grep -q operator; do
  echo "    still syncing..."
  sleep 15
done

kubectl wait --namespace monitoring \
  --for=condition=Available deployment \
  --selector app=kube-prometheus-stack-operator \
  --timeout=600s

echo
echo "==> done"
echo
echo "Grafana password:"
echo "  kubectl get secret grafana-admin -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d; echo"
echo
echo "Open Grafana (run this on your LAPTOP, not the box):"
echo "  ssh -i <key.pem> -L 3000:localhost:3000 ubuntu@<public-ip> \\"
echo "      'kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml -n monitoring port-forward svc/kps-grafana 3000:80'"
echo "  then http://localhost:3000  (user: admin)"
echo
echo "Same idea for Prometheus itself, on 9090:"
echo "  ... -L 9090:localhost:9090 ... port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090"
echo
echo "Neither is exposed through the Ingress on purpose: an open Grafana is a"
echo "full read of your infrastructure, and Prometheus has no login at all."
