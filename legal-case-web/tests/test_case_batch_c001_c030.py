"""30 件去識別化候選罪名回歸案例。

這批案例只驗證候選方向保留，不把候選當作法律結論；缺事實與代稱不明
案例仍須由後續 v3 狀態與人工審核處理。
"""

from app.rules import candidate_offenses, classify_candidates
from tests.helpers import BANK


CASES = [
    ("C001", "甲於夜間潛入乙住宅後院，以工具撬開後門進入屋內，竊取乙放置於客廳之現金及金飾後逃逸。乙返家後發現財物失竊並報案。", "aggravated_theft"),
    ("C002", "甲進入某住家取走財物後離開。事主發現東西不見。", "theft"),
    ("C003", "某人夜晚到一間房子拿了東西就走。屋主回來發現少了物品。", "theft"),
    ("C004", "甲持刀至乙經營之商店，以言語及動作威脅乙交出櫃內現金，乙因恐懼而交付後，甲取走現金離去。", "robbery"),
    ("C005", "甲到店裡要店員拿錢，店員給了就走。", "robbery"),
    ("C006", "有人拿著東西去一家店，要店裡的人給錢，對方給了就離開。", "robbery"),
    ("C007", "甲透過通訊軟體向乙佯稱可代購稀有商品，要求乙先匯款訂金，乙匯款後甲即失聯，未交付任何商品。", "fraud"),
    ("C008", "甲跟乙說有好東西，乙就匯了錢，之後聯絡不上。", "fraud"),
    ("C009", "有人用訊息跟另一個人說可以幫忙買東西，對方匯了款後就沒消息。", "fraud"),
    ("C010", "甲因細故與乙發生爭執，徒手毆打乙臉部及身體數下，致乙受有瘀傷及擦傷。", "injury"),
    ("C011", "甲和乙吵架，甲動手打了乙，乙有傷。", "injury"),
    ("C012", "兩個人因為小事起衝突，其中一方打了另一方，對方身上有痕跡。", "injury"),
    ("C013", "甲多次以簡訊及電話向乙表示「再出現就讓你後悔」，並於乙住家附近徘徊，使乙心生畏懼。", "intimidation"),
    ("C014", "甲對乙說了一些話，乙覺得很害怕。", "intimidation"),
    ("C015", "有人用訊息和電話對另一個人說了一些內容，對方感到不安。", "intimidation"),
    ("C016", "甲於公開場合當眾以言語辱罵乙「騙子、不要臉」，並散布不實訊息指乙侵占款項，經乙提出告訴。", "defamation"),
    ("C017", "甲在很多人面前說乙的壞話，乙覺得很丟臉。", "defamation"),
    ("C018", "某人在公開地方對另一個人說了難聽的話，並傳了一些訊息。", "defamation"),
    ("C019", "甲於員警執行臨檢勤務時，以推拉及言語阻撓，致員警無法完成勤務，經當場制止。", "obstruction"),
    ("C020", "甲在警察處理事情時插手，警察無法順利進行。", "obstruction"),
    ("C021", "有人在執法人員執行工作時加以干擾，使工作無法繼續。", "obstruction"),
    ("C022", "甲未經乙同意，於夜間以鑰匙開啟乙住宅大門進入屋內，經乙發現後報案。", "residential_trespass"),
    ("C023", "甲進了乙的家，乙發現後報警。", "residential_trespass"),
    ("C024", "有人沒有經過允許就進了一間住家，屋主發現了。", "residential_trespass"),
    ("C025", "甲因與乙有糾紛，持棍棒將乙停放於路邊之機車車體及後照鏡砸毀，造成損壞。", "damage"),
    ("C026", "甲把乙的車弄壞了，乙發現後報案。", "damage"),
    ("C027", "有人因為糾紛把另一個人的交通工具弄得不能用。", "damage"),
    ("C028", "甲連續數週於乙通勤路線及住家附近尾隨，並多次寄送未署名信件及禮物，經乙表示拒絕後仍持續，使乙感到不安。", "stalking"),
    ("C029", "甲一直跟著乙，乙覺得很煩。", "stalking"),
    ("C030", "有人長時間在另一個人附近出現並送東西，對方不喜歡但對方沒停。", "stalking"),
]


def test_c001_c030_candidate_directions_are_retained():
    for case_id, summary, expected in CASES:
        actual = {item["id"] for item in classify_candidates(summary, BANK)["candidates"]}
        assert expected in actual, f"{case_id}: expected {expected}, actual={sorted(actual)}"


def test_candidates_expose_missing_element_metadata():
    candidate = next(
        item for item in candidate_offenses(CASES[0][1], BANK)
        if item["id"] == CASES[0][2]
    )
    assert isinstance(candidate["missing"], list)


def test_fallback_status_and_subject_gap_are_preserved():
    result = classify_candidates(CASES[2][1], BANK)
    assert result["status"] == {
        "subject_identified": "false",
        "has_victim": "true",
        "is_solved": "unknown",
    }
    theft = next(item for item in result["candidates"] if item["id"] == "theft")
    assert "主體不明" in theft["missing"]


def test_residential_trespass_is_explicit_model_supplement():
    result = classify_candidates(
        "甲未經乙同意，於夜間以鑰匙開啟乙住宅大門進入屋內，經乙發現後報案。",
        BANK,
    )
    supplement = next(item for item in result["candidates"] if item["id"] == "residential_trespass")
    assert supplement["name"].endswith("（模型補充）")
    assert supplement["source"]["status"] == "NOT_FOUND"
