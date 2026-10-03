# agentic-software-factory

A small software factory built from what Unix already has: nodes that talk by
mail, work on shared code in git, and are run by AI agents. It is an experiment, not a product. What it has shown so far is in
[`docs/findings.md`](docs/findings.md); the principles it follows are in
[`docs/principles.md`](docs/principles.md).

## The idea

- **A node is one container with one process.** Each runs Postfix, and its
  hostname is `NAME.factory`. Mail for `USER@NAME.factory` is kept in the
  user's `~/Maildir`.
- **An agent is woken by mail.** The agent's `~/.forward` runs `wake`, which
  shows every waiting mail to `pi`, the agent harness, as one prompt. There
  is one pi session per agent; if a turn stops short (the 90-minute limit, or a
  failure on the model such as a rate limit), the agent is told and goes on after
  a pause, up to three times.
- **A seat is a node for a person.** Same mail, no agent.
- **One shared repository,** on a repo node. Every push runs a check
  (`make check`) and mails the verdict to whoever made the commit.
- **A list node** is the team's town hall: a mailing list anyone can join.
- **The model** is not part of the repository: `pi` can use any model and any
  way of serving it, and each agent's model configuration is part of `config/`.

## Layout

| Path | What it is |
| --- | --- |
| `images/` | One container definition per kind of node (`mail`, `seat`, `agent`, `repo`, `list`). Configuration is files under each image's `rootfs/`, copied to `/`. |
| `bin/` | The tools that drive it: `build`, `onboard`, `offboard`, `up`, `down`, `repo`, `team`, `watch`. Each starts with a comment saying what it does. |
| `examples/` | A config to start from (see below). |
| `docs/` | `principles.md`, and `findings.md`: only what a recorded run or probe showed. |

Not in the repository: `state/` (every node's home, mail and sessions) and
`offboarded/` (nodes taken out). Also not versioned is `config/`, which depends
on the machine and on the state of the factory; [`examples/config/`](examples/config)
is a config to start from.

## The config

`bin/onboard` reads everything about a node from `config/`:

| File | What it is |
| --- | --- |
| `node.container`, `node.volume` | Templates for a node's Quadlet units. `@NAME@`, `@KIND@`, `@IMAGE@`, `@ACCOUNT@` and `@DIR@` are filled in for each node. |
| `KIND/kind` | What a kind of node is: the image and the account it runs (`IMAGE=asf-agent`, `ACCOUNT=agent`). The folders are the kinds `bin/onboard` accepts. |
| `KIND/home/` | Files added to a node's home after its first start. |
| `agent/home/.pi/agent/models.json` | How agents reach their model: any server `pi` can use. The example has placeholders (`PORT`, `MODEL-ID`) for you to fill in. |

## Running it

It needs rootless podman with Quadlet and a model server that the nodes can
reach.

    cp -r examples/config config      # then edit config/agent/home/.pi/agent/models.json
    bin/build                         # build the images
    bin/onboard repo repo             # a node: bin/onboard NAME KIND
    bin/onboard townhall list
    bin/onboard you seat              # a seat for a person
    bin/onboard ana agent             # an agent
    bin/repo repo hub                 # a shared repository: git://repo.factory/hub.git
    bin/watch                         # one live stream of the whole factory

`bin/onboard` also tells every agent who is on the team (`bin/team`). To reach
an agent, mail it from a seat: `mail -s "subject" agent@ana.factory`.

`bin/down` stops every node and `bin/up` starts them again; nothing is lost,
since each home lives in `state/`.
