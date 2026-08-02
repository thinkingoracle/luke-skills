#!/usr/bin/env python3
"""Render a validated proposal into the exact submission the form collects.

The proposal form is the structure a reviewer reads and the structure the
arrival check verifies. What it should not be is thirteen boxes a person retypes
from output their agent already produced.

This turns the two generated files plus one answers file into that structure,
including the size and SHA-256 of each payload, which is what makes a truncated
or substituted submission impossible to land unnoticed.

It renders. It does not submit, and it cannot: filing is `gh issue create`, and
the person's yes belongs in front of that rather than inside a script.

    render_submission.py --answers answers.json --proposal-root /tmp/my-proposal
    render_submission.py --answers answers.json --proposal-root /tmp/p --dry-run
    render_submission.py --answers answers.json --proposal-root /tmp/p --json

Exit 0 only when the rendered submission is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# The proposal form's fields, in the form's own order. A rendered submission and
# a form-filled one must read identically to a reviewer and verify identically
# to the arrival check.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("skill-name", "Proposed skill name and ID"),
    ("user-need", "User and need"),
    ("public-hosts", "Public hosts"),
    ("authentication-boundary", "Authentication boundary"),
    ("data-boundary", "Data boundary"),
    ("mutation-boundary", "Mutation boundary"),
    ("behavior-and-result", "Expected behavior and result"),
    ("examples", "Realistic examples"),
    ("evaluation-evidence", "Evaluation evidence"),
    ("provenance", "Provenance"),
    ("license", "License and notices"),
)

# Exact strings, because these two are dropdowns on the form and a paraphrase
# reads as a different answer to the boundary question.
FIXED_CHOICES: dict[str, tuple[str, ...]] = {
    "authentication-boundary": (
        "No authentication or credentials are required",
        (
            "Authentication uses only Luke's owned browser; the user signs in "
            "locally and no credentials are collected"
        ),
    ),
    "mutation-boundary": ("Read-only, with no external mutation",),
}

ATTESTATIONS: tuple[str, ...] = (
    "I have the right to submit this material under Apache-2.0-compatible terms "
    "and included all required notices.",
    "I included no secret, credential, private user data, copied browser "
    "session, or undisclosed vulnerability detail.",
    "I understand this issue is proposal intake only and cannot review, accept, "
    "publish, install, or activate the skill.",
    "I understand maintainers control the only source-review lifecycle, public "
    "status stays on this issue, and each user separately trusts the exact "
    "content hash.",
)


class RenderError(Exception):
    """A named failure an agent can act on without reading this source."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def fence_for(text: str) -> str:
    """A fence longer than any backtick run inside the payload.

    A three-backtick fence around a file containing three ends early. The
    extracted file is then shorter, hashes differently, and still passes every
    validator, which is how a maintainer lands bytes the author never wrote.
    """
    longest = 0
    run = 0
    for character in text:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def identity(name: str, text: str) -> str:
    encoded = text.encode("utf-8")
    return f"`{name}`, {len(encoded)} bytes, sha256 {hashlib.sha256(encoded).hexdigest()}"


def load(path: Path, code: str) -> str:
    try:
        # Bytes, not text: universal newlines would rewrite separators the
        # arrival check refuses, and the declared hash must cover what was sent.
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RenderError(code, f"could not read {path}: {error}") from error


def render(answers: dict[str, object], slug: str, skill: str, evaluation: str) -> str:
    missing = [
        field
        for field, _ in SECTIONS
        if not isinstance(answers.get(field), str) or not answers[field].strip()
    ]
    if missing:
        raise RenderError(
            "RENDER_FIELD_MISSING",
            "the answers file is missing: " + ", ".join(sorted(set(missing))),
        )

    for field, allowed in FIXED_CHOICES.items():
        if answers.get(field) not in allowed:
            allowed_text = " or ".join(repr(value) for value in allowed)
            raise RenderError(
                "RENDER_CHOICE_INVALID",
                f"{field} must be exactly: {allowed_text}. Anything else is a "
                "different answer to the boundary question, and V1 accepts only "
                "the listed choices.",
            )

    if answers.get("attestations_confirmed_by_human") is not True:
        raise RenderError(
            "RENDER_ATTESTATION_UNCONFIRMED",
            "ask the person, in their own words, where the material came from, "
            "under what licence, and whether it contains anything private. Set "
            "attestations_confirmed_by_human to true only after they answer. An "
            "attestation you filled in yourself is worth nothing.",
        )

    # No deduplication. It existed to hide a heading collision, and hiding a
    # collision meant dropping a contributor's answer without saying so. Two
    # fields sharing a heading is a bug in this table, not input to handle.
    headings = [heading for _, heading in SECTIONS]
    duplicated = {h for h in headings if headings.count(h) > 1}
    if duplicated:
        raise RenderError(
            "RENDER_HEADING_COLLISION",
            "two fields share a heading, which would drop one answer: "
            + ", ".join(sorted(duplicated)),
        )

    out: list[str] = []
    for field, heading in SECTIONS:
        out.append(f"### {heading}\n\n{str(answers[field]).strip()}\n")

    for path, text in (
        (f"skills/{slug}/SKILL.md", skill),
        (f"evals/{slug}.json", evaluation),
    ):
        fence = fence_for(text)
        language = "markdown" if path.endswith(".md") else "json"
        out.append(f"### {path}\n")
        out.append(identity(path.rsplit("/", 1)[-1], text) + "\n")
        out.append(f"{fence}{language}\n{text.rstrip()}\n{fence}\n")

    out.append("### Contributor attestations\n")
    out.extend(f"- [x] {line}" for line in ATTESTATIONS)
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--proposal-root", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("submission.md"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the submission and the command instead of writing anything.",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable result.")
    parser.add_argument(
        "--repository",
        default="thinkingoracle/luke-skills",
        help="Where the proposal would be filed.",
    )
    arguments = parser.parse_args(argv)

    try:
        decoded = json.loads(load(arguments.answers, "RENDER_ANSWERS_UNREADABLE"))
        if not isinstance(decoded, dict):
            raise RenderError(
                "RENDER_ANSWERS_INVALID", "the answers file must be a JSON object"
            )
        slug = decoded.get("slug")
        if not isinstance(slug, str) or not slug:
            raise RenderError("RENDER_SLUG_MISSING", "the answers file needs a slug")

        root = arguments.proposal_root
        body = render(
            decoded,
            slug,
            load(root / "skills" / slug / "SKILL.md", "RENDER_SKILL_UNREADABLE"),
            load(root / "evals" / f"{slug}.json", "RENDER_EVALUATION_UNREADABLE"),
        )
    except RenderError as error:
        if arguments.json:
            print(json.dumps({"ok": False, "code": error.code, "detail": error.detail}))
        else:
            print(f"{error.code}: {error.detail}", file=sys.stderr)
        return 1

    title = f"[skill proposal] {slug}"
    command = (
        f"gh issue create --repo {arguments.repository} "
        f'--title "{title}" --body-file {arguments.out}'
    )

    # Retry safety belongs here, before the create, rather than in a report
    # afterwards. An interrupted run cannot remember that it already filed, so
    # it asks the only thing that knows.
    existing = None
    try:
        found = subprocess.run(
            ["gh", "issue", "list", "--repo", arguments.repository, "--state", "open",
             "--search", f'"{title}" in:title', "--json", "number", "--jq", ".[0].number // empty"],
            check=False, capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        existing = int(found) if found.isdigit() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        # No gh, no network, no opinion. Never block on a check that cannot run.
        existing = None

    if existing is not None:
        detail = (
            f"issue #{existing} in {arguments.repository} is already an open "
            f"proposal titled {title!r}. If a previous run was interrupted, this "
            "would be the second one. Edit that issue instead, or close it first."
        )
        if arguments.json:
            print(json.dumps({"ok": False, "code": "RENDER_ALREADY_FILED", "detail": detail, "existing": existing}))
        else:
            print(f"RENDER_ALREADY_FILED: {detail}", file=sys.stderr)
        return 1

    if arguments.dry_run:
        # Everything a real run would submit, submitted nowhere.
        if arguments.json:
            print(json.dumps({"ok": True, "dry_run": True, "body": body, "command": command}, indent=2))
        else:
            print(body)
            print(f"\n--- dry run, nothing written or filed. To do it for real:\n{command}")
        return 0

    arguments.out.write_text(body, encoding="utf-8")
    if arguments.json:
        print(json.dumps({"ok": True, "dry_run": False, "path": str(arguments.out), "command": command}, indent=2))
    else:
        print(f"wrote {arguments.out} ({len(body.encode('utf-8'))} bytes)")
        print(f"ask before filing, then: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
