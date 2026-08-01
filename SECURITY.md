# Security policy

## Private-reporting availability gate

The public catalog must not launch until operators have enabled GitHub private
vulnerability reporting for `thinkingoracle/luke-skills`, verified that
maintainer notifications arrive, and retained evidence of that check. This
policy describes the required route. Its presence does not prove that the
repository setting or notifications are live.

When the repository Security area shows **Report a vulnerability** and the
route has been verified, use that private path for suspected catalog security
issues. It is the only supported reporting channel for vulnerability details.

If **Report a vulnerability** is not visible, do not post sensitive details
publicly. Do not use a proposal, issue, pull request, discussion, conduct
channel, or unrelated repository as a substitute. The repository is not ready
for public security intake until operators restore and verify the private path.

## Include useful evidence

When possible, include:

- the affected skill ID, version, commit-pinned source URL, and content
  SHA-256;
- the affected catalog release tag and public artifact path;
- a concise impact description and the authority or data boundary involved;
- reproducible steps or a minimal proof without secrets or personal data;
- whether the issue affects source, publication provenance, validation, or
  local activation; and
- any known safe workaround.

Do not include credentials, tokens, private user data, copied browser sessions,
or unrelated sensitive material.

## Maintainer handling

Maintainers evaluate the report against the exact affected bytes and preserve
the proposal, review, release, commit, tree, and hash provenance needed for an
audit. Depending on verified impact, they may hold publication, remove release
eligibility, prepare corrected versioned content, or publish an exact-hash
revocation for clients that support verified revocation refresh.

A correction never reuses an existing version with different bytes, silently
substitutes content, or grants local trust. Known-good revisions remain
distinguishable from affected hashes.

Coordination and disclosure stay in the private GitHub advisory until
maintainers and the reporter agree that public disclosure is appropriate. This
project does not publish a response or resolution deadline without measured
capacity and an operator-approved service commitment.

## Conduct reports are separate

Private vulnerability reporting is not a conduct-reporting route. Conduct
concerns go to the Luke Support desk named in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), which is a different queue with its
own responder assignment, so a report about one person is never handled only by
that person.

Do not use this vulnerability channel for a conduct concern, and do not use a
conduct report for a suspected vulnerability.
