#!/usr/bin/env python3
"""Run the catalog validator from the contributor-facing creator skill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


CATALOG_ROOT = Path(__file__).resolve().parents[3]
CATALOG_SCRIPTS = CATALOG_ROOT / "scripts"
if str(CATALOG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CATALOG_SCRIPTS))

from catalog_tooling import CatalogValidationError, validate_catalog  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a Luke catalog source or creator proposal bundle."
    )
    parser.add_argument("--catalog-root", required=True, type=Path)
    parser.add_argument(
        "--allow-draft-provenance",
        action="store_true",
        help="Allow null proposal/review URLs in a not-yet-submitted bundle.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        records = validate_catalog(
            arguments.catalog_root,
            allow_draft_provenance=arguments.allow_draft_provenance,
        )
    except CatalogValidationError as error:
        for diagnostic in error.diagnostics:
            print(diagnostic.render(), file=sys.stderr)
        return 1
    print(f"validated {len(records)} Luke catalog skill(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
