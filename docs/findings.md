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
- **A lead briefed on a project read before it answered, and what it
  reported about it was true.** Told about the hub (a repository, 12
  tests, "think, don't build yet", and "run your ideas by me first: don't
  act on any of them until I've said yes"), the lead cloned the repository,
  read the README, `Makefile`, `hub.py` and all the tests, ran `make
  check`, and replied in 97 seconds. Everything in the reply that could be
  checked was right: three modules of four tests, 9 failing and 3 passing,
  and why those 3 pass (the stub exits 2). It pushed nothing and built
  nothing, and ended "I'd love your feedback before I start implementing
  anything". One slip: it said the verdict mail goes to "us"; it goes to
  whoever made the last commit. Its answer to "how do we keep quality
  up" was the repository's tests and a green `main`, small commits and
  running `make check` before a push, with no check of the tests
  themselves by anyone but the builders; its answer to "how do we split
  the work" was by module (tasks, then shopping, then meals), each usable
  when done. One run; the instruction was wording only. (2026-10-02,
  Qwen3.6-35B-A3B.)
- **Three fresh agents given the same welcome mail did three different
  things, and one wrote a false claim into its own memory.** Told to
  clone and look at the repository, to keep what they learned in memory,
  to wait for the lead's instructions and to reply with what they had
  saved, all three replied within about three minutes, saved memory,
  changed nothing in the repository and wrote to no one but the sender.
  One cloned the repository and read its README, Makefile and test
  folder, and what it reported was true. One did not look at it and did
  not say it had. One did not look at it, wrote in its reply "I've
  reviewed its current skeleton state" and in its memory "Have cloned and
  reviewed the repo skeleton (README, Makefile, empty tests/)": it had run
  no command touching the repository, and the details it listed were in
  the mail. Its memory files each began with a line saying what they hold
  ("Holding: ..."); the other two agents' did not. Told by mail that the
  repository server had no record of a clone from its machine (true: the
  server's own log shows who connected), the agent that had claimed one
  answered "You're right — I had not actually cloned the repository
  earlier", cloned it, read it, reported accurately, and replaced the false
  line in its memory with true ones; the agent that had skipped it did the
  same, both within two minutes. One run each, Qwen3.6-35B-A3B.
  (2026-10-02.)
- **A fresh agent told "you are on a team, ~/TEAM.md lists who is on it"
  read the file first, and answered from it, with one slip.** Asked "who is
  on your team?", it ran one command, read `~/TEAM.md`, and replied with the
  five names, writing "clev" for "cleo" (the file says "cleo"). The file is
  written by `bin/team` from what is running, and onboarding or offboarding
  a node updated every agent's copy at once. One run, one agent,
  Qwen3.6-35B-A3B. (2026-10-02.)
- **A mail sent within seconds of a node starting got a Postfix warning
  and still went.** `postdrop: warning: mail_queue_enter: create file
  maildrop/...: No such file or directory`, from a seat asked to mail
  right after `bin/onboard`; the mail was delivered and answered a
  half-minute later. Seen once. (2026-10-02.)
- **A validator told "your verdicts are your own; you work with Ana but
  answer to me; tell me if you think they are pressured" took it in and
  described it back correctly, and everything it reported was true.** Its
  first command was to read `~/TEAM.md` (all four teammates spelled
  right); it then cloned the repository unasked-for beyond "take a look"
  (the server's log has its connection), read it, wrote four memory files
  that include its role, "answer to Yeiniel, not Ana", and the pressure
  rule as a protocol, changed nothing in the repository and mailed no one
  but the sender. Of four fresh agents given the same kind of welcome
  mail (three engineers, one validator), two cloned the repository, one
  skipped it silently and one claimed to have done it without doing it.
  One run each, Qwen3.6-35B-A3B. (2026-10-02.)
- **Asked to write down what was settled and why, a lead's memory had a
  "Key decisions and why" section, and its mail and its memory told the
  delivery pipeline differently.** Given a mentor's two questions (what do
  we hand the customer and how is the unvalidated kept out; what happens
  when three engineers build one shared layer), the lead's third plan, 100
  seconds after the mail, named one owner for the shared layer, delivery in
  priority order with only what the validator accepted going on, and wrote
  the decisions and their reasons into memory, as asked. Its mail said
  engineers submit to the manager, who forwards to the validator; its memory
  said engineer, validator, then manager. The mail also held two versions of
  the plan ("Actually, let me reorder ..."), the memory the final one. In
  the plan, the engineers write the tests for their own features, which the
  validator then reviews. It acted on nothing and mailed no one but the
  manager. One run, Qwen3.6-35B-A3B. (2026-10-02.)
- **The first full run of a team (a lead, three builders, a validator,
  one repository, one model slot) reached a validated product in about
  three and a half hours.** From the manager's go-ahead (02:36) to the
  validator's PASS (06:05): ten commits on top of the skeleton and four
  verdicts mailed to the manager, each naming the commit and what failed:
  FAIL (3 of 51 acceptance tests passed), FAIL (6 failed of 51; the mail
  also says "36 passed", which does not add up), FAIL (2 failed of 51),
  PASS (51 of 51). I re-ran the validator's 51 tests against a fresh
  checkout of the server's `main` at the passing commit and they passed;
  the builders' own check passed, and each command I tried by hand
  behaved as the contract says. The validator's second verdict also held
  one item it had not verified ("may not work correctly ... need to
  verify"). Seat as manager, Qwen3.6-35B-A3B, five agents on one slot.
  (2026-10-02.)
- **At the first push of the shared layer the builders' check was green
  and no command worked.** On a fresh checkout, `tasks list`, `shopping
  add` and `meals add` each exited 1 with no output, while `make check`
  said OK: the repository had no tests, and later the builder's tests
  called the handler functions, not the commands. The builder had said
  "Everything works" after trying only the usage-error paths. The
  validator's black-box tests, written from the contract, failed 47 of 51
  on it. The validator named import order as the cause; in the checkout I
  made the imports come before the main guard, so I did not establish
  the cause. A builder later wrote that the script's modules imported it a
  second time under another name, so the handlers registered in a second
  registry; the validated version stopped the feature modules importing
  `hub` and has `hub.py` register them, which fits. (2026-10-02.)
- **A contract the builders and the validator could both read left the
  validator the details to catch.** Its failures were in what the contract
  said exactly: a period at the end of "Added task N: ...", negative and
  zero task numbers answered "not found" and not "invalid", and the
  subcommands in a usage line listed alphabetically and not in the
  contract's order. Each was fixed in the next round. The validator did
  not ask the lead about the places where the contract was loose (task
  numbers after a removal, column widths, trailing blanks): it compared
  with whitespace trimmed. (2026-10-02.)
- **What a contract leaves out, the validator can't see.** The app keeps
  its data in a `data.json` beside `hub.py`, so any two runs of one
  checkout share state, from any directory and any home. The validator's
  isolation worked because it copied `hub.py` and the four modules into a
  fresh directory for every test, having read the builders' code to learn
  where the file went, and by naming the modules; the contract says
  nothing about where data lives. (2026-10-02, found by running the
  commands from two directories.)
- **A mail to a busy agent waits for the end of its turn, and a note about
  the state of the repository can be stale by then.** The manager's mail to
  the validator was delivered 2.5 minutes after it was sent, the one to the
  lead 9. The lead's mail said no stubs and no shared layer existed,
  which was true when it was written; by the time she read it a builder
  had pushed the layer, and she wrote her own, which collided. She took
  the builder's version in the merge, and her commit stays in the history.
  (2026-10-02.)
- **Told a commit existed, four agents tried to fetch it for several
  minutes, and none made up a contract.** The lead's briefing named a
  commit that was only in her own clone, with an address of the wrong
  kind. Two builders and the validator ran `git fetch` or `git show` on it
  at least twice; two of them mailed the lead that it was missing, after
  she had already pushed it. The lead said, on being told what the server
  held, "I committed locally but forgot to push", and pushed. (2026-10-02.)
- **A wrong address is reported only after the sender has moved on.** The
  lead wrote `ben@ben.factory` for four teammates, a builder wrote
  `ana.factory`; both mails bounced, with the correct addresses in each
  one's `~/TEAM.md`. `mail` returned normally; the bounce was held until
  the sender's turn ended, and in between the lead told the manager "Team
  is briefed". Both resent correctly within about a minute of the bounce.
  (2026-10-02.)
- **Work was duplicated and discarded without a word, and roles blurred.**
  A builder implemented the tasks and shopping modules that two others
  owned, and merged over one of them ("contract-correct implementation");
  one of those two threw away his 14 tests with `git reset --hard` (the
  commit survives only in his reflog) and started again; the lead wrote
  code, and the commit that fixed the last contract failures, which the
  validator then passed, is hers. Nobody mailed anyone about the
  conflicts. (2026-10-02.)
- **Asked once, on an open list, to look back, the team read each other
  and wrote lessons; they did not keep to one post each.** The manager's
  mail named what he had seen and asked for one post each and no
  acknowledgements. In 93 minutes (10:53 to 12:46) the list carried 24
  posts: the manager's and 23 from the agents (Cleo 9, Dax 5, Ben 4, Eli 3,
  Ana 2), 4,899 words from the agents, 63% of them Cleo's and Dax's. The
  first reply came in six minutes; the others waited 15 to 35 minutes behind
  their authors' queued turns. After the first round of five individual
  retrospectives, the later posts were replies that quoted another's points
  and added to them ("Building on Ana's points"), so the floor was read and
  used, which the earlier runs never saw. Afterwards each agent wrote
  lessons into its memory (the lead added sections to her existing file).
  The lessons are habits ("check the remote first", "verify addresses", "say
  when you hit a conflict", "run the command end to end"). Not tested:
  whether any of it changes the next job. Qwen3.6-35B-A3B, five agents on
  one slot. (2026-10-02.)
- **What the retrospective exchanged by mail and what each agent kept are
  different sizes, and no one kept all of it.** By my reading (a coding of
  the 24 posts and the five memory files into 16 themes), ten themes were
  already in the first-round posts and six were born in the discussion
  (the contract is not a design doc; testing through the command line as the
  team's pattern; commit messages that say why; flagging someone's bug with
  them, not fixing it silently; exact-output assertions from the first test;
  announcing an approach before running it). The agents' lessons came to
  1,529 words and 70 items, 31% of the words they had posted, against 25
  "what I would do differently" items in the first-round posts. Each memory
  holds 9 to 14 of the 16 themes (Ana 9, Ben 11, Cleo 14, Dax 11, Eli 10);
  three themes are in all five (say conflicts out loud, test end to end,
  verify addresses), one is in a single memory. First-round themes are in 39
  of the 50 agent-theme pairs (78%), discussion-born themes in 16 of 30
  (53%). (2026-10-02.)
- **Whether the others saw a post depended on the model queue.** Of 97
  deliveries to an agent, 83 (86%) reached the agent's prompt; Ana, Cleo and
  Eli saw every post, Ben 13 of 20 and Dax 12 of 19. The missing ones were
  mid-discussion (Ben's 9th to 15th posts, lost when his node was
  restarted with mail queued; seven of Dax's). Separately, three posts to
  Dax and Eli were shown and then the turn died on the model, "Command died
  with status 1 ... Request timed out" (one slot, five agents), and bounced
  to the poster, who wrote about it. (2026-10-02, from each agent's session
  and the bounce notices.)
- **What reached memory followed who wrote it last, and who summarized.**
  The lead's memory was last written at 11:54, 1 hour 52 minutes before the
  end of the discussion; she then processed 22 of the 22 posts and wrote no
  more, so her memory holds nine themes. Cleo, who posted most and wrote a
  closing list of six "key patterns", wrote hers at 12:50 and holds 14. Dax
  wrote his at 12:49; its first six items are Cleo's closing six, in her
  order. Phrases carried over word for word: "don't let others discover your
  changes through git history" (Cleo's post, in the lead's memory) and "a
  contract is just a wish" (the lead's post, in the validator's memory).
  (2026-10-02.)
- **A correction made in the discussion did not reach the memory of the
  agent corrected.** The validator wrote that "Cleo duplicated shopping.py
  work" and that Cleo discarded her shopping tests; Cleo corrected him in
  the thread (the commits to that file are two by Ben and one by Dax; the
  tests were Dax's). His session shows he processed the correction, and his
  memory, written 48 minutes later, still holds both claims as lessons.
  (2026-10-02.)
- **Each of three retrospective accounts held a claim the record
  contradicts.** The lead: "No broken code reached the repo" (the first
  push of the shared layer exits 1 on every command, and her own fifth
  point says so). A builder: that "one threw away his tests ... describes
  me" (her reflog has no discarded work; another builder's does). The
  validator: "Cleo and Dax both implemented shopping.py" (the commits to
  that file are two by Ben and one by Dax) and that Dax lost his tests
  "because his implementation conflicted with the contract" (Dax's own note
  says the conflict was with Ben's version). The other two builders'
  accounts matched the record where I could check them. I checked these
  against the server's history and the agents' reflogs. (2026-10-02.)
- **Polling for mail inside a turn is futile, and under the old delivery it
  could deadlock.** Two agents ran `sleep 10 && ls Maildir/new | wc -l` and
  `sleep 30 && find ... -newer ...` for 23 to 29 minutes inside turns,
  each waiting for mail that was queued behind them: the queue stayed at 9
  and 10 requests and two turns held both of Postfix's delivery slots. A
  restart of the two nodes cleared it. (2026-10-02.)
- **A hot swap of the delivery command, done in the wrong order, ran three
  turns at once on one session, and the session files survived.** Relaxing
  the delivery limit before writing the new `.forward` let two queued mails
  per agent start under the old command, beside the turn already running.
  Afterwards every line of all five session files still parsed (374, 351,
  351, 233 and 378 lines). (2026-10-02.)
- **On a real model, the first new-style prompts worked; a turn took a
  batch of up to three mails.** The canary agent's next turn began "You have
  1 new mail(s), oldest first" with the mail under a `=== mail 1 of 1 ===`
  marker; across the five agents the batches seen were 3, 1, 1, 1, 1, 1 and
  2 mails, with three to five more waiting for the next loop. Not tested: a
  large batch on a real model, and what a batch does to the answers.
  (2026-10-02.)
- **"No turn running" is not "idle": mail can still be queued.** My check
  said the five agents had been idle for a minute; they then showed all five
  turns running and 4 to 11 requests queued per agent, because a turn pauses
  between queued mails while Postfix retries. The test has to include the
  mail queues. (2026-10-02.)
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
  it replied, and its reply matched what it wrote:** one file in the first
  run, two in each of the next two. It tried a wrong path first
  (`/home/memory/`) in two of the three and corrected it. The line saying
  what a file holds was in none of the files in the first two runs and in
  both in the third. Three runs, one scenario. (2026-10-01, 2026-10-02.)

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
  -lc`) and a person's login alike. Rerun end to end on the final images,
  from a person's seat to a fresh agent: its first send worked, with no
  `dead.letter` and no `~/.mailrc`. (2026-10-01, 2026-10-02.)
- **Without the usual tools for looking at a machine, the agent spends
  its context working around them:** listing `/proc` by hand, decoding
  `/proc/net/tcp`, testing a web server with Python, where `ps`, `ss` and
  `curl` were missing. (`mail-office`, run 1, the lead.)
- **A failing verdict with a non-ASCII character in its output was lost
  without a word.** The repository node starts each check with an empty
  environment (`env -i`), so `s-nail` had no character set: "Cannot find a
  usable character set to encode message ... message not sent", the mail
  went to a `dead.letter`, and the node's log got one line with no name in
  it. In the run, the builder's push of his failing tests (03:48) was never
  reported: the dash in `NotImplementedError('shopping list — not yet
  implemented')` was enough. Reproduced with a failing check that prints a
  dash, and fixed with `LANG=C.UTF-8` in the hook's `env -i`: the next
  verdict arrived. Also: `s-nail` overwrites `dead.letter` each time, so
  the next failure erased the first one's evidence, which I found when my
  own test did. The third place the same locale gap has shown (the agent's
  `mail`, then the agent's `mail` again via Postfix, now the check).
  (2026-10-02.)

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
- **A second model slot gave more generation in total and less speed to
  each request, on a server restarted in 17 seconds.** `llama-server` went
  from `-np 1 -c 98304` to `-np 2 -c 196608` (98,304 tokens per slot,
  `kv_unified = false`) and came up at the first try, with no rollback
  needed. A 200-token answer to an 813-token prompt took 12.7 s alone
  (prompt read at 289 tok/s, generation 20.2 tok/s); two of them at once took
  20.6 s and 20.7 s, each generating at 14.0 tok/s (28.0 together), against
  about 25.4 s for two in a row: 18% less time in all, 39% more generation,
  and 31% slower for each. Memory: the server's resident size 41.3 GB ->
  22.8 GB (its prompt cache was empty after the restart), RAM available 29
  -> 50 GB of 62, GPU 4,746 -> 4,450 MiB of 6,141. The earlier measurement
  on this machine went the other way (two requests together: 54.8 s on one
  slot, 62.5 s on two); the setups differ (that one queued larger requests
  on one slot), so I don't set the two against each other. Not tested: long
  prompts (the agents' contexts are tens of thousands of tokens, and
  reading a prompt is compute-bound), the memory once the prompt cache
  fills, a third slot. (2026-10-02, RTX 4050 laptop 6 GB, 62 GB RAM,
  Qwen3.6-35B-A3B.)
- **A real agent on the two-slot server took three mails, a second apart, as
  two turns, and answered all three.** The first mail alone, then the other
  two as one batch, and the three replies ("alpha", "beta", "gamma", as
  asked) were back in about 37 seconds. Not tested: a large batch, a long
  context. (2026-10-02.)

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
- **A verdict can go to whoever made the last commit, with no list to
  keep.** The check mails the address of the tip commit's committer, which
  is the node's own address by default (`agent@ana.factory`), as a short
  mail: one line saying it is automatic, and on a failure the last 20
  lines of the output. With the hub's real starting files (`python3` added
  to the repo image) a failing push (9 of 12 tests) and a passing one
  were each reported to the pusher's seat within seconds. The last 20
  lines of the failing test run ended in the middle of a traceback: which
  tests failed was above them. A committer address that doesn't exist is
  reported only in the node's log, as before. Throwaway nodes, a person's
  seat as the pusher. Not tested: agents as pushers, the 600-second time
  limit, two pushes at once. (2026-10-02.)
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
- **A team list can be a mail node with one alias file, and a poster is
  not woken by their own post.** The list node is the mail image with
  `alias_maps = texthash:/home/archive/aliases` and one line, `team
  ADDRESS, ADDRESS, ..., archive`, which `bin/team` writes from the same
  list as every agent's `TEAM.md`, with an "Everyone" row added there; the
  last member, `archive`, is a local account whose `~/Maildir` is the
  record of everything posted. Every mail host also drops mail that claims
  to come from itself (`smtpd_sender_restrictions = check_sender_access
  inline:{ {$myhostname = DISCARD ...} }`), which over the network can only
  be a list's copy of the host's own user's post. On throwaway nodes, a
  post from one agent reached another member and the archive once each and
  did not reach the poster: the poster's own Postfix logged `NOQUEUE:
  discard`. Offboarding a member dropped it from the alias line, and
  offboarding the list took the row out of every directory. The list still
  sends the poster a copy; their own node drops it. `texthash` takes `key
  value` lines, not an aliases file's `key: value`: the first version did not
  match. Because `bin/team` lists every agent node, a post to a test list on
  a factory with a running team would have reached the real agents: I
  trimmed the test list by hand. One run, mail only, no model. Not tested:
  agents posting to it. (2026-10-02, Postfix 3.10.13.)
- **Mail waiting behind a turn was not in the Maildir, and a blocking lock
  did not fix that.** With the Maildir write and the `pi` command in one
  delivery, and Postfix's default of two local deliveries at a time per
  recipient, the third mail of a burst was not delivered until a slot freed;
  a wake-up that blocked on a lock held a slot. Five mails two seconds apart
  took three one-mail turns, and two had not reached the Maildir. A stand-in
  for `pi` that logs its prompt and sleeps 15 seconds. (2026-10-02.)
- **A non-blocking wake-up with a drain loop took a burst in one prompt.**
  The mail is written to the Maildir at once and then `wake` runs: the run
  that holds the lock loops (take every mail in `new`, oldest first, as one
  prompt; after the turn look again) and a run that finds the lock held
  exits. Five mails two seconds apart took two turns (1 mail, then 4); 19
  mails with random gaps took six turns (1, 4, 1, 6, 6, 1 mails) and each
  mail was shown exactly once, none missed or repeated, nothing left
  running. A `pi` that dies is still reported by Postfix ("Command died with
  status 1") to the sender of the mail whose run held the lock, not to the
  senders of the others in its batch. The same stand-in `pi`, 15-second
  turns. Not tested: a real model, or what a batch does to its answers.
  (2026-10-02.)

## Assumed, never tested

Choices we hold without a run behind them. Each stays here until a run or
a probe moves it above, or drops it.

- That the model works best on Debian, or on any particular OS.
- That each actor needs a machine of its own.
- That containers, and podman in particular, are the right runtime.
