import os
import glob
import json
import time
import subprocess
from llm_client import get_token_stats, reset_token_stats
from spec_synth import run_ast_extractor, synthesize_specs
from schedule_explorer import explore_interleavings
from test_gen import generate_and_run_test
from reporter import write_full_report

CACHE_PATH = "results/eval_cache.json"

def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"impl_only": {}, "interleave_guard": {}}

def save_cache(cache: dict):
    os.makedirs("results", exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def compute_metrics(preds: list, truths: list, runtime_sec: float, tokens: int) -> dict:
    tp = sum(1 for p, t in zip(preds, truths) if p and t)
    fp = sum(1 for p, t in zip(preds, truths) if p and not t)
    tn = sum(1 for p, t in zip(preds, truths) if not p and not t)
    fn = sum(1 for p, t in zip(preds, truths) if not p and t)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": prec, "recall": rec, "f1": f1,
        "runtime_sec": runtime_sec, "tokens": tokens
    }

def main():
    bench_dirs = sorted(glob.glob("benchmarks/[bc][0-9][0-9]_*"))
    print(f"Found {len(bench_dirs)} benchmark packages.")
    cache = load_cache()

    truths = []
    race_preds = []
    stress_preds = []
    impl_only_preds = []
    ig_preds = []
    detailed_runs = []

    # 1. Baseline 1: Standard `go test -race`
    t0 = time.time()
    for bdir in bench_dirs:
        pkg_name = os.path.basename(bdir)
        is_buggy = pkg_name.startswith("b")
        truths.append(is_buggy)

        proc = subprocess.run(
            ["go", "test", "-race", "-timeout", "4s", f"./{pkg_name}"],
            cwd="benchmarks", capture_output=True, text=True
        )
        race_preds.append(proc.returncode != 0)
    race_time = time.time() - t0

    # 2. Baseline 2: Random Concurrent Stress (`go test -race -count=25`)
    t0 = time.time()
    for bdir in bench_dirs:
        pkg_name = os.path.basename(bdir)
        proc = subprocess.run(
            ["go", "test", "-race", "-count=25", "-timeout", "5s", f"./{pkg_name}"],
            cwd="benchmarks", capture_output=True, text=True
        )
        stress_preds.append(proc.returncode != 0)
    stress_time = time.time() - t0

    # 3. Ablation: Implementation-Only LLM (No Top-Down Caller Context)
    reset_token_stats()
    t0 = time.time()
    for bdir in bench_dirs:
        pkg_name = os.path.basename(bdir)
        if pkg_name in cache["impl_only"]:
            vuln = cache["impl_only"][pkg_name]
        else:
            print(f"[Impl-Only] Auditing {pkg_name}...")
            target = os.path.join(bdir, "target.go")
            ast_data = run_ast_extractor(target)
            specs = synthesize_specs(ast_data, mode="impl-only")
            explored = explore_interleavings(ast_data, specs)
            vuln = bool(explored["analysis"].get("vulnerable", False))
            cache["impl_only"][pkg_name] = vuln
            save_cache(cache)
            time.sleep(0.5)
        impl_only_preds.append(vuln)
    impl_time = time.time() - t0
    impl_tokens = get_token_stats()["prompt"] + get_token_stats()["completion"]

    # 4. Full System: InterleaveGuard (Top-Down Rely-Guarantee + Deterministic Test Synthesis)
    reset_token_stats()
    t0 = time.time()
    for bdir in bench_dirs:
        pkg_name = os.path.basename(bdir)
        target = os.path.join(bdir, "target.go")
        is_buggy = pkg_name.startswith("b")

        if pkg_name in cache["interleave_guard"]:
            entry = cache["interleave_guard"][pkg_name]
        else:
            print(f"[InterleaveGuard] Auditing {pkg_name}...")
            ast_data = run_ast_extractor(target)
            specs = synthesize_specs(ast_data, mode="caller-driven")
            explored = explore_interleavings(ast_data, specs)
            test_exec = generate_and_run_test(ast_data, explored, keep_test=False)

            rg_vuln = bool(explored["analysis"].get("vulnerable", False))
            witnessed = bool(test_exec["compiled"] and test_exec["bug_witnessed_by_test"])
            final_detected = rg_vuln or witnessed

            entry = {
                "package": pkg_name,
                "ground_truth": "BUGGY" if is_buggy else "SAFE",
                "final_detected": final_detected,
                "specs": specs["specs"],
                "analysis": explored["analysis"],
                "test_execution": test_exec
            }
            cache["interleave_guard"][pkg_name] = entry
            save_cache(cache)
            time.sleep(0.5)

        ig_preds.append(entry["final_detected"])
        detailed_runs.append(entry)
    ig_time = time.time() - t0
    ig_tokens = get_token_stats()["prompt"] + get_token_stats()["completion"]

    eval_summary = {
        "total_benchmarks": len(bench_dirs),
        "methods": {
            "1. go test -race (Baseline)": compute_metrics(race_preds, truths, race_time, 0),
            "2. Random Stress (-count=25)": compute_metrics(stress_preds, truths, stress_time, 0),
            "3. LLM Impl-Only (Ablation)": compute_metrics(impl_only_preds, truths, impl_time, impl_tokens),
            "4. InterleaveGuard (Full RG + TestGen)": compute_metrics(ig_preds, truths, ig_time, ig_tokens)
        }
    }

    write_full_report("results", eval_summary, detailed_runs)
    print("\n=== EVALUATION COMPLETE ===")
    print(json.dumps(eval_summary, indent=2))
    print("\nSaved results/eval_summary.json and results/report.md")

if __name__ == "__main__":
    main()