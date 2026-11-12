"""Read-only candidate checks; callers supply a trusted allowlist from a chosen Git tree.

Run on a quiescent exported/installed tree, with caches outside it.
Hashes detect divergence, not origin authenticity, authorization or a filesystem sandbox.
"""
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat


FORBIDDEN_NAMES = {"auth.json", ".env"}


def checked_paths(paths):
    paths = list(paths)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("Empty or duplicate payload paths")
    for name in paths:
        if not isinstance(name, str):
            raise ValueError("Payload paths must be strings")
        path = PurePosixPath(name)
        if path.is_absolute() or str(path) != name or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe payload path")
        if not path.parts or any(p in FORBIDDEN_NAMES or p.startswith(".env.") or p == ".git" for p in path.parts):
            raise ValueError("Forbidden payload path")
    return paths


def tree_files(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError("Payload root must be a physical directory")
    result = {}

    def visit(directory):
        for child in sorted(directory.iterdir()):
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError("Payload symlink rejected")
            if child == root / ".git":
                if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    raise ValueError("Invalid Git metadata")
                continue
            if stat.S_ISDIR(mode):
                visit(child)
            elif stat.S_ISREG(mode):
                result[child.relative_to(root).as_posix()] = child
            else:
                raise ValueError("Non-regular payload entry rejected")

    visit(root)
    return result


def hash_tree(root, paths):
    paths = checked_paths(paths)
    files = tree_files(root)
    if set(files) != set(paths):
        raise ValueError("Payload differs from explicit allowlist")
    return {name: hashlib.sha256(files[name].read_bytes()).hexdigest() for name in sorted(paths)}


def verify_tree(root, expected):
    if not isinstance(expected, dict):
        raise ValueError("Expected hashes must be an external mapping")
    checked_paths(expected)
    if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in expected.values()):
        raise ValueError("Invalid SHA-256")
    files = tree_files(root)
    findings = ["missing:" + name for name in sorted(set(expected) - set(files))]
    findings += ["extra:" + name for name in sorted(set(files) - set(expected))]
    for name in sorted(set(files) & set(expected)):
        if hashlib.sha256(files[name].read_bytes()).hexdigest() != expected[name]:
            findings.append("modified:" + name)
    return findings
