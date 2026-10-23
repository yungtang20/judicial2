"""第五批候選罪名回歸案例（C126-C155）。

批次契約（`docs/HANDOFF_MANUAL.md` §6）：每批至少包含完整事實、缺事實、
主體不明三類，並對完整事實鎖定允許的相鄰競爭假設，使「多列」也會被測試抓到。

編號說明：原始需求以 C121-C150 標示，但 C121-C125 已由第四批
（`tests/test_case_batch_c091_c120.py`）使用且內容不同。為維持 `case_id`
唯一，本批順延為 C126-C155；原始編號保留在 `ORIGINAL_CASE_IDS`，兩者
一對一，並由 `test_original_case_ids_are_mapped_one_to_one` 鎖定。

原則：候選方向不等於法律結論；缺事實與主體不明案例仍由 v3 狀態與人工
審核處理。本批案例全部為虛構文字，不含真實個資。
"""

from app.rules import classify_candidates
from tests.helpers import BANK


# 完整事實案例：預期候選必須保留，且不得出現允許集合以外的候選。
CASES = [
    # 原始 C121：清晨自未上鎖後門侵入住宅行竊。刑法 §321Ⅰ①「侵入住宅」
    # 不以夜間為要件，故預期為加重竊盜（theft 為其基礎方向）。
    ("C126", "甲於清晨趁乙尚未起床，自後門未上鎖處進入乙住家，翻找抽屜後竊取現金與金飾後離去。乙起床後發現財物失竊並報案。", "aggravated_theft"),
    ("C129", "甲持開山刀進入乙經營之小吃店，以言語及刀械威脅乙交出收銀機內現金，乙因恐懼交付後甲取走現金逃逸。", "robbery"),
    ("C132", "甲透過通訊軟體向乙佯稱可代購稀有商品，要求乙先匯款訂金，乙匯款後甲即失聯，未交付任何商品。", "fraud"),
    ("C135", "甲因細故與乙發生爭執，徒手毆打乙臉部及身體數下，致乙受有瘀傷及擦傷。", "injury"),
    ("C138", "甲多次以簡訊及電話向乙表示「再出現就讓你後悔」，並於乙住家附近徘徊，使乙心生畏懼。", "intimidation"),
    ("C141", "甲於公開場合當眾以言語辱罵乙「騙子、不要臉」，並散布不實訊息指乙侵占款項，經乙提出告訴。", "defamation"),
    ("C144", "甲於員警執行臨檢勤務時，以推拉及言語阻撓，致員警無法完成勤務，經當場制止。", "obstruction"),
    ("C147", "甲未經乙同意，於夜間以鑰匙開啟乙住宅大門進入屋內，經乙發現後報案。", "residential_trespass"),
    ("C150", "甲因與乙有糾紛，持棍棒將乙停放於路邊之機車車體及後照鏡砸毀，造成損壞。", "damage"),
    ("C153", "甲連續數週於乙通勤路線及住家附近尾隨，並多次寄送未署名信件及禮物，經乙表示拒絕後仍持續，使乙感到不安。", "stalking"),
]

# 缺事實案例：事實不足時仍保留候選方向，但要件缺口必須留給人工。
INCOMPLETE_CASES = [
    ("C127", "甲進了某間屋子拿走東西就走，屋主後來發現少了物品。", "theft"),
    ("C130", "甲到店裡要店員拿錢，店員給了就走。", "robbery"),
    ("C133", "甲跟乙說有好東西，乙就匯了錢，之後聯絡不上。", "fraud"),
    ("C136", "甲和乙吵架，甲動手打了乙，乙有傷。", "injury"),
    ("C139", "甲對乙說了一些話，乙覺得很害怕。", "intimidation"),
    ("C142", "甲在很多人面前說乙的壞話，乙覺得很丟臉。", "defamation"),
    ("C145", "甲在警察處理事情時插手，警察無法順利進行。", "obstruction"),
    ("C148", "甲進了乙的家，乙發現後報警。", "residential_trespass"),
    ("C151", "甲把乙的車弄壞了，乙發現後報案。", "damage"),
    ("C154", "甲一直跟著乙，乙覺得很煩。", "stalking"),
]

# 主體不明案例：不得自行補上人物，方向保留且缺口須標示。
UNKNOWN_SUBJECT_CASES = [
    ("C128", "有人從窗戶進了一間房子，拿走一些物品後離開，住戶回來發現東西不見。", "theft"),
    ("C131", "有人拿著東西去一家店，要店裡的人給錢，對方給了就離開。", "robbery"),
    ("C134", "有人用訊息跟另一個人說可以幫忙買東西，對方匯了款後就沒消息。", "fraud"),
    ("C137", "兩個人因為小事起衝突，其中一方打了另一方，對方身上有痕跡。", "injury"),
    ("C140", "有人用訊息和電話對另一個人說了一些內容，對方感到不安。", "intimidation"),
    ("C143", "某人在公開地方對另一個人說了難聽的話，並傳了一些訊息。", "defamation"),
    ("C146", "有人在執法人員執行工作時加以干擾，使工作無法繼續。", "obstruction"),
    ("C149", "有人沒有經過允許就進了一間住家，屋主發現了。", "residential_trespass"),
    ("C152", "有人因為糾紛把另一個人的交通工具弄得不能用。", "damage"),
    ("C155", "有人長時間在另一個人附近出現並送東西，對方不喜歡但對方沒停。", "stalking"),
]

# 需求端原始編號 → 倉庫編號。保留原始編號是為了讓需求、審查紀錄與測試輸出
# 能互相對照；`case_id` 本身仍必須唯一。
ORIGINAL_CASE_IDS = {
    "C126": "C121",
    "C127": "C122",
    "C128": "C123",
    "C129": "C124",
    "C130": "C125",
    "C131": "C126",
    "C132": "C127",
    "C133": "C128",
    "C134": "C129",
    "C135": "C130",
    "C136": "C131",
    "C137": "C132",
    "C138": "C133",
    "C139": "C134",
    "C140": "C135",
    "C141": "C136",
    "C142": "C137",
    "C143": "C138",
    "C144": "C139",
    "C145": "C140",
    "C146": "C141",
    "C147": "C142",
    "C148": "C143",
    "C149": "C144",
    "C150": "C145",
    "C151": "C146",
    "C152": "C147",
    "C153": "C148",
    "C154": "C149",
    "C155": "C150",
}

# 完整事實案例的允許候選集合：預期方向之外的相鄰競爭假設須經人工區辨，
# 不視為誤列；集合外的候選即為誤列。
ALLOWED_EXTRAS = {
    # 侵入住宅竊盜：§320 基礎方向，以及題庫尚無獨立項目的 §306 侵入住宅。
    "C126": {"theft", "residential_trespass"},
    # 強盜：竊盜與恐嚇只作相鄰競爭假設（HINT_ONLY）。
    "C129": {"theft", "intimidation"},
    "C132": set(),
    "C135": set(),
    "C138": set(),
    "C141": set(),
    "C144": set(),
    "C147": set(),
    "C150": set(),
    "C153": set(),
}

# 缺事實與主體不明案例只鎖定「多列」：本批實測皆只有單一方向。
INCOMPLETE_ALLOWED_EXTRAS = {
    "C127": set(),
    "C130": set(),
    "C133": set(),
    "C136": set(),
    "C139": set(),
    "C142": set(),
    "C145": set(),
    "C148": set(),
    "C151": set(),
    "C154": set(),
}

UNKNOWN_ALLOWED_EXTRAS = {
    # 從窗戶進入住宅取財亦可能構成 §321Ⅰ② 越窗加重竊盜，屬相鄰方向。
    "C128": {"aggravated_theft", "residential_trespass"},
    "C131": set(),
    "C134": set(),
    "C137": set(),
    "C140": set(),
    "C143": set(),
    "C146": set(),
    "C149": set(),
    "C152": set(),
    "C155": set(),
}


def _candidates(summary):
    return {item["id"]: item for item in classify_candidates(summary, BANK)["candidates"]}


def _ids(summary):
    return set(_candidates(summary))


def test_complete_case_directions_are_retained():
    for case_id, summary, expected in CASES:
        assert expected in _ids(summary), f"{case_id}: actual={sorted(_ids(summary))}"


def test_complete_cases_have_no_unexpected_candidates():
    for case_id, summary, expected in CASES:
        extra = _ids(summary) - {expected} - ALLOWED_EXTRAS[case_id]
        assert not extra, f"{case_id}: unexpected extra candidates {sorted(extra)}"


def test_complete_cases_are_eligible_except_missing_bank_item():
    """完整事實的方向必須是 ELIGIBLE，唯一例外是題庫缺 §306 獨立項目。

    侵入住宅（§306）目前沒有題庫項目，引擎只能以 `HINT_ONLY` 呈現並附上
    「題庫缺少第306條獨立項目」的保留說明；本測試把這個限制寫死，避免
    日後誤以為該方向已可作為主要候選。
    """

    for case_id, summary, expected in CASES:
        candidate = _candidates(summary)[expected]
        if expected == "residential_trespass":
            assert candidate["candidate_eligibility"] == "HINT_ONLY", case_id
            assert "第306條" in candidate["reservation_reason"], case_id
        else:
            assert candidate["candidate_eligibility"] == "ELIGIBLE_CANDIDATE", case_id


def test_incomplete_cases_keep_direction_and_leave_element_gaps():
    for case_id, summary, expected in INCOMPLETE_CASES:
        candidates = _candidates(summary)
        assert expected in candidates, f"{case_id}: actual={sorted(candidates)}"
        assert candidates[expected]["missing"], f"{case_id}: 缺事實案例必須留下要件缺口"
        extra = set(candidates) - {expected} - INCOMPLETE_ALLOWED_EXTRAS[case_id]
        assert not extra, f"{case_id}: unexpected extra candidates {sorted(extra)}"


def test_unknown_subject_cases_are_flagged_not_filled_in():
    for case_id, summary, expected in UNKNOWN_SUBJECT_CASES:
        result = classify_candidates(summary, BANK)
        assert result["status"]["subject_identified"] == "false", case_id
        candidates = {item["id"]: item for item in result["candidates"]}
        assert expected in candidates, f"{case_id}: actual={sorted(candidates)}"
        assert "主體不明" in candidates[expected]["missing"], case_id
        extra = set(candidates) - {expected} - UNKNOWN_ALLOWED_EXTRAS[case_id]
        assert not extra, f"{case_id}: unexpected extra candidates {sorted(extra)}"


def test_robbery_keeps_adjacent_directions_as_competition_hypotheses_only():
    candidates = _candidates(CASES[1][1])
    assert candidates["robbery"]["candidate_eligibility"] == "ELIGIBLE_CANDIDATE"
    for offense_id in ("theft", "intimidation"):
        assert candidates[offense_id]["candidate_eligibility"] == "HINT_ONLY", offense_id
        assert "競爭假設" in candidates[offense_id]["reservation_reason"], offense_id


def test_bare_entry_without_intrusion_signal_stays_ordinary_theft():
    """「進了某間屋子拿走東西」未描述侵入方式或住宅性質，不得升為加重竊盜。

    這是 §321Ⅰ① 情境分支的反向鎖定：只有同時具備侵入訊號、進入住宅、
    取財事實才觸發；否則僅保留 §320 竊盜方向。
    """

    actual = _ids(INCOMPLETE_CASES[0][1])
    assert "theft" in actual
    assert "aggravated_theft" not in actual


def test_daytime_residential_intrusion_is_aggravated_theft():
    """白天自後門侵入住宅行竊仍屬 §321Ⅰ①；此分支 2026-10-23 補上。

    舊情境把「侵入住宅」與夜間／工具綁在一起，清晨自未上鎖後門侵入
    （本批 C126）只得到 §320，漏掉加重事由。
    """

    candidates = _candidates(CASES[0][1])
    assert candidates["aggravated_theft"]["candidate_eligibility"] == "ELIGIBLE_CANDIDATE"
    assert candidates["aggravated_theft"]["matched_terms"] == ["侵入住宅竊盜情境"]


def test_night_entry_with_permission_is_not_aggravated_theft():
    """「夜間進入住宅」本身不是侵入訊號。

    §321Ⅰ① 要求的是「侵入」（未經允許／擅自等），不是時段。若只憑夜間
    就升為加重竊盜，會把經同意入內修繕、臨時起意取財誤判為加重竊盜。
    """

    summary = "甲於夜間進入乙住家協助修繕水管，離去時取走客廳抽屜內現金。"
    actual = _ids(summary)
    assert "theft" in actual
    assert "aggravated_theft" not in actual


def test_original_case_ids_are_mapped_one_to_one():
    """需求端 C121-C150 與倉庫端 C126-C155 必須一對一，避免對照失真。"""

    case_ids = {case[0] for case in CASES}
    case_ids |= {case[0] for case in INCOMPLETE_CASES}
    case_ids |= {case[0] for case in UNKNOWN_SUBJECT_CASES}
    assert set(ORIGINAL_CASE_IDS) == case_ids
    assert sorted(ORIGINAL_CASE_IDS.values()) == [f"C{n}" for n in range(121, 151)]
    assert len(set(ORIGINAL_CASE_IDS.values())) == len(ORIGINAL_CASE_IDS)
