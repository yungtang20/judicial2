"""載入邊界問句衛生：他案殘留、角色錯置、正規化去重。

測試字串取自 QA 實測（%TEMP%\\qa_report.txt）之完整問句原文。
"""

from __future__ import annotations

import pytest

from app.question_hygiene import RULES, classify, normalize
from app.workflow import apply_action, create_case
from app.xlsm_questions import load_xlsm_questions
from tests.helpers import BANK, intake


# ── 實測證據原文 ──

UMBRELLA_ARTIFACT = (
    "依北市警刑偵字第1133115422號所分，按刑法第337條所規定侵占遺失物、漂流物或其他離本人持有之物，"
    "係指該物並非出於本人意思而脫離本人持有，且尚未落入任何人管領而持有之物，亦即依法律及一般社會通念"
    "尚難謂該物已與他人具有事實上監督及管領之支配關係而言。行為人取得該物時，該物若尚在持有權人支配管領"
    "所及範圍，應論以竊盜之罪，反之則應論以刑法第337條侵占遺失物、漂流物或其他離本人持有之物罪"
    "（最高法院110年度台上字第3477號判決意旨參照）。本案被害人將其雨傘置放於自家店外傘架上，"
    "該物仍在其支配管領範圍內，而遭不明人士取走，應受理竊盜罪(列為第一案類)為宜。請問你是否清楚？要提告何告訴？"
)
SUSPECT_CASE_DATE = "警方告知今(24)日因處理「〈代號〉-〈代號〉」115年03月23日所提性騷擾申訴及告訴事件通知你到場製作調查筆錄，是否清楚？"
FRAUD_PLAIN_DAY = "你(29)日因何事至本所製作詢問筆錄？"
SUSPECT_SLASH_DAY = "你今（6/19）因何事前來派出所製作調查筆錄？"
SUSPECT_INJURY_VICTIM_PHRASE = "你於何時、何地如何遭人傷害？因何事與對方起爭執？他為何要傷害你？請詳述案發經過。"
VICTIM_ASKS_ABOUT_VICTIM = "你是否認識被害人？是否曾有仇怨糾紛或借貸關係？"

# 合法問句（必須維持 SERVE）
SUSPECT_QUOTES_VICTIM = "被害人向警方指稱…（被害人對行為人之指訴內容），是否屬實?"
SUSPECT_KNOWS_VICTIM = "你是否認識被害人？"
# 「遭人」描述的是被害人報案內容或他人對涉嫌人的對待，不是在把涉嫌人當被害人問
SUSPECT_HEARS_DAMAGE_REPORT = "警方受理被害人報案稱渠所有之物品於案發時、地遭人毀損，你是否知悉此事？"
SUSPECT_ABUSE_DURING_FLIGHT = "遭警方逮捕時有無受傷？逃逸期間有無遭人虐待？"
VICTIM_CODE_TABLE = "〈代號〉-〈代號〉號姓名對照表(彌封)之年籍資料是否正確？是否為你本人？"

THEFT_SUMMARY = (
    "甲於114年3月1日15時許，在○○市○○區○○路1段1號便利商店內，趁店員不注意，"
    "徒手拿取貨架上價值新臺幣500元之洗髮精1瓶放入背包，未結帳即離去，經店員發覺後報警查獲。"
)
PHONE_THEFT_SUMMARY = (
    "甲於114年3月1日15時許，在○○市○○區○○路1段1號便利商店內，趁店員不注意，"
    "竊取貨架上價值新臺幣500元之手機1支放入背包，未結帳即離去，經店員發覺後報警查獲。"
)


def _prepared_case(summary: str) -> dict:
    case = create_case(intake(summary=summary), BANK)
    return apply_action(case, "auto_prepare", {}, BANK)


@pytest.mark.parametrize(
    "text, role",
    [
        (UMBRELLA_ARTIFACT, "victim"),
        (SUSPECT_CASE_DATE, "victim"),
        (FRAUD_PLAIN_DAY, "victim"),
        (SUSPECT_SLASH_DAY, "suspect"),
    ],
)
def test_foreign_case_artifact_is_reference_only(text: str, role: str):
    verdict = classify(text, role)
    assert verdict.decision == "REFERENCE_ONLY"
    assert verdict.rule_id == "foreign_case_artifact"
    assert verdict.reason == "他案案情或日期殘留（company-standard 四）"


def test_foreign_case_artifact_leaves_neutral_question_served():
    verdict = classify("你於何時、何地發現財物遭竊？請詳述經過。", "victim")
    assert verdict.decision == "SERVE"


def test_foreign_case_instance_detail_is_reference_only():
    verdict = classify("你是否知悉你碰撞自小客貨6N-5698車體何處？", "suspect")
    assert verdict.decision == "REFERENCE_ONLY"
    assert verdict.rule_id == "foreign_case_instance_detail"


@pytest.mark.parametrize(
    "text",
    [SUSPECT_INJURY_VICTIM_PHRASE, "你於何時、何地遭受行為人實施性騷擾行為？請詳述案發過程"],
)
def test_role_inversion_quarantines_victim_phrasing_for_suspect(text: str):
    verdict = classify(text, "suspect")
    assert verdict.decision == "REFERENCE_ONLY"
    assert verdict.rule_id == "role_inversion"
    assert verdict.reason == "涉嫌人/證人題組含被害人語句（review-checklist 二）"


@pytest.mark.parametrize("text", [SUSPECT_QUOTES_VICTIM, SUSPECT_KNOWS_VICTIM])
def test_role_inversion_leaves_legitimate_suspect_questions_served(text: str):
    assert classify(text, "suspect").decision == "SERVE"


@pytest.mark.parametrize(
    "text", [SUSPECT_HEARS_DAMAGE_REPORT, SUSPECT_ABUSE_DURING_FLIGHT]
)
def test_role_inversion_leaves_victim_report_phrasing_served(text: str):
    assert classify(text, "suspect").decision == "SERVE"


def test_foreign_case_artifact_leaves_code_table_question_served():
    assert classify(VICTIM_CODE_TABLE, "victim").decision == "SERVE"


def test_role_inversion_victim_quarantines_self_directed_question():
    verdict = classify(VICTIM_ASKS_ABOUT_VICTIM, "victim")
    assert verdict.decision == "REFERENCE_ONLY"
    assert verdict.rule_id == "role_inversion_victim"
    assert verdict.reason == "被害人題組含他角色語句（review-checklist 二）"


def test_role_inversion_victim_leaves_victim_injury_question_served():
    assert classify(SUSPECT_INJURY_VICTIM_PHRASE, "victim").decision == "SERVE"


def test_normalize_folds_full_width_punctuation_and_whitespace():
    assert normalize(VICTIM_ASKS_ABOUT_VICTIM) == normalize("你是否認識被害人？是否曾有仇怨糾紛或借貸關係?")
    assert normalize(" 你 是 否 認 識 被 害 人 ？ ") == normalize("你是否認識被害人?")


def test_normalized_duplicate_is_dropped_at_load_boundary():
    served = load_xlsm_questions()
    texts = [item["text"] for item in served["suspect"]]
    assert VICTIM_ASKS_ABOUT_VICTIM in texts
    assert "你是否認識被害人？是否曾有仇怨糾紛或借貸關係?" not in texts
    dropped = [
        record for record in load_xlsm_questions.quarantine["suspect"]
        if record["rule_id"] == "duplicate_normalized"
    ]
    assert any(record["text"].endswith("借貸關係?") for record in dropped)
    assert all(record["decision"] == "DROP_DUPLICATE" for record in dropped)


def test_theft_case_serves_no_phone_question():
    case = _prepared_case(THEFT_SUMMARY)
    assert case.get("selected_offenses") == ["theft"]
    served = [question["text"] for question in case["questions"]]
    assert served
    assert not any("手機" in text for text in served)


def test_phone_theft_case_serves_phone_question():
    case = _prepared_case(PHONE_THEFT_SUMMARY)
    served = [question["text"] for question in case["questions"]]
    assert any("手機" in text for text in served)


@pytest.mark.parametrize(
    "fragment",
    ["雨傘", "6/19", "(29)日", "115年03月23日"],
)
def test_runtime_evidence_cells_are_quarantined_not_served(fragment: str):
    case = _prepared_case(THEFT_SUMMARY)
    served = [question["text"] for question in case["questions"]]
    quarantine = case["question_quarantine"]
    assert any(fragment in record["text"] for record in quarantine)
    assert not any(fragment in text for text in served)
    for record in quarantine:
        assert set(record) == {"text", "role", "source_cell", "rule_id", "decision", "reason"}
        assert record["decision"] in {"REFERENCE_ONLY", "DROP_DUPLICATE"}
        assert set(record["source_cell"]) == {"row", "col"}


def test_every_served_question_has_source():
    for summary in (THEFT_SUMMARY, PHONE_THEFT_SUMMARY):
        case = _prepared_case(summary)
        assert case["questions"]
        assert all(question.get("source") for question in case["questions"])


def test_company_bank_serves_no_foreign_or_role_inverted_cell():
    served = load_xlsm_questions()
    for rule in RULES:
        if rule.decision != "REFERENCE_ONLY" or rule.pattern is None:
            continue
        for role in rule.scope:
            for item in served.get(role, []):
                assert not rule.pattern.search(item["text"]), (rule.rule_id, item["text"])
