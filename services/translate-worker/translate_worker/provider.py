"""Translation provider abstraction for translate-worker."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib import request

from ft_common.config import AppConfig


class TranslationProvider(Protocol):
    name: str

    def translate(self, *, text: str, uid: str, source_lang: str, target_lang: str) -> str:
        ...


@dataclass(frozen=True)
class MockTranslationProvider:
    name: str = "mock"

    def translate(self, *, text: str, uid: str, source_lang: str, target_lang: str) -> str:
        if text == "":
            return text
        return f"[{target_lang}] {text}"


@dataclass(frozen=True)
class HttpTranslationProvider:
    base_url: str
    timeout_seconds: int
    name: str = "http"

    def translate(self, *, text: str, uid: str, source_lang: str, target_lang: str) -> str:
        payload = json.dumps({"string": text, "uid": uid}).encode("utf-8")
        http_request = request.Request(
            self.base_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
        decoded = json.loads(body)
        result = _extract_result(decoded)
        if not isinstance(result, str):
            raise ValueError("translation API response must contain a result string")
        return result


def build_translation_provider(config: AppConfig) -> TranslationProvider:
    provider = config.translation_provider.lower()
    if provider == "mock":
        return MockTranslationProvider()
    if provider in {"http", "api", "internal"}:
        return HttpTranslationProvider(
            base_url=config.translation_api_base_url,
            timeout_seconds=config.translation_api_timeout_seconds,
        )
    raise ValueError(f"unsupported TRANSLATION_PROVIDER: {config.translation_provider!r}")


def _extract_result(decoded: Any) -> Any:
    if isinstance(decoded, str):
        return decoded
    if not isinstance(decoded, dict):
        return None
    for key in ("result", "translated", "translated_text", "translation"):
        if key in decoded:
            return decoded[key]
    return None

