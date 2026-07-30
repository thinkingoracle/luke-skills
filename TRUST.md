# Trust model

The Luke skills catalog is curated supply, not activation authority.

Repository review records declared format, read-only boundaries, provenance,
evaluation evidence, checks performed, and the disposition of one exact
revision. It is not a quality or safety verdict, and it does not activate that
revision for any Luke user.

## Trust binds to exact bytes

Luke's catalog trust identity is:

```text
skill_id + content_sha256
```

A local trust decision applies only to that pair. A familiar ID, author,
maintainer, source repository, popularity signal, scanner result, catalog
badge, or earlier accepted version cannot transfer trust to different bytes.

The content hash covers the exact inert UTF-8 `SKILL.md` artifact. Generated
metadata and a commit-pinned source URL may describe that artifact, but neither
can substitute for it. Luke must verify that fetched bytes match the declared
SHA-256 before parsing, persistence, review, or activation.

## What public terms prove

| Term | Bounded meaning |
|---|---|
| **Curated** | Maintainers applied the catalog process to one exact revision. It does not mean universally suitable and does not prove quality or safety in every context. It also does not make the bytes trusted or active. |
| **Validated** | The named mechanical checks passed for those bytes. It does not predict future source behavior, prove factual accuracy, or grant trust. |
| **Reviewed** | Maintainer-controlled source review recorded a bounded decision for the exact source and evaluation evidence. It is not a general endorsement. |
| **Available** | A governed catalog release selected exact, retrievable public bytes. A file merely present in source is not available by this definition, and availability does not install or activate it. |

These terms report process and state. They are never substitutes for the
user's exact-byte decision.

## What lifecycle states do and do not mean

- **Proposed** means editable public intake exists. The issue cannot publish or
  activate content.
- **Reviewed** means maintainer-controlled source review recorded a bounded
  decision for exact source and evidence. Contributors read current status on
  the public proposal issue.
- **Release-eligible** means the reviewed bytes landed on protected Luke
  `main`. It does not mean they were published.
- **Published** means a valid non-draft, non-prerelease
  `luke-skills-vX.Y.Z` release selected that exact protected-main tree.
- **Locally trusted** means a Luke user reviewed and trusted the exact verified
  content hash.

Only the last state grants local activation, and only on that user's machine.
No label, issue comment, source merge, release, or review record grants it.

The public proposal issue is readable, editable status context. For a released
revision, the public review record binds that proposal, version, bounded
checks, decision, and exact content hash inside the selected public payload.
Neither the issue nor the record grants local trust. The current presentation
record is not catalog machine authority and does not make an unreleased
candidate available.

## Updates

Different bytes never inherit an earlier trust decision, even when the skill
ID or maintainer is unchanged. A changed revision must use an honest version, a
new hash, and fresh repository and local review.

Catalog-enabled Luke keeps a known-good trusted revision active while a changed
candidate waits in Needs Review. Rejecting or failing to verify the candidate
must not damage the known-good copy. User edits are user-owned and refresh must
not overwrite them.

## Bundled Luke 2.0 skills

The five mirrored bundled IDs are canonical internal source fixtures. They are
not safe re-import targets on unmodified Luke 2.0. That client associates
bundled trust too broadly by ID, so different remote bytes could inherit the
embedded artifact's decision.

The V1 manual-import pilot is limited to an eligible, commit-pinned **new skill
ID**. Later client work must bind bundled trust to the exact embedded artifact
before remote same-ID content is offered safely.

## Revocation

A revocation identifies an exact content hash and preserves provenance and
evidence. It does not silently replace the affected revision with different
bytes. After a verified catalog refresh, a catalog-enabled client can stop
matching the revoked hash and show the source and reason. A feed failure cannot
erase the last verified catalog or replace trusted content with unverified
bytes.

Catalog maintainers can remove release eligibility and publish exact-hash
incident information. They cannot silently reach into a user's machine, grant
trust, or transfer a trust decision to another revision.

`revoked_hashes` is published in the same verified feed as the artifact
declaration. It is an operational containment signal from that source, not an
independently signed revocation authority. A compromised feed could omit a
revocation before a client observes it. Catalog-enabled Luke therefore keeps
an observed exact-hash denial sticky across later feed omission, refresh
failure, cache fallback, offline relaunch, and same-ID updates. Revocation
never grants replacement trust, and there is no automatic un-revoke path.

Catalog-enabled Luke stores an independent monotonic observation-count watermark
beside the revocation ledger. A valid older ledger can create or advance that
watermark, but once the watermark is nonzero a missing, truncated, rolled-back,
or corrupt ledger fails closed rather than restoring matching or trust. Luke
never reconstructs lost observations from a later feed because that feed may
omit a previously observed denial.

## Characters a proposal may contain

Some characters are invisible, and some change the direction text is drawn in.
Together they let a file read one way to the person reviewing it and mean
something else to the software running it. A reviewer can read a line
carefully, approve exactly what they saw, and still have approved something
different.

Proposals are checked against a named, versioned character profile called
`luke-skill-unicode-v1` before validation continues. That check refuses:

- the byte order mark, an invisible character some editors add at the start of
  a file;
- invisible marks that change or override text direction;
- control characters, apart from the tab and the line break.

It does not refuse ordinary writing. Every written language is welcome.
Accents, combining marks, emoji, and the joining characters that scripts like
Persian and Hindi need are all accepted, because a check that refuses real
languages is a check people work around.

When a proposal is refused, the message names the exact character and the line
and column it sits on, and the file is left exactly as it was submitted.
Nothing is quietly stripped, replaced, or rewritten, so the content hash always
belongs to the bytes that were actually sent.

The profile is versioned on purpose. Loosening what it accepts means publishing
a new profile that can be reviewed on its own, never quietly editing this one.

Like every other check here, this one reports what was inspected. It does not
make bytes trusted, safe, or active.

## Limits of review

Automated validation and scanning compare declared policy, payload structure,
and known patterns. Human maintenance records its assessment of purpose,
evidence, and provenance. Neither proves quality or safety in every context.
Luke preserves the final local decision so the user can inspect the exact
revision and its declared authority before use.
