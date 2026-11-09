"""Cache privé de calibration pour le moteur local, non destiné à des fichiers partagés.

Le cache contient des objets Python sérialisés (pickle), lus exclusivement depuis
un dossier généré par cette application. Ne jamais y placer de fichiers externes.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import tempfile
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")
CACHE_VERSION = 1


def fingerprint(files: list[Path], parameters: dict) -> str:
    """L'empreinte change lorsque les données, paramètres ou le code changent."""
    manifests = []
    for path in files:
        stat = path.stat() if path.exists() else None
        manifests.append({
            "path": str(path.resolve()),
            "size": stat.st_size if stat else None,
            "modified_ns": stat.st_mtime_ns if stat else None,
        })
    manifest = {"version": CACHE_VERSION, "files": manifests, "parameters": parameters}
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


def load_or_build(cache_dir: Path, namespace: str, key: str, build: Callable[[], T]) -> T:
    """Écriture atomique; en cas de corruption recalcul. Cache accessible au seul propriétaire."""
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = cache_dir / f"{namespace}-{key}.pickle"
    if path.is_file():
        try:
            # Ne jamais utiliser ce mécanisme avec un cache téléchargé ou non fiable.
            with path.open("rb") as handle:
                return pickle.load(handle)
        except (OSError, EOFError, ValueError, TypeError, AttributeError, ImportError, pickle.UnpicklingError):
            try:
                path.unlink()
            except OSError:
                pass
    result = build()
    # Ne pas échouer une estimation correcte à cause d'un cache non accessible.
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".eco-routage-", dir=cache_dir)
        with os.fdopen(fd, "wb") as handle:
            if hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), 0o600)
            pickle.dump(result, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temporary, path)
    except OSError:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
    return result
