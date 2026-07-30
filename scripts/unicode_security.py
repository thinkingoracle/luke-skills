#!/usr/bin/env python3
"""Versioned source-byte admission for untrusted Luke catalog proposals.

Catalog proposals arrive as bytes written by strangers. Invisible and
directional characters let those bytes render one way to a human reviewer and
mean something else to a machine, so they are refused at admission rather than
explained away later.

The profile is deliberately local and version controlled. It is never fetched
over the network, never negotiated by a source, evaluation, or schema field,
and never silently relaxed: a future boundary becomes a separately reviewed
profile identifier, not a quiet edit to this one.

Nothing here rewrites, repairs, normalizes, strips, or re-encodes the bytes it
inspects. A rejected file is reported at its exact location and left exactly as
it was submitted, so the hash a reviewer sees is always the hash of the
submitted bytes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROFILE_LUKE_SKILL_UNICODE_V1 = "luke-skill-unicode-v1"
SUPPORTED_PROFILES = frozenset({PROFILE_LUKE_SKILL_UNICODE_V1})
DEFAULT_PROFILE = PROFILE_LUKE_SKILL_UNICODE_V1

DIAGNOSTIC_BOM = "CATALOG_UNICODE_BOM_FORBIDDEN"
DIAGNOSTIC_BIDI = "CATALOG_UNICODE_BIDI_FORBIDDEN"
DIAGNOSTIC_CONTROL = "CATALOG_UNICODE_CONTROL_FORBIDDEN"
DIAGNOSTIC_PROFILE_UNKNOWN = "CATALOG_UNICODE_PROFILE_UNKNOWN"

BYTE_ORDER_MARK = "\ufeff"

# Tab and line feed are the only control characters a skill or evaluation may
# carry. Carriage return is deliberately absent: a lone or paired CR is a
# control character that changes how a file renders without being visible.
ALLOWED_CONTROL_CHARACTERS = frozenset({"\n", "\t"})

# Explicit directional and invisible formatting characters. These are the
# characters that let submitted source read differently to a human than it
# parses to a machine.
FORBIDDEN_FORMAT_CODE_POINTS = frozenset(
    {0x061C}  # ARABIC LETTER MARK
    | {0x200E, 0x200F}  # LEFT-TO-RIGHT MARK, RIGHT-TO-LEFT MARK
    | set(range(0x202A, 0x202F))  # LRE, RLE, PDF, LRO, RLO
    | set(range(0x2066, 0x206A))  # LRI, RLI, FSI, PDI
    | {0xFEFF}  # ZERO WIDTH NO-BREAK SPACE, and the UTF-8 BOM
)


class UnknownUnicodeProfileError(ValueError):
    """The requested source-security profile is not available locally.

    Raised instead of falling back to a permissive scan. There is no network
    lookup and no default-on-miss: an unrecognized profile identifier stops
    admission.
    """


@dataclass(frozen=True, order=True)
class UnicodeSecurityFinding:
    """One stable, sortable source-admission finding."""

    code: str
    path: str
    message: str

    def render(self) -> str:
        return f"{self.code} {self.path}: {self.message}"


def require_supported_profile(profile: str) -> str:
    """Return the profile identifier, or fail closed if it is not supported."""

    if profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise UnknownUnicodeProfileError(
            f"{DIAGNOSTIC_PROFILE_UNKNOWN}: source-security profile "
            f"{profile!r} is not available locally; supported profiles: "
            f"{supported}"
        )
    return profile


def _line_and_column(text: str, offset: int) -> tuple[int, int]:
    """Return the 1-based line and column of a code point offset."""

    preceding = text[:offset]
    line = preceding.count("\n") + 1
    last_newline = preceding.rfind("\n")
    column = offset - last_newline
    return line, column


def _describe_code_point(character: str) -> str:
    """Name a code point without ever echoing surrounding source."""

    return f"U+{ord(character):04X}"


def _scan_code_points(
    text: str,
    *,
    path: str,
    profile: str,
    location_prefix: str = "",
) -> list[UnicodeSecurityFinding]:
    """Report every forbidden code point in already-decoded text."""

    findings: list[UnicodeSecurityFinding] = []
    for offset, character in enumerate(text):
        code_point = ord(character)
        is_bom_at_start = character == BYTE_ORDER_MARK and offset == 0 and not location_prefix
        if is_bom_at_start:
            findings.append(
                UnicodeSecurityFinding(
                    DIAGNOSTIC_BOM,
                    path,
                    f"{profile} rejects a leading UTF-8 byte order mark "
                    f"({_describe_code_point(character)})",
                )
            )
            continue
        if code_point in FORBIDDEN_FORMAT_CODE_POINTS:
            line, column = _line_and_column(text, offset)
            findings.append(
                UnicodeSecurityFinding(
                    DIAGNOSTIC_BIDI,
                    path,
                    f"{profile} rejects invisible or directional character "
                    f"{_describe_code_point(character)} at "
                    f"{location_prefix}line {line}, column {column}",
                )
            )
            continue
        if character in ALLOWED_CONTROL_CHARACTERS:
            continue
        if code_point <= 0x1F or 0x7F <= code_point <= 0x9F:
            line, column = _line_and_column(text, offset)
            findings.append(
                UnicodeSecurityFinding(
                    DIAGNOSTIC_CONTROL,
                    path,
                    f"{profile} rejects control character "
                    f"{_describe_code_point(character)} at "
                    f"{location_prefix}line {line}, column {column}; only tab "
                    f"and line feed are allowed",
                )
            )
    return findings


def scan_source_text(
    text: str,
    *,
    path: str,
    profile: str = DEFAULT_PROFILE,
) -> list[UnicodeSecurityFinding]:
    """Scan decoded skill source for forbidden code points.

    `text` must already be the result of a strict UTF-8 decode of the exact
    submitted bytes. The text is inspected, never rewritten.
    """

    require_supported_profile(profile)
    return _scan_code_points(text, path=path, profile=profile)


def _json_member_paths(value: Any, pointer: str = "$") -> list[tuple[str, str]]:
    """Yield (json pointer, string) for every string in a parsed document.

    Object keys are walked as well as values: a forbidden code point hidden in
    a key is exactly as effective as one hidden in a value.
    """

    members: list[tuple[str, str]] = []
    if isinstance(value, str):
        members.append((pointer, value))
    elif isinstance(value, dict):
        for key in value:
            if isinstance(key, str):
                members.append((f"{pointer}.{key} (key)", key))
            members.extend(_json_member_paths(value[key], f"{pointer}.{key}"))
    elif isinstance(value, list):
        for position, item in enumerate(value):
            members.extend(_json_member_paths(item, f"{pointer}[{position}]"))
    return members


def scan_evaluation_json(
    raw_text: str,
    *,
    path: str,
    profile: str = DEFAULT_PROFILE,
    parsed: Any = None,
) -> list[UnicodeSecurityFinding]:
    """Scan an evaluation fixture in both of its meaningful representations.

    A forbidden code point can be written literally into the file, or hidden
    behind a `\\uXXXX` escape that only appears after JSON decoding. Both are
    scanned so the two forms fail identically. Neither representation is
    rewritten.
    """

    require_supported_profile(profile)
    findings = _scan_code_points(raw_text, path=path, profile=profile)
    if parsed is None:
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            # Structural JSON problems are reported by the catalog validator.
            # The literal scan above already covered the submitted bytes.
            return findings
    for pointer, member in _json_member_paths(parsed):
        for finding in _scan_code_points(
            member,
            path=path,
            profile=profile,
            location_prefix=f"decoded JSON string {pointer}, ",
        ):
            if finding not in findings:
                findings.append(finding)
    return findings


def scan_catalog_source(
    root: Path | str,
    profile: str = DEFAULT_PROFILE,
) -> list[UnicodeSecurityFinding]:
    """Scan every skill source and evaluation fixture under a catalog root.

    This is the standalone entry point. It reads from disk on every call and
    holds no cache, so a result produced for one set of bytes can never admit a
    different set.
    """

    require_supported_profile(profile)
    catalog_root = Path(root)
    findings: list[UnicodeSecurityFinding] = []

    skills_root = catalog_root / "skills"
    if skills_root.is_dir():
        for skill_directory in sorted(skills_root.iterdir()):
            skill_path = skill_directory / "SKILL.md"
            if not skill_path.is_file():
                continue
            relative = skill_path.relative_to(catalog_root).as_posix()
            try:
                text = skill_path.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                # Unreadable or non-UTF-8 source is reported by the catalog
                # validator; admission never guesses at undecodable bytes.
                continue
            findings.extend(scan_source_text(text, path=relative, profile=profile))

    evaluations_root = catalog_root / "evals"
    if evaluations_root.is_dir():
        for evaluation_path in sorted(evaluations_root.iterdir()):
            if not evaluation_path.is_file() or evaluation_path.suffix != ".json":
                continue
            relative = evaluation_path.relative_to(catalog_root).as_posix()
            try:
                raw_text = evaluation_path.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            findings.extend(
                scan_evaluation_json(raw_text, path=relative, profile=profile)
            )

    return sorted(findings)
