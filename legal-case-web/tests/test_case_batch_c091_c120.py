"""第四批候選罪名回歸案例（C091-C125）與反向安全案例。

批次契約（docs/HANDOFF_MANUAL.md §6）：每批至少包含完整事實、缺事實、
主體不明，以及「不應誤列該罪名的反向案例」四類。本批即依此契約撰寫。

原則：候選方向不等於法律結論；缺事實與主體不明案例仍須由後續 v3 狀態
與人工審核處理。
"""

from app.rules import classify_candidates
from tests.helpers import BANK


# 完整事實案例：預期候選必須保留。
CASES = [
    ("C091", "甲於夜間持工具撬開乙住家後門進入，翻找抽屜後竊取現金、金飾及手機後逃逸。乙返家發現財物失竊並報案。", "aggravated_theft"),
    ("C092", "甲趁乙外出上班時自陽台爬入乙公寓，搜尋客廳及臥室後取走筆記型電腦及錢包內現金後離開。乙下班後發現失竊報案。", "aggravated_theft"),
    ("C093", "甲於白天潛入乙辦公室，打開未上鎖抽屜竊取員工放置之現金及貴重物品後離去。乙發現後報警處理。", "theft"),
    ("C094", "甲持刀進入乙經營之便利商店，以言語及刀械威脅乙交出收銀機內現金，乙因恐懼交付後甲取走現金逃逸。", "robbery"),
    # 計畫主題原為「強盜」，但砸破車窗取走車內財物無對人施暴，依刑法
    # 第 320 條為竊盜；既有 C065 與
    # test_vehicle_window_taking_is_not_promoted_to_robbery_without_person_force
    # 亦已鎖定同一結論。此處更正計畫標籤，非放寬斷言。
    ("C095", "甲於夜間持鐵棒至乙路邊停車處，砸破車窗後強行取走乙置於車內之公事包及現金後加速離去。", "theft"),
    # 計畫主題原為「加重強盜」，但刑法無「加重強盜」此獨立罪名，第 328
    # 條各款為同條法定刑之升級，候選方向仍為強盜。
    ("C096", "甲夥同他人持武器進入乙住家，以暴力及恐嚇方式迫使乙交出財物後離去。乙報案處理。", "robbery"),
    ("C097", "甲透過通訊軟體向乙佯稱可代購限量商品，要求乙先匯款訂金，乙匯款後甲即失聯且未交付任何商品。", "fraud"),
    ("C098", "甲於社群平台刊登虛假投資方案，誘使乙匯款至指定帳戶並承諾高額報酬，乙匯款後甲未返還本金亦無收益。", "fraud"),
    ("C099", "甲以電話向乙謊稱中獎需先繳納稅金，乙依指示匯款後甲失聯，未交付任何獎品。", "fraud"),
    ("C100", "甲因細故與乙發生爭執，徒手毆打乙臉部及身體數下，致乙受有瘀傷、擦傷及疼痛。", "injury"),
    ("C101", "甲與乙因停車糾紛口角，甲以拳頭連續毆打乙胸部及手臂，致乙出現紅腫、瘀青及疼痛。", "injury"),
    ("C102", "甲於公共場所因細故推擠乙跌倒，並以腳踢打乙腿部，致乙受有挫傷及擦傷。", "injury"),
    ("C103", "甲多次以簡訊及電話向乙表示「再出現就讓你後悔」，並於乙住家附近徘徊，使乙心生畏懼而不敢單獨外出。", "intimidation"),
    ("C104", "甲連續數日於乙通勤路線尾隨，並以簡訊寫「別以為躲得掉」，使乙產生恐懼。", "intimidation"),
    ("C105", "甲於乙工作地點附近守候並以言語威脅「小心點」，使乙感到生命身體安全受危害。", "intimidation"),
    # 計畫主題原為「公然侮辱／誹謗」，題庫對應項為妨害名譽
    # （刑法第 304 條併含公然侮辱與誹謗），故預期 id 為 defamation。
    ("C106", "甲於公開場合當眾以言語辱罵乙「騙子、不要臉」，並散布不實訊息指乙侵占款項，經乙提出告訴。", "defamation"),
    ("C107", "甲於網路公開社團貼文指乙「作弊、不守信用」，並散布不實內容稱乙挪用公款，經乙提出告訴。", "defamation"),
    ("C108", "甲於多人聚會場合當面辱罵乙「無恥、下流」，並向在場人士散布乙有不實行為之訊息。", "defamation"),
    ("C109", "甲於員警執行臨檢勤務時，以推拉及言語阻撓，致員警無法完成勤務，經當場制止。", "obstruction"),
    ("C110", "甲於員警執行交通違規取締時，以推擠及大聲叫罵方式阻撓，使員警無法完成開單程序。", "obstruction"),
    ("C111", "甲於員警處理糾紛現場，以肢體推擠及言語干擾，致員警無法順利執行公務。", "obstruction"),
    ("C112", "甲未經乙同意，於夜間以鑰匙開啟乙住宅大門進入屋內，經乙發現後報案。", "residential_trespass"),
    ("C113", "甲於乙外出期間，以自備鑰匙開啟乙住家大門進入，於屋內停留後離開，經乙發現異狀報案。", "residential_trespass"),
    ("C114", "甲自乙住家後窗翻入屋內，未經允許於屋內徘徊後離開，經乙返家發現並報案。", "residential_trespass"),
    ("C115", "甲因與乙有糾紛，持棍棒將乙停放於路邊之機車車體及後照鏡砸毀，造成損壞。", "damage"),
    ("C116", "甲因債務糾紛，持石頭砸毀乙停放於停車場之汽車擋風玻璃及車門，造成明顯損壞。", "damage"),
    ("C117", "甲因細故不滿，以鐵器敲打乙停放之腳踏車車體及輪胎，致車輛無法正常使用。", "damage"),
    ("C118", "甲連續數週於乙通勤路線及住家附近尾隨，並多次寄送未署名信件及禮物，經乙表示拒絕後仍持續，使乙感到不安。", "stalking"),
    ("C119", "甲連續多日於乙住家附近守候，並多次以匿名方式寄送信件及出現在乙工作地點附近，經乙明確表示拒絕後仍持續。", "stalking"),
    ("C120", "甲長期於乙日常活動範圍尾隨並寄送物品，經乙以書面及口頭明確拒絕後仍未停止，使乙產生恐懼。", "stalking"),
]

# 缺事實案例：事實不足時仍保留候選方向，但要件缺口必須留給人工。
INCOMPLETE_CASES = [
    ("C121", "有人進入住家後拿走了東西，屋主回來發現不見了物品。", "theft"),
    ("C122", "甲進入乙的住家後離開，乙發現家中遭人進入。", "residential_trespass"),
    ("C123", "甲趁乙外出時取走乙放在桌上的現金後離開。", "theft"),
]

# 主體不明案例：不得自行補上人物，方向保留且缺口須標示。
UNKNOWN_SUBJECT_CASES = [
    ("C124", "某人於夜間潛入住家後取走財物逃逸，屋主返家發現失竊。", "theft"),
    ("C125", "有人進入他人家中取走財物後離開，屋主發現後報案。", "theft"),
]

# 反向安全案例：該罪名不得出現。附帶的正確方向一併檢查。
REVERSE_CASES = [
    # 誹謗事實中的「騙子」是對被害人的貶抑稱呼，不是詐騙行為。
    ("R01", "甲於公開場合當眾辱罵乙「騙子、不要臉」。", "defamation", {"fraud"}),
    # 「散布不實訊息指乙侵占」中的侵占是被指控的內容，不是行為人的處分。
    ("R02", "甲散布不實訊息指乙侵占公款，致乙名譽受損。", "defamation", {"embezzlement"}),
    # 砸破車窗取走車內財物無對人施暴，不得誤列強盜。
    ("R03", "甲於夜間持鐵棒砸破乙車窗後取走車內公事包及現金後離去。", "theft", {"robbery"}),
    # 否定結果：「乙未受傷」不得成立傷害候選。
    ("R04", "甲與乙發生口角後自行離開，乙未受傷。", None, {"injury"}),
    # 否定行為：「並未毆打乙」不得成立傷害候選。
    ("R05", "甲與乙爭執後離開，並未毆打乙。", None, {"injury"}),
    # 否定窗口不得誤傷未成年人條款：「未成年人遭乙毆打致受傷」仍須成立。
    ("R06", "未成年人遭乙毆打致受傷，乙已受調查。", "injury", set()),
]

# 完整事實案例的允許候選集合：預期方向之外的相鄰競爭假設，須經人工
# 區辨，不得視為誤列；集合外的候選即為誤列。
ALLOWED_EXTRAS = {
    "C091": {"theft"},
    "C092": {"theft"},
    "C093": set(),
    "C094": {"theft", "intimidation"},
    "C095": {"damage"},
    "C096": {"intimidation", "residential_trespass"},
    "C097": set(),
    "C098": set(),
    "C099": set(),
    "C100": set(),
    "C101": set(),
    "C102": set(),
    "C103": set(),
    "C104": set(),
    "C105": set(),
    "C106": set(),
    "C107": set(),
    "C108": set(),
    "C109": set(),
    "C110": set(),
    "C111": set(),
    "C112": set(),
    "C113": set(),
    "C114": set(),
    "C115": set(),
    "C116": set(),
    "C117": set(),
    "C118": set(),
    "C119": set(),
    "C120": set(),
}


def _ids(summary):
    return {item["id"] for item in classify_candidates(summary, BANK)["candidates"]}


def test_c091_c120_complete_case_directions_are_retained():
    for case_id, summary, expected in CASES:
        actual = _ids(summary)
        assert expected in actual, f"{case_id}: expected {expected}, actual={sorted(actual)}"


def test_no_unexpected_extra_candidates():
    """反向檢查：不該出現的候選不得出現。

    既有批次契約只斷言「預期候選有出現」，多餘候選不會讓測試失敗；
    2026-10-22 起每批補上允許集合，使誤列（例如誹謗案誤列詐欺）會被
    測試直接抓到。
    """
    for case_id, summary, expected in CASES:
        actual = _ids(summary)
        extra = actual - {expected} - ALLOWED_EXTRAS[case_id]
        assert not extra, f"{case_id}: unexpected extra candidates {sorted(extra)}"


def test_incomplete_facts_keep_direction_and_leave_element_gaps():
    for case_id, summary, expected in INCOMPLETE_CASES:
        actual = _ids(summary)
        assert expected in actual, f"{case_id}: expected {expected}, actual={sorted(actual)}"


def test_unknown_subject_is_reported_in_missing_elements():
    for case_id, summary, expected in UNKNOWN_SUBJECT_CASES:
        result = classify_candidates(summary, BANK)
        assert result["status"]["subject_identified"] == "false", case_id
        candidate = next(item for item in result["candidates"] if item["id"] == expected)
        assert "主體不明" in candidate["missing"], case_id


def test_reverse_cases_do_not_create_forbidden_candidates():
    for case_id, summary, expected, forbidden in REVERSE_CASES:
        actual = _ids(summary)
        assert not (actual & forbidden), f"{case_id}: forbidden candidates {sorted(actual & forbidden)}"
        if expected is not None:
            assert expected in actual, f"{case_id}: expected {expected}, actual={sorted(actual)}"
