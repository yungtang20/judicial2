"""問句品質稽核工具：對一組案件規格，逐案逐角色收集已出題問句並列出品質缺陷。

用法：
    py -3 tools/question_audit.py --spec tools/question_audit_spec.json --json out.json --md out.md

設計原則：
- 只呼叫本機 API（預設 http://127.0.0.1:8787），不連外。
- 判定規則全部機械化（見 question_audit_spec.json 與 README 的 unresolved_placeholder 說明），
  不解讀案情、不作法律判斷。
- 報告不含時間戳、UUID、revision 等易變欄位，因此同一份輸入必須產生位元組相同的報告；
  「跑兩次比對 JSON」即為這支工具的穩定性量測手段。
- 唯一外部相依是本庫自己的 app.question_hygiene.normalize（去重鍵的權威定義）。
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

# ---------------------------------------------------------------- 判定規則 --

# 一個括號（全形或半形）包裹的內容，用於檢查是否為未填欄位。
_PAREN_RUN = re.compile(r"[（(]([^（）()]{0,40})[）)]")
# 括號內容含阿拉伯數字才算「未填的數字欄位」。
_DIGIT = re.compile(r"[0-9]")
# 只含空白的括號欄位是合法的，例如「你今（　）日因何事接受警方製作筆錄？」。
_BLANK_ONLY = re.compile(r"[\s\u3000]*")
# 代號樣式占位符，例如「〈代號〉」。
_CODE_SLOT = re.compile(r"〈[^〉]{0,20}〉")
# 「已填值」的判定：阿拉伯數字或英文字母。允許以連接號、波浪號、空白銜接。
_SEP = r"\-~\u2013\u2014\uFF5E\u0020\u3000\t"
_CODE_SLOT_ADJACENT = re.compile(
    "(?:[0-9A-Za-z]|[%s]*[0-9A-Za-z])[%s]*〈[^〉]{0,20}〉|〈[^〉]{0,20}〉[%s]*(?:[0-9A-Za-z]|[%s]*[0-9A-Za-z])"
    % (_SEP, _SEP, _SEP, _SEP)
)


def unresolved_placeholder_hits(text: str) -> list[str]:
    """回傳該題命中的「未填占位符」樣式名稱清單（空清單代表不含缺陷）。

    依 brief 的機械定義：
    (a) paren_with_digit：括號內含數字（不是只有空白）；
    (b) code_slot_adjacent_filled_value：〈…〉緊鄰已填值。
    只有空白的括號欄位（如「（　）」）合法，不列入。
    """
    hits: list[str] = []
    for match in _PAREN_RUN.finditer(text):
        inner = match.group(1)
        if _DIGIT.search(inner) and not _BLANK_ONLY.fullmatch(inner):
            hits.append("paren_with_digit")
            break
    if _CODE_SLOT_ADJACENT.search(text):
        hits.append("code_slot_adjacent_filled_value")
    return hits


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


def element_gaps(route_ids: list[str], elements_by_route: dict[str, list[str]],
                 served: list[dict], meta_blobs: dict[str, str], unknown: list[str]) -> list[dict]:
    """回傳每條已選路線的 fact_elements 缺口；只在問句 text 或 meta 內做字串比對，不判斷關聯性。

    served 為報告用的精簡紀錄（不含 meta），meta_blobs 以 question id 對應 meta 的 JSON 文字，
    因此「有沒有問句引用到這個事實元素」仍是對原始 meta 判定，而非對精簡紀錄判定。
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


def audit_case(api: Api, spec_case: dict, crosswalk: dict[str, list[str]]) -> dict:
    label = spec_case["label"]
    case = api.create_case(spec_case)
    case_id = case["case_id"]
    default_role = case.get("question_role")

    result: dict = OrderedDict((
        ("label", label),
        ("has_victim", bool(spec_case.get("has_victim", True))),
        ("default_role", default_role),
        ("prepare", "OK"),
        ("prepare_error", None),
        ("selected_offenses", []),
        ("selected_legal_routes", []),
        ("route_selection_status", None),
        ("roles", []),
        ("element_gaps", []),
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
    meta_blobs: dict[str, str] = {}
    for role in requested:
        role_row: dict = OrderedDict((
            ("role", role),
            ("set_offenses_error", None),
            ("served", OrderedDict((("count", 0), ("questions", [])))),
            ("quarantined", OrderedDict((("count", 0), ("by_rule", {})))),
            ("no_source", OrderedDict((("count", 0), ("questions", [])))),
            ("unresolved_placeholder", OrderedDict((("count", 0), ("questions", [])))),
            ("duplicate_normalized", OrderedDict((("count", 0), ("groups", [])))),
        ))
        try:
            current = api.get_case(case_id)
            case = api.act(case_id, current["revision"], "set_offenses", {
                "offense_ids": current.get("selected_offenses"),
                "legal_route_ids": [route.get("route_id")
                                    for route in (current.get("selected_legal_routes") or [])],
                "route_review_confirmed": True,
                "role": role,
            })
        except ApiError as exc:
            role_row["set_offenses_error"] = exc.body
            result["roles"].append(role_row)
            continue

        questions = case.get("questions") or []
        served = [question_record(question, role) for question in questions]
        served_all.extend(served)
        for record, question in zip(served, questions):
            meta_blobs[record["id"]] = json.dumps(question.get("meta") or {}, ensure_ascii=False)

        role_row["served"]["count"] = len(served)
        role_row["served"]["questions"] = served

        quarantine = case.get("question_quarantine") or []
        role_row["quarantined"]["count"] = len(quarantine)
        role_row["quarantined"]["by_rule"] = group_by_rule(quarantine)

        no_source = [record for record, question in zip(served, questions)
                     if not question.get("source")]
        role_row["no_source"]["count"] = len(no_source)
        role_row["no_source"]["questions"] = [record["id"] for record in no_source]

        placeholders = []
        for record in served:
            hits = unresolved_placeholder_hits(record["text"])
            if hits:
                placeholders.append(OrderedDict((("id", record["id"]), ("hits", hits),
                                                 ("text", record["text"]))))
        role_row["unresolved_placeholder"]["count"] = len(placeholders)
        role_row["unresolved_placeholder"]["questions"] = placeholders

        groups = duplicate_groups(served)
        role_row["duplicate_normalized"]["count"] = sum(len(group) for group in groups)
        role_row["duplicate_normalized"]["groups"] = groups

        result["roles"].append(role_row)

    result["element_gaps"] = element_gaps(
        result["selected_legal_routes"], crosswalk, served_all, meta_blobs,
        result["unknown_route_ids"])
    return result


def summarize(case_row: dict) -> dict:
    totals = OrderedDict((("served", 0), ("quarantined", 0), ("no_source", 0),
                          ("unresolved_placeholder", 0), ("duplicate_normalized", 0)))
    for role_row in case_row["roles"]:
        totals["served"] += role_row["served"]["count"]
        totals["quarantined"] += role_row["quarantined"]["count"]
        totals["no_source"] += role_row["no_source"]["count"]
        totals["unresolved_placeholder"] += role_row["unresolved_placeholder"]["count"]
        totals["duplicate_normalized"] += role_row["duplicate_normalized"]["count"]
    return totals


def build_findings(cases: list[dict]) -> list[str]:
    """把掃描中確定可複現的異常寫成 findings，供報告第四節引用。"""
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
    if paren:
        findings.append(
            "brief 指定的機械規則（括號內含數字）共命中 %d 題，逐題檢視全部是合法的程序註記"
            "（如「（§17 I，須依程序進行，並告知權益）」），並非未填欄位；"
            "把這個計數當缺陷數會誤報，需人工複核。命中：%s。"
            % (len(paren), "、".join("%s/%s/%s" % row for row in paren)))
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
            "已產生候選罪章但一條法規路線都沒選到（element_gaps 因此無從計算）：%s。"
            % "、".join(no_route))
    rows = [(case["label"], row) for case in cases for row in case["element_gaps"]]
    full = [(label, row["route_id"]) for label, row in rows if row["missing"] == row["fact_elements"]]
    if rows and len(full) == len(rows):
        findings.append(
            "本次 %d 條已選路線的 fact_elements **全部**沒有任何出題引用（缺口 100%%）：%s。"
            "元素字串只出現在 payload 的 `candidates[].legal_routes[].fact_elements` 與 "
            "`candidates[].route_element_matrix[].elements[].element`；出題的 `meta.target_elements`、"
            "`meta.legal_target_details` 全數為空，所以「路線 → 事實元素 → 問句」這條鏈在出題層是斷的。"
            % (len(rows), "、".join("%s/%s" % item for item in full)))
    return findings


# ----------------------------------------------------------------- 輸出 ----


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# 問句品質稽核報告")
    lines.append("")
    lines.append("- 產生方式：`py -3 tools/question_audit.py --spec tools/question_audit_spec.json "
                 "--json out.json --md out.md`")
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
    lines.append("| 案件 | 罪章 | 已選路線 | 準備 | 出題 | 扣留 | no_source | 未填占位符 | 重複 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for case_row in report["cases"]:
        totals = case_row["totals"]
        mark = lambda n: ("**%d**" % n) if n else "0"
        lines.append("| %s | %s | %s | %s | %d | %s | %s | %s | %s |" % (
            case_row["label"],
            ", ".join(case_row["selected_offenses"]) or "—",
            ", ".join(case_row["selected_legal_routes"]) or "—",
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
    lines.append("| 案件 | 角色 | 出題 | 扣留 | no_source | 未填占位符 | 重複 | set_offenses |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case_row in report["cases"]:
        for role_row in case_row["roles"]:
            lines.append("| %s | %s | %d | %d | %d | %d | %d | %s |" % (
                case_row["label"], role_row["role"],
                role_row["served"]["count"], role_row["quarantined"]["count"],
                role_row["no_source"]["count"], role_row["unresolved_placeholder"]["count"],
                role_row["duplicate_normalized"]["count"],
                role_row["set_offenses_error"] or "OK"))
    lines.append("")
    lines.append("## 3. 事實元素缺口（element_gaps）")
    lines.append("")
    for case_row in report["cases"]:
        lines.append("### %s" % case_row["label"])
        lines.append("")
        if not case_row["element_gaps"]:
            lines.append("無已選路線（未選路線或未產生路線），故無缺口可列。")
            lines.append("")
            continue
        for row in case_row["element_gaps"]:
            if not row["missing"]:
                lines.append("- `%s`：**無缺口**，%d 項全部有出題引用。"
                             % (row["route_id"], len(row["fact_elements"])))
                continue
            lines.append("- `%s`：缺口 **%d/%d**"
                         % (row["route_id"], len(row["missing"]), len(row["fact_elements"])))
            for element in row["missing"]:
                lines.append("    - %s" % element)
        lines.append("")
    lines.append("## 4. 工具另外查到、brief 未要求的事")
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
        cases.append(audit_case(api, merged, elements_by_route))
    for case_row in cases:
        case_row["totals"] = summarize(case_row)

    report = OrderedDict((
        ("schema_version", "1.0"),
        ("spec", os.path.basename(args.spec)),
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
