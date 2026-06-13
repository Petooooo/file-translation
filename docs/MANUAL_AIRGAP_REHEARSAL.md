# Manual Airgap Operator Rehearsal

This rehearsal prepares a k3d cluster so an operator can install `file-translation` manually with their own `values.closed.yaml`, runtime Secret, and Helm or ArgoCD workflow.

It does not install the `file-translation` app.

## Rehearsal Modes

Strict bundle-only receiver:

- Uses only images and files included in the generated airgap bundle.
- Does not require a source checkout after extracting the bundle.
- Installs the packaged chart and runs health smoke from bundle-local scripts.
- Use this mode to prove that the application bundle can be received and run without external pulls.

Manual operator rehearsal:

- Uses the airgap bundle for `file-translation` app images and chart material.
- Keeps `file-translation` app images on `imagePullPolicy: Never`.
- Prepares PostgreSQL, RabbitMQ, MinIO, pgAdmin, and ArgoCD so an operator can install the app manually later.
- Allows pgAdmin and ArgoCD online install only for local operator convenience.

pgAdmin/ArgoCD online install is for local manual rehearsal only.
In a real closed network, these images/manifests must already exist in the internal registry or be separately mirrored.

## Cluster

Target cluster:

```bash
k3d cluster create file-translation-manual-airgap \
  --agents 1 \
  --image rancher/k3s:v1.32.13-k3s1 \
  --api-port 127.0.0.1:6555
```

Namespaces:

- `file-translation-deps`
- `file-translation`
- `argocd`

K9s:

```bash
kubectl config use-context k3d-file-translation-manual-airgap
k9s --context k3d-file-translation-manual-airgap
```

Check these namespaces in k9s:

- `file-translation-deps`
- `file-translation`
- `argocd`

## Bundle Import

The `file-translation` images and chart should be loaded from the airgap bundle:

```bash
scripts/airgap/check-airgap-bundle.sh /tmp/file-translation-airgap-test
rm -rf /tmp/file-translation-manual-airgap-bundle
mkdir -p /tmp/file-translation-manual-airgap-bundle
tar -xzf /tmp/file-translation-airgap-test.tar.gz -C /tmp/file-translation-manual-airgap-bundle
cd /tmp/file-translation-manual-airgap-bundle/file-translation-airgap-test
./scripts/airgap/check-airgap-bundle.sh .
LOAD_TARGET=k3d K3D_CLUSTER=file-translation-manual-airgap ./scripts/airgap/load-airgap-bundle.sh .
```

The application install later should use:

```yaml
global:
  imagePullPolicy: Never
```

This verifies that missing application images fail as `ErrImageNeverPull` instead of silently pulling from an external registry.

## Infra Install

Install only the manual rehearsal infra:

```bash
ALLOW_ONLINE_INFRA_PULL=1 scripts/dev/manual-airgap-infra-install.sh
```

Without `ALLOW_ONLINE_INFRA_PULL=1`, the script installs PostgreSQL, RabbitMQ, and MinIO, then skips pgAdmin and ArgoCD with an explanatory warning.

Local dependency images:

- PostgreSQL: `postgres:16-alpine`
- RabbitMQ: `rabbitmq:3.13-management`
- MinIO: `minio/minio:RELEASE.2025-02-07T23-21-09Z`

These use `imagePullPolicy: Never` by default and should already be imported into the k3d cluster from the bundle.

Operator convenience tools:

- pgAdmin image defaults to `dpage/pgadmin4:latest`; override with `PGADMIN_IMAGE`.
- ArgoCD defaults to `ARGOCD_VERSION=v3.4.1`; override with `ARGOCD_VERSION`.
- Both require `ALLOW_ONLINE_INFRA_PULL=1` in this local manual rehearsal mode.

## Port Forwarding

Start forwards:

```bash
scripts/dev/manual-airgap-port-forward.sh
```

Stop forwards:

```bash
scripts/dev/manual-airgap-stop-port-forward.sh
```

PID directory:

```text
/tmp/file-translation-manual-airgap-portforwards
```

Localhost port map:

| Component | Local endpoint | Kubernetes service |
| --- | --- | --- |
| MinIO API | `http://localhost:19000` | `file-translation-deps/manual-minio:9000` |
| MinIO Console | `http://localhost:19001` | `file-translation-deps/manual-minio:9001` |
| RabbitMQ AMQP | `localhost:25672` | `file-translation-deps/manual-rabbitmq:5672` |
| RabbitMQ Web | `http://localhost:15672` | `file-translation-deps/manual-rabbitmq:15672` |
| PostgreSQL | `localhost:15432` | `file-translation-deps/manual-postgresql:5432` |
| pgAdmin Web | `http://localhost:15050` | `file-translation-deps/manual-pgadmin:80` |
| ArgoCD Web | `https://localhost:18080` | `argocd/argocd-server:443` |

## Dependency Endpoints

Use these values when writing `values.closed.yaml` manually:

```yaml
postgresql:
  bundled: false
  host: manual-postgresql.file-translation-deps.svc.cluster.local
  port: 5432

rabbitmq:
  bundled: false
  host: manual-rabbitmq.file-translation-deps.svc.cluster.local
  port: 5672

minio:
  bundled: false
  endpoint: http://manual-minio.file-translation-deps.svc.cluster.local:9000

secrets:
  existingSecret: file-translation-secrets

global:
  imagePullPolicy: Never
```

Create the application Secret yourself before installing the app. Use real values only outside Git-tracked files:

```bash
kubectl -n file-translation create secret generic file-translation-secrets \
  --from-literal=RABBITMQ_USERNAME='<rabbitmq-username>' \
  --from-literal=RABBITMQ_PASSWORD='<rabbitmq-password>' \
  --from-literal=MINIO_ACCESS_KEY='<minio-access-key>' \
  --from-literal=MINIO_SECRET_KEY='<minio-secret-key>' \
  --from-literal=POSTGRES_USER='<postgres-user>' \
  --from-literal=POSTGRES_PASSWORD='<postgres-password>' \
  --from-literal=TRANSLATION_API_TOKEN='<translation-api-token>' \
  --from-literal=EMAIL_API_TOKEN='<email-api-token>' \
  --from-literal=EMAIL_API_USERNAME='<email-api-username>' \
  --from-literal=EMAIL_API_PASSWORD='<email-api-password>'
```

## Validation

Minimum checks:

```bash
kubectl get nodes
kubectl get pods -n file-translation-deps
kubectl get pods -n argocd
kubectl get svc -n file-translation-deps
kubectl get svc -n argocd
```

After port-forwarding:

```bash
curl -I http://localhost:19001 || true
curl -I http://localhost:15672 || true
curl -I http://localhost:15050 || true
curl -k -I https://localhost:18080 || true
nc -vz localhost 25672
nc -vz localhost 15432
curl -I http://localhost:19000/minio/health/live || true
```

Do not install the `file-translation` app as part of this setup. The next step belongs to the operator: write `values.closed.yaml`, create `file-translation-secrets`, then install with Helm or create an ArgoCD Application that points at an internal Git or chart source.
