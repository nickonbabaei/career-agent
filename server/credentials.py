"""Local provider key storage; values are never returned by UI endpoints."""
import json
import os
from pathlib import Path
import tempfile

KEYS = ('OPENWEBNINJA_API_KEY', 'GEMINI_API_KEY', 'TAVILY_API_KEY')
STORE = Path(__file__).resolve().parents[1] / '.local/keys.json'


def saved_keys():
    if not STORE.exists():
        return {}
    try:
        value = json.loads(STORE.read_text())
        if not isinstance(value, dict) or any(k not in KEYS or not isinstance(v, str) for k, v in value.items()):
            raise ValueError()
        return value
    except (ValueError, OSError):
        raise ValueError('Local key settings could not be read. Check .local/keys.json.') from None


def worker_environment():
    return {**os.environ, **saved_keys()}


def key_status():
    env = worker_environment()
    return {k: bool(env.get(k, '').strip()) for k in KEYS}


def save_keys(values):
    """Merge nonblank allowed keys atomically; invalid inputs never alter storage."""
    if any(k not in KEYS or not isinstance(v, str) or len(v) > 4096 or any(c.isspace() for c in v.strip()) for k, v in values.items()):
        raise ValueError('Enter valid API keys without spaces or line breaks.')
    merged = saved_keys()
    merged.update({k: v.strip() for k, v in values.items() if v.strip()})
    STORE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    STORE.parent.chmod(0o700)
    descriptor, name = tempfile.mkstemp(dir=STORE.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(merged, handle)
        temporary.chmod(0o600)
        temporary.replace(STORE)
    finally:
        temporary.unlink(missing_ok=True)
