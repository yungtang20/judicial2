# ARCHITECTURE_GAP_AUDIT.md

## Document Metadata
- **Created**: 2026-10-11T02:30:00Z
- **Branch**: `fix/legal-reasoning`
- **Current HEAD**: `51d5045fe58...` (structured Gate 1 facts)
- **Baseline Comparison**: `main` branch `a376b83f...` (original)

---

## Phase 0 — Repository Baseline

### Repository State
- Owner: `yungtang20`
- Name: `judicial2`
- Default Branch: `main`
- Current Branches: `main`, `fix/legal-reasoning`, `feature/flow-v0.3`
- Permissions: admin/maintain/push
- Last Push: 2026-10-11 02:24:23 UTC

### Critical Files Audit

#### 1. `legal-case-web/app/rules.py`
- **Branch**: `fix/legal-reasoning` (`51d5045f...`)
- **Change**: Added `_fact_status()` + `_summarize_facts()` functions
- **Status**: ✅ STRUCTURED FACTS IMPLEMENTATION
- **Evidence**:
  - Lines 21–56: Fact decomposition with id/text/status/type/source_ref
  - Lines 70–90: `analyze_gate1()` returns `"facts"` array, not just summary blob
  - Line 242: Backward-compatible alias `analyze_gate1_summary = analyze_gate1`

#### 2. `legal-case-web/app/workflow.py`
- **Branch**: `fix/legal-reasoning` (`8b7535da...`)
- **Status**: ⚠️ PARTIAL - File exists but summary-only view returned by API
- **Change Expected**: `update_gate1` action, `_invalidate()` downstream approvals
- **Evidence Check Needed**: Full file retrieval

#### 3. `legal-case-web/tests/test_workflow.py`
- **Branch**: `fix/legal-reasoning`
- **Status**: ⚠️ REGRESSION TESTS ADDED
- **Change Expected**: `test_gate1_facts_are_structured_and_invalidate_downstream()`
- **Evidence Check Needed**: Full file retrieval

#### 4. `legal-case-web/app/storage.py`
- **Status**: NOT CHECKED YET

#### 5. `legal-case-web/app/static/app.js`
- **Status**: NOT CHECKED YET

---

## Phase 1 — Gate 1 Structural Validation

### Requirement 1: Fact Decomposition Instead of Summary Blob
**Current Implementation** (`fix/legal-reasoning`):
```python
# ✅ FOUND: _summarize_facts() breaks down case summary
def _summarize_facts(summary: str, intake: dict[str, Any]) -> list[dict[str, Any]]:
    fragments = [piece.strip() for piece in re.split(r"[。！？\n]+", summary)]
    # Each fragment becomes a structured fact with id, text, status, type, source_ref
```

**Status**: ✅ PASS
- Fact array is generated from case summary
- Each fact has: id, text, status, type, source_ref, source_excerpt
- Facts retain: person, time, place, object, causal_relation, review_status, notes

### Requirement 2: Traceable Source & Status
**Evidence**:
- `source_ref`: "intake.summary" (or user-updated)
- `source_excerpt`: exact fragment text
- `status`: "KNOWN" or "UNKNOWN" based on content keywords
- `review_status`: "HUMAN_REVIEW_REQUIRED" (blocking premature approval)

**Status**: ✅ PASS

### Requirement 3: Gate 1 Modification Invalidates Downstream
**Expected Behavior**:
- Action `update_gate1` should accept new fact array
- Downstream approvals (gate2, case_numbers, output) should be cleared
- Questions and interviews should be reset

**Verification Needed**: 
- [ ] Check if `update_gate1` action exists in workflow.py
- [ ] Check if `_invalidate(case, "gate1")` is called
- [ ] Verify test case `test_gate1_facts_are_structured_and_invalidate_downstream()`

**Status**: ⚠️ NEEDS FULL FILE REVIEW

### Requirement 4: Backward Compatibility
**Expected**: 
- Existing tests should still pass
- Old data without `facts` array should not crash

**Status**: ⚠️ NEEDS VERIFICATION

---

## Gap Summary (Pre-Full-Review)

| Item | Gap | Evidence | Status |
|------|-----|----------|--------|
| Fact Decomposition | ✅ Implemented | `_summarize_facts()` in rules.py lines 30–56 | PASS |
| Traceable Source | ✅ Implemented | `source_ref`, `source_excerpt` fields present | PASS |
| Status Field | ✅ Implemented | `_fact_status()` in rules.py lines 21–27 | PASS |
| `update_gate1` Action | ⚠️ Not verified | workflow.py partial view | NEEDS CHECK |
| Downstream Invalidation | ⚠️ Not verified | `_invalidate()` expected in workflow.py | NEEDS CHECK |
| Regression Tests | ⚠️ Not verified | test_workflow.py expected new test | NEEDS CHECK |
| Storage Persistence | ⚠️ Not verified | storage.py not checked | NEEDS CHECK |
| Frontend Sync | ⚠️ Not verified | app.js not checked | NEEDS CHECK |

---

## Phase 2 — Gate 2 Preliminary Assessment

**NOT YET EXAMINED**. Will proceed after Phase 1 verification.

### Gate 2 Expected Architecture
1. Candidate offense generation (rules + AI)
2. Constituent element checklist per offense
3. Supporting fact / contradicting fact / unknown item tracking
4. Question generation tied to offense + element
5. Answer persistence with traceability
6. Human review approval

### Known Issues (from code review):
- Candidate offenses currently: id, name, matched_terms, status, notice, supporting_fact_refs, contradicting_fact_refs, unknown_elements, source
- No explicit "element_id" link in questions to structured facts
- No "element_status" tracking (met/not met/unknown/contradicting)

**Status**: BLOCKED until Phase 1 completes

---

## Next Steps

1. **Phase 1a**: Retrieve full workflow.py and verify `update_gate1` + `_invalidate()` implementation
2. **Phase 1b**: Verify test_workflow.py has regression test
3. **Phase 1c**: Check storage.py for fact persistence
4. **Phase 1d**: Check app.js frontend synchronization
5. **Phase 1e**: Run pytest on `fix/legal-reasoning` branch
6. **Phase 2**: Proceed to Gate 2 architecture assessment

---

**Document Status**: IN PROGRESS
**Last Updated**: 2026-10-11 (Phase 0 baseline)
