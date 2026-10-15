from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .section_questions import read_section_questions


CATALOG: tuple[dict[str, Any], ...] = (
    {"id": "state_security", "name": "內亂／外患／妨害國交", "file": "state-security.md", "keywords": ["內亂", "外患", "國交", "敵國", "國防秘密"]},
    {"id": "duty", "name": "瀆職", "file": "duty.md", "keywords": ["瀆職", "受賄", "行賄", "圖利", "枉法"]},
    {"id": "obstruction", "name": "妨害公務", "file": "obstruction.md", "keywords": ["妨害公務", "公務員", "查封", "封印"]},
    {"id": "judicial_integrity", "name": "妨害司法公正", "file": "judicial-integrity.md", "keywords": ["妨害司法", "證人報復", "不法關說", "證言利益", "第172條之1", "第172條之2", "第172條之3", "172-1", "172-2", "172-3"]},
    {"id": "voting", "name": "妨害投票", "file": "voting.md", "keywords": ["投票", "選舉", "賄選", "幽靈人口"]},
    {"id": "disorder", "name": "妨害秩序", "file": "disorder.md", "keywords": ["聚眾", "妨害秩序", "煽惑", "冒充公務員"]},
    {"id": "escape", "name": "脫逃／藏匿人犯", "file": "escape-concealment.md", "keywords": ["脫逃", "藏匿人犯", "頂替", "通緝"]},
    {"id": "evidence", "name": "湮滅證據", "file": "evidence.md", "keywords": ["湮滅證據", "隱匿證據", "偽造證據"]},
    {"id": "accusation", "name": "偽證／誣告", "file": "accusation.md", "keywords": ["偽證", "誣告", "虛偽陳述"]},
    {"id": "currency", "name": "偽造貨幣", "file": "currency.md", "keywords": ["偽鈔", "偽造貨幣", "假鈔"]},
    {"id": "securities", "name": "偽造有價證券", "file": "securities.md", "keywords": ["有價證券", "偽造股票", "偽造票券"]},
    {"id": "weights_measures", "name": "偽造度量衡", "file": "weights-measures.md", "keywords": ["度量衡", "磅秤", "計量"]},
    {"id": "sexual", "name": "妨害性自主", "file": "sexual.md", "keywords": ["性侵害", "強制性交", "強制猥褻", "性自主"]},
    {"id": "obscenity", "name": "妨害風化", "file": "obscenity.md", "keywords": ["妨害風化", "猥褻物", "媒介性交"]},
    {"id": "marriage", "name": "妨害婚姻及家庭", "file": "marriage.md", "keywords": ["重婚", "略誘", "和誘", "婚姻"]},
    {"id": "graves_religion", "name": "褻瀆祀典／侵害墳墓屍體", "file": "graves-religion.md", "keywords": ["墳墓", "屍體", "骨灰", "祀典"]},
    {"id": "agriculture_commerce", "name": "妨害農工商", "file": "agriculture-commerce.md", "keywords": ["農工商", "商品標記", "囤積"]},
    {"id": "opium", "name": "鴉片", "file": "opium.md", "keywords": ["鴉片", "罌粟"]},
    {"id": "gambling", "name": "賭博", "file": "gambling.md", "keywords": ["賭博", "賭場", "下注", "彩票"]},
    {"id": "homicide", "name": "殺人／過失致死", "file": "homicide.md", "keywords": ["殺人", "死亡", "致死", "加工自殺"]},
    {"id": "abortion", "name": "墮胎", "file": "abortion.md", "keywords": ["墮胎", "流產"]},
    {"id": "abandonment", "name": "遺棄", "file": "abandonment.md", "keywords": ["遺棄", "無自救力", "扶養"]},
    {"id": "liberty", "name": "妨害自由", "file": "liberty.md", "keywords": ["拘禁", "妨害自由", "強制", "侵入住宅"]},
    {"id": "privacy", "name": "妨害秘密／性隱私", "file": "privacy.md", "keywords": ["妨害秘密", "竊錄", "竊聽", "性影像", "偷拍", "側錄", "散布私密", "私密影像", "私密照片"]},
    {"id": "robbery", "name": "搶奪／強盜／海盜", "file": "robbery.md", "keywords": ["搶奪", "強盜", "海盜", "不能抗拒"]},
    {"id": "trafficking", "name": "人口販運", "file": "trafficking.md", "keywords": ["人口販運", "剝削", "強迫勞動", "債務約束"]},
    {"id": "juvenile", "name": "少年事件", "file": "juvenile.md", "keywords": ["少年事件", "未滿十八歲", "觸法少年"]},
    {"id": "domestic_violence", "name": "家庭暴力／違反保護令", "file": "domestic-violence.md", "keywords": ["家庭暴力", "家暴", "保護令"]},
    {"id": "child_protection", "name": "兒少保護／性剝削", "file": "child-protection.md", "keywords": ["兒少性剝削", "兒童虐待", "少年性剝削"]},
    {"id": "gender_equality", "name": "職場／校園性別事件", "file": "gender-equality.md", "keywords": ["職場性騷擾", "校園性別", "性平申訴"]},
)


EXISTING_FILES = {
    "theft": "theft.md",
    "aggravated_theft": "theft.md",
    "embezzlement": "embezzlement.md",
    "fraud": "fraud.md",
    "injury": "injury.md",
    "damage": "damage.md",
    "intimidation": "threat.md",
    "defamation": "defamation.md",
    "forgery": "forgery.md",
    "computer": "computer.md",
    "sexual_harassment": "sexual-harassment.md",
    "stalking": "stalking.md",
    # question_bank 的 public_danger 目前只建模刑法 §185-3。廣義公共危險
    # public-danger.md 必須等 legal-route split 完成，不能混接到酒駕 elements。
    "public_danger": "drink-driving.md",
    "drugs": "drugs.md",
}


def merge_markdown_questions(bank: dict[str, Any], root: Path) -> dict[str, Any]:
    merged = deepcopy(bank)
    by_id = {item["id"]: item for item in merged["offenses"]}
    # 載入順序：EXISTING_FILES 明確映射 → offense 自帶 question_file（核實法源新增者）→ CATALOG 其餘
    seen_files: set[str] = set()
    for offense_id, filename in EXISTING_FILES.items():
        path = root / filename
        if path.is_file() and offense_id in by_id:
            by_id[offense_id]["section_questions"] = read_section_questions(path)
            by_id[offense_id]["role_questions"] = flatten_sections(
                by_id[offense_id]["section_questions"]
            )
            by_id[offense_id]["question_source"] = filename
            seen_files.add(offense_id)
    # question_bank.json 內自帶 question_file 的 offense（法源核實新增）也載入 markdown 題
    for offense_id, offense in by_id.items():
        if offense_id in seen_files:
            continue
        filename = offense.get("source", {}).get("question_file") or offense.get("question_file")
        if not filename:
            continue
        path = root / filename
        if path.is_file():
            offense["section_questions"] = read_section_questions(path)
            offense["role_questions"] = flatten_sections(offense["section_questions"])
            offense["question_source"] = filename
    for entry in CATALOG:
        if entry["id"] in by_id:
            continue  # 已在 question_bank.json（含核實法源），不得重複
        path = root / entry["file"]
        if not path.is_file():
            continue
        sections = read_section_questions(path)
        offense = {
            "id": entry["id"],
            "name": entry["name"],
            "keywords": entry["keywords"],
            "related": [],
            "source": {
                "label": f"questions/{entry['file']}；現行法與個案適用仍須人工確認",
                "status": "HUMAN_REVIEW_REQUIRED",
            },
            "elements": [],
            "section_questions": sections,
            "role_questions": flatten_sections(sections),
            "question_source": entry["file"],
        }
        merged["offenses"].append(offense)
    return merged


def flatten_sections(sections: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    """向後相容：把區段結構攤平成舊的 role_questions 形態。"""
    return {
        role: [item for section in sections.get(role, {}).values() for item in section]
        for role in ("victim", "suspect", "transfer")
    }
