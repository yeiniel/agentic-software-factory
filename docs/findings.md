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

- **Without a word about memory in its prompt, an agent claimed to have
  saved what it hadn't.** Asked by mail to reply with what it had saved to
  its memory, the lead's reply said "the key points I've saved" and its
  session ran only mail commands; there was no `~/memory`. (First run on
  `images/agent`, 2026-10-01, Qwen3.6-35B-A3B.)
- **With three sentences about memory in its prompt (keep what you need
  in `~/memory`, one file per subject, each starting with a line that says
  what it holds; look there before you start work), it wrote memory before
  it replied, and its reply matched what it wrote:** one file in one run,
  two in another. It tried a wrong path first (`/home/memory/`) in one run
  and corrected it. Neither file in the second run started with a line
  saying what it holds. Two runs, one scenario. (2026-10-01.)

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

## The machine

- **Postfix's default `import_environment` sets `LANG=C`,** so every
  command it runs (the agent's pi, and each `mail` it runs) has no usable
  character set for a message with non-ASCII text: `s-nail: Cannot find a
  usable character set to encode message ... message not sent`, with a
  `dead.letter` left in the home, although the container's own `LANG` was
  `C.UTF-8`. The agent worked around it in two different ways (a `LC_ALL`
  per command; a `~/.mailrc` with `set charset=utf-8`) before the mail
  went. With `LANG=C.UTF-8` in Postfix's `import_environment`, the third
  run's first send worked and nothing was left behind. The same condition reproduced without Postfix (`env -i LANG=C`, a mail with
  an accented letter and a dash): it fails in a plain shell and sends in a
  login shell, where `/etc/profile.d/locale.sh` sets `LANG`; the image now
  does that instead, which covers the agent (its `.forward` runs `bash
  -lc`) and a person's login alike. Not rerun end to end after that
  change. (2026-10-01.)
- **Without the usual tools for looking at a machine, the agent spends
  its context working around them:** listing `/proc` by hand, decoding
  `/proc/net/tcp`, testing a web server with Python, where `ps`, `ss` and
  `curl` were missing. (`mail-office`, run 1, the lead.)

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

## Infrastructure

- **Rootless systemd-nspawn doesn't start on a default host.** Importing a
  Debian rootfs with `importctl --user -m import-tar` failed: "Failed to
  allocate transient user namespace". It needs `systemd-nsresourced` and
  `systemd-mountfsd`, whose sockets are disabled by default; enabling them
  takes root. Not tried: anything past that step. Its man page also limits
  rootless machines to a link with the host each (no shared bridge), and
  folders owned by the "foreign" UID range. (2026-10-01, systemd 261 on
  Arch Linux, NetworkManager, networkd disabled.)
- **A node can be a container whose main process is its mail server.**
  One Debian trixie-slim image, Postfix in the foreground (`postfix
  start-fg`) under podman's `--init`, no systemd; each mail delivered to a
  command that stores it and, for an account with a model, wakes pi. Two
  agents and a person's mailbox, rootless podman: the person asked one
  agent for something only the other could answer, and had the answer 66
  seconds later, relayed through both agents. The sender was checked
  throughout: a forged sender over SMTP and a forged sender from inside a
  node were both refused; a wrong user, a wrong host, a stopped node, root
  and an address outside the domain each bounced at once. The image's own
  files are 142 lines, against 450 for `mail-office`'s base and agent
  (which also had lists, a git daemon, accounts restored at boot, a memory
  index and an extra turn). One run, one model (Qwen3.6-35B-A3B). Not
  tested: more than one mail in flight, restarts with mail queued, a
  target. (2026-10-01, `images/node`.)
- **The same node needs no code of ours: Postfix alone does it.** The
  account's `~/.forward` keeps each mail in `~/Maildir/` and pipes it to
  pi (`bash -lc`, for a login's PATH); pi takes the mail on stdin as its
  prompt. One delivery at a time per account (`local_destination_
  concurrency_limit = 1`) makes an agent take its mail one at a time: a
  reply that came while the agent was in its turn waited in Postfix's
  queue and was delivered after it. `command_time_limit` bounds a turn.
  Three images: `images/mail`, a mail host (131 MB), `images/seat` on top
  of it (a person's account), and `images/agent` on top of it (818 MB: pi,
  the jobs' tools, the system prompt, the `.forward`); the node's own
  config is pi's `models.json`. The same task took 45, 50 and 73 seconds
  over three runs as the images were reworked; the wrong user, wrong
  host, outside address and root bounced at once every time. Without a
  sender check of our own, a forged sender over SMTP was accepted, and
  woke the agent (which did nothing with it). In a fourth run Ana asked
  Ben to mail the answer to Boss himself, and he did. Qwen3.6-35B-A3B.
  (2026-10-01, `images/mail`, `images/agent`.)
- **A home volume backed by the node's folder is filled from the image
  the first time** (`podman volume create --opt type=none --opt o=bind
  --opt device=DIR`): the agent's `.forward` came from the image, and the
  files are owned by the host user (`--userns keep-id`). A plain bind
  mount hides what the image put there. (2026-10-01, podman 6.1.1.)
- **A turn that fails or times out is reported to the sender by Postfix
  itself, with the reason, and is not retried.** pi exiting with an error
  (its model server unreachable) became a permanent bounce 14 seconds
  later, "Command died with status 1", with pi's own output ("Connection
  error") in it. A command running past `command_time_limit` (15 seconds
  in the test) became a bounce, "Command time limit exceeded", ran once
  and left no process behind. In both, the mail had already been kept in
  the agent's Maildir (the first line of its `.forward`) and was never
  looked at by the agent again. The bounce reaches the sender as mail from
  `MAILER-DAEMON` with an empty Return-Path. Not tested: a bounce to a
  sender that is an agent. (2026-10-01, Postfix 3.10.13, three nodes.)
- **Stopping a node mid-turn loses mail without a word.** Two mails to an
  agent, the node stopped while the first one's command ran and started
  again four seconds later: the queue was empty, the Maildir held only the
  first mail, the second was never delivered, the first's command was
  killed and not run again, and the sender got nothing. Postfix's queue is
  in the container's own filesystem, which is recreated at every start;
  only the home is a volume. One run, a command that only sleeps. Not
  tested: the queue on a volume, which would deliver again what was in
  flight, the first mail's Maildir copy and command included.
  (2026-10-01.)
- **A shared repository can be a container whose main process is `git
  daemon`.** One image (`images/repo`: git, make, s-nail), the daemon
  starting as root and dropping to the account `git`, repositories as
  plain folders in that account's home, visible on the host
  (`state/NODE/home/NAME.git`). Two other nodes cloned it and pushed over
  `git://`, no accounts. Three lines in the image's `/etc/gitconfig`
  (`receive.denyNonFastForwards`, `receive.denyDeletes`, a system hooks
  path) apply to every repository: a force-push and a deletion of `main`
  were both refused by the server, and a second pusher working from an
  old state was rejected at once ("fetch first"), and integrated with a
  rebase. Throwaway nodes, people's seats as pushers, no agent.
  (2026-10-01, `images/repo`.)
- **A check on every push to `main` can be the repository's own hook,
  and its verdict can be mailed with no mail host on the node.** The
  `post-receive` hook starts `make check` on a fresh checkout, detached
  (the pusher isn't held) and one at a time, and mails the result with
  `s-nail` speaking SMTP straight to each receiver's Postfix. A failing,
  a failing again and a passing push were each reported in one to four
  seconds, the mail marked `Auto-Submitted` and saying in its text that it
  is automatic. Not tested: the 600-second time limit, two pushes at
  once, agents as pushers or receivers. (2026-10-01.)
- **The first version of that mail was lost without a word.** `s-nail`
  needs the port written (the slim image has no `/etc/services`), and a
  user in the URL, or it prints an obsoletion warning; with the user in
  the URL it refused to send at all, "New-style URL used without
  *v15-compat* being set", and the two verdicts that followed existed
  only in a `dead.letter` and a line of the node's log, until a test
  caught it. With `v15-compat` and `smtp-auth=none` it sent. Also: an
  address that doesn't exist is reported only in the same log, the other
  addresses still get the verdict; with no addresses at all the pusher is
  told, on the push. (2026-10-01, s-nail 14.9.)
- **A fresh node can't commit, and the account's full name is all it
  lacks:** "Author identity unknown", since its account has no full name.
  With one (`useradd -c agent`), git works out the rest itself from the
  account and the node's fully qualified hostname: `agent
  <agent@ana.factory>`, `user <user@yeiniel.factory>`: the same in a login
  shell, through the agent's `.forward` (Postfix's own environment), and
  in a real commit. (2026-10-02.)

- **OpenSMTPD can't deliver between podman containers.** Podman's DNS
  answers a container's name but returns "no such domain" for its MX
  record, which rules out falling back to the name, and OpenSMTPD has no
  setting to skip MX lookups. Postfix does (`smtp_dns_support_level =
  disabled`). (2026-10-01, podman 6.1.1, OpenSMTPD 7.6.0.)
- **A command run by Postfix's delivery has a minimal PATH,** so the first
  wake-up failed to find pi, and said so only in a log in the agent's
  home. (2026-10-01.)

## Assumed, never tested

Choices we hold without a run behind them. Each stays here until a run or
a probe moves it above, or drops it.

- That the model works best on Debian, or on any particular OS.
- That each actor needs a machine of its own.
- That containers, and podman in particular, are the right runtime.
