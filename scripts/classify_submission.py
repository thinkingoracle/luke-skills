#!/usr/bin/env python3
"""Decide what an arriving issue is, and whether its attestations are present.

This is the logic the arrival workflow runs. It lives here, as a script with
tests, rather than as bash inside YAML, because every defect in that workflow so
far reached review unnoticed for the same reason: nothing executed it. A
classifier nobody can run is a classifier nobody can check.

Two questions, kept separate because they fail differently:

  - is this issue a skill proposal at all, and if so is it structured?
  - are the four contributor attestations present, by their exact words?

    classify_submission.py --body body.md
    classify_submission.py --body body.md --github-output "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# The four claims, verbatim. Whole-line matches only: a box that begins with a
# required claim and then negates it is a checked box for a claim nobody made.
REQUIRED_ATTESTATIONS: dict[str, str] = {
    "right-to-submit":
        "I have the right to submit this material under Apache-2.0-compatible "
        "terms and included all required notices.",
    "no-private-data":
        "I included no secret, credential, private user data, copied browser "
        "session, or undisclosed vulnerability detail.",
    "intake-only":
        "I understand this issue is proposal intake only and cannot review, "
        "accept, publish, install, or activate the skill.",
    "review-lifecycle":
        "I understand maintainers control the only source-review lifecycle, "
        "public status stays on this issue, and each user separately trusts the "
        "exact content hash.",
}

# What only a proposal carries.
FILE_SECTION = re.compile(r"^#{1,6}[ \t]+`?(?:skills/|evals/)", re.MULTILINE)
DECLARED_HASH = re.compile(r"sha-?256[:\s]+[0-9a-fA-F]{64}", re.IGNORECASE)
FENCE = re.compile(r"^[ \t]*`{3,}", re.MULTILINE)

# What the other intake forms carry. Checked first, because a bug report naming
# a skill by its canonical `browser-skill:` ID would otherwise look like a
# proposal that forgot its structure, and telling a bug reporter to add file
# sections is worse than saying nothing.
OTHER_FORM_MARKERS = (
    re.compile(r"^#{1,6}[ \t]+Skill ID[ \t]*$", re.MULTILINE),
    re.compile(r"^#{1,6}[ \t]+What you asked, and what came back[ \t]*$", re.MULTILINE),
    re.compile(r"^#{1,6}[ \t]+What you ran or read[^\n]*$", re.MULTILINE),
    re.compile(r"^#{1,6}[ \t]+What do you want Luke to be able to look up\?[ \t]*$", re.MULTILINE),
    re.compile(r"^#{1,6}[ \t]+Does it need a login[^\n]*$", re.MULTILINE),
)

CHECKBOX = re.compile(r"^[ \t]*-[ \t]*\[([ xX])\][ \t]*(.*)$")


def canonical(text: str) -> str:
    """Whitespace-insensitive, punctuation-tolerant form for comparison."""
    return " ".join(text.split()).rstrip(".").casefold()


def ticked_claims(body: str) -> set[str]:
    """Every ticked checkbox, with wrapped continuation lines rejoined.

    The governed prompt wraps each attestation across several indented lines.
    Matching physical lines therefore recognised none of them, and a contributor
    following the published block exactly was told their attestations were
    missing.
    """
    found: set[str] = set()
    lines = body.split("\n")
    index = 0
    while index < len(lines):
        match = CHECKBOX.match(lines[index])
        if not match:
            index += 1
            continue
        state, first = match.group(1), match.group(2)
        parts = [first]
        index += 1
        # A continuation is an indented, non-empty line that starts no new list
        # item, heading, or fence.
        while index < len(lines):
            following = lines[index]
            if not following.strip():
                break
            if not following[:1].isspace():
                break
            if CHECKBOX.match(following) or following.lstrip().startswith(("#", "```", "- ", "* ")):
                break
            parts.append(following.strip())
            index += 1
        if state in ("x", "X"):
            found.add(canonical(" ".join(parts)))
    return found


def missing_attestations(body: str) -> list[str]:
    ticked = ticked_claims(body)
    return [
        name
        for name, claim in REQUIRED_ATTESTATIONS.items()
        if canonical(claim) not in ticked
    ]


def classify(body: str) -> str:
    """One of: structured, unstructured, other.

    `other` means an issue this check has nothing to say about, which includes
    every non-proposal intake form. Saying nothing is the correct output there;
    posting a proposal-contract correction to a bug reporter is not.
    """
    if any(marker.search(body) for marker in OTHER_FORM_MARKERS):
        return "other"

    if FILE_SECTION.search(body) or DECLARED_HASH.search(body):
        return "structured"

    # Carries a payload but not the structure that makes it checkable. This is
    # the hand-crafted API case, and it must be reported rather than skipped:
    # a submission must not bypass the contract by being less complete.
    if FENCE.search(body) and re.search(r"browser-skill:|SKILL\.md|evals/", body):
        return "unstructured"

    return "other"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", required=True, type=Path)
    parser.add_argument("--github-output", type=Path)
    arguments = parser.parse_args(argv)

    try:
        body = arguments.body.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"CLASSIFY_BODY_UNREADABLE: {error}", file=sys.stderr)
        return 1

    shape = classify(body)
    missing = missing_attestations(body) if shape != "other" else []
    result = {"shape": shape, "missing": missing}

    if arguments.github_output:
        with arguments.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"shape={shape}\n")
            handle.write("missing=" + " ".join(missing) + "\n")

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
