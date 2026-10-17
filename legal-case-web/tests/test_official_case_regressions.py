from app.workflow import apply_action, create_case
from tests.helpers import BANK


FRAUD_SUMMARY = (
    "張紘愷於民國109年9月24日在Facebook手機買賣社團見朱敏瑄徵求手機之貼文後，"
    "於同日16時許，在新北市○○區○○路000巷00號住處，以臉書帳號私訊朱敏瑄，"
    "佯稱可以1,800元販賣iphone6s手機1支，致朱敏瑄陷於錯誤，"
    "於同日16時59分許轉帳匯款1,000元定金至張紘愷之郵局帳戶；"
    "張紘愷得款後又佯稱再匯款500元即可降價，朱敏瑄於翌日25日23時8分許再次匯款500元，"
    "嗣因遲未收到商品且得悉張紘愷並無手機可以給付，始悉受騙。"
    "證據有雙方網路對話訊息截圖、反詐騙諮詢專線紀錄表、帳戶交易清單。"
)

MEDICAL_NEGLIGENCE_SUMMARY = (
    "醫師丁立文於民國104年2月12日，在臺北市○○區○○路0段00號之台港華豪美診所，"
    "為孫嘉欣施行抽脂豐胸手術，於抽取腰部脂肪時，不慎使快速震動之抽脂管刺穿孫嘉欣之降結腸，"
    "導致孫嘉欣受有大腸穿孔併腹膜炎引發敗血症之傷害。"
    "孫嘉欣於104年2月14日前往國泰綜合醫院就診並接受大腸穿孔修補、膿瘍引流及人工腸造口手術。"
    "證據有診斷證明書、手術紀錄、住院病歷、手術照片、醫療影像光碟及醫事審議委員會鑑定書。"
)

DRUNK_DRIVING_SUMMARY = (
    "陳光軒於民國113年8月22日凌晨零時許，在苗栗縣○○市○○路00號餐酒館內飲用酒類後，"
    "仍於同日8時許駕駛自用小客車上路，於同日8時18分許在苗栗縣○○市○○路0000號旁，"
    "自後撞擊丁中瀚駕駛之自用小客車，無人受傷。警方到場後於同日8時44分許測得"
    "吐氣酒精濃度每公升0.32毫克。證據有酒精測定紀錄表、酒測器檢定合格證書、"
    "道路交通事故現場圖、事故調查報告表及現場照片。"
)

THEFT_DAMAGE_SUMMARY = (
    "甲於民國111年5月1日2時許，在臺北市○○區○○路停車場，"
    "破壞乙所有自用小客車之車窗玻璃，致車窗玻璃不堪使用，並開啟車門進入車內，"
    "取走乙放在車內之現金2萬元及筆記型電腦1台。現場監視器及車窗照片可供查證。"
)

OBSTRUCTION_INJURY_SUMMARY = (
    "甲於民國115年3月1日10時許，在桃園市殯葬服務中心辦公室前，"
    "欲強行進入辦公室，經正在執行門禁管理職務之公務員乙攔阻後，"
    "徒手揮打乙臉部及手部數十下，致乙受有左側顏面挫傷、左前臂挫傷。"
    "現場監視器及乙之診斷證明書可供查證。"
)


def _prepared(summary: str):
    return apply_action(
        create_case({"summary": summary, "has_victim": True}, BANK),
        "auto_prepare",
        {},
        BANK,
    )


def _assert_contains(values, *terms):
    joined = "｜".join(values)
    for term in terms:
        assert term in joined


def _pack_ids(case):
    return {
        question.get("meta", {}).get("pack_id")
        for question in case["questions"]
        if question.get("meta", {}).get("pack_id")
    }


def _assert_source_offsets(case, summary):
    for fact in case["gate1"]["facts"]:
        excerpt = fact.get("source_excerpt", "")
        if not excerpt:
            continue
        start = fact["source_start"]
        end = fact["source_end"]
        assert summary[start:end] == excerpt


def test_official_fraud_case_has_complete_gate1_and_exact_route():
    case = _prepared(FRAUD_SUMMARY)
    gate1 = case["gate1"]
    _assert_contains(gate1["people"], "張紘愷", "朱敏瑄")
    _assert_contains(gate1["objects"], "iphone6s", "1,000元", "500元")
    _assert_contains(
        gate1["times"],
        "民國109年9月24日16時許",
        "民國109年9月24日16時59分許",
        "民國109年9月25日23時8分許",
    )
    _assert_contains(gate1["behaviors"], "佯稱", "轉帳匯款")
    _assert_contains(gate1["results"], "遲未收到商品", "受騙")
    _assert_contains(gate1["evidence"], "網路對話訊息截圖", "帳戶交易清單")
    assert case["selected_offenses"] == ["fraud"]
    assert [route["route_id"] for route in case["selected_legal_routes"]] == ["fraud_339_general"]
    assert _pack_ids(case) == {"fraud_339_general"}
    assert not any(
        term in question["text"]
        for question in case["questions"]
        for term in ("信用卡", "收費設備", "自動付款設備", "重利")
    )
    assert {question["id"] for question in case["questions"] if question.get("meta", {}).get("known_from_summary")} >= {
        "Q-F339-REPRESENTATION", "Q-F339-DISPOSITION", "Q-F339-NONPERFORMANCE", "Q-F339-EVIDENCE",
    }


def test_official_medical_negligence_case_is_not_blocked_or_place_polluted():
    case = _prepared(MEDICAL_NEGLIGENCE_SUMMARY)
    gate1 = case["gate1"]
    _assert_contains(gate1["people"], "丁立文", "孫嘉欣")
    assert not any("就診並接受" in place for place in gate1["places"])
    _assert_contains(gate1["behaviors"], "抽脂管刺穿")
    _assert_contains(gate1["times"], "民國104年2月12日", "104年2月14日")
    _assert_contains(gate1["results"], "大腸穿孔", "腹膜炎", "敗血症")
    _assert_contains(gate1["evidence"], "診斷證明書", "醫事審議委員會鑑定書")
    assert case["selected_offenses"] == ["injury"]
    assert [route["route_id"] for route in case["selected_legal_routes"]] == ["injury_284_negligent"]
    assert _pack_ids(case) == {"injury_284_negligent"}
    assert not any("車禍當時" in question["text"] for question in case["questions"])


def test_official_drunk_driving_case_extracts_events_and_exact_route():
    case = _prepared(DRUNK_DRIVING_SUMMARY)
    gate1 = case["gate1"]
    _assert_contains(gate1["people"], "陳光軒", "丁中瀚")
    _assert_contains(gate1["behaviors"], "駕駛", "撞擊")
    _assert_contains(gate1["times"], "民國113年8月22日凌晨零時許", "民國113年8月22日8時許")
    _assert_contains(gate1["results"], "0.32毫克", "無人受傷")
    _assert_contains(gate1["evidence"], "酒精測定紀錄表", "事故現場圖")
    assert case["selected_offenses"] == ["public_danger"]
    assert [route["route_id"] for route in case["selected_legal_routes"]] == [
        "public_danger_185_3_impaired_driving"
    ]
    assert _pack_ids(case) == {"public_danger_185_3_impaired_driving"}
    assert not any("逃逸" in question["text"] for question in case["questions"] if question.get("offense_id") == "public_danger")


def test_theft_damage_case_keeps_both_offenses_and_one_route_each():
    case = _prepared(THEFT_DAMAGE_SUMMARY)
    assert set(case["selected_offenses"]) == {"theft", "damage"}
    routes = {route["route_id"] for route in case["selected_legal_routes"]}
    assert {"theft_320_1_movable", "damage_354_property"} <= routes
    assert _pack_ids(case) == {"theft_320_1_movable", "damage_354_property"}
    _assert_contains(case["gate1"]["objects"], "現金2萬元", "筆記型電腦1台", "車窗玻璃")
    _assert_contains(case["gate1"]["results"], "不堪使用")


def test_obstruction_injury_case_keeps_both_offenses_and_one_route_each():
    case = _prepared(OBSTRUCTION_INJURY_SUMMARY)
    assert set(case["selected_offenses"]) == {"obstruction", "injury"}
    routes = {route["route_id"] for route in case["selected_legal_routes"]}
    assert {"obstruction_135_violence_threat", "injury_277_general"} <= routes
    assert _pack_ids(case) == {"obstruction_135_violence_threat", "injury_277_general"}
    _assert_contains(case["gate1"]["people"], "甲", "乙")
    _assert_contains(case["gate1"]["behaviors"], "徒手揮打")
    _assert_contains(case["gate1"]["results"], "左側顏面挫傷", "左前臂挫傷")


def test_official_regression_cases_are_deterministic_and_fresh():
    for summary in (
        FRAUD_SUMMARY,
        MEDICAL_NEGLIGENCE_SUMMARY,
        DRUNK_DRIVING_SUMMARY,
        THEFT_DAMAGE_SUMMARY,
        OBSTRUCTION_INJURY_SUMMARY,
    ):
        first = _prepared(summary)
        second = _prepared(summary)
        assert first["case_id"] != second["case_id"]
        assert first["gate1"] == second["gate1"]
        assert first["selected_offenses"] == second["selected_offenses"]
        assert first["selected_legal_routes"] == second["selected_legal_routes"]
        _assert_source_offsets(first, summary)
