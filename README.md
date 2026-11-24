# InterleaveGuard: Automated Concurrency Vulnerability Auditing for Go via Top-Down Rely-Guarantee Synthesis

**InterleaveGuard** is a formal concurrency auditing pipeline for Go programs that detects high-level logical concurrency bugs—such as split-lock atomicity violations, check-then-act (TOCTOU) gaps, reentrant `sync.RWMutex` deadlocks, and undrained `time.Timer` resets—that pass Go's built-in dynamic race detector (`go test -race`) without triggering data races.

By combining static Go AST/call-graph extraction (`go/ast`), **top-down caller-driven Rely-Guarantee ($\langle R, G \rangle \vdash \{P\}\ C\ \{Q\}$) specification synthesis**, and **compilation-gated deterministic Go test generation**, InterleaveGuard distinguishes genuine concurrency vulnerabilities from intentional caller-enforced synchronization.

---

## Architecture Overview

```text
Target Go Package (benchmarks/*/target.go)
       │
       ▼
1. Go AST & Sync Analyzer (analyzer/extract.go)
   └─ Extracts structs, line ranges, caller/callee edges, and sync primitives
       │
       ▼
2. Top-Down RG Spec Synthesizer (engine/spec_synth.py)
   └─ Kahn's topological layering (Layer 0 callers -> Layer k callees)
   └─ Synthesizes <R, G> |- {P} C {Q} + expected_callees obligations
       │
       ▼
3. Interleaving Schedule Explorer (engine/schedule_explorer.py)
   └─ Checks caller-callee contract discharge & Go concurrency invariants
       │
       ▼
4. Deterministic Witness Test Generator (engine/test_gen.py)
   └─ Emits interleaveguard_gen_test.go with channel start barriers
   └─ Executes `go test -race -timeout 5s` with compilation gating
       │
       ▼
5. Audit Reporter & Evaluation Harness (engine/reporter.py, engine/run_eval.py)
   └─ Outputs results/eval_summary.json & results/report.md