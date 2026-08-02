---
name: trip-plan
skill_id: browser-skill:trip-plan
description: A real trip decided: where, when, roughly what it costs, book this first
when_to_use:
  - intent_keywords: [trip, holiday, vacation, plan a trip, travel, book a trip, going away]
    require_auth: false
    mutation_boundary: read_only
steps:
  - caption: where to go on this kind of trip and the best time of year
    capability_target: web_search
    mutation_boundary: read_only
  - caption: typical flight and accommodation costs for a week there
    capability_target: web_search
    mutation_boundary: read_only
  - caption: what to do there and how many days each place needs
    capability_target: web_search
    mutation_boundary: read_only
parameters:
  - name: trip
    current_value: a week away in spring, mid budget
    fill_rule: say roughly when, how long, and what you want out of it
adapter_preferences:
  preferred: browserbase
  fallback: owned_browser
  declined: []
schema_version: 1
metadata:
  luke:
    tags: [travel, trip, planning, holiday, budget]
    related_skills: [browser-skill:group-trip-herder, browser-skill:weekend-escape]
platforms: [macos]
---
# Trip plan

## Purpose
The trip you keep talking about, turned into something with dates and a price.
One destination, a shape for the days, and the one booking to make today.

## Reads
- Search results for where to go on this kind of trip and the best time of year a week away in spring, mid budget.
- Search results for typical flight and accommodation costs for a week there a week away in spring, mid budget.
- Search results for what to do there and how many days each place needs a week away in spring, mid budget.

## Lands in
- Commits to one destination and one set of dates, not a shortlist. Short enough to act on straight away.

## Steps
1. Look up where to go on this kind of trip and the best time of year a week away in spring, mid budget.
2. Look up typical flight and accommodation costs for a week there a week away in spring, mid budget.
3. Look up what to do there and how many days each place needs a week away in spring, mid budget.
4. Commits to one destination and one set of dates, not a shortlist.

## Success criteria
- Commits to one destination and one set of dates, not a shortlist.
- Gives the trip an order: which days go where, and how long each leg takes.
- Names the first thing to book right now, and what can wait a few weeks.
- States a rough total and what the big line items are.
- Accounts for the constraint that actually breaks trips: travel time between
  places, a season that ruins it, or a budget that will not stretch.

## Failure behavior
- If a fare or rate page will not load, give the published range and say it is
  approximate.
- If the budget does not reach the destination, say so plainly and plan the
  version that does.

## Never
- Never sign in to an airline, hotel or booking account.
- Never book, reserve, hold or buy anything.
- Never invent a fare, a rate, a hotel or an opening date.

## Redaction
Omit query strings, account details, booking references, saved cards, passport
and loyalty numbers, home address, and anything shown after a page unexpectedly
asks for a login.
