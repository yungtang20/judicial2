"""白話情境語句提示的回歸測試（R1 探針實測漏失後的 recall 補強）。

背景：同一段事實用構成要件詞（既有人工核可語料）可命中候選，
但被害人白話描述（動手打／要讓我好看／摔壞／匯錢沒到貨／酒後開車／
跟在後面／群組罵我）曾造成零候選。`app.rules._PHRASE_HINTS` 只在
零關鍵字命中時觸發、沿用否定語句護欄，且僅建立 NEED_REVIEW 候選方向。

本檔不斷言任何法律結論；候選與問句仍是人工審查資料。
"""

from __future__ import annotations

from app.questions import enrich_question_metadata, validate_generated_questions
from app.rules import candidate_offenses
from tests.helpers import BANK


# 正例：白話描述 → 至少應建立對應罪章候選方向（R1 探針實測漏失例）。
PHRASE_HIT_CASES = [
    ("injury", "對方動手打我，我的頭被打了好幾下，腫起來。"),
    ("injury", "在夜市跟人發生爭執，對方推我撞到桌子，手臂瘀青。"),
    ("defamation", "他在網路群組罵我不要臉，還到處跟別人說我偷公司的錢。"),
    ("intimidation", "他傳訊息說要讓我好看，還說知道我家住哪裡。"),
    ("damage", "他把我的手機摔在地上，螢幕壞了。"),
    ("fraud", "網友叫我匯錢買手機，說好三天到貨，結果東西沒到人也不回覆。"),
    ("public_danger", "同事喝了酒還自己開車回家，在路上撞到電線桿。"),
    # 跟騷法 §3 要求「違反其意願」，正例敘述須含拒絕／反對事實
    # （人工審查 E-2 修正後補足，2026-10-20）。
    ("stalking", "前男友一直跟在我後面，還反覆傳訊息說要見面，我早已明確拒絕。"),
    ("robbery", "嫌犯在超商毆打店員並強搶收銀機內的現金。"),
    ("robbery", "我的手機在路上被人搶走了。"),
    ("embezzlement", "出納把公款轉入自己的帳戶，花用在個人消費上，拒不返還。"),
    ("obstruction", "交通警察要我配合酒精測試，我推開他並大聲罵他，阻止他執行職務。"),
    ("robbery", "甲沒有脅迫乙，丙脅迫丁交付現金。"),
    ("obstruction", "甲聲請停止執行，丙推打執勤員警。"),
    ("robbery", "甲從未脅迫乙，丙脅迫丁交付現金。"),
    # 真實書類敘述：反對事實以「告知無須再私下聯繫」表述（無須再＝
    # 違反其意願事實方向指標，跟騷法 §3 錨點）。
    ("stalking", "報案人曾告知該行為人彼此不熟，無須再私下聯繫，該行為人反覆持續來訊騷擾。"),
]

# 反例：否定語句不得觸發提示（既有關鍵字命中不受本機制影響，故
# 護欄例刻意避免會直接命中題庫關鍵字的詞）。
NEGATION_GUARDED_CASES = [
    ("injury", "他並沒有動手打我，只是拉了一下我的衣服，沒有造成任何傷口。"),
    ("intimidation", "他並未說要讓我好看，也沒表示知道我家住哪裡。"),
    ("public_danger", "同事沒有喝酒就開車回家，全程遵守交通規則。"),
    ("robbery", "他並沒有強搶收銀機的現金，只是只是站在超商門口聊天。"),
]

# 不得誤觸：普通對話／日常情境不應帶入候選。
FALSE_POSITIVE_CASES = [
    ("fraud", "我昨天跟朋友匯錢一起吃飯分攤，他都有確認收到。"),
    ("stalking", "媽媽叫我跟在妹妹後面去接她下課。"),
    ("public_danger", "聚會時大家喝酒聊開車技術，沒有人要駕駛。"),
    ("robbery", "同事說上次看新聞搶劫報導，提醒保管好隨身財物。"),
]

# 人工審查（2026-10-20）提出的五個近鄰負例：接近但缺構成要件區辨
# 事實的敘述，不得建立對應章候選（E-1～E-5 修正後的 precision 錨點）。
NEAR_MISS_CASES = [
    # 一般安全提醒沒有「惡害通知」內容（刑法 §305）。
    ("intimidation", "警衛在門口值勤時提醒我晚上回家的路上要小心一點。"),
    # 相約等人的日常互動沒有「違反其意願」（跟騷法 §3）。
    ("stalking", "同事每天下班都會在公司等我一起吃飯，我們事先約好的。"),
    # 口頭抱怨／辱罵不是「施強暴脅迫」（刑法 §135 第 1 項）。
    ("obstruction", "他把警察開罰的動作拍下來，還大聲抱怨罵了幾句，但完全沒有碰觸。"),
    # 只有威脅、沒有取財或使人交付事實（刑法 §328）。
    ("robbery", "對方放話威脅，要把我手機裡的照片公開給大家看。"),
    # 第三人欠款往來不是「自己持有之他人之物」（刑法 §335）。
    ("embezzlement", "會計說客戶不還欠款，這筆先掛在帳上。"),
    # ── 第二輪複審（2026-10-20 P0）指出之關鍵字／fallback 繞進路徑 ──
    # bank keyword（守候／徘徊守候）先建立候選，缺違反其意願事實須清除。
    ("stalking", "我們事先約好，他每天在公司門口守候接我下班。"),
    ("stalking", "他一直守候在我住處樓下等我。"),
    # 「公務員」keyword／含「妨害」的結構式 fallback，缺強暴脅迫須清除。
    ("obstruction", "我父親是公務員，這次會議都在討論年度預算。"),
    ("obstruction", "他在警察執勤時大聲抱怨，還說這樣會妨害公務，但完全沒有動手。"),
    # 手段＋財物名詞不足以成立；未要求取財或使人交付（刑法 §328）。
    ("robbery", "對方脅迫，要把我手機裡的照片公開給大家看。"),
    ("robbery", "他持著刀子喊著要搶奪，但最後沒有取走我的任何財物。"),
    # 保管／代關鍵字先建立候選，缺變易持有事實須清除（刑法 §335）。
    ("embezzlement", "他幫我代管這批貨物，合約到期我已請他全數返還完畢。"),
    ("embezzlement", "我都很小心保管客戶的物品，沒有占為己有，也沒有拒絕返還。"),
    # ── 第三輪複審（2026-10-20）指出之同句未綁定／泛用錨點繞進 ──
    ("stalking", "同事每天守候在公司門口，公司通知我無須再填寫報告。"),
    ("obstruction", "公務員依法執行職務，機關安排強制休假，全程沒有衝突。"),
    ("robbery", "對方脅迫，要把我手機裡的照片公開給大家看。"),
    ("robbery", "他持著刀子喊著要搶奪，但最後沒有取走我的任何財物。"),
    # ── 第四輪複審（2026-10-20）指出之「從未」否定詞表缺口 ──
    ("stalking", "我從未騷擾她，她也從未明確拒絕。"),
    ("obstruction", "員警依法執行職務，他從未攔阻或脅迫。"),
    ("robbery", "他從未脅迫，也沒有搶走。"),
    ("embezzlement", "他保管公款，從未侵占，也沒有拒不返還。"),
    # ── 第五輪複審（2026-10-20）指出之裸拒絕過／程序攔阻／泛用交付 ──
    ("stalking", "他騷擾同事，我拒絕過另一人的邀約。"),
    ("obstruction", "員警執行職務時，我依法聲請停止執行，以攔阻該執行。"),
    ("robbery", "他以脅迫方式使人交付報告。"),
    # ── 階段 2（2026-10-20）actor—conduct—target 交叉人物案例 ──
    # 關係綁定不成立的近鄰負例：
    # 甲反覆傳訊騷擾乙，丙拒絕另一人的邀約：拒絕者與被騷擾者不同，不得綁定。
    ("stalking", "甲反覆傳訊騷擾乙，丙拒絕過另一人的邀約。"),
]


def _candidate_ids(summary: str) -> set[str]:
    return {candidate["id"] for candidate in candidate_offenses(summary, BANK)}


def test_every_probed_fast_phrase_hint_yields_expected_candidate():
    missing = []
    for offense_id, summary in PHRASE_HIT_CASES:
        ids = _candidate_ids(summary)
        if offense_id not in ids:
            missing.append((offense_id, summary))
    assert not missing, f"白語句提示漏失：{missing}"


def test_negated_phrases_do_not_trigger_hints():
    leaked = []
    for offense_id, summary in NEGATION_GUARDED_CASES:
        if offense_id in _candidate_ids(summary):
            leaked.append((offense_id, summary))
    assert not leaked, f"否定語句仍觸發提示：{leaked}"


def test_plain_conversation_does_not_create_candidates():
    noisy = []
    for offense_id, summary in FALSE_POSITIVE_CASES:
        if offense_id in _candidate_ids(summary):
            noisy.append((offense_id, summary))
    assert not noisy, f"日常情境誤觸提示：{noisy}"


def test_near_miss_statute_elements_do_not_create_candidates():
    """人工審查（2026-10-20）近鄰負例：缺構成要件區辨事實的敘述不得
    建立對應章候選。此測試僅鎖定提示層候選方向的精度錨點，不得用於
    判定任何法律要件成立。"""
    leaked = []
    for offense_id, summary in NEAR_MISS_CASES:
        if offense_id in _candidate_ids(summary):
            leaked.append((offense_id, summary))
    assert not leaked, f"近鄰負例仍觸發對應章候選：{leaked}"


def test_quoted_allegation_does_not_create_theft_candidate():
    """被罵時引述「說我偷錢」是妨害名譽的爭執內容，不得由關鍵字
    「偷」建立竊盜正式候選；但摘要有獨立取財事實時不受影響。"""
    summary = "他在網路群組罵我不要臉，還到處跟別人說我偷公司的錢。"
    ids = _candidate_ids(summary)
    assert "theft" not in ids, f"轉述指控仍建立竊盜候選：{ids}"
    assert "defamation" in ids, "妨害名譽候選仍須存在"


def test_real_theft_facts_are_not_suppressed_by_the_guard():
    suppressed = []
    for summary in [
        "同事告訴我，有人偷了我的機車。",  # 轉述第三人對第三人，非對本人指控
        "他到處說我偷公司的錢，但監視器畫面證明是另一名同事拿走了營業款。",
    ]:
        if "theft" not in _candidate_ids(summary):
            suppressed.append(summary)
    assert not suppressed, f"真實取財事實遭護欄誤傷：{suppressed}"


def test_attributed_allegations_do_not_create_candidates_across_chapters():
    """泛化轉述指控護欄：引用他人對本人指控的摘要不得建立對應
    罪章正式候選（R-fuzz 探針實測五個罪章都有雜訊）。"""
    noisy = []
    for offense_id, summary in [
        ("fraud", "他在群組說我詐騙他，可是我從來沒收過他的錢。"),
        ("intimidation", "有人跟主管說我恐嚇他，我只是提醒他排班規則。"),
        ("injury", "同事向警察說我打傷了他，當天我請假在家。"),
        ("embezzlement", "他跟公司說我侵占公款，我不能接受這種指控。"),
        ("stalking", "他向學校說我跟蹤他，我完全沒有去過他的教室。"),
    ]:
        if offense_id in _candidate_ids(summary):
            noisy.append((offense_id, summary))
    assert not noisy, f"轉述指控仍建立候選：{noisy}"


def test_attributed_scene_nouns_do_not_spawn_other_candidates():
    """引述句內的場景名詞（倉庫、存貨）不得為其他罪章建立關鍵字命中，
    也不得觸發財物路徑的關聯擴展（friend-q 探針原始雜訊四罪章）。"""
    assert not _candidate_ids("我同事跟老闆說我拿走倉庫的存貨，我根本沒進過倉庫。")
    assert not _candidate_ids("我媽跟訓導主任說我偷同學的錢，但我沒有拿任何東西。")


def test_attributed_guard_keeps_summary_with_independent_facts():
    suppressed = []
    for offense_id, summary in [
        ("fraud", "他跟別人說我詐騙他，但他確實匯款給我訂手機，後來東西未到貨。"),
        ("embezzlement", "他跟公司說我侵占公款，但我經手的帳目都有對帳單。"),
        ("injury", "他跟警察說我打傷了他，但他的驗傷單是三天前另一場糾紛的。"),
    ]:
        if offense_id not in _candidate_ids(summary):
            suppressed.append((offense_id, summary))
    assert not suppressed, f"獨立事實存在卻遭護欄誤傷：{suppressed}"


def test_hint_triggered_candidates_still_generate_clean_question_sets():
    """提示觸發後的完整流程仍必須可生成且品質檢核零 problems。"""
    dirty = []
    for offense_id, summary in PHRASE_HIT_CASES:
        candidates = [
            {"id": c["id"], "offense_id": c["id"]}
            for c in candidate_offenses(summary, BANK)
        ]
        questions = _build_questions(candidates)
        enriched = enrich_question_metadata(questions, {}, candidates)
        result = validate_generated_questions(enriched, "victim")
        if not questions or result["problems"]:
            dirty.append(
                {
                    "offense_id": offense_id,
                    "questions": len(questions),
                    "problems": result["problems"][:3],
                }
            )
    assert not dirty, f"提示候選的問句生成有問題：{dirty[:3]}"


def _build_questions(candidates):
    from app.rules import build_questions

    return build_questions(BANK, "victim", [c["id"] for c in candidates])


def test_hint_candidate_values_keep_machine_contracts():
    """提示建立的候選必須與既有候選相同的契約欄位與狀態。"""
    summary = "同事喝了酒還自己開車回家，在路上撞到電線桿。"
    candidate = next(
        candidate
        for candidate in candidate_offenses(summary, BANK)
        if candidate["id"] == "public_danger"
    )
    assert candidate["status"] == "NEED_REVIEW"
    assert candidate["selection_origin"] == "keyword_hint"
    assert candidate["prohibited_conclusions"] == [
        "犯罪成立",
        "故意成立",
        "因果關係成立",
        "競合成立",
    ]
    assert candidate["unknown_elements"], "候選必須保留待查要件清單"


def test_embezzlement_recount_narrative_gets_property_facts_and_questions():
    """「保管→拒不返還」敘述無「拿走」類動作詞，原不進屬性事實路徑、
    focused 屬性題為 0（覆蓋限制探針）。現在：持有訊號＋侵占動作雙條件
    以 rules.py 擴充（question_bank 關鍵字不動）；引述指控句不觸發本路徑
    （action 事實不得由被指控內容建立）。"""
    from app.rules import analyze_gate1, _property_taking_values
    from app.questions import build_property_taking_questions
    from tests.helpers import intake

    info = intake()
    info["summary"] = "店長保管公司公款之後拒不返還。"
    gate1 = analyze_gate1(info, use_ai=False)
    fact_keys = {f["fact_key"] for f in gate1["facts"] if f.get("fact_key")}
    assert {"action", "object"} <= fact_keys
    questions = build_property_taking_questions(
        "victim", {"embezzlement"}, gate1, None, "materialized:test"
    )
    assert len(questions) >= 3
    assert all(q["meta"]["mapping_version"] == "property-taking-v1" for q in questions)

    # 引述指控句不得建立屬性事實
    assert _property_taking_values("他跟公司說我侵占公款，我不能接受這種指控。") is None
    # 既有「拿走」路徑行為不變
    values = _property_taking_values("有人趁沒人注意拿走櫃檯相機。")
    assert values is not None and values["action"] == "取走物品"
    # 動詞前式敘述沒有「我的／把」結構 → object 依原設計為 UNKNOWN
    assert values["object"] == "UNKNOWN" and values["consent"] == "UNKNOWN"
