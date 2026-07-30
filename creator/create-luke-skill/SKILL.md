---
name: create-luke-skill
description: Create and validate a proposal bundle for a declarative, read-only Luke schema-v1 catalog skill. Use when a contributor wants to turn a public-information task into `skills/<slug>/SKILL.md` plus the required positive-routing, negative-routing, failure, and redaction evaluation fixture before opening a public proposal issue.
---

# Create a Luke catalog skill

Create proposal artifacts only. Do not publish, open a pull request, install the
skill, or imply that catalog curation grants runtime trust.

Use this creator only from the complete catalog repository tree. For a governed
public contribution, acquire that tree at an exact non-draft
`luke-skills-vX.Y.Z` release tag by following
[`CONTRIBUTING.md`](../../CONTRIBUTING.md). A standalone copy of this creator
directory and a floating `main` checkout are not the supported contribution
contract. Before a governed release exists, an exact candidate-tree rehearsal
does not prove that public acquisition or intake is live.

## Workflow

1. Confirm the requested task is read-only and uses a public host without
   authentication. Redirect scripts, installers, credentials, private hosts,
   local files, and external mutations out of catalog v1.
2. Collect:
   - a lowercase kebab-case slug;
   - a one-line purpose;
   - the public host;
   - the public data the skill reads;
   - where the answer lands;
   - one positive-routing, negative-routing, failure, and redaction example.
3. Read [references/luke-schema-v1.md](references/luke-schema-v1.md) before
   changing the generated contract or hand-authoring fields.
4. From the catalog repository root, confirm that `python3` is CPython 3.11 or
   later:

   ```bash
   python3 --version
   ```

   If it is older, install a currently supported Python from
   [python.org](https://www.python.org/downloads/) or your operating system's
   package manager, then confirm that `python3` resolves to that installation.
5. Run:

   ```bash
   export PROPOSAL_ROOT="${TMPDIR:-/tmp}/northstar-planetarium-hours-read-proposal"

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
   ```

6. Validate the complete proposal bundle with the same validator used by CI:

   ```bash
   python3 creator/create-luke-skill/scripts/validate.py \
     --catalog-root "$PROPOSAL_ROOT" \
     --allow-draft-provenance
   ```

7. Inspect both generated files. Replace generic routing and failure language
   with evidence-backed detail while preserving the read-only boundary, then
   validate again.
8. Paste the complete `SKILL.md` into the issue form's rendered Markdown field
   and the complete evaluation fixture into its rendered JSON field. Use UTF-8,
   LF line endings, and exactly one final newline in each file. Immutable public
   links may supplement, but never replace, the inline files. Explain that
   maintainers control the single source-review lifecycle, post readable status
   on the public issue, and use a later catalog release to control publication.
   The user still reviews and trusts the exact bytes locally.

## Output contract

Produce exactly:

```text
<output-root>/
├── skills/<slug>/SKILL.md
└── evals/<slug>.json
```

Keep proposal and review URLs null in this draft. Maintainers add verified
machine provenance during maintainer-controlled source review. If the exact
bytes are released, the public payload carries a review record while the
proposal issue remains the readable status path.

The creator never overwrites an existing proposal artifact. A failed write or
post-write validation returns a named `CREATOR_*` diagnostic and removes every
artifact and directory created by that run. If local permissions prevent
complete cleanup, `CREATOR_ROLLBACK_FAILED` names the remaining paths so a
partial bundle cannot be mistaken for successful output.

Only one creator may use an output root at a time. `CREATOR_OUTPUT_BUSY` means
another run holds that root's creator lock; wait for it to finish and retry.
After a crashed or interrupted run, first confirm that no creator is still
running, then remove only the stale lock directory named by the diagnostic.
The creator never reclaims or removes a lock it did not acquire.
