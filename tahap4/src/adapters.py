"""Adapter model dengan antarmuka seragam: ``chat(messages, params) -> ChatResult``.

``messages`` adalah daftar ``{"role": "system"|"user"|"assistant", "content": str}``.
``params`` yang dikenali (semuanya opsional, hanya yang ada yang dikirim):

- ``max_tokens``   batas token keluaran
- ``num_ctx``      panjang konteks (Ollama saja)
- ``seed``         seed sampling (Ollama; penyedia lain hanya bila ``send_seed: true`` di config)
- ``temperature``  hanya dipakai untuk penilai; model komersial yang diuji tidak dikirimi parameter sampling
- ``json_schema``  minta keluaran JSON terstruktur (penilai)

Setiap ``ChatResult`` mencatat parameter yang benar-benar dikirim (``params_sent``).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx


class AdapterError(Exception):
    """Galat panggilan model. ``retryable`` menandai apakah panggilan layak diulang."""

    def __init__(self, message: str, retryable: bool = True, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


@dataclass
class ChatResult:
    """Respons satu panggilan beserta metadata yang dicatat ke log."""

    text: str
    model_reported: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_s: float
    finish_reason: str | None
    params_sent: dict[str, Any]
    provider_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _api_key(cfg: dict) -> str:
    env = cfg.get("api_key_env")
    if not env:
        return "unused"
    key = os.environ.get(env)
    if not key:
        raise AdapterError(f"Variabel lingkungan {env} kosong; isi di tahap4/.env", retryable=False)
    return key


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    return system, [m for m in messages if m["role"] != "system"]


def _status_retryable(status: int | None) -> bool:
    return status is None or status == 408 or status == 409 or status == 429 or status >= 500


class BaseAdapter:
    """Dasar adapter; turunan mengisi ``chat`` dan boleh memperkaya ``describe``."""

    provider = "base"

    def __init__(self, cfg: dict, timeout_s: float):
        self.cfg = cfg
        self.model_id: str = cfg["model_id"]
        self.timeout_s = timeout_s

    def chat(self, messages: list[dict], params: dict[str, Any]) -> ChatResult:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        """Metadata model untuk log (ID, penyedia, URL; Ollama menambah digest dan kuantisasi)."""
        return {"provider": self.provider, "model_id": self.model_id, "base_url": self.cfg.get("base_url"),
                "family": self.cfg.get("family")}


class OllamaAdapter(BaseAdapter):
    """Ollama lokal lewat REST API /api/chat (tanpa streaming)."""

    provider = "ollama"

    def __init__(self, cfg: dict, timeout_s: float, keep_alive: str = "30m"):
        super().__init__(cfg, timeout_s)
        self.client = httpx.Client(base_url=cfg.get("base_url") or "http://localhost:11434", timeout=timeout_s)
        self.keep_alive = keep_alive

    def chat(self, messages: list[dict], params: dict[str, Any]) -> ChatResult:
        options = {}
        for k_in, k_out in (("num_ctx", "num_ctx"), ("max_tokens", "num_predict"), ("seed", "seed"),
                            ("num_gpu", "num_gpu"), ("temperature", "temperature")):
            if k_in in params:
                options[k_out] = params[k_in]
        body: dict[str, Any] = {"model": self.model_id, "messages": messages, "stream": False,
                                "keep_alive": self.keep_alive, "options": options}
        if "json_schema" in params:
            body["format"] = params["json_schema"]
        t0 = time.perf_counter()
        try:
            r = self.client.post("/api/chat", json=body)
        except httpx.HTTPError as e:
            raise AdapterError(f"{type(e).__name__}: {e}", retryable=True) from e
        latency = time.perf_counter() - t0
        if r.status_code != 200:
            raise AdapterError(f"HTTP {r.status_code}: {r.text[:500]}", _status_retryable(r.status_code), r.status_code)
        d = r.json()
        msg = d.get("message") or {}
        meta = {k: d.get(k) for k in ("created_at", "total_duration", "load_duration", "prompt_eval_count",
                                      "prompt_eval_duration", "eval_count", "eval_duration")}
        if d.get("eval_count") and d.get("eval_duration"):
            meta["tokens_per_s"] = d["eval_count"] / (d["eval_duration"] / 1e9)
        if msg.get("thinking"):
            meta["thinking"] = msg["thinking"]
        sent = {"options": options, "keep_alive": self.keep_alive}
        if "format" in body:
            sent["format"] = "json_schema"
        return ChatResult(text=msg.get("content") or "", model_reported=d.get("model"),
                          input_tokens=d.get("prompt_eval_count"), output_tokens=d.get("eval_count"),
                          latency_s=latency, finish_reason=d.get("done_reason"), params_sent=sent, provider_meta=meta)

    def describe(self) -> dict[str, Any]:
        info = super().describe()
        try:
            tags = self.client.get("/api/tags").json().get("models", [])
            tag = next((t for t in tags if t.get("name") in (self.model_id, f"{self.model_id}:latest")), None)
            show = self.client.post("/api/show", json={"model": self.model_id}).json()
            ver = self.client.get("/api/version").json().get("version")
        except (httpx.HTTPError, ValueError) as e:
            info["describe_error"] = f"{type(e).__name__}: {e}"
            return info
        mi = show.get("model_info") or {}
        info.update({
            "ollama_server_version": ver,
            "digest": tag.get("digest") if tag else None,
            "size_bytes": tag.get("size") if tag else None,
            "details": show.get("details"),
            "parameters": show.get("parameters"),
            "template_sha256": hashlib.sha256((show.get("template") or "").encode()).hexdigest(),
            "has_system": any(line.startswith("SYSTEM") for line in (show.get("modelfile") or "").splitlines()),
            "general": {k: v for k, v in mi.items() if k.startswith("general.") and not isinstance(v, list)},
        })
        return info


class OpenAIAdapter(BaseAdapter):
    """OpenAI Chat Completions; juga dipakai untuk endpoint openai_compatible lewat ``base_url``."""

    provider = "openai"

    def __init__(self, cfg: dict, timeout_s: float):
        super().__init__(cfg, timeout_s)
        from openai import OpenAI
        self.client = OpenAI(api_key=_api_key(cfg), base_url=cfg.get("base_url") or None,
                             timeout=timeout_s, max_retries=0)
        default_param = "max_completion_tokens" if cfg["provider"] == "openai" else "max_tokens"
        self.max_tokens_param = cfg.get("max_tokens_param", default_param)
        self.provider = cfg["provider"]

        # fallback penilai yang "lengket" per instans: sekali ditolak API, tidak dicoba lagi
        self.temperature_dropped = False
        self.json_mode = "json_schema"
        self.fallback_events: list[dict[str, Any]] = []

    def _build_kwargs(self, messages: list[dict], params: dict[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": self.model_id, "messages": messages, "stream": False}
        if "max_tokens" in params:
            kwargs[self.max_tokens_param] = params["max_tokens"]
        if "temperature" in params and not self.temperature_dropped:
            kwargs["temperature"] = params["temperature"]
        if "seed" in params and self.cfg.get("send_seed"):
            kwargs["seed"] = params["seed"]
        if "json_schema" in params:
            kwargs["response_format"] = (
                {"type": "json_schema", "json_schema": {"name": "JudgeOutput", "schema": params["json_schema"],
                                                        "strict": False}}
                if self.json_mode == "json_schema" else {"type": "json_object"})
        return kwargs

    def _try_fallback(self, err: Exception, kwargs: dict[str, Any]) -> bool:
        """Untuk HTTP 400/422 yang menolak temperature atau json_schema: aktifkan fallback bila diizinkan config."""
        msg = str(err).lower()
        if "temperature" in kwargs and "temperature" in msg and self.cfg.get("temperature_fallback"):
            self.temperature_dropped = True
            self.fallback_events.append({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "fallback": "temperature_dropped",
                                         "error": str(err)[:500]})
            return True
        if (kwargs.get("response_format", {}).get("type") == "json_schema"
                and ("response_format" in msg or "json_schema" in msg) and self.cfg.get("json_mode_fallback")):
            self.json_mode = "json_object"
            self.fallback_events.append({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "fallback": "json_object",
                                         "error": str(err)[:500]})
            return True
        return False

    def chat(self, messages: list[dict], params: dict[str, Any]) -> ChatResult:
        import openai
        for _ in range(3):  # maksimal dua fallback (temperature, json_schema) + panggilan akhir
            kwargs = self._build_kwargs(messages, params)
            t0 = time.perf_counter()
            try:
                raw = self.client.chat.completions.with_raw_response.create(**kwargs)
                resp = raw.parse()
                break
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                raise AdapterError(f"{type(e).__name__}: {e}", retryable=True) from e
            except openai.APIStatusError as e:
                if e.status_code in (400, 422) and self._try_fallback(e, kwargs):
                    continue
                raise AdapterError(f"{type(e).__name__} {e.status_code}: {str(e)[:500]}",
                                   _status_retryable(e.status_code), e.status_code) from e
        else:
            raise AdapterError("fallback penilai habis tanpa respons", retryable=False)
        latency = time.perf_counter() - t0
        ch = resp.choices[0]
        usage = resp.usage
        content = ch.message.content or ""
        headers = _safe_headers(raw.headers)
        meta: dict[str, Any] = {"id": resp.id, "system_fingerprint": getattr(resp, "system_fingerprint", None),
                                "headers": headers}
        if resp.model_extra:
            meta["response_extra"] = {k: v for k, v in resp.model_extra.items() if k != "choices"}
        if usage is not None:
            details = getattr(usage, "completion_tokens_details", None)
            if details is not None and getattr(details, "reasoning_tokens", None) is not None:
                meta["reasoning_tokens"] = details.reasoning_tokens
            pdetails = getattr(usage, "prompt_tokens_details", None)
            if pdetails is not None and getattr(pdetails, "cached_tokens", None) is not None:
                meta["cached_input_tokens"] = pdetails.cached_tokens
            if usage.model_extra:
                meta["usage_extra"] = usage.model_extra
        reasoning = _extract_reasoning(ch.message)
        if reasoning is not None:
            meta["reasoning_text"] = reasoning  # disimpan terpisah; TIDAK masuk riwayat dialog
        if "<think>" in content:
            meta["inline_think_tag"] = True  # hanya ditandai; isi respons tidak diubah
        cost = _reported_cost(headers, usage)
        if cost is not None:
            meta["api_reported_cost_usd"] = cost
        if self.fallback_events:
            meta["fallback_events"] = list(self.fallback_events)
        sent = {k: v for k, v in kwargs.items() if k not in ("model", "messages")}
        if "response_format" in sent:
            sent["response_format"] = sent["response_format"]["type"]
        return ChatResult(text=content, model_reported=resp.model,
                          input_tokens=usage.prompt_tokens if usage else None,
                          output_tokens=usage.completion_tokens if usage else None,
                          latency_s=latency, finish_reason=ch.finish_reason, params_sent=sent, provider_meta=meta)


_SECRET_HINTS = ("key", "auth", "cookie", "token", "secret")


def _safe_headers(headers: Any) -> dict[str, str]:
    """Header respons tanpa apa pun yang mirip rahasia (kunci, cookie, token)."""
    return {k.lower(): v for k, v in headers.items() if not any(s in k.lower() for s in _SECRET_HINTS)}


def _extract_reasoning(message: Any) -> str | None:
    """Teks penalaran yang dikembalikan API terpisah dari ``content`` (mis. ``reasoning_content`` DeepSeek)."""
    extra = getattr(message, "model_extra", None) or {}
    for key in ("reasoning_content", "reasoning"):
        val = getattr(message, key, None) or extra.get(key)
        if isinstance(val, str) and val.strip():
            return val
    details = getattr(message, "reasoning_details", None) or extra.get("reasoning_details")
    if details:
        parts = [d.get("text") or d.get("summary") or "" for d in details if isinstance(d, dict)]
        return "\n".join(p for p in parts if p) or json.dumps(details, ensure_ascii=False)
    return None


def _reported_cost(headers: dict[str, str], usage: Any) -> float | None:
    """Biaya per panggilan yang dilaporkan gateway (header LiteLLM atau field usage.cost), bila ada."""
    for h in ("x-litellm-response-cost", "x-response-cost"):
        if h in headers:
            try:
                return float(headers[h])
            except ValueError:
                pass
    extra = getattr(usage, "model_extra", None) or {}
    if isinstance(extra.get("cost"), (int, float)):
        return float(extra["cost"])
    return None


class AnthropicAdapter(BaseAdapter):
    """Anthropic Messages API. SDK terpasang tidak menyediakan parameter temperature."""

    provider = "anthropic"

    def __init__(self, cfg: dict, timeout_s: float):
        super().__init__(cfg, timeout_s)
        import anthropic
        self.client = anthropic.Anthropic(api_key=_api_key(cfg), base_url=cfg.get("base_url") or None,
                                          timeout=timeout_s, max_retries=0)

    def chat(self, messages: list[dict], params: dict[str, Any]) -> ChatResult:
        import anthropic
        system, msgs = _split_system(messages)
        kwargs: dict[str, Any] = {"model": self.model_id, "max_tokens": params.get("max_tokens", 1024),
                                  "messages": msgs}
        if system:
            kwargs["system"] = system
        if "temperature" in params:
            if not self.cfg.get("send_temperature_extra_body"):
                raise AdapterError("SDK Anthropic terpasang tidak mendukung temperature; set "
                                   "send_temperature_extra_body: true bila API model ini menerimanya.", retryable=False)
            kwargs["extra_body"] = {"temperature": params["temperature"]}
        if "json_schema" in params:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": params["json_schema"]}}
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(**kwargs)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            raise AdapterError(f"{type(e).__name__}: {e}", retryable=True) from e
        except anthropic.APIStatusError as e:
            raise AdapterError(f"{type(e).__name__} {e.status_code}: {str(e)[:500]}",
                               _status_retryable(e.status_code), e.status_code) from e
        latency = time.perf_counter() - t0
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        sent = {k: v for k, v in kwargs.items() if k not in ("model", "messages", "system")}
        if "output_config" in sent:
            sent["output_config"] = "json_schema"
        return ChatResult(text=text, model_reported=resp.model, input_tokens=resp.usage.input_tokens,
                          output_tokens=resp.usage.output_tokens, latency_s=latency, finish_reason=resp.stop_reason,
                          params_sent=sent, provider_meta={"id": resp.id})


class GoogleAdapter(BaseAdapter):
    """Google Gemini lewat SDK google-genai. Token 'thoughts' dihitung sebagai keluaran (ditagih)."""

    provider = "google"

    def __init__(self, cfg: dict, timeout_s: float):
        super().__init__(cfg, timeout_s)
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client(api_key=_api_key(cfg), http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))

    def chat(self, messages: list[dict], params: dict[str, Any]) -> ChatResult:
        from google.genai import errors
        types = self.types
        system, msgs = _split_system(messages)
        contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                                  parts=[types.Part(text=m["content"])]) for m in msgs]
        conf: dict[str, Any] = {}
        if "max_tokens" in params:
            conf["max_output_tokens"] = params["max_tokens"]
        if system:
            conf["system_instruction"] = system
        if "temperature" in params:
            conf["temperature"] = params["temperature"]
        if "seed" in params and self.cfg.get("send_seed"):
            conf["seed"] = params["seed"]
        if "json_schema" in params:
            conf["response_mime_type"] = "application/json"
            conf["response_json_schema"] = params["json_schema"]
        t0 = time.perf_counter()
        try:
            resp = self.client.models.generate_content(model=self.model_id, contents=contents,
                                                       config=types.GenerateContentConfig(**conf))
        except errors.APIError as e:
            code = getattr(e, "code", None)
            raise AdapterError(f"{type(e).__name__} {code}: {str(e)[:500]}", _status_retryable(code), code) from e
        except httpx.HTTPError as e:
            raise AdapterError(f"{type(e).__name__}: {e}", retryable=True) from e
        latency = time.perf_counter() - t0
        um = resp.usage_metadata
        thoughts = (um.thoughts_token_count or 0) if um else 0
        out_tok = ((um.candidates_token_count or 0) + thoughts) if um else None
        cand = resp.candidates[0] if resp.candidates else None
        finish = str(cand.finish_reason) if cand and cand.finish_reason is not None else None
        try:
            text = resp.text or ""
        except ValueError:
            text = ""
        sent = {k: v for k, v in conf.items() if k not in ("system_instruction", "response_json_schema")}
        return ChatResult(text=text, model_reported=resp.model_version,
                          input_tokens=um.prompt_token_count if um else None, output_tokens=out_tok,
                          latency_s=latency, finish_reason=finish, params_sent=sent,
                          provider_meta={"thoughts_tokens": thoughts, "response_id": getattr(resp, "response_id", None)})


def make_adapter(cfg: dict, full_cfg: dict) -> BaseAdapter:
    """Pabrik adapter berdasarkan ``provider`` di config slot."""
    timeout = float(full_cfg["retry"]["timeout_s"])
    p = cfg["provider"]
    if p == "ollama":  # keep_alive per slot menimpa default (mis. -1 agar model milik pengguna tetap termuat)
        return OllamaAdapter(cfg, timeout, keep_alive=cfg.get("keep_alive", full_cfg["ollama"].get("keep_alive", "30m")))
    if p in ("openai", "openai_compatible"):
        return OpenAIAdapter(cfg, timeout)
    if p == "anthropic":
        return AnthropicAdapter(cfg, timeout)
    if p == "google":
        return GoogleAdapter(cfg, timeout)
    raise SystemExit(f"Provider tidak dikenal: {p}")
