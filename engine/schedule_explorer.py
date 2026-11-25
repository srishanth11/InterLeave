import sys
import json
from llm_client import call_llm, get_token_stats
from spec_synth import run_ast_extractor, synthesize_specs

def validate_schedule_against_ast(schedule_steps: list, ast_data: dict) -> dict:
    valid_funcs = {f["name"] for f in ast_data.get("functions", [])}
    valid_structs = {s["name"] for s in ast_data.get("structs", [])}
    valid_symbols = valid_funcs | valid_structs

    validated_steps = []
    invalid_reasons = []

    for step in schedule_steps:
        if not isinstance(step, dict):
            continue
        fn_ref = step.get("function", "").strip()
        short_fn = fn_ref.split(".")[-1] if "." in fn_ref else fn_ref
        if short_fn and short_fn in valid_symbols:
            validated_steps.append(step)
        elif any(sym in step.get("action", "") for sym in valid_symbols):
            validated_steps.append(step)
        else:
            invalid_reasons.append(f"Unresolved symbol '{fn_ref}' in step {step.get('step')}")

    is_valid = len(validated_steps) >= 2 and len(invalid_reasons) == 0
    return {
        "valid": is_valid,
        "validated_steps": validated_steps,
        "rejected_reasons": invalid_reasons
    }

def explore_interleavings(ast_data: dict, spec_result: dict) -> dict:
    sys_prompt = (
        "You are an expert Go concurrency verifier using Rely-Guarantee reasoning. "
        "Given the Go source code, synchronization primitives, and Rely-Guarantee specs, "
        "propose up to 4 concrete candidate goroutine interleaving schedules to test whether any "
        "caller expectation or invariant can be violated. "
        "Explicitly check: (1) check-then-act / split-lock gaps across callers and callees, "
        "(2) reentrant RWMutex.RLock() calls that deadlock when a concurrent writer calls Lock(), "
        "(3) time.Timer.Reset() without draining timer.C when Stop() returns false, "
        "(4) premature pool/resource release before final field mutation, "
        "(5) non-idempotent sync.Once caching transient errors, and "
        "(6) channel close/send races, WaitGroup Add/Wait races, and Cond lost wakeups. "
        "Conversely, do NOT flag unexported helpers if their top-down caller holds the protecting mutex, "
        "and do NOT flag mutex-free maps/slices strictly confined to a single actor goroutine via channels. "
        "Every step in every schedule MUST reference exact function/method names from the package AST. "
        "Output ONLY a valid JSON object."
    )

    user_prompt = (
        f"Package: {ast_data['package']}\n"
        f"Structs: {json.dumps(ast_data.get('structs', []))}\n"
        f"Functions & Sync Ops:\n{json.dumps(ast_data['functions'], indent=2)}\n\n"
        f"Synthesized Rely-Guarantee Specs:\n{json.dumps(spec_result['specs'], indent=2)}\n\n"
        "Return a JSON object with:\n"
        '  "vulnerable": true or false,\n'
        '  "bug_category": "Atomicity Violation | Deadlock | Channel Bug | Condition Variable Bug | Data Race | WaitGroup Misuse | Goroutine Leak | None",\n'
        '  "violated_contract": "Exact caller expectation or invariant violated, or None if safe",\n'
        '  "candidate_schedules": [\n'
        '    {\n'
        '      "schedule_id": "SCHED-1",\n'
        '      "description": "Concise description of adversarial interleaving",\n'
        '      "synchronization_mechanism": "barrier | staggered_sleep | deadlock_timeout | panic_recovery | concurrent_stress",\n'
        '      "steps": [\n'
        '        {"step": 1, "goroutine": "G1", "function": "<ExactFuncName>", "action": "..."},\n'
        '        {"step": 2, "goroutine": "G2", "function": "<ExactFuncName>", "action": "..."}\n'
        '      ],\n'
        '      "oracle_assertion": "Exact Go assertion proving invariant failure"\n'
        '    }\n'
        '  ],\n'
        '  "repair_suggestion": "Concrete Go code fix"\n'
    )

    raw = call_llm(sys_prompt, user_prompt, json_mode=True)
    verdict = json.loads(raw)
    if isinstance(verdict, list):
        verdict = verdict[0] if (verdict and isinstance(verdict[0], dict)) else {"vulnerable": False}
    elif not isinstance(verdict, dict):
        verdict = {"vulnerable": False}

    raw_schedules = verdict.get("candidate_schedules", [])
    if not isinstance(raw_schedules, list):
        raw_schedules = []

    validated_schedules = []
    for sched in raw_schedules:
        if not isinstance(sched, dict):
            continue
        val = validate_schedule_against_ast(sched.get("steps", []), ast_data)
        sched_record = dict(sched)
        sched_record["ast_valid"] = val["valid"]
        sched_record["validated_steps"] = val["validated_steps"]
        sched_record["rejected_reasons"] = val["rejected_reasons"]
        if val["valid"]:
            validated_schedules.append(sched_record)

    if not validated_schedules and raw_schedules:
        first_valid_dict = next((s for s in raw_schedules if isinstance(s, dict)), None)
        if first_valid_dict:
            validated_schedules = [first_valid_dict]

    primary_steps = validated_schedules[0].get("validated_steps", []) if validated_schedules else []
    verdict["interleaving_schedule"] = primary_steps
    verdict["proposed_schedule_count"] = len(raw_schedules)
    verdict["validated_schedule_count"] = len(validated_schedules)
    verdict["validated_schedules"] = validated_schedules

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