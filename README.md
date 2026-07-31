# Luke skills catalog

Luke catalog skills give Luke a bounded recipe for answering a public
information request. A V1 skill declares when it applies, which public host it
may read, what it returns, and where it must stop. It cannot sign in, handle
credentials, change an external system, or install executable code.

For example, a release-notes skill may read a project's public release page
and summarize a named version. The skill does not gain access to private pages
and cannot publish, purchase, register, send, edit, upload, or delete anything.

Curated does not mean trusted. Repository review records exact bytes, declared
boundaries, evidence, checks, and a disposition for one revision. It does not
prove quality or safety, and it cannot activate a skill in Luke. A Luke user
separately reviews and trusts the exact content hash on their machine.

## Start here

- To decide whether an idea fits V1 and create a proposal bundle, follow
  [CONTRIBUTING.md](CONTRIBUTING.md).
- To understand exact-byte trust, updates, and revocation, read
  [TRUST.md](TRUST.md).
- To report a suspected vulnerability without publishing sensitive details,
  read [SECURITY.md](SECURITY.md).
- To inspect the Apache License 2.0 terms and notice rules, read
  [LICENSE](LICENSE).

## Source and availability

Luke maintainers control the editable catalog source and its only source-review
lifecycle. The
[`thinkingoracle/luke-skills`](https://github.com/thinkingoracle/luke-skills)
repository is the designated proposal-intake and one-way distribution surface.
It serves as a public surface only when it is anonymously readable and the
governed release conditions below are satisfied. It is not a second editable
source tree or an alternative source-review workflow.

Files in a checkout do not prove that a catalog revision is published or
available to Luke. Publication requires a non-draft, non-prerelease
`luke-skills-vX.Y.Z` release whose protected-main tag selects the exact public
tree. If no such release exists, treat the checked-in bytes as staged
candidates only. An ordinary commit, source-review merge, app release, draft,
prerelease, or different tag family is not catalog publication.

## V1 eligibility boundary

Catalog V1 accepts only:

- one inert, UTF-8 `SKILL.md` install payload per skill;
- Luke schema version 1;
- read-only behavior against declared public hosts;
- no authentication or credential handling;
- no send, purchase, edit, upload, delete, install, or other external mutation;
- no scripts, executables, dependencies, symlinks, hidden payloads, or
  installers; and
- positive-routing, negative-routing, failure, and redaction evaluation
  evidence.

Ideas outside this boundary may still be useful. They are not V1-eligible and
must not be represented as release-ready content.

## Catalog words and lifecycle

These words describe bounded evidence and mechanical state. None is a quality
or safety verdict.

| Term | What it means and does not mean |
|---|---|
| **Curated** | Maintainers apply the catalog review process to one exact revision. Curation does not grant runtime trust or approve the skill for every context. |
| **Validated** | The submitted bytes passed the named mechanical checks at that revision. Validation does not prove quality, safety, factual accuracy, or future behavior. |
| **Proposed** | A public issue records the user need, boundaries, provenance, examples, and evidence. It is editable intake only. |
| **Reviewed** | Maintainer-controlled source review records a bounded decision for one exact source and evaluation bundle. The public issue carries readable status. |
| **Release-eligible** | The reviewed bytes have landed in the protected Luke `main` source tree. Landing does not publish them. |
| **Published** | A governed `luke-skills-vX.Y.Z` release selects the exact public tree for distribution. |
| **Available** | Exact bytes can be called available from this catalog only when a governed release selected them and their public artifact is retrievable. Availability does not install, trust, or activate them. |
| **Locally trusted** | A Luke user reviewed and trusted the exact installed `{skill_id, content_sha256}` pair. Publication does not grant this state. |

No earlier state implies a later one. A proposal cannot publish content, a
merge is not publication, and publication is not local activation.

## Proposal, review, release, and trust

1. A contributor opens the structured proposal issue in the public catalog
   repository.
2. If the proposal fits V1, a maintainer starts the only source-review change
   in the maintainer-controlled source repository.
3. Automated checks and code-owner review evaluate the exact skill, evaluation
   evidence, provenance, license, and declared boundary.
4. Landing on protected Luke `main` makes those bytes release-eligible.
5. A later governed catalog release may select an exact public tree for
   one-way publication.
6. Luke verifies published bytes, and the local user makes the separate trust
   decision.

Direct edits or source pull requests against the distribution branch cannot
replace this lifecycle.

## Public status and provenance

The public proposal issue is the readable status path. Maintainers post the
current state, decision, candidate version and hash, and next gate there.
Labels may summarize a state, but readers do not need a label or access to the
maintainer source repository to understand it.

Issue text is editable intake evidence, not immutable review proof. A governed
release includes a public review record keyed by skill, version, and exact
content hash. That record names the public proposal, bounded checks, and
disposition without granting trust. The current
[`public-release-notes-read` candidate record](review-records/public-release-notes-read/0.1.0/ac683e64883a288929c59fabd8f29136154c0e4ff3ee47ab6f60727a350af10c.md)
binds the public proposal, bounded checks, decision, and exact content hash.
The first governed release published that revision as `held`, so it remained
undiscoverable and un-installable. A later reviewed source change and higher
governed release may promote the descriptor to `available` only after both
public evidence links resolve anonymously.

## Security and conduct readiness

Vulnerability details do not belong in a proposal or public issue.
[SECURITY.md](SECURITY.md) explains the private-reporting requirement and what
to do when the required GitHub path is unavailable. The existence of this
policy file is not evidence that repository settings or maintainer
notifications have been verified.

Security reporting is not a conduct-reporting channel. A public community
launch remains held until the exact public tree includes a Code of Conduct and
operators verify a monitored private conduct route, a named enforcement owner,
a distinct alternate recipient, and durable evidence. No conduct form,
contact, response deadline, or enforcement promise is invented here.

## Luke 2.0 pilot boundary

Unmodified Luke 2.0 may manually import an eligible, commit-pinned **new skill
ID** into Needs Review. The five mirrored bundled IDs are canonical internal
fixtures and are not safe re-import targets on unmodified Luke 2.0. That client
does not yet isolate bundled trust from different remote bytes sharing an ID.
General catalog discovery and safe update handling require later
catalog-enablement work.
