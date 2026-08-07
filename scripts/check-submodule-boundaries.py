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
EXPECTED = {
    "anticaptrad/act-interfaces",
    "anticaptrad/act-lib",
    "anticaptrad/act-clients",
}
GITHUB_SCP = re.compile(r"^git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$")
RELATIVE_GIT = re.compile(r"^\.\.?/[A-Za-z0-9_.-]+(?:\.git)?$")


@dataclass(frozen=True)
class Submodule:
    name: str
    path: str
    url: str
    branch: str | None
    update: str | None


def load(path: pathlib.Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def parse_gitmodules(path: pathlib.Path) -> list[Submodule]:
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    with path.open(encoding="utf-8") as handle:
        parser.read_file(handle)
    result: list[Submodule] = []
    for section in parser.sections():
        if not section.startswith('submodule "') or not section.endswith('"'):
            raise ValueError(f"invalid .gitmodules section: {section}")
        result.append(Submodule(
            name=section[len('submodule "') : -1],
            path=parser.get(section, "path"),
            url=parser.get(section, "url"),
            branch=parser.get(section, "branch", fallback=None),
            update=parser.get(section, "update", fallback=None),
        ))
    return result


def leaf(url: str) -> str:
    value = url.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if ":" in value and not value.startswith(("http://", "https://")):
        value = value.rsplit(":", 1)[-1]
    return value.rsplit("/", 1)[-1]


def classify(name: str, policy: dict) -> tuple[str, bool]:
    for rule in policy.get("rule", []):
        suffix = str(rule.get("suffix", ""))
        if suffix and name.endswith(suffix):
            return str(rule.get("classification", "source")), bool(rule.get("zed_dependency", True))
    defaults = policy.get("defaults", {})
    return str(defaults.get("classification", "source")), bool(defaults.get("zed_dependency", True))


def portable_path(value: str) -> bool:
    path = pathlib.PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "." not in path.parts and "\\" not in value


def portable_url(value: str) -> bool:
    if RELATIVE_GIT.fullmatch(value) or GITHUB_SCP.fullmatch(value):
        return True
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.netloc == "github.com" and bool(parsed.path.strip("/"))


def main() -> int:
    errors: list[str] = []
    gitmodules = ROOT / ".gitmodules"
    if not gitmodules.is_file():
        print("error: act-monorepo must keep a checked-in .gitmodules file", file=sys.stderr)
        return 1
    try:
        submodules = parse_gitmodules(gitmodules)
    except (OSError, configparser.Error, ValueError) as exc:
        print(f"error: invalid .gitmodules: {exc}", file=sys.stderr)
        return 1
    if not submodules:
        errors.append(".gitmodules contains no submodules")

    manifest = load(ROOT / ".zpkg.toml")
    lock = load(ROOT / ".zpkg.lock")
    policy = load(ROOT / "submodule-policy.toml")
    package = manifest.get("package", {})
    dependencies = manifest.get("dependencies", {})
    if package.get("org") != "anticaptrad" or package.get("name") != "act-monorepo":
        errors.append("package identity must be anticaptrad/act-monorepo")
    if package.get("repository", {}).get("url") != "https://github.com/anticaptrad/act-monorepo":
        errors.append("package.repository.url must match the canonical repository")
    if not isinstance(dependencies, dict) or not EXPECTED.issubset(dependencies):
        errors.append("monorepo must import interfaces, singular lib, and clients")
        dependencies = dependencies if isinstance(dependencies, dict) else {}
    if lock.get("version") != 1:
        errors.append(".zpkg.lock must use version = 1")

    names: set[str] = set()
    paths: set[str] = set()
    repositories: set[str] = set()
    for submodule in submodules:
        repo = leaf(submodule.url)
        classification, should_depend = classify(repo, policy)
        print(f"{submodule.path}: {repo} -> {classification}; zed_dependency={str(should_depend).lower()}")
        if submodule.name in names:
            errors.append(f"duplicate submodule name: {submodule.name}")
        names.add(submodule.name)
        if submodule.path in paths:
            errors.append(f"duplicate submodule path: {submodule.path}")
        paths.add(submodule.path)
        if repo in repositories:
            errors.append(f"duplicate submodule repository: {repo}")
        repositories.add(repo)
        if not portable_path(submodule.path):
            errors.append(f"non-portable submodule path: {submodule.path}")
        if not portable_url(submodule.url):
            errors.append(f"non-portable submodule URL: {submodule.url}")
        if submodule.branch == ".":
            errors.append(f"submodule {submodule.name} may not use branch = .")
        if submodule.update and (submodule.update == "command" or submodule.update.startswith("!")):
            errors.append(f"submodule {submodule.name} may not execute a custom update command")
        coordinate = f"anticaptrad/{repo}"
        if not should_depend and coordinate in dependencies:
            errors.append(f"{classification} submodule {repo} must not be a Zed dependency")

    forbidden = [item for item in dependencies if item.rsplit("/", 1)[-1].endswith(("-cli", "-infra", "-libs"))]
    if forbidden:
        errors.append("monorepo may not import CLI, infra, or alternate libs: " + ", ".join(sorted(forbidden)))

    status = subprocess.run(["git", "submodule", "status", "--recursive"], cwd=ROOT, check=False, capture_output=True, text=True)
    if status.returncode != 0:
        errors.append("git submodule status --recursive failed: " + status.stderr.strip())
    for line in status.stdout.splitlines():
        if line.startswith("-"):
            errors.append("uninitialized recursive submodule: " + line[1:].strip())
        elif line.startswith("U"):
            errors.append("submodule has merge conflicts: " + line[1:].strip())

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"validated {len(submodules)} recursive submodules and the Anticaptrad Zed boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
