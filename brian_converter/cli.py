from __future__ import annotations

import argparse
import json

from brian_converter.pipeline import audit_blog, convert_many
from brian_converter.specs import BLOG_SPECS, selected_specs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert archived Brian Micklethwait blogs.")
    parser.add_argument("blog", choices=[*BLOG_SPECS.keys(), "all"])
    return parser


def main_convert() -> int:
    args = _parser().parse_args()
    results = convert_many(selected_specs(args.blog))
    for result in results:
        print(
            json.dumps(
                {
                    "blog": result.blog,
                    "generated_pages": result.generated_pages,
                    "copied_assets": result.copied_assets,
                    "rewritten_links": result.rewritten_links,
                    "removed_popup_image_links": result.removed_popup_image_links,
                    "unresolved_links": len(result.unresolved_links),
                    "unresolved_assets": len(result.unresolved_assets),
                }
            )
        )
    return 0


def main_audit() -> int:
    args = _parser().parse_args()
    exit_code = 0
    for spec in selected_specs(args.blog):
        ok, report = audit_blog(spec)
        print(json.dumps(report, indent=2))
        if not ok:
            exit_code = 1
    return exit_code
