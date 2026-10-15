# Task 0.5: 資料完整性與法律檢索能力複核報告
**生成時間:** 2026-10-15 13:24:53
**目前階段:** Step 1 — 環境保護狀態與檔案清單盤點

## 1. 目錄檢查
- `root_dir` (D:\工作用\judicial1\legal-case-web) 存在: True
- `questions_dir` (D:\工作用\judicial1\questions) 存在: True
- `review_dir` (D:\工作用\judicial1\legal-case-web\review) 存在: True

## 2. Git 狀態 (工作樹)
```text
M legal-case-web/README.md
 M legal-case-web/app/ai.py
 M legal-case-web/app/config.py
 M legal-case-web/app/documents.py
 M legal-case-web/app/markdown_questions.py
 M legal-case-web/app/roc_time.py
 M legal-case-web/app/rules.py
 M legal-case-web/app/section_questions.py
 M legal-case-web/app/security.py
 M legal-case-web/app/server.py
 M legal-case-web/app/static/app.js
 M legal-case-web/app/static/index.html
 M legal-case-web/app/static/styles.css
 M legal-case-web/app/storage.py
 M legal-case-web/app/workflow.py
 M legal-case-web/app/xlsm_questions.py
 M legal-case-web/data/question_bank.json
 M legal-case-web/data/source_manifest.json
 M legal-case-web/docs/LIFECYCLE_RECORD.md
 M legal-case-web/start.ps1
 M legal-case-web/tests/helpers.py
 M legal-case-web/tests/test_ai.py
 M legal-case-web/tests/test_documents.py
 M legal-case-web/tests/test_line_cases.py
 M legal-case-web/tests/test_rules.py
 M legal-case-web/tests/test_server_security.py
 M legal-case-web/tests/test_storage_security.py
 M legal-case-web/tests/test_workflow.py
 M questions/index.md
 M questions/judicial-integrity.md
 M questions/obstruction.md
?? .gitattributes
?? .gitignore
?? legal-case-web/1.md
?? legal-case-web/2.md
?? legal-case-web/app/acts.py
?? legal-case-web/app/document_validation.py
?? legal-case-web/app/law_reference.py
?? legal-case-web/app/legal_provider_fixtures.py
?? legal-case-web/app/legal_retrieval.py
?? legal-case-web/app/legal_retrieval_batch.py
?? legal-case-web/app/legal_retrieval_cache.py
?? legal-case-web/app/legal_retrieval_reconciliation.py
?? legal-case-web/app/legal_retrieval_replay.py
?? legal-case-web/app/legal_retrieval_sync.py
?? legal-case-web/app/legal_semantic_corpus.py
?? legal-case-web/app/offense_linkage.py
?? legal-case-web/app/questions.py
?? legal-case-web/app/rcq_loader.py
?? legal-case-web/data/law_reference_cache.json
?? legal-case-web/data/legal_route_crosswalk.json
?? legal-case-web/data/offense_linkage_poc.json
?? legal-case-web/docs/AI_EXECUTION_PROTOCOL.md
?? legal-case-web/docs/AI_HANDOFF_PROMPT.md
?? legal-case-web/docs/CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md
?? legal-case-web/docs/HG_LR_01_PROVIDER_REVIEW.md
?? legal-case-web/docs/HG_LR_02_PRIVACY_SECURITY_REVIEW.md
?? legal-case-web/docs/LAW_LIFECYCLE.md
?? legal-case-web/docs/LAW_REGISTRY.md
?? legal-case-web/docs/LEGAL_RETRIEVAL_HUMAN_GATE.md
?? legal-case-web/docs/OFFENSE_QUESTION_WORK_QUEUE.md
?? legal-case-web/docs/QUESTION_DESIGN_AND_USE.md
?? legal-case-web/docs/QUESTION_WORK_ITEM.md
?? legal-case-web/docs/RCQ_HUMAN_REVIEW_WORKSHEET.md
?? legal-case-web/docs/README.md
?? legal-case-web/docs/REFERENCE_STANDARD_LIBRARY.md
?? legal-case-web/docs/SEMANTIC_TEST_SET_REVIEW_WORKSHEET.md
?? legal-case-web/docs/SYSTEM_ARCHITECTURE.md
?? legal-case-web/docs/evidence/
?? legal-case-web/review/
?? legal-case-web/tests/_budget_audit.py
?? legal-case-web/tests/fixtures/
?? legal-case-web/tests/test_e2e_flow.py
?? legal-case-web/tests/test_frontend_api_errors.mjs
?? legal-case-web/tests/test_frontend_api_errors.py
?? legal-case-web/tests/test_gate2_legal_route_selection.py
?? legal-case-web/tests/test_hg_lr_01_provider_review.py
?? legal-case-web/tests/test_hg_lr_02_privacy_security_review.py
?? legal-case-web/tests/test_legal_provider_fixtures.py
?? legal-case-web/tests/test_legal_retrieval.py
?? legal-case-web/tests/test_legal_retrieval_batch.py
?? legal-case-web/tests/test_legal_retrieval_cache.py
?? legal-case-web/tests/test_legal_retrieval_human_gate_packet.py
?? legal-case-web/tests/test_legal_retrieval_reconciliation.py
?? legal-case-web/tests/test_legal_retrieval_replay.py
?? legal-case-web/tests/test_legal_retrieval_sync.py
?? legal-case-web/tests/test_legal_semantic_corpus.py
?? legal-case-web/tests/test_offense_linkage_poc.py
?? legal-case-web/tests/test_p0_confirmed_rules.py
?? legal-case-web/tests/test_question_logic.py
?? legal-case-web/tests/test_question_work_item_contract.py
?? legal-case-web/tests/test_rcq_loader.py
?? rule/
```

## 3. Questions 目錄 .md 檔案清單
**總數:** 51
| 檔名 | 大小 (Bytes) |
|---|---|
| `abandonment.md` | 6931 |
| `abortion.md` | 2131 |
| `accusation.md` | 6451 |
| `agriculture-commerce.md` | 1668 |
| `child-protection.md` | 10055 |
| `common.md` | 4520 |
| `company-standard.md` | 3146 |
| `complaint.md` | 2996 |
| `computer.md` | 6873 |
| `currency.md` | 6023 |
| `damage.md` | 7901 |
| `defamation.md` | 7760 |
| `disorder.md` | 6206 |
| `domestic-violence.md` | 10125 |
| `drink-driving.md` | 8666 |
| `drugs.md` | 11942 |
| `duty.md` | 7560 |
| `embezzlement.md` | 9236 |
| `escape-concealment.md` | 5755 |
| `evidence.md` | 4591 |
| `fence.md` | 5102 |
| `forgery.md` | 6791 |
| `fraud.md` | 9849 |
| `gambling.md` | 5857 |
| `gender-equality.md` | 10658 |
| `graves-religion.md` | 1468 |
| `homicide.md` | 7346 |
| `index.md` | 5678 |
| `infanticide-procuring.md` | 6688 |
| `injury.md` | 7771 |
| `judicial-integrity.md` | 1953 |
| `juvenile.md` | 14757 |
| `liberty.md` | 7592 |
| `marriage.md` | 5317 |
| `obscenity.md` | 5824 |
| `obstruction.md` | 8202 |
| `opium.md` | 1580 |
| `privacy.md` | 10864 |
| `public-danger.md` | 2772 |
| `review-checklist.md` | 3861 |
| `robbery.md` | 8931 |
| `securities.md` | 6491 |
| `sexual-harassment.md` | 11457 |
| `sexual.md` | 9445 |
| `stalking.md` | 6689 |
| `state-security.md` | 2975 |
| `theft.md` | 11549 |
| `threat.md` | 7341 |
| `trafficking.md` | 14796 |
| `voting.md` | 6358 |
| `weights-measures.md` | 1196 |

## 4. 排除檔案檢查與數量核對
- `index.md` 存在: True
- `common.md` 存在: True
- `complaint.md` 存在: True
- `review-checklist.md` 存在: True
- `company-standard.md` 存在: True

**數量核對結果:**
- 全部 .md 檔案: 51
- 排除 4 個基礎檔案後 (預期 53): 47
- 再排除 company-standard.md 後 (預期 52): 46
