# E 輪 rules.py 審閱筆記（目標版本 sha256 `9bd6474d…`）

> **【2026-10-20 審查結論：CHANGES_REQUESTED】** E-1～E-6 全部 ✗，D1 定案
> 「B 修正版（theft／embezzlement／robbery 三路區辨）」。各項否定理由與
> 修復結果詳見 `e2_round_rules_py_review_notes.md`，決策記錄見
> `docs/evidence/hg_rules_py_e2_correction_record.json`。以下內容保留為
> 當時送審版本之紀錄，未回填任何勾選。

> 背景：人工以 /goal 授權直接修改（goal 28196bb3…）。本輪 `app/rules.py` 由
> `7d785584…`（前輪已審閱完成，記錄 HG-RULES-REVIEW-20261019-01）演進為
> `9bd6474d…`。請對照以下六項修改逐一勾選 ✗／✓。
> 全部僅為「**白話情境語句提示層**」與「**元素訊號層**」修改：只建立
> NEED_REVIEW 候選方向、只擴大元素「可檢查」訊號，不得且不會升級任何
> 法律結論；`question_bank.json` 未動（git diff 驗證空）。

---

## 修改點清單

### E-1 intimidation hint 擴充
- 位置：`app/rules.py` `_PHRASE_HINTS` → `offense_id: "intimidation"`
- pattern1 補：`小心一點|要你小心|會出事|不會放過你|會傷害|傷害你`
- pattern2 補：`很害怕|不敢出門|不敢報警|家門口|到我家|到你家|在門口|等在門口|不告訴就傷害`
- 新增 exclude：`新聞|報導|聽說|聽到有人|電影|小說|歷史`
- 探針：V1「晚上小心一點＋知道我家住哪＋我很害怕」修前**空**→修後 intimidation；
  V2「不會放過我＋嚇得不敢出門」修後 intimidation；否定句「沒有恐嚇我的意思」仍**空** ✓
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-2 stalking hint 擴充
- pattern1 補：`守候|徘徊|守在|等候|等在|(到|來)(我|你|人)(家|學校|公司|工作|住處|門口|樓下|附近)|在門口|等在門口`
- pattern2（頻率）補：`每天|一週|每個月|常常|經常|連續`
- exclude 補干擾詞：`包裹|外送|快遞|郵件|簽收|派送`
- 探針：V1「連續一週每天到樓下等我，明確拒絕見面」修前**空**→修後 stalking；
  V2「家門口徘徊＋早拒絕聯絡」修後 stalking；V5「守在車站出口等我」修後 stalking；
  快遞句仍**空** ✓；既有測試句「前男友一直跟在我後面，還反覆傳訊息」不 rupture ✓
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-3 obstruction hint **新增**（原無 hint 條目）
- pattern1：`公務員|警察|員警|交警|交通警察|執勤|依法執行|執行職務|查封|封印`
- pattern2：`推開|攔阻|撞開|阻止|拒絕配合|不配合|強暴|脅迫|毆打|揮打|辱罵|妨害`
- exclude：`新聞|報導|聽說|聽到有人|電影|小說|歷史`
- 真實書類對照（§135-1）：「對於公務員依法執行職務時，施強暴脅迫為要件」
- 探針：罵交警＋阻止酒測、攔阻執勤交警兩句修前**空**→修後 obstruction
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-4 robbery hint pattern1 擴充
- 補：`威脅|持刀|兇器|行兇|刀械`（pattern2 財物詞不變）
- 探針：菜刀逼交現金句修前只給 intimidation→修後 robbery＋intimidation 皆候選
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-5 embezzlement hint **新增**（原無 hint 條目；bank 無「拒不返還」關鍵字）
- pattern1：`保管|代管|代收|受託|業務上|出納|財務|會計`
- pattern2：`拒不返還|不還|占為己有|當作自己的|轉入自己帳戶|花用|侵吞`
- exclude：`新聞|報導|聽說|聽到有人|電影|小說|歷史`
- 探針：「出納把公款轉入自己的帳戶，花用在個人消費上，拒不返還」修前**空**→修後 embezzlement
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-6 意圖元素訊號擴充（`_element_evidence_patterns`）
- 「為自己或第三人不法所有之意圖」訊號由僅 `不法所有`
  補為 +`花用|轉入自己帳戶|當作自己的|當成自己的|侵吞|據為己有`
- 效果：僅擴大該元素「可檢查」判定訊號（真實書類強調變易持有為所有）；
  不改任何候選狀態或結論語義
- 判定：□ ✓　□ ✗（備註：＿＿）

---

## 穩定性驗收證據
- pytest **390 passed**（含 test_legal_retrieval_human_gate_packet hash 鏈自檢）
- node `tests/test_frontend_api_errors.mjs` **22/22**
- hash 鏈機械刷新：rules.py `9bd6474d` → packet `7cd468e7` → hg01 `3515143a` →
  hg02、review_record target 五節點對等；frozen_files 10/10
- 18 句探針邊界全表：見 `discovery_quality_comparison.md` §5「探針邊界複驗」

## 已知未決（非本檔範圍）
- **D1**（財物相關擴展降鄰）：已於 2026-10-20 人工核定「B 修正版（三路區辨）」並實作；原提案檔已移除，記錄見 `docs/evidence/hg_rules_py_e2_correction_record.json` 與 `e2_round_rules_py_review_notes.md`
- 新聞句仍可經 bank 關鍵字直接命中（既有行為；bank 關鍵字凍結不動）

## 你勾完後我做的事（機械記帳）
1. 依勾選結果更新 `hg_rules_py_human_review_record.json`（目標 sha 已指向 9bd6474d）
2. 有 ✗ 項 → 探針重現 → 最小修改 → 回歸 → hash 鏈再刷新
3. D1 若選 B，另走 crosswalk 流程
