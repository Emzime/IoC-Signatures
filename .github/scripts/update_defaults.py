#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Met à jour les valeurs par défaut (DEFAULT_*) dans le dépôt ioc-scanner
à partir des fichiers JSON de ce dépôt (ioc-signatures).

Usage:
    python .github/scripts/update_defaults.py /chemin/vers/ioc-scanner
Ex. dans le workflow:
    python .github/scripts/update_defaults.py ioc-scanner
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------- Utils I/O ----------

def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"JSON introuvable: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def dumps_python(value: Any) -> str:
    """
    Sérialise en 'pseudo Python' lisible, en s'appuyant sur json.dumps.
    (suffisant pour nos objets simples: dict/list/str/numbers)
    """
    return json.dumps(value, indent=4, ensure_ascii=False)


def replace_block(src: str, pattern: str, replacement: str) -> tuple[str, bool]:
    """
    Remplace le premier bloc qui matche `pattern` (regex DOTALL) par `replacement`.
    Retourne (nouveau_texte, changé?).
    """
    new_src, n = re.subn(pattern, replacement, src, count=1, flags=re.DOTALL)
    return new_src, bool(n)


# ---------- Mises à jour concrètes ----------

def update_packages_defaults(scanner_root: Path, bad_packages: dict, extra_targets: list[str]) -> bool:
    """
    Met à jour DEFAULT_BAD_PACKAGES et DEFAULT_EXTRA_TARGETS dans scanner/refs/packages.py
    """
    target = scanner_root / "scanner" / "refs" / "packages.py"
    if not target.exists():
        raise FileNotFoundError(f"Fichier introuvable: {target}")

    src = target.read_text(encoding="utf-8")

    # 1) DEFAULT_BAD_PACKAGES: Dict[str, List[str]] = { ... }
    new_bad = f"DEFAULT_BAD_PACKAGES: Dict[str, List[str]] = {dumps_python(bad_packages)}"
    pat_bad = r"DEFAULT_BAD_PACKAGES\s*:\s*Dict\[\s*str\s*,\s*List\[\s*str\s*\]\]\s*=\s*\{.*?\}"
    src, changed_bad = replace_block(src, pat_bad, new_bad)

    # 2) DEFAULT_EXTRA_TARGETS: List[str] = [ ... ]
    new_targets = f"DEFAULT_EXTRA_TARGETS: List[str] = {dumps_python(extra_targets)}"
    pat_targets = r"DEFAULT_EXTRA_TARGETS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    src, changed_targets = replace_block(src, pat_targets, new_targets)

    if changed_bad or changed_targets:
        target.write_text(src, encoding="utf-8")
    return changed_bad or changed_targets


def update_miners_defaults(scanner_root: Path, file_hints: list[str], proc_hints: list[str], script_patterns: list[str]) -> bool:
    """
    Met à jour les DEFAULT_* dans scanner/refs/miners.py
    - DEFAULT_MINER_FILE_HINTS
    - DEFAULT_MINER_PROC_HINTS
    - DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS
    """
    target = scanner_root / "scanner" / "refs" / "miners.py"
    if not target.exists():
        # Si le fichier n'existe pas (ou a un autre nom), on ignore proprement
        return False

    src = target.read_text(encoding="utf-8")

    # 1) DEFAULT_MINER_FILE_HINTS: List[str] = [ ... ]
    new_file = f"DEFAULT_MINER_FILE_HINTS: List[str] = {dumps_python(file_hints)}"
    pat_file = r"DEFAULT_MINER_FILE_HINTS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    src, c1 = replace_block(src, pat_file, new_file)

    # 2) DEFAULT_MINER_PROC_HINTS: List[str] = [ ... ]
    new_proc = f"DEFAULT_MINER_PROC_HINTS: List[str] = {dumps_python(proc_hints)}"
    pat_proc = r"DEFAULT_MINER_PROC_HINTS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    src, c2 = replace_block(src, pat_proc, new_proc)

    # 3) DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS: List[str] = [ ... ]
    new_scr = f"DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS: List[str] = {dumps_python(script_patterns)}"
    pat_scr = r"DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    src, c3 = replace_block(src, pat_scr, new_scr)

    if c1 or c2 or c3:
        target.write_text(src, encoding="utf-8")
    return c1 or c2 or c3


# ---------- Main ----------

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: update_defaults.py /chemin/vers/ioc-scanner")
        sys.exit(1)

    scanner_root = Path(sys.argv[1]).resolve()

    # Charger les JSON depuis ioc-signatures (repo courant)
    bad_packages = load_json(Path("bad_packages.json"))
    extra_targets = load_json(Path("targets.json")).get("extra_targets", [])

    # Optionnels (pour miners.py) : s'ils n'existent pas, on ne bloque pas
    file_hints = []
    proc_hints = []
    script_patterns = []
    try:
        file_hints = load_json(Path("miner_file_hints.json")).get("patterns", [])
    except FileNotFoundError:
        pass
    try:
        proc_hints = load_json(Path("miner_proc_hints.json")).get("patterns", [])
    except FileNotFoundError:
        pass
    try:
        script_patterns = load_json(Path("suspicious_patterns.json")).get("patterns", [])
    except FileNotFoundError:
        pass

    # Mises à jour
    changed_pkg = update_packages_defaults(scanner_root, bad_packages, extra_targets)
    changed_min = update_miners_defaults(scanner_root, file_hints, proc_hints, script_patterns)

    print(f"[✓] packages.py mis à jour: {changed_pkg}")
    print(f"[✓] miners.py   mis à jour: {changed_min}")


if __name__ == "__main__":
    main()
