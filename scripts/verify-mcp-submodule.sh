#!/usr/bin/env bash
set -euo pipefail

test -f .gitmodules

test "$(git config -f .gitmodules --get submodule.apps/act-mcp-server.rs.path)" = \
  "apps/act-mcp-server.rs"
test "$(git config -f .gitmodules --get submodule.apps/act-mcp-server.rs.url)" = \
  "git@github.com:anticaptrad/act-mcp-server.rs.git"
test "$(git config -f .gitmodules --get submodule.apps/act-mcp-server.rs.branch)" = \
  "main"
test "$(git ls-files --stage -- apps/act-mcp-server.rs | awk 'NR == 1 {print $1}')" = \
  "160000"
grep -qF '`act-mcp-server.rs`' README.md

while IFS=' ' read -r key value; do
  case "$key" in
    *.path)
      [[ "$value" == apps/* ]]
      test "$(git ls-files --stage -- "$value" | awk 'NR == 1 {print $1}')" = "160000"
      ;;
    *.url)
      [[ "$value" =~ ^git@github\.com:anticaptrad/[A-Za-z0-9._-]+(\.git)?$ ]]
      ;;
    *.branch)
      test "$value" = "main"
      ;;
  esac
done < <(git config -f .gitmodules --get-regexp '^submodule\.')

if git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- . ':(exclude)*.lock'; then
  echo 'Git conflict markers found' >&2
  exit 1
fi

echo 'ACT monorepo MCP submodule contract passed'
