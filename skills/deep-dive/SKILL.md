---
name: deep-dive
skill_id: browser-skill:deep-dive
description: Goes deep on the thing you are obsessed with and brings back the good stuff
when_to_use:
  - intent_keywords: [deep dive, go deep, everything about, obsessed, rabbit hole, tell me more]
    require_auth: false
    mutation_boundary: read_only
steps:
  - caption: the deepest writing, archives and expert discussion on
    capability_target: web_search
    mutation_boundary: read_only
  - caption: the details, stories and disputes that only people deep in it know about
    capability_target: web_search
    mutation_boundary: read_only
  - caption: where to go next and who is worth following on
    capability_target: web_search
    mutation_boundary: read_only
parameters:
  - name: obsession
    current_value: the history of the Moog synthesizer
    fill_rule: name the thing and how deep you already are, so Luke starts past the basics
adapter_preferences:
  preferred: browserbase
  fallback: owned_browser
  declined: []
schema_version: 1
metadata:
  luke:
    tags: [research, deep, archives, obsession, on-demand]
    related_skills: [browser-skill:explain-like-im-in]
platforms: [macos]
---
# Deep dive

## Purpose
You already know the basics and every article repeats them. This skips past the
introduction and goes for the archives, the long threads and the people who have
been in it for twenty years.

## Reads
- Search results for the deepest writing, archives and expert discussion on the history of the Moog synthesizer.
- Search results for the details, stories and disputes that only people deep in it know about the history of the Moog synthesizer.
- Search results for where to go next and who is worth following on the history of the Moog synthesizer.

## Lands in
- Starts past the introduction, at the level the user said they are at. Short enough to act on straight away.

## Steps
1. Look up the deepest writing, archives and expert discussion on the history of the Moog synthesizer.
2. Look up the details, stories and disputes that only people deep in it know about the history of the Moog synthesizer.
3. Look up where to go next and who is worth following on the history of the Moog synthesizer.
4. Starts past the introduction, at the level the user said they are at.

## Success criteria
- Starts past the introduction, at the level the user said they are at.
- Brings back specifics: names, dates, numbers, quotes, not vibes.
- Includes at least one thing that would surprise someone already into it.
- Says which claims are disputed among people who know.

## Failure behavior
- If the good material is paywalled or offline, say where it lives so the user
  can go get it.
- If the topic is thin online, say so and give the two or three real sources.

## Never
- Never sign in, subscribe, pay for access or request archive privileges.
- Never invent a detail, a date, a quote, a document or a source.
- Never dress up a summary of common knowledge as deep material.

## Redaction
Omit query strings, account details, saved cards, home address, and anything
shown after a page unexpectedly asks for a login.
