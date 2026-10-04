# Questions

What we mean to find out next, in order. Each question is answered by a
run, read from the record (repository, mail, list, sessions), and its result
goes in `findings.md`; then it leaves this list.

## Where we are

The question so far: given a set of agents, can a scenario make the need to
coordinate, and to slice the work vertically, emerge in them, and can they
learn from it? Not yet, on one local model and one frame (`findings.md`,
Part I): they don't ask, don't talk, build the whole job each, and the
lessons they write change little in the next job.

## The bet

If a team learns well from its own failures, coordination and vertical
slicing may emerge as a consequence of learning, as they do in human teams:
the models are trained on human behaviour. This is a hypothesis; it belongs
under "Assumed, never tested" until a run shows it.

Learning has two levels, the individual's and the team's, and the questions
below take them in that order.

## 0. A frame that doesn't teach false lessons

Before any learning run, the faults in `findings.md` Part II are fixed or
controlled, so that what an agent learns comes from its work and not from
our frame:

- A mail delivered to an agent whose turn then fails comes back to its
  sender as "Undelivered"; two agents believed their PASS never arrived.
  The same notice is how a lead learned that a builder's turn died. To
  decide.
- A turn cut by the time limit leaves the work half done and nothing wakes
  the agent again. `wake` now goes on after a cut, up to twice; untested with
  a real model.
- A wrong address bounces only after the sender's turn ends, after it has
  reported the mail sent.
- Mail queued behind a turn arrives stale; mail queued on a node is lost when
  it restarts.
- With five agents on one model slot, turns die on "Request timed out" when
  the whole team wakes at once.
- A turn can end with no message and nothing to say why.

## 1. A baseline series

**Question.** How does the team do over a fixed series of needs, on today's
frame?

The same series is run again after each change below, so that every change is
measured against the same work and not against one run of a different job.
Every agent stays on the same local model throughout: a capped hosted model
turns some failures into quota failures, not behaviour.
The series is designed so that the same failures can recur: a fact split
between two agents, a shared layer, a contract with gaps, feedback after
delivery.

**Read from the record.** For each need: who asked whom, what was posted to
the list, work built twice or thrown away, false claims against the record,
verdicts, what reached the customer.

## 2. Individual learning

**Question.** Does better individual learning, with what pi offers (to be
checked: skills, skills the agent writes itself, anything like rules), make
a better factory over a continued delivery, not over one job?

**Read from the record.** Whether a failure an agent made once recurs in the
same agent later in the series; whether memory is read before work, and
after a compaction.

## 3. One mail, one session

**Question.** If individual learning is good, does a fresh session for every
mail do as well as one long session?

If it does, memory carries what the work needs, which is the open question of
how much of a product's theory can be written down for a fresh session to
reload. Depends on 2.

**Read from the record.** The baseline measures, against 2's.

## 4. Collective learning

**Question.** What does collective learning look like for agents? In good
human teams a lesson turns into an action: a change to the product, the
process, the frame. Does a team of agents turn its lessons into something it
shares and that holds, a check, a hook, a shared skill, an agreement a tool
enforces, and does that change the next job?

To decide first: which parts of the frame the team may change.

**Read from the record.** Commits that change the process after a
retrospective; whether the failure they address recurs.

## 5. Unlearning

**Question.** Does a team find and drop a lesson that is wrong?

**Read from the record.** Lessons in memory that the record contradicts, and
whether they are still there, and still acted on, later in the series.
