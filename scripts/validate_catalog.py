#!/usr/bin/env python3
"""Validate Luke catalog source, evaluations, and optionally its generated index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from catalog_tooling import (
    CatalogValidationError,
    check_catalog_index,
    validate_catalog,
)


DEFAULT_CATALOG_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Luke catalog V1 inputs.")
    parser.add_argument("--catalog-root", type=Path, default=DEFAULT_CATALOG_ROOT)
    parser.add_argument(
        "--allow-draft-provenance",
        action="store_true",
        help="Allow proposal bundles that do not yet have issue/PR URLs.",
    )
    parser.add_argument(
        "--check-index",
        action="store_true",
        help=(
            "Also regenerate twice, re-resolve available public evidence, "
            "and compare catalog/index.json."
        ),
    )
    parser.add_argument(
        "--index",
        type=Path,
        help="Index path (default: <catalog-root>/catalog/index.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        records = validate_catalog(
            arguments.catalog_root,
            allow_draft_provenance=arguments.allow_draft_provenance,
        )
        if arguments.check_index:
            index_path = arguments.index or (
                arguments.catalog_root / "catalog" / "index.json"
            )
            check_catalog_index(arguments.catalog_root, index_path)
        print(f"validated {len(records)} Luke catalog skill(s)")
        return 0
    except CatalogValidationError as error:
        for diagnostic in error.diagnostics:
            print(diagnostic.render(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
