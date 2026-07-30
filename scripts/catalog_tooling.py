#!/usr/bin/env python3
"""Deterministic validation and index generation for the Luke skills catalog."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

# Source-byte admission is a hard dependency, not an optional enhancement. If
# the profile module is missing this import fails and no catalog tooling runs,
# which is the intended fail-closed behavior: unscanned proposal bytes must
# never reach validation.
import unicode_security


SOURCE_SECURITY_PROFILE = unicode_security.PROFILE_LUKE_SKILL_UNICODE_V1


SKILL_ID_PATTERN = re.compile(r"^browser-skill:([a-z0-9]+(?:-[a-z0-9]+)*)$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
# Legacy pre-authority catalogs only. Current records are bound to a public
# `review_record_url` instead, so this shape is deliberately not pinned to a
# maintainer repository: naming one here would publish it to every contributor
# who reads this file from the public distribution repository.
REVIEW_URL_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*$"
)
PROPOSAL_URL_PATTERN = re.compile(
    r"^https://github\.com/thinkingoracle/luke-skills/issues/[1-9][0-9]*$"
)
SOURCE_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REQUIRED_EVALUATION_CATEGORIES = frozenset(
    {"positive_routing", "negative_routing", "failure", "redaction"}
)
ALLOWED_CATALOG_ROLES = frozenset({"bundled_mirror", "new_id_pilot", "community"})
REQUIRED_VALIDATION_CHECKS = (
    "catalog_schema_v1",
    "read_only_public_boundary",
    "routing_failure_redaction_cases",
    "source_security_profile_luke_skill_unicode_v1",
)
REVIEW_RECORD_FIELDS = frozenset(
    {
        "artifact_path",
        "content_sha256",
        "proposal_url",
        "review_decision",
        "review_record_schema_version",
        "skill_id",
        "validation_checks",
        "version",
    }
)
REVIEW_DECISION = "accepted_candidate"
BUNDLED_MIRROR_IDS = frozenset(
    {
        "browser-skill:example-docs-read",
        "browser-skill:github-public-pr-read",
        "browser-skill:public-status-page-read",
        "browser-skill:remote-gmail-inbox-read",
        "browser-skill:remote-workspace-read",
    }
)
ALLOWED_CAPABILITY_TARGETS = frozenset(
    {
        "connector.execute",
        "delegate_web_action",
        "fetch_url",
        "local_sidecar.execute",
        "web_search",
    }
)
MAX_SKILL_BYTES = 512 * 1024

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?im)^\s*(?:api[_-]?key|access[_-]?token|secret|password)\s*:\s*"
        r"(?!<|\[|\$\{|\{\{)(?=\S).{8,}$"
    ),
)
URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+")


@dataclass(frozen=True, order=True)
class Diagnostic:
    """One stable, sortable validator finding."""

    code: str
    path: str
    message: str

    def render(self) -> str:
        return f"{self.code} {self.path}: {self.message}"


class CatalogValidationError(Exception):
    """Raised when catalog validation produces one or more diagnostics."""

    def __init__(self, diagnostics: Iterable[Diagnostic]):
        self.diagnostics = tuple(sorted(set(diagnostics)))
        super().__init__("\n".join(diagnostic.render() for diagnostic in self.diagnostics))


class RestrictedYAMLError(ValueError):
    """The frontmatter used syntax outside Luke's deliberately small YAML subset."""


def _source_admission_diagnostics(
    findings: Iterable[unicode_security.UnicodeSecurityFinding],
) -> list[Diagnostic]:
    """Convert source-admission findings into catalog validator diagnostics."""

    return [
        Diagnostic(finding.code, finding.path, finding.message)
        for finding in findings
    ]


@dataclass(frozen=True)
class CatalogRecord:
    slug: str
    source_path: Path
    source_bytes: bytes
    frontmatter: dict[str, Any]
    body_markdown: str
    evaluation_path: Path
    evaluation: dict[str, Any]
    review_record_path: Path | None
    review_record: dict[str, Any] | None


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("["):
        if not stripped.endswith("]"):
            raise RestrictedYAMLError("unterminated inline list")
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item) for item in _split_inline_list(inner)]
    if stripped.startswith("{") or stripped.startswith("&") or stripped.startswith("*"):
        raise RestrictedYAMLError("maps, anchors, and aliases are not supported")
    if stripped.startswith(("|", ">")):
        raise RestrictedYAMLError("block scalars are not supported")
    if stripped.startswith('"'):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise RestrictedYAMLError(f"invalid double-quoted scalar: {error.msg}") from error
        if not isinstance(parsed, str):
            raise RestrictedYAMLError("quoted frontmatter values must be strings")
        return parsed
    if stripped.startswith("'"):
        if not stripped.endswith("'") or len(stripped) < 2:
            raise RestrictedYAMLError("unterminated single-quoted scalar")
        return stripped[1:-1].replace("''", "'")
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", stripped):
        return int(stripped)
    return stripped


def _split_inline_list(value: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for character in value:
        if quote:
            current.append(character)
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            current.append(character)
        elif character == ",":
            items.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if quote:
        raise RestrictedYAMLError("unterminated quoted inline-list value")
    items.append("".join(current).strip())
    if any(not item for item in items):
        raise RestrictedYAMLError("inline lists cannot contain empty values")
    return items


def _split_mapping_line(content: str) -> tuple[str, str]:
    if ":" not in content:
        raise RestrictedYAMLError(f"expected key: value, got {content!r}")
    key, value = content.split(":", 1)
    key = key.strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise RestrictedYAMLError(f"invalid mapping key {key!r}")
    return key, value.strip()


def parse_restricted_yaml(frontmatter: str) -> dict[str, Any]:
    """Parse the mapping/list subset used by Luke schema-v1 frontmatter."""

    tokens: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(frontmatter.splitlines(), start=1):
        if "\t" in raw_line:
            raise RestrictedYAMLError(f"line {line_number}: tabs are not allowed")
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indentation = len(raw_line) - len(raw_line.lstrip(" "))
        if indentation % 2:
            raise RestrictedYAMLError(
                f"line {line_number}: indentation must use multiples of two spaces"
            )
        tokens.append((indentation, raw_line[indentation:]))
    if not tokens:
        raise RestrictedYAMLError("frontmatter is empty")

    def parse_node(index: int, indentation: int) -> tuple[Any, int]:
        if index >= len(tokens) or tokens[index][0] != indentation:
            raise RestrictedYAMLError("invalid nested indentation")
        if tokens[index][1].startswith("- "):
            result: list[Any] = []
            while index < len(tokens) and tokens[index][0] == indentation:
                content = tokens[index][1]
                if not content.startswith("- "):
                    raise RestrictedYAMLError("cannot mix list and mapping entries")
                remainder = content[2:].strip()
                if not remainder:
                    index += 1
                    if index >= len(tokens) or tokens[index][0] <= indentation:
                        raise RestrictedYAMLError("empty list item")
                    item, index = parse_node(index, indentation + 2)
                    result.append(item)
                    continue
                if ":" not in remainder:
                    result.append(_parse_scalar(remainder))
                    index += 1
                    continue
                key, raw_value = _split_mapping_line(remainder)
                item_mapping: dict[str, Any] = {}
                index += 1
                if raw_value:
                    item_mapping[key] = _parse_scalar(raw_value)
                else:
                    if index >= len(tokens) or tokens[index][0] <= indentation:
                        raise RestrictedYAMLError(f"missing nested value for {key}")
                    nested, index = parse_node(index, indentation + 4)
                    item_mapping[key] = nested
                while index < len(tokens) and tokens[index][0] == indentation + 2:
                    nested_content = tokens[index][1]
                    if nested_content.startswith("- "):
                        raise RestrictedYAMLError("unexpected nested list item")
                    nested_key, nested_raw_value = _split_mapping_line(nested_content)
                    if nested_key in item_mapping:
                        raise RestrictedYAMLError(f"duplicate key {nested_key}")
                    index += 1
                    if nested_raw_value:
                        item_mapping[nested_key] = _parse_scalar(nested_raw_value)
                    else:
                        if index >= len(tokens) or tokens[index][0] <= indentation + 2:
                            raise RestrictedYAMLError(
                                f"missing nested value for {nested_key}"
                            )
                        nested, index = parse_node(index, indentation + 4)
                        item_mapping[nested_key] = nested
                result.append(item_mapping)
            return result, index

        result_mapping: dict[str, Any] = {}
        while index < len(tokens) and tokens[index][0] == indentation:
            content = tokens[index][1]
            if content.startswith("- "):
                raise RestrictedYAMLError("cannot mix mapping and list entries")
            key, raw_value = _split_mapping_line(content)
            if key in result_mapping:
                raise RestrictedYAMLError(f"duplicate key {key}")
            index += 1
            if raw_value:
                result_mapping[key] = _parse_scalar(raw_value)
            else:
                if index >= len(tokens) or tokens[index][0] <= indentation:
                    raise RestrictedYAMLError(f"missing nested value for {key}")
                nested, index = parse_node(index, indentation + 2)
                result_mapping[key] = nested
        return result_mapping, index

    if tokens[0][0] != 0:
        raise RestrictedYAMLError("frontmatter must begin at indentation zero")
    parsed, final_index = parse_node(0, 0)
    if final_index != len(tokens) or not isinstance(parsed, dict):
        raise RestrictedYAMLError("frontmatter root must be one mapping")
    return parsed


def split_skill_markdown(markdown: str) -> tuple[dict[str, Any], str]:
    normalized = markdown.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise RestrictedYAMLError("SKILL.md must begin with a YAML frontmatter fence")
    closing_index = normalized.find("\n---\n", 4)
    if closing_index < 0:
        raise RestrictedYAMLError("SKILL.md frontmatter is missing its closing fence")
    frontmatter = normalized[4:closing_index]
    body = normalized[closing_index + 5 :]
    return parse_restricted_yaml(frontmatter), body


def split_review_record_markdown(markdown: str) -> tuple[dict[str, Any], str]:
    """Split the strict machine front matter from public explanatory prose."""

    normalized = markdown.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise RestrictedYAMLError(
            "review record must begin with a YAML frontmatter fence"
        )
    closing_index = normalized.find("\n---\n", 4)
    if closing_index < 0:
        raise RestrictedYAMLError(
            "review record frontmatter is missing its closing fence"
        )
    frontmatter = normalized[4:closing_index]
    body = normalized[closing_index + 5 :]
    return parse_restricted_yaml(frontmatter), body


def _relative_path(path: Path, catalog_root: Path) -> str:
    try:
        return path.relative_to(catalog_root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_executable(path: Path) -> bool:
    return bool(path.lstat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def _is_public_host(host: str) -> bool:
    candidate = host.strip().lower().rstrip(".")
    if not candidate or candidate in {"localhost", "localhost.localdomain"}:
        return False
    if candidate.endswith((".local", ".internal", ".localhost", ".lan", ".home")):
        return False
    if "." not in candidate:
        return False
    try:
        address = ipaddress.ip_address(candidate.strip("[]"))
    except ValueError:
        return bool(
            re.fullmatch(
                r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?",
                candidate,
            )
        )
    return bool(address.is_global)


def validate_public_host(host: str) -> bool:
    """Public helper used by the creator CLI."""

    return _is_public_host(host)


def _validate_urls_and_secrets(
    text: str, relative_path: str, diagnostics: list[Diagnostic]
) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SECRET_DETECTED",
                    relative_path,
                    "high-confidence secret material is forbidden",
                )
            )
            break
    for url_text in URL_PATTERN.findall(text):
        parsed = urlparse(url_text.rstrip(".,;:)"))
        if parsed.username or parsed.password:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_CREDENTIAL_URL",
                    relative_path,
                    "credential-bearing URLs are forbidden",
                )
            )
        if parsed.hostname and not _is_public_host(parsed.hostname):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_PRIVATE_HOST",
                    relative_path,
                    f"URL host {parsed.hostname!r} is not public",
                )
            )


def _validate_skill_structure(
    catalog_root: Path, diagnostics: list[Diagnostic]
) -> list[tuple[str, Path]]:
    skills_root = catalog_root / "skills"
    if skills_root.is_symlink():
        diagnostics.append(
            Diagnostic("CATALOG_SYMLINK_FORBIDDEN", "skills", "symlinks are forbidden")
        )
        return []
    if not skills_root.is_dir():
        diagnostics.append(
            Diagnostic("CATALOG_SKILLS_MISSING", "skills", "skills directory is required")
        )
        return []
    discovered: list[tuple[str, Path]] = []
    for child in sorted(skills_root.iterdir(), key=lambda path: path.name):
        relative = _relative_path(child, catalog_root)
        if child.name.startswith("."):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_HIDDEN_PAYLOAD",
                    relative,
                    "hidden files and directories are forbidden",
                )
            )
            continue
        if child.is_symlink():
            diagnostics.append(
                Diagnostic("CATALOG_SYMLINK_FORBIDDEN", relative, "symlinks are forbidden")
            )
            continue
        if not child.is_dir():
            diagnostics.append(
                Diagnostic(
                    "CATALOG_PAYLOAD_SHAPE",
                    relative,
                    "skills must be directories containing only SKILL.md",
                )
            )
            continue
        if not SLUG_PATTERN.fullmatch(child.name):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_PATH_INVALID",
                    relative,
                    "skill directory must be a lowercase kebab-case slug",
                )
            )
        entries = sorted(child.iterdir(), key=lambda path: path.name)
        for entry in entries:
            entry_relative = _relative_path(entry, catalog_root)
            if entry.name.startswith("."):
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_HIDDEN_PAYLOAD",
                        entry_relative,
                        "hidden payloads are forbidden",
                    )
                )
            if entry.is_symlink():
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_SYMLINK_FORBIDDEN",
                        entry_relative,
                        "symlinks are forbidden",
                    )
                )
            elif entry.name != "SKILL.md" or not entry.is_file():
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_PAYLOAD_SHAPE",
                        entry_relative,
                        "the install payload may contain only one SKILL.md file",
                    )
                )
            elif _is_executable(entry):
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_EXECUTABLE_FORBIDDEN",
                        entry_relative,
                        "SKILL.md must not have executable mode bits",
                    )
                )
        skill_path = child / "SKILL.md"
        if skill_path.is_file() and not skill_path.is_symlink():
            discovered.append((child.name, skill_path))
        else:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_FILE_MISSING",
                    f"skills/{child.name}/SKILL.md",
                    "SKILL.md is required",
                )
            )
    if not discovered:
        diagnostics.append(
            Diagnostic("CATALOG_NO_SKILLS", "skills", "at least one skill is required")
        )
    return discovered


def _load_evaluations(
    catalog_root: Path, diagnostics: list[Diagnostic]
) -> dict[str, tuple[Path, dict[str, Any]]]:
    evaluations_root = catalog_root / "evals"
    if evaluations_root.is_symlink():
        diagnostics.append(
            Diagnostic("CATALOG_SYMLINK_FORBIDDEN", "evals", "symlinks are forbidden")
        )
        return {}
    if not evaluations_root.is_dir():
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVALS_MISSING", "evals", "evaluations directory is required"
            )
        )
        return {}
    evaluations: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(evaluations_root.iterdir(), key=lambda item: item.name):
        relative = _relative_path(path, catalog_root)
        if path.name.startswith("."):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_HIDDEN_PAYLOAD",
                    relative,
                    "hidden files and directories are forbidden",
                )
            )
            continue
        if path.is_symlink():
            diagnostics.append(
                Diagnostic("CATALOG_SYMLINK_FORBIDDEN", relative, "symlinks are forbidden")
            )
            continue
        if not path.is_file() or path.suffix != ".json":
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_PAYLOAD_INVALID",
                    relative,
                    "evals may contain only <slug>.json files",
                )
            )
            continue
        if _is_executable(path):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EXECUTABLE_FORBIDDEN",
                    relative,
                    "evaluation fixtures must not be executable",
                )
            )
        try:
            # Decode the exact bytes rather than using read_text, whose
            # universal-newline handling rewrites a carriage return to a line
            # feed before any check sees it. That translation would admit a
            # control character the profile refuses, and would mean the text
            # being validated is not the text that was submitted.
            raw_text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_UTF8_REQUIRED",
                    relative,
                    "evaluation fixtures must be valid UTF-8",
                )
            )
            continue
        admission_findings = unicode_security.scan_evaluation_json(
            raw_text,
            path=relative,
            profile=SOURCE_SECURITY_PROFILE,
        )
        if admission_findings:
            diagnostics.extend(_source_admission_diagnostics(admission_findings))
            continue
        _validate_urls_and_secrets(raw_text, relative, diagnostics)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as error:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative,
                    f"invalid JSON at line {error.lineno}, column {error.colno}",
                )
            )
            continue
        if not isinstance(parsed, dict):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative,
                    "evaluation root must be an object",
                )
            )
            continue
        evaluations[path.stem] = (path, parsed)
    return evaluations


def _validate_evaluation(
    evaluation: dict[str, Any],
    slug: str,
    relative_path: str,
    allow_draft_provenance: bool,
    require_public_authority: bool,
    diagnostics: list[Diagnostic],
) -> None:
    required_fields = {
        "schema_version",
        "skill_id",
        "version",
        "min_luke_version",
        "catalog_role",
        "luke_2_0_import",
        "trust_tier",
        "proposal_url",
        "deprecated",
        "replaced_by",
        "revoked_hashes",
        "cases",
    }
    required_fields.update(
        {"artifact_path", "review_decision", "validation_checks"}
        if require_public_authority
        else {"review_url"}
    )
    missing = sorted(required_fields - evaluation.keys())
    if missing:
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                f"missing required fields: {', '.join(missing)}",
            )
        )
    if evaluation.get("schema_version") != 1:
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                "schema_version must be integer 1",
            )
        )
    expected_id = f"browser-skill:{slug}"
    if evaluation.get("skill_id") != expected_id:
        diagnostics.append(
            Diagnostic(
                "CATALOG_ID_MISMATCH",
                relative_path,
                f"evaluation skill_id must equal {expected_id}",
            )
        )
    for field_name in ("version", "min_luke_version"):
        value = evaluation.get(field_name)
        if not isinstance(value, str) or not SEMVER_PATTERN.fullmatch(value):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_VERSION_INVALID",
                    relative_path,
                    f"{field_name} must be canonical X.Y.Z SemVer",
                )
            )
    role = evaluation.get("catalog_role")
    if role not in ALLOWED_CATALOG_ROLES:
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                f"catalog_role must be one of {sorted(ALLOWED_CATALOG_ROLES)}",
            )
        )
    expected_id_is_bundled = expected_id in BUNDLED_MIRROR_IDS
    role_claims_bundled = role == "bundled_mirror"
    if expected_id_is_bundled != role_claims_bundled:
        diagnostics.append(
            Diagnostic(
                "CATALOG_ROLE_INVALID",
                relative_path,
                (
                    "catalog_role=bundled_mirror is reserved for the five exact "
                    "Luke 2.0 baseline IDs"
                ),
            )
        )
    import_lane = evaluation.get("luke_2_0_import")
    expected_lane = (
        "not_eligible_bundled_id"
        if role == "bundled_mirror"
        else "eligible_new_id"
    )
    if import_lane != expected_lane:
        diagnostics.append(
            Diagnostic(
                "CATALOG_IMPORT_LANE_INVALID",
                relative_path,
                f"{role!r} must declare luke_2_0_import={expected_lane!r}",
            )
        )
    if evaluation.get("trust_tier") != "curated":
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                "trust_tier must be 'curated'",
            )
        )
    proposal_url = evaluation.get("proposal_url")
    if proposal_url is not None and (
        not isinstance(proposal_url, str)
        or not PROPOSAL_URL_PATTERN.fullmatch(proposal_url)
    ):
        diagnostics.append(
            Diagnostic(
                "CATALOG_PROVENANCE_INVALID",
                relative_path,
                "proposal_url must name an issue in thinkingoracle/luke-skills",
            )
        )
    if require_public_authority:
        expected_artifact_path = f"skills/{slug}/SKILL.md"
        if evaluation.get("artifact_path") != expected_artifact_path:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_AUTHORITY_MISMATCH",
                    relative_path,
                    f"artifact_path must equal {expected_artifact_path}",
                )
            )
        if "review_url" in evaluation:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_LEGACY_REVIEW_URL_FORBIDDEN",
                    relative_path,
                    "current catalog records require public review_record_url evidence",
                )
            )
        review_decision = evaluation.get("review_decision")
        validation_checks = evaluation.get("validation_checks")
        if allow_draft_provenance:
            valid_decision = review_decision in {None, REVIEW_DECISION}
            valid_checks = isinstance(validation_checks, list) and all(
                isinstance(check, str) for check in validation_checks
            )
        else:
            valid_decision = review_decision == REVIEW_DECISION
            valid_checks = validation_checks == list(REQUIRED_VALIDATION_CHECKS)
        if not valid_decision:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_AUTHORITY_INVALID",
                    relative_path,
                    f"review_decision must be {REVIEW_DECISION!r} (or null for a draft)",
                )
            )
        if not valid_checks:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_AUTHORITY_INVALID",
                    relative_path,
                    f"validation_checks must name {list(REQUIRED_VALIDATION_CHECKS)!r}",
                )
            )
    else:
        review_url = evaluation.get("review_url")
        if review_url is not None and (
            not isinstance(review_url, str)
            or not REVIEW_URL_PATTERN.fullmatch(review_url)
        ):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_PROVENANCE_INVALID",
                    relative_path,
                    "review_url must name the maintainer review pull request",
                )
            )
        if not allow_draft_provenance and review_url is None:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_PROVENANCE_MISSING",
                    relative_path,
                    "landed legacy catalog entries require review_url",
                )
            )
    if not allow_draft_provenance:
        if role not in {"bundled_mirror", "new_id_pilot"} and proposal_url is None:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_PROVENANCE_MISSING",
                    relative_path,
                    (
                        "community entries require proposal_url; only the staged "
                        "new-ID pilot may omit it before public intake launches"
                    ),
                )
            )
    if not isinstance(evaluation.get("deprecated"), bool):
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                "deprecated must be a boolean",
            )
        )
    replaced_by = evaluation.get("replaced_by")
    if replaced_by is not None and (
        not isinstance(replaced_by, str) or not SKILL_ID_PATTERN.fullmatch(replaced_by)
    ):
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                "replaced_by must be null or a valid browser-skill ID",
            )
        )
    revoked_hashes = evaluation.get("revoked_hashes")
    if (
        not isinstance(revoked_hashes, list)
        or any(
            not isinstance(item, str) or not SHA256_PATTERN.fullmatch(item)
            for item in revoked_hashes
        )
        or len(revoked_hashes) != len(set(revoked_hashes or []))
    ):
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                "revoked_hashes must contain unique lowercase SHA-256 values",
            )
        )
    cases = evaluation.get("cases")
    if not isinstance(cases, list):
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVAL_SCHEMA_INVALID",
                relative_path,
                "cases must be an array",
            )
        )
        return
    categories: set[str] = set()
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    "each evaluation case must be an object",
                )
            )
            continue
        case_id = case.get("id")
        category = case.get("category")
        if not isinstance(case_id, str) or not case_id:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    "each evaluation case requires a non-empty id",
                )
            )
        elif case_id in case_ids:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    f"duplicate evaluation case id {case_id!r}",
                )
            )
        else:
            case_ids.add(case_id)
        if category not in REQUIRED_EVALUATION_CATEGORIES:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    f"unsupported evaluation category {category!r}",
                )
            )
        else:
            categories.add(category)
        if not isinstance(case.get("input"), str) or not case.get("input", "").strip():
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    "each evaluation case requires non-empty input",
                )
            )
        if not isinstance(case.get("expected"), str) or not case.get(
            "expected", ""
        ).strip():
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    "each evaluation case requires non-empty expected",
                )
            )
    missing_categories = sorted(REQUIRED_EVALUATION_CATEGORIES - categories)
    if missing_categories:
        diagnostics.append(
            Diagnostic(
                "CATALOG_EVALUATIONS_INCOMPLETE",
                relative_path,
                f"missing evaluation categories: {', '.join(missing_categories)}",
            )
        )


def _load_review_record(
    catalog_root: Path,
    *,
    slug: str,
    content_sha256: str,
    evaluation: dict[str, Any],
    allow_draft_provenance: bool,
    diagnostics: list[Diagnostic],
) -> tuple[Path | None, dict[str, Any] | None]:
    version = evaluation.get("version")
    if not isinstance(version, str):
        return None, None
    path = (
        catalog_root
        / "review-records"
        / slug
        / version
        / f"{content_sha256}.md"
    )
    relative_path = _relative_path(path, catalog_root)
    if not path.is_file() or path.is_symlink():
        if not allow_draft_provenance:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_REVIEW_RECORD_MISSING",
                    relative_path,
                    "landed catalog entries require the canonical exact-hash review record",
                )
            )
        return None, None
    try:
        raw_text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        diagnostics.append(
            Diagnostic(
                "CATALOG_REVIEW_RECORD_INVALID",
                relative_path,
                f"review record must be readable UTF-8: {error}",
            )
        )
        return path, None
    admission_findings = unicode_security.scan_source_text(
        raw_text,
        path=relative_path,
        profile=SOURCE_SECURITY_PROFILE,
    )
    if admission_findings:
        diagnostics.extend(_source_admission_diagnostics(admission_findings))
        return path, None
    _validate_urls_and_secrets(raw_text, relative_path, diagnostics)
    try:
        record, body = split_review_record_markdown(raw_text)
    except RestrictedYAMLError as error:
        diagnostics.append(
            Diagnostic("CATALOG_REVIEW_RECORD_INVALID", relative_path, str(error))
        )
        return path, None

    unknown_fields = sorted(record.keys() - REVIEW_RECORD_FIELDS)
    missing_fields = sorted(REVIEW_RECORD_FIELDS - record.keys())
    if unknown_fields or missing_fields:
        details: list[str] = []
        if missing_fields:
            details.append(f"missing fields: {', '.join(missing_fields)}")
        if unknown_fields:
            details.append(f"unknown fields: {', '.join(unknown_fields)}")
        diagnostics.append(
            Diagnostic(
                "CATALOG_REVIEW_RECORD_INVALID",
                relative_path,
                "; ".join(details),
            )
        )

    expected = {
        "artifact_path": f"skills/{slug}/SKILL.md",
        "content_sha256": content_sha256,
        "proposal_url": evaluation.get("proposal_url"),
        "review_decision": evaluation.get("review_decision"),
        "review_record_schema_version": 1,
        "skill_id": f"browser-skill:{slug}",
        "validation_checks": evaluation.get("validation_checks"),
        "version": version,
    }
    for field_name, expected_value in expected.items():
        if record.get(field_name) != expected_value:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_AUTHORITY_MISMATCH",
                    relative_path,
                    (
                        f"{field_name} conflicts with exact source/evaluation "
                        f"authority; expected {expected_value!r}"
                    ),
                )
            )

    authority_label = re.compile(
        (
            r"(?im)^\s*(?:[-*]\s+|\|\s*)?"
            r"(?:artifact path|content sha-256|decision|proposal url|"
            r"public proposal|skill id|validation checks|version)\b"
        )
    )
    if authority_label.search(body):
        diagnostics.append(
            Diagnostic(
                "CATALOG_REVIEW_RECORD_BODY_CONFLICT",
                relative_path,
                (
                    "authority fields belong only in machine front matter; "
                    "the explanatory body must not restate them"
                ),
            )
        )
    return path, record


def _validate_frontmatter(
    frontmatter: dict[str, Any],
    body: str,
    slug: str,
    evaluation: dict[str, Any],
    relative_path: str,
    diagnostics: list[Diagnostic],
) -> None:
    expected_id = f"browser-skill:{slug}"
    if frontmatter.get("schema_version") != 1:
        diagnostics.append(
            Diagnostic(
                "CATALOG_SKILL_SCHEMA_INVALID",
                relative_path,
                "schema_version must be integer 1",
            )
        )
    if frontmatter.get("name") != slug:
        diagnostics.append(
            Diagnostic(
                "CATALOG_PATH_NAME_MISMATCH",
                relative_path,
                f"frontmatter name must equal directory slug {slug!r}",
            )
        )
    if frontmatter.get("skill_id") != expected_id:
        diagnostics.append(
            Diagnostic(
                "CATALOG_ID_MISMATCH",
                relative_path,
                f"frontmatter skill_id must equal {expected_id}",
            )
        )
    if not isinstance(frontmatter.get("description"), str) or not frontmatter.get(
        "description", ""
    ).strip():
        diagnostics.append(
            Diagnostic(
                "CATALOG_SKILL_SCHEMA_INVALID",
                relative_path,
                "description must be a non-empty string",
            )
        )
    rules = frontmatter.get("when_to_use")
    role = evaluation.get("catalog_role")
    if not isinstance(rules, list) or not rules:
        diagnostics.append(
            Diagnostic(
                "CATALOG_SKILL_SCHEMA_INVALID",
                relative_path,
                "when_to_use must be a non-empty array",
            )
        )
        rules = []
    for rule in rules:
        if not isinstance(rule, dict):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_SCHEMA_INVALID",
                    relative_path,
                    "each when_to_use rule must be an object",
                )
            )
            continue
        if rule.get("mutation_boundary") != "read_only":
            diagnostics.append(
                Diagnostic(
                    "CATALOG_MUTATION_FORBIDDEN",
                    relative_path,
                    "all when_to_use rules must use mutation_boundary=read_only",
                )
            )
        keywords = rule.get("intent_keywords")
        if (
            not isinstance(keywords, list)
            or not keywords
            or any(not isinstance(item, str) or not item.strip() for item in keywords)
        ):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_SCHEMA_INVALID",
                    relative_path,
                    "intent_keywords must be a non-empty string array",
                )
            )
        require_auth = rule.get("require_auth")
        if not isinstance(require_auth, bool):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_SCHEMA_INVALID",
                    relative_path,
                    "require_auth must be a boolean",
                )
            )
        host = rule.get("host")
        if host is not None:
            if not isinstance(host, str) or not _is_public_host(host):
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_PRIVATE_HOST",
                        relative_path,
                        f"when_to_use host {host!r} is not public",
                    )
                )
        if role != "bundled_mirror":
            if require_auth is not False:
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_AUTH_FORBIDDEN",
                        relative_path,
                        "new-ID V1 skills must not require authentication",
                    )
                )
            if not isinstance(host, str) or not host:
                diagnostics.append(
                    Diagnostic(
                        "CATALOG_PUBLIC_HOST_REQUIRED",
                        relative_path,
                        "new-ID V1 skills require an explicit public host",
                    )
                )
    steps = frontmatter.get("steps", [])
    if not isinstance(steps, list):
        diagnostics.append(
            Diagnostic(
                "CATALOG_SKILL_SCHEMA_INVALID",
                relative_path,
                "steps must be an array when present",
            )
        )
        steps = []
    sidecar_targets_present = "capability_targets" in evaluation
    sidecar_targets = evaluation.get("capability_targets")
    if sidecar_targets_present:
        if role != "bundled_mirror":
            diagnostics.append(
                Diagnostic(
                    "CATALOG_CAPABILITY_FORBIDDEN",
                    relative_path,
                    (
                        "evaluation capability_targets are reserved for byte-faithful "
                        "bundled mirrors"
                    ),
                )
            )
        if steps:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    (
                        "evaluation capability_targets are allowed only when a bundled "
                        "mirror manifest has no steps"
                    ),
                )
            )
        if (
            not isinstance(sidecar_targets, list)
            or not sidecar_targets
            or any(
                not isinstance(target, str) or not target
                for target in sidecar_targets
            )
            or len(sidecar_targets) != len(set(sidecar_targets or []))
        ):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_SCHEMA_INVALID",
                    relative_path,
                    (
                        "evaluation capability_targets must contain unique, non-empty "
                        "strings"
                    ),
                )
            )
        else:
            for target in sidecar_targets:
                if target not in ALLOWED_CAPABILITY_TARGETS:
                    diagnostics.append(
                        Diagnostic(
                            "CATALOG_CAPABILITY_FORBIDDEN",
                            relative_path,
                            (
                                f"capability_target {target!r} is outside the V1 "
                                "read-only allowlist"
                            ),
                        )
                    )
    if not steps and (
        role != "bundled_mirror"
        or not isinstance(sidecar_targets, list)
        or not sidecar_targets
    ):
        diagnostics.append(
            Diagnostic(
                "CATALOG_CAPABILITY_TARGETS_MISSING",
                relative_path,
                (
                    "at least one manifest step, or a bundled-mirror evaluation "
                    "sidecar, must declare a read-only capability_target"
                ),
            )
        )
    for step in steps:
        if not isinstance(step, dict):
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_SCHEMA_INVALID",
                    relative_path,
                    "each step must be an object",
                )
            )
            continue
        if step.get("mutation_boundary") != "read_only":
            diagnostics.append(
                Diagnostic(
                    "CATALOG_MUTATION_FORBIDDEN",
                    relative_path,
                    "all steps must use mutation_boundary=read_only",
                )
            )
        target = step.get("capability_target")
        if target not in ALLOWED_CAPABILITY_TARGETS:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_CAPABILITY_FORBIDDEN",
                    relative_path,
                    f"capability_target {target!r} is outside the V1 read-only allowlist",
                )
            )
        if target in {"connector.execute", "local_sidecar.execute"} and role != "bundled_mirror":
            diagnostics.append(
                Diagnostic(
                    "CATALOG_CAPABILITY_FORBIDDEN",
                    relative_path,
                    f"capability_target {target!r} is reserved for byte-faithful bundled mirrors",
                )
            )
    lowered_body = body.lower()
    if "## success criteria" not in lowered_body:
        diagnostics.append(
            Diagnostic(
                "CATALOG_GUIDANCE_MISSING",
                relative_path,
                "body must include a Success criteria section",
            )
        )
    if "## redaction" not in lowered_body:
        diagnostics.append(
            Diagnostic(
                "CATALOG_GUIDANCE_MISSING",
                relative_path,
                "body must include a Redaction section",
            )
        )


def validate_catalog(
    catalog_root: Path | str,
    *,
    allow_draft_provenance: bool = False,
    require_public_authority: bool | None = None,
) -> list[CatalogRecord]:
    """Validate source and evaluation inputs, returning canonical records."""

    root = Path(catalog_root).resolve()
    infer_public_authority = require_public_authority is None
    # Fail closed before any source is read. An unsupported profile never
    # degrades into a permissive scan.
    unicode_security.require_supported_profile(SOURCE_SECURITY_PROFILE)
    diagnostics: list[Diagnostic] = []
    skill_paths = _validate_skill_structure(root, diagnostics)
    evaluations = _load_evaluations(root, diagnostics)
    if infer_public_authority:
        require_public_authority = (root / "review-records").is_dir() or any(
            "artifact_path" in evaluation
            for _, evaluation in evaluations.values()
        )
    assert require_public_authority is not None
    records: list[CatalogRecord] = []
    known_slugs = {slug for slug, _ in skill_paths}
    for orphan_slug, (orphan_path, _) in evaluations.items():
        if orphan_slug not in known_slugs:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVAL_ORPHANED",
                    _relative_path(orphan_path, root),
                    "evaluation fixture has no matching skills/<slug>/SKILL.md",
                )
            )
    for slug, skill_path in skill_paths:
        relative_skill = _relative_path(skill_path, root)
        try:
            source_bytes = skill_path.read_bytes()
        except OSError as error:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_UNREADABLE", relative_skill, f"cannot read skill: {error}"
                )
            )
            continue
        if len(source_bytes) > MAX_SKILL_BYTES:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_TOO_LARGE",
                    relative_skill,
                    f"SKILL.md exceeds {MAX_SKILL_BYTES} bytes",
                )
            )
        try:
            source_text = source_bytes.decode("utf-8")
        except UnicodeDecodeError:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_UTF8_REQUIRED",
                    relative_skill,
                    "SKILL.md must be valid UTF-8",
                )
            )
            continue
        admission_findings = unicode_security.scan_source_text(
            source_text,
            path=relative_skill,
            profile=SOURCE_SECURITY_PROFILE,
        )
        if admission_findings:
            diagnostics.extend(_source_admission_diagnostics(admission_findings))
            continue
        _validate_urls_and_secrets(source_text, relative_skill, diagnostics)
        try:
            frontmatter, body = split_skill_markdown(source_text)
        except RestrictedYAMLError as error:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SKILL_YAML_INVALID", relative_skill, str(error)
                )
            )
            continue
        evaluation_pair = evaluations.get(slug)
        if evaluation_pair is None:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_EVALUATION_MISSING",
                    f"evals/{slug}.json",
                    "every skill requires a matching evaluation fixture",
                )
            )
            continue
        evaluation_path, evaluation = evaluation_pair
        relative_evaluation = _relative_path(evaluation_path, root)
        _validate_evaluation(
            evaluation,
            slug,
            relative_evaluation,
            allow_draft_provenance,
            require_public_authority,
            diagnostics,
        )
        _validate_frontmatter(
            frontmatter,
            body,
            slug,
            evaluation,
            relative_skill,
            diagnostics,
        )
        content_sha256 = hashlib.sha256(source_bytes).hexdigest()
        review_record_path: Path | None = None
        review_record: dict[str, Any] | None = None
        if require_public_authority:
            review_record_path, review_record = _load_review_record(
                root,
                slug=slug,
                content_sha256=content_sha256,
                evaluation=evaluation,
                allow_draft_provenance=allow_draft_provenance,
                diagnostics=diagnostics,
            )
        records.append(
            CatalogRecord(
                slug=slug,
                source_path=skill_path,
                source_bytes=source_bytes,
                frontmatter=frontmatter,
                body_markdown=body,
                evaluation_path=evaluation_path,
                evaluation=evaluation,
                review_record_path=review_record_path,
                review_record=review_record,
            )
        )
    if diagnostics:
        raise CatalogValidationError(diagnostics)
    return sorted(records, key=lambda record: record.frontmatter["skill_id"])


def _string_array(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def _frontmatter_enrichment(frontmatter: dict[str, Any]) -> tuple[list[str], ...]:
    metadata = frontmatter.get("metadata")
    luke_metadata: dict[str, Any] = {}
    if isinstance(metadata, dict) and isinstance(metadata.get("luke"), dict):
        luke_metadata = metadata["luke"]
    prerequisites = frontmatter.get("prerequisites")
    if not isinstance(prerequisites, dict):
        prerequisites = {}
    return (
        _string_array(luke_metadata.get("tags")),
        _string_array(luke_metadata.get("related_skills")),
        _string_array(prerequisites.get("commands")),
        _string_array(frontmatter.get("platforms")),
    )


def _record_entry(
    record: CatalogRecord,
    source_repository: str,
    source_commit: str,
    install_state: str,
) -> dict[str, Any]:
    rules = [rule for rule in record.frontmatter["when_to_use"] if isinstance(rule, dict)]
    steps = [
        step
        for step in record.frontmatter.get("steps", [])
        if isinstance(step, dict)
    ]
    hosts = sorted(
        {
            rule["host"]
            for rule in rules
            if isinstance(rule.get("host"), str) and rule["host"]
        }
    )
    boundaries = sorted(
        {
            boundary
            for boundary in (
                [rule.get("mutation_boundary") for rule in rules]
                + [step.get("mutation_boundary") for step in steps]
            )
            if isinstance(boundary, str)
        }
    )
    manifest_targets = sorted(
        {
            target
            for target in [step.get("capability_target") for step in steps]
            if isinstance(target, str)
        }
    )
    targets = manifest_targets or sorted(
        {
            target
            for target in record.evaluation.get("capability_targets", [])
            if isinstance(target, str)
        }
    )
    tags, related_skills, prerequisite_commands, platforms = _frontmatter_enrichment(
        record.frontmatter
    )
    evaluation = record.evaluation
    source_path = f"skills/{record.slug}/SKILL.md"
    if record.review_record_path is None or record.review_record is None:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_DRAFT_NOT_RELEASE_ELIGIBLE",
                    record.evaluation_path.as_posix(),
                    "draft validation cannot emit a catalog descriptor",
                )
            ]
        )
    content_sha256 = hashlib.sha256(record.source_bytes).hexdigest()
    review_record_path = (
        f"review-records/{record.slug}/{evaluation['version']}/"
        f"{content_sha256}.md"
    )
    return {
        "auth_required": any(rule.get("require_auth") is True for rule in rules),
        "capability_targets": targets,
        "catalog_role": evaluation["catalog_role"],
        "content_sha256": hashlib.sha256(record.source_bytes).hexdigest(),
        "deprecated": evaluation["deprecated"],
        "distribution_origin": "optional",
        "distribution_source_id": "thinkingoracle-curated",
        "hosts": hosts,
        "install_state": install_state,
        "luke_2_0_import": evaluation["luke_2_0_import"],
        "min_luke_version": evaluation["min_luke_version"],
        "mutation_boundaries": boundaries,
        "name": record.frontmatter["name"],
        "platforms": platforms,
        "prerequisite_commands": prerequisite_commands,
        "proposal_url": evaluation["proposal_url"],
        "related_skills": related_skills,
        "replaced_by": evaluation["replaced_by"],
        "review_decision": evaluation["review_decision"],
        "review_record_url": (
            f"https://raw.githubusercontent.com/{source_repository}/"
            f"{source_commit}/{review_record_path}"
        ),
        "revoked_hashes": sorted(evaluation["revoked_hashes"]),
        "schema_version": 1,
        "skill_id": record.frontmatter["skill_id"],
        "source_path": source_path,
        "source_url": (
            f"https://raw.githubusercontent.com/{source_repository}/"
            f"{source_commit}/{source_path}"
        ),
        "tags": tags,
        "trust_state": "needs_review",
        "trust_tier": evaluation["trust_tier"],
        "validation_status": "validated",
        "validation_checks": evaluation["validation_checks"],
        "version": evaluation["version"],
    }


def _load_index(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_INDEX_INVALID",
                    path.as_posix(),
                    f"cannot read index JSON: {error}",
                )
            ]
        ) from error
    if not isinstance(parsed, dict) or not isinstance(parsed.get("skills"), list):
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_INDEX_INVALID",
                    path.as_posix(),
                    "index must be an object with a skills array",
                )
            ]
        )
    return parsed


def _validate_source_identity(source_repository: str, source_commit: str) -> None:
    diagnostics: list[Diagnostic] = []
    if not SOURCE_REPOSITORY_PATTERN.fullmatch(source_repository):
        diagnostics.append(
            Diagnostic(
                "CATALOG_SOURCE_REPOSITORY_INVALID",
                "catalog/index.json",
                "source repository must use owner/repository form",
            )
        )
    if not COMMIT_PATTERN.fullmatch(source_commit):
        diagnostics.append(
            Diagnostic(
                "CATALOG_SOURCE_COMMIT_INVALID",
                "catalog/index.json",
                "source commit must be a full lowercase 40-character Git SHA",
            )
        )
    if diagnostics:
        raise CatalogValidationError(diagnostics)


def _same_version_diagnostics(
    generated_index: dict[str, Any], baseline_index: dict[str, Any], baseline_path: Path
) -> list[Diagnostic]:
    baseline_by_identity: dict[tuple[str, str], str] = {}
    for entry in baseline_index.get("skills", []):
        if not isinstance(entry, dict):
            continue
        identity = (entry.get("skill_id"), entry.get("version"))
        content_hash = entry.get("content_sha256")
        if all(isinstance(item, str) for item in identity) and isinstance(
            content_hash, str
        ):
            baseline_by_identity[identity] = content_hash
    diagnostics: list[Diagnostic] = []
    for entry in generated_index["skills"]:
        identity = (entry["skill_id"], entry["version"])
        previous_hash = baseline_by_identity.get(identity)
        if previous_hash and previous_hash != entry["content_sha256"]:
            diagnostics.append(
                Diagnostic(
                    "CATALOG_SAME_VERSION_DRIFT",
                    baseline_path.as_posix(),
                    (
                        f"{entry['skill_id']} {entry['version']} changed from "
                        f"{previous_hash} to {entry['content_sha256']}; bump version"
                    ),
                )
            )
    return diagnostics


def generate_catalog_index(
    catalog_root: Path | str,
    *,
    source_repository: str,
    source_commit: str,
    baseline_index_path: Path | str | None = None,
    allow_draft_provenance: bool = False,
    install_state: str = "held",
    public_evidence_resolver: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Validate inputs and generate the canonical deterministic index object."""

    _validate_source_identity(source_repository, source_commit)
    if install_state not in {"held", "available"}:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_INSTALL_STATE_INVALID",
                    "catalog/index.json",
                    "install_state must be held or available",
                )
            ]
        )
    if allow_draft_provenance:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_DRAFT_NOT_RELEASE_ELIGIBLE",
                    "catalog/index.json",
                    "draft validation cannot emit a catalog descriptor",
                )
            ]
        )
    records = validate_catalog(
        catalog_root,
        allow_draft_provenance=allow_draft_provenance,
        require_public_authority=True,
    )
    generated = {
        "schema_version": 1,
        "source_commit": source_commit,
        "source_repository": source_repository,
        "skills": [
            _record_entry(
                record,
                source_repository,
                source_commit,
                install_state,
            )
            for record in records
        ],
    }
    if install_state == "available":
        diagnostics: list[Diagnostic] = []
        for entry in generated["skills"]:
            for field_name in ("proposal_url", "review_record_url"):
                evidence_url = entry.get(field_name)
                try:
                    resolved = (
                        isinstance(evidence_url, str)
                        and public_evidence_resolver is not None
                        and public_evidence_resolver(evidence_url)
                    )
                except Exception:
                    resolved = False
                if not resolved:
                    diagnostics.append(
                        Diagnostic(
                            "CATALOG_PUBLIC_EVIDENCE_UNAVAILABLE",
                            entry["source_path"],
                            f"available entries require anonymously resolvable {field_name}",
                        )
                    )
        if diagnostics:
            raise CatalogValidationError(diagnostics)
    if baseline_index_path is not None:
        baseline_path = Path(baseline_index_path)
        if baseline_path.exists():
            baseline = _load_index(baseline_path)
            diagnostics = _same_version_diagnostics(generated, baseline, baseline_path)
            if diagnostics:
                raise CatalogValidationError(diagnostics)
    return generated


def render_catalog_index(index: dict[str, Any]) -> bytes:
    return (json.dumps(index, indent=2, sort_keys=True) + "\n").encode("utf-8")


def check_catalog_index(
    catalog_root: Path | str, index_path: Path | str
) -> dict[str, Any]:
    """Regenerate twice, reject nondeterminism, and compare checked-in bytes."""

    index_file = Path(index_path)
    baseline = _load_index(index_file)
    source_repository = baseline.get("source_repository")
    source_commit = baseline.get("source_commit")
    if not isinstance(source_repository, str) or not isinstance(source_commit, str):
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_INDEX_INVALID",
                    index_file.as_posix(),
                    "checked-in index must record source_repository and source_commit",
                )
            ]
        )
    install_states = {
        entry.get("install_state")
        for entry in baseline.get("skills", [])
        if isinstance(entry, dict)
    }
    if install_states != {"held"}:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_INDEX_INVALID",
                    index_file.as_posix(),
                    (
                        "checked-in source candidate must remain held; only the "
                        "governed publisher may produce an available descriptor"
                    ),
                )
            ]
        )
    first = generate_catalog_index(
        catalog_root,
        source_repository=source_repository,
        source_commit=source_commit,
        baseline_index_path=index_file,
        install_state="held",
    )
    second = generate_catalog_index(
        catalog_root,
        source_repository=source_repository,
        source_commit=source_commit,
        baseline_index_path=index_file,
        install_state="held",
    )
    first_bytes = render_catalog_index(first)
    second_bytes = render_catalog_index(second)
    if first_bytes != second_bytes:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_NONDETERMINISTIC",
                    index_file.as_posix(),
                    "two clean regenerations produced different bytes",
                )
            ]
        )
    checked_in = index_file.read_bytes()
    if checked_in != first_bytes:
        raise CatalogValidationError(
            [
                Diagnostic(
                    "CATALOG_INDEX_DRIFT",
                    index_file.as_posix(),
                    "checked-in index differs from deterministic generation",
                )
            ]
        )
    return first
