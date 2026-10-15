import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ITEM = ROOT / "docs" / "QUESTION_WORK_ITEM.md"
CROSSWALK = ROOT / "data" / "legal_route_crosswalk.json"


def _allowed_route_ids():
    data = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    ids = set()
    for route in data["routes"]:
        for child in route.get("child_routes", []):
            if isinstance(child, dict):
                ids.add(child.get("id"))
    return ids


ALLOWED_ROUTE_IDS = _allowed_route_ids()
PHASES = {"narrative", "single_fact", "evidence_followup"}
ANSWER_MODES = {"narrative_only", "boolean", "enum"}
ROLES = {"victim", "suspect", "transfer", "witness_review_only"}


def _target_route():
    """Extract target_child_route_id from the work item header."""
    text = WORK_ITEM.read_text(encoding="utf-8")
    header = text.split("## A.", 1)[0]
    match = re.search(r"target_child_route_id:\s*([^\n\s]+)", header)
    assert match, "QUESTION_WORK_ITEM header missing target_child_route_id"
    return match.group(1)


def _allowed_alternative_route_ids():
    """Extract non-offense alternative labels from the declared route scope."""
    text = WORK_ITEM.read_text(encoding="utf-8")
    scope = re.search(r"```yaml\s*route_scope:(.*?)```", text, re.DOTALL)
    assert scope, "QUESTION_WORK_ITEM missing route_scope"

    alternatives = re.search(
        r"allowed_alternative_routes:\s*((?:\n\s+-\s*[^\n]+)+)",
        scope.group(1),
    )
    if not alternatives:
        return set()
    return {
        match.group(1)
        for match in re.finditer(r"^\s*-\s*([^\s]+)\s*$", alternatives.group(1), re.MULTILINE)
    }


def _standard_set():
    """Return (concepts, target_route)."""
    text = WORK_ITEM.read_text(encoding="utf-8")
    target_route = _target_route()
    match = re.search(
        r"<!-- STANDARD_SET_START -->\s*```json\s*(.*?)\s*```\s*<!-- STANDARD_SET_END -->",
        text,
        re.DOTALL,
    )
    assert match, "QUESTION_WORK_ITEM 缺少可機械驗證的 STANDARD_SET JSON"
    return json.loads(match.group(1)), target_route


def _crosswalk_child_ids():
    data = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    return {
        child["id"]
        for route in data["routes"]
        for child in route.get("child_routes", [])
        if isinstance(child, dict)
    }


def _canonical_submission(text):
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    submission = normalized.split("<!-- SUBMISSION_START -->", 1)[1]
    submission = submission.split("<!-- SUBMISSION_END -->", 1)[0]
    return submission.strip("\n") + "\n"


def test_reference_standard_has_bounded_unique_concepts():
    concepts, _ = _standard_set()
    ids = [concept["question_concept_id"] for concept in concepts]
    assert 1 <= len(ids) <= 8
    assert len(ids) == len(set(ids))


def test_reference_standard_uses_canonical_schema_and_parent_linkage():
    concepts, target_route = _standard_set()
    ids = {concept["question_concept_id"] for concept in concepts}

    for concept in concepts:
        assert concept["designer_role"] == "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT"
        assert concept["question_phase"] in PHASES
        assert concept["answer_mode"] in ANSWER_MODES
        assert concept["fact_target"]
        assert concept["distinction_axis"]
        assert concept["source_basis"]
        assert concept["rationale"]
        assert concept["trigger_condition"]
        assert f"candidate:{target_route}:present" in concept["trigger_condition"]
        assert set(concept["target_interview_roles"]) == set(concept["role_variants"])
        assert set(concept["role_variants"]) <= ROLES
        assert all(text.strip() for text in concept["role_variants"].values())
        assert concept["exclusion_safe"] is False

        parent = concept["parent_question_id"]
        if concept["question_phase"] == "narrative":
            assert parent is None
            assert concept["answer_mode"] == "narrative_only"
            assert concept["answer_map"] is None
        else:
            assert parent in ids
            trigger_parent = concept.get("depends_on_question_id", parent)
            assert trigger_parent in ids
            assert f"after:{trigger_parent}" in concept["trigger_condition"]
            assert f'fact:{concept["fact_target"]}:UNKNOWN' in concept["trigger_condition"]
            assert isinstance(concept["answer_map"], dict)
            assert set(concept["answer_map"]) == set(concept["answer_codes"]) | {"UNKNOWN"}
            assert all(key == value for key, value in concept["answer_map"].items())


def test_reference_standard_materializes_to_single_role_questions():
    role_codes = {
        "victim": "V",
        "suspect": "S",
        "transfer": "T",
        "witness_review_only": "W",
    }

    instances = []
    concepts, _ = _standard_set()
    for concept in concepts:
        for role, text in concept["role_variants"].items():
            instances.append(
                {
                    "id": f"{concept['question_concept_id']}-{role_codes[role]}",
                    "target_interview_role": role,
                    "text": text,
                    "question_phase": concept["question_phase"],
                    "fact_target": concept["fact_target"],
                    "legal_targets": concept["legal_targets"],
                    "runtime_enabled": role != "witness_review_only",
                }
            )

    ids = [instance["id"] for instance in instances]
    assert ids
    assert len(ids) == len(set(ids))
    for instance in instances:
        assert instance["target_interview_role"] in ROLES
        assert "target_interview_roles" not in instance
        assert instance["text"].strip()
        if instance["target_interview_role"] == "witness_review_only":
            assert instance["runtime_enabled"] is False


def test_reference_standard_uses_only_approved_exact_routes():
    concepts, _ = _standard_set()
    approved = ALLOWED_ROUTE_IDS
    allowed_alternatives = _allowed_alternative_route_ids()
    assert allowed_alternatives.isdisjoint(approved)
    for concept in concepts:
        targets = set(concept["legal_targets"])
        assert targets, concept["question_concept_id"]
        assert targets <= approved, (
            f"{concept['question_concept_id']} has non-approved routes: "
            f"{sorted(targets - approved)}"
        )
        # Offense details and non-offense alternatives are separate namespaces.
        # Legal details must cover exact child routes only; alternative details
        # must be explicitly allowlisted and can never produce an offense effect.
        if concept["question_phase"] != "narrative":
            detail_ids = {detail["route_id"] for detail in concept["legal_target_details"]}
            assert detail_ids == targets, (
                f"{concept['question_concept_id']} details "
                f"{sorted(detail_ids)} do not cover legal_targets {sorted(targets)}"
            )
            for detail in concept["legal_target_details"]:
                assert detail["route_id"] in approved, (
                    f"{concept['question_concept_id']} detail route "
                    f"{detail['route_id']} is not an approved exact route"
                )

            alternative_details = concept.get("alternative_target_details", [])
            alternative_ids = {detail["route_id"] for detail in alternative_details}
            assert len(alternative_ids) == len(alternative_details)
            assert alternative_ids <= allowed_alternatives, (
                f"{concept['question_concept_id']} has non-approved alternatives: "
                f"{sorted(alternative_ids - allowed_alternatives)}"
            )
            for detail in alternative_details:
                required_codes = set(concept["answer_codes"]) | {"UNKNOWN", "CONFLICT"}
                assert set(detail["effects"]) == required_codes
                assert set(detail["effects"].values()) == {"NEED_REVIEW"}
                assert detail["exclusion_safe"] is False
                assert detail["candidate_eligible"] is False
                assert detail["routing_eligible"] is False
                assert detail["question_generation_eligible"] is False
                assert detail["template_activation_eligible"] is False
                assert detail["effect_executable"] is False
                assert detail["human_review_required"] is True


def test_reference_standard_effects_cover_declared_answers_and_fail_closed():
    concepts, _ = _standard_set()
    for concept in concepts:
        if concept["answer_mode"] == "narrative_only":
            continue
        required_codes = set(concept["answer_codes"]) | {"UNKNOWN", "CONFLICT"}
        for detail in concept["legal_target_details"]:
            assert set(detail["effects"]) == required_codes
            assert set(detail["effects"].values()) <= {"ACTIVE", "LOWERED", "NEED_REVIEW"}
            assert detail["effects"]["UNKNOWN"] == "NEED_REVIEW"
            assert detail["effects"]["CONFLICT"] == "NEED_REVIEW"
            assert detail["exclusion_safe"] is False


def test_reference_standard_declares_dedupe_actions_and_safe_consent_effects():
    concepts, _ = _standard_set()
    concepts_dict = {item["question_concept_id"]: item for item in concepts}
    for concept in concepts_dict.values():
        assert isinstance(concept["existing_question_refs"], list)
        assert concept["dedupe_action"] in {
            "REUSE_OR_REPLACE_DO_NOT_COEMIT",
            "REPLACE_COMPOUND_QUESTION_DO_NOT_COEMIT",
            "NEW_GAP",
        }

    consent = next(
        (
            c
            for c in concepts_dict.values()
            if "authorization" in c["fact_target"] or "consent" in c["fact_target"]
        ),
        None,
    )
    if consent:
        assert consent["fact_target"] in {
            "authorization_scope_status",
            "authorization_status",
        }
        civil = next(
            detail
            for detail in consent["alternative_target_details"]
            if detail["route_id"] == "civil_possession_dispute"
        )
        assert set(civil["effects"].values()) == {"NEED_REVIEW"}


def test_reference_standard_preserves_role_boundaries():
    concepts, _ = _standard_set()
    concepts_dict = {item["question_concept_id"]: item for item in concepts}

    for concept_id, concept in concepts_dict.items():
        if "witness_review_only" in concept["role_variants"]:
            witness_text = concept["role_variants"]["witness_review_only"]
            assert witness_text.strip()
            assert "親自" in witness_text
            assert not any(
                banned in witness_text
                for banned in ["你認為", "我認為", "是否知道"]
            )

    text = WORK_ITEM.read_text(encoding="utf-8")
    assert "刑事訴訟法第95條" in text


def test_reference_standard_and_canonical_rules_do_not_drift():
    work_item = WORK_ITEM.read_text(encoding="utf-8")
    rules = (ROOT / "docs" / "QUESTION_DESIGN_AND_USE.md").read_text(encoding="utf-8")
    queue = (ROOT / "docs" / "OFFENSE_QUESTION_WORK_QUEUE.md").read_text(encoding="utf-8")
    target_route = _target_route()

    assert target_route in ALLOWED_ROUTE_IDS
    assert "最多使用八個 question concepts" in rules
    assert "next_route: NOT_AUTHORIZED" in work_item
    assert "next_route: WAITING_FOR_EXPLICIT_SELECTION" not in work_item
    assert "current_target: NONE_SELECTED" in queue
    if "submission_status: READY_FOR_REVIEW" in work_item:
        raise AssertionError("No work item may be READY_FOR_REVIEW while no queue target is selected")


def test_reviewer_decision_binds_the_canonical_submission_only():
    text = WORK_ITEM.read_text(encoding="utf-8")
    decision = text.split("## Reviewer Decision", 1)[1]
    declared = re.search(r"submission_sha256: ([A-F0-9]{64})", decision)

    assert declared
    assert "reviewer_decision:" in decision
    assert "hash_scope: UTF8_LF_BYTES_BETWEEN_SUBMISSION_MARKERS" in decision
    assert "artifact_sha256:" not in decision

    actual = hashlib.sha256(_canonical_submission(text).encode("utf-8")).hexdigest().upper()
    assert declared.group(1) == actual
