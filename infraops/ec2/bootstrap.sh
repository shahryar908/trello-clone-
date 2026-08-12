#!/usr/bin/env bash
# Turns a fresh Ubuntu 22.04/24.04 EC2 instance into a single-node Kubernetes
# cluster ready for the manifests in infraops/k8s/.
#
#   scp -i key.pem infraops/ec2/bootstrap.sh ubuntu@<ip>:~
#   ssh -i key.pem ubuntu@<ip> 'bash bootstrap.sh'
#
# Safe to re-run.
set -euo pipefail

echo "==> system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq curl

echo "==> k3s (single-node Kubernetes)"
# --disable=traefik: k3s ships Traefik, but our Ingress objects use
#   nginx-specific annotations (rewrite-target, proxy timeouts), so we install
#   ingress-nginx instead and keep one mental model across kind/EC2/EKS.
# --write-kubeconfig-mode=644: lets the ubuntu user run kubectl without sudo.
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik --write-kubeconfig-mode=644" sh -

echo "==> waiting for the node to be Ready"
until sudo k3s kubectl get nodes 2>/dev/null | grep -q ' Ready '; do sleep 3; done

# k3s puts its kubeconfig here rather than the usual ~/.kube/config
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "==> ingress-nginx"
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/ingress-nginx/main/deploy/static/provider/baremetal/deploy.yaml

# baremetal provider exposes the controller as NodePort. On a single EC2 box we
# want it on the real ports 80/443, so switch the Service to hostPort-style
# access by patching it to LoadBalancer — k3s's built-in servicelb then binds
# the node's ports directly.
kubectl patch svc ingress-nginx-controller -n ingress-nginx \
  -p '{"spec":{"type":"LoadBalancer"}}'

kubectl wait -n ingress-nginx --for=condition=ready pod \
  -l app.kubernetes.io/component=controller --timeout=300s

echo
echo "==> done. Node status:"
kubectl get nodes
echo
echo "Next:"
echo "  kubectl apply -f k8s/            # copy infraops/k8s up first"
echo "  kubectl create secret generic backend-secret -n tack \\"
echo "    --from-literal=SECRET_KEY=<64-hex key> --dry-run=client -o yaml | kubectl apply -f -"
