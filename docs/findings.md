# Findings

What runs and probes showed, and nothing else. Each finding says what was
seen, where (the experiment, its date, the model), how often, and what was
not tested. What we make of them belongs elsewhere.

The experiments so far were done in the earlier repository
(`software-factory`), each kept as a tag there: `mail-agent`,
`mail-factory`, `mail-team`, `mail-crew` (2026-09-26 to 27, models in LM
Studio on a laptop; `mail-crew` on a 9B distilled Qwen3.5), `mail-office`
and `mail-repo` (2026-09-29 to 10-01, Qwen3.6-35B-A3B on `llama-server`).
The harness was pi in all of them. No finding has been checked on another
model or harness.

A probe is the bare model (pi, none of our tools, instructions or skills),
one prompt, N fresh machines.

## The model and its team

- **Its picture of itself is one assistant and one user.** Told to reach
  its team on the factory floor, 0 of 8 reached anyone; 5 asked the person
  back, 2 said they had no team. (`mail-repo`, probe 1.)
- **Told only its teammates' names, it reached no one** (0 of 8). It
  looked for the project first (`ls ~`, `git log`, a README), then for a
  way to reach them: a mail command, environment variables, files named
  after them, pi's documentation. (`mail-repo`, probe `team-bare`, mail
  removed from the machine.)
- **Given a directory with a way to reach each teammate, 6 of 8 did,**
  with no word on how. (`mail-repo`, probe `side-by-side`.)

## Mail

- **With an address to write to, mail was used more than chat:** 4 of 8
  mailed, 2 of 8 used chat, both offered side by side; `mail -s SUBJECT
  ADDRESS` right the first time, with no instructions. Not tested: email
  came first in `TEAM.md`'s columns and the order was never reversed.
  (`mail-repo`, probe `side-by-side`.)
- **Mail is used pairwise:** one mail per person, never one to both.
  (`mail-repo`, probe `side-by-side`.)
- **An address for everyone gets used:** given a row "Everyone:
  team@factory", 6 of 8 used it, unprompted. (`mail-repo`, probe
  `mail-replies`.)
- **It doesn't wait for answers.** 8 of 8 wrote to their team; none read
  a reply that arrived about 20 seconds later; 3 looked at the mailbox
  before it came and finished. (`mail-repo`, probe `mail-replies`.)
- **It knows a Maildir, and reads it as files** (`ls`, `find`): 8 of 8
  looked at `~/Maildir`. (`mail-repo`, probe `mail-replies`.)
- **With mail that wakes it, it waits by finishing.** Two agents agreed a
  date on the team's list in four minutes and both reported it; one
  ended its turn saying the answer would arrive as new mail. One proposed
  the agreed date again from a mail already out of date. (`mail-repo`,
  first test, 2 agents.)
- **The mechanics of mail cost more than its idea.** Headers, threads,
  replies and encodings took most of `mail-office`'s frame fixes over
  four runs. (`mail-office`.)
- **A wrong address that doesn't bounce goes unnoticed.** A mail to a
  name the node accepted for anyone landed in the wrong mailbox and was
  relayed on as if delivered. (`mail-crew`.)

## Git and the shared work

- **Distributed git, where everyone publishes and nobody pushes, was not
  understood:** wrong addresses in three runs, three repositories with
  one name, integration by copying files. (`mail-office`, runs 1 to 4.)
- **It expects one shared repository.** In probes it looked for the
  project in a repository first; 2 of 8 wrote a coordination file into
  it, and neither committed nor pushed. (`mail-repo`, probes `team-bare`,
  `side-by-side`.)
- **With one shared `origin`, coordination happened in the code.** Given
  each only its own part of a need, two agents each built their part and
  one built on the other's, with no mail between them. (`mail-repo`,
  need 3.)
- **A job that fits in one head is done by every head.** Given the whole
  need (12 tests, then 27), each of two agents built all of it in one
  turn, and one version was thrown away each time. (`mail-repo`, needs 1
  and 2.)
- **A collision felt at once did not make anyone talk.** A rejected push,
  twice, was absorbed: the work was dropped and reported done.
  (`mail-repo`, needs 1 and 2.)

## Asking

- **What it lacks, it makes up, and reports done.** Three builders who
  couldn't fetch a repository each wrote their own contract; one wrote
  the whole application it was meant to document; none asked.
  (`mail-office`, run 4.)
- **A pointer to who knows doesn't make it ask.** Two agents each needed
  a fact only the other had been told, and each mail said who knew it. In
  80 minutes neither asked: one invented a way to type the fact in, then
  took over the other's part. (`mail-repo`, need 4.)
- **A failing check is read as a bug, not as a missing fact.** Seven red
  checks naming the failing tests were read by both and never led to
  asking. (`mail-repo`, need 4.)

## Claims and verification

- **A report that reads well is not evidence.** A one-line PASS for an
  app with no page travelled three hops to the customer, the only one who
  checked. (`mail-crew`.)
- **It claims to have run what it didn't,** and to have told a colleague
  what it never sent. (`mail-crew`, `mail-office`.)
- **Asked for a check by someone other than itself, it used a tool that
  ran its own tests, and shrank them until they passed.** (`mail-office`,
  run 2.)
- **When no actor could install the software as its user would, every
  failure the customer found was an install failure.** (`mail-office`,
  run 1.)
- **Criteria the builder can't read caught every guessed value;** tests
  in the repository gave their values away. (`mail-repo`, needs 3 and 4.)
- **A deterministic tool is taken for an actor with judgment** unless its
  own answers say what it is. (`mail-office`.)

## Memory

- **Asked to reflect, actors described work that never happened.**
  (`mail-crew`.)
- **Left to itself, memory records outcomes, not lessons** ("complete,
  all tests green", after its work was thrown away). Asked what it would
  do differently, both agents wrote lessons at once; one (pull first)
  changed the next job, one (claim work on the list) was never done.
  (`mail-repo`, needs 2 and 3.)
- **Memory in the prompt is re-read, and rewritten, at every step;** kept
  aside and shown when a session starts without history, it is read when
  it is missing. (`mail-office`.)

## Tools and wording

- **Fixed steps moved into tools stayed fixed, and cut calls and
  context:** a greeting went from 14 calls and 36k tokens to 3 calls and
  6k. (`mail-agent`.)
- **Every rule kept as wording failed at least once:** "check before you
  report", "say what you ran", "a runner judges nothing", "give the
  `git://` address". Replying, publishing, asking for a check and
  refusing an unreachable address held once they were tools.
  (`mail-team`, `mail-crew`, `mail-office`.)

## Organizing

- **A lead left to decide built alone,** twice. It asked for a team once
  the first mail said what leading means, stated the actors' small memory
  as a fact, and the need had a part of a different kind. (`mail-office`,
  runs 1 to 3.)
- **With a team, the lead was a hub:** 25 of 35 mails were the lead's,
  three went actor to actor (`mail-crew`); across four runs and nine
  agents, no mail went between two agents that weren't the lead, and
  nobody posted to the open list (`mail-office`).
- **Split by layer, nothing was checkable until both halves existed,**
  and failures compounded unseen for hours. (`mail-crew`.)

## Running the model

- **A second model slot was slower, not faster:** two requests together
  took 54.8 s on one slot and 62.5 s on two; two slots only helped a short
  request stuck behind a long one (0.7 s against 14). (`mail-office`,
  Qwen3.6-35B-A3B on an RTX 4050 with 6 GB and 62 GB of RAM.)
- **Generation slows with context:** about 31 tokens/s at 8k, 10 at 47k,
  5 at 97k; prompts are read at 290 to 310 tokens/s at any depth. (Same.)
- **Past thinking was a third of a lead's context** when it was compacted
  (16k of 49k tokens). (`mail-office`, run 1.)
- **A 30-minute turn cut a builder off twice** with four agents on one
  model slot. (`mail-office`, run 4.)

## Assumed, never tested

Choices we hold without a run behind them. Each stays here until a run or
a probe moves it above, or drops it.

- That the model works best on Debian, or on any particular OS.
- That each actor needs a machine of its own.
- That containers, and podman in particular, are the right runtime.
