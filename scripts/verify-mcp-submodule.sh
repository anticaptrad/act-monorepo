#!/usr/bin/env bash
set -euo pipefail

test -f .gitmodules

expected_modules=$(cat <<'EOF'
apps/act-mcp-server.rs|act-mcp-server.rs
apps/act-api-server.rs|act-api-server.rs
apps/act-web-server.rs|act-web-server.rs
apps/act-ai-server.ts|act-ai-server.ts
packages/act-interfaces|act-interfaces
packages/act-clients|act-clients
tests/act-e2e|act-e2e
tools/act-sync|act-sync
EOF
)

expected_count=$(printf '%s\n' "$expected_modules" | sed '/^$/d' | wc -l | tr -d ' ')
actual_count=$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | wc -l | tr -d ' ')
test "$actual_count" = "$expected_count"

while IFS='|' read -r path repo; do
  test -n "$path"
  test -n "$repo"

  key="submodule.${path}"
  test "$(git config -f .gitmodules --get "${key}.path")" = "$path"
  test "$(git config -f .gitmodules --get "${key}.url")" = \
    "https://github.com/anticaptrad/${repo}.git"
  test "$(git config -f .gitmodules --get "${key}.branch")" = "main"
  test "$(git ls-files --stage -- "$path" | awk 'NR == 1 {print $1}')" = "160000"

  grep -qF "\`${repo}\`" README.md
  grep -qF "\`${path}\`" docs/architecture.md
done <<< "$expected_modules"

while IFS=' ' read -r key value; do
  case "$key" in
    *.path)
      [[ "$value" == apps/* || "$value" == packages/* || "$value" == tests/* || "$value" == tools/* ]]
      [[ "$value" != *act-infra* ]]
      test "$(git ls-files --stage -- "$value" | awk 'NR == 1 {print $1}')" = "160000"
      ;;
    *.url)
      [[ "$value" =~ ^https://github\.com/anticaptrad/[A-Za-z0-9._-]+\.git$ ]]
      ;;
    *.branch)
      test "$value" = "main"
      ;;
  esac
done < <(git config -f .gitmodules --get-regexp '^submodule\.')

if git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | grep -q 'act-infra'; then
  echo 'act-infra must remain standalone, not a monorepo gitlink' >&2
  exit 1
fi

if git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- . ':(exclude)*.lock'; then
  echo 'Git conflict markers found' >&2
  exit 1
fi

echo "ACT monorepo platform contract passed for ${expected_count} pinned repositories"
