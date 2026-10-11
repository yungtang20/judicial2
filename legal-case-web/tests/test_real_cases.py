from __future__ import annotations

from app.rules import candidate_offenses
from tests.helpers import BANK


def test_real_line_warrant_arrest_yields_escape_and_fraud():
    candidates = candidate_offenses(
        "警方於上述時、地查獲通緝犯到案，通緝案由為詐欺，依法逮捕後解送地檢署。",
        BANK,
    )
    assert {item["id"] for item in candidates} >= {"escape", "fraud"}


def test_real_line_negligent_injury_food_case_yields_injury():
    candidates = candidate_offenses(
        "報案人外送訂購餐點，食用時發現包裝有紫色印泥油墨，食用後喉嚨不適噁心嘔吐腹瀉就醫，"
        "因店家疏失造成身體傷害，提出過失傷害告訴。",
        BANK,
    )
    assert candidates[0]["id"] == "injury"


def test_real_line_domestic_violence_yields_domestic_violence():
    candidates = candidate_offenses(
        "報案人稱丈夫情緒失控對渠辱罵並拿裝滿滾燙熱水的杯子潑向渠兩次，"
        "未潑到但造成心理驚嚇恐慌，表示暫不提出刑事告訴及聲請保護令，警方依職權家暴通報。",
        BANK,
    )
    assert "domestic_violence" in {item["id"] for item in candidates}


def test_real_line_stalking_group_message_yields_stalking():
    candidates = candidate_offenses(
        "報案人稱於上述時、地反覆持續收到行為人來訊騷擾，報案人曾告知該行為人彼此不熟，"
        "無須再私下聯繫，該行為人便傳報案人與行為人聊天之訊息內容至報案人工作群組，"
        "報案人認行為人前開行為已對其造成散播有害名譽訊息致報案人因而喪失該份工作，"
        "故今日至所提出跟蹤騷擾之告訴。",
        BANK,
    )
    assert candidates[0]["id"] == "stalking"
