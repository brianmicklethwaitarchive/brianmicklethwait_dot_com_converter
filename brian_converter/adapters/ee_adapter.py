from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brian_converter.specs import BlogSpec, SOURCE_ROOT


@dataclass(frozen=True)
class PageJob:
    source_file: Path
    output_rel: str
    old_paths: tuple[str, ...]


def _default_old_paths(file_path: Path) -> tuple[str, ...]:
    rel = file_path.relative_to(SOURCE_ROOT).as_posix()
    old_path = f"/{rel}"
    aliases = {old_path}
    if rel.endswith("/index.html"):
        aliases.add("/" + rel[: -len("index.html")])
    return tuple(sorted(aliases))


def collect_pages(spec: BlogSpec) -> list[PageJob]:
    pages: list[PageJob] = [
        PageJob(spec.home_source, "index.html", spec.home_aliases),
    ]

    for source_file in sorted(spec.scan_root.rglob("*.html")):
        rel = source_file.relative_to(spec.scan_root).as_posix()
        pages.append(PageJob(source_file, rel, _default_old_paths(source_file)))

    if spec.include_search and spec.search_root is not None:
        for source_file in sorted(spec.search_root.rglob("*.html")):
            rel = source_file.relative_to(spec.search_root).as_posix()
            output_rel = f"search/{rel}"
            pages.append(PageJob(source_file, output_rel, _default_old_paths(source_file)))

    top_level_index_php = SOURCE_ROOT / "index.php"
    for source_file in sorted(top_level_index_php.glob("C*/index.html")):
        rel = source_file.relative_to(top_level_index_php).as_posix()
        output_rel = rel
        pages.append(PageJob(source_file, output_rel, _default_old_paths(source_file)))

    return pages
