"""Paths and the local-only API key file.

The key lives in config.local.json at the project root. That file is in
.gitignore and is written with 0600 permissions. It is never sent anywhere
except to the provider the user picked.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("HOMESCHOOL_DATA", os.path.join(ROOT, "data"))
WORKSPACE_DIR = os.environ.get("HOMESCHOOL_WORKSPACE", os.path.join(ROOT, "workspace"))
COURSES_DIR = os.path.join(ROOT, "courses")
WEB_DIR = os.path.join(ROOT, "web")
CONFIG_PATH = os.environ.get("HOMESCHOOL_CONFIG", os.path.join(ROOT, "config.local.json"))

PROVIDERS = {
    "anthropic": {"label": "Claude (Anthropic)", "default_model": "claude-opus-5-5"},
    "openai": {"label": "OpenAI", "default_model": "gpt-5"},
}


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)
    os.chmod(CONFIG_PATH, 0o600)


def public_config():
    """What the browser may see: never the key itself."""
    cfg = load_config()
    key = cfg.get("api_key") or ""
    provider = cfg.get("provider") or ""
    return {
        "provider": provider,
        "model": cfg.get("model") or (PROVIDERS.get(provider, {}).get("default_model", "")),
        "has_key": bool(key),
        "key_hint": ("…" + key[-4:]) if len(key) >= 8 else "",
        "providers": {k: v for k, v in PROVIDERS.items()},
    }
