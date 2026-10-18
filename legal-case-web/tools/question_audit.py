"""問句品質稽核工具：對一組案件規格，逐案逐角色收集已出題問句並列出品質缺陷。

用法：
    py -3 tools/question_audit.py --spec tools/question_audit_spec.json --json out.json --md out.md

設計原則：
- 只呼叫本機 API（預設 http://127.0.0.1:8787），不連外。
- 路線覆蓋率的權威判定來自 app 自己回報的 `question_coverage_by_route`（以 concept id 計），
  本工具只轉錄，不自行計算覆蓋與否；`fact_element_text_hits` 的字串比對僅為診斷。
- 判定規則全部機械化（見 question_audit_spec.json 與 README 的 unresolved_placeholder 說明），
  不解讀案情、不作法律判斷。
- 報告不含時間戳、UUID、revision 等易變欄位，因此同一份輸入必須產生位元組相同的報告；
  「跑兩次比對 JSON」即為這支工具的穩定性量測手段。
- 唯一外部相依是本庫自己的 app.question_hygiene.normalize（去重鍵的權威定義）與
  app.xlsm_questions 的罪章欄名對照（扣留紀錄不帶 offense_id，需由來源格反查）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import OrderedDict

DEFAULT_BASE_URL = "http://127.0.0.1:8787"

# 覆蓋率判定的來源鍵名，原樣寫進報告，讓讀者看得出判定從哪裡來。
COVERAGE_SOURCE = "question_coverage_by_route"

# ---------------------------------------------------------------- 判定規則 --

# 一個括號（全形或半形）包裹的內容，用於檢查是否為未填欄位。
_PAREN_RUN = re.compile(r"[（(]([^（）()]{0,40})[）)]")
# 括號內容含阿拉伯數字才算「未填的數字欄位」。
_DIGIT = re.compile(r"[0-9]")
# 只含空白的括號欄位是合法的，例如「你今（　）日因何事接受警方製作筆錄？」。
_BLANK_ONLY = re.compile(r"[\s\u3000]*")
# 題目自帶的法條／程序註記，例如「（§5，僅詢問事實）」「（第320條第1項）」。
# 這些是題庫核定的法源標註，不是未填欄位，不得計入缺陷。
_LEGAL_ARTICLE = re.compile(r"第\s*\d+\s*條")
_LEGAL_SECTION = "§"
# 代號樣式占位符，例如「〈代號〉」。
_CODE_SLOT = re.compile(r"〈[^〉]{0,20}〉")
# 「已填值」的判定：阿拉伯數字或英文字母。允許以連接號、波浪號、空白銜接。
_SEP = r"\-~\u2013\u2014\uFF5E\u0020\u3000\t"
_CODE_SLOT_ADJACENT = re.compile(
    "(?:[0-9A-Za-z]|[%s]*[0-9A-Za-z])[%s]*〈[^〉]{0,20}〉|〈[^〉]{0,20}〉[%s]*(?:[0-9A-Za-z]|[%s]*[0-9A-Za-z])"
    % (_SEP, _SEP, _SEP, _SEP)
)


def unresolved_placeholder_hits(text: str) -> tuple[list[str], int]:
    """回傳（該題命中的「未填占位符」樣式名稱清單, 略過的法條註記數）。

    依 brief 的機械定義：
    (a) paren_with_digit：括號內含數字（不是只有空白），且非法條／程序註記；
    (b) code_slot_adjacent_filled_value：〈…〉緊鄰已填值。
    只有空白的括號欄位（如「（　）」）合法，不列入。
    括號內含「§」或「第 N 條」者是題目自帶的法源註記
    （如「（§17 I，須依程序進行，並告知權益）」），不是未填欄位；
    略過並計數回報，讓排除看得見，而不是讓命中憑空消失。
    """
    hits: list[str] = []
    skipped = 0
    for match in _PAREN_RUN.finditer(text):
        inner = match.group(1)
        if not (_DIGIT.search(inner) and not _BLANK_ONLY.fullmatch(inner)):
            continue
        if _LEGAL_SECTION in inner or _LEGAL_ARTICLE.search(inner):
            skipped += 1
            continue
        hits.append("paren_with_digit")
        break
    if _CODE_SLOT_ADJACENT.search(text):
        hits.append("code_slot_adjacent_filled_value")
    return hits, skipped


# ------------------------------------------------------------ HTTP 傳輸層 --


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__("HTTP %s: %s" % (status, body))
        self.status = status
        self.body = body


class Api:
    def __init__(self, base_url: str, timeout: float = 240.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = ""

    def _request(self, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path, data=data, method="POST" if data else "GET"
        )
        if data:
            request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("X-Session-Token", self.token)
        request.add_header("Origin", self.base_url)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiError(exc.code, exc.read().decode("utf-8", "replace")) from exc

    def wait_until_ready(self, attempts: int = 120) -> None:
        last: Exception | None = None
        for _ in range(attempts):
            try:
                self._request("/api/health")
                return
            except Exception as exc:  # noqa: BLE001 - 只做重試
                last = exc
                time.sleep(0.25)
        raise RuntimeError("本機 API 未就緒：%s" % last)

    def fetch_token(self) -> str:
        html = urllib.request.urlopen(self.base_url + "/", timeout=20).read().decode("utf-8")
        match = re.search(r'name="session-token" content="([^"]+)"', html)
        if not match:
            raise RuntimeError("首頁找不到 session-token")
        self.token = match.group(1)
        return self.token

    def health(self) -> dict:
        return self._request("/api/health")

    def create_case(self, spec_case: dict) -> dict:
        return self._request("/api/cases", {
            "summary": spec_case["summary"],
            "has_victim": bool(spec_case.get("has_victim", True)),
            "station": spec_case.get("station") or "○○所",
            "officer": spec_case.get("officer") or "○○○",
        })

    def get_case(self, case_id: str) -> dict:
        return self._request("/api/cases/%s" % case_id)

    def act(self, case_id: str, revision: int, action: str, payload: dict) -> dict:
        return self._request("/api/cases/%s/actions" % case_id, {
            "revision": revision, "action": action, "payload": payload,
        })


# -------------------------------------------------------------- 抽取層 ----


def question_record(question: dict, role: str) -> dict:
    """只取穩定、可供人工判讀的欄位（不含 answer/status 等作答狀態）。"""
    source = question.get("source")
    if isinstance(source, dict):
        source_label = source.get("label")
        source_status = source.get("status")
    else:
        source_label = source
        source_status = None
    return OrderedDict((
        ("id", question.get("id")),
        ("role", role),
        ("offense_id", question.get("offense_id")),
        ("source_label", source_label),
        ("source_status", source_status),
        ("kind", question.get("kind")),
        ("text", question.get("text") or ""),
    ))


def group_by_rule(records: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record.get("rule_id") or "(none)", []).append(OrderedDict((
            ("text", record.get("text")),
            ("role", record.get("role")),
            ("source_cell", record.get("source_cell")),
            ("decision", record.get("decision")),
            ("reason", record.get("reason")),
        )))
    return {key: grouped[key] for key in sorted(grouped)}


def duplicate_groups(served: list[dict]) -> list[list[str]]:
    seen: dict[str, list[str]] = {}
    order: list[str] = []
    for record in served:
        key = normalize(record["text"])
        if key not in seen:
            seen[key] = []
            order.append(key)
        seen[key].append(record["id"])
    return [seen[key] for key in order if len(seen[key]) > 1]


def load_crosswalk(repo_root: str) -> tuple[str, dict[str, list[str]]]:
    path = os.path.join(repo_root, "data", "legal_route_crosswalk.json")
    with open(path, encoding="utf-8") as handle:
        crosswalk = json.load(handle)
    elements: dict[str, list[str]] = {}
    for route in crosswalk.get("routes", []):
        for child in route.get("child_routes", []):
            elements[child["id"]] = list(child.get("fact_elements") or [])
    return str(crosswalk.get("schema_version", "")), elements


def load_quarantine_offense_ids(repo_root: str) -> dict[tuple[str, int, str], str]:
    """(角色, 列, 欄) → 罪章 id，供反查扣留紀錄所屬罪章。

    `case["question_quarantine"]` 的紀錄由 app.xlsm_questions._quarantine_record 產生，
    欄位只有 text/role/source_cell/rule_id/decision/reason，沒有 offense_id；因此用來源格
    對回原始 `data/xlsm_questions.json` 的罪章欄名，再套用 app 自己的欄名對照。
    對照不到的欄名一律略過，與載入器（欄名不在對照表即不產生題目）的行為一致。
    """
    from app.xlsm_questions import OFFENSE_NAME_TO_ID, SHEET_ROLE_ALIASES  # noqa: PLC0415

    path = os.path.join(repo_root, "data", "xlsm_questions.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    index: dict[tuple[str, int, str], str] = {}
    for role, items in raw.items():
        for item in items:
            offense_name = str(item.get("offense", "")).strip()
            if offense_name in SHEET_ROLE_ALIASES:
                continue
            offense_id = OFFENSE_NAME_TO_ID.get(offense_name)
            if offense_id is None:
                continue
            index[(role, item.get("row", 0), item.get("col", ""))] = offense_id
    return index


def quarantine_scopes(quarantine: list[dict], role: str, selected_offenses: set[str],
                      offense_index: dict[tuple[str, int, str], str]) -> tuple[int, int]:
    """回傳（與本次訪談相關的扣留數, 其餘扣留數）。

    question_quarantine 是整庫範圍，單一案件會帶回其他罪章的紀錄；
    「相關」的定義是角色相同且罪章屬於本案已選罪章，其餘都是雜訊。
    """
    applicable = 0
    other = 0
    for record in quarantine:
        if record.get("role") != role:
            other += 1
            continue
        offense_id = record.get("offense_id")
        if not offense_id:
            cell = record.get("source_cell") or {}
            offense_id = offense_index.get(
                (record.get("role"), cell.get("row"), cell.get("col")))
        if offense_id in selected_offenses:
            applicable += 1
        else:
            other += 1
    return applicable, other


def route_coverage(route_ids: list[str], coverage: dict | None,
                   served_route_contexts: list[list[str]],
                   unknown: list[str]) -> list[dict]:
    """轉錄 app 自己的路線覆蓋判定（`question_coverage_by_route`），不自行判定。

    coverage 為該案最後一次 set_offenses 回應的 `question_coverage_by_route`。
    app 沒有回傳該路線的覆蓋物件時，materialization_status 記 null 並列入
    unknown_route_ids，而不是自行推論一個覆蓋結果。
    """
    routes = {}
    if isinstance(coverage, dict) and isinstance(coverage.get("routes"), dict):
        routes = coverage["routes"]
    rows = []
    for route_id in route_ids:
        entry = routes.get(route_id)
        served_with_context = sum(
            1 for context_ids in served_route_contexts if route_id in context_ids)
        if not isinstance(entry, dict):
            unknown.append(route_id)
            rows.append(OrderedDict((
                ("route_id", route_id),
                ("materialization_status", None),
                ("missing_concept_ids", None),
                ("pruned_concept_ids", None),
                ("served_questions_with_route_context", served_with_context),
                ("coverage_source", COVERAGE_SOURCE),
            )))
            continue
        rows.append(OrderedDict((
            ("route_id", route_id),
            ("materialization_status", entry.get("materialization_status")),
            ("missing_concept_ids", entry.get("missing_concept_ids")),
            ("pruned_concept_ids", entry.get("pruned_concept_ids")),
            ("served_questions_with_route_context", served_with_context),
            ("coverage_source", COVERAGE_SOURCE),
        )))
    return rows


def fact_element_text_hits(route_ids: list[str], elements_by_route: dict[str, list[str]],
                           served: list[dict], meta_blobs: dict[str, str],
                           unknown: list[str]) -> list[dict]:
    """（診斷）每條已選路線的 fact_elements 在問句 text 或 meta 內是否有字串命中。

    這不是覆蓋率判定：覆蓋率由 app 的 concept id 模型判定（見 route_coverage）。
    served 為報告用的精簡紀錄（不含 meta），meta_blobs 以 question id 對應 meta 的 JSON
    文字，因此「有沒有問句引用到這個事實元素」仍是對原始 meta 判定，而非對精簡紀錄判定。
    """
    rows = []
    for route_id in route_ids:
        elements = elements_by_route.get(route_id)
        if elements is None:
            unknown.append(route_id)
            continue
        matched: dict[str, list[str]] = {}
        missing: list[str] = []
        for element in elements:
            hits = []
            for record in served:
                if not element:
                    continue
                if element in record["text"]:
                    hits.append(record["id"] + ":text")
                elif element in meta_blobs.get(record["id"], ""):
                    hits.append(record["id"] + ":meta")
            if hits:
                matched[element] = hits
            else:
                missing.append(element)
        rows.append(OrderedDict((
            ("route_id", route_id),
            ("fact_elements", elements),
            ("matched", {key: matched[key] for key in sorted(matched)}),
            ("missing", missing),
        )))
    return rows


# ---------------------------------------------------------------- 主流程 --


def audit_case(api: Api, spec_case: dict, crosswalk: dict[str, list[str]],
               offense_index: dict[tuple[str, int, str], str]) -> dict:
    label = spec_case["label"]
    case = api.create_case(spec_case)
    case_id = case["case_id"]
    default_role = case.get("question_role")

    declared_route_ids = spec_case.get("route_ids")
    forced_route_ids = list(declared_route_ids) if declared_route_ids else []

    result: dict = OrderedDict((
        ("label", label),
        ("has_victim", bool(spec_case.get("has_victim", True))),
        ("default_role", default_role),
        ("prepare", "OK"),
        ("prepare_error", None),
        ("route_mode", "forced" if forced_route_ids else "auto"),
        ("spec_route_ids", None if declared_route_ids is None else list(declared_route_ids)),
        ("selected_offenses", []),
        ("selected_legal_routes", []),
        ("route_selection_status", None),
        ("coverage_role", None),
        ("roles", []),
        ("route_coverage", []),
        ("fact_element_text_hits", []),
        ("unknown_route_ids", []),
    ))

    try:
        case = api.act(case_id, case["revision"], "auto_prepare", {})
    except ApiError as exc:
        result["prepare"] = "FAILED"
        result["prepare_error"] = exc.body
        return result

    result["selected_offenses"] = list(case.get("selected_offenses") or [])
    result["route_selection_status"] = case.get("route_selection_status")
    result["selected_legal_routes"] = [route.get("route_id")
                                       for route in (case.get("selected_legal_routes") or [])]

    requested = list(spec_case.get("roles") or [])
    result["default_role_in_requested"] = default_role in requested
    if default_role and not result["default_role_in_requested"]:
        # 預設角色不在 brief 指定清單時，另外記錄，不與指定角色混算（避免污染表格計數）。
        requested = requested + [default_role]

    served_all: list[dict] = []
    served_route_contexts: list[list[str]] = []
    meta_blobs: dict[str, str] = {}
    coverage_payload: dict | None = None
    last_case: dict | None = None
    for role in requested:
        role_row: dict = OrderedDict((
            ("role", role),
            ("set_offenses_error", None),
            ("served", OrderedDict((("count", 0), ("questions", [])))),
            ("quarantined", OrderedDict((("count", 0), ("applicable_count", 0),
                                         ("other_offense_count", 0), ("by_rule", {})))),
            ("no_source", OrderedDict((("count", 0), ("questions", [])))),
            ("unresolved_placeholder", OrderedDict((("count", 0),
                                                   ("legal_annotation_skipped", 0),
                                                   ("questions", [])))),
            ("duplicate_normalized", OrderedDict((("count", 0), ("groups", [])))),
        ))
        try:
            current = api.get_case(case_id)
            route_ids_for_call = forced_route_ids or [
                route.get("route_id")
                for route in (current.get("selected_legal_routes") or [])
            ]
            case = api.act(case_id, current["revision"], "set_offenses", {
                "offense_ids": current.get("selected_offenses"),
                "legal_route_ids": route_ids_for_call,
                "route_review_confirmed": True,
                "role": role,
            })
        except ApiError as exc:
            role_row["set_offenses_error"] = exc.body
            result["roles"].append(role_row)
            continue

        last_case = case
        coverage_payload = case.get("question_coverage_by_route")
        result["coverage_role"] = role

        questions = case.get("questions") or []
        served = [question_record(question, role) for question in questions]
        served_all.extend(served)
        for record, question in zip(served, questions):
            meta = question.get("meta") or {}
            meta_blobs[record["id"]] = json.dumps(meta, ensure_ascii=False)
            context_ids = meta.get("route_context_ids")
            served_route_contexts.append(
                [item for item in context_ids if isinstance(item, str)]
                if isinstance(context_ids, list) else [])

        role_row["served"]["count"] = len(served)
        role_row["served"]["questions"] = served

        quarantine = case.get("question_quarantine") or []
        applicable, other = quarantine_scopes(
            quarantine, role, set(result["selected_offenses"]), offense_index)
        role_row["quarantined"] = OrderedDict((
            ("count", len(quarantine)),
            ("applicable_count", applicable),
            ("other_offense_count", other),
            ("by_rule", group_by_rule(quarantine)),
        ))

        no_source = [record for record, question in zip(served, questions)
                     if not question.get("source")]
        role_row["no_source"]["count"] = len(no_source)
        role_row["no_source"]["questions"] = [record["id"] for record in no_source]

        placeholders = []
        legal_annotation_skipped = 0
        for record in served:
            hits, skipped = unresolved_placeholder_hits(record["text"])
            legal_annotation_skipped += skipped
            if hits:
                placeholders.append(OrderedDict((("id", record["id"]), ("hits", hits),
                                                 ("text", record["text"]))))
        role_row["unresolved_placeholder"]["count"] = len(placeholders)
        role_row["unresolved_placeholder"]["legal_annotation_skipped"] = legal_annotation_skipped
        role_row["unresolved_placeholder"]["questions"] = placeholders

        groups = duplicate_groups(served)
        role_row["duplicate_normalized"]["count"] = sum(len(group) for group in groups)
        role_row["duplicate_normalized"]["groups"] = groups

        result["roles"].append(role_row)

    if last_case is not None:
        result["selected_legal_routes"] = [route.get("route_id")
                                           for route in (last_case.get("selected_legal_routes") or [])]
        if last_case.get("route_selection_status"):
            result["route_selection_status"] = last_case["route_selection_status"]

    applied_route_ids = result["selected_legal_routes"] or forced_route_ids
    result["route_coverage"] = route_coverage(
        applied_route_ids, coverage_payload, served_route_contexts,
        result["unknown_route_ids"])
    result["fact_element_text_hits"] = fact_element_text_hits(
        applied_route_ids, crosswalk, served_all, meta_blobs,
        result["unknown_route_ids"])
    return result


def summarize(case_row: dict) -> dict:
    totals = OrderedDict((("served", 0), ("quarantined", 0), ("quarantine_applicable", 0),
                          ("no_source", 0), ("unresolved_placeholder", 0),
                          ("legal_annotation_skipped", 0), ("duplicate_normalized", 0)))
    for role_row in case_row["roles"]:
        totals["served"] += role_row["served"]["count"]
        totals["quarantined"] += role_row["quarantined"]["count"]
        totals["quarantine_applicable"] += role_row["quarantined"]["applicable_count"]
        totals["no_source"] += role_row["no_source"]["count"]
        totals["unresolved_placeholder"] += role_row["unresolved_placeholder"]["count"]
        totals["legal_annotation_skipped"] += role_row["unresolved_placeholder"]["legal_annotation_skipped"]
        totals["duplicate_normalized"] += role_row["duplicate_normalized"]["count"]
    return totals


def _route_coverage_finding(cases: list[dict]) -> str | None:
    """(a) 逐條列出 app 自己的覆蓋判定，並點名任何不是 COMPLETE 的路線。"""
    rows = [(case["label"], row) for case in cases for row in case["route_coverage"]]
    if not rows:
        return None
    complete = [(label, row["route_id"]) for label, row in rows
                if row["materialization_status"] == "COMPLETE"]
    others = [(label, row) for label, row in rows
              if row["materialization_status"] != "COMPLETE"]
    if not others:
        return ("app 自身的路線覆蓋率判定（`question_coverage_by_route`）：本次 %d 條已選路線全部為 "
                "COMPLETE（%s）。" % (len(rows), "、".join("%s/%s" % item for item in complete)))
    return (
        "app 自身的路線覆蓋率判定（`question_coverage_by_route`）有 %d/%d 條已選路線不是 COMPLETE：%s。"
        "其中 NOT_APPLICABLE 代表該子路線沒有逐要件的核准題組（本次只有 `theft_320_1_movable` 有），"
        "materialization_status=null 代表 app 未回傳該路線的覆蓋物件（已列入 `unknown_route_ids`）；"
        "兩者都不是問句缺陷，但是路線覆蓋的如實狀態。COMPLETE：%s。"
        % (len(others), len(rows),
           "、".join("%s/%s=%s" % (label, row["route_id"], row["materialization_status"])
                     for label, row in others),
           "、".join("%s/%s" % item for item in complete) or "無"))


def _fact_element_diagnostic_finding(cases: list[dict]) -> str | None:
    """(b) 事實元素字串在出題層的命中狀況，明示為診斷而非覆蓋率判定。"""
    rows = [(case["label"], row) for case in cases for row in case["fact_element_text_hits"]]
    if not rows:
        return None
    total_elements = sum(len(row["fact_elements"]) for _, row in rows)
    matched_elements = sum(len(row["matched"]) for _, row in rows)
    full = [(label, row["route_id"]) for label, row in rows
            if row["fact_elements"] and not row["matched"]]
    return (
        "（診斷，非缺陷）已選路線的 `fact_elements` 字串在出題 text 與 meta 內比對，"
        "命中 %d/%d 個元素；%d 條路線完全未命中（%s）。"
        "路線覆蓋率由 concept id 判定（見各案 `route_coverage`），不走事實元素字串，"
        "因此文字未命中是可預期的，本身不是覆蓋缺口。"
        % (matched_elements, total_elements, len(full),
           "、".join("%s/%s" % item for item in full) or "無"))


def build_findings(cases: list[dict]) -> list[str]:
    """把掃描中確定可複現的異常寫成 findings，供報告第五節引用。"""
    findings: list[str] = []
    failed = [case["label"] for case in cases if case["prepare"] != "OK"]
    if failed:
        findings.append(
            "auto_prepare 無法產生候選罪章，整案完全無法出題（%d/%d 案）：%s。"
            "API 只回傳通用化的「操作未完成，請確認輸入內容或稍後再試」，"
            "真正原因「目前摘要不足以產生候選罪章」被 server._safe_error_message 遮蔽。"
            % (len(failed), len(cases), "、".join(failed)))
    paren = [(case["label"], role_row["role"], hit["id"])
             for case in cases for role_row in case["roles"]
             for hit in role_row["unresolved_placeholder"]["questions"]
             if "paren_with_digit" in hit["hits"]]
    skipped = sum(role_row["unresolved_placeholder"]["legal_annotation_skipped"]
                  for case in cases for role_row in case["roles"])
    if paren or skipped:
        findings.append(
            "未填占位符的括號規則（括號內含數字、非法條註記）命中 %d 題，需人工複核（%s）；"
            "另有 %d 個括號是題目自帶的法條／程序註記（如「（§17 I，須依程序進行，並告知權益）」），"
            "已排除於計數之外，逐案記於 `legal_annotation_skipped`，不再當成未填欄位。"
            % (len(paren), "、".join("%s/%s/%s" % row for row in paren) or "無", skipped))
    slots = [hit["id"] for case in cases for role_row in case["roles"]
             for hit in role_row["unresolved_placeholder"]["questions"]
             if "code_slot_adjacent_filled_value" in hit["hits"]]
    if slots:
        findings.append("〈代號〉緊鄰已填值（真正的未填占位符）：%s。" % "、".join(slots))
    nosource = ["%s/%s" % (case["label"], role_row["role"]) for case in cases
                for role_row in case["roles"] if role_row["no_source"]["count"]]
    if nosource:
        findings.append("有題目缺 source：%s。" % "、".join(nosource))
    no_route = [case["label"] for case in cases
                if case["prepare"] == "OK" and not case["selected_legal_routes"]]
    if no_route:
        findings.append(
            "已產生候選罪章但一條法規路線都沒選到（route_coverage 與 fact_element_text_hits "
            "因此無從計算）：%s。" % "、".join(no_route))
    coverage_finding = _route_coverage_finding(cases)
    if coverage_finding:
        findings.append(coverage_finding)
    diagnostic_finding = _fact_element_diagnostic_finding(cases)
    if diagnostic_finding:
        findings.append(diagnostic_finding)
    return findings


# ----------------------------------------------------------------- 輸出 ----


def _invocation_command(report: dict) -> str:
    """實際執行的那一行指令。報告必須說得出自己是怎麼被跑出來的。"""
    invocation = report.get("invocation") or {}
    command = "py -3 tools/question_audit.py --spec %s --base-url %s" % (
        invocation.get("spec") or report["spec"], report["base_url"])
    if invocation.get("json_out"):
        command += " --json %s" % invocation["json_out"]
    if invocation.get("md_out"):
        command += " --md %s" % invocation["md_out"]
    return command


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# 問句品質稽核報告")
    lines.append("")
    lines.append("- 產生方式：`%s`" % _invocation_command(report))
    lines.append("- 規格檔：`%s`" % report["spec"])
    lines.append("- 法規路線對照表版本：`%s`" % report["crosswalk_version"])
    lines.append("- 服務模式：`%s`（external_ai=%s）" % (report["health"].get("mode"),
                                                        report["health"].get("external_ai")))
    lines.append("")
    lines.append("## 1. 穩定性量測")
    lines.append("")
    lines.append(report["determinism"]["result"])
    lines.append("")
    lines.append("## 2. 逐案計數")
    lines.append("")
    lines.append("非零缺陷以 **粗體** 標示；括號內為角色別細目。")
    lines.append("")
    lines.append("| 案件 | 罪章 | 已選路線 | 路線模式 | 準備 | 出題 | 扣留 | no_source | 未填占位符 | 重複 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for case_row in report["cases"]:
        totals = case_row["totals"]
        mark = lambda n: ("**%d**" % n) if n else "0"
        routes = ", ".join(case_row["selected_legal_routes"]) or "—"
        if case_row["spec_route_ids"] is not None:
            routes = "%s（規格宣告：%s）" % (
                routes, ", ".join(case_row["spec_route_ids"]) or "無")
        lines.append("| %s | %s | %s | %s | %s | %d | %s | %s | %s | %s |" % (
            case_row["label"],
            ", ".join(case_row["selected_offenses"]) or "—",
            routes,
            "強制" if case_row["route_mode"] == "forced" else "自動",
            case_row["prepare"],
            totals["served"],
            mark(totals["quarantined"]),
            mark(totals["no_source"]),
            mark(totals["unresolved_placeholder"]),
            mark(totals["duplicate_normalized"]),
        ))
    lines.append("")
    lines.append("角色別細目（含 API 預設角色與呼叫錯誤）：")
    lines.append("")
    lines.append("扣留為整庫範圍，故另列「適用」（角色相同且罪章屬本案）與「他罪」（其餘）。")
    lines.append("")
    lines.append("| 案件 | 角色 | 出題 | 扣留 | 扣留適用 | 扣留他罪 | no_source | 未填占位符 | 法條註記略過 | 重複 | set_offenses |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for case_row in report["cases"]:
        for role_row in case_row["roles"]:
            lines.append("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %d | %s |" % (
                case_row["label"], role_row["role"],
                role_row["served"]["count"], role_row["quarantined"]["count"],
                role_row["quarantined"]["applicable_count"],
                role_row["quarantined"]["other_offense_count"],
                role_row["no_source"]["count"], role_row["unresolved_placeholder"]["count"],
                role_row["unresolved_placeholder"]["legal_annotation_skipped"],
                role_row["duplicate_normalized"]["count"],
                role_row["set_offenses_error"] or "OK"))
    lines.append("")
    lines.append("## 3. 事實元素文字比對（診斷，非覆蓋率判定）")
    lines.append("")
    lines.append("覆蓋率由第 4 節的 `route_coverage` 判定，因此 `fact_element_text_hits` "
                 "命中率低是可預期的，本身不是缺陷。本節只回答「路線的 fact_elements 字串"
                 "有沒有出現在問句文字或 meta 裡」。")
    lines.append("")
    lines.append("| 案件 | 路線 | 元素數 | 命中 | 未命中 |")
    lines.append("|---|---|---|---|---|")
    for case_row in report["cases"]:
        if not case_row["fact_element_text_hits"]:
            lines.append("| %s | — | 0 | 0 | 0（無已選路線） |" % case_row["label"])
            continue
        for row in case_row["fact_element_text_hits"]:
            lines.append("| %s | `%s` | %d | %d | %d |" % (
                case_row["label"], row["route_id"], len(row["fact_elements"]),
                len(row["matched"]), len(row["missing"])))
    lines.append("")
    lines.append("未命中的元素明細：")
    lines.append("")
    for case_row in report["cases"]:
        for row in case_row["fact_element_text_hits"]:
            if not row["missing"]:
                continue
            lines.append("- `%s/%s`：%d/%d 未命中" % (
                case_row["label"], row["route_id"], len(row["missing"]), len(row["fact_elements"])))
            for element in row["missing"]:
                lines.append("    - %s" % element)
    lines.append("")
    lines.append("## 4. 路線覆蓋率（route_coverage，權威判定）")
    lines.append("")
    lines.append("逐條轉錄 app 回報的 `question_coverage_by_route`（以 concept id 判定），"
                 "本工具不自行判定覆蓋與否。`materialization_status: null` 代表 app 未回傳該路線的"
                 "覆蓋物件，路線已列入該案 `unknown_route_ids`。")
    lines.append("")
    lines.append("覆蓋物件取自該案最後一次成功的 `set_offenses` 回應（`coverage_role` 記該次角色）；"
                 "同一路線的覆蓋率可能因角色而異。")
    lines.append("")
    lines.append("| 案件 | 角色 | 路線 | materialization_status | missing_concept_ids | pruned_concept_ids | 帶此路線的問句 | 來源 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case_row in report["cases"]:
        if not case_row["route_coverage"]:
            lines.append("| %s | — | — | — | — | — | 0 | %s（無已選路線） |"
                         % (case_row["label"], "question_coverage_by_route"))
            continue
        for row in case_row["route_coverage"]:
            status = row["materialization_status"]
            lines.append("| %s | %s | `%s` | %s | %s | %s | %d | `%s` |" % (
                case_row["label"], case_row["coverage_role"] or "—", row["route_id"],
                status if status is not None else "**null**",
                _format_id_list(row["missing_concept_ids"]),
                _format_id_list(row["pruned_concept_ids"]),
                row["served_questions_with_route_context"],
                row["coverage_source"]))
    lines.append("")
    unknown = ["%s/%s" % (case["label"], route_id)
               for case in report["cases"] for route_id in case["unknown_route_ids"]]
    lines.append("`unknown_route_ids`（無法取得覆蓋物件或對照表沒有此路線）：%s"
                 % ("、".join(unknown) if unknown else "（無。）"))
    lines.append("")
    lines.append("## 5. 工具另外查到、brief 未要求的事")
    lines.append("")
    lines.append("以下依重要性排序，第一項最重要。")
    lines.append("")
    for finding in report["findings"]:
        lines.append("- %s" % finding)
    lines.append("")
    lines.append("## 附錄 A：未填占位符判定的原始命中")
    lines.append("")
    if not any(role_row["unresolved_placeholder"]["count"]
               for case in report["cases"] for role_row in case["roles"]):
        lines.append("（無。）")
    for case_row in report["cases"]:
        for role_row in case_row["roles"]:
            for hit in role_row["unresolved_placeholder"]["questions"]:
                lines.append("- `%s/%s/%s`（%s）：%s"
                             % (case_row["label"], role_row["role"], hit["id"],
                                ", ".join(hit["hits"]), hit["text"]))
    lines.append("")
    return "\n".join(lines)


def _format_id_list(value: object) -> str:
    if value is None:
        return "**null**"
    if isinstance(value, list) and not value:
        return "[]"
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本機案件問句品質稽核")
    parser.add_argument("--spec", required=True, help="案件規格 JSON 檔")
    parser.add_argument("--json", dest="json_out", help="輸出 JSON 報告")
    parser.add_argument("--md", dest="md_out", help="輸出 Markdown 報告")
    parser.add_argument("--base-url", default=None, help="本機 API 位址")
    parser.add_argument("--extra-md", default=None,
                        help="額外附加到 Markdown 報告的片段檔（例如頁面顯示落差分析）")
    parser.add_argument("--determinism", default="未量測（單次執行）",
                        help="穩定性量測結論，原樣寫入報告第一節")
    args = parser.parse_args(argv)

    with open(args.spec, encoding="utf-8") as handle:
        spec = json.load(handle)

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    global normalize
    from app.question_hygiene import normalize  # noqa: PLC0415 - 需先設定 sys.path

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crosswalk_version, elements_by_route = load_crosswalk(repo_root)
    offense_index = load_quarantine_offense_ids(repo_root)

    base_url = args.base_url or spec.get("base_url") or DEFAULT_BASE_URL
    api = Api(base_url)
    api.wait_until_ready()
    api.fetch_token()
    health = api.health()

    cases = []
    for spec_case in spec["cases"]:
        merged = dict(spec_case)
        for key in ("station", "officer"):
            merged.setdefault(key, spec.get(key))
        cases.append(audit_case(api, merged, elements_by_route, offense_index))
    for case_row in cases:
        case_row["totals"] = summarize(case_row)

    report = OrderedDict((
        ("schema_version", "1.0"),
        ("spec", os.path.basename(args.spec)),
        ("invocation", OrderedDict((("spec", args.spec),
                                    ("base_url", base_url),
                                    ("json_out", args.json_out),
                                    ("md_out", args.md_out)))),
        ("base_url", base_url),
        ("crosswalk_version", crosswalk_version),
        ("health", OrderedDict((("mode", health.get("mode")),
                                ("external_ai", health.get("external_ai")),
                                ("external_ai_enabled", health.get("external_ai_enabled"))))),
        ("determinism", OrderedDict((("result", args.determinism),))),
        ("cases", cases),
        ("findings", build_findings(cases)),
    ))

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    if args.md_out:
        markdown = render_markdown(report)
        if args.extra_md:
            with open(args.extra_md, encoding="utf-8") as handle:
                markdown = markdown + "\n" + handle.read()
        with open(args.md_out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)
    if not args.json_out and not args.md_out:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
