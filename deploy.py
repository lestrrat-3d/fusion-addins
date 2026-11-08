#!/usr/bin/env python3
"""Install a Fusion add-in into Fusion's AddIns folder and check the result.

Usage:
    python3 deploy.py fingerprint <addin>
    python3 deploy.py deploy <addin>
    python3 deploy.py verify <addin>
    python3 deploy.py check <addin>

<addin> is a folder name under addins/, or a path to an add-in folder. The installed folder (the bundle) is the
add-in folder, plus this repo's lib/addinkit/ at the same path, plus LICENSE. The shipped-set rules and the hash
come from lib/addinkit/fingerprint.py next to this script. Nothing is copied to compute a fingerprint.

`check` builds the bundle that `deploy` would install into .tmp/check/<addin>/ and reports every problem it finds.
Exit codes: 0 ok, 1 contract failure (check problems, verify mismatch, deploy fingerprint mismatch), 2 usage or
config error.
"""

from __future__ import annotations

import argparse
import configparser
import glob
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parent
ADDINS_DIR = ROOT / "addins"
CONF_PATH = ROOT / ".deploy.conf"
CHECK_DIR = ROOT / ".tmp" / "check"
KIT_DIR = ROOT / "lib" / "addinkit"
LICENSE_PATH = ROOT / "LICENSE"
KIT_REL = "lib/addinkit"
LICENSE_REL = "LICENSE"

_FP_CACHE: dict[str, object] = {}


class ToolError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def load_fp():
    """Load KIT_DIR/fingerprint.py by file path as a module (cached per resolved path)."""
    path = KIT_DIR / "fingerprint.py"
    if not path.is_file():
        raise ToolError(2, f"missing {path}")
    key = str(path.resolve())
    if key not in _FP_CACHE:
        spec = importlib.util.spec_from_file_location("addinkit_fingerprint", path)
        if spec is None or spec.loader is None:
            raise ToolError(2, f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
        _FP_CACHE[key] = module
    return _FP_CACHE[key]


def resolve_addin(arg: str) -> Path:
    """Return the add-in directory named by arg: a bare name under addins/, or a path."""
    path = ADDINS_DIR / arg
    if not path.is_dir():
        path = Path(arg)
        if not path.is_dir():
            raise ToolError(2, f"no add-in directory: {arg}")
    return path.resolve()


def missing_required(addin_dir: Path) -> list[str]:
    """Return the required files that are not regular files in addin_dir."""
    fp = load_fp()
    return [f for f in fp.required_files(addin_dir.name) if not (addin_dir / f).is_file()]


def bundled_collisions(relpaths: list[str]) -> list[str]:
    """Return the paths deploy.py itself supplies: LICENSE and anything under lib/addinkit."""
    return [r for r in relpaths if r == LICENSE_REL or r == KIT_REL or r.startswith(KIT_REL + "/")]


def _collision_problem(rel: str) -> str:
    return f"bundled by deploy.py, remove from the add-in folder: {rel}"


def source_problems(addin_dir: Path) -> list[str]:
    """Return problems with the add-in folder itself: missing required files, then bundled-path collisions."""
    fp = load_fp()
    problems = [f"missing {f}" for f in missing_required(addin_dir)]
    if not problems:
        problems = [_collision_problem(r) for r in bundled_collisions(fp.shipped_files(str(addin_dir)))]
    return problems


def bundle_sources(addin_dir: Path) -> dict[str, Path]:
    """Return {bundle path: source file}: the add-in's files, the shared kit, and LICENSE."""
    fp = load_fp()
    if LICENSE_PATH.is_symlink():
        raise ToolError(2, f"symlink not allowed: {LICENSE_PATH}")
    if not LICENSE_PATH.is_file():
        raise ToolError(2, f"missing {LICENSE_PATH}")
    kit = fp.tree_files(str(KIT_DIR))
    if "fingerprint.py" not in kit:
        raise ToolError(2, f"missing {KIT_DIR / 'fingerprint.py'}")
    own = fp.shipped_files(str(addin_dir))
    collisions = bundled_collisions(own)
    if collisions:
        raise ToolError(2, f"{addin_dir.name}: " + "; ".join(_collision_problem(r) for r in collisions))
    sources: dict[str, Path] = {rel: addin_dir / rel for rel in own}
    for f in kit:
        sources[f"{KIT_REL}/{f}"] = KIT_DIR / f
    sources[LICENSE_REL] = LICENSE_PATH
    return {rel: sources[rel] for rel in sorted(sources, key=lambda r: r.encode("utf-8"))}


def bundle_digest(addin_dir: Path) -> str:
    """Return the fingerprint of the bundle for addin_dir, without copying anything."""
    return load_fp().digest_map({rel: str(p) for rel, p in bundle_sources(addin_dir).items()})


def standard_patterns(environ: Mapping[str, str], home: Path) -> list[str]:
    """Return glob patterns for the standard Fusion AddIns folders."""
    patterns = ["/mnt/c/Users/*/AppData/Roaming/Autodesk/Autodesk Fusion 360/API/AddIns"]
    appdata = environ.get("APPDATA")
    if appdata:
        patterns.append(
            os.path.join(glob.escape(appdata), "Autodesk", "Autodesk Fusion 360", "API", "AddIns")
        )
    patterns.append(
        os.path.join(
            glob.escape(str(home)),
            "Library",
            "Application Support",
            "Autodesk",
            "Autodesk Fusion 360",
            "API",
            "AddIns",
        )
    )
    return patterns


def discover_parents(patterns: list[str]) -> list[Path]:
    """Expand patterns and return the distinct existing directories, sorted."""
    seen: dict[str, str] = {}
    for pattern in patterns:
        for p in glob.glob(pattern):
            if os.path.isdir(p):
                seen.setdefault(os.path.normcase(os.path.abspath(p)), p)
    return sorted(Path(p) for p in seen.values())


def _no_destination_message(name: str, parents: list[Path]) -> str:
    lines = [f"cannot pick a destination for {name}: found {len(parents)} standard AddIns folders"]
    lines += [f"  {p}" for p in parents]
    lines += [
        f"Set FUSION_ADDIN_DIR to the add-in's own folder (<AddIns folder>/{name}),",
        "or create .deploy.conf at the repo root containing:",
        "  [deploy]",
        "  addins_dir = <AddIns folder>",
        "Standard AddIns folders:",
        "  Windows from WSL: /mnt/c/Users/<you>/AppData/Roaming/Autodesk/Autodesk Fusion 360/API/AddIns",
        "  Windows:          %APPDATA%\\Autodesk\\Autodesk Fusion 360\\API\\AddIns",
        "  macOS:            ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns",
    ]
    return "\n".join(lines)


def resolve_destination(
    name: str, environ: Mapping[str, str], conf_path: Path, patterns: list[str]
) -> tuple[Path, str]:
    """Return (destination folder, source description) for add-in `name`."""
    env_value = environ.get("FUSION_ADDIN_DIR")
    if env_value:
        dest = Path(os.path.abspath(os.path.expanduser(env_value)))
        source = "FUSION_ADDIN_DIR"
    elif conf_path.is_file():
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(conf_path, encoding="utf-8")
        except configparser.Error as err:
            raise ToolError(2, f"{conf_path}: {err}")
        value = parser.get("deploy", "addins_dir", fallback="").strip()
        if not value:
            raise ToolError(2, f"{conf_path}: needs [deploy] addins_dir = <Fusion AddIns folder>")
        value = os.path.expanduser(value)
        if not os.path.isabs(value):
            raise ToolError(2, f"{conf_path}: addins_dir must be an absolute path")
        if not os.path.isdir(value):
            raise ToolError(2, f"{conf_path}: addins_dir does not exist: {value}")
        dest = Path(value) / name
        source = ".deploy.conf"
    else:
        parents = discover_parents(patterns)
        if len(parents) != 1:
            raise ToolError(2, _no_destination_message(name, parents))
        dest = parents[0] / name
        source = "auto-discovery"
    if dest.name != name:
        raise ToolError(2, f"destination folder must be named {name}, got {dest}")
    return dest, source


def ensure_separate(addin_dir: Path, dest: Path) -> None:
    """Raise ToolError(2) when dest equals, contains, or sits inside addin_dir."""
    a = os.path.normcase(os.path.realpath(addin_dir))
    d = os.path.normcase(os.path.realpath(dest))
    if a == d or d.startswith(a + os.sep) or a.startswith(d + os.sep):
        raise ToolError(2, f"destination {dest} overlaps the add-in source {addin_dir}")


def mirror(fp, sources: Mapping[str, Path], dest: Path) -> None:
    """Make dest match the bundle `sources`, leaving excluded artifacts alone.

    `fp` is a fingerprint module; its is_excluded decides which artifacts stay.
    """
    if dest.is_symlink():
        raise ToolError(2, f"destination is a symlink: {dest}")
    if not dest.parent.exists():
        raise ToolError(2, f"destination parent does not exist: {dest.parent}")
    dest.mkdir(exist_ok=True)
    wanted = set(sources)

    def rel_of(base: str, name: str) -> str:
        return os.path.relpath(os.path.join(base, name), dest).replace(os.sep, "/")

    for dirpath, dirnames, filenames in os.walk(dest, topdown=True):
        keep = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            rel = rel_of(dirpath, d)
            if fp.is_excluded(rel):
                continue
            if os.path.islink(full):
                os.unlink(full)
            elif rel in wanted:
                shutil.rmtree(full)
            else:
                keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = rel_of(dirpath, f)
            if os.path.islink(full):
                os.unlink(full)
            elif rel in wanted or fp.is_excluded(rel):
                continue
            else:
                os.remove(full)

    for dirpath, *_ in os.walk(dest, topdown=False):
        if os.path.normpath(dirpath) == os.path.normpath(str(dest)):
            continue
        rel = os.path.relpath(dirpath, dest).replace(os.sep, "/")
        if fp.is_excluded(rel):
            continue
        if not os.listdir(dirpath):
            os.rmdir(dirpath)

    for rel in sources:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sources[rel], target)


def deploy_to(addin_dir: Path, dest: Path) -> tuple[str, int]:
    """Mirror the bundle into dest and confirm the fingerprints agree."""
    fp = load_fp()
    ensure_separate(addin_dir, dest)
    ensure_separate(KIT_DIR, dest)
    sources = bundle_sources(addin_dir)
    want = fp.digest_map({rel: str(p) for rel, p in sources.items()})
    mirror(fp, sources, dest)
    got = fp.compute(str(dest), addin_dir.name)
    if got != want:
        raise ToolError(1, f"deployed fingerprint {got} differs from repo fingerprint {want}")
    return got, len(sources)


def file_digests(sources: Mapping[str, Path]) -> dict[str, str]:
    """Map each bundle path to the SHA-256 hex digest of its source file's bytes."""
    return {rel: hashlib.sha256(Path(p).read_bytes()).hexdigest() for rel, p in sources.items()}


def compare(addin_dir: Path, dest: Path) -> list[str]:
    """List differences between the checkout's bundle and the deployed copy."""
    fp = load_fp()
    a = file_digests(bundle_sources(addin_dir))
    b = file_digests({rel: dest / rel for rel in fp.shipped_files(str(dest), addin_dir.name)})
    lines = [f"changed: {p}" for p in sorted(a) if p in b and a[p] != b[p]]
    lines += [f"only in repo: {p}" for p in sorted(a) if p not in b]
    lines += [f"only in deployed: {p}" for p in sorted(b) if p not in a]
    return lines


def _verify(addin_dir: Path, dest: Path, source: str) -> int:
    fp = load_fp()
    print(f"destination {dest} (from {source})")
    if not dest.is_dir():
        print("mismatch")
        print(f"  deployed folder missing: {dest}")
        return 1
    repo = bundle_digest(addin_dir)
    deployed = fp.compute(str(dest), addin_dir.name)
    if repo == deployed:
        print(f"match {repo}")
        return 0
    print("mismatch")
    print(f"  repo     {repo}")
    print(f"  deployed {deployed}")
    lines = compare(addin_dir, dest)
    for line in lines[:20]:
        print(f"  {line}")
    if len(lines) > 20:
        print(f"  ... and {len(lines) - 20} more")
    return 1


def violations(relpaths: list[str], name: str) -> list[str]:
    """Return at most one problem string per path that should not be in a shipped folder."""
    fp = load_fp()
    top_files = fp.required_files(name) + fp.OPTIONAL_FILES
    problems = []
    for rel in relpaths:
        parts = rel.split("/")
        if len(parts) == 1 and rel not in top_files:
            problems.append(f"not in allowlist: {rel}")
        elif len(parts) > 1 and parts[0] not in fp.SHIPPED_DIRS:
            problems.append(f"not in allowlist: {rel}")
        elif fp.is_excluded(rel):
            problems.append(f"excluded artifact shipped: {rel}")
        elif not rel.isascii():
            problems.append(f"non-ASCII path: {rel}")
    return problems


def manifest_problems(manifest_path: Path) -> list[str]:
    """Return problems found in the add-in manifest file."""
    try:
        data = json.loads(manifest_path.read_bytes())
    except ValueError as err:
        return [f"manifest is not valid JSON: {err}"]
    if not isinstance(data, dict):
        return ["manifest is not a JSON object"]
    problems = []
    ident = data.get("id")
    ok = False
    if isinstance(ident, str):
        try:
            ok = str(uuid.UUID(ident)) == ident
        except ValueError:
            ok = False
    if not ok:
        problems.append("manifest id must be a lowercase hyphenated UUID")
    if data.get("version") != "":
        problems.append('manifest version must be "" (the fingerprint identifies the build)')
    return problems


def compile_problems(root: Path, relpaths: list[str]) -> list[str]:
    """Compile each file in memory and return one problem per file that fails."""
    problems = []
    for rel in relpaths:
        data = (root / rel).read_bytes()
        try:
            compile(data, rel, "exec", dont_inherit=True)
        except SyntaxError as e:
            problems.append(f"does not compile: {rel}:{e.lineno}: {e.msg}")
        except ValueError as e:
            problems.append(f"does not compile: {rel}: {e}")
    return problems


def check(addin_dir: Path, scratch_parent: Path) -> tuple[list[str], int, int, str]:
    """Build the bundle into scratch_parent/<name> and validate the result."""
    fp = load_fp()
    name = addin_dir.name
    src_problems = source_problems(addin_dir)
    if src_problems:
        return (src_problems, 0, 0, "")
    dest = scratch_parent / name
    ensure_separate(addin_dir, dest)
    ensure_separate(KIT_DIR, dest)
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    scratch_parent.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    try:
        digest, _ = deploy_to(addin_dir, dest)
    except ToolError as e:
        if e.code != 1:
            raise
        problems.append(str(e))
        digest = ""
    rels = []
    for dirpath, _, filenames in os.walk(dest):
        for f in filenames:
            rels.append(os.path.relpath(os.path.join(dirpath, f), dest).replace(os.sep, "/"))
    rels.sort(key=lambda r: r.encode("utf-8"))
    problems += violations(rels, name)
    problems += [f"missing {f}" for f in fp.required_files(name) if f not in rels]
    manifest = dest / f"{name}.manifest"
    if manifest.is_file():
        problems += manifest_problems(manifest)
    py = [r for r in rels if r.endswith(".py")]
    problems += compile_problems(dest, py)
    return problems, len(rels), len(py), digest


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    if environ is None:
        environ = os.environ
    parser = argparse.ArgumentParser(prog="deploy.py", description="Install a Fusion add-in.")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("fingerprint", "deploy", "verify", "check"):
        p = sub.add_parser(cmd)
        p.add_argument("addin")
    args = parser.parse_args(argv)
    try:
        addin_dir = resolve_addin(args.addin)
        name = addin_dir.name
        if args.command == "check":
            problems, shipped, pys, digest = check(addin_dir, CHECK_DIR)
            if problems:
                print(f"check failed: {name}", file=sys.stderr)
                for problem in problems:
                    print(f"  {problem}", file=sys.stderr)
                return 1
            print(f"check ok: {name}: {shipped} files shipped, {pys} Python files compile")
            print(f"fingerprint {digest}")
            return 0
        problems = source_problems(addin_dir)
        if problems:
            raise ToolError(2, f"{name}: " + "; ".join(problems))
        if args.command == "fingerprint":
            print(bundle_digest(addin_dir))
        elif args.command == "deploy":
            dest, source = resolve_destination(
                name, environ, CONF_PATH, standard_patterns(environ, Path.home())
            )
            print(f"destination {dest} (from {source})")
            digest, count = deploy_to(addin_dir, dest)
            print(f"deployed {name}: {count} files")
            print(f"fingerprint {digest}")
        elif args.command == "verify":
            dest, source = resolve_destination(
                name, environ, CONF_PATH, standard_patterns(environ, Path.home())
            )
            return _verify(addin_dir, dest, source)
        return 0
    except ToolError as e:
        print(f"deploy.py: {e}", file=sys.stderr)
        return e.code
    except ValueError as e:
        print(f"deploy.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
