import sys
import json
from llm_client import call_llm, get_token_stats
from spec_synth import run_ast_extractor, synthesize_specs

def explore_interleavings(ast_data: dict, spec_result: dict) -> dict:
    sys_prompt = (
        "You are an expert Go concurrency verifier using Rely-Guarantee reasoning. "
        "Given the Go source code, synchronization primitives, and top-down Rely-Guarantee specs, "
        "determine whether a concurrent interleaving can violate any caller expectation or invariant. "
        "Explicitly check: (1) check-then-act / split-lock gaps across callers and callees, "
        "(2) reentrant RWMutex.RLock() calls that deadlock when a concurrent writer calls Lock(), "
        "(3) time.Timer.Reset() without draining timer.C when Stop() returns false, "
        "(4) premature pool/resource release before final field mutation, and "
        "(5) non-idempotent sync.Once caching transient errors. "
        "Conversely, do NOT flag unexported helpers if their top-down caller holds the protecting mutex, "
        "and do NOT flag mutex-free maps/slices strictly confined to a single actor goroutine via channels. "
        "Output ONLY a valid JSON object."
    )

    user_prompt = (
        f"Package: {ast_data['package']}\n"
        f"Structs: {json.dumps(ast_data.get('structs', []))}\n"
        f"Functions & Sync Ops:\n{json.dumps(ast_data['functions'], indent=2)}\n\n"
        f"Synthesized Rely-Guarantee Specs:\n{json.dumps(spec_result['specs'], indent=2)}\n\n"
        "Analyze whether concurrent calls to the exported/caller entrypoints can break any Rely-Guarantee contract.\n"
        "Return a JSON object with:\n"
        '  "vulnerable": true or false,\n'
        '  "bug_category": "Atomicity Violation | Deadlock | Channel Bug | Condition Variable Bug | Data Race | WaitGroup Misuse | Goroutine Leak | None",\n'
        '  "violated_contract": "Exact caller expectation or invariant violated, or None if safe",\n'
        '  "interleaving_schedule": [\n'
        '    {"step": 1, "goroutine": "G1", "action": "function call & line/lock event"},\n'
        '    {"step": 2, "goroutine": "G2", "action": "interleaving action that breaks Rely condition"}\n'
        '  ],\n'
        '  "test_strategy": "How to deterministically trigger and assert this failure in a Go _test.go file (e.g., concurrent goroutines with barrier/channel sync checking post-state invariant or timeout for deadlock)",\n'
        '  "repair_suggestion": "Concrete Go code fix"\n'
    )

    raw = call_llm(sys_prompt, user_prompt, json_mode=True)
    verdict = json.loads(raw)
    return {
        "package": ast_data["package"],
        "file": ast_data["file"],
        "mode": spec_result["mode"],
        "specs": spec_result["specs"],
        "analysis": verdict,
        "token_stats": get_token_stats()
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 engine/schedule_explorer.py <path-to-target.go> [caller-driven|impl-only]")
        sys.exit(1)
    target = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "caller-driven"
    ast_json = run_ast_extractor(target)
    specs = synthesize_specs(ast_json, mode=mode)
    out = explore_interleavings(ast_json, specs)
    print(json.dumps(out, indent=2))