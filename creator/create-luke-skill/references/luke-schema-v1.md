# Luke catalog schema v1

Use this reference when editing creator output or diagnosing validator results.

## Eligibility

- One inert UTF-8 `skills/<slug>/SKILL.md` is the complete install payload.
- The slug is lowercase kebab case. `name` equals the slug and `skill_id`
  equals `browser-skill:<slug>`.
- Every routing rule declares `mutation_boundary: read_only`.
- `require_auth: true` is allowed only for a public-host-bound skill whose
  steps are all read-only `delegate_web_action`, whose adapter preference is
  `owned_browser` with no fallback, and whose declined adapters are exactly
  `browserbase`, `frontmost_local`, and `yutori`. The user signs in directly in
  Luke's isolated local profile; the artifact never contains credentials.
- A rule normally declares one public DNS `host`. It may omit `host` only when
  every executable step is read-only `web_search`; host-free `fetch_url`,
  `delegate_web_action`, connector, sidecar, authenticated, or mutating skills
  are rejected.
- Every `intent_keywords` array is non-empty. For a host-free rule it is also
  case-insensitively unique and bounded to at most 16 entries of at most 64
  characters each.
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

For a host-free public-search skill, omit both `host` and `path_prefix` from the
routing rule. Omission is not wildcard fetch authority: the artifact remains
limited to its declared `web_search` steps, and every public source used must be
identified in the result.

For an authenticated owned-browser read, every routing rule names a public
host and every step repeats one of those hosts:

```yaml
when_to_use:
  - host: open.spotify.com
    path_prefix: /
    intent_keywords: [spotify, playlists, trending]
    require_auth: true
    mutation_boundary: read_only
steps:
  - caption: "Read visible Spotify charts and trending playlists"
    capability_target: delegate_web_action
    host: open.spotify.com
    mutation_boundary: read_only
adapter_preferences:
  preferred: owned_browser
  declined: [browserbase, frontmost_local, yutori]
```

This route fails closed when Luke's owned browser is unavailable. It cannot use
Browserbase, a hosted fetch/search provider, or the user's everyday browser.
Eligibility does not bypass evaluation, human safety review, exact-hash Trust,
per-navigation approval, installation review, or activation.

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
  boundary, mutation boundary, or a change between host-bound and host-free
  routing.

Changing bytes without changing the version is rejected against a prior index.
IDs are never reused. Curation never activates a skill; Luke trust binds to the
exact content SHA-256.
