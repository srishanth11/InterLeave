import os
import sys
import json
import time
import subprocess
from llm_client import call_llm, get_token_stats
from spec_synth import run_ast_extractor, synthesize_specs
from schedule_explorer import explore_interleavings

REPRO_ATTEMPTS = 5

def _strip_fences(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        code = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
    return code

def _build_only_check(pkg_dir: str) -> tuple:
    rel_pkg = "./" + os.path.basename(pkg_dir)
    proc = subprocess.run(
        ["go", "test", "-race", "-c", "-o", os.devnull, rel_pkg],
        cwd="benchmarks",
        capture_output=True,
        text=True
    )
    err_out = (proc.stdout + "\n" + proc.stderr).strip()
    return (proc.returncode == 0), err_out

def _run_single_test_execution(pkg_dir: str) -> tuple:
    rel_pkg = "./" + os.path.basename(pkg_dir)
    proc = subprocess.run(
        ["go", "test", "-race", "-count=1", "-timeout", "5s", "-run", "TestInterleaveGuardAudit", rel_pkg],
        cwd="benchmarks",
        capture_output=True,
        text=True
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    bug_witnessed = proc.returncode != 0 and (
        "--- FAIL:" in output
        or "DATA RACE" in output
        or "panic:" in output
        or "test timed out" in output
        or "fatal error:" in output
    )
    return bug_witnessed, proc.returncode, output

def generate_and_run_test(ast_data: dict, explorer_result: dict, keep_test: bool = False) -> dict:
    pkg = ast_data["package"]
    target_path = ast_data["file"]
    pkg_dir = os.path.dirname(target_path)
    gen_test_path = os.path.join(pkg_dir, "interleaveguard_gen_test.go")

    full_src = ast_data.get("full_source") or "\n".join(f["code"] for f in ast_data["functions"])
    schedules = explorer_result["analysis"].get("validated_schedules", [])
    if not schedules:
        schedules = [{"schedule_id": "SCHED-DEFAULT", "description": "Default concurrent stress", "steps": []}]

    sys_prompt = (
        "You are an expert Go concurrency test engineer. Write a self-contained Go test file that compiles cleanly "
        "against the target package and deterministically reproduces the concurrency bug described in the schedule. "
        "Output ONLY valid Go source code (no markdown fences, no commentary)."
    )

    t_start = time.time()
    time_to_first_failure = None
    interleavings_executed = 0
    compiled = False
    executed = False
    bug_witnessed = False
    best_go_code = ""
    last_output = ""
    last_exit_code = -1
    winning_schedule_id = None

    try:
        is_pred_vuln = bool(explorer_result["analysis"].get("vulnerable", False))
        for sched in (schedules[:2] if is_pred_vuln else schedules[:1]):
            interleavings_executed += 1
            user_prompt = (
                f"Package name: {pkg}\n"
                f"Complete target.go source code:\n```go\n{full_src}\n```\n\n"
                f"Vulnerability Analysis:\n{json.dumps(explorer_result['analysis'], indent=2)}\n\n"
                f"Target Interleaving Schedule ({sched.get('schedule_id')}):\n{json.dumps(sched, indent=2)}\n\n"
                "Write `interleaveguard_gen_test.go` following these strict Go rules:\n"
                f"1. Start with `package {pkg}`.\n"
                "2. Import ONLY standard library packages actually used in the test (never leave unused imports).\n"
                "3. Define `func TestInterleaveGuardAudit(t *testing.T)`.\n"
                "4. Use `chan struct{}` barriers, `runtime.Gosched()`, and/or staggered `time.Sleep(5 * time.Millisecond)` across 2+ goroutines in a loop of 40 iterations to force the exact interleaving in the schedule.\n"
                "5. Bug-specific oracle rules:\n"
                "   - For Deadlocks / Lost Wakeups: run operations in goroutines and fail via `select { case <-done: case <-time.After(750 * time.Millisecond): t.Fatalf(\"deadlock detected\") }` so the test fails fast rather than hanging.\n"
                "   - For Channel close/send races: execute concurrent send + close without recovering panics (an unrecovered panic proves the bug) or fail if panic occurs.\n"
                "   - For `time.Timer` reset races: let initial timer expire, call `Kick`/`Reset`, and verify `WaitExpired` does not return in `< 50ms`.\n"
                "   - For `sync.Once` error poisoning: call once with failure (`true`), then call again with healthy input (`false`) and call `t.Fatalf` if cached error persists.\n"
                "   - For Atomicity / TOCTOU / Pool / Conservation bugs: check exact post-state invariant (e.g. negative balance, over-allocation, `a+b != total`, dirty flag) and call `t.Fatalf`.\n"
                "   - For Safe packages: verify invariants hold across 40 concurrent iterations without false failures.\n"
                "6. Output ONLY raw Go code starting with `package `."
            )

            go_code = _strip_fences(call_llm(sys_prompt, user_prompt, json_mode=False))

            # Build-only validation + up to 2 compiler-feedback repair attempts
            sched_compiled = False
            build_err = ""
            for _repair in range(2):
                with open(gen_test_path, "w", encoding="utf-8") as f:
                    f.write(go_code + "\n")
                sched_compiled, build_err = _build_only_check(pkg_dir)
                if sched_compiled:
                    break
                repair_prompt = (
                    f"The Go test file failed `go test -c` compilation with:\n{build_err}\n\n"
                    f"Target source:\n```go\n{full_src}\n```\n\n"
                    f"Broken test code:\n```go\n{go_code}\n```\n\n"
                    "Fix all compilation errors (imports, types, signatures) and output ONLY valid raw Go code."
                )
                go_code = _strip_fences(call_llm(sys_prompt, repair_prompt, json_mode=False))

            best_go_code = go_code
            if not sched_compiled:
                last_output = f"BUILD FAILED:\n{build_err}"
                last_exit_code = 2
                continue

            compiled = True
            witnessed, rc, out = _run_single_test_execution(pkg_dir)
            executed = True
            last_output = out
            last_exit_code = rc

            if witnessed:
                bug_witnessed = True
                winning_schedule_id = sched.get("schedule_id")
                time_to_first_failure = round(time.time() - t_start, 3)
                break

        # Reproducibility evaluation across REPRO_ATTEMPTS repeated runs
        repro_successes = 0
        if compiled and executed:
            if bug_witnessed:
                repro_successes = 1
                for _ in range(REPRO_ATTEMPTS - 1):
                    w_rep, _, _ = _run_single_test_execution(pkg_dir)
                    if w_rep:
                        repro_successes += 1
            else:
                # Confirm whether repeated runs ever trigger a probabilistic failure
                for _ in range(REPRO_ATTEMPTS - 1):
                    w_rep, rc_rep, out_rep = _run_single_test_execution(pkg_dir)
                    if w_rep:
                        repro_successes += 1
                        bug_witnessed = True
                        last_exit_code = rc_rep
                        last_output = out_rep
                        if time_to_first_failure is None:
                            time_to_first_failure = round(time.time() - t_start, 3)

        repro_rate_pct = round((repro_successes / REPRO_ATTEMPTS) * 100.0, 1) if (compiled and executed) else 0.0
        if repro_successes == REPRO_ATTEMPTS:
            repro_type = "Deterministic"
        elif repro_successes > 0:
            repro_type = "Probabilistic"
        else:
            repro_type = "Unreproduced"

    finally:
        if not keep_test and os.path.exists(gen_test_path):
            os.remove(gen_test_path)

    return {
        "package": pkg,
        "compiled": compiled,
        "executed": executed,
        "bug_witnessed_by_test": bug_witnessed,
        "winning_schedule_id": winning_schedule_id,
        "interleavings_considered": explorer_result["analysis"].get("proposed_schedule_count", len(schedules)),
        "interleavings_validated": explorer_result["analysis"].get("validated_schedule_count", len(schedules)),
        "interleavings_executed": interleavings_executed,
        "time_to_first_failure_sec": time_to_first_failure,
        "reproducibility": {
            "attempts": REPRO_ATTEMPTS if (compiled and executed) else 0,
            "successful_reproductions": repro_successes,
            "reproduction_rate_pct": repro_rate_pct,
            "classification": repro_type
        },
        "llm_predicted_vulnerable": explorer_result["analysis"].get("vulnerable", False),
        "test_exit_code": last_exit_code,
        "test_output": last_output[:1500],
        "generated_test_code": best_go_code,
        "token_stats": get_token_stats()
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 engine/test_gen.py <path-to-target.go> [--keep]")
        sys.exit(1)
    target = sys.argv[1]
    keep = "--keep" in sys.argv
    ast_json = run_ast_extractor(target)
    specs = synthesize_specs(ast_json, mode="caller-driven")
    explored = explore_interleavings(ast_json, specs)
    res = generate_and_run_test(ast_json, explored, keep_test=keep)
    print(json.dumps(res, indent=2))