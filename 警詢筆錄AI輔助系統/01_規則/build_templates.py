# -*- coding: utf-8 -*-
"""Main builder: reads data_*.json files, produces final questions_templates.json."""
import json, os, sys

ROOT = r"D:\工作用\judicial1\警詢筆錄AI輔助系統\01_規則"

# case code mapping for template IDs
CASE_CODE = {
    "sexual_image_suspect": "SX-S", "sexual_image_victim": "SX-V",
    "sexual_harassment_actor": "SH-A", "sexual_harassment_victim": "SH-V",
    "stalking_victim": "ST-V", "protection_order_victim": "PO-V",
    "theft_suspect": "TH-S", "dui_suspect": "DU-S",
    "fraud_suspect": "FR-S", "drug_suspect": "DR-S",
}
ROLE_CODE = {"suspect":"S","victim":"V","witness":"W"}

def build_templates():
    templates = []
    for fname, meta in [
        ("t061_data.json", ("06-1","性影像嫌疑人筆錄例稿","suspect","sexual_image_suspect")),
        ("t062_data.json", ("06-2","性影像被害人筆錄例稿","victim","sexual_image_victim")),
        ("t063_data.json", ("06-3","性騷擾行為人詢問紀錄例稿","suspect","sexual_harassment_actor")),
        ("t064_data.json", ("06-4","性騷擾被害人詢問紀錄例稿","victim","sexual_harassment_victim")),
        ("t065_data.json", ("06-5","跟蹤騷擾罪被害人警詢筆錄例稿","victim","stalking_victim")),
        ("t066_data.json", ("06-6","違反保護令罪警詢筆錄例稿","victim","protection_order_victim")),
        ("t067_data.json", ("06-7","竊盜嫌疑人筆錄例稿","suspect","theft_suspect")),
        ("t068_data.json", ("06-8","酒駕嫌疑人筆錄例稿","suspect","dui_suspect")),
        ("t069_data.json", ("06-9","詐欺嫌疑人筆錄例稿","suspect","fraud_suspect")),
        ("t010_data.json", ("06-10","毒品嫌疑人筆錄例稿","suspect","drug_suspect")),
    ]:
        path = os.path.join(ROOT, fname)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        tid, name, rid, ctid = meta
        role = ROLE_CODE[rid]
        code = CASE_CODE[ctid]
        qs = []
        for i, entry in enumerate(raw, 1):
            section, text = entry[0], entry[1]
            qs.append({
                "id": f"{role}-{code}-TPL-{i:03d}",
                "source": "template",
                "source_ref": f"{section}第{i}題",
                "text": text,
                "locked": True,
            })
        templates.append({"template_id": tid, "name": name, "role_id": rid, "case_type_id": ctid, "questions": qs})
        print(f"  {tid}: {len(qs)} questions")
    out = {"version": "1.0", "templates": templates}
    dst = os.path.join(ROOT, "questions_templates.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {dst} ({os.path.getsize(dst)} bytes)")

if __name__ == "__main__":
    build_templates()
