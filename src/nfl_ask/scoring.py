"""Fixed-rule scoring for the golden questions (no LLM grader): did the answer name the right
player or team, and state the right number at the precision it chose?"""

import re

NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")


def numbers(text: str) -> list[tuple[float, int]]:
    """(value, decimals) for each number written in `text`."""
    found = []
    for token in NUMBER.findall(text):
        cleaned = token.replace(",", "").lstrip("+")
        found.append((float(cleaned), len(cleaned.split(".")[1]) if "." in cleaned else 0))
    return found


def has_value(answer: str, expected: float, decimals: int, as_percent_too: bool = True) -> bool:
    """`expected` appears with at least `decimals` decimals, rounded correctly (as is, or x100)."""
    targets = [expected, expected * 100] if as_percent_too else [expected]
    for value, written in numbers(answer):
        if written < decimals:
            continue
        tolerance = 0.5 * 10 ** -written + 1e-9
        if any(abs(abs(t) - abs(value)) <= tolerance for t in targets):
            return True
    return False


def check(answer: str, kind: str, expected, row: dict, decimals: int = 0) -> bool:
    text = answer.lower()
    if kind == "name":
        return str(expected).split(".")[-1].lower() in text
    if kind == "full_name":  # passer_full_name ("Jordan Love"): a guessed first name fails
        return str(expected).lower() in text
    if kind == "team":
        words = str(row.get("team_name") or "").split()
        nickname = words[-1].lower() if words else ""
        return bool(re.search(rf"\b{re.escape(str(expected).lower())}\b", text)) or (nickname and nickname in text)
    if kind == "value":
        return has_value(answer, float(expected), decimals)
    if kind == "percent":
        return has_value(answer, float(expected), decimals, as_percent_too=False)
    if kind == "count":
        return any(value == float(expected) and written == 0 for value, written in numbers(answer))
    raise ValueError(f"Unknown check kind: {kind}")
