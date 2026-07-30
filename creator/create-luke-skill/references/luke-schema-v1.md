# Luke catalog schema v1

Use this reference when editing creator output or diagnosing validator results.

## Eligibility

- One inert UTF-8 `skills/<slug>/SKILL.md` is the complete install payload.
- The slug is lowercase kebab case. `name` equals the slug and `skill_id`
  equals `browser-skill:<slug>`.
- Every routing rule declares `require_auth: false`, one public DNS host, and
  `mutation_boundary: read_only`.
- Every step uses an allowed read-only capability target and
  `mutation_boundary: read_only`.
- Catalog v1 does not accept scripts, installers, symlinks, executable payloads,
  hidden payloads, credentials, private-network hosts, local files, or external
  mutations.
- The body includes purpose, reads, never, lands in, steps, success criteria,
  failure behavior, and redaction guidance.

## Required frontmatter

```yaml
---
name: public-release-notes-read
skill_id: browser-skill:public-release-notes-read
description: "Read public release notes for a named project."
when_to_use:
  - host: example.com
    path_prefix: /
    intent_keywords: [release, notes, version]
    require_auth: false
    mutation_boundary: read_only
steps:
  - caption: "Read the requested public information"
    capability_target: web_search
    mutation_boundary: read_only
adapter_preferences:
  preferred: browserbase
  fallback: owned_browser
  declined: []
schema_version: 1
---
```

Allowed contributor capability targets are `web_search`, `fetch_url`, and
`delegate_web_action`. Connector and local-sidecar targets are reserved for
byte-faithful bundled mirrors.

## Required evaluation fixture

`evals/<slug>.json` records catalog metadata plus at least one case in each
category:

- `positive_routing`: the skill should be selected;
- `negative_routing`: the skill should not be selected;
- `failure`: the skill fails safely and explains the limitation;
- `redaction`: the skill omits sensitive or unexpected private data.

Each case has a stable `id`, an `input`, and an observable `expected` result.
Draft creator output uses null `proposal_url` and `review_decision` plus an
empty `validation_checks` array. Normal catalog validation requires the exact
hash-named review record and its machine-readable authority front matter; only
creator validation uses `--allow-draft-provenance`. Draft validation cannot be
reused to emit an available descriptor.

Released descriptors use `review_record_url`, pinned to a full 40-character
public payload commit. The legacy private-source `review_url` field is not
current release evidence. `validation_status: validated` records only the
named bounded validator result, `install_state: held` remains undiscoverable,
and neither field grants local trust.

## Versioning

- Patch: prose, selector, redaction, or reliability correction without changed
  task authority.
- Minor: a new supported public host or variant without mutation authority.
- Major: changed purpose, authentication assumption, capability, data
  boundary, or mutation boundary.

Changing bytes without changing the version is rejected against a prior index.
IDs are never reused. Curation never activates a skill; Luke trust binds to the
exact content SHA-256.
