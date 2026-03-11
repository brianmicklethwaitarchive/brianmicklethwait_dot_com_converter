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
    if rel.endswith(".shtml.html"):
        aliases.add("/" + rel[: -len(".html")])
    return tuple(sorted(aliases))


def collect_pages(spec: BlogSpec) -> list[PageJob]:
    pages: list[PageJob] = [
        PageJob(spec.home_source, "index.html", spec.home_aliases),
    ]

    for source_file in sorted(spec.scan_root.rglob("*")):
        if not source_file.is_file():
            continue
        if source_file.suffix.lower() not in {".html", ".htm"}:
            continue

        rel = source_file.relative_to(spec.scan_root).as_posix()
        if rel == "index.html":
            continue

        pages.append(PageJob(source_file, rel, _default_old_paths(source_file)))

    return pages
