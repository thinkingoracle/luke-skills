---
name: golden-hour
skill_id: browser-skill:golden-hour
description: Where to be at sunset tonight, and what time to leave
when_to_use:
  - intent_keywords: [sunset, golden hour, view, viewpoint, lookout, sunset spot, tonight]
    require_auth: false
    mutation_boundary: read_only
steps:
  - caption: best sunset viewpoints, lookouts and rooftops near
    capability_target: web_search
    mutation_boundary: read_only
  - caption: sunset time tonight and sky conditions in
    capability_target: web_search
    mutation_boundary: read_only
trigger:
  kind: schedule
  recurrence: daily
  time: 17:15
  timezone: America/Los_Angeles
  follows_device: true
parameters:
  - name: view
    current_value: sunset spots in Los Angeles
    fill_rule: say your city and Luke uses it instead
adapter_preferences:
  preferred: browserbase
  fallback: owned_browser
  declined: []
schema_version: 1
metadata:
  luke:
    tags: [sunset, views, golden hour, outdoors, daily]
    related_skills: [browser-skill:trail-today]
platforms: [macos]
---
# Golden hour

## Purpose
Quarter to four, with enough runway to actually get there. One place to watch the
sun go down tonight, and the time to walk out the door.

## Reads
- Search results for best sunset viewpoints, lookouts and rooftops near sunset spots in Los Angeles.
- Search results for sunset time tonight and sky conditions in sunset spots in Los Angeles.

## Lands in
- Gives a real sunset time and a leave time that includes the travel. Short enough to act on straight away.

## Steps
1. Look up best sunset viewpoints, lookouts and rooftops near sunset spots in Los Angeles.
2. Look up sunset time tonight and sky conditions in sunset spots in Los Angeles.
3. Gives a real sunset time and a leave time that includes the travel.

## Success criteria
- Gives a real sunset time and a leave time that includes the travel.
- Says where to park or which side of the spot to stand on.
- Offers one closer backup for a night with less runway.

## Failure behavior
- If a source will not load, skip it and keep going.
- If the sky is fully socked in, say so in one line and name a spot worth it
  anyway.

## Never
- Never sign in, buy a ticket or reserve a table.
- Never invent a sunset time, a viewpoint or an access route.
- Never pass a sponsored rooftop listing off as a real recommendation.

## Redaction
Omit query strings, account details, order history, saved cards, home address,
and anything shown after a page unexpectedly asks for a login.
