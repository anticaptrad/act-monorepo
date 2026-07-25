# AntiCapTrad Monorepo

Meta-repo describing the AntiCapTrad service constellation. Each service lives in
its own git repository under `~/codes/anticaptrad/`; the backend services deploy
to the k8s cluster at `~/codes/ores/k8s-cluster` (which also hosts the shared
Playwright / Puppeteer / Selenium services and a NATS message-queue bridge).

## Repositories

| Repo | Language | Role | Container port |
| --- | --- | --- | --- |
| `act-api-server.rs` | Rust (axum) | HTTP API + NATS event-bus bridge | 8080 |
| `act-web-server.rs` | Rust (axum + sea-orm) | Supabase-authenticated web API | 8080 |
| `act-mcp-server.rs` | Rust (axum) | Model Context Protocol (JSON-RPC) server | 8080 |
| `act-ai-server.ts` | Node/TypeScript (Fastify) | Multi-provider LLM + video + YouTube | 3000 |
| `act-infra` | k8s YAML | Deployments, Services, ConfigMaps | — |
| `act-e2e` | Node ESM | Browser + integration e2e tests | — |
| `act-clients`, `act-interfaces`, `act-sync`, `act-monorepo` | — | Shared clients / interfaces / sync / docs | — |

Repository naming uses the **dotted** convention (`act-<name>.<lang>`). Earlier
`act-<name>-<lang>` duplicates were consolidated into their dotted counterparts.

## Conventions (`agents.md`)

Every repo carries an `agents.md` with the platform rules, mirrored into
`.claude/`, `.gemini/`, and `.openai/`:

- Blacklisted operations: `git reset`, `rm` (except scratch), `git filter-repo`, `git clean`.
- Blacklisted dependency: `dotenv` (config comes from the environment / k8s).

See [docs/architecture.md](docs/architecture.md) for the platform architecture and
operational contract, and [AUDIT.md](AUDIT.md) for the consolidation + hardening
changelog.
