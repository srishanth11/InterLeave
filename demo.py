import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))
from engine.run_eval import run_interleave_pipeline

def run_demo(target_dir: str, label: str):
    print("=" * 72)
    print(f"INTERLEAVE END-TO-END 10-STEP DEMONSTRATION: {label}")
    print("=" * 72)
    res = run_interleave_pipeline(target_dir, mode="caller-driven", validate_specs=True)
    te = res["test_execution"]
    an = res["analysis"]
    sv = res["spec_validation"]

    print(f"[1-2] Target Module & AST Extracted : {target_dir}/target.go")
    print(f"[3-4] Candidate Specs Generated     : {res['candidate_count']} specs | Ground-Truth Grade: {sv.get('package_verdict')} ({sv.get('correctness_pct')}%)")
    print(f"[5]   Suspected Bug Category        : {an.get('bug_category')} (Predicted Vulnerable: {res['predicted_vulnerable']})")
    print(f"      Violated Contract             : {an.get('violated_contract')}")
    print(f"[6]   Interleavings Explored        : Proposed={te['interleavings_considered']}, Validated={te['interleavings_validated']}, Executed={te['interleavings_executed']}")
    print(f"      Selected Schedule Steps       :")
    for st in an.get("interleaving_schedule", []):
        print(f"        Step {st.get('step')}: [{st.get('goroutine')}] {st.get('function')} -> {st.get('action')}")
    print(f"[7-8] Test Compiled & Executed      : Compiled={te['compiled']}, Executed={te['executed']}")
    print(f"[9]   Bug Reproduced Empirically    : {res['bug_reproduced']} | Reproducibility: {te['reproducibility']} | TTFF: {te['time_to_first_failure_sec']}s")
    print(f"[10]  Root Cause & Repair           : {an.get('repair_suggestion')}\n")

if __name__ == "__main__":
    run_demo("benchmarks/b01_bank", "BUGGY EXAMPLE (Split-Lock Atomicity Violation)")
    run_demo("benchmarks/c07_lockedhelper", "SAFE CONTROL (Caller-Enforced Mutex Discipline)")