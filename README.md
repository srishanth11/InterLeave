# InterLeave: Automated Concurrency Verification & Interleaving-Guided Test Synthesis for Go

**InterLeave** is a hybrid static-dynamic concurrency verification framework for Go packages. It combines Go `go/ast` structural extraction, LLM-synthesized **Caller-Driven Rely-Guarantee (RG)** specifications, deterministic AST-validated interleaving exploration, and automated reproducible Go test generation (`go test -race`).

## Architecture

1. **AST Structural & Concurrency Extractor (`go_ast_extractor/`):**
   Parses target Go packages using `go/ast` and `go/parser` to extract shared struct/global state, synchronization primitives (`sync.Mutex`, `sync.RWMutex`, `sync.Cond`, `sync.Once`, `sync.WaitGroup`, `atomic`, channels), lock acquisition sequences, and exported API entry points.
2. **Caller-Driven Rely-Guarantee Specification Synthesizer (`engine/spec_synth.py`):**
   Generates >=10 candidate Rely-Guarantee contracts (caller assumptions, state invariants, atomic region expectations, and lock-ordering obligations) per package and grades them against ground-truth concurrency contracts.
3. **AST-Validated Schedule Explorer (`engine/schedule_explorer.py`):**
   Identifies high-risk multi-goroutine interleavings that violate inferred RG contracts and validates every candidate schedule against extracted AST methods and synchronization primitives to prune hallucinated operations.
4. **Reproducible Concurrency Test Generator (`engine/test_gen.py`):**
   Synthesizes standalone `_test.go` stress and barrier-guided harnesses, verifies compilation (`go test -c`), executes under `go test -race`, measures Time-to-First-Failure (TTFF), and classifies bugs as **Deterministic** or **Probabilistic** across 5 repeated trials.

## Benchmark Suite (`benchmarks/`)

- **Seeded Suite (`b01`–`b18` Buggy, `c01`–`c08` Safe — 26 Packages):** Covers lost updates, check-then-act TOCTOU races, lock-order deadlocks, RWMutex upgrades, lost `sync.Cond` wakeups, broken double-checked locking, WaitGroup misuse, context leaks, slice aliasing, double transfers, pool poisoning, `sync.Once` fallback races, pub/sub races, timer resets, and safe concurrency patterns.
- **AI-Generated Code Suite (`ai01`–`ai04` — 4 Packages):** Evaluates generalization on unseen LLM-authored concurrent Go modules (`ai01_ratelimiter`, `ai02_cacheclose`, `ai03_safecircuit`, `ai04_safebatch`).

## Reproducing the Evaluation

```bash
# Set an LLM provider key (Gemini, Groq, OpenAI, or Anthropic)
export GEMINI_API_KEY="your-api-key"

# Run full uncached evaluation (resumes automatically from results/fresh_checkpoint.json)
python3 engine/run_eval.py --fresh