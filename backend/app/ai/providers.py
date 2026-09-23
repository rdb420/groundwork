"""Model providers behind one function. No vendor SDKs: plain HTTP keeps the dependency list short
and makes swapping providers a config change."""
import httpx

from ..config import get_settings

LOCAL = {"ollama"}


class ProviderError(RuntimeError):
    pass


def complete(system: str, user: str, *, json_mode: bool = True) -> tuple[str, str, str]:
    """Returns (text, provider, model)."""
    s = get_settings()
    if s.ai_provider == "ollama":
        body = {"model": s.ollama_model, "stream": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": 0.2}}
        if json_mode:
            body["format"] = "json"
        r = httpx.post(f"{s.ollama_url.rstrip('/')}/api/chat", json=body, timeout=300)
        if r.status_code >= 400:
            raise ProviderError(f"Ollama returned {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"], "ollama", s.ollama_model
    if s.ai_provider == "anthropic":
        if not s.anthropic_api_key:
            raise ProviderError("GW_ANTHROPIC_API_KEY is not set.")
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=180,
                       headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": s.anthropic_model, "max_tokens": 8000, "system": system,
                             "messages": [{"role": "user", "content": user}]})
        if r.status_code >= 400:
            raise ProviderError(f"Anthropic returned {r.status_code}: {r.text[:300]}")
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        return text, "anthropic", s.anthropic_model
    if s.ai_provider == "openai":
        if not s.openai_model:
            raise ProviderError("GW_OPENAI_MODEL is not set.")
        headers = {"Authorization": f"Bearer {s.openai_api_key}"} if s.openai_api_key else {}
        body = {"model": s.openai_model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(s.openai_url, headers=headers, json=body, timeout=240)
        if r.status_code >= 400:
            raise ProviderError(f"OpenAI-compatible endpoint returned {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"], "openai", s.openai_model
    raise ProviderError("AI is switched off. Set GW_AI_PROVIDER to ollama, anthropic or openai.")


def is_local() -> bool:
    s = get_settings()
    return s.ai_provider in LOCAL or (s.ai_provider == "openai" and s.openai_is_local)
