# Contributing with a coding agent

You are probably here because someone asked you to add a skill to this catalog,
or to look into something about one. This file tells you what to do without
making them find anything first.

`README.md` and `CONTRIBUTING.md` both point here, because this file is
deliberately not called `AGENTS.md`. That name is read automatically as project
rules by most coding agents, and it belongs to the maintainer workflow rather
than to contribution. A file that told every arriving agent that scaffolding
proposals is what this project is for would be wrong about the project.

Read `CONTRIBUTING.md` for what a skill may do and what a proposal must contain.
It is the authority on both, and it wins over this file on both. It does not
describe how to file, which is below.

## What this repository takes

Proposals arrive as **issues**. This repository accepts no pull requests from
contributors and there is nothing here to fork. Do not open one, and do not push
a branch.

Nothing you do here installs, trusts, or activates anything. Being listed in the
catalog does not make a skill trusted; each person approves an exact content hash
on their own machine before it runs.

## Work out what is being asked

**To propose a skill**, follow the sequence below.

**If the idea changes anything in the outside world, collects credentials, reads
a private origin, or uses a hosted or everyday browser for signed-in content**,
stop. It is not eligible today. A signed-in, read-only skill can be proposed only
when every step is bound to an explicit public host and runs in Luke's isolated
owned browser with no fallback. The person signs in directly there; the skill
never receives the credential. Open the *Suggest a skill idea* issue for anything
outside that route and say what was wanted.

**If a published skill answered wrongly**, open *A published skill answered
wrongly*. Read `catalog/index.json` for the exact version and `content_sha256`
rather than asking the person for them. If it is a security problem, do not
describe it in an issue; use the private vulnerability route.

**If a command failed or the guidance was wrong**, open *The creator, validator,
or guidance did not work*, with the verbatim diagnostic.

## Proposing a skill

1. Clone at the exact release tag named in the pinned card, never `main`, and
   verify it with `git describe --tags --exact-match HEAD`.

2. Confirm the idea is read-only and either reads public information without
   authentication, or uses the exact public-host-bound owned-browser route above.
   Host-free `web_search` is allowed only without authentication.

3. Build both files with `creator/create-luke-skill/scripts/new_skill.py`, then
   run `creator/create-luke-skill/scripts/validate.py` with
   `--allow-draft-provenance` until it prints `validated 1 Luke catalog skill(s)`.
   For the signed-in route, pass `--capability-target delegate_web_action` and
   `--auth-assumption owned_browser` with an explicit `--host`.
   Every failure carries a named `CREATOR_` or `CATALOG_` code; read it.

4. Write the submission with the proposal form's own headings, and state each
   file's byte count and SHA-256 directly above its fenced contents. Fence with a
   longer run of backticks than any inside the file. You can check your own
   submission before filing:

   ```bash
   python3 scripts/verify_submission.py --issue-body your-submission.md
   ```

5. **Ask the person before you file, and ask them the attestations in their own
   words.** Provenance, licensing, and whether the material contains anything
   private are claims about them, not about the skill. Do not answer those for
   them and do not tick the boxes yourself; a submission you attested is worth
   nothing.

6. File it once they say yes, and give them the link.

## What you must never do

- Post anything without an explicit yes from the person you are working for.
- Open a pull request against this repository, or push a branch to it.
- Answer the licence, provenance, or no-secrets attestations on someone's behalf.
- Present a passing check as review. Conformance is not approval, and a
  maintainer reads every proposal.
- Present the owned-browser route as a security clearance. It does not bypass
  validation, evaluation, maintainer review, local Trust approval, navigation
  approval, or activation gates.

## If something here was unclear

Say so, to the person you are working for and in the issue you file. Guidance
that made you guess is a defect worth reporting, and the reports are how it
stops being wrong.
