import os
import sys
import json
import time
import random
import urllib.request
import urllib.error

TOTAL_TOKENS = {"prompt": 0, "completion": 0, "calls": 0}

def get_token_stats():
    return dict(TOTAL_TOKENS)

def reset_token_stats():
    TOTAL_TOKENS["prompt"] = 0
    TOTAL_TOKENS["completion"] = 0
    TOTAL_TOKENS["calls"] = 0

def _post_json(url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
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

def call_llm(system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    if gemini_key:
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        models = [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.8-flash",
            "gemini-3.1-flash-lite",
        ]
        last_err = None

        for attempt in range(6):
            for model in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                try:
                    data = _post_json(url, payload, {"Content-Type": "application/json"}, timeout=30)
                    usage = data.get("usageMetadata", {})
                    TOTAL_TOKENS["prompt"] += usage.get("promptTokenCount", 0)
                    TOTAL_TOKENS["completion"] += usage.get("candidatesTokenCount", 0)
                    TOTAL_TOKENS["calls"] += 1
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    if "HTTP 404" in err_str:
                        continue
                    if "HTTP 503" in err_str or "HTTP 429" in err_str or "timed out" in err_str:
                        wait = min(15.0, (2 ** attempt) + random.uniform(0.3, 1.2))
                        sys.stderr.write(f"[LLM] {model} busy (503/429), backing off {wait:.1f}s...\n")
                        sys.stderr.flush()
                        time.sleep(wait)
                        continue
                    raise
        raise last_err

    if openai_key or openrouter_key:
        is_or = bool(openrouter_key and not openai_key)
        key = openrouter_key if is_or else openai_key
        url = "https://openrouter.ai/api/v1/chat/completions" if is_or else "https://api.openai.com/v1/chat/completions"
        model = "anthropic/claude-sonnet-4-6" if is_or else "gpt-4o-mini"
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
        data = _post_json(url, payload, {"Content-Type": "application/json"}, timeout=60)
        usage = data.get("usage", {})
        TOTAL_TOKENS["prompt"] += usage.get("prompt_tokens", 0)
        TOTAL_TOKENS["completion"] += usage.get("completion_tokens", 0)
        TOTAL_TOKENS["calls"] += 1
        return data["choices"][0]["message"]["content"]

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
        })
        usage = data.get("usage", {})
        TOTAL_TOKENS["prompt"] += usage.get("input_tokens", 0)
        TOTAL_TOKENS["completion"] += usage.get("output_tokens", 0)
        TOTAL_TOKENS["calls"] += 1
        return data["content"][0]["text"]

    raise RuntimeError("No LLM API key found! Export GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY.")