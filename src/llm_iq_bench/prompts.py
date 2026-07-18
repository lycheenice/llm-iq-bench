from __future__ import annotations

ALPHABET = "ABCDEFGH"


def render(template: str, sample: dict) -> str:
    if template == "raw":
        return sample.get("prompt") or sample.get("question", "")

    if template == "knowledge_mc":
        q = sample.get("question", "")
        choices = sample.get("choices", [])
        lines = [q, ""]
        for i, c in enumerate(choices):
            lines.append(f"{ALPHABET[i]}. {c}")
        lines.append("")
        lines.append("Answer with the letter of the correct choice.")
        return "\n".join(lines)

    if template == "knowledge_mc_cn":
        q = sample.get("question", "")
        choices = sample.get("choices", [])
        lines = [q, ""]
        for i, c in enumerate(choices):
            lines.append(f"{ALPHABET[i]}. {c}")
        lines.append("")
        lines.append("请直接回答选项字母。")
        return "\n".join(lines)

    if template == "reasoning_qa":
        q = sample.get("question", "")
        return f"{q}\n\nSolve it step by step. Put the final answer in \\boxed{{}}."

    if template == "code_complete":
        return f"Complete the following Python function. Only output code.\n\n{sample.get('prompt','')}"

    if template == "long_qa":
        ctx = sample.get("context", "")
        q = sample.get("question", "")
        return f"Read the following passage and answer.\n\n{ctx}\n\nQuestion: {q}"

    if template == "function_call":
        return f"{sample.get('prompt','')}\n\nRespond with a JSON function call."

    if template == "agent_task":
        return sample.get("question") or sample.get("prompt", "")

    q = sample.get("question") or sample.get("prompt", "")
    return q
