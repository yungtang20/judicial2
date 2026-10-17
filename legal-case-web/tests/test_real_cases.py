from __future__ import annotations

from app.rules import candidate_offenses
from app.workflow import apply_action, create_case
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


def test_prosecutor_style_threat_wording_yields_intimidation_candidate():
    candidates = candidate_offenses(
        "許金仙女於民國101年1月11日下午3時40分許，對邱翊婷揚言「打個半死」等語，致邱翊婷心生畏懼。",
        BANK,
    )
    assert "intimidation" in {item["id"] for item in candidates}


def test_plain_language_false_online_statement_yields_defamation_candidate():
    candidates = candidate_offenses(
        "丙○○於民國112年3月4日，在網路上刊登不實訊息，使甲○○名譽受損。",
        BANK,
    )
    assert "defamation" in {item["id"] for item in candidates}


def test_plain_language_hit_and_run_yields_public_danger_candidate():
    candidates = candidate_offenses(
        "張○○駕車發生交通事故致人受傷後，未停留處理即駕車離開現場。",
        BANK,
    )
    assert "public_danger" in {item["id"] for item in candidates}


def test_deprivation_and_armed_property_narrative_surfaces_both_directions():
    summary = (
        "被告等人持空氣槍及束帶脅迫被害人，限制其行動自由，"
        "並迫使被害人交付現金及簽立本票。"
    )
    candidates = candidate_offenses(summary, BANK)
    ids = {item["id"] for item in candidates if item["selection_origin"] != "related_hint"}
    assert {"liberty", "robbery"} <= ids


def test_minor_sexual_image_narrative_yields_child_protection_candidate():
    candidates = candidate_offenses(
        "行為人明知A女為12歲以上未滿18歲之少年，仍引誘A女於視訊中裸露身體，並截取其裸體照片及性影像。",
        BANK,
    )
    assert "child_protection" in {item["id"] for item in candidates}


def test_tl_rag_prosecutor_samples_are_new_cases_and_structured_without_storage():
    """以地檢署來源改寫的五個摘要各自建立新 case，不讀取或寫入案件儲存。"""
    samples = [
        ("甲○○與辛○○共同基於竊盜犯意，於民國113年1月24日晚上8時許，在臺北市○○區○○路工寮，竊得農藥噴霧機1台。", {"甲○○", "辛○○"}, "theft"),
        ("汪加禾於民國106年5月28日上午9時30分許，在臺北市○○區，先後以腳踢踹林慧靜、林楊阿差，致二人受傷，經報警處理。", {"汪加禾", "林慧靜", "林楊阿差"}, "injury"),
        ("甲○○於民國112年某日下午4時50分許，在臺北市萬華區廣州街夜市附近，見代號AW000-A112645號A男，手套弄A男生殖器而猥褻得逞。", {"甲○○", "A男"}, "sexual"),
        ("李貽龍於民國113年某日，在醫院病房內，強行親吻B女，將手伸入B女上衣內撫摸胸部，並試圖褪去B女外褲。", {"李貽龍", "B女"}, "sexual"),
        ("張博翔於民國113年某日，透過網路向被害人佯稱投資獲利，要求匯款，涉犯三人以上共同詐欺取財未遂罪。", {"張博翔"}, "fraud"),
    ]
    for summary, expected_people, expected_offense in samples:
        case = create_case({"summary": summary, "event_time": "UNKNOWN", "location": "UNKNOWN"}, BANK)
        assert expected_people <= set(case["gate1"]["people"])
        assert expected_offense in {item["id"] for item in case["candidates"]}
        assert "drugs" not in {item["id"] for item in case["candidates"]}
        assert all("涉犯" not in value for value in case["gate1"]["behaviors"])


def test_random_legal_case_style_summaries_auto_prepare_without_manual_offense_selection():
    samples = [
        "乙○○因積欠債務，意圖為自己不法所有，於民國112年2月6日凌晨0時53分許，前往臺中市某彩券行，攜帶主廚刀進入，持刀指向店員並進入櫃檯取走現金20萬1066元後逃逸。",
        "被告在彩券行對店員恫稱你再讓我等我就把你掀掉，並丟擲物品使店員心生畏懼。",
    ]
    for summary in samples:
        case = create_case({"summary": summary, "has_victim": True}, BANK)
        prepared = apply_action(case, "auto_prepare", {}, BANK)
        assert prepared["state"] == "GATE2_QA"
        assert prepared["selected_offenses"]
        assert prepared["questions"]


def test_nonconsensual_sex_and_recording_summary_is_structured_without_theft_false_positive():
    summary = (
        "事發於民國112年11月15日晚上約11點，在台北市信義區租屋處。我與老婆佩容因小孩發生爭執，"
        "佩容以想讓小孩多一個弟妹想與我性交，但我不同意，所以佩容稱我睡著時，偷偷的與我性交並內射？"
        "幾天後佩容拿那天偷拍我們性交的影片，又來威脅我與他性交"
    )
    case = create_case({"summary": summary, "has_victim": True}, BANK)
    gate1 = case["gate1"]
    assert gate1["times"] == ["民國112年11月15日晚上約11點"]
    assert gate1["places"] == ["台北市信義區租屋處"]
    assert "性交影片" in gate1["objects"]
    assert "性交行為" not in gate1["objects"]
    assert {"sexual", "privacy", "intimidation", "domestic_violence"} <= {
        item["id"] for item in case["candidates"]
    }
    assert "theft" not in {item["id"] for item in case["candidates"]}
    prepared = apply_action(case, "auto_prepare", {}, BANK)
    assert prepared["state"] == "GATE2_QA"
    assert prepared["selected_offenses"] == [
        "sexual", "privacy", "domestic_violence"
    ]


def test_opportunistic_sexual_assault_narrative_does_not_become_robbery_or_harassment():
    summary = (
        "趙子興與AW000-A114462（真實姓名及年籍詳卷，下稱A女）原本素不相識，"
        "趙子興透過網絡，委請A女於民國114年8月29日，至其經營且位在臺北市○○區○○路0段000巷0○0號"
        "「○○○○韓式烤肉專門店」拍攝宣傳影片，A女於當日晚間，在上址，因趙子興邀約飲用酒類後，"
        "已呈現嘔吐、全身癱軟無力之情狀，趙子興竟於乘機猥褻之犯意，先在上址洗手間內，"
        "乘A女不能抗拒之際，以雙手摟抱A女，其後將A女扶至店內合併之高腳椅上平躺後，"
        "親吻A女之嘴部、徒手伸入A女內衣中撫摸其胸部而對A女為猥褻行為得逞，"
        "適A女之男友○○○至店內並喝斥之，趙子興始停止。"
    )
    case = create_case({"summary": summary, "has_victim": True}, BANK)
    gate1 = case["gate1"]
    assert {"趙子興", "A女"} <= set(gate1["people"])
    assert "民國114年8月29日" in gate1["times"]
    assert any("韓式烤肉專門店" in item for item in gate1["places"])
    assert any("猥褻" in item for item in gate1["behaviors"])
    candidate_ids = {item["id"] for item in case["candidates"]}
    assert "sexual" in candidate_ids
    assert "robbery" not in candidate_ids
    assert "sexual_harassment" not in candidate_ids
    prepared = apply_action(case, "auto_prepare", {}, BANK)
    assert prepared["selected_offenses"] == ["sexual"]
    assert prepared["selected_legal_routes"][0]["route_id"] == "sexual_225_incapacity"
    assert "性交影片" not in gate1["objects"]
    known = [q for q in prepared["questions"] if q.get("meta", {}).get("known_from_summary")]
    assert any("身體接觸" in q["text"] for q in known)
    assert not any("通報" in q["text"] for q in known)


def test_intoxicated_minor_case_has_complete_gate1_exact_route_and_additional_questions_only():
    summary = (
        "林念澄與代號AW000-A113415(民國96年1月生，真實姓名年籍詳卷，下稱A女)及一群友人"
        "於113年8月10日22時許，在臺北市○○區○○街0段00號(THE 58 BAR)共同飲酒，"
        "俟A女飲用威士忌13至14杯，因受酒精之影響，呈現意識不清之泥醉狀態，並倒臥在上開酒吧前，"
        "詎林念澄於翌(11)日0時10分許，明知A女未滿18歲，竟基於乘機性交之犯意，"
        "利用A女不能或不知抗拒之情形，先用手撫摸A女之胸部、陰部，"
        "再將手指插入A女陰部抽動數次，而對A女性交得逞。嗣經路人發現，報警處理，始悉上情。"
    )
    case = create_case({"summary": summary, "has_victim": True}, BANK)
    gate1 = case["gate1"]

    assert gate1["people"] == ["AW000-A113415／A女", "林念澄", "一群友人", "路人"]
    assert gate1["times"] == ["民國113年8月10日22時許", "民國113年8月11日0時10分許"]
    assert gate1["places"] == ["臺北市○○區○○街0段00號(THE 58 BAR)", "THE 58 BAR前"]
    assert "將手指插入A女陰部抽動數次" in gate1["behaviors"]
    assert "意識不清之泥醉狀態" in gate1["results"]
    assert {"真實姓名年籍詳卷", "路人發現", "報警處理"} <= set(gate1["evidence"])
    assert "受酒精之影響" in gate1["causation"]
    assert "基於乘機性交之犯意" not in gate1["events"]
    assert "性交行為" not in gate1["objects"]
    assert gate1["unknowns"] == []
    assert all(
        fact["source_excerpt"] in summary
        for fact in gate1["facts"]
        if fact["source_excerpt"]
    )
    assert len({fact["fact_id"] for fact in gate1["facts"]}) == len(gate1["facts"])
    legal_facts = [fact for fact in gate1["facts"] if fact["fact_key"] == "legal_characterization"]
    assert legal_facts
    assert all(fact["machine_status"] == "ASSERTED_NOT_VERIFIED" for fact in legal_facts)
    resolved_times = [fact for fact in gate1["facts"] if fact["fact_key"] == "time"]
    assert [fact["source_excerpt"] for fact in resolved_times] == [
        "113年8月10日22時許", "翌(11)日0時10分許",
    ]
    assert len({fact["event_id"] for fact in resolved_times}) == 2

    assert case["intake"]["victim_identifier"] == "AW000-A113415"
    assert case["intake"]["victim_is_code"] is True
    assert [item["id"] for item in case["candidates"]] == ["sexual"]

    prepared = apply_action(case, "auto_prepare", {}, BANK)
    assert prepared["selected_offenses"] == ["sexual"]
    assert [item["route_id"] for item in prepared["selected_legal_routes"]] == ["sexual_225_incapacity"]
    assert prepared["candidates"][0]["legal_route_states"]["sexual_227_age"] == "EXCLUDED"

    route_questions = [item for item in prepared["questions"] if item.get("offense_id") == "sexual"]
    assert {item["meta"]["pack_id"] for item in route_questions} == {"sexual_225_incapacity"}
    known = [item for item in route_questions if item["meta"].get("known_from_summary")]
    assert {item["meta"]["fact_target"] for item in known} == {
        "victim_age_evidence", "event_time_place", "sexual_contact_details",
    }
    assert all(item["answer"] and item["meta"]["coverage_evidence"] for item in known)
    additional = [item for item in route_questions if not item["meta"].get("known_from_summary")]
    assert {item["meta"]["fact_target"] for item in additional} == {
        "capacity_detail",
        "memory_timeline",
        "state_observation_sources",
        "discovery_report_details",
        "scene_record_sources",
        "post_event_medical_evidence",
        "observable_prior_interaction",
    }
    assert all(item["meta"]["coverage_status"] == "UNCOVERED" for item in additional)
    forbidden = ("交通工具", "車輛", "兇器", "死亡", "重傷", "直系血親")
    assert not any(any(word in item["text"] for word in forbidden) for item in prepared["questions"])


def test_alcohol_without_driving_does_not_create_public_danger_candidate():
    candidates = candidate_offenses("甲女在酒吧飲酒後呈現酒醉狀態，由友人陪同返家。", BANK)
    assert "public_danger" not in {item["id"] for item in candidates}


def test_public_danger_requires_driving_context_but_retains_drunk_driving_recall():
    candidates = candidate_offenses("甲男飲酒後駕駛自用小客車上路，經攔查接受酒測。", BANK)
    assert "public_danger" in {item["id"] for item in candidates}
