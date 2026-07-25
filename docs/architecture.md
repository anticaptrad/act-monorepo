# AntiCapTrad platform architecture

Each service is its own git repository under `~/codes/anticaptrad/`. The backend
services deploy to the Kubernetes cluster at `~/codes/ores/k8s-cluster`, which
also hosts the shared browser-automation and NATS infrastructure they depend on.

## Services

| Repo | Stack | Role | Port |
| --- | --- | --- | --- |
| `act-api-server.rs` | Rust · axum | HTTP API + NATS event-bus bridge | 8080 |
| `act-web-server.rs` | Rust · axum + sea-orm | Supabase-authenticated web API | 8080 |
| `act-mcp-server.rs` | Rust · axum | Model Context Protocol (JSON-RPC) server | 8080 |
| `act-ai-server.ts` | Node · Fastify | Multi-provider LLM, video, YouTube publishing | 3000 |
| `act-infra` | k8s YAML | Deployments, Services, ConfigMaps | — |
| `act-e2e` | Node ESM | End-to-end tests (see its `docs/`) | — |
| `act-clients`, `act-interfaces`, `act-sync` | — | Shared clients, interfaces, sync | — |

Repository naming uses the **dotted** convention, `act-<name>.<lang>`. Earlier
`act-<name>-<lang>` duplicates were consolidated into their dotted counterparts;
see [../AUDIT.md](../AUDIT.md).

## Operational contract

These invariants hold across both the Rust and Node stacks, and `act-e2e`'s
`platform-contracts` suite enforces them so a new service cannot quietly diverge.

**Configuration comes from the environment.** No `.env` files — `dotenv` is
blacklisted platform-wide (see any repo's `agents.md`). Secrets arrive as a k8s
Secret via `envFrom`; non-secret config as a ConfigMap.

**Probes are uniform and public.** Every service serves `GET /health`
(`{"status":"ok"}`) and `GET /ready`, as JSON, without credentials — the kubelet
sends no `Authorization` header.

**Optional dependencies fail soft; auth fails closed.** A missing NATS broker,
database, or LLM credential must not stop a service answering probes: readiness
*reports* dependency state but never gates on it, so a dependency outage cannot
cascade into a rolling restart. Auth is the deliberate exception — an
unconfigured signing secret denies every protected request rather than allowing
them.

**Shutdown is graceful and bounded.** SIGTERM drains in-flight work, then the
process exits. The drain has a deadline, because a client that never reads its
response body keeps a connection active and would otherwise hold the pod open
until the kubelet SIGKILLed it, stalling the rollout.

## Data and messaging

- **Postgres (Supabase)** via sea-orm, owned by `act-web-server.rs`. The schema
  is a migration crate (`migration/`), applied with
  `cargo run -p migration -- up`.
- **NATS** is the event bus. `act-api-server.rs` subscribes to `act.events.>`.
  The connection is optional at boot and reconnects on its own.
- **OpenTelemetry** is initialised in every service, exporting OTLP when
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set and falling back to console tracing
  otherwise.

## Auth

`act-web-server.rs` verifies Supabase-issued HS256 JWTs. Beyond signature and
`exp`, three defaults in `jsonwebtoken` needed tightening because each accepted
a token that should not authenticate:

- `nbf` is not validated by default — a not-yet-valid token was accepted.
- Audience matching is **skipped entirely** when the token carries no `aud`
  claim, so a token minted for another service authenticated. `aud` is therefore
  a required claim, not an optional one.
- The 60s expiry leeway is wider than needed; it is now 5s and configurable.

Issuer pinning is available via `SUPABASE_JWT_ISS`.

## Testing

`act-e2e` covers the platform end to end and is layered by what owns the thing
under test, since that determines which failures are observable at all. See
[act-e2e/docs/testing-architecture.md](../../act-e2e/docs/testing-architecture.md)
and, for the deployed clusters,
[act-e2e/docs/cluster-browser-e2e.md](../../act-e2e/docs/cluster-browser-e2e.md).

The cluster deliberately does **not** expose raw Playwright/CDP/WebDriver
endpoints — an open one is a remote-control primitive reachable from inside the
cluster. All three drivers sit behind one authenticated scenario API on
`dd-browser-test-server`, which is what the cluster test layer drives.
