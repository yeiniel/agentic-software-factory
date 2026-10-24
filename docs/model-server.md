# Model server

What the hardware allows, what was tried, and what the current setup is.

## Hardware

- CPU: Intel i7-13650HX — 6 P-cores + 8 E-cores, 20 threads, AVX2 only (no AVX-512)
- RAM: 62 GB DDR5
- GPU: NVIDIA RTX 4050 Max-Q Mobile — 6 GB VRAM (PCIe 4.0 x8)
- Disk: 952 GB, ~280 GB free

The GPU is the binding constraint. With 6 GB VRAM only a fraction of any useful model fits on the GPU; the rest
runs in RAM over the CPU memory bus (~68 GB/s). That makes generation, not prompt processing, the cost of a Run:
across the Factory trials ~96% of the model's busy time was spent generating tokens, because the prompt cache hits on
almost every turn of an Agent's session (cached input was 10 to 50 times the new input).

## Current setup

`bin/model` starts `llama-server` (the `llama.cpp-cuda-git` package) as a transient user systemd unit with
**Ornith-1.5-35B-A3B**, `Q4_K_M` (`ornith-ai/Ornith-1.5-35B-A3B-GGUF`, 21.7 GB, MIT licence): a 35B mixture-of-experts
model with ~3B active parameters and a reasoning mode. The served name is `ornith-1.5-35b`, which must match
`ASF_MODEL_NAME`.

**Flags that matter for this hardware:**

- `-t 20`: all hardware threads. Generation scales with threads on this machine: one request decoded at 8.0 tok/s
  with `-t 10`, 10.4 with `-t 14` and 12.4 with `-t 20` (Qwen3-Coder-Next, same prompt), and a Factory pass at
  `-t 20` generated ~50% faster than at `-t 10`. The Agents' own test runs share the CPU, and the gain survived that.
- `-c 98304 -np 2`: 49,152 tokens per slot, two slots, one per concurrent Agent (the Implementor and the Acceptance
  Writer at the default `task_concurrency` of 1). Slots = `task_concurrency` x Agents per Task; a Graph with one
  Agent per Task (the experiment Graph) can run two Tasks. Pi's context window (`ASF_MODEL_CONTEXT_WINDOW`) must
  match the per-slot size. Two slots do not add throughput: two simultaneous requests share the speed of one
  (Ornith: 18.5 tok/s alone, 8.3 + 12.2 with two), so concurrency saves no total time, it only runs two roles at once.
- `--cache-type-k q8_0 --cache-type-v q8_0`: halves KV cache memory at long contexts. Measured KL divergence for
  Qwen3 at q8_0 is very low.
- `--fit on -fitt 256`: let llama.cpp maximise GPU layer offloading, keeping 256 MiB of VRAM free.
- `-fa on`, `--jinja`, `--cache-ram 24576`, `--metrics` (for the Console).
- `-ub 2048`: the physical batch size used in every trial from the first one. It makes no difference to generation
  and prompt processing is a small share of a Run; the earlier setting was 1024 and either is fine.

The Agents' output limit is `maxTokens` 8192 per turn in `images/agent/entrypoint.sh`, reasoning included. Over
~1,000 trial turns only two hit it (one Coder-Next, one Qwen3.6), so it is left alone.

## How models were compared

The comparison is Factory Runs, not prompts. Four small Tasks from two repositories (a trailing-slash fix in `ufo`,
a punycode fix in `pydantic-extra-types`, each at two commits) ran through the default Graph, one Task at a time,
with a 45-minute Agent timeout, so a candidate's result is the number of Tasks reaching `done`, the wall clock and
the turns. A faster Graph was also used to isolate the Implementor: `src/factory/graphs/implementor-golden` runs only
the Implementor against fixed golden specs (see its `README.md`). Everything was measured on the same machine in
October 2026; the samples are small (4 to 8 per candidate) and one Task alone ranged from 4 minutes to more than an hour
in the earlier baseline, so a difference smaller than about 2 of 8 is noise.

| Candidate | Tasks | Done | Green in the first Run | Wall clock per Task | Turns per Task |
|---|---|---|---|---|---|
| Qwen3-Coder-Next UD-IQ4_NL, `-t 10`, Implementor only | 8 | 3 | n/a | Implementor 1017 to 2678 s, 5 timeouts | 27 to 62 |
| Qwen3-Coder-Next, `-t 20`, Implementor only | 8 | 4 | n/a | 835 to 2501 s | 23 to 102 |
| Qwen3.6-35B-A3B UD-Q4_K_M, Implementor only | 8 | 8 | n/a | 116 to 534 s | 6 to 15 |
| Qwen3.6-35B-A3B, full Graph | 12 | 10 | 7 | 288 to 1412 s | 13 to 62 |
| **Ornith-1.5-35B Q4_K_M, full Graph** | 8 | 8 | 7 | 183 to 1129 s (median ~540) | 15 to 40 |
| Flint UD-Q4_K_XL, full Graph | 4 | 4 | 4 | 707 to 1609 s | 18 to 34 |
| Laguna-XS-2.1 Q4_K_M, full Graph | 4 | 4 | 3 | 1120 to 3511 s | 72 to 119 |
| Qwen3-Coder-REAP-25B-A3B Q6_K | 0 | n/a | n/a | not run: 6 tok/s | n/a |

- **Ornith** was the most consistent, so it is the choice; Qwen3.6 is close and within noise.
- **Qwen3-Coder-Next** (the 80B model used for the first baseline) was 3 to 4 times slower per Task and timed out
  often: its generation is 12.4 tok/s at best on this machine against 18.5 for the 35B models, and each Task needed
  more turns. It also produced the only malformed tool calls (`Failed to parse tool call arguments as JSON`, a 500
  from the server that ends the Agent's attempt).
- **Flint** is correct but slow: 25 to 27k output tokens per Task against 3 to 15k for Ornith, and 14.3 tok/s per
  request. It needs a `llama.cpp` newer than the installed `b11647` (support merged 2026-10-21, tested on master at
  `9ae73e6`); the open tool-call bug (llama.cpp issue 31000) did not appear under Pi.
- **Laguna** decodes as fast as Ornith but needed 3 to 5 times the turns and the Acceptance Writer often took more
  than 30 minutes, so Tasks were 1120 to 3511 s.
- **REAP-25B** at Q6_K decodes at 6 tok/s (3 times slower than the 35B models): the Q6_K file moves about half as many
  more bytes per token and it did not earn a Factory pass. A smaller quant of it was not tried.
- Most of the Tasks that stopped `blocked` did so after both Agents finished: the Acceptance Writer's spec and the
  Implementor's code disagreed on an edge case the Task text leaves open, and the second Run re-ran only the
  Implementor against the same spec. That is a Graph property, not a model-server one.

### Decode speed

One request, a fixed ~9k-token uncached prompt, 200 generated tokens, `-ub 2048`. These are screening numbers; the
table above decides.

| Model | `-t` | 1 request (tok/s) | 2 simultaneous (tok/s each) |
|---|---|---|---|
| Qwen3-Coder-Next UD-IQ4_NL | 10 | 8.0 | 3.8, 4.7 |
| Qwen3-Coder-Next | 20 | 12.4 | 6.1, 5.1 |
| Qwen3.6-35B-A3B Q4_K_M, `b11660` | 20 | 17.0 | 10.7, 7.5 |
| Qwen3.6-35B-A3B Q4_K_M, master `9ae73e6` | 20 | 18.6 | 8.2, 11.9 |
| Ornith-1.5-35B Q4_K_M, `b11647` | 20 | 18.2 | 11.7, 8.1 |
| Ornith-1.5-35B Q4_K_M, master `9ae73e6` | 20 | 18.5 | 8.3, 12.2 |
| Laguna-XS-2.1 Q4_K_M, master | 20 | 19.0 | 7.8, 12.0 |
| Flint UD-Q4_K_XL, master | 20 | 14.3 | 8.7, 11.0 |
| Qwen3-Coder-REAP-25B-A3B Q6_K, master | 20 | 6.1 | 2.9, 3.4 |

The newer `llama.cpp` was ~9% faster on Qwen3.6 and made no difference for Ornith, so the Factory stays on the
installed package; it is only needed for Flint. Generation slows as the context grows (Qwen3.6: 31 tok/s near empty,
10 at 47k, 5 at 97k, from an earlier measurement); long-context speed was not re-measured for Ornith.

## Earlier measurements (before the Factory comparison)

Qwen3-Coder-Next, 3,568-token prompt, 128 tokens, greedy, two slots; differences under ~7% are noise:

| Flags (besides the base ones) | Prompt tok/s | Gen tok/s, 1 request | VRAM |
|---|---|---|---|
| base: `-c 196608` | 182 | 12.5 | 4.55 GB |
| `-c 98304` | 189 | 16.7 | 4.7 GB |
| `-c 98304 -fitt 256` | 193 | 18.3 | 5.5 GB |
| `-c 98304 -fitt 256 -ub 1024` | 284 | 18.1 | 5.4 GB |
| base + `-ub 2048` | 412 | 8.1 | 4.6 GB |
| base + `-lm none` (no mmap) | 201 | 11.0 | 4.6 GB |
| base + `-tb 14` | 181 | 12.5 | 4.6 GB |

Qwen3.5-9B (a distilled reasoning model) was too weak for agentic work: repeated failing commands, invented results.

## Not tried

- **Quants of Coder-Next below `UD-IQ4_NL`** (for example `UD-IQ3_XXS`) and **other quants of the 35B models**: Coder-Next
  was dropped on speed and quality of Runs, and the 35B models already run fast.
- **Expert placement and cache flags** (`--n-cpu-moe`, `--moe-cache-mib`) and **KV cache in f16**: decode, not prefill, is
  the cost, and these were not varied.
- **Speculative decoding (MTP, n-gram)**: MTP needs `-np 1` for Qwen3.6 and its other combinations with `-np 2` were
  not checked.
- **Pruned variants beyond REAP-25B** (for example the ISTA Qwen3.8-Flash-Next coder, which loops at long context and has
  an unclear licence).
- **A harder Task set.** All four Tasks are small fixes (one to nine lines); the results say little about large changes.
- **Long-context behaviour of Ornith** (past ~47k tokens per slot).
