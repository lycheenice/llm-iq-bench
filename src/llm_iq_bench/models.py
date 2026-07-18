from __future__ import annotations

import json
import os
import random
import string
from dataclasses import dataclass, field

import requests


@dataclass
class ModelClient:
    """统一模型客户端。provider 为 mock / openai（兼容接口，含本地 sglang/vllm）。

    generate() 返回纯文本；generate_with_tools() 返回工具调用结构。
    本类不依赖 openai 库，直接走 HTTP，兼容 sglang / vllm / OpenAI 官方。
    """
    model_id: str
    provider: str
    api_model_id: str = ""            # 实际发给 API 的 model 名（可能与 config key 不同）
    base_url: str = ""
    api_key: str = ""
    params: dict = field(default_factory=dict)

    def generate(self, prompt: str, **overrides) -> str:
        params = {**self.params, **overrides}
        if self.provider == "mock":
            return _mock_generate(prompt, params)
        if self.provider == "openai":
            return _openai_generate(self, prompt, params)[0]
        raise ValueError(f"unknown provider: {self.provider}")

    def generate_n(self, prompt: str, n: int, **overrides) -> list[str]:
        params = {**self.params, **overrides, "n": n}
        if self.provider == "mock":
            return [_mock_generate(prompt, {k: v for k, v in params.items() if k != "n"}) for _ in range(n)]
        if self.provider == "openai":
            return _openai_generate(self, prompt, params, return_all=True)
        raise ValueError(f"unknown provider: {self.provider}")

    def generate_with_tools(self, prompt: str, tools: list[dict], **overrides) -> dict:
        """返回 {"content": str|None, "tool_calls": list[dict], "raw": dict}.

        tool_calls 每项: {"id","name","arguments": dict}（arguments 已解析为 dict）。
        """
        params = {**self.params, **overrides}
        if self.provider == "mock":
            return _mock_tools(prompt, tools, params)
        if self.provider == "openai":
            return _openai_tools(self, prompt, tools, params)
        raise ValueError(f"unknown provider: {self.provider}")


def build_model_client(model_id: str, models_cfg: dict) -> ModelClient:
    if model_id not in models_cfg:
        raise KeyError(f"model not in configs/models.yaml: {model_id}")
    spec = models_cfg[model_id]
    provider = spec["provider"]
    api_model_id = spec.get("api_model_id") or spec.get("api_model", "") or model_id
    base_url = spec.get("base_url", "").rstrip("/")
    api_key_env = spec.get("api_key_env", "")
    api_key = os.environ.get(api_key_env, "") if api_key_env else ""
    if not api_key and provider == "openai":
        if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            api_key = "EMPTY"
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
    return ModelClient(
        model_id=model_id,
        provider=provider,
        api_model_id=api_model_id,
        base_url=base_url,
        api_key=api_key,
        params=dict(spec.get("default_params", {})),
    )


def _mock_generate(prompt: str, params: dict) -> str:
    rng = random.Random(hash(prompt) & 0xFFFFFFFF)
    lowered = prompt.lower()
    if any(k in lowered for k in ["answer:", "选", "a)", "b)", "choice"]):
        return rng.choice(["A", "B", "C", "D"])
    if "only output code" in lowered or "complete the following python" in lowered:
        return "def f(x):\n    return x\n"
    nums = [str(rng.randint(0, 100)) for _ in range(1)]
    return f"The answer is {rng.choice(nums)}."


def _openai_generate(client: ModelClient, prompt: str, params: dict, return_all: bool = False):
    url = f"{client.base_url}/chat/completions"
    body = {
        "model": client.api_model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": params.get("temperature", 0),
        "max_tokens": params.get("max_tokens", 1024),
    }
    if "n" in params:
        body["n"] = params["n"]
    if "stop" in params:
        body["stop"] = params["stop"]
    resp = _post(url, client.api_key, body)
    choices = resp.get("choices", [])
    if return_all:
        return [_choice_content(c) for c in choices]
    return (_choice_content(choices[0]) if choices else ""), resp


def _openai_tools(client: ModelClient, prompt: str, tools: list[dict], params: dict) -> dict:
    url = f"{client.base_url}/chat/completions"
    body = {
        "model": client.api_model_id,
        "messages": [{"role": "user", "content": prompt}],
        "tools": tools,
        "tool_choice": params.pop("tool_choice", "auto"),
        "temperature": params.get("temperature", 0),
        "max_tokens": params.get("max_tokens", 1024),
    }
    resp = _post(url, client.api_key, body)
    choices = resp.get("choices", [])
    if not choices:
        return {"content": None, "tool_calls": [], "raw": resp}
    msg = choices[0].get("message", {})
    content = msg.get("content")
    raw_calls = msg.get("tool_calls") or []
    parsed = []
    for tc in raw_calls:
        fn = tc.get("function", {}) or {}
        args_raw = fn.get("arguments", "")
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) and args_raw else {}
        except Exception:
            args = {"_raw": args_raw}
        parsed.append({
            "id": tc.get("id", ""),
            "name": fn.get("name", ""),
            "arguments": args,
        })
    return {"content": content, "tool_calls": parsed, "raw": resp}


def _mock_tools(prompt: str, tools: list[dict], params: dict) -> dict:
    if not tools:
        return {"content": "mock", "tool_calls": [], "raw": {}}
    fn = tools[0]["function"]
    return {
        "content": None,
        "tool_calls": [{
            "id": "call_mock",
            "name": fn["name"],
            "arguments": {k: 0 for k in fn.get("parameters", {}).get("properties", {})},
        }],
        "raw": {},
    }


def _choice_content(choice: dict) -> str:
    msg = choice.get("message", {}) or {}
    content = msg.get("content") or ""
    if not content and msg.get("reasoning_content"):
        content = msg.get("reasoning_content", "")
    return content


def _post(url: str, api_key: str, body: dict, timeout: int = 180) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()
