from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html import escape, unescape
from pathlib import Path

from brian_converter.specs import BlogSpec, SOURCE_ROOT

BLOG_RE = re.compile(r"""<div class="blog">(?P<content>.*?)</div>\s*</div>\s*<div id="links">""", re.DOTALL)
ARCHIVES_RE = re.compile(
    r"""(<div class="sidetitle">Archives</div>\s*<div class="side">)(?P<content>.*?)(</div>)(?=\s*<div class="sidetitle">)""",
    re.DOTALL,
)
DATE_RE = re.compile(
    r"""<div class="date">(?P<month>[A-Za-z]+)&nbsp;(?P<day>\d{1,2}), <span class="year">(?P<year>\d{4})</span></div>""",
    re.DOTALL,
)
TITLE_RE = re.compile(r"""<div class="title">(?P<title>.*?)</div>""", re.DOTALL)
POSTED_RE = re.compile(
    r"""Posted by Brian Micklethwait at <a href="[^"]+">(?P<time>\d{1,2}:\d{2} [AP]M)</a>""",
    re.DOTALL,
)


@dataclass(frozen=True)
class PageJob:
    source_file: Path
    output_rel: str
    old_paths: tuple[str, ...]
    source_html: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ArchiveEntry:
    source_file: Path
    output_rel: str
    old_paths: tuple[str, ...]
    title: str
    published_at: datetime
    date_label: str
    month_key: tuple[int, int]
    month_label: str

    @property
    def primary_old_path(self) -> str:
        return self.old_paths[0]


def _default_old_paths(file_path: Path) -> tuple[str, ...]:
    rel = file_path.relative_to(SOURCE_ROOT).as_posix()
    old_path = f"/{rel}"
    aliases = {old_path}
    if rel.endswith("/index.html"):
        aliases.add("/" + rel[: -len("index.html")])
    if rel.endswith(".shtml.html"):
        aliases.add("/" + rel[: -len(".html")])
    return tuple(sorted(aliases))


def _parse_entry(source_file: Path) -> ArchiveEntry | None:
    text = source_file.read_text(encoding="latin-1")
    date_match = DATE_RE.search(text)
    title_match = TITLE_RE.search(text)
    posted_match = POSTED_RE.search(text)
    if date_match is None or title_match is None or posted_match is None:
        return None

    month_name = unescape(date_match.group("month"))
    day = int(date_match.group("day"))
    year = int(date_match.group("year"))
    time_label = posted_match.group("time")
    published_at = datetime.strptime(f"{month_name} {day} {year} {time_label}", "%B %d %Y %I:%M %p")

    rel = source_file.relative_to(source_file.parents[3]).as_posix()
    title_text = re.sub(r"<.*?>", "", title_match.group("title"))
    title = unescape(" ".join(title_text.split()))
    return ArchiveEntry(
        source_file=source_file,
        output_rel=rel,
        old_paths=_default_old_paths(source_file),
        title=title,
        published_at=published_at,
        date_label=published_at.strftime("%B %d, %Y"),
        month_key=(published_at.year, published_at.month),
        month_label=published_at.strftime("%B %Y"),
    )


def _collect_entries(spec: BlogSpec) -> list[ArchiveEntry]:
    entries: list[ArchiveEntry] = []
    archives_root = spec.scan_root / "archives"
    for source_file in sorted(archives_root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*")):
        if not source_file.is_file():
            continue
        if source_file.suffix.lower() not in {".html", ".htm"}:
            continue
        entry = _parse_entry(source_file)
        if entry is not None:
            entries.append(entry)
    return sorted(entries, key=lambda entry: (entry.published_at, entry.output_rel), reverse=True)


def _month_index_old_paths(spec: BlogSpec, year: int, month: int) -> tuple[str, ...]:
    base = f"/{spec.public_root}/archives/{year:04d}/{month:02d}"
    return (f"{base}/", f"{base}/index.html", base)


def _archive_sidebar(spec: BlogSpec, month_entries: list[tuple[str, int, str]]) -> str:
    if not month_entries:
        return "<br />"
    lines = []
    for href, count, label in month_entries:
        suffix = "" if count == 1 else "s"
        lines.append(f'<a href="http://www.brianmicklethwait.com{href}">{escape(label)}</a> ({count} post{suffix})<br />')
    return "\n".join(lines)


def _replace_archive_sidebar(text: str, sidebar_html: str) -> str:
    match = ARCHIVES_RE.search(text)
    if match is None:
        return text
    return text[: match.start()] + match.group(1) + "\n" + sidebar_html + "\n" + match.group(3) + text[match.end() :]


def _listing_html(
    heading: str,
    entries: list[ArchiveEntry],
    more_href: str | None,
    more_label: str | None,
) -> str:
    parts = [f'<div class="title">{escape(heading)}</div>', ""]
    for entry in entries:
        parts.extend(
            [
                f'<div class="date">{escape(entry.date_label)}</div>',
                "",
                '<div class="blogbody">',
                f'<div class="title"><a href="http://www.brianmicklethwait.com{entry.primary_old_path}">{escape(entry.title)}</a></div>',
                "</div>",
                "",
            ]
        )
    if more_href and more_label:
        parts.extend(
            [
                '<div class="blogbody">',
                f'<p><a href="http://www.brianmicklethwait.com{more_href}">{escape(more_label)}</a></p>',
                "</div>",
                "",
            ]
        )
    return "\n".join(parts)


def _replace_blog_content(text: str, blog_html: str) -> str:
    match = BLOG_RE.search(text)
    if match is None:
        return text
    return text[: match.start("content")] + "\n" + blog_html + "\n" + text[match.end("content") :]


def _month_groups(entries: list[ArchiveEntry]) -> list[tuple[tuple[int, int], list[ArchiveEntry]]]:
    grouped: dict[tuple[int, int], list[ArchiveEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.month_key, []).append(entry)
    return sorted(grouped.items(), key=lambda item: item[0], reverse=True)


def _month_sidebar_entries(spec: BlogSpec, grouped_entries: list[tuple[tuple[int, int], list[ArchiveEntry]]]) -> list[tuple[str, int, str]]:
    items: list[tuple[str, int, str]] = []
    for (year, month), entries in grouped_entries:
        items.append((f"/{spec.public_root}/archives/{year:04d}/{month:02d}/", len(entries), entries[0].month_label))
    return items


def _synthesize_home_page(spec: BlogSpec, entries: list[ArchiveEntry], sidebar_html: str) -> PageJob:
    template = spec.home_source.read_text(encoding="latin-1")
    latest_entries = entries[:12]
    more_href = None
    more_label = None
    if len(entries) > len(latest_entries):
        oldest_displayed = latest_entries[-1]
        year, month = oldest_displayed.month_key
        more_href = f"/{spec.public_root}/archives/{year:04d}/{month:02d}/"
        more_label = f"More from {oldest_displayed.month_label} and earlier"

    source_html = _replace_archive_sidebar(template, sidebar_html)
    source_html = _replace_blog_content(
        source_html,
        _listing_html("Latest Entries", latest_entries, more_href, more_label),
    )
    return PageJob(
        source_file=spec.home_source,
        output_rel="index.html",
        old_paths=spec.home_aliases,
        source_html=source_html,
        source_url=f"http://www.brianmicklethwait.com/{spec.home_source.relative_to(SOURCE_ROOT).as_posix()}",
    )


def _synthesize_month_pages(
    spec: BlogSpec,
    grouped_entries: list[tuple[tuple[int, int], list[ArchiveEntry]]],
    sidebar_html: str,
) -> list[PageJob]:
    template = spec.home_source.read_text(encoding="latin-1")
    pages: list[PageJob] = []
    for index, ((year, month), entries) in enumerate(grouped_entries):
        more_href = None
        more_label = None
        if index + 1 < len(grouped_entries):
            next_year, next_month = grouped_entries[index + 1][0]
            next_label = grouped_entries[index + 1][1][0].month_label
            more_href = f"/{spec.public_root}/archives/{next_year:04d}/{next_month:02d}/"
            more_label = f"More from {next_label}"

        source_html = _replace_archive_sidebar(template, sidebar_html)
        source_html = _replace_blog_content(
            source_html,
            _listing_html(f"Archive for {entries[0].month_label}", entries, more_href, more_label),
        )
        output_rel = f"archives/{year:04d}/{month:02d}/index.html"
        pages.append(
            PageJob(
                source_file=spec.home_source,
                output_rel=output_rel,
                old_paths=_month_index_old_paths(spec, year, month),
                source_html=source_html,
                source_url=f"http://www.brianmicklethwait.com/{spec.home_source.relative_to(SOURCE_ROOT).as_posix()}",
            )
        )
    return pages


def collect_pages(spec: BlogSpec) -> list[PageJob]:
    entries = _collect_entries(spec)
    grouped_entries = _month_groups(entries)
    sidebar_html = _archive_sidebar(spec, _month_sidebar_entries(spec, grouped_entries))

    pages: list[PageJob] = [_synthesize_home_page(spec, entries, sidebar_html)]
    pages.extend(_synthesize_month_pages(spec, grouped_entries, sidebar_html))

    for source_file in sorted(spec.scan_root.rglob("*")):
        if not source_file.is_file():
            continue
        if source_file.suffix.lower() not in {".html", ".htm"}:
            continue

        rel = source_file.relative_to(spec.scan_root).as_posix()
        if rel == "index.html":
            continue
        if re.fullmatch(r"archives/\d{4}/\d{2}/index\.html", rel):
            continue

        source_html = _replace_archive_sidebar(source_file.read_text(encoding="latin-1"), sidebar_html)
        pages.append(
            PageJob(
                source_file=source_file,
                output_rel=rel,
                old_paths=_default_old_paths(source_file),
                source_html=source_html,
            )
        )

    return pages
