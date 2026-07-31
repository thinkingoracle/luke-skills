# Contributing a Luke skill

Thank you for proposing a useful Luke capability. First-time contributors are
welcome. This guide takes one read-only public-information idea from eligibility
through an exact two-file proposal. It does not create a catalog release,
install a skill, or grant runtime trust.

This project does not promise a review time. The public proposal issue is the
readable record of current state. If exact bytes are later released, their
public review record binds the final disposition to the proposal, version, and
content hash.

## 1. Check V1 eligibility

A V1 skill must:

- solve a concrete user need by reading public information and reporting a
  result;
- use Luke schema version 1;
- declare every public host and the data it reads;
- require no authentication and handle no credential, browser session, private
  endpoint, or local file;
- declare a read-only mutation boundary;
- contain one inert, UTF-8 `SKILL.md` install payload;
- include positive-routing, negative-routing, failure, and redaction evaluation
  evidence; and
- have clear provenance and Apache-2.0-compatible licensing.

A V1 skill must not send, purchase, edit, upload, delete, install, execute
payloads, or otherwise mutate an external system. It must not include scripts,
executables, dependencies, symlinks, hidden payloads, installers, secrets, or
private-network hosts.

An idea outside this boundary may still be valuable, but it is not eligible for
V1. Maintainers cannot make it eligible by weakening or omitting its authority.

## 2. Acquire one exact catalog tree

The creator depends on the complete repository layout. Do not download or copy
only `creator/create-luke-skill/`, and do not use a floating `main` checkout as
the governed contribution contract.

After the public Releases page shows a non-draft, non-prerelease
`luke-skills-vX.Y.Z` release, replace `<exact-release-tag>` below with that
exact tag and clone the complete repository:

```bash
export LUKE_SKILLS_RELEASE_TAG="<exact-release-tag>"
git clone \
  --branch "$LUKE_SKILLS_RELEASE_TAG" \
  --depth 1 \
  https://github.com/thinkingoracle/luke-skills.git
cd luke-skills
test "$(git describe --tags --exact-match HEAD)" = "$LUKE_SKILLS_RELEASE_TAG"
```

Do not substitute `main`, another tag family, a draft, or a prerelease. If the
governed release does not exist or the repository is not anonymously readable,
the public contribution path is not open yet.

During pre-publication operator acceptance, reviewers may instead start from
the exact inert candidate tree supplied for that review. That rehearsal proves
the candidate documentation and tooling work together. It does not prove that
public acquisition, release, or publication is live.

## 3. Create and validate the exact two-file bundle

From the catalog repository root, confirm that `python3` is CPython 3.11 or
later. If needed, install a currently supported Python from
[python.org](https://www.python.org/downloads/) or your operating system's
package manager.

The walkthrough uses the fictional slug
`northstar-planetarium-hours-read`, which is not a bundled or public V1 skill in
this candidate. Before proposing a different slug, search the published
`skills/` and `evals/` paths and public proposal issues. Skill IDs are never
reused.

Run this block from the catalog repository root:

<!-- clean-room-walkthrough:start -->
```bash
export PROPOSAL_ROOT="${TMPDIR:-/tmp}/northstar-planetarium-hours-read-proposal"

python3 --version

python3 creator/create-luke-skill/scripts/new_skill.py \
  --output-root "$PROPOSAL_ROOT" \
  --slug northstar-planetarium-hours-read \
  --description "Read public opening hours for a fictional planetarium." \
  --host planetarium.example.org \
  --data-read "public opening dates, hours, and closure notices" \
  --result-lands-in "Luke's response to the requesting user" \
  --positive-example "When is the Northstar Planetarium open this weekend?" \
  --negative-example "Buy two planetarium tickets for Saturday." \
  --failure-example "The public hours page is unavailable." \
  --redaction-example "The page unexpectedly shows a visitor account token."

python3 creator/create-luke-skill/scripts/validate.py \
  --catalog-root "$PROPOSAL_ROOT" \
  --allow-draft-provenance
```
<!-- clean-room-walkthrough:end -->

Successful creation produces exactly:

```text
<proposal-root>/
├── skills/northstar-planetarium-hours-read/SKILL.md
└── evals/northstar-planetarium-hours-read.json
```

The final validator line is:

```text
validated 1 Luke catalog skill(s)
```

The evaluation fixture must use the same `browser-skill:<slug>` ID as
`SKILL.md`, use a version that follows the documented versioning rules, and
contain at least one case in each category:

- `positive_routing`, where Luke should select the skill;
- `negative_routing`, where Luke should not select the skill;
- `failure`, where the public source is unavailable or outside the boundary;
  and
- `redaction`, where unexpected sensitive or private material must be omitted.

Each case needs a stable `id`, an `input`, and an observable `expected` result.
The complete field shape is documented in
[`creator/create-luke-skill/references/luke-schema-v1.md`](creator/create-luke-skill/references/luke-schema-v1.md).
Draft creator output keeps `proposal_url` and `review_decision` null and
`validation_checks` empty. Draft validation is deliberately non-release-
eligible and cannot emit an available descriptor.

Inspect both generated files. Replace generic routing and failure language with
evidence-backed detail while preserving the read-only boundary, then run the
same validator command again. Do not hand-edit generated catalog indexes or
commit-pinned artifact metadata.

The creator never overwrites an existing proposal artifact. A named
`CREATOR_*` diagnostic explains an unsupported runtime, invalid input, busy
output root, write failure, validation failure, or incomplete rollback. Follow
that diagnostic. Do not treat a partial directory as a valid proposal.

## 4. Submit both complete files in one public issue

Open the **Propose a Luke skill** issue form in
[`thinkingoracle/luke-skills`](https://github.com/thinkingoracle/luke-skills/issues/new/choose).
If that page is unavailable, public intake is not open. Do not use a source pull
request, discussion, archive, or unrelated public issue as a substitute.

The form requires both complete files:

1. paste `skills/<slug>/SKILL.md` into the rendered Markdown field; and
2. paste `evals/<slug>.json` into the rendered JSON field.

Use UTF-8, LF line endings, and exactly one final newline in each file.
Immutable public links may supplement the inline files, but they never replace
them. A maintainer posts the canonical diff and SHA-256 for contributor
confirmation before source review can rely on the submitted bytes.

The form also asks for:

- the user and their need;
- public hosts and authentication assumptions;
- data read and the read-only mutation boundary;
- expected behavior and realistic examples;
- local evaluation evidence;
- provenance; and
- license and notice information.

Do not put secrets, credentials, private data, browser sessions, or
undisclosed vulnerability details in the issue.

The issue is intake only. It cannot accept source, merge code, publish catalog
bytes, install a skill, or grant local trust.

## 5. Follow status without private source access

Maintainers post status as comments on the public proposal issue. Labels are
optional and are not the status contract. A status comment uses this shape:

```text
Proposal status: <received | boundary review | source review | held |
                  release-eligible | published | outside V1>
Skill ID: <browser-skill:slug>
Candidate version: <version or not assigned>
Candidate content SHA-256: <64 lowercase hex characters or not assigned>
Decision: <factual disposition or pending>
Public review record: <public link or not released>
Next gate: <factual next gate or none>
```

The comment reports only events that have happened. Editable issue text is
readable context, not immutable proof.

If the proposal fits V1, a maintainer creates one change against the canonical
catalog source. That maintainer-controlled change is the only source-review
lifecycle:

- it links the public proposal issue;
- it contains the exact skill and evaluation bytes under review;
- repository validation and deterministic generation run there;
- code owners review the full source, authority, evidence, provenance, and
  license; and
- all review iteration and landing happen there.

Contributors answer questions and follow progress on the public proposal issue.
They do not need access to the maintainer source repository. Released
descriptors link an exact-hash review record through a full-commit public raw
URL; the public issue remains editable intake context rather than immutable
proof. A direct source pull request to the public distribution repository is
not an alternative review path.

## 6. Understand merge, release, availability, and trust

Landing the reviewed change on protected Luke `main` makes the exact bytes
**release-eligible**. It does not publish them. Accepted changes may wait for a
later catalog release.

Only a maintainer-published, non-draft, non-prerelease
`luke-skills-vX.Y.Z` release at a protected Luke-main commit selects the exact
tree for public distribution. An ordinary commit, source-review merge, app
release, another tag family, draft, or prerelease does not publish catalog
content.

Publication and public availability still do not make a skill trusted or
active. Each Luke user reviews and trusts the exact
`{skill_id, content_sha256}` pair locally. Changed bytes receive a new hash and
never inherit an earlier decision.

The source candidate descriptor remains `install_state: held` until a
maintainer explicitly regenerates it as `available` after anonymous checks
resolve both the public proposal and the exact commit-pinned review record.
That reviewed source change is only release-eligible. A later governed release
must still select and publish it before Luke can discover the exact bytes.
`validation_status: validated` means only that the exact bytes passed the
named bounded validators. `trust_state: needs_review` is Luke's local posture,
not a maintainer verdict or a trust grant.

## 7. Maintain accepted work

Corrections and authority changes start with a new proposal issue and a new
maintainer-controlled source review. Do not replace bytes under an existing
version.

- Patch versions cover corrections that do not expand authority.
- Minor versions may add supported public hosts or variants without mutation
  authority.
- Major versions cover purpose, authentication, capability, data-boundary, or
  mutation-boundary changes.

Deprecation should name a replacement when one exists. A security revocation
names the exact affected hash and must not silently substitute different
content.

## Licensing

The catalog is licensed under Apache License 2.0. By contributing, you
represent that you have the right to submit the material under compatible
terms. Third-party material must preserve all required copyright, attribution,
`NOTICE`, and other license notices. Put required notices beside the
contributed material or in the repository notice location selected by
maintainers. Do not copy content whose terms are unknown or incompatible.

## Security and conduct reports

Do not disclose a suspected vulnerability in a public proposal or issue. Follow
the private-reporting requirements in [SECURITY.md](SECURITY.md). If the
verified private vulnerability path is unavailable, do not post sensitive
details publicly.

The vulnerability path is not a conduct-reporting route. This candidate does
not invent a conduct form or contact. Public community intake remains held
until operators verify the separate conduct prerequisites described in the
[README](README.md).
