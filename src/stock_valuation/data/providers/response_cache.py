from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_PROVIDER_CACHE_DIR = Path("data/cache/providers")


class ProviderResponseCache:
    """Small file-backed cache for provider responses.

    JSON payloads and text documents live below ``data/cache`` which is ignored by git. API keys
    are never part of cache keys or persisted metadata. Text caching is used for original filing
    documents so repeated local audits do not redownload the same SEC/ESEF source files.
    """

    def __init__(self, provider: str, root: Path = DEFAULT_PROVIDER_CACHE_DIR) -> None:
        self.provider = provider.strip().lower()
        self.root = root / self.provider

    @staticmethod
    def _canonical_request(function: str, params: dict[str, Any]) -> str:
        payload = {
            "function": function,
            "params": {key: params[key] for key in sorted(params)},
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def cache_key(self, function: str, params: dict[str, Any]) -> str:
        canonical = self._canonical_request(function, params)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def path_for(self, function: str, params: dict[str, Any]) -> Path:
        return self.root / f"{self.cache_key(function, params)}.json"

    def text_path_for(self, function: str, params: dict[str, Any]) -> Path:
        return self.root / f"{self.cache_key(function, params)}.txt"

    def get(self, function: str, params: dict[str, Any]) -> dict[str, Any] | None:
        path = self.path_for(function, params)
        if not path.exists():
            return None
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        payload = wrapper.get("payload") if isinstance(wrapper, dict) else None
        return payload if isinstance(payload, dict) else None

    def put(self, function: str, params: dict[str, Any], payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(function, params)
        wrapper = {
            "provider": self.provider,
            "function": function,
            "params": {key: params[key] for key in sorted(params)},
            "cached_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        path.write_text(
            json.dumps(wrapper, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def get_text(self, function: str, params: dict[str, Any]) -> str | None:
        path = self.text_path_for(function, params)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def put_text(self, function: str, params: dict[str, Any], payload: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.text_path_for(function, params)
        path.write_text(payload, encoding="utf-8")
        return path

    def has(self, function: str, params: dict[str, Any]) -> bool:
        return self.path_for(function, params).exists()

    def has_text(self, function: str, params: dict[str, Any]) -> bool:
        return self.text_path_for(function, params).exists()
