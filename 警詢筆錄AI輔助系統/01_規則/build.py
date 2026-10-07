# -*- coding: utf-8 -*-
"""Build all JSON data files for the system."""
import json, os, re

ROOT = r"D:\工作用\judicial1\警詢筆錄AI輔助系統\01_規則"
os.makedirs(ROOT, exist_ok=True)

# Case code map for template IDs
CASE_CODE = {
    "sexual_image_suspect": "SX-S",
    "sexual_image_victim": "SX-V",
    "sexual_harassment_actor": "SH-A",
    "sexual_harassment_victim": "SH-V",
    "stalking_victim": "ST-V",
    "protection_order_victim": "PO-V",
    "theft_suspect": "TH-S",
    "dui_suspect": "DU-S",
    "fraud_suspect": "FR-S",
    "drug_suspect": "DR-S",
}
ROLE_CODE = {"suspect": "S", "victim": "V", "witness": "W"}

def clean(text):
    """Strip any stray tokens from the source template data."""
    return text.replace("</think>", "").strip()

def Tpls(tid, name, rid, ctid, pairs):
    """pairs = list of (section_label, question_text) tuples."""
    role = ROLE_CODE[rid]
    code = CASE_CODE[ctid]
    qs = []
    for i, (section, text) in enumerate(pairs, 1):
        num = f"{i:03d}"
        qs.append({
            "id": f"{role}-{code}-TPL-{num}",
            "source": "template",
            "source_ref": f"{section}第{i}題",
            "text": clean(text),
            "locked": True,
        })
    return {"template_id": tid, "name": name, "role_id": rid, "case_type_id": ctid, "questions": qs}

# =========== 06-1 性影像嫌疑人 (70 題) ===========
t061 = [
    ("伍一（一）","上述年籍資料是否正確？是否為你本人？是否有刑案紀錄？"),
    ("伍一（一）","上述權利是否知悉？意識是否清楚？可否製作筆錄？"),
    ("伍一（一）","是否有身心智能障礙？有無身心障礙證明？是否具有原住民身分？是否請家屬、律師到場？"),
    ("伍一（二）","現在時間是****，為夜間時段，你是否同意警方製作警詢筆錄？"),
    ("伍一（二）","依據提審法規定，人民被法院以外之機關逮捕、拘禁時，其本人或他人得向逮捕、拘禁地之地方法院聲請提審，你是否要聲請提審？"),
    ("</think>