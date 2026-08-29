# AntiCapTrad Monorepo

Aggregate checkout for the AntiCapTrad service constellation. Every component
remains an independently versioned source repository under the `anticaptrad`
GitHub organization; this repository pins reviewed commits so cluster and local
integration work use one reproducible platform snapshot.

The backend services deploy to the Kubernetes cluster at
`~/codes/ores/k8s-cluster`, which also hosts the authenticated browser-scenario
service and the HTTP-to-NATS bridge. The cluster pins this repository as a
separate git submodule rather than copying application source.

## Repositories

| Repo | Language | Role | Aggregate path | Container port |
| --- | --- | --- | --- | --- |
| `act-mcp-server.rs` | Rust (axum) | Model Context Protocol (JSON-RPC) server | `apps/act-mcp-server.rs` | 8080 |
| `act-api-server.rs` | Rust (axum) | Public JSON API and Google Apps Script control plane | `apps/act-api-server.rs` | 8080 |
| `act-web-server.rs` | Rust (axum + SeaORM) | Authenticated operator UI and web API | `apps/act-web-server.rs` | 8080 |
| `act-ai-server.ts` | Node.js/TypeScript (Fastify) | Multi-provider script/video orchestration and YouTube integration | `apps/act-ai-server.ts` | 3000 |
| `act-interfaces` | Schemas/contracts | Versioned shared interfaces | `packages/act-interfaces` | — |
| `act-clients` | Polyglot SDKs | Generated and hand-written client packages | `packages/act-clients` | — |
| `act-e2e` | Node.js ESM | Cross-service and browser-scenario verification | `tests/act-e2e` | — |
| `act-sync` | Integration tooling | Explicit repository/reference synchronization | `tools/act-sync` | — |
| `act-infra` | Kubernetes YAML | App-of-apps, Deployments, Services, ConfigMaps, and secret references | **standalone** | — |

`act-infra` deliberately remains outside the aggregate gitlink tree. Operational
state has a different review and deployment lifecycle from application source,
and `submodule-policy.toml` enforces that boundary.

Repository naming uses the **dotted** convention (`act-<name>.<lang>`). Earlier
`act-<name>-<lang>` duplicates were consolidated into their dotted counterparts.

## Reproducible checkout

```sh
git clone --recurse-submodules https://github.com/anticaptrad/act-monorepo.git
cd act-monorepo
git submodule status --recursive
python3 scripts/check-submodule-boundaries.py
```

The tracked `branch = main` values document upstream intent; the gitlinks remain
immutable commit pins until a reviewed aggregate update advances them.

## Conventions (`agents.md`)

Every repo carries an `agents.md` with the platform rules, mirrored into
`.claude/`, `.gemini/`, and `.openai/`:

- Blacklisted operations: `git reset`, `rm` except known scratch data,
  `git filter-repo`, and `git clean`.
- Blacklisted dependency: `dotenv`; configuration comes from the environment,
  Kubernetes ConfigMaps, and secret references.
- Component repositories are authoritative. Fix a component there first, then
  advance its gitlink here explicitly.
- Raw Playwright, CDP, and WebDriver endpoints are never exposed; automation
  uses the authenticated browser-scenario API.

See [docs/architecture.md](docs/architecture.md) for the platform architecture and
operational contract, and [AUDIT.md](AUDIT.md) for the consolidation and
hardening history.
