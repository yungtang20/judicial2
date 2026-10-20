"""問句生成穩定性與品質回歸（前一輪品質檢查結論）。

前一輪外部比對（TLR／官方裁判）只證明了既有流程「三次重建一致」，
本檔把該性質固定為回歸測試：任何人改動 build_questions 或題庫後，
同一輸入必須得到完全相同的問句輸出，且軟性品質檢核不得出現 problems。

注意：這裡驗證的是工程可重現性與題目 metadata 完整性，
不構成法律內容的正確性驗收；法律正確性仍需個案人工審核。
"""

from __future__ import annotations

import hashlib
import json

from app.questions import enrich_question_metadata, validate_generated_questions
from app.rules import build_questions
from tests.helpers import BANK


_OFFENDERS = [offense["id"] for offense in BANK["offenses"]]
_ROLES = ("victim", "suspect", "transfer")
_RUNS = 3


def _fingerprint(questions: list[dict]) -> str:
    payload = json.dumps(
        [
            [question["id"], question["text"], question.get("kind"), question.get("offense_id")]
            for question in questions
        ],
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_all_offense_role_question_sets_are_bit_stable_across_rebuilds():
    """同一（罪章, 角色）連續重建三次，問句身分與文字必須逐題一致。"""
    unstable = []
    for offense_id in _OFFENDERS:
        for role in _ROLES:
            fingerprints = {
                _fingerprint(build_questions(BANK, role, [offense_id]))
                for _ in range(_RUNS)
            }
            if len(fingerprints) != 1:
                unstable.append((offense_id, role, len(fingerprints)))
    assert not unstable, f"重建輸出不穩定：{unstable}"


def test_generated_questions_enrichment_and_validation_are_stable_and_clean():
    """enrichment 後同一輸入輸出一致，且品質檢核 problems 必須為空。"""
    dirty = []
    for offense_id in _OFFENDERS:
        for role in _ROLES:
            candidates = [{"id": offense_id, "offense_id": offense_id}]
            fingerprints = set()
            problems: list[str] = []
            for _ in range(_RUNS):
                questions = enrich_question_metadata(
                    build_questions(BANK, role, [offense_id]), {}, candidates
                )
                fingerprints.add(_fingerprint(questions))
                problems = validate_generated_questions(questions, role)["problems"]
            if len(fingerprints) != 1 or problems:
                dirty.append({
                    "offense_id": offense_id,
                    "role": role,
                    "fingerprints": len(fingerprints),
                    "problems": problems[:3],
                })
    assert not dirty, f"enrichment/品質檢核不穩定或有問題：{dirty[:5]}"


def test_offense_questions_carry_purpose_and_legal_targets():
    """每一題非公司／通用題都必須有 purpose 與 legal_targets（spec §7.2 雙鏈）。"""
    missing = []
    for offense_id in _OFFENDERS:
        for role in _ROLES:
            questions = enrich_question_metadata(
                build_questions(BANK, role, [offense_id]), {}, [{"id": offense_id}]
            )
            for question in questions:
                if question["kind"] in {"company", "common"}:
                    continue
                meta = question.get("meta", {})
                if not meta.get("purpose") or not meta.get("legal_targets"):
                    missing.append((offense_id, role, question["id"]))
    assert not missing, f"缺 purpose/legal_targets：{missing[:5]}"


def test_company_standard_offenses_keep_verbatim_only_questions():
    """COMPANY_STANDARD_ONLY_OFFENSES 只允許公司核定題，不混入 md／JSON 題。

    `app.xlsm_questions.COMPANY_STANDARD_ONLY_OFFENSES` 規定：sexual_harassment
    與 stalking 已有公司逐字筆錄；victim／suspect 的 XLSM sheet 存在，
    runtime 不得混入本庫 markdown 或 JSON 問句，以免公司標準筆錄被改寫或重複。
    transfer（移送）角色沒有對應的公司 sheet，仍走本庫核心題，屬既有設計。
    """
    from app.xlsm_questions import COMPANY_STANDARD_ONLY_OFFENSES

    allowed_kinds = {"company", "common", "company_offense"}
    mixed = []
    for offense_id in sorted(COMPANY_STANDARD_ONLY_OFFENSES):
        for role in ("victim", "suspect"):
            questions = build_questions(BANK, role, [offense_id])
            for question in questions:
                if question["kind"] not in allowed_kinds:
                    mixed.append((offense_id, role, question["id"], question["kind"]))
    assert not mixed, f"公司逐字罪章混入主庫題目：{mixed[:5]}"
