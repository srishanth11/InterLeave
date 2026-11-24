import os
import json

def format_single_report(pkg_result: dict) -> str:
    analysis = pkg_result.get("analysis", {})
    test_res = pkg_result.get("test_execution", {})
    status = "VULNERABLE" if pkg_result.get("final_detected") else "SAFE (VERIFIED)"

    lines = [
        f"## Package `{pkg_result['package']}` — **{status}**",
        f"- **Ground Truth:** `{pkg_result.get('ground_truth', 'N/A')}` | **Detected:** `{pkg_result.get('final_detected')}`",
        f"- **Bug Category:** {analysis.get('bug_category', 'None')}",
        f"- **Violated Rely-Guarantee Contract:** {analysis.get('violated_contract', 'None')}",
        f"- **Empirical Test Witnessed Bug:** `{test_res.get('bug_witnessed_by_test', False)}` (Compiled: `{test_res.get('compiled', False)}`)",
        "",
        "### Adversarial Interleaving Schedule"
    ]
    for step in analysis.get("interleaving_schedule", []):
        lines.append(f"{step.get('step', '-')}. **[{step.get('goroutine', 'G?')}]** {step.get('action', '')}")

    lines.extend([
        "",
        "### Recommended Repair",
        f"{analysis.get('repair_suggestion', 'No repair needed.')}",
        "\n---\n"
    ])
    return "\n".join(lines)

def write_full_report(results_dir: str, eval_summary: dict, detailed_runs: list):
    os.makedirs(results_dir, exist_ok=True)
    summary_path = os.path.join(results_dir, "eval_summary.json")
    report_path = os.path.join(results_dir, "report.md")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)

    md = [
        "# InterleaveGuard Evaluation & Audit Report",
        "",
        "## Comparative Benchmark Metrics (18 Go Concurrency Scenarios: 12 Buggy, 6 Safe)",
        "",
        "| Method / Ablation | TP | FP | TN | FN | Precision | Recall | F1 Score | Runtime (s) | Total Tokens |",
        "|---|---|---|---|---|---|---|---|---|---|"
    ]
    for m_name, m in eval_summary["methods"].items():
        md.append(
            f"| {m_name} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | "
            f"{m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | "
            f"{m['runtime_sec']:.1f}s | {m['tokens']} |"
        )

    md.extend(["", "## Detailed Per-Benchmark Audit Findings", ""])
    for item in detailed_runs:
        md.append(format_single_report(item))

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))