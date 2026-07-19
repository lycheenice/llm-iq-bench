"""IFEval 指令遵循校验器（逐条可验证指令）。

严格/宽松两档；未识别 instruction_id 标 fail 不崩。
对齐 google/IFEval 的指令语义子集（P0-5），P1 可扩展更多指令类型。
"""
from __future__ import annotations

import json
import re
from typing import Callable

_MISSING = object()


def check_instruction(instruction_id: str, kwargs: dict, response: str, strict: bool = True) -> bool:
    """单条指令校验。未识别 id 返回 False（forward-compat）。"""
    fn = INSTRUCTION_CHECKS.get(instruction_id)
    if fn is None:
        return False
    try:
        return bool(fn(response, kwargs or {}, strict))
    except Exception:
        return False


def score_response(response: str, instructions: list[dict], strict: bool = True) -> dict:
    """对一条响应算所有指令的 pass/fail，返回 {passed, total, details}。"""
    details = []
    passed = 0
    total = 0
    for ins in instructions or []:
        iid = ins.get("instruction_id") or ins.get("id")
        kw = ins.get("kwargs") or {}
        ok = check_instruction(iid, kw, response, strict)
        details.append({"id": iid, "passed": ok})
        total += 1
        if ok:
            passed += 1
    return {"passed": passed, "total": total, "details": details}


# ============================ 指令实现 ============================

def _count_sentences(response: str) -> int:
    """按 [.!?。！？] 终止符计数句子。"""
    cleaned = response.strip()
    if not cleaned:
        return 0
    # 句末标点切分，保留非空段
    parts = re.split(r"[.!?。！？]+", cleaned)
    parts = [p.strip() for p in parts if p.strip()]
    return len(parts) if parts else 1


def _count_words(response: str) -> int:
    """词数：英文按空白分词，中文按字符（CJK Unified）计。近似官方 IFEval 的 word count。"""
    cleaned = response.strip()
    if not cleaned:
        return 0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", cleaned))
    ascii_words = len(re.findall(r"[A-Za-z0-9']+", cleaned))
    return cjk + ascii_words


def _num_bullet_lines(response: str) -> int:
    """统计以 'N. ' 或 'N) ' 开头的行数（N 为数字）。"""
    lines = response.strip().splitlines()
    return sum(1 for ln in lines if re.match(r"\s*\d+[.)]\s+\S", ln))


def _num_sentences(response: str, kwargs: dict, strict: bool) -> bool:
    target = int(kwargs.get("num_sentences", 0))
    got = _count_sentences(response)
    if strict:
        return got == target
    return abs(got - target) <= 1


def _num_words(response: str, kwargs: dict, strict: bool) -> bool:
    target = int(kwargs.get("num_words", 0))
    got = _count_words(response)
    if strict:
        return got == target
    # loose: ±5% 或至少 ±1
    tol = max(1, int(target * 0.05))
    return abs(got - target) <= tol


def _number_bullet_lists(response: str, kwargs: dict, strict: bool) -> bool:
    target = int(kwargs.get("num_bullets", 0))
    got = _num_bullet_lines(response)
    if strict:
        return got == target
    return abs(got - target) <= 1


def _json_format(response: str, kwargs: dict, strict: bool) -> bool:
    s = response.strip()
    # 去除可能的 ```json fence
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s).strip()
    try:
        obj = json.loads(s)
    except Exception:
        return False
    if strict:
        return isinstance(obj, dict)
    return isinstance(obj, (dict, list))


def _no_comma(response: str, kwargs: dict, strict: bool) -> bool:
    return "," not in response and "，" not in response


def _quotation(response: str, kwargs: dict, strict: bool) -> bool:
    s = response.strip()
    return s.startswith('"') and s.endswith('"') and len(s) >= 2


def _capital_word(response: str, kwargs: dict, strict: bool) -> bool:
    """每个 ASCII 词首字母大写。"""
    words = re.findall(r"[A-Za-z]+", response)
    if not words:
        return False
    return all(w[:1].isupper() for w in words)


def _chinese_only(response: str, kwargs: dict, strict: bool) -> bool:
    """不含 ASCII 字母（中文场景）。"""
    return not re.search(r"[A-Za-z]", response)


INSTRUCTION_CHECKS: dict[str, Callable] = {
    "length_constraint:num_sentences": _num_sentences,
    "length_constraint:num_words": _num_words,
    "detectable_format:number_bullet_lists": _number_bullet_lists,
    "detectable_format:json_format": _json_format,
    "punctuation:no_comma": _no_comma,
    "startend:quotation": _quotation,
    "case:capital_word": _capital_word,
    "language:chinese_only": _chinese_only,
}
