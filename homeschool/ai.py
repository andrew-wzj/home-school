"""Bring-your-own-key AI calls (Claude or OpenAI), standard library only.

Raw HTTPS instead of the vendor SDKs keeps the app dependency-free and lets
it run on the Python 3.9 that ships with macOS.
"""
import json
import urllib.error
import urllib.request

from . import config

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2026-10-21"
# Models that accept server-side refusal fallbacks.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
                   "claude-fable-5-1", "claude-fable-5-2"}
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class AIError(Exception):
    pass


def _post(url, headers, body, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers=dict(headers, **{"content-type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("error", {}).get("message", detail)
        except (ValueError, AttributeError):
            pass
        raise AIError("%s %s: %s" % (e.code, e.reason, detail[:400]))
    except urllib.error.URLError as e:
        raise AIError("Network error: %s" % e.reason)


def _anthropic(key, model, system, user):
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    body = {
        "model": model,
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if model in FALLBACK_MODELS:
        headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
        body["fallbacks"] = "default"
    data = _post(ANTHROPIC_URL, headers, body)
    if data.get("stop_reason") == "refusal":
        raise AIError("The model declined this request.")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if not text.strip():
        raise AIError("Empty response (stop_reason: %s)" % data.get("stop_reason"))
    return text


def _openai(key, model, system, user):
    data = _post(OPENAI_URL, {"authorization": "Bearer " + key}, {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIError("Unexpected response shape from OpenAI.")


def ask(system, user):
    cfg = config.load_config()
    key, provider = cfg.get("api_key"), cfg.get("provider")
    if not key or provider not in config.PROVIDERS:
        raise AIError("No API key set. Add one in Settings.")
    model = cfg.get("model") or config.PROVIDERS[provider]["default_model"]
    fn = _anthropic if provider == "anthropic" else _openai
    return fn(key, model, system, user)


def configured():
    cfg = config.load_config()
    return bool(cfg.get("api_key")) and cfg.get("provider") in config.PROVIDERS
