"""公司標準筆錄範本：問句逐字保留自三份公司 .doc 範本。

來源檔案（見 data/source_manifest.json）：
- ../通用被害人筆錄.doc（victim）
- ../通用涉嫌人筆錄.doc（suspect）
- ../通用涉嫌人筆錄（移送）.doc（transfer）

規則（questions/company-standard.md）：
- 公司必問題保持原文與原順序，不得改寫、合併或增刪。
- 範本中的示例答案與個資（姓名、身分證、地址等）不匯入本模組。
- 涉嫌人範本中的佔位數字題（「問 0」）為空位，不屬於必問題，予以排除。
- 範本原有罪章專屬題（例如竊盜「你為何要拿取該物品」）改由 questions/*.md
  各罪章檔的中性同義題負責；本模組只保留通用程序題，避免重複詢問。
- 夜間偵訊題原文含「警方不得對你詢問製作筆錄」；依 questions/common.md 第七節，
  保留原文但加註承辦人依刑訴 §100-3 認定是否適用。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# 受詢問人年籍表欄位（三份範本共用）
IDENTITY_FIELDS: tuple[dict[str, str], ...] = (
    {"key": "name", "label": "姓名"},
    {"key": "alias", "label": "別（綽號）號"},
    {"key": "gender", "label": "性別"},
    {"key": "birth_date", "label": "出生年月日"},
    {"key": "birth_place", "label": "出生地"},
    {"key": "occupation", "label": "職業"},
    {"key": "national_id", "label": "身分證統一編號"},
    {"key": "registered_address", "label": "戶籍地址"},
    {"key": "current_address", "label": "現住地址"},
    {"key": "education", "label": "教育程度"},
    {"key": "phone", "label": "電話號碼"},
)
INCOME_LEVELS: tuple[str, ...] = ("貧寒", "勉持", "小康", "中產", "富裕")

# 應告知事項（涉嫌人與移送範本）
NOTICE_SUSPECT: tuple[str, ...] = (
    "一、得保持沉默，無須違背自己之意思而為陳述。",
    "二、得選任辯護人。如為低收入戶、中低收入戶、原住民或其他依法令得請求法律扶助者，得請求之。",
    "三、得請求調查有利之證據。",
)
NOTICE_TRANSFER_EXTRA: str = (
    "四、提審法第1條：人民被法院以外之任何機關逮捕、拘禁時，其本人或他人得向逮捕、"
    "拘禁地之地方法院聲請提審。但其他法律規定得聲請即時由法院審查者，依其規定。"
    "前項聲請及第10條之抗告，免徵費用。"
)

FOOTER_LINES: tuple[str, ...] = (
    "上開筆錄因本所警力事實不足無法由詢問人外進行記錄",
    "並經受詢問人親閱無訛後始簽名捺印",
    "受詢問人：",
    "詢 問 人：",
    "筆 錄 記 錄 人：",
)

# 逐字公司必問題。question 為範本原文；placeholder 標示需代入之資料。
# 來源：通用被害人筆錄.doc（順序照原範本）
VICTIM_COMPANY_QUESTIONS: tuple[str, ...] = (
    "你上述年籍資料是否正確？是否為你本人？有無攜帶身分證明文件?",
    "你今（{today}）日因何事接受警方製作筆錄？",
    "對於特定或不特定人士做不實指控或謊報、隱匿實情，致使公務人員於文書登載不實必須擔負法律責任，是否清楚？",
    "是否知道對方年籍資料、聯絡方式？與對方是否認識？有無仇恨或糾紛？",
    "現場有無裝設監視器或其他人見聞？時間有無誤差？有無聯絡方式？有無佐證資料可提供警方?或有利事證須請警方協助調查?",
    "你是否要提出告訴？提出何種告訴？是否曾向其他警察單位報案（有無開立證明單或未獲受理緣由過程）？是否附帶民事求償？有無與嫌犯和解或調解之意願？",
    "上述所說是否實在？有無其他意見補充？",
)

# 來源：通用涉嫌人筆錄.doc（順序照原範本；「問 0」空位題排除；
# 夜間偵訊題文字照原文保留，但實際夜間判斷依程序檢核）
SUSPECT_COMPANY_QUESTIONS: tuple[str, ...] = (
    "你上述年籍資料是否正確？是否為你本人？有無攜帶身分證明文件?",
    "警方所告知之罪名及權利你是否清楚?你有無刑案紀錄？",
    "你是否具有低收入戶、中低收入戶、原住民或其他依法令得請求法律扶助者的身分？你是否需要通知親屬、法扶或委任律師陪同到場？",
    "現在時間{now_time}許，依刑事訴訟法為夜間偵訊時間，警方不得對你詢問製作筆錄，你是否知悉？（承辦人注意：非夜間詢問時此題不適用；是否屬夜間及法定例外由承辦人依刑事訴訟法第100條之3認定）",
    "你今（{today}）日因何事接受警方製作筆錄？",
    "你是否知悉於警詢筆錄中做不實陳述須負法律責任?",
    "你有無為自己或他人推卸刑責而向警方為不實陳述？",
    "警方製作警詢筆錄時，有無全程錄音錄影？",
    "警方於偵訊時你所陳述之事實是否為你自由意識下所陳述？警方有無以強暴脅迫等不正方法對你取供？",
    "是否知道對方年籍資料、聯絡方式？與對方是否認識？有無仇恨或糾紛？",
    "上述所說是否實在？有無其他意見補充？",
)

# 來源：通用涉嫌人筆錄（移送）.doc（順序照原範本；「問 0」空位題排除）
TRANSFER_COMPANY_QUESTIONS: tuple[str, ...] = (
    "你上述年籍資料是否正確？是否為你本人？有無攜帶身分證明文件?",
    "警方所告知之罪名及權利你是否清楚?你有無刑案紀錄？",
    "你是否具有低收入戶、中低收入戶、原住民或其他依法令得請求法律扶助者的身分？你是否需要通知親屬、法扶或委任律師陪同到場？",
    "依據提審法第1條之規定，人民被法院以外之任何機關逮捕、拘禁時，其本人或他人得向逮捕、拘禁地之地方法院聲請提審。但其他法律規定得聲請及時由法院審查者，依其規定。前項聲請及第10條之抗告，免徵費用，你是否清楚此規定？是否需要聲請提審？",
    "現在時間{now_time}許，依刑事訴訟法為夜間偵訊時間，你是否同意接受製作夜間警詢筆錄？目前精神狀況是否良好？意識是否清醒？（承辦人注意：非夜間詢問時此題不適用；是否屬夜間及法定例外由承辦人依刑事訴訟法第100條之3認定）",
    "你今（{today}）日因何事接受警方製作筆錄？",
    "你是否知悉於警詢筆錄中做不實陳述須負法律責任?",
    "你有無為自己或他人推卸刑責而向警方為不實陳述？",
    "警方製作警詢筆錄時，有無全程錄音錄影？",
    "警方於偵訊時你所陳述之事實是否為你自由意識下所陳述？警方有無以強暴脅迫等不正方法對你取供？警方在逮捕你時，有無使你受傷？",
    "上述所說是否實在？有無其他意見補充？",
)

COMPANY_QUESTIONS: dict[str, tuple[str, ...]] = {
    "victim": VICTIM_COMPANY_QUESTIONS,
    "suspect": SUSPECT_COMPANY_QUESTIONS,
    "transfer": TRANSFER_COMPANY_QUESTIONS,
}

_NOTICE_TEXTS: dict[str, tuple[str, ...]] = {
    "suspect": NOTICE_SUSPECT,
    "transfer": NOTICE_SUSPECT + (NOTICE_TRANSFER_EXTRA,),
}


def company_questions(role: str) -> list[dict[str, Any]]:
    """公司必問題，kind=company，順序與原文照範本。"""
    if role not in COMPANY_QUESTIONS:
        raise ValueError(f"未知身分：{role}")
    questions: list[dict[str, Any]] = []
    for index, text in enumerate(COMPANY_QUESTIONS[role], start=1):
        questions.append({
            "id": f"COMPANY-{role[0].upper()}-{index:02d}",
            "text": text,
            "kind": "company",
            "role": role,
            "priority": 1,
            "status": "PENDING",
            "answer": "",
        })
    return questions


def render_company_text(template: str, **values: str) -> str:
    return template.format(**values)


def notice_lines(role: str, offense_name: str) -> list[str]:
    header = f"你涉嫌　{offense_name}　案，於受詢問時，得行使下列權利："
    return [header, *_NOTICE_TEXTS[role]]


def template_meta() -> dict[str, Any]:
    return {
        "template_version": "company-verbatim-2026-10-11",
        "sources": [
            "通用被害人筆錄.doc",
            "通用涉嫌人筆錄.doc",
            "通用涉嫌人筆錄（移送）.doc",
        ],
        "placeholder_questions_removed": 6,
        "pii_scrubbed": True,
    }


def identity_defaults() -> dict[str, str]:
    return {field["key"]: "" for field in IDENTITY_FIELDS}


def copy_identity(values: dict[str, Any]) -> dict[str, str]:
    return {field["key"]: str(values.get(field["key"], "") or "") for field in IDENTITY_FIELDS}


def merged_identity_copy() -> dict[str, str]:
    """深層複製，避免呼叫端誤改常數。"""
    return deepcopy(identity_defaults())
