"""Run the Ask loop on a model served through OpenRouter (GLM-5.3 Flash), for comparison.

OpenRouterClient looks like the Anthropic client the loop uses (client.messages.create(...)
in, Anthropic-shaped response out), so both models run the identical loop and rules; only
the model differs. It translates to OpenRouter's OpenAI-style chat API and back.

Every request carries PRIVACY: OpenRouter only routes to providers that keep no data (zdr)
and don't collect it. Tested: OpenRouter accepts both keys (it rejects unknown ones with a
400), and the account's Privacy settings say the same as a second layer.
"""

import json
import os
import urllib.request
from types import SimpleNamespace

URL = "https://openrouter.ai/api/v1/chat/completions"
PRIVACY = {"zdr": True, "data_collection": "deny"}


def _http_post(api_key: str):
    def post(body: dict) -> dict:
        request = urllib.request.Request(
            URL, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    return post


def _blocks(content) -> list:
    """Message content as a list of blocks (a plain string is one text block)."""
    if isinstance(content, str):
        return [SimpleNamespace(type="text", text=content)]
    return [b if not isinstance(b, dict) else SimpleNamespace(**b) for b in content]


def to_openai_messages(system: list, messages: list) -> list[dict]:
    out = []
    system_text = "".join(block["text"] for block in system)
    if system_text:
        out.append({"role": "system", "content": system_text})
    for message in messages:
        blocks = _blocks(message["content"])
        if message["role"] == "assistant":
            text = "".join(b.text for b in blocks if b.type == "text")
            calls = [{"id": b.id, "type": "function",
                      "function": {"name": b.name, "arguments": json.dumps(b.input)}}
                     for b in blocks if b.type == "tool_use"]
            entry = {"role": "assistant", "content": text or None}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
        elif all(b.type == "tool_result" for b in blocks):
            for b in blocks:
                prefix = "Error: " if getattr(b, "is_error", False) else ""
                out.append({"role": "tool", "tool_call_id": b.tool_use_id, "content": prefix + b.content})
        else:
            out.append({"role": "user", "content": "".join(b.text for b in blocks if b.type == "text")})
    return out


def to_openai_tools(tools: list) -> list[dict]:
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in tools]


class _Messages:
    def __init__(self, client: "OpenRouterClient"):
        self.client = client

    def create(self, *, system=(), messages, tools=(), max_tokens=2000, **_ignored):
        # **_ignored: model (the adapter has its own), output_config, cache_control: Anthropic-only.
        body = {
            "model": self.client.model,
            "max_tokens": max_tokens,
            "messages": to_openai_messages(list(system), messages),
            "tools": to_openai_tools(list(tools)),
            "provider": PRIVACY,
        }
        reply = self.client.post(body)
        choice = reply["choices"][0]
        message = choice.get("message") or {}
        content = []
        if message.get("content"):
            content.append(SimpleNamespace(type="text", text=message["content"]))
        for call in message.get("tool_calls") or []:
            content.append(SimpleNamespace(type="tool_use", id=call["id"], name=call["function"]["name"],
                                           input=json.loads(call["function"]["arguments"] or "{}")))
        if choice.get("finish_reason") == "content_filter":
            stop_reason = "refusal"
        else:
            stop_reason = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        usage = reply.get("usage") or {}
        self.client.total_cost += usage.get("cost") or 0
        if reply.get("provider"):
            self.client.providers.add(reply["provider"])
        return SimpleNamespace(
            content=content, stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=usage.get("prompt_tokens", 0),
                                  output_tokens=usage.get("completion_tokens", 0)),
        )


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, model: str = "z-ai/glm-5.3-flash", post=None):
        self.model = model
        self.post = post or _http_post(api_key or os.environ["OPENROUTER_API_KEY"])
        self.total_cost = 0.0  # dollars, as reported by OpenRouter
        self.providers: set[str] = set()  # which hosting companies served the requests
        self.messages = _Messages(self)
