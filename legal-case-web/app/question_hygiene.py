"""問句衛生判定：載入公司題庫前，先決定每一格能否進訪談頻道。

依 questions/company-standard.md 第四節（不匯入已填寫實例的案情答案）與
questions/review-checklist.md 第一、二節（去重複、角色語句不得錯置）。
判定只決定「通道」，不修改公司原文：不合衛生的格子改列參考資料回報。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    scope: frozenset[str]
    pattern: re.Pattern[str] | None
    decision: str
    reason: str


@dataclass(frozen=True)
class Verdict:
    rule_id: str
    decision: str
    reason: str


ALL_ROLES = frozenset({"victim", "suspect", "witness", "transfer"})

# 他案案情或日期殘留。第三個複合樣式（`字第…號`）補足無外文前綴的公文文號
# （例：北市警刑偵字第1133115422號），只靠 [A-Z]{2,} 會漏掉中文機關前綴。
_FOREIGN_CASE_ARTIFACT = re.compile(
    "|".join((
        r"民國\d+年\d+月\d+日",
        r"(?<!\d)\d{3,4}年\d{1,2}月\d{1,2}日",
        r"今?[（(]\s*\d{1,2}\s*[）)]日?",
        r"(?<![\d:：])\d{1,2}/\d{1,2}(?![\d:：])",
        r"[A-Z]{2,}字第\d+號",
        r"字第\s*\d{3,}號",
    )),
)

# 他案已填寫實例的車牌等識別細節（company-standard 第四節）。
_INSTANCE_DETAIL = re.compile(r"(?<![A-Za-z0-9])[A-Z0-9]{1,3}-\d{3,4}(?![A-Za-z0-9])")

RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="foreign_case_artifact",
        scope=ALL_ROLES,
        pattern=_FOREIGN_CASE_ARTIFACT,
        decision="REFERENCE_ONLY",
        reason="他案案情或日期殘留（company-standard 四）",
    ),
    Rule(
        rule_id="foreign_case_instance_detail",
        scope=ALL_ROLES,
        pattern=_INSTANCE_DETAIL,
        decision="REFERENCE_ONLY",
        reason="他案已填寫實例細節（company-standard 四）",
    ),
    Rule(
        rule_id="role_inversion",
        scope=frozenset({"suspect", "witness"}),
        pattern=re.compile("|".join((r"遭人(?:傷害|毆打|攻擊)", r"遭受行為人", r"他為何要傷害你"))),
        decision="REFERENCE_ONLY",
        reason="涉嫌人/證人題組含被害人語句（review-checklist 二）",
    ),
    Rule(
        rule_id="role_inversion_victim",
        scope=frozenset({"victim"}),
        pattern=re.compile("|".join((r"是否認識被害人", r"遭受行為人", r"你於何時、何地遭受"))),
        decision="REFERENCE_ONLY",
        reason="被害人題組含他角色語句（review-checklist 二）",
    ),
    Rule(
        rule_id="duplicate_normalized",
        scope=ALL_ROLES,
        pattern=None,
        decision="DROP_DUPLICATE",
        reason="語意相同（review-checklist 一.6）",
    ),
)

SERVE = Verdict(rule_id="", decision="SERVE", reason="")

_PUNCTUATION_FOLD = str.maketrans({
    "？": "?", "！": "!", "，": ",", "。": ".", "、": ",",
    "：": ":", "；": ";", "（": "(", "）": ")",
    "「": '"', "」": '"', "『": '"', "』": '"', "〈": "<", "〉": ">",
    "－": "-", "\u3000": "",
})


def classify(text: str, role: str) -> Verdict:
    """依 RULES 順序判定單一格；第一個命中者決定通道，未命中即 SERVE。"""
    for rule in RULES:
        if rule.pattern is None or role not in rule.scope:
            continue
        if rule.pattern.search(text):
            return Verdict(rule_id=rule.rule_id, decision=rule.decision, reason=rule.reason)
    return SERVE


def duplicate_verdict() -> Verdict:
    """重複判定由載入器執行（classify 看不到先前的格子），規則資料仍取自同一表。"""
    rule = next(rule for rule in RULES if rule.rule_id == "duplicate_normalized")
    return Verdict(rule_id=rule.rule_id, decision=rule.decision, reason=rule.reason)


def normalize(text: str) -> str:
    """去重鍵：去除所有空白並折疊全形標點，使「？」與「?」等視為同一題。"""
    return re.sub(r"\s+", "", text.translate(_PUNCTUATION_FOLD))
