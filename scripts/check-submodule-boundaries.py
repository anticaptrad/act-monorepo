#!/usr/bin/env python3
"""Validate Anticaptrad git-submodule portability and Zed dependency boundaries."""
from __future__ import annotations
import configparser
import pathlib
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED = {"anticaptrad/act-interfaces", "anticaptrad/act-clients"}
GITHUB_SCP = re.compile(r"^git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$")
RELATIVE_GIT = re.compile(r"^\.\.?/[A-Za-z0-9_.-]+(?:\.git)?$")

@dataclass(frozen=True)
class Submodule:
    name: str; path: str; url: str; branch: str | None; update: str | None

def load(path: pathlib.Path) -> dict:
    with path.open("rb") as handle: return tomllib.load(handle)

def parse_gitmodules(path: pathlib.Path) -> list[Submodule]:
    parser = configparser.ConfigParser(interpolation=None, strict=True); parser.optionxform = str
    with path.open(encoding="utf-8") as handle: parser.read_file(handle)
    out=[]
    for section in parser.sections():
        if not section.startswith('submodule "') or not section.endswith('"'): raise ValueError(f"invalid .gitmodules section: {section}")
        out.append(Submodule(section[len('submodule "'):-1], parser.get(section,"path"), parser.get(section,"url"), parser.get(section,"branch",fallback=None), parser.get(section,"update",fallback=None)))
    return out

def leaf(url: str) -> str:
    value=url.rstrip('/'); value=value[:-4] if value.endswith('.git') else value
    if ':' in value and not value.startswith(('http://','https://')): value=value.rsplit(':',1)[-1]
    return value.rsplit('/',1)[-1]

def portable_path(value: str) -> bool:
    p=pathlib.PurePosixPath(value); return bool(value) and not p.is_absolute() and '..' not in p.parts and '.' not in p.parts and '\\' not in value

def portable_url(value: str) -> bool:
    if RELATIVE_GIT.fullmatch(value) or GITHUB_SCP.fullmatch(value): return True
    p=urlparse(value); return p.scheme=='https' and p.netloc=='github.com' and bool(p.path.strip('/'))

def main() -> int:
    errors=[]
    try: modules=parse_gitmodules(ROOT/'.gitmodules')
    except Exception as exc: print(f"error: invalid .gitmodules: {exc}", file=sys.stderr); return 1
    manifest=load(ROOT/'.zpkg.toml'); deps=manifest.get('dependencies',{})
    if manifest.get('package',{}).get('org')!='anticaptrad' or manifest.get('package',{}).get('name')!='act-monorepo': errors.append('package identity must be anticaptrad/act-monorepo')
    if manifest.get('install',{}).get('dir')!='.vendor/.zed': errors.append('Zed packages must install under .vendor/.zed')
    if set(deps)!=EXPECTED: errors.append('monorepo must import exactly existing interfaces and clients packages')
    names=set(); paths=set(); repos=set()
    for module in modules:
        repo=leaf(module.url)
        if module.name in names: errors.append(f'duplicate submodule name: {module.name}')
        if module.path in paths: errors.append(f'duplicate submodule path: {module.path}')
        if repo in repos: errors.append(f'duplicate submodule repository: {repo}')
        names.add(module.name); paths.add(module.path); repos.add(repo)
        if not portable_path(module.path): errors.append(f'non-portable submodule path: {module.path}')
        if not portable_url(module.url): errors.append(f'non-portable submodule URL: {module.url}')
        if repo.endswith(('-cli','-infra')): errors.append(f'{repo} must remain standalone, not a monorepo gitlink')
        if module.update and (module.update=='command' or module.update.startswith('!')): errors.append(f'{module.name} may not execute custom update commands')
    status=subprocess.run(['git','submodule','status','--recursive'], cwd=ROOT, check=False, capture_output=True, text=True)
    if status.returncode: errors.append('git submodule status --recursive failed: '+status.stderr.strip())
    for line in status.stdout.splitlines():
        if line.startswith('-'): errors.append('uninitialized recursive submodule: '+line[1:].strip())
        elif line.startswith('U'): errors.append('submodule merge conflict: '+line[1:].strip())
    for error in errors: print('error: '+error, file=sys.stderr)
    if errors: return 1
    print(f'validated {len(modules)} source gitlinks and {len(EXPECTED)} resolvable Zed dependencies')
    return 0
if __name__=='__main__': raise SystemExit(main())
