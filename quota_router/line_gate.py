# Implements AGENTS.md, "Texto e verificações"; README.md, HQR-08.
"""Repository gate library; exceptions name exact frozen public/data paths."""
from pathlib import Path

from .verification import checked_paths

EXEMPTIONS = {
    "LICENSE": "Standard MIT third-party license text",
    "evidence/plugin-existing-research.txt": "Frozen public research",
    "evidence/plugin-native-research.txt": "Frozen public research",
    "evidence/product-delivery-research.txt": "Frozen public research",
    "evidence/product-plan-sources.json": "Citation ledger data",
    "evidence/product-spec-sources.json": "Citation ledger data",
}


def check_lines(root, paths):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("Root symlinks rejected")
    findings = []
    for name in checked_paths(paths):
        path = root / name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("File symlinks rejected")
        text = path.read_text(encoding="utf-8")
        if name not in EXEMPTIONS:
            for number, line in enumerate(text.splitlines(), 1):
                if len(line) > 2000:
                    findings.append(f"{name}:{number}:{len(line)}")
    return findings
