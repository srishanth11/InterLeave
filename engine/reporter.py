import os
import json

def format_single_report(pkg_result: dict) -> str:
    analysis = pkg_result.get("analysis", {})
    test_res = pkg_result.get("test_execution", {})
    spec_val = pkg_result.get("spec_validation", {})
    repro = test_res.get("reproducibility", {})

    pred_vuln = pkg_result.get("predicted_vulnerable", False)
    reproduced = pkg_result.get("bug_reproduced", False)
    status = "REPRODUCED BUG" if reproduced else ("SUSPECTED (UNREPRODUCED)" if pred_vuln else "SAFE (VERIFIED)")

    lines = [
        f"## Package `{pkg_result['package']}` — **{status}**",
        f"- **Ground Truth:** `{pkg_result.get('ground_truth', 'N/A')}` | **Predicted Vulnerable:** `{pred_vuln}` | **Empirically Reproduced:** `{reproduced}`",
        f"- **Bug Category:** {analysis.get('bug_category', 'None')}",
        f"- **Violated Rely-Guarantee Contract:** {analysis.get('violated_contract', 'None')}",
        f"- **Specification Validation:** `{spec_val.get('package_verdict', 'N/A')}` ({spec_val.get('correctness_pct', 0.0)}% weighted across {spec_val.get('total_candidates', 0)} candidates)",
        f"- **Test Pipeline:** Compiled=`{test_res.get('compiled', False)}` | Executed=`{test_res.get('executed', False)}` | Reproducibility=`{repro.get('successful_reproductions', 0)}/{repro.get('attempts', 0)} ({repro.get('reproduction_rate_pct', 0.0)}%, {repro.get('classification', 'N/A')})`",
        f"- **Interleavings & TTFF:** Considered=`{test_res.get('interleavings_considered', 0)}` | Validated=`{test_res.get('interleavings_validated', 0)}` | Executed=`{test_res.get('interleavings_executed', 0)}` | TTFF=`{test_res.get('time_to_first_failure_sec', 'N/A')}s`",
        "",
        "### Validated Interleaving Schedule"
    ]
    for step in analysis.get("interleaving_schedule", []):
        lines.append(f"{step.get('step', '-')}. **[{step.get('goroutine', 'G?')}]** (`{step.get('function', '')}`) {step.get('action', '')}")

    lines.extend([
        "",
        "### Recommended Repair",
        f"{analysis.get('repair_suggestion', 'No repair needed.')}",
        "\n---\n"
    ])
    return "\n".join(lines)

def write_full_report(results_dir: str, eval_summary: dict, detailed_runs: list, ai_summary: dict = None, ai_runs: list = None):
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "eval_summary.json"), "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)

    if ai_summary is not None:
        with open(os.path.join(results_dir, "ai_eval_summary.json"), "w", encoding="utf-8") as f:
            json.dump(ai_summary, f, indent=2)

    total = eval_summary["total_benchmarks"]
    buggy_cnt = eval_summary["buggy_count"]
    safe_cnt = eval_summary["safe_count"]

    md = [
        "# InterLeave Evaluation & Formal Concurrency Audit Report",
        "",
        f"## 1. Seeded Benchmark Comparison ({total} Scenarios: {buggy_cnt} Buggy, {safe_cnt} Safe)",
        "",
        "| Method / Ablation | TP | FP | TN | FN | Precision | Recall | F1 | FPR | Failing Tests | Runtime (s) | Tokens | Calls |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    ]
    for m_name, m in eval_summary["methods"].items():
        ft_str = f"{m.get('failing_tests_reproduced', 0)}/{buggy_cnt} ({m.get('failing_test_rate_pct', 0.0):.1f}%)" if "failing_tests_reproduced" in m else "N/A"
        md.append(
            f"| {m_name} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['fpr']:.3f} | "
            f"{ft_str} | {m['runtime_sec']:.1f}s | {m['tokens']} | {m.get('llm_calls', 0)} |"
        )

    qm = eval_summary.get("interleave_quality_metrics", {})
    md.extend([
        "",
        "## 2. InterLeave Pipeline Quality & Reproducibility Metrics",
        f"- **Candidate Specifications Generated:** {qm.get('total_candidate_specs', 0)} total ({qm.get('avg_candidates_per_pkg', 0.0):.1f}/pkg) — Correct: {qm.get('spec_correct', 0)}, Partially Correct: {qm.get('spec_partially_correct', 0)}, Incorrect: {qm.get('spec_incorrect', 0)}",
        f"- **Specification Correctness Rate:** **{qm.get('spec_correctness_pct', 0.0):.1f}%** (strict: {qm.get('spec_strict_correct_pct', 0.0):.1f}%)",
        f"- **Test Compilation Success Rate:** **{qm.get('test_compilation_rate_pct', 0.0):.1f}%** ({qm.get('tests_compiled', 0)}/{total})",
        f"- **Test Execution Success Rate:** **{qm.get('test_execution_rate_pct', 0.0):.1f}%** ({qm.get('tests_executed', 0)}/{total})",
        f"- **Failing-Test Generation Rate (on Buggy Benchmarks):** **{qm.get('failing_test_rate_pct', 0.0):.1f}%** ({qm.get('failing_tests_reproduced', 0)}/{buggy_cnt})",
        f"- **Mean Reproduction Rate (across 5 repeated runs on reproduced bugs):** **{qm.get('mean_reproduction_rate_pct', 0.0):.1f}%** (Deterministic: {qm.get('deterministic_bugs', 0)}, Probabilistic: {qm.get('probabilistic_bugs', 0)})",
        f"- **Interleavings Explored:** Proposed={qm.get('total_interleavings_proposed', 0)}, AST-Validated={qm.get('total_interleavings_validated', 0)}, Executed={qm.get('total_interleavings_executed', 0)}",
        f"- **Mean Time to First Failure (TTFF):** **{qm.get('mean_ttff_sec', 0.0):.2f}s**",
        ""
    ])

    if ai_summary and ai_runs:
        md.extend([
            "## 3. Separate Evaluation: AI-Generated Go Code Benchmarks",
            f"- **Total AI-Generated Scenarios:** {ai_summary['total_benchmarks']} ({ai_summary['buggy_count']} Buggy, {ai_summary['safe_count']} Safe)",
            f"- **Empirical Reproduction Metrics:** TP={ai_summary['empirical']['tp']}, FP={ai_summary['empirical']['fp']}, TN={ai_summary['empirical']['tn']}, FN={ai_summary['empirical']['fn']} | Precision={ai_summary['empirical']['precision']:.3f}, Recall={ai_summary['empirical']['recall']:.3f}, F1={ai_summary['empirical']['f1']:.3f}",
            f"- **Failing-Test Generation Rate:** {ai_summary['failing_tests_reproduced']}/{ai_summary['buggy_count']} ({ai_summary['failing_test_rate_pct']:.1f}%)",
            ""
        ])
        for item in ai_runs:
            md.append(format_single_report(item))

    md.extend(["## 4. Detailed Per-Benchmark Audit Findings (Seeded Suite)", ""])
    for item in detailed_runs:
        md.append(format_single_report(item))

    with open(os.path.join(results_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))