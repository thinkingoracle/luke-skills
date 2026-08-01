# Contributing a Luke skill

Thank you for proposing a useful Luke capability. First-time contributors are
welcome. This guide takes one read-only public-information idea from eligibility
through an exact two-file proposal. It does not create a catalog release,
install a skill, or grant runtime trust.

This project does not promise a review time. The public proposal issue is the
readable record of current state. If exact bytes are later released, their
public review record binds the final disposition to the proposal, version, and
content hash.

## Give this to your coding agent

If you use Claude Code, Codex, Cursor, or anything similar, paste this and
replace the idea line. It does the rest of this document for you, and asks you
before it files anything.

<!-- agent-onramp-prompt:start -->
```
I want to add a skill to the public Luke skills catalog at
https://github.com/thinkingoracle/luke-skills

My idea: <one sentence: who needs what public information, from which
public website>

Do this:

1. Clone at the exact release tag below, never main. Use this tag
   literally. Do not pick a different one off the Releases page, which
   currently lists two and marks the older one Latest.

     export LUKE_SKILLS_RELEASE_TAG="luke-skills-v0.1.1"
     git clone --branch "$LUKE_SKILLS_RELEASE_TAG" --depth 1 \
       https://github.com/thinkingoracle/luke-skills.git
     cd luke-skills
     git describe --tags --exact-match HEAD   # must print that tag

2. Read CONTRIBUTING.md there. It is the authority on what a skill may
   do and what the bundle must contain, and it wins over this message on
   both. It is not the authority on how to submit: it describes the
   issue form, and this block files the same issue with gh. Either way
   the result is one public proposal issue and never a pull request.

3. Check my idea first. If it needs a login, a credential, a private
   page, or changes anything in the world, stop and tell me. It is not
   eligible yet, and there is a better place to put it.

4. Build both files with the creator, then run the validator until it
   passes clean. The validator needs --allow-draft-provenance or it
   rejects a draft proposal. Both commands are in CONTRIBUTING.md:

     python3 creator/create-luke-skill/scripts/new_skill.py \
       --output-root /tmp/my-proposal \
       --slug your-skill-slug \
       --description "one line saying what it reads" \
       --host the.public.host.it.reads \
       --data-read "what it reads from that page" \
       --result-lands-in "Luke's response to the requesting user" \
       --positive-example "a request that should use it" \
       --negative-example "a similar request that should not" \
       --failure-example "what unavailable looks like" \
       --redaction-example "sensitive material it must omit"
     python3 creator/create-luke-skill/scripts/validate.py \
       --catalog-root /tmp/my-proposal --allow-draft-provenance

   Replace those values with mine. Do not write them inside angle
   brackets: an unquoted < is a shell redirect, so a command with
   <placeholders> in it fails before python ever runs.

   Keep going until it prints: validated 1 Luke catalog skill(s)
   Every failure has a named CREATOR_ or CATALOG_ code. Read it; it
   says what to fix.

5. Write the whole submission yourself, as markdown, using these
   headings in this order: Proposed skill name and ID; User and need;
   Public hosts; Authentication boundary; Data boundary; Mutation
   boundary; Expected behavior and result; Realistic examples;
   Evaluation evidence; Provenance; License and notices; then both
   complete files in fenced blocks. You already know all of it because
   you wrote it. Do not ask me to retype any of it.

   Two of those take fixed wording, not your own. Authentication
   boundary is exactly "No authentication or credentials are required".
   Mutation boundary is exactly "Read-only, with no external mutation".
   If either is not true of my idea, it is not eligible; go back to
   step 3.

6. Two things you must not answer for me: where the material came from
   and under what licence, and whether it contains anything private.
   Ask me in plain language and use my words.

   Fence both files with a run of backticks LONGER than any run inside
   the file, and directly above each fence state its exact size and
   SHA-256, like this:

     `SKILL.md`, 1684 bytes, sha256 92884a8a...

   Get these from the files themselves:

     wc -c < skills/<slug>/SKILL.md
     shasum -a 256 skills/<slug>/SKILL.md

   This is not decoration. A fence that ends early truncates the file
   silently, and a truncated skill still passes every validator. The
   declared size and hash are what make that impossible to land.

   Then end the submission with this block, and only tick a box after I
   have actually said yes to it. These are legal and safety claims about
   me, not about the skill, and filing without them makes the submission
   incomplete even though the files will still validate:

     ### Contributor attestations

     - [ ] I have the right to submit this material under
           Apache-2.0-compatible terms and included all required notices.
     - [ ] I included no secret, credential, private user data, copied
           browser session, or undisclosed vulnerability detail.
     - [ ] I understand this issue is proposal intake only and cannot
           review, accept, publish, install, or activate the skill.
     - [ ] I understand maintainers control the only source-review
           lifecycle, public status stays on this issue, and each user
           separately trusts the exact content hash.

7. Show me the finished submission and ask whether to post it. If I say
   yes, file it yourself:

     gh issue create --repo thinkingoracle/luke-skills \
       --title "Propose skill: <slug>" --body-file <your-file>.md

   Then give me the link. If gh is not set up, say so and show me the
   block to paste instead.

8. Never post without asking me first. Never open a pull request and
   never push a branch to that repository.

9. Tell me what was unclear or what you had to guess.
```
<!-- agent-onramp-prompt:end -->

[`CONTRIBUTING_WITH_AN_AGENT.md`](CONTRIBUTING_WITH_AN_AGENT.md) carries the same
sequence for an agent that finds the tree without being handed the block.

The rest of this document is what that prompt is following. Read it if you want
to know why the boundaries are where they are, or if you would rather do it by
hand.

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

The vulnerability path is not a conduct-reporting route. Conduct concerns go to
the separate private route named in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), which reaches a different queue.
Neither channel is a substitute for the other.
