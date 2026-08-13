# Monitoring

Prometheus scrapes, Alertmanager notifies, Grafana draws. All three arrive as
one Helm chart (`kube-prometheus-stack`), deployed by ArgoCD like everything
else — so the chart version in git *is* the version running.

```
infraops/monitoring/
├── 00-stack.yml      ArgoCD Application -> kube-prometheus-stack 88.3.0 (Helm)
├── 01-rules.yml      ArgoCD Application -> the rules/ folder below
├── install.sh        run once on the box
└── rules/
    ├── servicemonitor.yml   what to scrape
    ├── alerts.yml           what to alert on
    └── dashboard.yml        what to draw
```

## Why three Applications instead of one

`tack` (the app), `monitoring` (the chart), `tack-monitoring` (our rules).

The important separation is the first one. If the ServiceMonitor and
PrometheusRule lived in `infraops/k8s/`, then on any cluster without the
Prometheus CRDs installed the **app's** Application would go Degraded and stop
deploying. Monitoring must never be able to break the thing it monitors.

The second separation is ownership: the chart is upstream code on someone
else's release schedule, the rules are yours. Different reasons to roll back.

On a fresh cluster `tack-monitoring` fails its first sync — the CRDs are still
being installed — and succeeds on retry. That is why it has a `retry` block.

## Install

```bash
./infraops/monitoring/install.sh
```

It creates the namespace, generates a Grafana password into a Secret (never
committed, same reason as `backend-secret`), applies both Applications, and
waits for the operator. Re-running it is safe.

## Access

Nothing here is exposed through the Ingress. An open Grafana is a full read of
your infrastructure and Prometheus has no login at all — both stay behind SSH.

```bash
# password
kubectl get secret grafana-admin -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d; echo

# from your laptop
ssh -i key.pem -L 3000:localhost:3000 ubuntu@<ip> \
  'kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml -n monitoring port-forward svc/kps-grafana 3000:80'
```

Then <http://localhost:3000>, user `admin`. The dashboard is **tack — service
overview**; it appears by itself, imported from `rules/dashboard.yml`.

## Verify it actually works

Three things have to be true, and they fail independently:

```bash
# 1. the app is exposing metrics at all
kubectl -n tack exec deploy/backend -- python -c \
  "import urllib.request;print(urllib.request.urlopen('http://localhost:9100/metrics').read()[:200])"

# 2. Prometheus found the target  (state must be "up")
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090 &
curl -s 'localhost:9090/api/v1/targets?state=active' | grep -o '"job":"backend"[^}]*'

# 3. the rules loaded
curl -s localhost:9090/api/v1/rules | grep -o '"name":"Tack[A-Za-z]*"'
```

Then generate some traffic and watch the graphs move:

```bash
for i in $(seq 1 200); do curl -s -o /dev/null http://<ip>/api/health; done
```

## What is measured

The app emits these itself (`backend/app/metrics.py`), on port **9100** — a
separate port from the API, so the Ingress cannot route to it and `/metrics`
stays private.

| Metric | Type | Reads as |
|---|---|---|
| `tack_http_requests_total{method,path,status}` | counter | every request, labelled by route **template** |
| `tack_http_request_duration_seconds` | histogram | latency, bucketed for percentiles |
| `tack_websocket_connections` | gauge | board sockets open right now |
| `tack_websocket_rooms` | gauge | boards with at least one viewer |
| `tack_comments_created_total` | counter | comments sent over the socket |
| `tack_signups_total` | counter | accounts created |

Counter vs gauge is the distinction to be able to explain: a counter only goes
up and you take `rate()` of it; a gauge is a reading and you look at it
directly. Asking for `rate(tack_websocket_connections)` is meaningless.

The rest — CPU, memory, restarts, disk, node health — comes free from
`node-exporter` (the machine) and `kube-state-metrics` (the objects).

## Alerts

| Alert | Fires when | Why it exists |
|---|---|---|
| `TackBackendDown` | scrape fails 2m | the obvious one |
| `TackBackendTargetMissing` | target absent 5m | `up == 0` **cannot** fire if the target vanishes entirely. Every `up == 0` alert needs an `absent()` partner or you get silence at the worst moment |
| `TackDeploymentDegraded` | ready < desired 10m | a rollout that never finished |
| `TackPodRestarting` | >2 restarts / 15m | OOMKill or a failing liveness probe |
| `TackHighErrorRate` | 5xx ratio > 5% for 5m | a **ratio**, so it means the same at any traffic level |
| `TackHighLatency` | p95 > 500ms for 10m | p95, not average — averages hide the tail users notice |
| `TackDataVolumeFillingUp` | PVC > 85% for 15m | SQLite lives there; full disk = failed writes |
| `NodeMemoryLow` / `NodeDiskFillingUp` | < 12% / < 15% | t2.medium is small and this stack is a big share of it |

Check them in the UI: Alertmanager on port 9093, or Prometheus → Alerts.

To test one for real, scale the backend to zero and wait two minutes:

```bash
kubectl -n tack scale deploy/backend --replicas=0   # TackBackendDown fires
kubectl -n tack scale deploy/backend --replicas=1
```

(ArgoCD `selfHeal` will scale it back on its own within a few minutes, which is
itself worth watching.)

## Memory, honestly

t2.medium is 4 GiB and this is a tight fit:

| | limit |
|---|---|
| k3s + system | ~700 Mi |
| ArgoCD | ~600 Mi |
| tack (backend + frontend) | ~640 Mi |
| Prometheus | 1 Gi |
| Grafana | 256 Mi |
| Alertmanager | 128 Mi |
| operator | 256 Mi |
| kube-state-metrics + node-exporter | 192 Mi |

Limits total more than the box has. That is normal — limits are ceilings, not
reservations, and the `requests` are what the scheduler actually adds up. But
if you see `OOMKilled` on the Prometheus pod, the options in order are:

1. drop `retention` to `1d`
2. `alertmanager.enabled: false` (Prometheus still evaluates rules; you just
   lose grouping and routing)
3. move to t3.large

## Things that will trip you up

| Symptom | Cause |
|---|---|
| ServiceMonitor exists, target never appears | `serviceMonitorSelectorNilUsesHelmValues` — Prometheus only adopts monitors with the Helm release label unless you set it `false`. Already set in `00-stack.yml` |
| Target appears but is `down` | the ServiceMonitor's `port:` must be the Service port **name** (`metrics`), not the number |
| Sync fails, `metadata.annotations: Too long` | the Prometheus CRDs exceed the client-side-apply annotation limit. `ServerSideApply=true` fixes it, already set |
| Alerts firing for etcd / scheduler / kube-proxy | k3s runs the control plane in one process; those targets do not exist. Disabled in the values |
| Grafana forgot my dashboard edits | by design — persistence is off. Dashboards come from `rules/dashboard.yml`. Edit, export JSON, commit |

## Not done yet

- **Alertmanager routing.** Alerts fire into the UI and stop there. Next: a
  Slack or email receiver, so an alert reaches a human who is not looking.
- **Logs.** Loki + Promtail. Metrics tell you *that* it broke; logs tell you
  *why*. This is the highest-value next addition.
- **Traces.** OpenTelemetry + Tempo. Probably too much for this box.
- **Blackbox probing.** Prometheus currently checks the app from *inside* the
  cluster. `blackbox-exporter` hitting the public URL would catch an Ingress or
  DNS failure that every internal check calls healthy.
- **An SLO.** e.g. 99.5% of requests under 300ms over 30 days, with a burn-rate
  alert. That is the step from "graphs" to "a promise you can be held to".
- **k6 load test in CI**, to prove the SLO holds before a release ships.
