# AntiCapTrad platform architecture

Each component is an independently versioned repository under the `anticaptrad`
GitHub organization. `act-monorepo` is an aggregate commit manifest: its gitlinks
pin reviewed component revisions for local integration and for the copy mounted
under `~/codes/ores/k8s-cluster/remote/deployments/anticaptrad-monorepo`.

The cluster also owns the shared browser-scenario and NATS infrastructure. ACT
services consume those capabilities through authenticated HTTP contracts; they
do not expose browser drivers or require external callers to understand NATS.

## Aggregate layout

| Path | Repository | Role |
| --- | --- | --- |
| `apps/act-mcp-server.rs` | `act-mcp-server.rs` | Model Context Protocol server |
| `apps/act-api-server.rs` | `act-api-server.rs` | Public JSON/control-plane API |
| `apps/act-web-server.rs` | `act-web-server.rs` | Authenticated operator UI and web API |
| `apps/act-ai-server.ts` | `act-ai-server.ts` | AI-provider, render, and publishing orchestration |
| `packages/act-interfaces` | `act-interfaces` | Canonical schemas and cross-language contracts |
| `packages/act-clients` | `act-clients` | Polyglot SDKs generated from those contracts |
| `tests/act-e2e` | `act-e2e` | Cross-service and browser-scenario verification |
| `tools/act-sync` | `act-sync` | Explicit repository/reference synchronization |

`act-infra` remains standalone. Infrastructure is reconciled by its own app-of-
apps lifecycle and must not become an application-source gitlink.

## Services

| Repo | Stack | Role | Port |
| --- | --- | --- | --- |
| `act-api-server.rs` | Rust · Axum | JSON API, Google Apps Script control-plane adapter, and cluster-bridge client | 8080 |
| `act-web-server.rs` | Rust · Axum + SeaORM | Script/video operator UI and authenticated web API | 8080 |
| `act-mcp-server.rs` | Rust · Axum | Model Context Protocol (JSON-RPC) server | 8080 |
| `act-ai-server.ts` | Node.js · Fastify | Multi-provider script/video orchestration and YouTube integration | 3000 |
| `act-infra` | Kubernetes YAML | Deployments, Services, ConfigMaps, ExternalSecrets, and app-of-apps declarations | — |

## Operational contract

These invariants hold across the Rust and Node.js stacks. `act-e2e` should enforce
them so a new service cannot quietly diverge.

**Configuration comes from the environment.** No `.env` files and no `dotenv`.
Secrets arrive through Kubernetes Secret references; non-secret configuration
comes from ConfigMaps or explicit process variables.

**Probes are uniform and public.** Every service serves `GET /health` and
`GET /ready` as bounded JSON without credentials. Probes never disclose secret
values, provider payloads, rendered media paths, or account identifiers.

**Optional dependencies fail soft; authentication fails closed.** Missing NATS,
database, render, LLM, or YouTube dependencies are represented in readiness and
job state rather than causing restart loops. Missing or invalid auth material
denies protected requests.

**Shutdown is graceful and bounded.** SIGTERM drains in-flight work and stops new
jobs. A fixed deadline prevents stalled network clients or provider streams from
holding a rollout open indefinitely.

**OpenTelemetry is explicit.** Services create spans around owned operations and
propagate W3C context deliberately. Runtime module patching and broad automatic
instrumentation are not part of the platform contract. Prompt text, generated
scripts, video content, local paths, OAuth material, and upstream exception
payloads must never be attached to spans.

## Data and messaging

- **Postgres (Supabase)** is accessed through SeaORM by the Rust web/API layer.
  Schema changes live in versioned migrations and run as an explicit deployment
  operation.
- **The cluster HTTP-to-NATS bridge is the only external queue ingress.** ACT
  workloads submit named, allow-listed message operations over authenticated
  HTTP. The bridge owns NATS credentials, subject mapping, JetStream publish
  policy, retry limits, and audit spans.
- **No ACT HTTP route is enabled before its stream, consumer, bridge grant, and
  redelivery/DLQ tests exist.** This prevents a nominally healthy endpoint from
  accepting work that has nowhere durable to go.
- **Browser automation uses the authenticated scenario API** hosted in the
  cluster. Raw Playwright, Puppeteer/CDP, Selenium/WebDriver, and browser profile
  endpoints are never published.

## Authentication

The target product boundary is dual authentication:

1. Supabase-issued user JWTs for interactive sessions; and
2. Shared Auth product/delegation credentials for service-to-service and central
   session flows.

Both paths must normalize into one internal principal containing subject,
organization, scopes, auth source, and expiry. Audience, issuer, `nbf`, and
bounded leeway are mandatory; ambiguous or partially configured auth denies the
request. Shared Auth integration should use a versioned HTTP/client contract or a
publicly consumable package rather than an unauthenticated dependency on a
private Git repository.

The current web implementation already performs strict Supabase JWT checks, but
full Shared Auth normalization is still an implementation gate. It must land in
the authoritative service repositories with unit and cross-service E2E coverage
before the cluster marks ACT authentication ready.

## Script, media, and YouTube workflow

1. An authenticated operator creates a research brief and evidence record.
2. The AI server asks one or more configured providers for structured script and
   scene candidates. Provider capability, model, cost ceiling, and provenance are
   recorded without storing credentials in job payloads.
3. A render worker creates media into a confined job directory or object store.
4. Human review approves the exact script, sources, media hash, title,
   description, visibility, and target channel.
5. Publishing uses the official YouTube Data API or the account-owned Google Apps
   Script control plane. Test uploads default to `private`; broader visibility is
   a separate explicit transition.
6. Browser automation is reserved for an unsupported account workflow and must
   run through the authenticated scenario API with an allow-listed scenario.

A generated asset is not publishable merely because rendering succeeded. The
approval record must bind the final media digest and metadata so a changed file
cannot inherit an earlier approval.

## Known convergence gates

- normalize Supabase and Shared Auth principals in the Rust services;
- replace placeholder video generation with capability-aware asynchronous render
  adapters and cost ceilings;
- certify the Google Apps Script deployment against the `@AntiCapTrad` channel
  identity without logging tokens or raw account responses;
- create ACT JetStream streams/consumers and matching HTTP bridge grants before
  enabling queue-backed routes;
- add app-of-apps manifests only after image digests, probes, secret references,
  network policies, and exact-head tests are available.

## Testing

`act-e2e` owns cross-service, auth-source, approval, bridge, and browser-scenario
contracts. Cluster tests must verify denial behavior as carefully as success:
wrong audience/issuer, expired or future tokens, missing bridge grants, unknown
scenario names, changed media hashes, mismatched YouTube channel identity, and
attempts to publish without an explicit visibility approval.
