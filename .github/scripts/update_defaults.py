#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Met à jour les valeurs par défaut (DEFAULT_*) dans le dépôt IoC-Scanner
à partir des fichiers JSON de ce dépôt (ioc-signatures).

Usage:
    python .github/scripts/update_defaults.py /chemin/vers/ioc-scanner
Ex. dans le workflow:
    python .github/scripts/update_defaults.py IoC-Scanner
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Tuple


# ---------- Utils I/O ----------

def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"JSON introuvable: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def dumps_python(value: Any) -> str:
    """
    Sérialise via json.dumps pour obtenir un rendu stable et lisible.
    sort_keys=True pour des diffs Git déterministes.
    (Les chaînes JSON sont aussi valides en littéraux Python.)
    """
    return json.dumps(value, indent=4, ensure_ascii=False, sort_keys=True)


def replace_first(src: str, patterns: Iterable[str], replacement: str) -> Tuple[str, bool, str]:
    """
    Tente une suite de patterns (regex DOTALL), renvoie (nouvelle_source, changé, pattern_utilisé).
    Le premier pattern qui matche est remplacé une seule fois (count=1).
    """
    for pat in patterns:
        new_src, n = re.subn(pat, replacement, src, count=1, flags=re.DOTALL)
        if n:
            return new_src, True, pat
    return src, False, ""


def replace_between_marks(src: str, begin: str, end: str, payload: str) -> Tuple[str, bool]:
    """
    Remplace le contenu entre deux marqueurs *sur une seule occurrence*.
    Les marqueurs eux-mêmes sont conservés.
    """
    pattern = re.compile(
        rf"({re.escape(begin)})(.*?)[ \t]*({re.escape(end)})",
        re.DOTALL
    )
    replacement = r"\1" + payload + r"\3"
    new_src, n = pattern.subn(replacement, src, count=1)
    return new_src, bool(n)


def write_atomic(path: Path, content: str, create_backup: bool = True) -> None:
    """
    Écriture atomique : écrit dans un fichier temporaire puis remplace.
    Optionnellement, crée un .bak s'il existe déjà un fichier.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if create_backup and path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
        tmp.write(content if content.endswith("\n") else content + "\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


# ---------- Mises à jour concrètes ----------

def update_packages_defaults(scanner_root: Path, bad_packages: dict, extra_targets: list[str], verbose: bool = False) -> bool:
    """
    Met à jour DEFAULT_BAD_PACKAGES et DEFAULT_EXTRA_TARGETS dans scanner/refs/packages.py
    (Regex OK ici car pas de crochets ']' dans des chaînes.)
    """
    target = scanner_root / "scanner" / "refs" / "packages.py"
    if not target.exists():
        raise FileNotFoundError(f"Fichier introuvable: {target}")

    src = target.read_text(encoding="utf-8")

    # Déclarations à injecter
    new_bad = f"DEFAULT_BAD_PACKAGES: Dict[str, List[str]] = {dumps_python(bad_packages)}"
    new_targets = f"DEFAULT_EXTRA_TARGETS: List[str] = {dumps_python(extra_targets)}"

    # Patterns (annoté puis fallback sans annotation)
    pat_bad_annot = r"DEFAULT_BAD_PACKAGES\s*:\s*Dict\[\s*str\s*,\s*List\[\s*str\s*\]\]\s*=\s*\{.*?\}"
    pat_bad_plain = r"DEFAULT_BAD_PACKAGES\s*=\s*\{.*?\}"
    pat_targets_annot = r"DEFAULT_EXTRA_TARGETS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    pat_targets_plain = r"DEFAULT_EXTRA_TARGETS\s*=\s*\[.*?\]"

    src, c_bad, used_bad = replace_first(src, (pat_bad_annot, pat_bad_plain), new_bad)
    if verbose and c_bad:
        print(f"[packages.py] Remplacement DEFAULT_BAD_PACKAGES via pattern: {used_bad}")

    src, c_targets, used_targets = replace_first(src, (pat_targets_annot, pat_targets_plain), new_targets)
    if verbose and c_targets:
        print(f"[packages.py] Remplacement DEFAULT_EXTRA_TARGETS via pattern: {used_targets}")

    if c_bad or c_targets:
        write_atomic(target, src)
        return True
    return False


def update_miners_defaults(
    scanner_root: Path,
    file_hints: list[str],
    proc_hints: list[str],
    script_patterns: list[str],
    verbose: bool = False,
) -> bool:
    """
    Met à jour les DEFAULT_* dans scanner/refs/miners.py
    - DEFAULT_MINER_FILE_HINTS
    - DEFAULT_MINER_PROC_HINTS
    - DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS

    ⚠️ D'abord via MARQUEURS (plus sûr), sinon fallback regex.
    """
    target = scanner_root / "scanner" / "refs" / "miners.py"
    if not target.exists():
        if verbose:
            print(f"[miners.py] Absent, aucun changement.")
        return False

    src = target.read_text(encoding="utf-8")

    # Payloads
    new_file = f"DEFAULT_MINER_FILE_HINTS: List[str] = {dumps_python(file_hints)}"
    new_proc = f"DEFAULT_MINER_PROC_HINTS: List[str] = {dumps_python(proc_hints)}"
    new_scr  = f"DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS: List[str] = {dumps_python(script_patterns)}"

    # Marqueurs attendus dans miners.py
    m_file_begin = "# BEGIN DEFAULT_MINER_FILE_HINTS (AUTO)"
    m_file_end   = "# END DEFAULT_MINER_FILE_HINTS (AUTO)"
    m_proc_begin = "# BEGIN DEFAULT_MINER_PROC_HINTS (AUTO)"
    m_proc_end   = "# END DEFAULT_MINER_PROC_HINTS (AUTO)"
    m_scr_begin  = "# BEGIN DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS (AUTO)"
    m_scr_end    = "# END DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS (AUTO)"

    # 1) Tentative par marqueurs
    src2, c1 = replace_between_marks(src, m_file_begin, m_file_end, new_file)
    src3, c2 = replace_between_marks(src2, m_proc_begin, m_proc_end, new_proc)
    src4, c3 = replace_between_marks(src3, m_scr_begin, m_scr_end, new_scr)

    if c1 or c2 or c3:
        if verbose:
            print(f"[miners.py] Remplacement via MARQUEURS: file={c1}, proc={c2}, scr={c3}")
        write_atomic(target, src4)
        return True

    # 2) Fallback regex si pas de marqueurs
    if verbose:
        print("[miners.py] Marqueurs absents → fallback regex (moins sûr).")

    pat_file_annot = r"DEFAULT_MINER_FILE_HINTS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    pat_file_plain = r"DEFAULT_MINER_FILE_HINTS\s*=\s*\[.*?\]"
    pat_proc_annot = r"DEFAULT_MINER_PROC_HINTS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    pat_proc_plain = r"DEFAULT_MINER_PROC_HINTS\s*=\s*\[.*?\]"
    pat_scr_annot  = r"DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS\s*:\s*List\[\s*str\s*\]\s*=\s*\[.*?\]"
    pat_scr_plain  = r"DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS\s*=\s*\[.*?\]"

    src, c1, u1 = replace_first(src, (pat_file_annot, pat_file_plain), new_file)
    if verbose and c1:
        print(f"[miners.py] Remplacement DEFAULT_MINER_FILE_HINTS via pattern: {u1}")

    src, c2, u2 = replace_first(src, (pat_proc_annot, pat_proc_plain), new_proc)
    if verbose and c2:
        print(f"[miners.py] Remplacement DEFAULT_MINER_PROC_HINTS via pattern: {u2}")

    src, c3, u3 = replace_first(src, (pat_scr_annot, pat_scr_plain), new_scr)
    if verbose and c3:
        print(f"[miners.py] Remplacement DEFAULT_SUSPICIOUS_SCRIPT_PATTERNS via pattern: {u3}")

    if c1 or c2 or c3:
        write_atomic(target, src)
        return True
    return False


# ---------- Main ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mise à jour des DEFAULT_* d'IoC-Scanner depuis ioc-signatures.")
    p.add_argument("scanner_root", help="Chemin vers le dépôt IoC-Scanner")
    p.add_argument("--dry-run", action="store_true", help="N'écrit rien, affiche seulement les actions")
    p.add_argument("-v", "--verbose", action="store_true", help="Logs détaillés")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scanner_root = Path(args.scanner_root).resolve()

    # Charger les JSON depuis le repo courant (ioc-signatures)
    bad_packages = load_json(Path("bad_packages.json"))
    extra_targets = load_json(Path("targets.json")).get("extra_targets", [])

    # Optionnels (pour miners.py)
    try:
        file_hints = load_json(Path("miner_file_hints.json")).get("patterns", [])
    except FileNotFoundError:
        file_hints = []
    try:
        proc_hints = load_json(Path("miner_proc_hints.json")).get("patterns", [])
    except FileNotFoundError:
        proc_hints = []
    try:
        script_patterns = load_json(Path("suspicious_patterns.json")).get("patterns", [])
    except FileNotFoundError:
        script_patterns = []

    if args.verbose:
        bp_len = len(bad_packages) if isinstance(bad_packages, dict) else "n/a"
        print(f"[info] Scanner root: {scanner_root}")
        print(f"[info] bad_packages: {bp_len} / extra_targets: {len(extra_targets)} / "
              f"file_hints: {len(file_hints)} / proc_hints: {len(proc_hints)} / script_patterns: {len(script_patterns)}")

    changed_pkg = update_packages_defaults(scanner_root, bad_packages, extra_targets, verbose=args.verbose)
    changed_min = update_miners_defaults(scanner_root, file_hints, proc_hints, script_patterns, verbose=args.verbose)

    if args.dry_run:
        print("[dry-run] Exécution en mode dry-run terminée.")

    print(f"[✓] packages.py mis à jour: {changed_pkg}")
    print(f"[✓] miners.py   mis à jour: {changed_min}")

    # Code retour : 2 si changements, 0 sinon (ton workflow sait gérer 2)
    if changed_pkg or changed_min:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
