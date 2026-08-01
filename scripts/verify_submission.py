#!/usr/bin/env python3
"""Refuse a proposal whose bytes are not exactly what the contributor declared.

Catalog trust binds to `{skill_id, content_sha256}`. Everything downstream of
intake assumes the bytes a maintainer holds are the bytes the contributor wrote,
and until now nothing checked that.

The failure this exists to prevent, reproduced 2026-07-31: a `SKILL.md` that
legitimately contains a fenced example truncates when extracted from a
three-backtick fence. The truncated file was 83 bytes shorter, had a different
SHA-256, and still printed `validated 1 Luke catalog skill(s)`. A maintainer
following the rehearsal procedure would have landed content the author never
wrote, under a hash the author never saw, with every automated check agreeing.

Guidance in the contributor prompt cannot close that, because guidance binds
only submissions that followed it. This does: extraction is checked against the
size and hash the submission itself declares, and anything that does not match
exactly is refused.

    verify_submission.py --issue-body body.md
    verify_submission.py --issue-url https://github.com/o/r/issues/7
    verify_submission.py --issue-body body.md --json

Exit 0 only when every declared identity matches the extracted bytes. That is
conformance only: it is not a usefulness, truthfulness, provenance, or safety
decision, and it does not replace maintainer review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# GitHub rejects an issue body above this character count. Check the same unit
# GitHub documents, not UTF-8 bytes: a locally valid body that cannot be posted
# is not a conforming submission.
MAX_ISSUE_BODY_CHARACTERS = 65_536

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
FULL_PATH = rf"(?:skills/{SLUG}/SKILL\.md|evals/{SLUG}\.json)"
DECLARED_PATH = rf"(?:{FULL_PATH}|SKILL\.md|{SLUG}\.json)"

# The contributor contract shows one declaration on its own line:
# "`SKILL.md`, 1684 bytes, sha256 92884a8a...". Anchor that grammar instead of
# accepting any prose that happens to contain a path, a number, and a digest.
# ASCII is deliberate. Catalog slugs and paths are ASCII even though payload
# contents are UTF-8; Python's default \w would otherwise admit lookalike paths.
DECLARATION = re.compile(
    rf"^\s*`?(?P<path>{DECLARED_PATH})`?\s*[-,]\s*"
    r"(?P<size>\d[\d,]*)\s+bytes\s*[-,]\s*"
    r"sha-?256[:\s]+(?P<sha>[0-9a-fA-F]{64})\s*$",
    re.ASCII | re.MULTILINE,
)

# A submission heading naming one of the two files. Matched only on lines that
# are outside every fenced block; see scan() for why.
SECTION_HEADING = re.compile(rf"^#{{1,6}}\s+`?(?P<path>{FULL_PATH})`?\s*$", re.ASCII)

FENCE_OPEN = re.compile(r"^(?P<ticks>`{3,})")


def scan(body: str) -> tuple[list[tuple[int, str]], list[tuple[int, int, str]]]:
    """Return submission headings and fenced blocks, both fence-aware.

    Payload text is taken as a literal slice of the body, never rebuilt from
    pieces. That is the invariant this function exists to hold, and it is the
    one that ended a run of five defects: every earlier version reassembled
    blocks by splitting and rejoining, and every reassembly normalised
    something. Carriage returns first, then U+2028, and each fix addressed the
    separator that had been named rather than the reassembly that made all of
    them possible. A slice cannot normalise anything, so the class is closed by
    construction rather than by enumeration.

    Line splitting on "\n" alone, never splitlines(), which also breaks on
    U+2028, U+2029, \x0b, \x0c and \x85. Those are payload text here.

    A fence closes only on a run at least as long as the one that opened it,
    which is what lets a four-backtick fence carry content containing three.
    An unclosed fence yields no block, so a truncated body cannot look whole.
    """
    headings: list[tuple[int, str]] = []
    blocks: list[tuple[int, int, str]] = []
    lines = body.split("\n")

    # Where each line begins in the original string, so payload can be sliced
    # out of it rather than rebuilt.
    starts: list[int] = []
    cursor = 0
    for line in lines:
        starts.append(cursor)
        cursor += len(line) + 1
    starts.append(len(body) + 1)

    open_ticks: str | None = None
    opened_at = 0

    for index, line in enumerate(lines):
        opener = FENCE_OPEN.match(line)
        if open_ticks is None:
            if opener:
                open_ticks = opener.group("ticks")
                opened_at = index
                continue
            heading = SECTION_HEADING.match(line)
            if heading:
                headings.append((index, heading.group("path")))
            continue

        closes = (
            opener is not None
            and len(opener.group("ticks")) >= len(open_ticks)
            and not line[len(opener.group("ticks")):].strip()
        )
        if closes:
            # From the first character after the opening fence line to the first
            # character of the closing fence line. Verbatim, including whatever
            # separators the contributor actually sent.
            blocks.append((opened_at, index, body[starts[opened_at + 1]:starts[index]]))
            open_ticks = None

    return headings, blocks


def sections(body: str) -> list[tuple[str, str, list[str]]]:
    """Split into (declared path, section prose, that section's fenced blocks).

    Prose and payload are separated once, here, and never re-derived from raw
    text downstream. Three defects on this branch were the same mistake made at
    different levels: matching structure with a regex over markdown that
    contains a submitted file. Headings were matched that way, then
    declarations were, and a submitted file may legitimately contain either.

    Prose is what a maintainer reads as structure. Payload is what the
    contributor sent. A line inside a fence is payload whatever it looks like.
    """
    headings, blocks = scan(body)
    if not headings:
        return []

    lines = body.split("\n")
    fenced_lines: set[int] = set()
    for open_at, close_at, _ in blocks:
        fenced_lines.update(range(open_at, close_at + 1))

    out: list[tuple[str, str, list[str]]] = []
    for position, (line_number, path) in enumerate(headings):
        end_line = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        prose = "\n".join(
            line
            for index, line in enumerate(lines[line_number + 1:end_line], start=line_number + 1)
            if index not in fenced_lines
        )
        owned = [text for (open_at, _, text) in blocks if line_number < open_at < end_line]
        out.append((path, prose, owned))
    return out


def _same_file(declared: str, heading: str) -> bool:
    # A declaration may name the full path or just the file name; anything else
    # is a declaration about a different file and must not satisfy this one.
    return declared == heading or declared == heading.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Finding:
    code: str
    detail: str

    def render(self) -> str:
        return f"{self.code}: {self.detail}"


def verify(body: str) -> list[Finding]:
    findings: list[Finding] = []

    # Carriage returns are refused rather than normalised. splitlines() drops
    # them, so a CRLF body reconstructs to the same LF text the declared hash
    # was taken over and the verifier agrees with itself, while a maintainer
    # extracting the literal bytes gets CRLF and a different hash. Silently
    # normalising is the one thing a byte-identity check must never do, and the
    # catalog's own profile forbids CR in a payload regardless.
    if "\r" in body:
        return [
            Finding(
                "SUBMISSION_CARRIAGE_RETURN",
                "the submission contains carriage returns. Catalog payloads use "
                "LF endings only, and normalising them here would bless bytes "
                "that differ from the ones a maintainer extracts. Resubmit with "
                "LF endings.",
            )
        ]

    if len(body) > MAX_ISSUE_BODY_CHARACTERS:
        return [
            Finding(
                "SUBMISSION_BODY_TOO_LONG",
                f"the issue body is {len(body)} characters; GitHub accepts at "
                f"most {MAX_ISSUE_BODY_CHARACTERS}. Shorten the proposal before "
                "submission rather than relying on transport truncation.",
            )
        ]

    parsed = sections(body)

    if not parsed:
        return [
            Finding(
                "SUBMISSION_SECTIONS_MISSING",
                "no file sections were found. Each file needs a heading naming "
                "its path, then its declared size and SHA-256, then its fenced "
                "contents.",
            )
        ]

    if not any(DECLARATION.search(prose) for _, prose, _ in parsed):
        return [
            Finding(
                "SUBMISSION_IDENTITY_MISSING",
                "the submission declares no file sizes or SHA-256 values, so the "
                "extracted bytes cannot be checked against what the contributor "
                "sent. Ask the contributor to restate each file's size and hash.",
            )
        ]

    seen_paths: set[str] = set()
    for path, prose, blocks in parsed:
        if path in seen_paths:
            findings.append(
                Finding(
                    "SUBMISSION_SECTION_DUPLICATED",
                    f"{path}: more than one section names this file, so which "
                    "bytes are meant is ambiguous.",
                )
            )
            continue
        seen_paths.add(path)

        # Prose only. A declaration inside the payload is the contributor's
        # content, not a claim about the submission, and counting it rejected
        # valid skills that happened to document one.
        declarations = list(DECLARATION.finditer(prose))

        # Exactly one of each. A second declaration or a second block inside one
        # section is a decoy: it lets a body carry a hash matching something
        # other than the bytes a maintainer would extract under this heading.
        if len(declarations) != 1:
            findings.append(
                Finding(
                    "SUBMISSION_DECLARATION_NOT_UNIQUE",
                    f"{path}: expected exactly one declared size and SHA-256 in "
                    f"this section, found {len(declarations)}.",
                )
            )
            continue
        if len(blocks) != 1:
            findings.append(
                Finding(
                    "SUBMISSION_BLOCK_NOT_UNIQUE",
                    f"{path}: expected exactly one fenced block in this section, "
                    f"found {len(blocks)}. A fence ending early is the usual "
                    "cause, and it truncates silently.",
                )
            )
            continue

        declaration = declarations[0]
        declared_path = declaration.group("path")
        declared_size = int(declaration.group("size").replace(",", ""))
        declared_sha = declaration.group("sha").lower()
        block = blocks[0]

        if not _same_file(declared_path, path):
            findings.append(
                Finding(
                    "SUBMISSION_IDENTITY_MISBOUND",
                    f"{path}: this section declares the identity of "
                    f"{declared_path!r} instead of its own. Swapping identities "
                    "between sections would hand a maintainer bytes that match "
                    "neither named file.",
                )
            )
            continue

        actual_size = len(block.encode("utf-8"))
        actual_sha = hashlib.sha256(block.encode("utf-8")).hexdigest()

        if actual_sha != declared_sha:
            findings.append(
                Finding(
                    "SUBMISSION_BYTES_ALTERED",
                    f"{path}: declared {declared_size} bytes / {declared_sha[:16]}, "
                    f"extracted {actual_size} bytes / {actual_sha[:16]}. "
                    + (
                        "The extracted content is shorter, which is what a fence "
                        "ending early looks like. Do not land these bytes."
                        if actual_size < declared_size
                        else "Do not land these bytes."
                    ),
                )
            )
            continue

        if actual_size != declared_size:
            findings.append(
                Finding(
                    "SUBMISSION_SIZE_CONTRADICTS_HASH",
                    f"{path}: the hash matches a block of {actual_size} bytes, "
                    f"but the declared size is {declared_size}.",
                )
            )

    return findings


def fetch_issue_body(issue_url: str) -> str:
    parts = issue_url.rstrip("/").split("/")
    try:
        number = parts[-1]
        repository = f"{parts[-4]}/{parts[-3]}"
    except IndexError as error:
        raise ValueError(f"could not parse an issue URL from {issue_url!r}") from error
    # Bytes, not text mode. Python's universal-newline handling rewrites CRLF to
    # LF on the way in, which would hide exactly the carriage returns verify()
    # refuses and turn that check into dead code.
    completed = subprocess.run(
        ["gh", "api", f"repos/{repository}/issues/{number}"],
        check=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)
    body = payload.get("body")
    if not isinstance(body, str):
        raise ValueError(f"issue {repository}#{number} has no text body")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue-body", type=Path)
    source.add_argument("--issue-url")
    parser.add_argument("--json", action="store_true", help="Machine-readable result.")
    arguments = parser.parse_args(argv)

    try:
        body = (
            # read_bytes rather than read_text: read_text applies universal
            # newlines and would strip the carriage returns verify() exists to
            # refuse, silently, before anything could see them.
            arguments.issue_body.read_bytes().decode("utf-8")
            if arguments.issue_body
            else fetch_issue_body(arguments.issue_url)
        )
    except (OSError, UnicodeDecodeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"SUBMISSION_UNREADABLE: {error}", file=sys.stderr)
        return 1

    findings = verify(body)

    if arguments.json:
        print(
            json.dumps(
                {
                    "ok": not findings,
                    "classification": "nonconforming" if findings else "conformance_only",
                    "findings": [{"code": f.code, "detail": f.detail} for f in findings],
                },
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(finding.render(), file=sys.stderr)
        if not findings:
            print(
                "submission bytes match every declared identity; conformance "
                "only, maintainer review is still required"
            )

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
