import os
from typing import Mapping

from ..utils import normalize_path
from .models import FileState, ManifestDiff


def get_file_state(filepath: str) -> FileState | None:
    try:
        stat_result = os.stat(filepath)
    except OSError:
        return None

    return FileState(
        filename=normalize_path(filepath),
        size=int(stat_result.st_size),
        mtime_ns=int(stat_result.st_mtime_ns),
    )


def plan_refresh(
    stored_manifest: Mapping[str, FileState],
    observed_manifest: Mapping[str, FileState],
) -> ManifestDiff:
    added: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []

    for filename, observed_state in observed_manifest.items():
        stored_state = stored_manifest.get(filename)
        if stored_state is None:
            added.append(filename)
            continue

        same_stat = (
            stored_state.size == observed_state.size
            and stored_state.mtime_ns == observed_state.mtime_ns
        )
        same_hash = (
            not stored_state.content_hash
            or not observed_state.content_hash
            or stored_state.content_hash == observed_state.content_hash
        )

        if same_stat and same_hash:
            unchanged.append(filename)
        else:
            changed.append(filename)

    removed = [filename for filename in stored_manifest if filename not in observed_manifest]

    return ManifestDiff(
        added=tuple(sorted(added)),
        changed=tuple(sorted(changed)),
        removed=tuple(sorted(removed)),
        unchanged=tuple(sorted(unchanged)),
    )