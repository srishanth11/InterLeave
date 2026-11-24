import sys
import json
import subprocess
from collections import deque
from llm_client import call_llm, get_token_stats

def run_ast_extractor(target_go_path: str) -> dict:
    proc = subprocess.run(
        ["go", "run", "./analyzer", target_go_path],
        capture_output=True, text=True, check=True
    )
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

def synthesize_specs(ast_data: dict, mode: str = "caller-driven") -> dict:
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
        "Output ONLY a valid JSON object mapping each function name to an object with keys: "
        "'precondition', 'postcondition', 'rely', 'guarantee', 'expected_callees'."
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
        "For EVERY function listed above, return a JSON entry mapping `<FuncName>` -> {\n"
        '  "precondition": "State required before function runs",\n'
        '  "postcondition": "State ensured after function returns",\n'
        '  "rely": "Critical assumption about what OTHER concurrent goroutines MUST NOT do to shared state/locks/channels while this function executes",\n'
        '  "guarantee": "Invariant this function promises to preserve for other goroutines",\n'
        '  "expected_callees": {"CalleeName": "What caller expects callee to atomically guarantee"}\n'
        "}"
    )

    raw = call_llm(sys_prompt, user_prompt, json_mode=True)
    specs = json.loads(raw)

    return {
        "package": ast_data["package"],
        "file": ast_data["file"],
        "mode": mode,
        "layers": layers,
        "specs": specs,
        "token_stats": get_token_stats()
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 engine/spec_synth.py <path-to-target.go> [caller-driven|impl-only]")
        sys.exit(1)
    target = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "caller-driven"
    ast_json = run_ast_extractor(target)
    result = synthesize_specs(ast_json, mode=mode)
    print(json.dumps(result, indent=2))