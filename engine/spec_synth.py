import os
import sys
import json
import subprocess
from collections import deque
from llm_client import call_llm, get_token_stats

def run_ast_extractor(target_go_path: str) -> dict:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    bin_path = os.path.join(repo_root, "analyzer", "extract_bin")
    src_path = os.path.join(repo_root, "analyzer", "extract.go")

    if not os.path.exists(bin_path) or os.path.getmtime(src_path) > os.path.getmtime(bin_path):
        build_proc = subprocess.run(
            ["go", "build", "-o", bin_path, src_path],
            cwd=repo_root, capture_output=True, text=True
        )
        if build_proc.returncode != 0:
            raise RuntimeError(f"Failed to build analyzer/extract.go:\n{build_proc.stderr}")

    proc = subprocess.run(
        [bin_path, os.path.abspath(target_go_path)],
        cwd=repo_root, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(f"AST extractor failed on {target_go_path}:\n{proc.stderr}")
    return json.loads(proc.stdout)

def compute_top_down_layers(functions: list) -> list:
    func_names = {f["name"] for f in functions}
    in_deg = {f["name"]: 0 for f in functions}
    adj = {f["name"]: [] for f in functions}

    for f in functions:
        caller = f["name"]
        for callee in f.get("calls", []):
            if callee in func_names and callee != caller:
                adj[caller].append(callee)
                in_deg[callee] += 1

    q = deque([name for name, deg in in_deg.items() if deg == 0])
    layers = []
    visited = set()

    while q:
        layer = list(q)
        layers.append(layer)
        q.clear()
        for u in layer:
            visited.add(u)
            for v in adj[u]:
                in_deg[v] -= 1
                if in_deg[v] == 0:
                    q.append(v)

    remaining = [name for name in func_names if name not in visited]
    if remaining:
        layers.append(remaining)

    return layers

def synthesize_specs(ast_data: dict, mode: str = "caller-driven", min_candidates: int = 10) -> dict:
    funcs_by_name = {f["name"]: f for f in ast_data["functions"]}
    layers = compute_top_down_layers(ast_data["functions"])

    ordered_funcs = []
    for layer_idx, layer in enumerate(layers):
        for fn_name in layer:
            if not fn_name.startswith("New"):
                fn = dict(funcs_by_name[fn_name])
                fn["top_down_layer"] = layer_idx
                if mode == "impl-only":
                    fn.pop("called_by", None)
                ordered_funcs.append(fn)

    sys_prompt = (
        "You are a formal verification assistant specializing in concurrent Go programs "
        "and Rely-Guarantee reasoning (<R, G> |- {P} C {Q}). "
        "Output ONLY a valid JSON object with two top-level keys: 'function_specs' and 'candidate_specifications'."
    )

    direction_note = (
        "Propagate caller expectations strictly TOP-DOWN from Layer 0 callers down to callees."
        if mode == "caller-driven"
        else "Analyze each function body independently in isolation without caller context."
    )

    user_prompt = (
        f"Package: {ast_data['package']}\n"
        f"Structs: {json.dumps(ast_data.get('structs', []))}\n"
        f"Top-Down Call Layers: {json.dumps(layers)}\n"
        f"Instruction: {direction_note}\n\n"
        f"Functions (ordered top-down):\n{json.dumps(ordered_funcs, indent=2)}\n\n"
        "Return a JSON object with:\n"
        '1. "function_specs": mapping `<FuncName>` -> {\n'
        '     "precondition": "...",\n'
        '     "postcondition": "...",\n'
        '     "rely": "What OTHER concurrent goroutines MUST NOT do (or locks caller must hold) during execution",\n'
        '     "guarantee": "Invariant this function preserves for concurrent callers/observers",\n'
        '     "expected_callees": {"CalleeName": "Atomicity/lock obligation expected from callee"}\n'
        "   }\n"
        f'2. "candidate_specifications": an array of at least {min_candidates} distinct formal Rely-Guarantee '
        "candidate contracts covering atomicity, lock discipline, channel ownership, ordering, and state invariants across the package:\n"
        '   [{"id": "CAND-01", "target_function": "<FuncName>", "property_type": "Atomicity|Locking|Channel|Ordering|Invariant", '
        '"rely": "...", "guarantee": "...", "confidence": 0.0-1.0}]'
    )

    raw = call_llm(sys_prompt, user_prompt, json_mode=True)
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        specs = {}
        candidates = parsed
    elif isinstance(parsed, dict):
        specs = parsed.get("function_specs", parsed if "specs" not in parsed else parsed["specs"])
        candidates = parsed.get("candidate_specifications", [])
    else:
        specs = {}
        candidates = []

    return {
        "package": ast_data["package"],
        "file": ast_data["file"],
        "mode": mode,
        "layers": layers,
        "specs": specs,
        "candidate_specifications": candidates,
        "candidate_count": len(candidates),
        "token_stats": get_token_stats()
    }

def validate_specs_against_ground_truth(spec_result: dict, spec_json_path: str) -> dict:
    if not os.path.exists(spec_json_path):
        return {"evaluated": False, "reason": "No ground-truth spec.json found"}

    with open(spec_json_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    gt_rely = gt.get("rely", "")
    gt_guarantee = gt.get("guarantee", "")
    gt_scenario = gt.get("scenario", "")

    sys_prompt = (
        "You are a formal methods evaluator grading synthesized Rely-Guarantee specifications against a ground-truth specification. "
        "Grade each synthesized function spec and candidate spec strictly on semantic equivalence (whether it captures the true concurrency rely assumption, "
        "lock/ownership discipline, and state guarantee—NOT merely syntax). "
        "Classify each item as 'Correct', 'Partially Correct', or 'Incorrect'. "
        "Output ONLY a valid JSON object."
    )

    user_prompt = (
        f"Ground-Truth Specification ({spec_json_path}):\n"
        f"- Scenario: {gt_scenario}\n"
        f"- Ground-Truth Rely (R): {gt_rely}\n"
        f"- Ground-Truth Guarantee (G): {gt_guarantee}\n"
        f"- Ground-Truth Trigger: {gt.get('interleaving_trigger', '')}\n\n"
        f"Synthesized Function Specs:\n{json.dumps(spec_result.get('specs', {}), indent=2)}\n\n"
        f"Synthesized Candidate Specifications:\n{json.dumps(spec_result.get('candidate_specifications', []), indent=2)}\n\n"
        "Return a JSON object:\n"
        '{\n'
        '  "package_verdict": "Correct | Partially Correct | Incorrect",\n'
        '  "rationale": "Concise semantic comparison against ground-truth R and G",\n'
        '  "candidate_grades": [{"id": "CAND-01", "grade": "Correct | Partially Correct | Incorrect", "reason": "..."}]\n'
        '}'
    )

    raw = call_llm(sys_prompt, user_prompt, json_mode=True)
    grading = json.loads(raw)

    if isinstance(grading, list):
        grades = grading
        correct = sum(1 for g in grades if isinstance(g, dict) and g.get("grade") == "Correct")
        partial = sum(1 for g in grades if isinstance(g, dict) and g.get("grade") == "Partially Correct")
        incorrect = sum(1 for g in grades if isinstance(g, dict) and g.get("grade") == "Incorrect")
        pkg_verdict = (
            "Correct" if correct >= max(1, len(grades) // 2)
            else ("Partially Correct" if (correct + partial) > 0 else "Incorrect")
        )
        rationale = "Derived from candidate specification grades."
    elif isinstance(grading, dict):
        grades = grading.get("candidate_grades", [])
        correct = sum(1 for g in grades if isinstance(g, dict) and g.get("grade") == "Correct")
        partial = sum(1 for g in grades if isinstance(g, dict) and g.get("grade") == "Partially Correct")
        incorrect = sum(1 for g in grades if isinstance(g, dict) and g.get("grade") == "Incorrect")
        pkg_verdict = grading.get("package_verdict", "Incorrect")
        rationale = grading.get("rationale", "")
    else:
        grades, correct, partial, incorrect = [], 0, 0, 0
        pkg_verdict, rationale = "Incorrect", "Unparseable grading output"

    total = len(grades)
    weighted_pct = ((correct + 0.5 * partial) / total * 100.0) if total > 0 else 0.0

    return {
        "evaluated": True,
        "package_verdict": pkg_verdict,
        "rationale": rationale,
        "total_candidates": total,
        "correct": correct,
        "partially_correct": partial,
        "incorrect": incorrect,
        "correctness_pct": round(weighted_pct, 2),
        "strict_correct_pct": round((correct / total * 100.0) if total > 0 else 0.0, 2),
        "candidate_grades": grades
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 engine/spec_synth.py <path-to-target.go> [caller-driven|impl-only]")
        sys.exit(1)
    target = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "caller-driven"
    ast_json = run_ast_extractor(target)
    result = synthesize_specs(ast_json, mode=mode)
    gt_path = os.path.join(os.path.dirname(target), "spec.json")
    result["validation"] = validate_specs_against_ground_truth(result, gt_path)
    print(json.dumps(result, indent=2))