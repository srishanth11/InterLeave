import os
import sys
import json
import subprocess
from llm_client import call_llm, get_token_stats
from spec_synth import run_ast_extractor, synthesize_specs
from schedule_explorer import explore_interleavings

def generate_and_run_test(ast_data: dict, explorer_result: dict, keep_test: bool = False) -> dict:
    pkg = ast_data["package"]
    target_path = ast_data["file"]
    pkg_dir = os.path.dirname(target_path)
    gen_test_path = os.path.join(pkg_dir, "interleaveguard_gen_test.go")

    sys_prompt = (
        "You are an expert Go test engineer. Write a self-contained Go test file that compiles cleanly "
        "against the target package and deterministically tests the concurrency invariant described. "
        "Output ONLY valid Go source code (no markdown fences, no commentary)."
    )

    user_prompt = (
        f"Package name: {pkg}\n"
        f"Target file source code:\n"
        + "\n".join(f["code"] for f in ast_data["functions"])
        + f"\n\nStructs: {json.dumps(ast_data.get('structs', []))}\n"
        f"Rely-Guarantee Analysis:\n{json.dumps(explorer_result['analysis'], indent=2)}\n\n"
        "Requirements for `interleaveguard_gen_test.go`:\n"
        f"1. Start with `package {pkg}`.\n"
        "2. Import only standard library packages you actually use (no unused imports!).\n"
        "3. Define `func TestInterleaveGuardAudit(t *testing.T)`.\n"
        "4. Launch 2+ goroutines synchronized with a `chan struct{}` start barrier (and repeat in a short loop up to 50 iterations if needed) to trigger the interleaving schedule.\n"
        "5. If the invariant is violated (e.g., negative balance, double booking, stale value, panic, or timeout > 1s indicating deadlock), call `t.Fatalf(...)`.\n"
        "6. If the code is thread-safe and preserves all invariants, the test must pass cleanly.\n"
        "7. Output ONLY raw Go code starting with `package `."
    )

    go_code = call_llm(sys_prompt, user_prompt, json_mode=False).strip()
    if go_code.startswith("```"):
        lines = go_code.splitlines()
        go_code = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()

    with open(gen_test_path, "w", encoding="utf-8") as f:
        f.write(go_code + "\n")

    try:
        rel_pkg = "./" + os.path.basename(pkg_dir)
        proc = subprocess.run(
            ["go", "test", "-race", "-timeout", "5s", "-run", "TestInterleaveGuardAudit", rel_pkg],
            cwd="benchmarks",
            capture_output=True,
            text=True
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        compiled = (
            proc.returncode != 2
            and "build failed" not in output
            and "undefined:" not in output
            and "imported and not used" not in output
        )
        bug_witnessed = compiled and proc.returncode != 0 and (
            "--- FAIL:" in output
            or "DATA RACE" in output
            or "panic:" in output
            or "test timed out" in output
        )
    finally:
        if not keep_test and os.path.exists(gen_test_path):
            os.remove(gen_test_path)

    return {
        "package": pkg,
        "compiled": compiled,
        "bug_witnessed_by_test": bug_witnessed,
        "llm_predicted_vulnerable": explorer_result["analysis"].get("vulnerable", False),
        "test_exit_code": proc.returncode,
        "test_output": output[:1500],
        "generated_test_code": go_code,
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