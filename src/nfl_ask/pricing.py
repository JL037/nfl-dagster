"""Claude Haiku 5.5 prices, $ per token, for cost per question. (OpenRouter reports its own
cost per request, so GLM needs no table here.)"""

HAIKU_PRICES = {
    "input_tokens": 0.10e-6,
    "output_tokens": 0.50e-6,
    "cache_read_input_tokens": 0.01e-6,   # 10% of input
    "cache_creation_input_tokens": 0.125e-6,  # 125% of input (5-minute cache)
}


def haiku_cost(usage: dict) -> float:
    return sum(HAIKU_PRICES[name] * tokens for name, tokens in usage.items() if name in HAIKU_PRICES)
