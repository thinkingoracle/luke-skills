#!/usr/bin/env python3
"""Prove a published catalog release from this repository alone.

A release is two commits and a tag. The payload commit ``P`` carries the
published bytes. The descriptor commit ``D`` is its direct child and carries
only the catalog descriptor and the deployment-control records. The release
tag names ``D``.

``structure`` proves that shape offline, from an anonymous clone, using only
objects already fetched: the tag resolves to ``D``, ``D^`` is ``P``, each
commit changed only the paths its role allows, the descriptor names ``P`` and
points only at evidence present there, and every recorded hash matches the
bytes. It needs no network, no credential, and no access to any repository
other than this one.

``release`` is the separate online gate. It proves that a published, non-draft,
non-prerelease release exists for the tag and that it immutably pins ``D``.
It reads public release metadata anonymously and asserts nothing about how the
release was reviewed before publication.

Neither mode reads a second repository, presents a token, or repeats a claim it
cannot check here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable


PUBLIC_REPOSITORY = "thinkingoracle/luke-skills"
CONTROL_DIRECTORY = ".luke-catalog"
CURRENT_DEPLOYMENT_PATH = f"{CONTROL_DIRECTORY}/deployment.json"
PUBLISHED_MANIFEST_PATH = f"{CONTROL_DIRECTORY}/manifest.json"
RELEASE_LEDGER_DIRECTORY = f"{CONTROL_DIRECTORY}/releases"
LEDGER_SCHEMA_VERSION = 2
PUBLIC_PAYLOAD_MANIFEST_SCHEMA_VERSION = 2
EXPECTED_MANIFEST_FIELDS = {"descriptor_paths", "paths", "schema_version"}
TAG_PATTERN = re.compile(
    r"^luke-skills-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RAW_CONTENT_URL_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/"
    r"(?P<owner>[A-Za-z0-9._-]+)/(?P<repository>[A-Za-z0-9._-]+)/"
    r"(?P<commit>[0-9a-f]{40})/(?P<path>.+)$"
)
DESCRIPTOR_PROVENANCE_URL_FIELDS = ("review_record_url", "source_url")
EXPECTED_RECORD_FIELDS = {
    "descriptor_paths",
    "descriptor_sha256",
    "manifest_sha256",
    "payload_commit",
    "payload_path_sha256",
    "payload_sha256",
    "previous_ledger_sha256",
    "previous_release_tag",
    "public_repository",
    "release_tag",
    "schema_version",
    "source_commit",
    "source_tree",
    "version",
}


class VerificationError(RuntimeError):
    """A stable fail-closed verification diagnostic."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def render(self) -> str:
        return f"{self.code}: {self.detail}"


def release_version(release_tag: str) -> tuple[int, int, int]:
    match = TAG_PATTERN.fullmatch(release_tag)
    if match is None:
        raise VerificationError(
            "VERIFY_RELEASE_TAG_INVALID",
            "release tag must match luke-skills-v<major>.<minor>.<patch> exactly",
        )
    return tuple(int(component) for component in match.groups())


def _run_git(
    repository_root: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(
            "VERIFY_GIT_COMMAND_FAILED",
            f"git {' '.join(arguments)} failed: {stderr}",
        )
    return completed


def _resolve_commit(repository_root: Path, revision: str) -> str:
    completed = _run_git(
        repository_root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{revision}^{{commit}}",
        check=False,
    )
    resolved = completed.stdout.decode("ascii", errors="replace").strip()
    if completed.returncode != 0 or COMMIT_PATTERN.fullmatch(resolved) is None:
        raise VerificationError(
            "VERIFY_REFERENCE_MISSING",
            f"{revision} does not resolve to a commit in this clone",
        )
    return resolved


def _read_tree_paths(repository_root: Path, commit: str) -> tuple[str, ...]:
    listing = _run_git(
        repository_root, "ls-tree", "-r", "--name-only", "-z", commit
    ).stdout
    return tuple(
        entry.decode("utf-8", errors="replace")
        for entry in listing.split(b"\0")
        if entry
    )


def _read_blob(repository_root: Path, commit: str, relative_path: str) -> bytes:
    completed = _run_git(
        repository_root, "show", f"{commit}:{relative_path}", check=False
    )
    if completed.returncode != 0:
        raise VerificationError(
            "VERIFY_PATH_MISSING",
            f"{relative_path} is not present at {commit}",
        )
    return completed.stdout


def _changed_paths(repository_root: Path, commit: str) -> tuple[str, ...]:
    changed = _run_git(
        repository_root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "-z",
        commit,
    ).stdout
    return tuple(
        entry.decode("utf-8", errors="replace")
        for entry in changed.split(b"\0")
        if entry
    )


def _commit_parents(repository_root: Path, commit: str) -> tuple[str, ...]:
    parents = (
        _run_git(repository_root, "rev-list", "--parents", "-n", "1", commit)
        .stdout.decode("ascii", errors="replace")
        .split()
    )
    return tuple(parents[1:])


def payload_digest(payload: dict[str, bytes]) -> str:
    """Digest a path-to-bytes mapping unambiguously.

    Each path and each blob is length-prefixed so that no rearrangement of
    names and contents can produce a colliding payload.
    """

    digest = hashlib.sha256()
    for relative_path in sorted(payload):
        encoded_path = relative_path.encode("utf-8")
        content = payload[relative_path]
        digest.update(len(encoded_path).to_bytes(8, byteorder="big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, byteorder="big"))
        digest.update(content)
    return digest.hexdigest()


def render_record(record: dict[str, object]) -> bytes:
    return (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_record(raw_record: bytes, label: str) -> dict[str, object]:
    try:
        record = json.loads(raw_record.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(
            "VERIFY_LEDGER_INVALID", f"{label} is not valid UTF-8 JSON"
        ) from error
    if not isinstance(record, dict) or set(record) != EXPECTED_RECORD_FIELDS:
        raise VerificationError(
            "VERIFY_LEDGER_INVALID",
            f"{label} does not contain the exact ledger schema",
        )
    if record["schema_version"] != LEDGER_SCHEMA_VERSION:
        raise VerificationError(
            "VERIFY_LEDGER_INVALID",
            f"{label} is not ledger schema {LEDGER_SCHEMA_VERSION}",
        )
    if record["public_repository"] != PUBLIC_REPOSITORY:
        raise VerificationError(
            "VERIFY_LEDGER_INVALID", f"{label} names another distribution repository"
        )
    release_tag = record["release_tag"]
    if not isinstance(release_tag, str):
        raise VerificationError(
            "VERIFY_LEDGER_INVALID", f"{label} has no release tag"
        )
    version = release_version(release_tag)
    if record["version"] != ".".join(str(component) for component in version):
        raise VerificationError(
            "VERIFY_LEDGER_INVALID", f"{label} version does not match its tag"
        )
    if COMMIT_PATTERN.fullmatch(str(record["payload_commit"])) is None:
        raise VerificationError(
            "VERIFY_LEDGER_INVALID", f"{label} has an invalid payload commit"
        )
    for field in ("descriptor_sha256", "manifest_sha256", "payload_sha256"):
        if DIGEST_PATTERN.fullmatch(str(record[field])) is None:
            raise VerificationError(
                "VERIFY_LEDGER_INVALID", f"{label} has an invalid {field}"
            )
    digests = record["payload_path_sha256"]
    descriptor_paths = record["descriptor_paths"]
    if (
        not isinstance(digests, dict)
        or not digests
        or any(
            DIGEST_PATTERN.fullmatch(str(value)) is None
            for value in digests.values()
        )
        or not isinstance(descriptor_paths, list)
        or not descriptor_paths
        or any(not isinstance(entry, str) for entry in descriptor_paths)
    ):
        raise VerificationError(
            "VERIFY_LEDGER_INVALID", f"{label} has an invalid path inventory"
        )
    return record


def read_ledger(
    repository_root: Path, descriptor_commit: str
) -> dict[str, dict[str, object]]:
    """Read every ledger record carried by the descriptor commit."""

    records: dict[str, dict[str, object]] = {}
    for relative_path in _read_tree_paths(repository_root, descriptor_commit):
        if (
            not relative_path.startswith(f"{RELEASE_LEDGER_DIRECTORY}/")
            or not relative_path.endswith(".json")
        ):
            continue
        raw_record = _read_blob(repository_root, descriptor_commit, relative_path)
        record = _parse_record(raw_record, relative_path)
        release_tag = str(record["release_tag"])
        if relative_path != f"{RELEASE_LEDGER_DIRECTORY}/{release_tag}.json":
            raise VerificationError(
                "VERIFY_LEDGER_INVALID",
                f"{relative_path} does not match the tag it records",
            )
        if raw_record != render_record(record):
            raise VerificationError(
                "VERIFY_LEDGER_INVALID",
                f"{relative_path} is not in canonical record form",
            )
        records[release_tag] = record
    if not records:
        raise VerificationError(
            "VERIFY_LEDGER_MISSING",
            "the descriptor commit carries no release ledger",
        )
    return records


def assert_ledger_chain(ledger: dict[str, dict[str, object]]) -> None:
    """Require an unbroken, strictly ascending chain of release records.

    Each record commits to the exact bytes of the record before it, so removing
    or replacing a historical record breaks the link that follows it.
    """

    ordered = sorted(
        ledger.values(),
        key=lambda record: release_version(str(record["release_tag"])),
    )
    expected_tag: str | None = None
    expected_digest: str | None = None
    for record in ordered:
        release_tag = str(record["release_tag"])
        if (
            record["previous_release_tag"] != expected_tag
            or record["previous_ledger_sha256"] != expected_digest
        ):
            raise VerificationError(
                "VERIFY_LEDGER_CHAIN_BROKEN",
                f"{release_tag} does not follow {expected_tag or 'the first release'}",
            )
        expected_tag = release_tag
        expected_digest = hashlib.sha256(render_record(record)).hexdigest()


def verify_published_manifest(
    repository_root: Path,
    descriptor_commit: str,
    record: dict[str, object],
    payload_paths: frozenset[str],
) -> dict[str, object]:
    """Recompute the recorded manifest identity from published bytes.

    The ledger states a manifest digest. That is only a claim until the bytes
    it digests are readable here, so the descriptor commit publishes the
    manifest and this recomputes the digest over it. The manifest is then held
    to what it declares: the paths it lists, minus the descriptors it names,
    must be exactly the paths the payload commit carries and the ledger hashes.
    """

    published = _read_blob(
        repository_root, descriptor_commit, PUBLISHED_MANIFEST_PATH
    )
    if hashlib.sha256(published).hexdigest() != record["manifest_sha256"]:
        raise VerificationError(
            "VERIFY_MANIFEST_DRIFT",
            "the published manifest does not match the recorded identity",
        )
    try:
        manifest = json.loads(published.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(
            "VERIFY_MANIFEST_INVALID",
            f"{PUBLISHED_MANIFEST_PATH} is not valid UTF-8 JSON",
        ) from error
    if (
        not isinstance(manifest, dict)
        or set(manifest) != EXPECTED_MANIFEST_FIELDS
        or manifest["schema_version"] != PUBLIC_PAYLOAD_MANIFEST_SCHEMA_VERSION
        or not isinstance(manifest["paths"], list)
        or not isinstance(manifest["descriptor_paths"], list)
        or any(not isinstance(entry, str) for entry in manifest["paths"])
        or any(
            not isinstance(entry, str) for entry in manifest["descriptor_paths"]
        )
    ):
        raise VerificationError(
            "VERIFY_MANIFEST_INVALID",
            f"{PUBLISHED_MANIFEST_PATH} does not contain the exact manifest schema",
        )
    declared_descriptors = sorted(manifest["descriptor_paths"])
    if declared_descriptors != sorted(str(p) for p in record["descriptor_paths"]):
        raise VerificationError(
            "VERIFY_MANIFEST_MISMATCH",
            "the manifest and the ledger name different descriptor paths",
        )
    declared_payload = set(manifest["paths"]) - set(declared_descriptors)
    if declared_payload != set(payload_paths):
        missing = sorted(declared_payload.symmetric_difference(payload_paths))
        raise VerificationError(
            "VERIFY_MANIFEST_MISMATCH",
            (
                "the manifest and the payload commit disagree on what is "
                f"published: {','.join(missing[:5])}"
            ),
        )
    return manifest


def _assert_descriptor_names_payload_commit(
    descriptor: bytes,
    *,
    payload_commit: str,
    payload_paths: frozenset[str],
    label: str,
) -> None:
    try:
        parsed = json.loads(descriptor.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(
            "VERIFY_DESCRIPTOR_INVALID", f"{label} is not valid UTF-8 JSON"
        ) from error
    if not isinstance(parsed, dict) or not isinstance(parsed.get("skills"), list):
        raise VerificationError(
            "VERIFY_DESCRIPTOR_INVALID",
            f"{label} is not an object carrying a skills array",
        )
    if parsed.get("source_commit") != payload_commit:
        raise VerificationError(
            "VERIFY_DESCRIPTOR_NOT_ANCHORED",
            f"{label} does not name the payload commit",
        )
    if parsed.get("source_repository") != PUBLIC_REPOSITORY:
        raise VerificationError(
            "VERIFY_DESCRIPTOR_NOT_ANCHORED",
            f"{label} names another distribution repository",
        )
    for entry in parsed["skills"]:
        if not isinstance(entry, dict):
            raise VerificationError(
                "VERIFY_DESCRIPTOR_INVALID", f"{label} has a non-object entry"
            )
        for field in DESCRIPTOR_PROVENANCE_URL_FIELDS:
            value = entry.get(field)
            match = (
                RAW_CONTENT_URL_PATTERN.fullmatch(value)
                if isinstance(value, str)
                else None
            )
            if match is None:
                raise VerificationError(
                    "VERIFY_DESCRIPTOR_INVALID",
                    f"{label} {field} is not a raw content permalink",
                )
            if (
                match.group("commit") != payload_commit
                or f"{match.group('owner')}/{match.group('repository')}"
                != PUBLIC_REPOSITORY
            ):
                raise VerificationError(
                    "VERIFY_DESCRIPTOR_NOT_ANCHORED",
                    f"{label} {field} does not name the payload commit",
                )
            if match.group("path") not in payload_paths:
                raise VerificationError(
                    "VERIFY_DESCRIPTOR_UNRESOLVABLE_EVIDENCE",
                    (
                        f"{label} {field} names {match.group('path')}, which the "
                        "payload commit does not publish"
                    ),
                )


def _assert_path_classes(
    repository_root: Path,
    *,
    payload_commit: str,
    descriptor_commit: str,
    descriptor_paths: frozenset[str],
) -> None:
    for relative_path in _changed_paths(repository_root, descriptor_commit):
        if (
            relative_path not in descriptor_paths
            and PurePosixPath(relative_path).parts[0] != CONTROL_DIRECTORY
        ):
            raise VerificationError(
                "VERIFY_COMMIT_TOPOLOGY_INVALID",
                f"the descriptor commit also changes {relative_path}",
            )
    if not _commit_parents(repository_root, payload_commit):
        return
    for relative_path in _changed_paths(repository_root, payload_commit):
        if (
            relative_path in descriptor_paths
            or PurePosixPath(relative_path).parts[0] == CONTROL_DIRECTORY
        ):
            raise VerificationError(
                "VERIFY_COMMIT_TOPOLOGY_INVALID",
                f"the payload commit also changes {relative_path}",
            )


def verify_structure(
    *,
    repository_root: Path,
    release_tag: str,
    expected_head: str | None = None,
) -> dict[str, object]:
    """Prove the released commit pair offline, from this clone alone."""

    release_version(release_tag)
    root = Path(repository_root).resolve()
    descriptor_commit = _resolve_commit(root, f"refs/tags/{release_tag}")
    parents = _commit_parents(root, descriptor_commit)
    if len(parents) != 1:
        raise VerificationError(
            "VERIFY_COMMIT_TOPOLOGY_INVALID",
            "the tagged commit must have exactly one parent",
        )
    payload_commit = parents[0]
    if expected_head is not None and expected_head != descriptor_commit:
        raise VerificationError(
            "VERIFY_HEAD_MISMATCH",
            f"{expected_head} is not the commit {release_tag} names",
        )

    ledger = read_ledger(root, descriptor_commit)
    assert_ledger_chain(ledger)
    if release_tag not in ledger:
        raise VerificationError(
            "VERIFY_LEDGER_MISSING", f"the ledger has no record for {release_tag}"
        )
    record = ledger[release_tag]
    highest_tag = max(ledger, key=release_version)
    if highest_tag != release_tag:
        raise VerificationError(
            "VERIFY_LEDGER_NOT_HEAD",
            f"{highest_tag} is recorded above the release being verified",
        )
    if record["payload_commit"] != payload_commit:
        raise VerificationError(
            "VERIFY_PAYLOAD_COMMIT_MISMATCH",
            f"{release_tag} records a payload commit that is not {release_tag}^",
        )
    deployment = _parse_record(
        _read_blob(root, descriptor_commit, CURRENT_DEPLOYMENT_PATH),
        CURRENT_DEPLOYMENT_PATH,
    )
    if deployment != record:
        raise VerificationError(
            "VERIFY_DEPLOYMENT_RECORD_STALE",
            f"{CURRENT_DEPLOYMENT_PATH} is not the ledger record for {release_tag}",
        )

    descriptor_paths = frozenset(str(path) for path in record["descriptor_paths"])
    recorded_digests = {
        str(key): str(value)
        for key, value in dict(record["payload_path_sha256"]).items()
    }
    published_payload = {
        relative_path: _read_blob(root, payload_commit, relative_path)
        for relative_path in _read_tree_paths(root, payload_commit)
        if relative_path not in descriptor_paths
        and PurePosixPath(relative_path).parts[0] != CONTROL_DIRECTORY
    }
    actual_digests = {
        relative_path: hashlib.sha256(content).hexdigest()
        for relative_path, content in published_payload.items()
    }
    if actual_digests != recorded_digests:
        differing = sorted(
            set(actual_digests).symmetric_difference(recorded_digests)
            or {
                relative_path
                for relative_path, digest in actual_digests.items()
                if recorded_digests.get(relative_path) != digest
            }
        )
        raise VerificationError(
            "VERIFY_PAYLOAD_DRIFT",
            f"the payload commit does not match the ledger: {','.join(differing[:5])}",
        )
    if payload_digest(published_payload) != record["payload_sha256"]:
        raise VerificationError(
            "VERIFY_PAYLOAD_DRIFT",
            "the payload digest does not match the ledger",
        )

    verify_published_manifest(
        root, descriptor_commit, record, frozenset(published_payload)
    )

    published_descriptors = {
        relative_path: _read_blob(root, descriptor_commit, relative_path)
        for relative_path in sorted(descriptor_paths)
    }
    if payload_digest(published_descriptors) != record["descriptor_sha256"]:
        raise VerificationError(
            "VERIFY_DESCRIPTOR_DRIFT",
            "the descriptor digest does not match the ledger",
        )
    payload_paths = frozenset(published_payload)
    for relative_path, descriptor in published_descriptors.items():
        _assert_descriptor_names_payload_commit(
            descriptor,
            payload_commit=payload_commit,
            payload_paths=payload_paths,
            label=relative_path,
        )
    _assert_path_classes(
        root,
        payload_commit=payload_commit,
        descriptor_commit=descriptor_commit,
        descriptor_paths=descriptor_paths,
    )
    return {
        "descriptor_commit": descriptor_commit,
        "payload_commit": payload_commit,
        "release_tag": release_tag,
    }


def _read_public_json(api_url: str, description: str) -> dict[str, object]:
    """Read public GitHub metadata anonymously, with no credential."""

    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "luke-skills-release-verifier",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            parsed = json.load(response)
    except (
        OSError,
        TimeoutError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as error:
        raise VerificationError(
            "VERIFY_RELEASE_EVIDENCE_UNAVAILABLE",
            f"cannot read {description}: {error}",
        ) from error
    if not isinstance(parsed, dict):
        raise VerificationError(
            "VERIFY_RELEASE_EVIDENCE_UNAVAILABLE",
            f"{description} is not the expected object",
        )
    return parsed


def github_release_evidence(release_tag: str) -> dict[str, object]:
    return _read_public_json(
        f"https://api.github.com/repos/{PUBLIC_REPOSITORY}/releases/tags/{release_tag}",
        f"the published release for {release_tag}",
    )


def github_tag_evidence(release_tag: str) -> dict[str, object]:
    return _read_public_json(
        f"https://api.github.com/repos/{PUBLIC_REPOSITORY}/git/ref/tags/{release_tag}",
        f"the tag reference for {release_tag}",
    )


def verify_release_evidence(
    *,
    release_tag: str,
    descriptor_commit: str,
    release_resolver: Callable[[str], dict[str, object]] = github_release_evidence,
    tag_resolver: Callable[[str], dict[str, object]] = github_tag_evidence,
) -> dict[str, object]:
    """Prove a published, immutable release pins the descriptor commit.

    Missing evidence and contradicted evidence are reported as different
    failures on purpose: the first says the release is not provable yet, the
    second says the published state disagrees with this clone.
    """

    release_version(release_tag)
    release = release_resolver(release_tag)
    if (
        release.get("draft") is not False
        or release.get("prerelease") is not False
        or release.get("tag_name") != release_tag
    ):
        raise VerificationError(
            "VERIFY_RELEASE_NOT_PUBLISHED",
            f"{release_tag} has no published, non-draft, non-prerelease release",
        )
    if release.get("immutable") is not True:
        raise VerificationError(
            "VERIFY_RELEASE_NOT_IMMUTABLE",
            f"{release_tag} is not attested as an immutable release",
        )
    tag = tag_resolver(release_tag)
    tag_object = tag.get("object")
    if not isinstance(tag_object, dict):
        raise VerificationError(
            "VERIFY_RELEASE_EVIDENCE_UNAVAILABLE",
            f"the tag reference for {release_tag} names no object",
        )
    # A release tag points straight at the descriptor commit. A tag object here
    # means the reference was rebuilt after publication, which is a different
    # fact from pointing at the wrong commit and deserves its own diagnostic.
    if tag_object.get("type") != "commit":
        raise VerificationError(
            "VERIFY_RELEASE_TAG_NOT_A_COMMIT",
            f"{release_tag} does not point directly at a commit",
        )
    if tag_object.get("sha") != descriptor_commit:
        raise VerificationError(
            "VERIFY_RELEASE_TAG_RETARGETED",
            f"{release_tag} does not resolve to the verified commit",
        )
    return {
        "descriptor_commit": descriptor_commit,
        "immutable": True,
        "release_tag": release_tag,
    }


def _release_tag_from_deployment(repository_root: Path) -> str:
    deployment = Path(repository_root) / CURRENT_DEPLOYMENT_PATH
    try:
        record = json.loads(deployment.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(
            "VERIFY_DEPLOYMENT_RECORD_MISSING",
            f"cannot read {CURRENT_DEPLOYMENT_PATH}: {error}",
        ) from error
    release_tag = record.get("release_tag") if isinstance(record, dict) else None
    if not isinstance(release_tag, str):
        raise VerificationError(
            "VERIFY_DEPLOYMENT_RECORD_MISSING",
            f"{CURRENT_DEPLOYMENT_PATH} records no release tag",
        )
    return release_tag


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a published Luke catalog release from this repository."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("structure", "release"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--repository-root", type=Path, default=Path("."))
        subparser.add_argument("--release-tag")
        if command == "structure":
            subparser.add_argument("--expect-head")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        release_tag = arguments.release_tag or _release_tag_from_deployment(
            arguments.repository_root
        )
        if arguments.command == "structure":
            proven = verify_structure(
                repository_root=arguments.repository_root,
                release_tag=release_tag,
                expected_head=arguments.expect_head,
            )
            print(
                "verified release structure: "
                f"{proven['release_tag']} {proven['payload_commit']} -> "
                f"{proven['descriptor_commit']}"
            )
        else:
            proven = verify_structure(
                repository_root=arguments.repository_root,
                release_tag=release_tag,
            )
            verify_release_evidence(
                release_tag=release_tag,
                descriptor_commit=str(proven["descriptor_commit"]),
            )
            print(
                "verified immutable release: "
                f"{release_tag} @ {proven['descriptor_commit']}"
            )
        return 0
    except VerificationError as error:
        print(error.render(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
