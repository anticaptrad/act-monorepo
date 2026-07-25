# AntiCapTrad — Consolidation & Hardening Audit

Consolidated the duplicate service repos, then audited, hardened, and augmented
every service. Rust crates were verified with `cargo check`, the TypeScript
service with `tsc`, the k8s manifests with `kubectl apply --dry-run=client`, and
the e2e suite with the Node test runner.

## 1. Repository consolidation

Another agent had created `act-<name>-<lang>` repos alongside the canonical
`act-<name>.<lang>` repos (the ones carrying real git history + GitHub remotes).
The `-<lang>` copies held unique files the canonical repos lacked. Merged those
in, then moved the duplicates out of the workspace (no `rm`, per `agents.md`).

| Duplicate (removed) | Merged into | Brought over |
| --- | --- | --- |
| `act-api-server-rs` | `act-api-server.rs` | Dockerfile, `agents.md`, AI-rules dirs, **NATS integration** |
| `act-mcp-server-rs` | `act-mcp-server.rs` | Dockerfile, `agents.md`, AI-rules dirs |
| `act-web-server-rs` | `act-web-server.rs` | Dockerfile, `agents.md`, AI-rules dirs |
| `act-ai-server-ts` | `act-ai-server.ts` | Dockerfile, `agents.md`, AI-rules dirs, **OTel + pipeline logic** |

## 2. Findings & fixes

### Cross-cutting
- **Blacklisted `dotenv` in use** — `act-ai-server.ts` imported `dotenv`, which
  `agents.md` forbids. Removed; all config now reads from the environment.
- **Port mismatches** — apps listened on 3001/3002/3003/3005 while k8s and the
  e2e tests expected 8080/3000. Standardized: Rust services on `PORT` (default
  **8080**), the AI server on `PORT` (default **3000**), and aligned every
  manifest and test.
- **No graceful shutdown** — every server exited abruptly. Added SIGTERM/SIGINT
  draining (axum `with_graceful_shutdown`; Fastify `close()` + OTel flush) so k8s
  rolling updates don't drop in-flight requests.
- **`.unwrap()` everywhere** in the Rust `main`s → replaced with `?`/`anyhow` and
  fail-soft handling for optional dependencies (NATS, Postgres).
- **OpenTelemetry declared but never initialized** — the OTLP crates were in
  `Cargo.toml` but no tracer was built. Added real OTLP export (gRPC for Rust,
  OTLP/HTTP for Node), gated on `OTEL_EXPORTER_OTLP_ENDPOINT` with console
  fallback.
- **No Dockerfiles / `.dockerignore`** in the canonical repos → added multi-stage,
  non-root, slim-runtime Dockerfiles with dependency-layer caching.

### act-api-server.rs
- Restructured into modules (`config`, `telemetry`, `nats`, `routes`).
- **NATS bridge**: connects to `nats://nats:4222`, subscribes to `act.events.>`,
  fails soft if the broker is down. Added `/health` (liveness) and `/ready`.

### act-mcp-server.rs
- Was a `Hello, world!` stub. Augmented into a real **MCP JSON-RPC server**
  (`initialize`, `ping`, `tools/list`, `tools/call`) at `POST /mcp`, plus probes.

### act-web-server.rs
- **Supabase auth was a pass-through placeholder** → implemented HS256 JWT
  verification (`jsonwebtoken`) with `exp`/`aud` validation, **fail-closed** when
  no secret is configured; verified claims flow to handlers via a protected
  `/api/me` route.
- **`migration` crate was a stub `add()`** → converted to a proper
  `sea-orm-migration` crate (lib + CLI bin) with an initial `events` table.
- Optional Postgres pool via sea-orm (fails soft; reflected in `/ready`).

### act-ai-server.ts
- Merged the Fastify server with the standalone pipeline: modules `telemetry`,
  `providers`, `youtube`, `index`. Routes: `/health`, `/ready`,
  `/api/generate/script`, `/api/generate/video`, `/api/publish/youtube`.
- Provider model IDs are env-overridable; Anthropic defaults to `claude-opus-5`
  and guards `stop_reason: "refusal"`. Bumped SDKs off placeholder versions.

### act-infra (k8s)
- Replaced the **mock `fiducia-secrets-loader` init container** (which echoed
  fake secrets into a file that was then `source`d) with `envFrom` a Secret
  (populated by the fiducia external-secrets operator) + a ConfigMap for
  non-secret config.
- Added to every Deployment: **liveness/readiness probes**, **resource
  requests/limits**, `securityContext` (runAsNonRoot, drop ALL caps,
  readOnlyRootFilesystem, seccomp RuntimeDefault, no privilege escalation),
  rolling-update strategy with `maxUnavailable: 0`.
- Wired NATS + OTLP env; **added the missing `act-mcp-server` Deployment/Service**.

### act-e2e (new suites)
- Rebuilt as plain-ESM `*.test.mjs` on the Node built-in test runner (dropped
  jest/ts-jest). Suites at the requested paths:
  `tests/browser/{playwright,puppeteer,selenium}/*.test.mjs`, plus
  `tests/integration/` (HTTP health sweep + MCP JSON-RPC + NATS round-trip).
- Targets the cluster's shared browser services and NATS bridge; every endpoint
  is env-overridable (`tests/config.mjs`).

## 3. Verification

| Repo | Check | Result |
| --- | --- | --- |
| act-api-server.rs | `cargo check` | ✅ |
| act-mcp-server.rs | `cargo check` | ✅ |
| act-web-server.rs | `cargo check --workspace` | ✅ |
| act-ai-server.ts | `npm run build` (tsc) | ✅ |
| act-infra | `kubectl apply --dry-run=client` | ✅ (4 manifests) |
| act-e2e | `node --test` discovery + syntax | ✅ (13 tests discovered) |

## 4. Second pass — defects found by end-to-end testing

Standing the services up locally against real dependencies (a NATS broker, a
Selenium Grid, a Playwright server, a CDP Chromium) surfaced defects that no
amount of static review had caught. Each is fixed, with a regression test.

| Defect | Impact | Fix |
| --- | --- | --- |
| `act-ai-server` constructed every LLM client at module load | A single missing API key aborted startup. The k8s `secretRef` is optional, so an unconfigured provider is expected — the pod would have crash-looped and taken the credential-free probes down with it. | Lazy per-provider construction; a missing key is now a 503 on that one route naming the variable |
| Supabase JWT: `nbf` unvalidated | `jsonwebtoken` leaves `validate_nbf` off, so a not-yet-valid token authenticated | `validate_nbf = true` |
| Supabase JWT: missing `aud` skipped audience matching | A token minted for another service authenticated here | `aud` is a required claim; its absence fails verification |
| Supabase JWT: 60s default expiry leeway | Wider acceptance window than needed | Narrowed to 5s, configurable; optional issuer pinning added |
| `act-ai-server` accepted whitespace-only input | A blank topic reached the provider and billed a paid call for nothing | `isNonEmptyString` guard on topic, script, and title |
| `act-e2e` scoped npm scripts passed a bare directory to `node --test` | Node 22 resolves it as a module path; every scoped script failed with `MODULE_NOT_FOUND` | Glob patterns |
| `act-ai-server` shutdown was unbounded | `fastify.close()` waits for connections to go idle; a client that never reads its response body kept one active forever, so the pod hung until SIGKILL and stalled every rolling update | Grace period (`SHUTDOWN_GRACE_MS`, default 10s) after which the process exits anyway, and logs that it did |

The suite is verified to *detect* regressions, not merely to pass: run against a
server trusting a different JWT secret, exactly the four "accepts a valid token"
tests fail while all fourteen rejection tests still pass.

Coverage now stands at **411 tests across 99 suites**. Three categories exist
because the behaviour they cover is invisible to a suite that only talks to a
running deployment:

- **`lifecycle/`** starts services on ephemeral ports with a chosen environment,
  which is the only way to observe graceful shutdown, fail-soft startup against
  a dead dependency, and fail-closed auth when no secret is configured.
- **`database/`** applies the sea-orm migrations to a throwaway Postgres —
  schema shape, constraints, idempotent re-runs, reversible `down`. It is also
  the only exercise anywhere of the service's database connection path; every
  other suite runs with `database_connected: false`.
- **`journeys/`** proves the api-server *itself* consumes the events it
  subscribes to, using its own log as evidence. The NATS suites only show the
  broker delivers to a subscriber we control, which would still pass if the
  service were subscribed to the wrong subject.

Plus **`contracts/manifests`**, which parses the act-infra manifests and checks
probes, resource limits, `securityContext`, secret injection, and port agreement
against the running services — drift that nothing else in the build catches.

## 5. Follow-ups (not done)

- Confirm the real in-cluster service names for NATS, the OTel collector, and the
  browser services; the manifests/tests use conventional defaults.
- Provide the `act-<svc>-secrets` Secrets via the fiducia operator.
- Consider NetworkPolicies and a PodDisruptionBudget for the HTTP services.
