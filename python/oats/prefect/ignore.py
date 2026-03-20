from __future__ import annotations

from collections.abc import Iterable
from os import PathLike
from typing import AnyStr

import pathspec


def filter_prefect_files(
    root: str | PathLike[str] = ".",
    ignore_patterns: Iterable[AnyStr] | None = None,
    include_dirs: bool = True,
) -> set[str]:
    spec = pathspec.GitIgnoreSpec.from_lines(ignore_patterns or [])
    ignored_files = {entry.path for entry in spec.match_tree_entries(root)}
    if include_dirs:
        all_files = {entry.path for entry in pathspec.util.iter_tree_entries(root)}
    else:
        all_files = set(pathspec.util.iter_tree_files(root))
    return all_files - ignored_files
