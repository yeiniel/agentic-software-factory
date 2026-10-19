# Model server

What the hardware allows, what was tried, and what the current setup is.

## Hardware

- CPU: Intel i7-13650HX — 6 P-cores + 8 E-cores, 20 threads, no AVX-512
- RAM: 62 GB DDR5
- GPU: NVIDIA RTX 4050 Max-Q Mobile — 6 GB VRAM, ~192 GB/s bandwidth
- Disk: 952 GB, ~350 GB free

The GPU is the binding constraint. With 6 GB VRAM only a fraction of any
useful model fits on the GPU; the rest runs in RAM over the CPU memory bus
(~68 GB/s). This sets a ceiling on generation speed: at Q4_K_M a 22 GB
model requires ~22 GB / 68 GB/s ≈ 0.32 s per token in the worst case
(single-threaded, no GPU), which is ~3 tok/s. In practice the GPU handles
what fits and the real ceiling is higher, around 15–20 tok/s for the models
tried here.

## Models tried

**qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2** (9B distilled, LM
Studio, earlier repository): too weak for agentic coding work — repeated
failing commands, invented results, could not recover from missing
dependencies.

**Qwen3.6-35B-A3B** (35B MoE, 3.6B active, `unsloth/Qwen3.6-35B-A3B-GGUF`,
UD-Q4_K_M, ~22 GB): strong enough for multi-agent runs. Used in all
experiments in this repository. Generation speed drops with context: ~31
tok/s at near-empty, ~10 tok/s at 47k, ~5 tok/s at 97k (blog, October
2026).

**Qwen3-Coder-REAP-25B-A3B** (25B MoE, 3B active, Cerebras REAP — 20%
expert pruning of Qwen3-Coder-30B-A3B-Instruct, `bartowski/
cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF`, Q6_K, ~20 GB): coding-
specialised, higher quant level. Benchmarked only at short context; not
yet tested on agent runs.

**Qwen3-Coder-Next** (80B total MoE, 3B active, 512 experts,
`unsloth/Qwen3-Coder-Next-GGUF`, UD-IQ4_NL, ~37 GB on disk): largest
model that fits in 62 GB RAM at a reasonable quant. Stronger coding model
than the 35B/25B class. VRAM usage is similar (~4.5 GB) because `--fit`
offloads a comparable number of layers; the speed penalty comes from more
total layers reading through RAM. Benchmarked only at short context (see
below).

## Server configuration

`bin/model` starts `llama-server` as a transient user systemd unit.

**Flags that matter for this hardware:**

- `-t 10`: use P-cores and some E-cores. `-t 4` (the earlier default) left
  most of the CPU idle and cost ~30% throughput.
- `--cache-type-k q8_0 --cache-type-v q8_0`: halves KV cache memory at
  long contexts, freeing RAM for more GPU-offloaded layers. Measured KL
  divergence for Qwen3 at q8_0 is very low (near-lossless).
- `--fit on`: let llama.cpp maximise GPU layer offloading automatically.
- `-fa on`: flash attention.
- `-c 294912 -np 3`: 98,304 tokens per slot, three slots — one per
  concurrent agent role.

## Benchmarks (2026-10-11, 150-token completion, near-empty context)

| Model | Flags | tok/s (warm) |
|---|---|---|
| Qwen3.6-35B-A3B UD-Q4_K_M | `-t 4`, no KV quant (original) | ~12.9 |
| Qwen3.6-35B-A3B UD-Q4_K_M | `-t 10`, q8_0 KV | ~18.2 |
| Qwen3-Coder-REAP-25B-A3B Q6_K | `-t 10`, q8_0 KV | ~15.3 |
| Qwen3-Coder-Next 80B UD-IQ4_NL | `-t 10`, q8_0 KV | ~10.2 |

Speed observations:
- REAP is ~3 tok/s slower than the tuned Qwen3.6 despite fewer parameters,
  because Q6_K costs more compute per weight than Q4_K_M.
- Qwen3-Coder-Next is ~44% slower than the tuned Qwen3.6. VRAM usage is
  similar across all three (~4.5 GB); the penalty comes from more total
  layers traversed in RAM per token.
- Speed at longer contexts has not been re-measured; expect a similar
  drop pattern to Qwen3.6 (31→10→5 tok/s at empty/47k/97k).
- Quality on real agent tasks has not been compared across models yet.

## Other coding models that fit this hardware

Surveyed 2026-10-11. All are MoE with ~3B active parameters.

| Model | SWE-bench Verified | Size @Q4_K_M | Notes |
|---|---|---|---|
| Qwen3-Coder-30B-A3B | — | ~19 GB | Unpruned base of REAP; useful control |
| Laguna XS 2.1 (Poolside) | 70.9% | ~19 GB | Agentic/long-horizon focus, 262k ctx, OpenMDW-1.1 |
| North Mini Code 1.0 (Cohere) | 67.6% | ~19 GB | Apache 2.0 |

SWE-bench figures are vendor-reported with different harnesses; treat as
directional only.

## Paths not yet explored

- **Speculative decoding (MTP)**: Qwen3.6 has a dedicated MTP GGUF
  (`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`); flags `--spec-type draft-mtp
  --spec-draft-n-max 2`. Requires `-np 1` — incompatible with three-slot
  operation. No net speedup measured on this model in at least one external
  benchmark.
- **Expert caching (`llama-moe-cache` fork)**: keeps hot experts in VRAM,
  cold in RAM. Reported ~2× on Qwen3-30B-A3B on an RTX 4070 Ti (12 GB).
  Very early stage (9 stars); prompt eval is 4× slower; not tested here.
- **More aggressive expert pruning**: REAP has a 50%-pruned variant of
  Qwen3-Coder-480B (246B-A35B) — too large for this machine. No 50%-pruned
  variant of the 30B model exists yet.
