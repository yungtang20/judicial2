# E2 輪 rules.py 審閱筆記（目標版本 sha256 `42f63e35…`，待人工複審）

> **【2026-10-20 第五輪複審結果：`EXACT_REPRO_PASS / GENERAL_GATE_FAIL`（僅第 1 項 ✓）】**
> 新反例：裸「拒絕過」未綁接觸對象、veto 未含「聲請停止執行」、「使人交付報告」
> 未綁財物、`_sentence_bound_anchor` 未真正逐一列舉 act×anchor。已依第六輪（E6）
> 修復，修復版 rules.py `9360d5b5…`，pytest 391 passed、前端 22/22，見下方 **E6 輪修訂**。
> P1 裁定 **A**（動態 ID 遮罩＋資產 hash 綁定＋重擷取＋擴充覆蓋）；P2 裁定 **A**
> （去重／英譯確認／AI_* 映射／跨案件汙染清理後重新抽樣）。兩者完成前維持 FAIL。

---

## E6 輪修訂（第五輪複審回饋之程式碼層修復；question_bank.json 仍零變更）

### 四項 ✗ 的根因與修法

| 審查項目 | 第五輪繞進路徑（你的重現） | E6 修復 |
|---|---|---|
| E-2 stalking | 「他騷擾同事，我**拒絕過**另一人的邀約。」 | 裸「拒絕過」移除；僅承認頻率補語（拒絕過很多次／多次／好幾次／無數次／一次又一次／一再） |
| E-3 obstruction | 「我依法**聲請停止執行**，以攔阻該執行。」 | veto 表補「聲請停止執行／依法聲請／聲請」 |
| E-4 robbery | 「他以脅迫方式使人交付**報告**。」 | `使人(不能抗拒)?(而)?交付` 後必須接財物名詞（財物／金錢／現金／贓款／款項／皮包／手機／車／鑰匙／存摺／證件／珠寶／金器）；hint／gate／D1 共用同一常數 |
| 機制 | `_sentence_bound_anchor` 找到第一個未否定 act 即 `break` | 重寫為**逐一列舉同句所有 act×anchor 配對**，任一配對成立（兩者皆未否定、錨點未落 veto）即通過 |

### E6 驗證
- 第五輪三個新反例＋第四輪四例＋第三輪五例＋裁定①三例：全部清除為空或其他行為章
- 正例電池 22 句全召回（含「拒絕過很多次」頻率型拒絕、「致使被害人不能抗拒而交付財物」制式句）
- pytest **391 passed**（hash 自檢綠）；前端 **22/22**
- hash 鏈五節點：rules.py `9360d5b5…` → packet `3bc8777e…` → hg01 `d6bbba8a…` → hg02 → record target；frozen 10/10
- 凍結檔 diff **空**；零 commit

### E6 已知限制（明列）
- 頻率型「拒絕過」仍依賴同句行為語存在；跨句的正當拒絕維持 Precision 優先損失。
- veto 為關鍵字表；表外的程序措辭需要你提供原句才能收緊。
- **actor—conduct—target 角色綁定（LawBank 式約束比對）尚未實作**——這是下一階段架構性步驟（見下方 LawBank 分析回應）。

### P0 最終覆驗（E6 修復後）
1. 「從未」群納入全域否定標記（keyword／hint／錨點／D1 四層同步生效） → **✓**
2. 拒絕錨點指向接觸對象／句尾收束（擋「拒絕另一人的邀約」） → **✓**
3. 攔阻的法律程序 veto（12 字前置窗口） → **✓**
4. 交付錨點綁定財物對象（hint／gate／D1 契約合一） → **✓**
5. `_sentence_bound_anchor` 逐一配對升級 → **✓**

覆驗證據：第四輪四類、第三輪五例、裁定①三例、第五輪新反例，加上非性失能、跨事件否定證據、推打／推擠／扯住員警及未取得財物之 fail-closed 案例均納入回歸。`pytest 405 passed`，前端 `25/25 passed`；當前 `rules.py` sha256 `84f100e12dda047a9b85588e286b220673d40ee8150e8b777e009a5e86eefcec`。

### 需你複審的 E6 勾選項
1. 裸「拒絕過」改頻率補語綁定 → ✓／✗＋備註
2. veto 補「聲請停止執行」群 → ✓／✗＋備註
3. 「使人交付」綁定財物對象 → ✓／✗＋備註
4. `_sentence_bound_anchor` 真正逐一列舉 act×anchor → ✓／✗＋備註

---

## （歷史）E5 輪修訂（第四輪複審回饋之程式碼層修復；question_bank.json 仍零變更）

### 四項 ✗ 的根因與修法

| 審查項目 | 第四輪繞進路徑（你的重現） | E5 修復 |
|---|---|---|
| E-2 stalking | 「我從未騷擾她，她也從未明確拒絕」（否定詞表缺「從未」）；「他騷擾同事，我明確拒絕另一人的邀約」（拒絕錨點不指向接觸對象） | `_NEGATION_MARKERS` 補「從未／未曾／從沒／從來沒有／從來不／從來未」（動詞與錨點同被否定）；「拒絕」錨點改指向聯繫／接觸類對象（拒絕＋見面/聯絡/聯繫/接觸/來往/跟蹤/騷擾/傳訊…），裸「明確拒絕」僅句尾或停頓收束時成立，「拒絕過」保留 |
| E-3 obstruction | 「從未攔阻或脅迫」未被擋；法律程序「攔阻」被當物理強暴 | 「從未」補入即擋；「攔阻」拆出獨立 bound pair，前置 12 字內有程序／法律途徑／聲明異議／訴願／行政救濟／訴訟語境者剔除 |
| E-4 robbery | 「從未脅迫／從未搶走」；裸「交付」被無關「不能抗拒」語境帶入 | 「從未」補入即擋；`_ROBBERY_TAKE_ANCHOR` 刪泛用 `交(出\|付\|給)`，交付面綁定財物對象（交出錢包／交付財物／使人(不能抗拒)(而)交付），hint pat2 引用同一常數——**hint／gate／D1 訊號契約合一** |
| E-5 related | 四訊號走 `_patterns_unnegated` 但其否定源頭 `_NEGATION_MARKERS` 缺「從未」 | 否定詞表補齊後，四訊號與閘門、hint 全部同步獲得「從未」感知（單一共用窗口語義） |
| 裁定① | ✓ | 驗證維持：性騷擾／聲請保護令／冒充公務員→只留各自行為章 |

### 機制變更（規模較大，請特別複審）
1. **否定詞表是全域共用**——從未群現在對關鍵字層／hint／錨點閘門／D1 四訊號同時生效（語義一致、Precision 優先）。
2. `_sentence_bound_anchor` 升級：同一句內**逐一枚舉**行為×錨點配對（原本只取第一個命中），配對支援 per-match 否定檢查與 veto 窗口。
3. 「攔阻 veto」是 12 字元前置窗口掃描——若你的法律程序重現句措辭在 veto 表之外，請提供句子，我再收緊。

### E5 驗證
- 第四輪四類重現例＋第三輪五例＋裁定①三例：全部清除為空或其他行為章
- 正例電池 22 句全召回（含新增「他攔阻員警的去路」「致使被害人不能抗拒而交付財物」制式句）
- pytest **391 passed ×2**（hash 自檢綠）；前端 **22/22**
- hash 鏈五節點：rules.py `255da715…` → packet `b77cf72e…` → hg01 `a9fd439f…` → hg02 → record target；frozen 10/10
- 凍結檔 diff **空**；零 commit

### 需你複審的 E5 勾選項
1. 「從未」群納入全域否定標記 → **✓**（六個標記逐一實測；keyword／hint／anchor／D1 四層均抑制命中）
2. 拒絕錨點指向接觸對象／句尾收束 → **✗**（指定句已清除，但裸 `拒絕過` 仍未綁接觸對象；「他騷擾同事，我拒絕過另一人的邀約。」仍回填 stalking）
3. 攔阻的法律程序 veto（12 字前置窗口） → **✗**（veto 表未涵蓋「聲請停止執行」；「員警執行職務時，我依法聲請停止執行，以攔阻該執行。」仍回填 obstruction）
4. 交付錨點綁定財物對象（hint／gate／D1 契約合一） → **✗**（三路確實共用常數，但 `使人(不能抗拒)?(而)?交付` 未綁財物；「他以脅迫方式使人交付報告。」於 hint／gate／D1 均成立並回填 robbery）
5. `_sentence_bound_anchor` 逐一配對升級 → **✗**（目前找到第一個未否定 act 後即 `break`，再獨立枚舉 anchor，未逐一枚舉 act×anchor 配對）

> **E5 輪複審結論（2026-10-20）：`EXACT_REPRO_PASS / GENERAL_GATE_FAIL`，`CHANGES_REQUESTED`。**
> 第四輪四類指定重現、第三輪五例與裁定①三例均維持清除；但上述三個新反例及
> 配對實作不符聲稱，故本輪僅第 1 項通過。完整 pytest 391 passed、前端 22/22，
> 但現有測試未涵蓋本輪新反例，不得據此升級為一般化契約通過。

---

## （歷史）E4 輪修訂（第三輪複審回饋之程式碼層修復；question_bank.json 仍零變更）

### 四項 ✗ 的根因與修法

| 審查項目 | 第三輪繞進路徑（你的重現例） | E4 修復 |
|---|---|---|
| E-2 stalking | 裸「無須再」／無關的「很害怕」或「保護令」放行（「公司通知我無須再填寫報告」） | 錨點改 **同句綁定**：行為語（跟蹤／騷擾／守候／聯絡／傳訊息…）與錨點必須在同一句（。；！？分行）且皆未落否定窗口；「無須再」限縮為「無須再(私下)聯繫／聯絡／傳／接觸／來」；裸「很害怕」移除；「保護令」須與行為同句 |
| E-3 obstruction | 裸「強制」放行（「機關安排強制休假，全程沒有衝突」） | 移除「強制」；錨點限物理強暴脅迫動作（推開／攔阻／毆打／強暴／脅迫…）**且**須與職務語句（公務員／執行職務／執勤／查封）同一句 |
| E-4 robbery | gate 清 keyword 後，phrase hint 繞回（「持刀喊著要搶奪，但最後沒有取走任何財物」→ robbery/keyword_hint） | 錨點閘門改套用**兩次**：keyword／structural 清除後，hint 命中必須再次通過同一錨點檢查；取財錨點抽為共用常數 `_ROBBERY_TAKE_ANCHOR`（lookbehind 擋「要／喊著要」的意向性搶奪） |
| E-5 related | `_property_discriminators()` 用裸 `re.search`，否定句把 robbery／embezzlement related 帶回 | 四訊號全部改走 `_patterns_unnegated`（14 字元否定窗口）；violence_take 之取財面共用 `_ROBBERY_TAKE_ANCHOR`。「沒有脅迫，也沒有搶走」／「沒有侵占，也沒有拒不返還」不再回填 related |

### 裁定①執行（REJECT → 已撤除豁免）
- `_bank_keyphrase_set` 與整句回顯豁免**全數刪除**，runtime 不再有任何關鍵字例外。
- 佈線測試（`tests/test_rules.py` 兩個 metadata 測試）改為「關鍵字＋最小事實敘述」探針
  （`_PROBE_NARRATIVE_SUFFIX`：四章各一句同句滿足錨點的敘述），不是回顯豁免。

### E4 驗證
- 你的五個重現例全部清除為空或僅剩其他行為章（見 record `third_fix_round.verification.repro_negatives`）
- 正例電池 23 句全召回（stalking 拒絕／畏怖／保護令／書類；obstruction 推開／攔阻／毆打／制式／查封；robbery 四型；embezzlement 四型）
- pytest **391 passed**（hash 自檢綠）；前端 **22/22**
- hash 鏈五節點刷新：rules.py `9e062b21…` → packet `90982f23…` → hg01 `f79f4aa1…` → hg02 → record target；frozen 10/10
- `question_bank.json`／crosswalk／`xlsm_questions.json` git diff **空**；零 commit

### E4 已知限制（明列）
- 同句綁定以 Precision 優先：跨句才出現錨點的正當敘述（行為句與意願句分離）可能不被召回。
- 「搶了」單詞取財仍不觸發（你已 ACCEPT，保留為已知召回損失）。
- 意向／完成取財混合句仍無法逐語分辨（你已 ACCEPT，但純否定回填缺陷已在 E4 修復）。

### 需你複審的 E4 勾選項
1. E-2 同句綁定＋「無須再」語境限縮 → **✗**（第三輪原例已清除；但「我從未騷擾她，她也從未明確拒絕」及同句不同主體「他騷擾同事，我明確拒絕另一人的邀約」仍回填 stalking）
2. E-3 移除「強制」＋同句職務綁定 → **✗**（第三輪原例已清除；但「從未攔阻或脅迫」未被否定窗口擋下，且法律程序「攔阻」仍被當成物理強暴脅迫）
3. E-4 雙重閘門（hint 亦套錨點）＋共用取財錨點 → **✗**（雙重閘門與共用常數已存在；但「從未脅迫／從未搶走」仍命中，裸「交付」亦可被無關的「不能抗拒」語境帶入 robbery）
4. E-5 四訊號否定感知（related 不回填） → **✗**（四訊號已改走 `_patterns_unnegated`；但共用否定詞表未涵蓋「從未」，實測 robbery／embezzlement 仍可回填）
5. 裁定①執行方式（測試探針改寫，非豁免） → **✓**（runtime 豁免已移除；`_PROBE_NARRATIVE_SUFFIX` 僅用於測試，三個既知 keyword-echo 洩漏例均未回填目標章）

> **E4 輪複審結論（2026-10-20）：CHANGES_REQUESTED。** 第三輪五個原始重現例為
> `EXACT_REPRO_PASS`，但一般化錨點／否定感知契約仍為 `GENERAL_GATE_FAIL`；
> 本輪本機驗證為 targeted pytest 61 passed、完整 pytest 391 passed、前端 22/22。

---

## （歷史）E3 輪修訂（第二輪複審回饋之程式碼層修復；question_bank.json 仍零變更）

### 根因與修法
四個 ✗ 的共同結構：**關鍵字／結構式 fallback 先建立候選 → hint 要件根本沒有機會把關**。
bank 凍結不能動 → 在程式碼層新增 candidate 組裝處的「構成要件最小錨點閘門」：

| 審查項目 | 原繞進路徑 | E3 修復 |
|---|---|---|
| E-2 stalking | bank kw `守候/反覆徘徊/騷擾/尾隨` 直建候選，無「違反其意願」事實也命中 | 閘門：須有拒絕／反對事實（拒絕／不要再／無須再／保護令）或畏怖反應，任一 |
| E-3 obstruction | kw `公務員` 直建候選；含 `妨害` 的 structural fallback 也放行 | 閘門：須有物理性強暴脅迫動作（推開／攔阻／毆打／強暴／脅迫／強制…） |
| E-4 robbery | hint pat2 接受裸財物名詞（`脅迫＋手機`→命中）；否定取財持刀句由 fallback 命中 | pat2 改為取財／使人交付動作（強搶／搶走／交出／交給／強取…）；閘門同構，「要／喊著要」引導的意向詞以 lookbehind 排除 |
| E-5 embezzlement | kw `代管/保管/拾得` 直建候選；已返還且明示未占為己有仍命中 | 閘門：須有變易持有事實（侵占／拒不返還／自行處分／占為己有／花用／轉自己帳戶／變賣…），否定窗口擋「沒有占為己有／沒有拒絕返還」 |

機制：`_ELEMENT_ANCHOR_GATES`（rules.py）＋ candidate loop 閘門，複用 `_patterns_unnegated`（14 字元否定窗口）；
錨點只回報「摘要是否含有對應區辨事實語句」，不判定任何法律要件成立，正式定性仍須 Gate 1／人工審查。

### 需你裁定的設計裁決（E3 新增）
- **關鍵字回顯豁免**：整句摘要完全等於單一已審查關鍵字（如查詢框輸入「妨害公務」）不套用閘門——無案情敘述可供區辨，維持既有行為供人工檢視。兩個 route-metadata 佈線測試依賴此語義。若你不同意，改法是替那些測試改用完整敘述。
- **C-13 corpus 期望值改空**：「住處門口反覆徘徊守候三小時」無違反意願／畏怖事實 → 依你的標準改 `expected_candidates=set()`（原文摘要未動）。
- **「無須再私下聯繫」納入反對事實錨點**：真實書類（real_cases 群組訊息案）以此表述違反意願事實。

### E3 回歸錨點更新
- `tests/test_candidate_phrase_hints.py`：`NEAR_MISS_CASES` 新增 8 句（本輪全部繞進重現例）
  ＋真實書類敘述正例 1 句（書類中的違反意願表述）。

### E3 驗證
- pytest **391 passed**（hint 12 全綠；corpus／real_cases／e2e／workflow 全綠；hash 鏈自檢綠）
- node `tests/test_frontend_api_errors.mjs` **22/22**
- hash 鏈五節點對等：rules.py `3e46456d…` → packet `c6511bf0…` → hg01 `731899df…` → hg02 → record target；frozen_files 10/10
- `question_bank.json`／`legal_route_crosswalk.json` git diff 為空

### E3 已知限制（明列，不隱藏）
- E-4：否定取財表述（「要／喊著要」「沒有取走…任何財物」）已排除；但同句混合其他肯定取財詞時無法逐一分辨（指示型意圖 vs. 已完成事實），錨點僅回報事實語句存在與否。
- 「錢包被搶了」此類僅「搶了」單詞取財之敘述，若無其他取財／交付動作詞仍不觸發（召回損失已知，依你的「取財動作必備」標準取 Precision 優先）。

---

## 你勾完後我做的事
1. 依勾選更新 `hg_rules_py_e2_correction_record.json` 的 `re_review` 欄（不改歷史欄位，另開 result 欄）。
2. 有 ✗ 項 → 重新探針 → 最小修正 → 回歸 → hash 鏈再刷新 → 留痕。

---
---
## （歷史）第一輪送審內容　（目標版本 sha256 `42f63e35…`）

> 背景：2026-10-20 人工審查 E 輪（`9bd6474d…`）結論 **CHANGES_REQUESTED**
> （E-1～E-6 全 ✗、D1 定案「B 修正版」三路區辨），記錄於
> `docs/evidence/hg_rules_py_e2_correction_record.json`。本檔為依該決策
> 修復後的審閱筆記，請對照以下各項再勾選一次（✓／✗）。
> question_bank.json 未動（git diff 驗證）；crosswalk 未動。

---

## 依審查決策逐項修復與對應法條

### E-1 intimidation hint（刑法 §305：通知加惡害之旨）
- **✗ 原因**：一般提醒（警衛「晚上小心一點、在門口值勤」）誤觸。
- **修正**：pattern 收緊為「惡害通知」具體清單（讓…好看｜不會放過…｜知道我(住|家)｜記得我(家|住)哪｜不告訴就傷害｜報警就…｜捅(你|死)｜砍(你|死)｜弄死你｜處理你）；**刪除**「小心一點／要你小心／會出事/很害怕／家門口／在門口／等在門口」等非惡害或一般提醒詞。
- 負例錨點：警衛句（空）✓；正例 V1/V2 與既有測試句召回不變 ✓。
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-2 stalking hint（跟騷法 §3：反覆或持續＋違反其意願）
- **✗ 原因**：「每天到公司等同事」誤觸。
- **修正**：新增第三必備 pattern＝違反意願事實（明確拒絕｜拒絕(過)?｜不要再(來|跟|找|聯絡)｜別再…｜叫我不要再｜早就拒絕）；接近＋頻率＋意願三者俱備才觸發。
- 負例錨點：同事相約吃飯句（空）✓；正例 V1/V2/V5 均含拒絕事實 ✓；既有測試句已補「我早已明確拒絕」（涉條文要求之區辨事實，變更已在上段明示）。
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-3 obstruction hint（刑法 §135 第 1 項：施強暴脅迫）
- **✗ 原因**：單純拒絕配合或辱罵（無強暴脅迫）誤觸。
- **修正**：pattern2 刪「阻止／拒絕配合／不配合／辱罵／妨害」，僅保留物理性強暴脅迫（推開｜攔阻｜撞開｜揮打｜毆打｜拉扯｜強暴｜脅迫）。
- 負例錨點：拍攝抱怨罵警察句（空）✓；正例（推開／攔阻兩句）不變 ✓。
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-4 robbery hint（刑法 §328：強暴脅迫等手段＋奪取或使人交付）
- **✗ 原因**：「威脅公開照片」無取財亦無使人交付，誤觸。
- **修正**：pattern1 改為手段／暴取出財動作（強暴｜脅迫｜持(刀|槍|械)｜菜刀｜兇器｜捅｜行兇｜捆綁｜勒住｜毆打｜搶走｜強搶|搶劫），**刪除**單獨「威脅／兇器外無取財」路徑；pattern2 改為取財／使人交付清單（現金…｜交出｜把…交/給）。
- 負例錨點：威脅公開照片句 → robbery（無）✓；正例（捅＋交出／菜刀＋交現金／搶走）不變 ✓。
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-5 embezzlement hint（刑法 §335：侵占自己持有之他人之物）
- **✗ 原因**：「會計說客戶不還欠款」無受託持有可能，誤觸。
- **修正**：pattern1 改為受託／持有關係清單（保管｜代管｜代收｜受託｜經手｜業務上｜公款｜拾得｜撿到），**刪除**職稱詞「出納／財務／會計」；pattern2 改為變易持有清單（拒不返還｜占為己有｜據為己有｜花用｜侵吞｜轉自己帳戶／名下），**刪除**泛「不還」；exclude 補「欠款｜借款｜貸款」。
- 負例錨點：客戶欠款句（空）✓；正例（店長保管／出納轉帳）不變 ✓。
- 判定：□ ✓　□ ✗（備註：＿＿）

### E-6 意圖元素訊號回退
- **✗ 原因**：訊號非純展示，會改變 supported_count、suggested route、ELIGIBLE_CANDIDATE。
- **修正**：`_element_evidence_patterns` 意圖訊號**回退**為僅 `("不法所有",)`（E 輪加的 花用／轉入自己帳戶／當作自己的／當成自己的／侵吞／據為己有 全部撤銷）。侵占意圖跡象由 E-5 hint（NEED_REVIEW 候選層）承擔。
- 判定：□ ✓　□ ✗（備註：＿＿）

---

## D1 實作（人工核定「B 修正版」：theft／embezzlement／robbery 三路區辨）

- **新增** `rules.py::_property_discriminators(summary)`：四個區辨事實訊號
  （consent_take／entrusted_possession／conversion／violence_take），只回報「摘要中
  是否存在對應區辨事實」，不判定要件成立，不改 candidate 狀態語義。
- **related 擴展閘門**（原無區辨的 `related_ids.update(PROPERTY_ROUTE_IDS…)` 移除）：
  條件＝財物事實存在（`_property_taking_values`）或財物罪章命中，且非引述主導；
  依訊號三路新增，**缺對應區辨事實不新增**，並撤銷 bank related 帶入的財物 id；
  `legal_route_crosswalk.json` 未動。
- 效果（探針）：
  | 場景 | D1 前 | D1 後 |
  |---|---|---|
  | 竊盜句（趁不注意拿走錢包） | theft＋embezzlement＋robbery | **theft 單章** |
  | 侵占句（保管／拒不返還；轉帳花用） | embezzlement＋robbery＋theft | **embezzlement 單章** |
  | 強盜句（捅＋交出＋搶走） | robbery＋embezzlement＋theft | robbery（＋intimidation 惡害通知候選） |
  | 引述句「他跟公司說我侵占公款」 | （護欄） | （護欄維持空） |

## 回歸錨點更新（皆人工核定行為變更，非靜默改test）
- `tests/test_rules.py`：兩處「theft 句需 ≥ {theft, embezzlement, robbery}」改為 `== {theft}`（D1）。
- `tests/test_workflow.py::test_gate1_summary_change…`：同上改 `== {"theft"}`。
- `app/legal_semantic_corpus.py`：A-01／A-02／A-06／C-09／C-17 的 `expected_related`
  由財物家族擴展值改為 `set()`（D1：缺區辨事實不新增）。
- `tests/test_question_logic.py::test_bidirectional_convergence_…codes`：fixture 摘要改為
  侵占敘述本體（原文依賴 family 污染選出 embezzlement）。
- `tests/test_candidate_phrase_hints.py`：stalking 正例補「我早已明確拒絕」（跟騷法 §3
  區辨事實）；**新增** `NEAR_MISS_CASES` ＋ `test_near_miss_statute_elements_do_not_create_…`
  （人工審查五反例，precision 錨點）；embezzlement／obstruction 正例各補一句。

## 驗證
- pytest **391 passed**（含 hash 鏈自檢）
- node `tests/test_frontend_api_errors.mjs` **22/22**
- hash 鏈五節點對等：packet `9939e7a2…`／hg01 `010a188a…`／hg02／record target `42f63e35…`；frozen_files 10/10

## 已知未決
- 「被害人發現店內物品遭取走」型摘要：D1 關閉污染路徑後，theft 第一手命中由
  structural rule 反向語序（財物…遭取走）承接，不再產生三路 family 污染。
- 外部語料逐字一致性仍 UNKNOWN（本輪未逐一重開 33 份原文）。

## 你勾完後我做的事
1. 依勾選更新 `hg_rules_py_e2_correction_record.json` 的 `re_review.status`（不改歷史欄位，另開 result 欄）。
2. 有 ✗ 項 → 重新探針 → 最小修正 → 回歸 → hash 鏈再刷新 → 留痕。
