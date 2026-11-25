import os
import sys
import json
import time
import urllib.request
import urllib.error

TOTAL_TOKENS = {"prompt": 0, "completion": 0, "calls": 0}
_GROQ_MODELS_CACHE = None

def get_token_stats():
    return dict(TOTAL_TOKENS)

def reset_token_stats():
    TOTAL_TOKENS["prompt"] = 0
    TOTAL_TOKENS["completion"] = 0
    TOTAL_TOKENS["calls"] = 0

def _post_json(url: str, payload: dict, headers: dict, timeout: int = 45) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e

def _clean_json_text(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        t = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
    return t

def _discover_groq_models(groq_key: str) -> list:
    global _GROQ_MODELS_CACHE
    if _GROQ_MODELS_CACHE is not None:
        return _GROQ_MODELS_CACHE
    preferred = [
        "openai/gpt-oss-20b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
    ]
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {groq_key}", "User-Agent": "InterLeave/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        live = [
            m["id"] for m in data.get("data", [])
            if not any(x in m["id"] for x in ("whisper", "guard", "orpheus", "safeguard", "compound"))
        ]
        ordered = [m for m in preferred if m in live] + [m for m in live if m not in preferred]
        if ordered:
            _GROQ_MODELS_CACHE = ordered
            return _GROQ_MODELS_CACHE
    except Exception:
        pass
    _GROQ_MODELS_CACHE = preferred
    return _GROQ_MODELS_CACHE

def call_llm(system_prompt: str, user_prompt: str, json_mode: bool = True, pace_sec: float = 0.8) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if groq_key:
        url = "https://api.groq.com/openai/v1/chat/completions"
        models = _discover_groq_models(groq_key)
        last_err = None
        for attempt in range(6):
            for model in models:
                payload = {
                    "model": model,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                try:
                    data = _post_json(url, payload, {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {groq_key}",
                        "User-Agent": "InterLeave/1.0"
                    }, timeout=45)
                    usage = data.get("usage", {})
                    TOTAL_TOKENS["prompt"] += usage.get("prompt_tokens", 0)
                    TOTAL_TOKENS["completion"] += usage.get("completion_tokens", 0)
                    TOTAL_TOKENS["calls"] += 1
                    if pace_sec > 0:
                        time.sleep(pace_sec)
                    out = data["choices"][0]["message"]["content"]
                    return _clean_json_text(out) if json_mode else out
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    if any(code in err_str for code in ("HTTP 404", "HTTP 400", "HTTP 413")):
                        continue
                    if "HTTP 429" in err_str or "HTTP 503" in err_str:
                        wait = 4.0 * (attempt + 1)
                        sys.stderr.write(f"[LLM] Groq ({model}) busy, sleeping {wait:.1f}s...\n")
                        sys.stderr.flush()
                        time.sleep(wait)
                        continue
                    raise
        raise last_err

    if openai_key or openrouter_key:
        is_or = bool(openrouter_key and not openai_key)
        key = openrouter_key if is_or else openai_key
        url = "https://openrouter.ai/api/v1/chat/completions" if is_or else "https://api.openai.com/v1/chat/completions"
        model = "meta-llama/llama-3.3-70b-instruct:free" if is_or else "gpt-4o-mini"
        payload = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        if json_mode and not is_or:
            payload["response_format"] = {"type": "json_object"}
        data = _post_json(url, payload, {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, timeout=60)
        usage = data.get("usage", {})
        TOTAL_TOKENS["prompt"] += usage.get("prompt_tokens", 0)
        TOTAL_TOKENS["completion"] += usage.get("completion_tokens", 0)
        TOTAL_TOKENS["calls"] += 1
        out = data["choices"][0]["message"]["content"]
        return _clean_json_text(out) if json_mode else out

    if anthropic_key:
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 2048,
            "temperature": 0.1,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        data = _post_json(url, payload, {
            "Content-Type": "application/json",
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01"
        }, timeout=60)
        usage = data.get("usage", {})
        TOTAL_TOKENS["prompt"] += usage.get("input_tokens", 0)
        TOTAL_TOKENS["completion"] += usage.get("output_tokens", 0)
        TOTAL_TOKENS["calls"] += 1
        return data["content"][0]["text"]

    if gemini_key:
        for model in ["gemini-2.5-flash-lite", "gemini-2.5-flash"]:
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.1}
            }
            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            data = _post_json(url, payload, {"Content-Type": "application/json"}, timeout=45)
            usage = data.get("usageMetadata", {})
            TOTAL_TOKENS["prompt"] += usage.get("promptTokenCount", 0)
            TOTAL_TOKENS["completion"] += usage.get("candidatesTokenCount", 0)
            TOTAL_TOKENS["calls"] += 1
            return data["candidates"][0]["content"]["parts"][0]["text"]

    raise RuntimeError("No API key found! Export GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY.")