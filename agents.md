# AntiCapTrad platform agent instructions

## Repository restrictions and platform contract

- Do not run `git reset`, `git filter-repo`, or `git clean`.
- Do not run `rm` except when explicitly deleting known temporary or scratch files.
- `dotenv` is blacklisted platform-wide. Configuration comes from the process environment, Kubernetes ConfigMaps, and secret references.
- Each service repository is the source of truth for its code. Make component changes there, merge them there, and update any aggregate references here explicitly; do not edit secondary checkouts as substitutes for source repositories.
- Preserve the platform-wide operational contract: uniform public JSON health/readiness probes, optional dependencies fail soft, authentication fails closed, and shutdown is graceful and bounded.
- Preserve strict Supabase JWT validation, including required audience, `nbf`, bounded expiry leeway, and optional issuer pinning. Never weaken authentication because a library default appears convenient.
- Do not expose raw Playwright, CDP, or WebDriver endpoints. Browser execution remains behind an authenticated scenario API.
- Keep repository naming, service ownership, architecture documentation, audit history, and E2E contracts synchronized when platform structure changes.

## Instruction discovery

Resolve `$PWD`, walk upward through every parent directory to the filesystem root, read every readable lowercase `agents.md` on that ancestor chain, and apply them root-to-leaf. Work inside a nested component must therefore load this broad platform guidance and the nearest component guidance. Do not search siblings. Deduplicate resolved paths/inodes, avoid symlink cycles, and report unreadable files.

## Synchronize with the remote

Before editing, inspect `git status`, current branch, configured remotes, the default branch, and any component/submodule state. Run `git fetch --all --prune` and create the feature branch from the latest remote default branch. Fetch again before pushing and incorporate upstream changes using repository merge policy.

- avoid git rebase in favor of git merge.
- Never discard remote commits, force-push, rewrite shared history, bypass review, or bypass required CI.

## Resolve Git conflicts semantically

Resolve conflicts by understanding and combining both sides' intent. Do not mechanically choose `ours`, `theirs`, current, or incoming changes. Produce the conceptually correct platform result while preserving compatible repository ownership, operational contracts, authentication guarantees, fail-soft/fail-closed boundaries, probe schemas, graceful shutdown, browser-control security, architecture/audit documentation, tests, configuration, and aggregate references. Resolve component conflicts in their source repositories first, then update references here. If intentions are incompatible, make the smallest explicit design decision and document it in the pull request.

After resolving, reread every affected file from the top, verify component references and architecture documentation, run platform and E2E contract validation, and search the entire worktree for conflict markers:

```sh
grep -RInE '^(<<<<<<<|=======|>>>>>>>)' --exclude-dir=.git .
```

If any marker or suspicious partial resolution remains, repeat semantic resolution from the top and rerun validation. A conflict is resolved only when the resulting platform is conceptually coherent and verified, not merely accepted by Git.