"""The OpenRouter adapter: Anthropic-style requests in, Anthropic-style responses out, so the
same loop and rules run on GLM. Tested against a fake HTTP call: no network, no cost."""

import json
from types import SimpleNamespace

from nfl_ask.agent import TOOLS
from nfl_ask.openrouter import PRIVACY, OpenRouterClient


def fake_post(reply):
    sent = []

    def post(body):
        sent.append(body)
        return reply

    post.sent = sent
    return post


TEXT_REPLY = {
    "choices": [{"message": {"content": "Drake Maye was +0.295.", "tool_calls": None}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 900, "completion_tokens": 40, "cost": 0.00005},
    "provider": "InferenceNet",
}
TOOL_REPLY = {
    "choices": [{"message": {"content": None, "tool_calls": [{
        "id": "call_1", "type": "function",
        "function": {"name": "run_query", "arguments": json.dumps({"sql": "select 1", "params": ["D.Maye"]})},
    }]}, "finish_reason": "tool_calls"}],
    "usage": {"prompt_tokens": 800, "completion_tokens": 30, "cost": 0.00004},
    "provider": "InferenceNet",
}


def create(post, messages=None):
    client = OpenRouterClient(api_key="test", model="z-ai/glm-5.3-flash", post=post)
    response = client.messages.create(
        model="ignored-the-adapter-has-its-own",
        max_tokens=2000,
        system=[{"type": "text", "text": "RULES AND CATALOG", "cache_control": {"type": "ephemeral"}}],
        tools=TOOLS,
        output_config={"effort": "low"},
        messages=messages or [{"role": "user", "content": "How good was Drake Maye?"}],
    )
    return client, response


def test_every_request_carries_the_privacy_routing():
    """Only providers that keep no data and don't collect it may serve the request."""
    post = fake_post(TEXT_REPLY)
    create(post)
    assert post.sent[0]["provider"] == PRIVACY == {"zdr": True, "data_collection": "deny"}


def test_request_translation():
    post = fake_post(TEXT_REPLY)
    create(post)
    body = post.sent[0]
    assert body["model"] == "z-ai/glm-5.3-flash"
    assert body["messages"][0] == {"role": "system", "content": "RULES AND CATALOG"}
    assert body["messages"][1] == {"role": "user", "content": "How good was Drake Maye?"}
    names = [t["function"]["name"] for t in body["tools"]]
    assert names == ["run_query", "answer", "no_data"]
    assert body["tools"][0]["function"]["parameters"] == TOOLS[0]["input_schema"]


def test_text_reply_becomes_an_end_turn_with_usage_and_cost():
    _, response = create(fake_post(TEXT_REPLY))
    assert response.stop_reason == "end_turn"
    assert [b.type for b in response.content] == ["text"]
    assert response.content[0].text == "Drake Maye was +0.295."
    assert response.usage.input_tokens == 900 and response.usage.output_tokens == 40


def test_tool_call_becomes_a_tool_use_block():
    _, response = create(fake_post(TOOL_REPLY))
    assert response.stop_reason == "tool_use"
    block = response.content[0]
    assert (block.type, block.id, block.name) == ("tool_use", "call_1", "run_query")
    assert block.input == {"sql": "select 1", "params": ["D.Maye"]}


def test_cost_and_provider_are_tracked_across_calls():
    post = fake_post(TOOL_REPLY)
    client, _ = create(post)
    client.messages.create(model="x", max_tokens=1, system=[], tools=TOOLS, messages=[{"role": "user", "content": "q"}])
    assert abs(client.total_cost - 0.00008) < 1e-12
    assert client.providers == {"InferenceNet"}


def test_tool_round_trip_translates_back_to_openai_messages():
    """The loop appends the assistant's tool_use blocks and a user tool_result message."""
    post = fake_post(TEXT_REPLY)
    assistant_blocks = [
        SimpleNamespace(type="text", text="Let me check."),
        SimpleNamespace(type="tool_use", id="call_1", name="run_query",
                        input={"sql": "select 1", "params": []}),
    ]
    messages = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": assistant_blocks},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1",
                                      "content": '{"rows": []}', "is_error": True}]},
    ]
    create(post, messages)
    sent = post.sent[0]["messages"]
    assert sent[2] == {
        "role": "assistant", "content": "Let me check.",
        "tool_calls": [{"id": "call_1", "type": "function",
                        "function": {"name": "run_query", "arguments": json.dumps({"sql": "select 1", "params": []})}}],
    }
    assert sent[3] == {"role": "tool", "tool_call_id": "call_1", "content": 'Error: {"rows": []}'}


def test_content_filter_is_a_refusal():
    reply = {"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 0, "cost": 0}}
    _, response = create(fake_post(reply))
    assert response.stop_reason == "refusal"
