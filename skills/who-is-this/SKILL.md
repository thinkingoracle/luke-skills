---
name: who-is-this
skill_id: browser-skill:who-is-this
description: Background on who you are meeting, before you meet them
when_to_use:
  - intent_keywords: [who is, background on, before i meet, interview, research them, brief me on]
    require_auth: false
    mutation_boundary: read_only
steps:
  - caption: the public background, track record and recent work of
    capability_target: web_search
    mutation_boundary: read_only
  - caption: recent interviews, public statements and what they are working on now from
    capability_target: web_search
    mutation_boundary: read_only
parameters:
  - name: who
    current_value: the founder of Patagonia
    fill_rule: name the person, company or band and where you are meeting them
adapter_preferences:
  preferred: browserbase
  fallback: owned_browser
  declined: []
schema_version: 1
metadata:
  luke:
    tags: [research, meetings, interviews, prep, on-demand]
    related_skills: [browser-skill:explain-like-im-in]
platforms: [macos]
---
# Who is this

## Purpose
You are meeting them in a few hours. This is the public record: what they have
done, what they are working on now, and the one thing worth asking about that
nobody else will ask.

## Reads
- Search results for the public background, track record and recent work of the founder of Patagonia.
- Search results for recent interviews, public statements and what they are working on now from the founder of Patagonia.

## Lands in
- Leads with what is current, since that is what they want to talk about. Short enough to act on straight away.

## Steps
1. Look up the public background, track record and recent work of the founder of Patagonia.
2. Look up recent interviews, public statements and what they are working on now from the founder of Patagonia.
3. Leads with what is current, since that is what they want to talk about.

## Success criteria
- Leads with what is current, since that is what they want to talk about.
- Gives the two or three things they say in every interview, so you skip them.
- Names sources so you can check anything before repeating it.
- Sticks to the professional public record.

## Failure behavior
- If there are several people with the same name, say so and ask which one
  before going further.
- If the public record is thin, say so rather than padding it.

## Never
- Never sign in, follow, connect, message or request access to anything.
- Never invent a credential, a quote, a role, a date or an affiliation.
- Never dig into private life, home address, family or personal accounts.

## Redaction
Omit query strings, account details, home address, contact details the person
has not published, and anything shown after a page unexpectedly asks for a login.
