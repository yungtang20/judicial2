import importlib.util
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "question_audit", Path(__file__).resolve().parents[1] / "tools" / "question_audit.py"
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
unresolved_placeholder_hits = _MODULE.unresolved_placeholder_hits


def test_legal_citation_is_not_reported_as_unresolved_placeholder():
    assert unresolved_placeholder_hits("你是否願意供出來源？（§17 I，須依程序進行）") == ([], 1)
    assert unresolved_placeholder_hits("本檔未確認（第355條）章節歸屬") == ([], 1)


def test_filled_code_slot_remains_reported():
    assert unresolved_placeholder_hits("請撥打412-〈代號〉轉2諮詢") == (
        ["code_slot_adjacent_filled_value"], 0
    )
