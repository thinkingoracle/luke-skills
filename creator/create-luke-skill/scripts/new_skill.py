#!/usr/bin/env python3
"""Create a deterministic draft bundle for one read-only Luke catalog skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


MINIMUM_PYTHON = (3, 11)
UNSUPPORTED_PYTHON_DIAGNOSTIC = "CREATOR_UNSUPPORTED_PYTHON"
LOCK_NAMESPACE = Path(tempfile.gettempdir()) / "luke-skill-creator-locks-v1"


def _require_supported_runtime() -> None:
    detected = sys.version_info[:2]
    if detected >= MINIMUM_PYTHON:
        return
    print(
        (
            f"{UNSUPPORTED_PYTHON_DIAGNOSTIC}: the Luke skill creator requires "
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or later; "
            f"detected Python {detected[0]}.{detected[1]}. Install a supported "
            "Python and run this command again."
        ),
        file=sys.stderr,
    )
    raise SystemExit(2)


_require_supported_runtime()


CATALOG_ROOT = Path(__file__).resolve().parents[3]
CATALOG_SCRIPTS = CATALOG_ROOT / "scripts"
if str(CATALOG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CATALOG_SCRIPTS))

from catalog_tooling import (  # noqa: E402
    ALLOWED_CAPABILITY_TARGETS,
    CatalogValidationError,
    SEMVER_PATTERN,
    SLUG_PATTERN,
    validate_catalog,
    validate_public_host,
)


CONTRIBUTOR_CAPABILITIES = tuple(
    sorted(
        ALLOWED_CAPABILITY_TARGETS
        - {"connector.execute", "local_sidecar.execute"}
    )
)


class CreatorError(RuntimeError):
    """A stable, contributor-facing creator failure."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def render(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True)
class OutputRootLock:
    directory: Path
    owner_marker: Path
    owner_token: str


def _one_line(value: str, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _intent_keywords(slug: str) -> list[str]:
    return list(dict.fromkeys(part for part in slug.split("-") if len(part) > 2)) or [
        slug
    ]


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_skill(arguments: argparse.Namespace) -> str:
    keywords = ", ".join(_yaml_string(keyword) for keyword in _intent_keywords(arguments.slug))
    return f"""---
name: {arguments.slug}
skill_id: browser-skill:{arguments.slug}
description: {_yaml_string(arguments.description)}
when_to_use:
  - host: {arguments.host}
    path_prefix: /
    intent_keywords: [{keywords}]
    require_auth: false
    mutation_boundary: read_only
steps:
  - caption: "Read the requested public information"
    capability_target: {arguments.capability_target}
    mutation_boundary: read_only
adapter_preferences:
  preferred: browserbase
  fallback: owned_browser
  declined: []
schema_version: 1
---

# {arguments.slug}

## Purpose

{arguments.description}

## Reads

{arguments.data_read}.

## Never

Never authenticate, mutate external state, run installers, or collect credentials.

## Lands in

{arguments.result_lands_in}.

## Steps

1. Open or search the public information on `{arguments.host}`.
2. Read only the information needed for the request.
3. Return a concise answer with the public source identified.

## Success criteria

- The answer addresses the requested public-information task.
- The answer identifies `{arguments.host}` as its source.
- No external state changes.

## Failure behavior

Explain when the public source is unavailable, ambiguous, or outside the
read-only boundary. Do not request credentials as a workaround.

## Redaction

Omit credentials, tokens, personal data, private page content, and unexpected
account state. Report that the source crossed the declared public-data boundary.
"""


def _render_evaluation(arguments: argparse.Namespace) -> str:
    evaluation = {
        "artifact_path": f"skills/{arguments.slug}/SKILL.md",
        "schema_version": 1,
        "skill_id": f"browser-skill:{arguments.slug}",
        "version": arguments.version,
        "min_luke_version": arguments.min_luke_version,
        "catalog_role": "community",
        "luke_2_0_import": "eligible_new_id",
        "trust_tier": "curated",
        "proposal_url": None,
        "review_decision": None,
        "validation_checks": [],
        "deprecated": False,
        "replaced_by": None,
        "revoked_hashes": [],
        "cases": [
            {
                "id": f"{arguments.slug}-positive-routing",
                "category": "positive_routing",
                "input": arguments.positive_example,
                "expected": f"Select browser-skill:{arguments.slug}.",
            },
            {
                "id": f"{arguments.slug}-negative-routing",
                "category": "negative_routing",
                "input": arguments.negative_example,
                "expected": (
                    f"Do not select browser-skill:{arguments.slug}; the request is "
                    "outside its read-only public-information boundary."
                ),
            },
            {
                "id": f"{arguments.slug}-failure",
                "category": "failure",
                "input": arguments.failure_example,
                "expected": (
                    "Explain the source failure without requesting credentials or "
                    "mutating external state."
                ),
            },
            {
                "id": f"{arguments.slug}-redaction",
                "category": "redaction",
                "input": arguments.redaction_example,
                "expected": (
                    "Omit the sensitive value and report that the public-data "
                    "boundary was crossed."
                ),
            },
        ],
    }
    return json.dumps(evaluation, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create SKILL.md and its required Luke catalog evaluation fixture."
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--data-read", required=True)
    parser.add_argument("--result-lands-in", required=True)
    parser.add_argument("--positive-example", required=True)
    parser.add_argument("--negative-example", required=True)
    parser.add_argument("--failure-example", required=True)
    parser.add_argument("--redaction-example", required=True)
    parser.add_argument(
        "--capability-target",
        choices=CONTRIBUTOR_CAPABILITIES,
        default="web_search",
    )
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--min-luke-version", default="2.0.0")
    parser.add_argument(
        "--auth-assumption",
        choices=("none",),
        default="none",
        help="Catalog v1 accepts public, unauthenticated tasks only.",
    )
    parser.add_argument(
        "--mutation-boundary",
        choices=("read_only",),
        default="read_only",
        help="Catalog v1 accepts read-only tasks only.",
    )
    return parser


def _output_lock_path(output_root: Path) -> Path:
    canonical_output_root = output_root.expanduser().resolve(strict=False)
    lock_name = hashlib.sha256(
        os.fsencode(str(canonical_output_root))
    ).hexdigest()
    return LOCK_NAMESPACE / lock_name


def _acquire_output_lock(output_root: Path) -> OutputRootLock:
    try:
        LOCK_NAMESPACE.mkdir(mode=0o700)
    except FileExistsError:
        if LOCK_NAMESPACE.is_symlink() or not LOCK_NAMESPACE.is_dir():
            raise CreatorError(
                "CREATOR_LOCK_FAILED",
                f"creator lock namespace is not a directory: {LOCK_NAMESPACE}",
            )
    except OSError as error:
        raise CreatorError(
            "CREATOR_LOCK_FAILED",
            f"could not prepare creator lock namespace: {error}",
        ) from error

    lock_directory = _output_lock_path(output_root)
    try:
        lock_directory.mkdir(mode=0o700)
    except FileExistsError as error:
        raise CreatorError(
            "CREATOR_OUTPUT_BUSY",
            (
                f"another creator is using output root {output_root}. Wait for "
                "that run to finish and retry. If a previous creator crashed, "
                "confirm that no creator is running, then remove the stale lock "
                f"directory {lock_directory} and retry."
            ),
        ) from error
    except OSError as error:
        raise CreatorError(
            "CREATOR_LOCK_FAILED",
            f"could not acquire the creator lock for {output_root}: {error}",
        ) from error

    owner_token = secrets.token_hex(32)
    owner_marker = lock_directory / "owner"
    try:
        with owner_marker.open(
            "x",
            encoding="utf-8",
            newline="\n",
        ) as marker_file:
            marker_file.write(owner_token + "\n")
    except OSError as error:
        cleanup_failures: list[str] = []
        try:
            owner_marker.unlink(missing_ok=True)
            lock_directory.rmdir()
        except OSError as cleanup_error:
            cleanup_failures.append(str(cleanup_error))
        detail = f"could not initialize the creator lock: {error}"
        if cleanup_failures:
            detail += "; lock cleanup also failed: " + " | ".join(cleanup_failures)
        raise CreatorError("CREATOR_LOCK_FAILED", detail) from error
    return OutputRootLock(lock_directory, owner_marker, owner_token)


def _release_output_lock(output_lock: OutputRootLock) -> CreatorError | None:
    try:
        recorded_owner = output_lock.owner_marker.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeDecodeError) as error:
        return CreatorError(
            "CREATOR_LOCK_RELEASE_FAILED",
            (
                "creator lock ownership could not be verified; the lock was "
                f"left in place at {output_lock.directory}: {error}"
            ),
        )
    if recorded_owner != output_lock.owner_token + "\n":
        return CreatorError(
            "CREATOR_LOCK_RELEASE_FAILED",
            (
                "creator lock ownership changed; another process's lock was "
                f"left untouched at {output_lock.directory}"
            ),
        )
    try:
        output_lock.owner_marker.unlink()
        output_lock.directory.rmdir()
    except OSError as error:
        return CreatorError(
            "CREATOR_LOCK_RELEASE_FAILED",
            (
                f"creator lock could not be removed from {output_lock.directory}: "
                f"{error}"
            ),
        )
    return None


def _ensure_parent(
    artifact_path: Path,
    created_directories: list[Path],
) -> None:
    missing_directories: list[Path] = []
    candidate = artifact_path.parent
    while not candidate.exists():
        missing_directories.append(candidate)
        if candidate == candidate.parent:
            break
        candidate = candidate.parent
    for directory in reversed(missing_directories):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise
        else:
            created_directories.append(directory)


def _write_new_artifact(
    artifact_path: Path,
    content: str,
    created_artifacts: list[Path],
) -> None:
    try:
        with artifact_path.open(
            "x",
            encoding="utf-8",
            newline="\n",
        ) as artifact_file:
            created_artifacts.append(artifact_path)
            artifact_file.write(content)
    except FileExistsError as error:
        raise CreatorError(
            "CREATOR_ARTIFACT_EXISTS",
            f"refusing to overwrite existing proposal artifact {artifact_path}",
        ) from error
    except OSError as error:
        raise CreatorError(
            "CREATOR_WRITE_FAILED",
            f"could not write proposal artifact {artifact_path}: {error}",
        ) from error


def _cleanup_created_output(
    created_artifacts: list[Path],
    created_directories: list[Path],
) -> list[str]:
    cleanup_failures: list[str] = []
    for artifact_path in reversed(created_artifacts):
        try:
            artifact_path.unlink(missing_ok=True)
        except OSError as error:
            cleanup_failures.append(f"{artifact_path}: {error}")
    for directory in reversed(created_directories):
        try:
            directory.rmdir()
        except FileNotFoundError:
            continue
        except OSError as error:
            cleanup_failures.append(f"{directory}: {error}")
    return cleanup_failures


def _report_failure(
    failure: CreatorError,
    created_artifacts: list[Path],
    created_directories: list[Path],
) -> int:
    print(failure.render(), file=sys.stderr)
    cleanup_failures = _cleanup_created_output(
        created_artifacts,
        created_directories,
    )
    if cleanup_failures:
        print(
            (
                "CREATOR_ROLLBACK_FAILED: the proposal bundle is incomplete and "
                "some creator-owned output could not be removed: "
                + " | ".join(cleanup_failures)
            ),
            file=sys.stderr,
        )
    return 1


def _create_bundle(arguments: argparse.Namespace) -> int:
    created_artifacts: list[Path] = []
    created_directories: list[Path] = []
    skill_path = arguments.output_root / "skills" / arguments.slug / "SKILL.md"
    evaluation_path = arguments.output_root / "evals" / f"{arguments.slug}.json"
    if skill_path.exists() or evaluation_path.exists():
        return _report_failure(
            CreatorError(
                "CREATOR_ARTIFACT_EXISTS",
                "refusing to overwrite an existing proposal artifact",
            ),
            created_artifacts,
            created_directories,
        )

    try:
        _ensure_parent(skill_path, created_directories)
        _ensure_parent(evaluation_path, created_directories)
        _write_new_artifact(
            skill_path,
            _render_skill(arguments),
            created_artifacts,
        )
        _write_new_artifact(
            evaluation_path,
            _render_evaluation(arguments),
            created_artifacts,
        )
    except CreatorError as error:
        return _report_failure(
            error,
            created_artifacts,
            created_directories,
        )
    except OSError as error:
        return _report_failure(
            CreatorError(
                "CREATOR_WRITE_FAILED",
                f"could not prepare the proposal output directories: {error}",
            ),
            created_artifacts,
            created_directories,
        )

    try:
        validate_catalog(arguments.output_root, allow_draft_provenance=True)
    except CatalogValidationError as error:
        diagnostic_summary = " | ".join(
            diagnostic.render() for diagnostic in error.diagnostics
        )
        return _report_failure(
            CreatorError(
                "CREATOR_VALIDATION_FAILED",
                f"generated proposal bundle did not pass validation: {diagnostic_summary}",
            ),
            created_artifacts,
            created_directories,
        )
    except OSError as error:
        return _report_failure(
            CreatorError(
                "CREATOR_VALIDATION_FAILED",
                f"generated proposal bundle could not be validated: {error}",
            ),
            created_artifacts,
            created_directories,
        )

    print(skill_path)
    print(evaluation_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        arguments.slug = _one_line(arguments.slug, "slug")
        arguments.description = _one_line(arguments.description, "description")
        arguments.host = _one_line(arguments.host, "host").lower().rstrip(".")
        arguments.data_read = _one_line(arguments.data_read, "data-read").rstrip(".")
        arguments.result_lands_in = _one_line(
            arguments.result_lands_in, "result-lands-in"
        ).rstrip(".")
        for field_name in (
            "positive_example",
            "negative_example",
            "failure_example",
            "redaction_example",
        ):
            setattr(
                arguments,
                field_name,
                _one_line(getattr(arguments, field_name), field_name.replace("_", "-")),
            )
        if not SLUG_PATTERN.fullmatch(arguments.slug):
            raise ValueError("slug must be lowercase kebab case")
        if not validate_public_host(arguments.host):
            raise ValueError("host must be a public DNS host")
        if not SEMVER_PATTERN.fullmatch(arguments.version):
            raise ValueError("version must be canonical X.Y.Z SemVer")
        if not SEMVER_PATTERN.fullmatch(arguments.min_luke_version):
            raise ValueError("min-luke-version must be canonical X.Y.Z SemVer")
    except ValueError as error:
        return _report_failure(
            CreatorError("CREATOR_INPUT_INVALID", str(error)),
            [],
            [],
        )

    try:
        output_lock = _acquire_output_lock(arguments.output_root)
    except CreatorError as error:
        print(error.render(), file=sys.stderr)
        return 1

    try:
        creation_result = _create_bundle(arguments)
    finally:
        release_failure = _release_output_lock(output_lock)
    if release_failure is not None:
        print(release_failure.render(), file=sys.stderr)
        return 1
    return creation_result


if __name__ == "__main__":
    raise SystemExit(main())
