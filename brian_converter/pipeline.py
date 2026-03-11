from __future__ import annotations

import json
import posixpath
import re
import shutil
from html import unescape
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

from brian_converter.adapters import ee_adapter, mt_adapter
from brian_converter.specs import BLOG_SPECS, BlogSpec, JEKYLL_ROOT, SOURCE_ROOT

OLD_HOSTS = {"www.brianmicklethwait.com", "brianmicklethwait.com"}
FORBIDDEN_PATTERNS = (
    "http://www.brianmicklethwait.com",
    "https://www.brianmicklethwait.com",
    "index.php%3Fcss=",
    "cgi-bin",
    "mt-comments",
    "mt-search",
    "mt-tb",
)

SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.IGNORECASE | re.DOTALL)
FORM_RE = re.compile(r"<form\b.*?</form>", re.IGNORECASE | re.DOTALL)
BROKEN_FORM_RE = re.compile(r"<form\b.*?</div>", re.IGNORECASE | re.DOTALL)
SEARCH_FORM_RE = re.compile(
    r"""<form\b[^>]*mt-search\.cgi[^>]*>.*?(?:</form>|</div>)""",
    re.IGNORECASE | re.DOTALL,
)
IMPORT_STYLE_RE = re.compile(r"<style\b[^>]*>.*?@import.*?</style>", re.IGNORECASE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEAD_META_LINK_RE = re.compile(
    r"""<link\b[^>]*rel=(['"])(?:alternate|EditURI)\1[^>]*>""",
    re.IGNORECASE | re.DOTALL,
)
ON_EVENT_RE = re.compile(r"""\s+on[a-z]+\s*=\s*(['"]).*?\1""", re.IGNORECASE | re.DOTALL)
UNWANTED_ANCHOR_RE = re.compile(
    r"""<a\b[^>]*href=(['"])[^'"]*(?:mt-comments\.cgi|mt-tb\.cgi|mt-search\.cgi|cgi-bin)[^'"]*\1[^>]*>.*?</a>""",
    re.IGNORECASE | re.DOTALL,
)
ANCHOR_IMG_RE = re.compile(
    r"""<a\b(?P<attrs>[^>]*?)href=(?P<quote>['"])(?P<href>.*?)(?P=quote)(?P<tail>[^>]*)>\s*(?P<img><img\b.*?>)\s*</a>""",
    re.IGNORECASE | re.DOTALL,
)
BROKEN_HREF_IMG_RE = re.compile(
    r"""<href=(?P<quote>['"]).*?(?P=quote)>\s*(?P<img><img\b.*?>)\s*</a>""",
    re.IGNORECASE | re.DOTALL,
)
ATTR_RE = re.compile(
    r"""(?P<attr>\b(?:href|src|action)\s*=\s*)(?P<quote>['"])(?P<value>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)
CSS_URL_RE = re.compile(r"""url\((?P<quote>['"]?)(?P<value>.*?)(?P=quote)\)""", re.IGNORECASE)
ANCHOR_NAME_RE = re.compile(r"""<a\s+name=(['"]?)(?P<name>[A-Za-z0-9_]+)\1""", re.IGNORECASE)


@dataclass(frozen=True)
class PageRecord:
    spec: BlogSpec
    source_file: Path
    output_rel: str
    old_paths: tuple[str, ...]
    source_html: str | None = None
    source_url: str | None = None

    @property
    def output_file(self) -> Path:
        return self.spec.output_root / self.output_rel

    @property
    def public_url(self) -> str:
        if self.output_rel == "index.html":
            return f"/{self.spec.public_root}/"
        return f"/{self.spec.public_root}/{self.output_rel}"


@dataclass
class ConversionStats:
    blog: str
    generated_pages: int = 0
    copied_assets: int = 0
    rewritten_links: int = 0
    removed_popup_image_links: int = 0
    unresolved_links: set[str] | None = None
    unresolved_assets: set[str] | None = None

    def __post_init__(self) -> None:
        if self.unresolved_links is None:
            self.unresolved_links = set()
        if self.unresolved_assets is None:
            self.unresolved_assets = set()


def _quote_path(path: str) -> str:
    return "/".join(quote(part, safe="@:+,()[]-_.~") for part in path.split("/"))


def _rel_url(from_rel: str, to_rel: str) -> str:
    from_dir = PurePosixPath(from_rel).parent
    rel = posixpath.relpath(str(PurePosixPath(to_rel)), str(from_dir))
    return _quote_path(rel)


def _load_records() -> list[PageRecord]:
    records: list[PageRecord] = []
    for spec in BLOG_SPECS.values():
        if spec.adapter == "mt":
            jobs = mt_adapter.collect_pages(spec)
        else:
            jobs = ee_adapter.collect_pages(spec)
        records.extend(
            PageRecord(
                spec,
                job.source_file,
                job.output_rel,
                job.old_paths,
                getattr(job, "source_html", None),
                getattr(job, "source_url", None),
            )
            for job in jobs
        )
    return records


def _build_page_index(records: Iterable[PageRecord]) -> dict[str, PageRecord]:
    index: dict[str, PageRecord] = {}
    for record in records:
        for old_path in record.old_paths:
            index[old_path] = record
            decoded = unquote(old_path)
            index[decoded] = record
    return index


def _normalize_path(raw_path: str) -> str:
    raw_path = raw_path.replace("\\", "/")
    if raw_path.endswith("/") and raw_path != "/":
        normal = posixpath.normpath(raw_path)
        return normal + "/"
    return posixpath.normpath(raw_path)


def _decode_mirror_external(parts) -> str | None:
    query = parse_qs(parts.query)
    if "URL" in query and query["URL"]:
        return query["URL"][0]
    decoded_path = unquote(parts.path)
    if "?URL=" in decoded_path:
        return decoded_path.split("?URL=", 1)[1]
    return None


def _css_query_key(parts) -> str | None:
    query = parse_qs(parts.query)
    if "css" in query and query["css"]:
        return unquote(query["css"][0])
    decoded_path = unquote(parts.path)
    if "?css=" in decoded_path:
        return unquote(decoded_path.split("?css=", 1)[1])
    return None


def _resolve_internal_url(raw_url: str, current_source_url: str) -> tuple[str, str | None]:
    cleaned = unescape(raw_url.strip()).replace("&amp;", "&").replace("\\", "/")
    if not cleaned or cleaned.startswith(("#", "mailto:", "javascript:", "data:", "tel:")):
        return ("leave", raw_url)
    if cleaned.startswith("www.brianmicklethwait.com/"):
        cleaned = f"http://{cleaned}"

    absolute = urljoin(current_source_url, cleaned)
    parts = urlparse(absolute)
    if parts.scheme in {"http", "https"} and parts.netloc and parts.netloc not in OLD_HOSTS:
        return ("leave", absolute)
    if cleaned.lower().startswith(("http:", "https:")) and not parts.netloc:
        return ("leave", cleaned)

    mirrored_external = _decode_mirror_external(parts)
    if mirrored_external:
        return ("leave", mirrored_external)

    css_key = _css_query_key(parts)
    if css_key:
        return ("css", css_key)

    normalized_path = _normalize_path(unquote(parts.path or "/"))
    fragment = parts.fragment or None
    return ("path", f"{normalized_path}#{fragment}" if fragment else normalized_path)


def _local_asset_source(path_key: str) -> Path | None:
    if path_key.endswith((".html", ".htm")):
        return None
    source = SOURCE_ROOT / path_key.lstrip("/")
    if source.exists() and source.is_file():
        return source
    return None


def _fallback_mt_asset(path_key: str) -> Path | None:
    match = re.match(
        r"^/(?P<blog>culture|education)/archives/[^/]+/(?P<tail>(?:img/.*|bm_style\.css|bm_forms\.css|rsd\.xml|index\.xml))$",
        path_key,
    )
    if match:
        candidate = SOURCE_ROOT / match.group("blog") / match.group("tail")
        if candidate.exists() and candidate.is_file():
            return candidate
    root_file_match = re.match(r"^/(?P<blog>culture|education)/archives/(?P<name>[^/]+\.(?:jpg|jpeg|gif|png|webp|bmp|svg))$", path_key, re.IGNORECASE)
    if root_file_match:
        candidate = SOURCE_ROOT / root_file_match.group("blog") / root_file_match.group("name")
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _css_source(css_key: str) -> Path | None:
    candidates = []
    for candidate_key in (css_key, unquote(css_key), quote(unquote(css_key), safe="")):
        candidate = SOURCE_ROOT / f"index.php?css={candidate_key}"
        if candidate not in candidates:
            candidates.append(candidate)
    for source in candidates:
        if source.exists() and source.is_file():
            return source
    return None


def _asset_output_rel(asset_source: Path) -> str:
    rel = asset_source.relative_to(SOURCE_ROOT).as_posix()
    if asset_source.name.startswith("index.php?css="):
        css_key = unquote(asset_source.name.split("?css=", 1)[1])
        return f"assets/css/{css_key}"
    return f"assets/{rel}"


def _rewrite_css(
    text: str,
    css_source: Path,
    css_output_rel: str,
    asset_sources: set[Path],
    unresolved_assets: set[str],
) -> str:
    current_source_url = f"http://www.brianmicklethwait.com/{css_source.relative_to(SOURCE_ROOT).as_posix()}"

    def replace_url(match: re.Match[str]) -> str:
        value = match.group("value").strip()
        if not value or value.startswith(("data:", "http://", "https://", "#")):
            return match.group(0)

        kind, resolved = _resolve_internal_url(value, current_source_url)
        if kind == "path" and resolved is not None:
            path_key = resolved.split("#", 1)[0]
            asset_source = _local_asset_source(path_key)
            if asset_source is None:
                unresolved_assets.add(value)
                return match.group(0)
            asset_sources.add(asset_source)
            asset_rel = _asset_output_rel(asset_source)
            rel = _rel_url(css_output_rel, asset_rel)
            return f"url({match.group('quote')}{rel}{match.group('quote')})"

        if kind == "css" and resolved is not None:
            css_file = _css_source(resolved)
            if css_file is None:
                unresolved_assets.add(value)
                return match.group(0)
            asset_sources.add(css_file)
            asset_rel = _asset_output_rel(css_file)
            rel = _rel_url(css_output_rel, asset_rel)
            return f"url({match.group('quote')}{rel}{match.group('quote')})"

        return match.group(0)

    return CSS_URL_RE.sub(replace_url, text)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_anchor_index(records: Iterable[PageRecord]) -> dict[str, PageRecord]:
    index: dict[str, PageRecord] = {}
    for record in records:
        if record.source_file.suffix.lower() not in {".html", ".htm"}:
            continue
        text = record.source_file.read_text(encoding="latin-1")
        for match in ANCHOR_NAME_RE.finditer(text):
            anchor_name = match.group("name")
            if anchor_name.isdigit():
                index.setdefault(anchor_name, record)
    return index


def _anchor_target(
    path_key: str,
    fragment: str | None,
    anchor_index: dict[str, PageRecord],
) -> tuple[PageRecord, str | None] | None:
    if fragment and fragment in anchor_index:
        return anchor_index[fragment], fragment

    stem_match = re.search(r"/(?P<entry>\d{5,})\.shtml$", path_key)
    if stem_match:
        entry_id = stem_match.group("entry")
        if entry_id in anchor_index:
            return anchor_index[entry_id], entry_id

    return None


def _should_unwrap_anchor(href: str, attrs: str, current_source_url: str, page_index: dict[str, PageRecord]) -> bool:
    if "window.open" in attrs.lower():
        return True
    kind, resolved = _resolve_internal_url(href, current_source_url)
    if kind == "css":
        return False
    if kind == "path" and resolved is not None:
        path_key = resolved.split("#", 1)[0]
        if path_key in page_index:
            return False
        if path_key.endswith((".jpg", ".jpeg", ".gif", ".png", ".webp", ".bmp", ".svg")):
            return True
        if path_key.endswith(".shtml"):
            return True
    return False


def _rewrite_page(
    record: PageRecord,
    page_index: dict[str, PageRecord],
    anchor_index: dict[str, PageRecord],
    asset_sources: set[Path],
    stats: ConversionStats,
) -> str:
    text = record.source_html if record.source_html is not None else record.source_file.read_text(encoding="latin-1")
    current_source_url = record.source_url or f"http://www.brianmicklethwait.com/{record.source_file.relative_to(SOURCE_ROOT).as_posix()}"

    text = SCRIPT_RE.sub("", text)
    text = FORM_RE.sub("", text)
    text = BROKEN_FORM_RE.sub("</div>", text)
    text = SEARCH_FORM_RE.sub("</div>", text)
    text = IMPORT_STYLE_RE.sub("", text)
    text = COMMENT_RE.sub("", text)
    text = HEAD_META_LINK_RE.sub("", text)
    text = UNWANTED_ANCHOR_RE.sub("", text)
    text = ON_EVENT_RE.sub("", text)

    def unwrap_anchor(match: re.Match[str]) -> str:
        if _should_unwrap_anchor(match.group("href"), match.group("attrs") + match.group("tail"), current_source_url, page_index):
            stats.removed_popup_image_links += 1
            return match.group("img")
        return match.group(0)

    text = ANCHOR_IMG_RE.sub(unwrap_anchor, text)
    text = BROKEN_HREF_IMG_RE.sub(lambda match: match.group("img"), text)
    current_site_rel = f"{record.spec.public_root}/{record.output_rel}"

    def rewrite_attr(match: re.Match[str]) -> str:
        attr = match.group("attr")
        quote = match.group("quote")
        raw_value = match.group("value")
        if "\n" in raw_value or "<br" in raw_value.lower():
            stats.rewritten_links += 1
            return f"{attr}{quote}#{quote}"

        kind, resolved = _resolve_internal_url(raw_value, current_source_url)
        if kind == "leave" or resolved is None:
            return match.group(0) if resolved == raw_value else f"{attr}{quote}{resolved}{quote}"

        if kind == "css":
            css_source = _css_source(resolved)
            if css_source is None:
                stats.unresolved_assets.add(raw_value)
                return match.group(0)
            asset_sources.add(css_source)
            asset_rel = _asset_output_rel(css_source)
            stats.rewritten_links += 1
            return f"{attr}{quote}{_rel_url(current_site_rel, f'{record.spec.public_root}/{asset_rel}')}{quote}"

        path_key, fragment = (resolved.split("#", 1) + [None])[:2]
        page_target = page_index.get(path_key)
        if page_target is not None:
            target_site_rel = f"{page_target.spec.public_root}/{page_target.output_rel}"
            rel = _rel_url(current_site_rel, target_site_rel)
            if fragment:
                rel = f"{rel}#{fragment}"
            stats.rewritten_links += 1
            return f"{attr}{quote}{rel}{quote}"

        anchor_target = _anchor_target(path_key, fragment, anchor_index)
        if anchor_target is not None:
            anchor_record, anchor_name = anchor_target
            target_site_rel = f"{anchor_record.spec.public_root}/{anchor_record.output_rel}"
            rel = _rel_url(current_site_rel, target_site_rel)
            if anchor_name:
                rel = f"{rel}#{anchor_name}"
            stats.rewritten_links += 1
            return f"{attr}{quote}{rel}{quote}"

        asset_source = _local_asset_source(path_key)
        if asset_source is None:
            asset_source = _fallback_mt_asset(path_key)
        if asset_source is not None:
            asset_sources.add(asset_source)
            asset_rel = _asset_output_rel(asset_source)
            rel = _rel_url(current_site_rel, f"{record.spec.public_root}/{asset_rel}")
            if fragment:
                rel = f"{rel}#{fragment}"
            stats.rewritten_links += 1
            return f"{attr}{quote}{rel}{quote}"

        if path_key.startswith("/") and path_key not in page_index:
            if "mt-search.cgi" in path_key:
                stats.rewritten_links += 1
                return f"{attr}{quote}#{quote}"
            email_target = path_key.rsplit("/", 1)[-1]
            if attr.lower().startswith("href") and "@" in email_target and "." in email_target:
                stats.rewritten_links += 1
                return f"{attr}{quote}mailto:{email_target}{quote}"
            if attr.lower().startswith("src") and path_key.lower().endswith(
                (".jpg", ".jpeg", ".gif", ".png", ".webp", ".bmp", ".svg")
            ):
                stats.rewritten_links += 1
                return f"{attr}{quote}{quote}"
            if path_key.endswith(".rdf"):
                stats.rewritten_links += 1
                return f"{attr}{quote}#{quote}"
            if path_key.endswith(".shtml"):
                stats.rewritten_links += 1
                if re.search(r"/\d{4}_\d{2}\.shtml$", path_key):
                    home_rel = _rel_url(current_site_rel, f"{record.spec.public_root}/index.html")
                    return f"{attr}{quote}{home_rel}{quote}"
                return f"{attr}{quote}#{quote}"
            stats.unresolved_links.add(raw_value)
        return match.group(0)

    return ATTR_RE.sub(rewrite_attr, text)


def _copy_assets(spec: BlogSpec, asset_sources: Iterable[Path], stats: ConversionStats) -> None:
    queue = list(sorted(set(asset_sources)))
    seen: set[Path] = set()
    while queue:
        asset_source = queue.pop(0)
        if asset_source in seen:
            continue
        seen.add(asset_source)

        output_rel = _asset_output_rel(asset_source)
        output_file = spec.output_root / output_rel
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if asset_source.name.startswith("index.php?css="):
            css_text = asset_source.read_text(encoding="latin-1")
            nested_assets: set[Path] = set()
            rewritten = _rewrite_css(
                css_text,
                asset_source,
                output_rel,
                nested_assets,
                stats.unresolved_assets,
            )
            _write_text(output_file, rewritten)
            for nested in sorted(nested_assets):
                if nested not in seen:
                    queue.append(nested)
        else:
            shutil.copy2(asset_source, output_file)
        stats.copied_assets += 1


def clean_output(spec: BlogSpec) -> None:
    if spec.output_root.exists():
        shutil.rmtree(spec.output_root)
    spec.output_root.mkdir(parents=True, exist_ok=True)


def convert_blog(spec: BlogSpec, page_index: dict[str, PageRecord]) -> ConversionStats:
    clean_output(spec)
    all_records = _load_records()
    anchor_index = _build_anchor_index(all_records)
    records = [record for record in all_records if record.spec.name == spec.name]
    stats = ConversionStats(blog=spec.name)
    asset_sources: set[Path] = set()

    for record in records:
        rewritten = _rewrite_page(record, page_index, anchor_index, asset_sources, stats)
        _write_text(record.output_file, rewritten)
        stats.generated_pages += 1

    _copy_assets(spec, asset_sources, stats)
    report = {
        "blog": spec.name,
        "generated_pages": stats.generated_pages,
        "copied_assets": stats.copied_assets,
        "rewritten_links": stats.rewritten_links,
        "removed_popup_image_links": stats.removed_popup_image_links,
        "unresolved_links": sorted(stats.unresolved_links),
        "unresolved_assets": sorted(stats.unresolved_assets),
    }
    _write_text(spec.output_root / "converter-report.json", json.dumps(report, indent=2) + "\n")
    return stats


def convert_many(specs: Iterable[BlogSpec]) -> list[ConversionStats]:
    records = _load_records()
    page_index = _build_page_index(records)
    return [convert_blog(spec, page_index) for spec in specs]


def audit_blog(spec: BlogSpec) -> tuple[bool, dict[str, object]]:
    output_root = spec.output_root
    html_files = sorted(output_root.rglob("*.html")) + sorted(output_root.rglob("*.htm"))
    offenders: dict[str, list[str]] = {}
    report_file = output_root / "converter-report.json"
    report_data = {}
    if report_file.exists():
        report_data = json.loads(report_file.read_text(encoding="utf-8"))

    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        attr_values = [match.group("value") for match in ATTR_RE.finditer(text)]
        file_offenders = [pattern for pattern in FORBIDDEN_PATTERNS if any(pattern in value for value in attr_values)]
        if file_offenders:
            offenders[html_file.relative_to(JEKYLL_ROOT).as_posix()] = file_offenders

    unresolved_links = [
        link
        for link in report_data.get("unresolved_links", [])
        if "brianmicklethwait.com" in link or link.startswith("/")
    ]
    unresolved_assets = report_data.get("unresolved_assets", [])
    ok = not offenders and not unresolved_links and not unresolved_assets
    return ok, {
        "blog": spec.name,
        "html_files_checked": len(html_files),
        "pattern_offenders": offenders,
        "unresolved_links": unresolved_links,
        "unresolved_assets": unresolved_assets,
    }
