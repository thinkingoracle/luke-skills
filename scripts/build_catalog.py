#!/usr/bin/env python3
"""Build or verify catalog/luke-skills/catalog/index.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from catalog_tooling import (
    CatalogValidationError,
    Diagnostic,
    check_catalog_index,
    generate_catalog_index,
    render_catalog_index,
)


DEFAULT_CATALOG_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic commit-pinned Luke catalog metadata."
    )
    parser.add_argument("--catalog-root", type=Path, default=DEFAULT_CATALOG_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        help="Index path (default: <catalog-root>/catalog/index.json)",
    )
    parser.add_argument(
        "--source-repository",
        default="thinkingoracle/luke-skills",
        help="Raw-content repository in owner/repository form.",
    )
    parser.add_argument(
        "--source-commit",
        help="Full lowercase 40-character Git commit used in artifact URLs.",
    )
    parser.add_argument(
        "--baseline-index",
        type=Path,
        help="Optional prior index used to reject same-version content drift.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate twice and compare with the checked-in output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    output = arguments.output or arguments.catalog_root / "catalog" / "index.json"
    try:
        if arguments.check:
            check_catalog_index(arguments.catalog_root, output)
            print(f"catalog index verified: {output}")
            return 0
        if not arguments.source_commit:
            raise CatalogValidationError(
                [
                    Diagnostic(
                        "CATALOG_SOURCE_COMMIT_REQUIRED",
                        output.as_posix(),
                        "--source-commit is required when writing an index",
                    )
                ]
            )
        generated = generate_catalog_index(
            arguments.catalog_root,
            source_repository=arguments.source_repository,
            source_commit=arguments.source_commit,
            baseline_index_path=arguments.baseline_index,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(render_catalog_index(generated))
        print(f"wrote deterministic catalog index: {output}")
        return 0
    except CatalogValidationError as error:
        for diagnostic in error.diagnostics:
            print(diagnostic.render(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
