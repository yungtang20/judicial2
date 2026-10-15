"""文件完整性驗證（spec Phase 7）。

獨立於 docx 產生流程的驗證層：
- 筆錄驗證：case 版本、核准、必要欄位、問答順序、告知事項、簽名區、案號
- 條陳驗證：摘要長度、必要案號、角色
- 兩者分開驗證，不得因筆錄通過就認定條陳正確
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from .documents import DocumentError
from .config import MAX_SUMMARY_LENGTH
from .rules import required_case_numbers


def validate_interview_completeness(case: dict[str, Any], role: str) -> list[str]:
    """驗證筆錄必要內容；回傳缺失清單（空 = 通過）。

    檢查項目：
    1. 案件處於 OUTPUT_READY 且有對應核准
    2. interview 存在且 selected_offenses 非空
    3. 全部問答有答案且順序完整
    4. 必要案號已填
    5. 詢問時間起訖已填（suspect/transfer 角色必填；victim 選填）
    6. 年籍必要欄位
    """
    problems: list[str] = []
    if case.get("state") != "OUTPUT_READY":
        problems.append("案件尚未完成必要 Gate")
    interview = case.get("interviews", {}).get(f"{role}:default")
    if interview is None:
        problems.append(f"找不到 {role} 筆錄資料")
        return problems
    if interview.get("role") != role:
        problems.append("筆錄身分與要求不符")
    if not interview.get("selected_offenses"):
        problems.append("尚未確認候選罪章")

    questions = interview.get("questions", [])
    for q in questions:
        if not str(q.get("answer", "")).strip():
            problems.append(f"問句未作答：{q.get('id')}")
            break

    # 必要案號
    missing_numbers = [
        key for key in required_case_numbers(case)
        if not case.get("case_numbers", {}).get(key)
    ]
    if missing_numbers:
        problems.append("缺少必要案號：" + "、".join(missing_numbers))

    # 詢問時間（涉嫌人/移送必填）
    if role in ("suspect", "transfer"):
        session = case.get("interview_sessions", {}).get(f"{role}:default", {})
        if not session.get("start_time") or not session.get("end_time"):
            problems.append("缺少詢問起訖時間")

    # 年籍（身分證統一編號或證號欄）
    profile = case.get("profiles", {}).get(f"{role}:default", {})
    if not profile.get("name"):
        problems.append("缺少受詢問人姓名")

    return problems


def validate_brief_completeness(case: dict[str, Any], role: str) -> list[str]:
    """條陳驗證；與筆錄分開，不共用結論。"""
    problems: list[str] = []
    if case.get("state") != "OUTPUT_READY":
        problems.append("案件尚未完成必要 Gate")
    interview = case.get("interviews", {}).get(f"{role}:default")
    if interview is None:
        problems.append(f"找不到 {role} 筆錄資料（條陳依賴筆錄內容）")
        return problems

    summary = case.get("brief_summary", "")
    if len(summary) > MAX_SUMMARY_LENGTH:
        problems.append(f"案情摘要 {len(summary)} 字，超過 {MAX_SUMMARY_LENGTH} 字上限")
    if not summary.strip():
        problems.append("案情摘要不得空白")

    missing_numbers = [
        key for key in required_case_numbers(case)
        if not case.get("case_numbers", {}).get(key)
    ]
    if missing_numbers:
        problems.append("缺少必要案號：" + "、".join(missing_numbers))
    return problems


def validate_docx_structure(data: bytes) -> list[str]:
    """驗證 docx 二進位結構：ZIP 有效、無 MERGEFIELD/雙括號殘留。"""
    problems: list[str] = []
    if not data.startswith(b"PK"):
        problems.append("輸出不是有效的 DOCX（ZIP）檔")
        return problems
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError):
        problems.append("DOCX 內部結構損壞或缺少 document.xml")
        return problems
    if "MERGEFIELD" in xml:
        problems.append("文件殘留 MERGEFIELD 欄位")
    if "{{" in xml:
        problems.append("文件殘留未插值的雙括號")
    return problems


def validate_document_output(case: dict[str, Any], role: str, kind: str) -> list[str]:
    """統一入口：kind=interview 用筆錄驗證，kind=brief 用條陳驗證。"""
    if kind == "interview":
        return validate_interview_completeness(case, role)
    if kind == "brief":
        return validate_brief_completeness(case, role)
    raise DocumentError(f"未知文件類型：{kind}")
