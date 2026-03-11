from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "www.brianmicklethwait.com"
JEKYLL_ROOT = PROJECT_ROOT / "brianmicklethwaitarchive-jekyll"


@dataclass(frozen=True)
class BlogSpec:
    name: str
    adapter: str
    public_root: str
    home_source: Path
    scan_root: Path
    home_aliases: tuple[str, ...]
    include_search: bool = False
    search_root: Path | None = None
    description: str = ""
    css_queries: tuple[str, ...] = field(default_factory=tuple)

    @property
    def output_root(self) -> Path:
        return JEKYLL_ROOT / self.public_root


BLOG_SPECS: dict[str, BlogSpec] = {
    "culture": BlogSpec(
        name="culture",
        adapter="mt",
        public_root="culture",
        home_source=SOURCE_ROOT / "culture.html",
        scan_root=SOURCE_ROOT / "culture",
        home_aliases=("/culture.html", "/culture/", "/culture/index.html"),
        description="Brian's Culture Blog",
    ),
    "education": BlogSpec(
        name="education",
        adapter="mt",
        public_root="education",
        home_source=SOURCE_ROOT / "education.html",
        scan_root=SOURCE_ROOT / "education",
        home_aliases=("/education.html", "/education/", "/education/index.html"),
        description="Brian's older Education Blog",
    ),
    "edublog": BlogSpec(
        name="edublog",
        adapter="ee",
        public_root="edublog",
        home_source=SOURCE_ROOT / "edublog.html",
        scan_root=SOURCE_ROOT / "index.php" / "education",
        home_aliases=(
            "/edublog.html",
            "/edublog/",
            "/edublog/index.html",
            "/index.php/education",
            "/index.php/education/",
            "/index.php/education/index.html",
            "/index.php/education.html",
        ),
        include_search=True,
        search_root=SOURCE_ROOT / "index.php" / "search",
        description="Brian's later education-era blog",
        css_queries=("education/weblog_css.css", "search/search_css.css"),
    ),
    "weblog": BlogSpec(
        name="weblog",
        adapter="ee",
        public_root="weblog",
        home_source=SOURCE_ROOT / "index.php.html",
        scan_root=SOURCE_ROOT / "index.php" / "weblog",
        home_aliases=(
            "/index.php.html",
            "/index.php",
            "/index.php/",
            "/index.php/index.html",
            "/index.html",
            "/weblog/",
            "/weblog/index.html",
            "/index.php/weblog",
            "/index.php/weblog/",
            "/index.php/weblog/index.html",
        ),
        include_search=True,
        search_root=SOURCE_ROOT / "index.php" / "search",
        description="Brian's main weblog",
        css_queries=("weblog/weblog_css.css", "search/search_css.css"),
    ),
}


def selected_specs(target: str) -> list[BlogSpec]:
    if target == "all":
        return [BLOG_SPECS[name] for name in ("culture", "education", "edublog", "weblog")]
    return [BLOG_SPECS[target]]
