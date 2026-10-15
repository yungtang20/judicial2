---
document_status: REVIEW_ONLY
runtime_enabled: false
loader_target: none
legal_completeness: NOT_CLAIMED
automated_guilt_determination: PROHIBITED
xlsm_written: false
source_verification_status: PARTIAL_VERIFIED_CURRENT_LAW_UPDATED
verification_date: 2026-10-12
last_content_review: 2026-10-12
last_structure_review: 2026-10-12
content_review_status: STRUCTURE_PASS_HUMAN_REVIEW_REQUIRED
review_notes: "藐視國會罪（第5章之一）路由至 C03；C04 僅對應第10章之一。C07、C08 分別標示第9章中的藏匿人犯與湮滅證據部分；C27、C28 就擄人勒贖的拘束與恐嚇事實交叉使用題組。以上僅為法源及問句路由索引，不代表完整構成要件、罪名成立或競合判斷，仍須核對行為時法並經人工審核。"
---

# 刑法分則與特別法：角色別罪章全部核心問句

> 本檔集中收錄全部問句，供逐題人工審核。本檔不構成法律意見，不代表任何罪名成立，也不得跳過承辦人、法源版本及個案程序審查後直接投入正式詢問。審核方法與驗證標準另見 `QUESTION_DESIGN_AND_USE.md`。

## 1. 使用邊界

- 本檔未連接 `questions/*.md` 載入器，也未寫入 `新套表.xlsm`。
- 本稿採「角色共通基底＋罪章差異題」。共通基底預定對應各角色工作表 A 欄，罪章差異題預定對應 B 欄起的罪章欄位。
- `APPLICABLE` 表示通常可使用，仍須依個案裁剪。
- `CONDITIONAL` 表示只有符合啟用條件時才使用。
- `NOT_APPLICABLE` 表示該角色不能直接回答，不得由其他人代答。
- 問句只蒐集可觀察事實。候選罪章、構成要件、競合、證據能力及程序適法性均保留人工判斷。
- 現行法查證不等同行為時法查證。事件日期早於修法時，應另查沿革及施行日期。
- 每題均應容許「不知道、不確定、不記得、不理解或依法拒絕回答」，不得據此自動作不利推論。

## 2. 角色共通基底（預定 A 欄）

### VICTIM_OR_AFFECTED（被害人、告訴人或直接受影響端）

- **RCQ-G-V-01** `[fact=identity_relation]`：請說明你與事件中各相關人的關係。
- **RCQ-G-V-02** `[fact=free_narrative]`：請用自己的話依時間順序說明你親身經歷的事情。
- **RCQ-G-V-03** `[fact=time]`：你最早在何時察覺事件發生？
- **RCQ-G-V-04** `[fact=location]`：事件發生在何處或哪一個通訊系統？
- **RCQ-G-V-05** `[fact=evidence_source]`：有哪些資料可以支持你剛才的說明？

### SUSPECT_OR_ACTOR（涉嫌人或行為人）

- **RCQ-G-S-01** `[fact=identity_relation]`：請說明你與事件中各相關人的關係。
- **RCQ-G-S-02** `[fact=own_conduct]`：請依時間順序說明你本人實際做過的事情。
- **RCQ-G-S-03** `[fact=decision_basis]`：你作成相關決定時依據哪些資訊？
- **RCQ-G-S-04** `[fact=authority]`：你當時具有何種職務、權限或授權？
- **RCQ-G-S-05** `[fact=evidence_source]`：有哪些資料可以支持你剛才的說明？

### WITNESS（證人、發現人或專業保管人）

- **RCQ-G-W-01** `[fact=identity_relation]`：請說明你與事件中各相關人的關係。
- **RCQ-G-W-02** `[fact=personal_knowledge]`：哪些內容是你親自看到、聽到或操作的？
- **RCQ-G-W-03** `[fact=hearsay_source]`：不是你親自見聞的內容，是由何人於何時告知？
- **RCQ-G-W-04** `[fact=observation_context]`：你當時從何處觀察或接觸事件？
- **RCQ-G-W-05** `[fact=evidence_source]`：你保有或知道哪些可供查證的資料？

## 3. 通用敏感提問防護

- `SENSITIVE` 類別應先確認安全、通譯、陪同及是否願意繼續，再開始實體問句。
- 先讓受詢問者自由敘述，再補問一個事實面向。已清楚且有紀錄的創傷細節不重複詢問。
- 不使用責難、羞辱、暗示同意或預設被害人應反抗的措辭。
- 兒少問句應使用符合年齡及理解能力的短句，並遵守專業詢問與陪同程序。
- 涉及影像、身體、性行為、遺體或控制手段時，只問辨識法律路由所需的最低限度內容。

## 4. 刑法分則（37 類）

### C01 國安與國交 `state-security`

- `category_id`: `C01-state-security`
- `source_module`: `criminal-code-ch01-03`
- `source_refs`: 中華民國刑法第1章至第3章
- `sensitivity`: `SENSITIVE_CONDITIONAL`（機密、外交或情報資料）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有可識別的受影響人、機關或資料管理端。
- **RCQ-C01-V-01** `[module=criminal-code-ch01-03] [fact=affected_interest]`：事件影響哪一項人員、機關、國防資料或對外權益？
- **RCQ-C01-V-02** `[module=criminal-code-ch01-03] [fact=security_classification]`：資料的保密等級由何機關以何文件確認？
- **RCQ-C01-V-03** `[module=criminal-code-ch01-03] [fact=foreign_request]`：是否有外國政府提出正式請求的紀錄？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C01-S-01** `[module=criminal-code-ch01-03] [fact=contact]`：你與哪些境內外人員或組織有聯繫？
- **RCQ-C01-S-02** `[module=criminal-code-ch01-03] [fact=material_handling]`：你曾取得、製作或交付哪些資料或物品？
- **RCQ-C01-S-03** `[module=criminal-code-ch01-03] [fact=knowledge]`：你當時如何理解該資料的性質或保密狀態？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人有親身見聞或負責資料、授權、收發管理。
- **RCQ-C01-W-01** `[module=criminal-code-ch01-03] [fact=observed_contact]`：你親自見到哪一次聯繫或交付？
- **RCQ-C01-W-02** `[module=criminal-code-ch01-03] [fact=custody]`：相關資料原由何人保管？
- **RCQ-C01-W-03** `[module=criminal-code-ch01-03] [fact=authority_record]`：你能確認哪些授權或保密紀錄？

### C02 瀆職 `duty`

- `category_id`: `C02-duty`
- `source_module`: `criminal-code-ch04`
- `source_refs`: 中華民國刑法第4章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有直接受影響人或職務所屬機關。
- **RCQ-C02-V-01** `[module=criminal-code-ch04] [fact=official_act]`：承辦公務原應如何處理？
- **RCQ-C02-V-02** `[module=criminal-code-ch04] [fact=requested_benefit]`：是否有人要求、收受或約定特定利益？
- **RCQ-C02-V-03** `[module=criminal-code-ch04] [fact=consequence]`：公務處理結果與原程序有何差異？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C02-S-01** `[module=criminal-code-ch04] [fact=official_authority]`：你在該公務中的法定職掌為何？
- **RCQ-C02-S-02** `[module=criminal-code-ch04] [fact=decision_process]`：你如何作成該次公務決定？
- **RCQ-C02-S-03** `[module=criminal-code-ch04] [fact=benefit_flow]`：你是否取得任何金錢、物品或其他利益？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人參與承辦、核決、交付或稽核。
- **RCQ-C02-W-01** `[module=criminal-code-ch04] [fact=normal_process]`：依你職務，該事項通常如何辦理？
- **RCQ-C02-W-02** `[module=criminal-code-ch04] [fact=observed_deviation]`：你親自發現哪一項程序差異？
- **RCQ-C02-W-03** `[module=criminal-code-ch04] [fact=record_location]`：原始公文或系統紀錄保存於何處？

### C03 妨害公務 `obstruction`

- `category_id`: `C03-obstruction`
- `source_module`: `criminal-code-ch05`
- `source_refs`: 中華民國刑法第5章及第5章之一（藐視國會罪）
- `sensitivity`: `NORMAL`
- `routing_note`: `RCQ-C03-*-04`、`RCQ-C03-*-05` 僅在刑法第141條之1被列為待人工審查候選法源，且已有立法院聽證或質詢程序的基礎資料時啟用；不得依回答自動認定受詢問者身分、陳述虛偽、主觀明知或犯罪成立。

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C03-V-01** `[module=criminal-code-ch05] [fact=official_duty]`：你當時正在執行何項職務？
- **RCQ-C03-V-02** `[module=criminal-code-ch05] [fact=interference]`：對方以何種具體言語或動作影響執行？
- **RCQ-C03-V-03** `[module=criminal-code-ch05] [fact=duty_identification]`：現場如何表明執行職務的身分或依據？
- **RCQ-C03-V-04** `[module=criminal-code-art141-1] [fact=legislative_proceeding]`：你當時參與的是哪一次立法院聽證或質詢程序？
- **RCQ-C03-V-05** `[module=criminal-code-art141-1] [fact=questioned_matter]`：你聽到主持人或委員詢問受詢問者什麼事項？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C03-S-01** `[module=criminal-code-ch05] [fact=perception]`：你當時如何辨識對方的身分？
- **RCQ-C03-S-02** `[module=criminal-code-ch05] [fact=own_words]`：你當時說了哪些話？
- **RCQ-C03-S-03** `[module=criminal-code-ch05] [fact=own_physical_act]`：你當時做了哪些肢體動作？
- **RCQ-C03-S-04** `[module=criminal-code-art141-1] [fact=statement_content]`：你在該次程序中陳述了什麼內容？
- **RCQ-C03-S-05** `[module=criminal-code-art141-1] [fact=knowledge_at_statement]`：你作成該陳述時，知道哪些與受詢問事項有關的事實？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C03-W-01** `[module=criminal-code-ch05] [fact=official_activity]`：你看到公務員當時正在做什麼？
- **RCQ-C03-W-02** `[module=criminal-code-ch05] [fact=observed_words]`：你親自聽到哪些言語？
- **RCQ-C03-W-03** `[module=criminal-code-ch05] [fact=observed_physical_act]`：你親自看到哪些肢體動作？
- **RCQ-C03-W-04** `[module=criminal-code-art141-1] [fact=heard_statement]`：你親耳聽到受詢問者陳述了什麼內容？
- **RCQ-C03-W-05** `[module=criminal-code-art141-1] [fact=statement_record]`：有哪些紀錄可以核對你親耳聽到的陳述？

### C04 妨害司法公正 `judicial-integrity`

- `category_id`: `C04-judicial-integrity`
- `source_module`: `criminal-code-judicial-integrity`
- `source_refs`: 中華民國刑法第10章之一（妨害司法公正罪）
- `sensitivity`: `SENSITIVE_CONDITIONAL`（偵查不公開、證人安全）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有受干預的證人、鑑定人、司法程序參與人或機關。
- **RCQ-C04-V-01** `[module=criminal-code-judicial-integrity] [fact=proceeding]`：受影響的是哪一個案件或司法程序？
- **RCQ-C04-V-02** `[module=criminal-code-judicial-integrity] [fact=contact_content]`：對方就陳述、作證或鑑定提出何種要求？
- **RCQ-C04-V-03** `[module=criminal-code-judicial-integrity] [fact=influence_method]`：對方以何種方式試圖影響你的決定？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C04-S-01** `[module=criminal-code-judicial-integrity] [fact=contact]`：你曾與哪些程序參與人聯繫？
- **RCQ-C04-S-02** `[module=criminal-code-judicial-integrity] [fact=communication]`：你在聯繫中表達了哪些內容？
- **RCQ-C04-S-03** `[module=criminal-code-judicial-integrity] [fact=benefit_or_pressure]`：你是否提出利益、要求或壓力？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人親自見聞接觸、轉達或利益交付。
- **RCQ-C04-W-01** `[module=criminal-code-judicial-integrity] [fact=observed_contact]`：你親自見到哪一次聯繫？
- **RCQ-C04-W-02** `[module=criminal-code-judicial-integrity] [fact=observed_content]`：你親自聽到哪些要求或回應？
- **RCQ-C04-W-03** `[module=criminal-code-judicial-integrity] [fact=record]`：你知道哪些通聯、會面或交付紀錄？

### C05 妨害投票 `voting`

- `category_id`: `C05-voting`
- `source_module`: `criminal-code-ch06`
- `source_refs`: 中華民國刑法第6章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有受影響選舉人、候選人或選務機關。
- **RCQ-C05-V-01** `[module=criminal-code-ch06] [fact=voting_right]`：你原本可以如何行使投票或選舉權？
- **RCQ-C05-V-02** `[module=criminal-code-ch06] [fact=influence_method]`：他人以何種方式影響你的選擇或投票行動？
- **RCQ-C05-V-03** `[module=criminal-code-ch06] [fact=benefit]`：是否有人提出金錢、物品或其他利益？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C05-S-01** `[module=criminal-code-ch06] [fact=contact_group]`：你曾接觸哪些選舉人或選務人員？
- **RCQ-C05-S-02** `[module=criminal-code-ch06] [fact=proposal]`：你曾提出哪些要求或條件？
- **RCQ-C05-S-03** `[module=criminal-code-ch06] [fact=fund_source]`：相關金錢或物品由何處取得？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人親自見聞要求、交付或選務異常。
- **RCQ-C05-W-01** `[module=criminal-code-ch06] [fact=observed_proposal]`：你親自聽到何種投票相關要求？
- **RCQ-C05-W-02** `[module=criminal-code-ch06] [fact=observed_delivery]`：你親自看到何種物品或金錢交付？
- **RCQ-C05-W-03** `[module=criminal-code-ch06] [fact=election_record]`：你知道哪些名冊、票券或監視紀錄可供查證？

### C06 妨害秩序 `disorder`

- `category_id`: `C06-disorder`
- `source_module`: `criminal-code-ch07`
- `source_refs`: 中華民國刑法第7章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有直接受威脅、妨害或管理公共場所的人員。
- **RCQ-C06-V-01** `[module=criminal-code-ch07] [fact=gathering]`：現場聚集的人數與分布情形為何？
- **RCQ-C06-V-02** `[module=criminal-code-ch07] [fact=conduct]`：你看到哪些具體言語或動作？
- **RCQ-C06-V-03** `[module=criminal-code-ch07] [fact=public_effect]`：現場通行、營業或公共活動受到何種影響？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C06-S-01** `[module=criminal-code-ch07] [fact=participation]`：你如何到達並參與現場活動？
- **RCQ-C06-S-02** `[module=criminal-code-ch07] [fact=coordination]`：你是否與他人討論現場分工？
- **RCQ-C06-S-03** `[module=criminal-code-ch07] [fact=own_conduct]`：你在現場做了哪些具體動作？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C06-W-01** `[module=criminal-code-ch07] [fact=crowd_observation]`：你從何處觀察現場人群？
- **RCQ-C06-W-02** `[module=criminal-code-ch07] [fact=actor_identification]`：你如何辨識各具體行為的人？
- **RCQ-C06-W-03** `[module=criminal-code-ch07] [fact=public_effect]`：你親自看到公共活動受到何種影響？

### C07 脫逃藏匿 `escape-concealment`

- `category_id`: `C07-escape-concealment`
- `source_module`: `criminal-code-ch08-09`
- `source_refs`: 中華民國刑法第8章（脫逃罪）及第9章（藏匿人犯罪部分）
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 由羈押、拘提、執行或追緝機關的承辦人回答。
- **RCQ-C07-V-01** `[module=criminal-code-ch08-09] [fact=legal_custody]`：當事人當時受何種合法拘束？
- **RCQ-C07-V-02** `[module=criminal-code-ch08-09] [fact=escape_method]`：拘束狀態如何被中斷？
- **RCQ-C07-V-03** `[module=criminal-code-ch08-09] [fact=search_action]`：機關何時開始追查或搜尋？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C07-S-01** `[module=criminal-code-ch08-09] [fact=custody_awareness]`：你如何理解當時受到的拘束或執行狀態？
- **RCQ-C07-S-02** `[module=criminal-code-ch08-09] [fact=departure]`：你以何種方式離開原處所？
- **RCQ-C07-S-03** `[module=criminal-code-ch08-09] [fact=assistance]`：離開或藏匿期間有哪些人提供協助？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人負責看守、運送、處所管理或親自見到協助行為。
- **RCQ-C07-W-01** `[module=criminal-code-ch08-09] [fact=custody_condition]`：你親自確認的拘束狀態為何？
- **RCQ-C07-W-02** `[module=criminal-code-ch08-09] [fact=observed_departure]`：你看到當事人如何離開？
- **RCQ-C07-W-03** `[module=criminal-code-ch08-09] [fact=observed_assistance]`：你看到何人提供何種協助？

### C08 湮滅證據 `evidence-destruction`

- `category_id`: `C08-evidence-destruction`
- `source_module`: `criminal-code-evidence-destruction`
- `source_refs`: 中華民國刑法第9章（湮滅證據罪部分）
- `sensitivity`: `SENSITIVE_CONDITIONAL`（偵查不公開）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 原證據持有人、案件承辦機關或直接受影響當事人可確認證據原狀。
- **RCQ-C08-V-01** `[module=criminal-code-evidence-destruction] [fact=evidence_identity]`：涉及哪一項刑事案件的何種證據？
- **RCQ-C08-V-02** `[module=criminal-code-evidence-destruction] [fact=original_state]`：該證據原本的內容或狀態如何？
- **RCQ-C08-V-03** `[module=criminal-code-evidence-destruction] [fact=change]`：何時發現證據滅失、變更或隱匿？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C08-S-01** `[module=criminal-code-evidence-destruction] [fact=access]`：你如何接觸到該證據？
- **RCQ-C08-S-02** `[module=criminal-code-evidence-destruction] [fact=handling]`：你對該證據做了哪些處理？
- **RCQ-C08-S-03** `[module=criminal-code-evidence-destruction] [fact=case_knowledge]`：你何時知道該證據與刑事案件有關？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見過原證據、保管流程或變更過程。
- **RCQ-C08-W-01** `[module=criminal-code-evidence-destruction] [fact=original_state]`：你最後一次看到證據原狀是在何時？
- **RCQ-C08-W-02** `[module=criminal-code-evidence-destruction] [fact=custody_chain]`：你知道哪些人曾經保管或接觸證據？
- **RCQ-C08-W-03** `[module=criminal-code-evidence-destruction] [fact=observed_change]`：你親自看到何種處理或變更？

### C09 偽證誣告 `perjury-false-accusation`

- `category_id`: `C09-perjury-false-accusation`
- `source_module`: `criminal-code-ch10`
- `source_refs`: 中華民國刑法第10章
- `sensitivity`: `SENSITIVE_CONDITIONAL`（司法程序、證人安全）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有遭指述者或受影響司法程序。
- **RCQ-C09-V-01** `[module=criminal-code-ch10] [fact=statement_context]`：相關陳述是在何種法定程序中作成？
- **RCQ-C09-V-02** `[module=criminal-code-ch10] [fact=disputed_statement]`：你認為需要查證的是哪一段具體陳述？
- **RCQ-C09-V-03** `[module=criminal-code-ch10] [fact=contrary_material]`：有哪些客觀資料與該陳述不一致？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C09-S-01** `[module=criminal-code-ch10] [fact=statement_source]`：你作成該陳述時依據哪些親身見聞或資料？
- **RCQ-C09-S-02** `[module=criminal-code-ch10] [fact=oath_or_warning]`：作成陳述前，你接受了哪些具結或程序告知？
- **RCQ-C09-S-03** `[module=criminal-code-ch10] [fact=uncertainty]`：哪些內容是你當時不能確定的？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人能確認程序、原始陳述或相反事實。
- **RCQ-C09-W-01** `[module=criminal-code-ch10] [fact=procedure]`：你親自參與哪一次陳述或具結程序？
- **RCQ-C09-W-02** `[module=criminal-code-ch10] [fact=exact_statement]`：你能確認的原始陳述內容為何？
- **RCQ-C09-W-03** `[module=criminal-code-ch10] [fact=personal_knowledge]`：你親自知道哪些與陳述不同的事實？

### C10 公共危險（含酒駕） `public-danger`

- `category_id`: `C10-public-danger`
- `source_module`: `criminal-code-ch11`
- `source_refs`: 中華民國刑法第11章
- `sensitivity`: `SENSITIVE_CONDITIONAL`（重大傷亡）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有直接受影響人、場所管理人、交通工具管理人或公眾安全主管端。
- **RCQ-C10-V-01** `[module=criminal-code-ch11] [fact=danger_source]`：最早發現的具體危險來源為何？
- **RCQ-C10-V-02** `[module=criminal-code-ch11] [fact=exposure_scope]`：哪些人、場所或交通工具進入危險範圍？
- **RCQ-C10-V-03** `[module=criminal-code-ch11] [fact=driving_observation]`：如涉及駕駛，你觀察到何種行車或操作狀況？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C10-S-01** `[module=criminal-code-ch11] [fact=operation]`：你對危險來源、設備或交通工具做了哪些操作？
- **RCQ-C10-S-02** `[module=criminal-code-ch11] [fact=risk_knowledge]`：操作前你已知哪些現場狀況？
- **RCQ-C10-S-03** `[module=criminal-code-ch11] [fact=substance_timeline]`：如涉及酒精或藥物，請說明使用時間及種類。

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人親自見聞危險形成、設備操作、飲用或駕駛狀況。
- **RCQ-C10-W-01** `[module=criminal-code-ch11] [fact=hazard_observation]`：你最早看到何種危險徵象？
- **RCQ-C10-W-02** `[module=criminal-code-ch11] [fact=actor_operation]`：你看到何人進行何種操作？
- **RCQ-C10-W-03** `[module=criminal-code-ch11] [fact=driving_or_consumption]`：如涉及酒駕，你親自看到哪些飲用或駕駛事實？

### C11 偽造貨幣 `currency`

- `category_id`: `C11-currency`
- `source_module`: `criminal-code-ch12`
- `source_refs`: 中華民國刑法第12章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 收受人、金融機構或貨幣管理端可確認票券來源與狀態。
- **RCQ-C11-V-01** `[module=criminal-code-ch12] [fact=currency_identity]`：涉及何種幣別、面額或票券？
- **RCQ-C11-V-02** `[module=criminal-code-ch12] [fact=receipt]`：你以何種交易或方式取得該貨幣？
- **RCQ-C11-V-03** `[module=criminal-code-ch12] [fact=authenticity_notice]`：你何時因何原因察覺真偽有疑？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C11-S-01** `[module=criminal-code-ch12] [fact=acquisition]`：你從何處取得該貨幣或製作材料？
- **RCQ-C11-S-02** `[module=criminal-code-ch12] [fact=handling]`：你對該貨幣做過哪些製作、變造或交付行為？
- **RCQ-C11-S-03** `[module=criminal-code-ch12] [fact=knowledge]`：你在何時開始懷疑或知道該貨幣的真偽？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到製作、交付、收受或負責鑑驗。
- **RCQ-C11-W-01** `[module=criminal-code-ch12] [fact=observed_transfer]`：你親自看到哪一次貨幣交付？
- **RCQ-C11-W-02** `[module=criminal-code-ch12] [fact=observed_production]`：你親自看到哪些製作或加工行為？
- **RCQ-C11-W-03** `[module=criminal-code-ch12] [fact=examination]`：鑑驗使用何種比對方式並得出何種結果？

### C12 有價證券 `securities`

- `category_id`: `C12-securities`
- `source_module`: `criminal-code-ch13`
- `source_refs`: 中華民國刑法第13章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 權利人、持有人、付款人或發行機構。
- **RCQ-C12-V-01** `[module=criminal-code-ch13] [fact=instrument_identity]`：涉及何種票據、股票或其他權利憑證？
- **RCQ-C12-V-02** `[module=criminal-code-ch13] [fact=right_holder]`：憑證所表彰的權利原屬何人？
- **RCQ-C12-V-03** `[module=criminal-code-ch13] [fact=use]`：該憑證曾被提示、交付或行使於何處？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C12-S-01** `[module=criminal-code-ch13] [fact=acquisition]`：你如何取得該憑證或其電子資料？
- **RCQ-C12-S-02** `[module=criminal-code-ch13] [fact=alteration]`：你曾對憑證的哪些欄位或內容進行處理？
- **RCQ-C12-S-03** `[module=criminal-code-ch13] [fact=purpose_of_use]`：你將該憑證交付或提示給何人？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人負責發行、簽發、付款、交割或鑑驗。
- **RCQ-C12-W-01** `[module=criminal-code-ch13] [fact=issuance_record]`：發行或簽發紀錄如何記載該憑證？
- **RCQ-C12-W-02** `[module=criminal-code-ch13] [fact=signature_authority]`：相關簽名或用印由誰有權作成？
- **RCQ-C12-W-03** `[module=criminal-code-ch13] [fact=transaction_record]`：提示、付款或移轉紀錄保存於何處？

### C13 度量衡 `weights-measures`

- `category_id`: `C13-weights-measures`
- `source_module`: `criminal-code-ch14`
- `source_refs`: 中華民國刑法第14章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 交易相對人、檢定機關或設備所有人。
- **RCQ-C13-V-01** `[module=criminal-code-ch14] [fact=device_identity]`：交易使用何種度量衡器具？
- **RCQ-C13-V-02** `[module=criminal-code-ch14] [fact=measurement_result]`：器具顯示的數值與實際數值有何差異？
- **RCQ-C13-V-03** `[module=criminal-code-ch14] [fact=transaction_use]`：該器具曾用於哪些交易或計價？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C13-S-01** `[module=criminal-code-ch14] [fact=device_control]`：你如何取得或管理該器具？
- **RCQ-C13-S-02** `[module=criminal-code-ch14] [fact=adjustment]`：你曾對器具做過哪些設定、修理或調整？
- **RCQ-C13-S-03** `[module=criminal-code-ch14] [fact=calibration_knowledge]`：你何時知道器具的檢定或誤差狀態？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到使用、調整或執行檢定。
- **RCQ-C13-W-01** `[module=criminal-code-ch14] [fact=observed_use]`：你親自看到器具如何被使用？
- **RCQ-C13-W-02** `[module=criminal-code-ch14] [fact=observed_adjustment]`：你親自看到何人調整器具？
- **RCQ-C13-W-03** `[module=criminal-code-ch14] [fact=calibration]`：檢定的日期、方法與結果為何？

### C14 文書 `forgery`

- `category_id`: `C14-forgery`
- `source_module`: `criminal-code-ch15`
- `source_refs`: 中華民國刑法第15章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C14-V-01** `[module=criminal-code-ch15] [fact=document_identity]`：涉及哪一份文書、印文或電子紀錄？
- **RCQ-C14-V-02** `[module=criminal-code-ch15] [fact=authorship_authority]`：依法或依內部規則，誰有權製作或簽署？
- **RCQ-C14-V-03** `[module=criminal-code-ch15] [fact=use_effect]`：該文書被提出後，哪項權利或程序受到影響？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C14-S-01** `[module=criminal-code-ch15] [fact=creation]`：你參與製作該文書的哪一部分？
- **RCQ-C14-S-02** `[module=criminal-code-ch15] [fact=authority]`：你製作、簽署或用印的授權來源為何？
- **RCQ-C14-S-03** `[module=criminal-code-ch15] [fact=use]`：你曾向何人或何機關提出該文書？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到製作、簽署、用印、提出或負責系統紀錄。
- **RCQ-C14-W-01** `[module=criminal-code-ch15] [fact=observed_creation]`：你親自看到誰製作或簽署文書？
- **RCQ-C14-W-02** `[module=criminal-code-ch15] [fact=normal_process]`：正常製作文書的權限與流程為何？
- **RCQ-C14-W-03** `[module=criminal-code-ch15] [fact=system_trace]`：系統或收發紀錄如何記載該文書？

### C15 妨害性自主 `sexual-autonomy`

- `category_id`: `C15-sexual-autonomy`
- `source_module`: `criminal-code-ch16`
- `source_refs`: 中華民國刑法第16章
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C15-V-01** `[module=criminal-code-ch16] [fact=free_narrative]`：請在你願意的範圍內，用自己的話說明對方做了什麼。
- **RCQ-C15-V-02** `[module=criminal-code-ch16] [fact=expressed_will]`：當時你如何表達自己的意願或不願意？
- **RCQ-C15-V-03** `[module=criminal-code-ch16] [fact=capacity_context]`：當時有沒有什麼狀況影響你理解或表達自己的意思？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C15-S-01** `[module=criminal-code-ch16] [fact=own_conduct]`：請分別說明你本人所做的身體接觸或性行為。
- **RCQ-C15-S-02** `[module=criminal-code-ch16] [fact=communication]`：行為前及行為中，雙方各自表達了哪些內容？
- **RCQ-C15-S-03** `[module=criminal-code-ch16] [fact=power_or_control]`：當時你對對方是否具有照護、監督或其他影響關係？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人有親身見聞、第一時間接觸或專業紀錄。
- **RCQ-C15-W-01** `[module=criminal-code-ch16] [fact=personal_observation]`：你親自看到或聽到哪些行為或言語？
- **RCQ-C15-W-02** `[module=criminal-code-ch16] [fact=first_disclosure]`：當事人第一次向你說明時使用了哪些原話？
- **RCQ-C15-W-03** `[module=criminal-code-ch16] [fact=record_creation]`：你在何時依何種專業程序製作紀錄？

### C16 妨害風化 `obscenity`

- `category_id`: `C16-obscenity`
- `source_module`: `criminal-code-ch16-1`
- `source_refs`: 中華民國刑法第16章之1
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有受招募、媒介、控制或直接影響之人。
- **RCQ-C16-V-01** `[module=criminal-code-ch16-1] [fact=recruitment]`：對方如何向你提出工作、交易或活動安排？
- **RCQ-C16-V-02** `[module=criminal-code-ch16-1] [fact=control_method]`：是否有人限制你停止、離開或拒絕？
- **RCQ-C16-V-03** `[module=criminal-code-ch16-1] [fact=benefit_flow]`：相關金錢或利益如何約定及分配？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C16-S-01** `[module=criminal-code-ch16-1] [fact=arrangement]`：你在招募、媒介、容留或場所管理中負責何事？
- **RCQ-C16-S-02** `[module=criminal-code-ch16-1] [fact=benefit]`：你取得何種報酬或利益？
- **RCQ-C16-S-03** `[module=criminal-code-ch16-1] [fact=content_distribution]`：如涉及物品或內容，你如何製作、持有或散布？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到招募、媒介、場所運作、交易或散布。
- **RCQ-C16-W-01** `[module=criminal-code-ch16-1] [fact=observed_arrangement]`：你親自看到何人安排哪些活動？
- **RCQ-C16-W-02** `[module=criminal-code-ch16-1] [fact=observed_payment]`：你親自看到哪一次金錢或利益交付？
- **RCQ-C16-W-03** `[module=criminal-code-ch16-1] [fact=venue_operation]`：你能確認場所或平台如何運作？

### C17 妨害婚姻家庭 `marriage-family`

- `category_id`: `C17-marriage-family`
- `source_module`: `criminal-code-ch17`
- `source_refs`: 中華民國刑法第17章
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C17-V-01** `[module=criminal-code-ch17] [fact=legal_relationship]`：事件發生時，各方的婚姻或家庭關係為何？
- **RCQ-C17-V-02** `[module=criminal-code-ch17] [fact=conduct]`：對方實際做了哪些與婚姻或家庭關係有關的行為？
- **RCQ-C17-V-03** `[module=criminal-code-ch17] [fact=knowledge_notice]`：你何時以何種方式知悉該行為？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C17-S-01** `[module=criminal-code-ch17] [fact=relationship_knowledge]`：你當時如何理解各方的婚姻或家庭關係？
- **RCQ-C17-S-02** `[module=criminal-code-ch17] [fact=own_conduct]`：你本人實際做了哪些相關行為？
- **RCQ-C17-S-03** `[module=criminal-code-ch17] [fact=document_basis]`：你依據哪些戶籍、婚姻或身分資料？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人親自見聞行為或負責身分登記。
- **RCQ-C17-W-01** `[module=criminal-code-ch17] [fact=relationship_basis]`：你如何得知各方的婚姻或家庭關係？
- **RCQ-C17-W-02** `[module=criminal-code-ch17] [fact=observed_conduct]`：你親自看到哪些相關行為？
- **RCQ-C17-W-03** `[module=criminal-code-ch17] [fact=registration]`：相關登記或證明文件如何記載？

### C18 褻瀆祀典墳墓 `graves-religion`

- `category_id`: `C18-graves-religion`
- `source_module`: `criminal-code-ch18`
- `source_refs`: 中華民國刑法第18章
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 家屬、宗教團體或場所管理人能說明原狀與管理權限。
- **RCQ-C18-V-01** `[module=criminal-code-ch18] [fact=site_or_object]`：事件涉及哪一處宗教場所、墳墓或遺體相關物？
- **RCQ-C18-V-02** `[module=criminal-code-ch18] [fact=original_state]`：事件前的位置、外觀或完整狀態如何？
- **RCQ-C18-V-03** `[module=criminal-code-ch18] [fact=authorization]`：哪些人有權同意開啟、移動或處理？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C18-S-01** `[module=criminal-code-ch18] [fact=purpose_at_site]`：你前往或進入該處的原因為何？
- **RCQ-C18-S-02** `[module=criminal-code-ch18] [fact=handling]`：你接觸、移動或處理哪些物品？
- **RCQ-C18-S-03** `[module=criminal-code-ch18] [fact=authorization]`：你認為自己取得何種同意或授權？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到行為、發現現場或負責管理與鑑識。
- **RCQ-C18-W-01** `[module=criminal-code-ch18] [fact=observed_conduct]`：你親自看到哪些言語或動作？
- **RCQ-C18-W-02** `[module=criminal-code-ch18] [fact=discovery_state]`：你第一次發現現場時的狀態如何？
- **RCQ-C18-W-03** `[module=criminal-code-ch18] [fact=management_record]`：墓籍、管理或修復紀錄如何記載？

### C19 妨害農工商 `agriculture-commerce`

- `category_id`: `C19-agriculture-commerce`
- `source_module`: `criminal-code-ch19`
- `source_refs`: 中華民國刑法第19章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 交易相對人、商標權人、農事水利使用人或主管機關。
- **RCQ-C19-V-01** `[module=criminal-code-ch19] [fact=goods_identity]`：涉及何種商品、農工必需品、商標或標示？
- **RCQ-C19-V-02** `[module=criminal-code-ch19] [fact=market_or_supply_change]`：供應、價格或用水狀態發生何種變化？
- **RCQ-C19-V-03** `[module=criminal-code-ch19] [fact=representation]`：商品對外標示的產地或品質為何？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C19-S-01** `[module=criminal-code-ch19] [fact=business_role]`：你在採購、庫存、定價、標示或銷售中負責何事？
- **RCQ-C19-S-02** `[module=criminal-code-ch19] [fact=decision_basis]`：你作成停止銷售、標示或供應決定時依據哪些資料？
- **RCQ-C19-S-03** `[module=criminal-code-ch19] [fact=source_document]`：產地、品質或權利資料由何處取得？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人參與交易、供應、標示、檢驗或行政公告。
- **RCQ-C19-W-01** `[module=criminal-code-ch19] [fact=inventory_or_supply]`：你能確認哪些庫存、供應或用水變化？
- **RCQ-C19-W-02** `[module=criminal-code-ch19] [fact=labeling]`：你親自看到何人製作或使用標示？
- **RCQ-C19-W-03** `[module=criminal-code-ch19] [fact=inspection]`：檢驗、公告或登記資料如何記載？

### C20 鴉片 `opium`

- `category_id`: `C20-opium`
- `source_module`: `criminal-code-ch20`
- `source_refs`: 中華民國刑法第20章；另與毒品危害防制條例分流
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有直接受影響人、場所所有人或查緝保管端。
- **RCQ-C20-V-01** `[module=criminal-code-ch20] [fact=item_identity]`：查獲物、種子、器具或設備的外觀與數量為何？
- **RCQ-C20-V-02** `[module=criminal-code-ch20] [fact=item_source]`：物品在何處被發現或取得？
- **RCQ-C20-V-03** `[module=criminal-code-ch20] [fact=examination]`：送驗品項與鑑驗結果為何？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C20-S-01** `[module=criminal-code-ch20] [fact=possession_relation]`：你與物品、場所或設備有何關係？
- **RCQ-C20-S-02** `[module=criminal-code-ch20] [fact=handling]`：你實際進行哪些製造、運送、交付或使用行為？
- **RCQ-C20-S-03** `[module=criminal-code-ch20] [fact=substance_knowledge]`：你當時如何理解物品的成分或用途？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到物品處理、場所使用或負責搜索、扣押、鑑驗。
- **RCQ-C20-W-01** `[module=criminal-code-ch20] [fact=observed_handling]`：你親自看到何人如何處理物品？
- **RCQ-C20-W-02** `[module=criminal-code-ch20] [fact=venue_use]`：你能確認場所如何被使用？
- **RCQ-C20-W-03** `[module=criminal-code-ch20] [fact=custody_chain]`：扣押物的保管與送驗流程為何？

### C21 賭博 `gambling`

- `category_id`: `C21-gambling`
- `source_module`: `criminal-code-ch21`
- `source_refs`: 中華民國刑法第21章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 場所所有人、財物權利人或主管機關可說明直接影響。
- **RCQ-C21-V-01** `[module=criminal-code-ch21] [fact=gambling_method]`：現場或平台以何種方式決定輸贏？
- **RCQ-C21-V-02** `[module=criminal-code-ch21] [fact=stake]`：參與者交付何種金錢、財物或利益？
- **RCQ-C21-V-03** `[module=criminal-code-ch21] [fact=venue_access]`：哪些人可以進入場所或使用平台？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C21-S-01** `[module=criminal-code-ch21] [fact=role]`：你在下注、收注、抽成或場所管理中負責何事？
- **RCQ-C21-S-02** `[module=criminal-code-ch21] [fact=money_flow]`：賭資、籌碼或款項如何收付？
- **RCQ-C21-S-03** `[module=criminal-code-ch21] [fact=equipment_control]`：相關設備、帳號或場地由誰控制？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到下注、收付、抽成或場所運作。
- **RCQ-C21-W-01** `[module=criminal-code-ch21] [fact=observed_game]`：你親自看到何種決定輸贏的活動？
- **RCQ-C21-W-02** `[module=criminal-code-ch21] [fact=observed_payment]`：你親自看到何種金錢或籌碼交付？
- **RCQ-C21-W-03** `[module=criminal-code-ch21] [fact=operator]`：你如何辨識管理或抽成的人？

### C22 殺人 `homicide`

- `category_id`: `C22-homicide`
- `source_module`: `criminal-code-homicide`
- `source_refs`: 中華民國刑法第22章殺人相關規定
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 僅限未遂案件的直接被害人，且其身心狀態足以陳述。既遂案件的死者無法回答，不得由家屬或他人代答；被害事實改由 WITNESS（例如法醫、現場處理人員）及客觀證據確認。
- **RCQ-C22-V-01** `[module=criminal-code-homicide] [fact=assault_conduct]`：如你能回答，對方對你做了哪些具體行為？
- **RCQ-C22-V-02** `[module=criminal-code-homicide] [fact=means]`：行為中使用了何種物品或方式？
- **RCQ-C22-V-03** `[module=criminal-code-homicide] [fact=medical_result]`：你接受何種急救或醫療處置？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C22-S-01** `[module=criminal-code-homicide] [fact=own_conduct]`：你對對方做了哪些具體動作？
- **RCQ-C22-S-02** `[module=criminal-code-homicide] [fact=means]`：你如何取得並使用相關物品？
- **RCQ-C22-S-03** `[module=criminal-code-homicide] [fact=post_event_action]`：事件後你採取了哪些救助或離開現場的行動？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C22-W-01** `[module=criminal-code-homicide] [fact=observed_conduct]`：你親自看到哪些攻擊或救助行為？
- **RCQ-C22-W-02** `[module=criminal-code-homicide] [fact=sequence]`：你看到的行為順序為何？
- **RCQ-C22-W-03** `[module=criminal-code-homicide] [fact=condition]`：你第一次接觸被害人時，其可觀察狀態如何？

### C23 殺嬰 `infanticide`

- `category_id`: `C23-infanticide`
- `source_module`: `criminal-code-infanticide`
- `source_refs`: 中華民國刑法第22章殺嬰相關規定
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `NOT_APPLICABLE`
- `reason`: 嬰兒不能直接回答本題組，不得由他人代答。
- `alternative_evidence`: 由醫療、照護、現場、出生及死亡相關紀錄，配合證人區塊確認。

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C23-S-01** `[module=criminal-code-infanticide] [fact=birth_timeline]`：請說明分娩開始至事件發生的時間順序。
- **RCQ-C23-S-02** `[module=criminal-code-infanticide] [fact=own_conduct]`：你對嬰兒實際做了哪些處置？
- **RCQ-C23-S-03** `[module=criminal-code-infanticide] [fact=physiological_context]`：當時有哪些身體或醫療狀況影響你的行動？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C23-W-01** `[module=criminal-code-infanticide] [fact=birth_observation]`：你親自看到哪些分娩或出生情形？
- **RCQ-C23-W-02** `[module=criminal-code-infanticide] [fact=infant_condition]`：你第一次接觸嬰兒時，其可觀察狀態如何？
- **RCQ-C23-W-03** `[module=criminal-code-infanticide] [fact=care_action]`：你看到何人採取何種照護或救助？

### C24 傷害 `injury`

- `category_id`: `C24-injury`
- `source_module`: `criminal-code-ch23`
- `source_refs`: 中華民國刑法第23章
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C24-V-01** `[module=criminal-code-ch23] [fact=assault_conduct]`：對方以何種具體動作接觸你的身體？
- **RCQ-C24-V-02** `[module=criminal-code-ch23] [fact=body_effect]`：你身體出現哪些可描述的不適或變化？
- **RCQ-C24-V-03** `[module=criminal-code-ch23] [fact=medical_care]`：你接受了何種檢查或治療？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C24-S-01** `[module=criminal-code-ch23] [fact=own_conduct]`：你與對方發生哪些身體接觸？
- **RCQ-C24-S-02** `[module=criminal-code-ch23] [fact=means]`：你是否使用任何物品或工具？
- **RCQ-C24-S-03** `[module=criminal-code-ch23] [fact=perceived_result]`：你當時觀察到對方出現何種身體狀態？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C24-W-01** `[module=criminal-code-ch23] [fact=observed_contact]`：你親自看到哪些身體接觸？
- **RCQ-C24-W-02** `[module=criminal-code-ch23] [fact=condition_before_after]`：你看到被害人在事件前後的狀態有何變化？
- **RCQ-C24-W-03** `[module=criminal-code-ch23] [fact=medical_record]`：如你是醫療人員，你依何種檢查作成紀錄？

### C25 墮胎 `abortion`

- `category_id`: `C25-abortion`
- `source_module`: `criminal-code-ch24`
- `source_refs`: 中華民國刑法第24章
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 不預設懷孕者為被害人；依其實際程序身分及自願陳述範圍啟用。
- **RCQ-C25-V-01** `[module=criminal-code-ch24] [fact=medical_procedure]`：你接受了何種醫療處置或使用何種物品？
- **RCQ-C25-V-02** `[module=criminal-code-ch24] [fact=information_received]`：處置前，相關人員向你說明了哪些內容？
- **RCQ-C25-V-03** `[module=criminal-code-ch24] [fact=pressure]`：有人說了或做了什麼，影響你的決定嗎？

#### SUSPECT_OR_ACTOR

- `applicability`: `CONDITIONAL`
- `activation_condition`: 依程序身分與不自證己罪保障啟用，不以性別或醫療身分預設責任。
- **RCQ-C25-S-01** `[module=criminal-code-ch24] [fact=own_action]`：你在相關處置中實際做了哪些事情？
- **RCQ-C25-S-02** `[module=criminal-code-ch24] [fact=medical_basis]`：你作成處置決定時依據哪些醫療資訊？
- **RCQ-C25-S-03** `[module=criminal-code-ch24] [fact=consent_record]`：當時有哪些同意、說明或病歷紀錄？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 醫療、陪同或其他證人有親身見聞。
- **RCQ-C25-W-01** `[module=criminal-code-ch24] [fact=observed_procedure]`：你親自參與或看到哪一項處置？
- **RCQ-C25-W-02** `[module=criminal-code-ch24] [fact=communication]`：你親自聽到哪些說明或回應？
- **RCQ-C25-W-03** `[module=criminal-code-ch24] [fact=medical_record]`：病歷、檢驗或處置紀錄如何記載？

### C26 遺棄 `abandonment`

- `category_id`: `C26-abandonment`
- `source_module`: `criminal-code-ch25`
- `source_refs`: 中華民國刑法第25章
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 被害人能陳述；無法陳述者以照護及客觀紀錄確認，不由他人代答。
- **RCQ-C26-V-01** `[module=criminal-code-ch25] [fact=care_need]`：事件發生時，你需要哪些日常或醫療照護？
- **RCQ-C26-V-02** `[module=criminal-code-ch25] [fact=care_arrangement]`：原本由誰以何種方式提供照護？
- **RCQ-C26-V-03** `[module=criminal-code-ch25] [fact=care_interruption]`：照護在何時以何種方式中斷？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C26-S-01** `[module=criminal-code-ch25] [fact=duty_source]`：你與受照護者間的照護責任從何而來？
- **RCQ-C26-S-02** `[module=criminal-code-ch25] [fact=care_action]`：你在事件前後提供了哪些照護或安排？
- **RCQ-C26-S-03** `[module=criminal-code-ch25] [fact=ability_or_obstacle]`：當時有哪些具體因素影響你提供照護？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C26-W-01** `[module=criminal-code-ch25] [fact=care_condition]`：你親自觀察到受照護者有哪些需求？
- **RCQ-C26-W-02** `[module=criminal-code-ch25] [fact=care_provider]`：你看到誰在何時提供或停止照護？
- **RCQ-C26-W-03** `[module=criminal-code-ch25] [fact=discovery]`：你在何種情況下發現受照護者？

### C27 妨害自由 `liberty`

- `category_id`: `C27-liberty`
- `source_module`: `criminal-code-liberty`
- `source_refs`: 中華民國刑法第26章（妨害自由罪）；擄人勒贖之拘束部分可與 C28 交叉使用
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C27-V-01** `[module=criminal-code-liberty] [fact=restricted_action]`：你當時想去哪裡，卻被阻止了？
- **RCQ-C27-V-02** `[module=criminal-code-liberty] [fact=restriction_method]`：對方以何種具體方式限制你？
- **RCQ-C27-V-03** `[module=criminal-code-liberty] [fact=duration]`：限制從何時開始，到何時結束？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C27-S-01** `[module=criminal-code-liberty] [fact=own_conduct]`：你對對方的移動、通訊或離開做了哪些處置？
- **RCQ-C27-S-02** `[module=criminal-code-liberty] [fact=authority_basis]`：你認為自己可採取該處置的依據為何？
- **RCQ-C27-S-03** `[module=criminal-code-liberty] [fact=release_condition]`：你提出了哪些解除限制的條件？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C27-W-01** `[module=criminal-code-liberty] [fact=observed_restriction]`：你親自看到哪些限制行動的措施？
- **RCQ-C27-W-02** `[module=criminal-code-liberty] [fact=attempt_to_leave]`：你看到當事人如何嘗試離開或求助？
- **RCQ-C27-W-03** `[module=criminal-code-liberty] [fact=access_control]`：你能確認門禁、通訊或監控如何被控制？

### C28 恐嚇 `threat`

- `category_id`: `C28-threat`
- `source_module`: `criminal-code-threat`
- `source_refs`: 中華民國刑法第26章（妨害自由相關恐嚇規定）及第33章（恐嚇及擄人勒贖罪之恐嚇部分）；擄人勒贖之拘束事實另可交叉使用 C27 題組
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C28-V-01** `[module=criminal-code-threat] [fact=message_content]`：對方使用哪些原話、文字、圖像或動作？
- **RCQ-C28-V-02** `[module=criminal-code-threat] [fact=communicated_harm]`：訊息指向何種人身、財產或其他損害？
- **RCQ-C28-V-03** `[module=criminal-code-threat] [fact=demand]`：對方是否要求你交付財物或採取特定行動？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C28-S-01** `[module=criminal-code-threat] [fact=own_message]`：你向對方傳達了哪些內容？
- **RCQ-C28-S-02** `[module=criminal-code-threat] [fact=delivery_method]`：你以何種方式傳達該內容？
- **RCQ-C28-S-03** `[module=criminal-code-threat] [fact=demand]`：你是否要求對方交付財物或採取行動？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C28-W-01** `[module=criminal-code-threat] [fact=heard_or_seen_message]`：你親自聽到或看到哪些訊息？
- **RCQ-C28-W-02** `[module=criminal-code-threat] [fact=sender_identity]`：你如何確認訊息的發送人？
- **RCQ-C28-W-03** `[module=criminal-code-threat] [fact=demand_or_delivery]`：你親自看到何種要求或財物交付？

### C29 妨害名譽 `defamation`

- `category_id`: `C29-defamation`
- `source_module`: `criminal-code-ch27`
- `source_refs`: 中華民國刑法第27章
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C29-V-01** `[module=criminal-code-ch27] [fact=exact_expression]`：對方使用的原話、文字、圖像或聲音為何？
- **RCQ-C29-V-02** `[module=criminal-code-ch27] [fact=audience]`：哪些人可以接觸到該內容？
- **RCQ-C29-V-03** `[module=criminal-code-ch27] [fact=identifiability]`：接收者如何辨識內容指向你？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C29-S-01** `[module=criminal-code-ch27] [fact=own_expression]`：你發布或傳達的原始內容為何？
- **RCQ-C29-S-02** `[module=criminal-code-ch27] [fact=audience_setting]`：你將內容設定給哪些人觀看或接收？
- **RCQ-C29-S-03** `[module=criminal-code-ch27] [fact=information_basis]`：你發布內容時依據哪些資料？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C29-W-01** `[module=criminal-code-ch27] [fact=received_content]`：你實際接收到的內容為何？
- **RCQ-C29-W-02** `[module=criminal-code-ch27] [fact=identification]`：你如何判斷內容指向哪一個人？
- **RCQ-C29-W-03** `[module=criminal-code-ch27] [fact=distribution]`：你看到內容被傳送或公開至哪些範圍？

### C30 妨害秘密與性隱私 `privacy-sexual-privacy`

- `category_id`: `C30-privacy-sexual-privacy`
- `source_module`: `criminal-code-ch28-28-1`
- `source_refs`: 中華民國刑法第28章及第28章之1
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C30-V-01** `[module=criminal-code-ch28-28-1] [fact=private_content]`：涉及何種非公開活動、談話、影像或資料？
- **RCQ-C30-V-02** `[module=criminal-code-ch28-28-1] [fact=privacy_expectation]`：這些內容原本放在只有你能看到的地方嗎？
- **RCQ-C30-V-03** `[module=criminal-code-ch28-28-1] [fact=consent_scope]`：你曾同意何人以何種範圍接觸或使用該內容？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C30-S-01** `[module=criminal-code-ch28-28-1] [fact=acquisition_method]`：你以何種設備或方式取得該內容？
- **RCQ-C30-S-02** `[module=criminal-code-ch28-28-1] [fact=authorization_basis]`：你認為自己取得何種同意或授權？
- **RCQ-C30-S-03** `[module=criminal-code-ch28-28-1] [fact=distribution]`：你曾將內容交付、展示或傳送給哪些對象？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到拍攝、取得、交付、展示或負責平台與設備紀錄。
- **RCQ-C30-W-01** `[module=criminal-code-ch28-28-1] [fact=observed_acquisition]`：你親自看到內容如何被取得？
- **RCQ-C30-W-02** `[module=criminal-code-ch28-28-1] [fact=observed_distribution]`：你實際收到或看到哪一份內容？
- **RCQ-C30-W-03** `[module=criminal-code-ch28-28-1] [fact=digital_trace]`：平台、設備或帳號紀錄可確認哪些操作？

### C31 竊盜 `theft`

- `category_id`: `C31-theft`
- `source_module`: `criminal-code-ch29`
- `source_refs`: 中華民國刑法第29章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C31-V-01** `[module=criminal-code-ch29] [fact=property_identity]`：遺失或遭取走的是何種財物或能源？
- **RCQ-C31-V-02** `[module=criminal-code-ch29] [fact=possession]`：事件前由何人實際持有或管理？
- **RCQ-C31-V-03** `[module=criminal-code-ch29] [fact=authorization]`：你曾允許何人以何種範圍取用？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C31-S-01** `[module=criminal-code-ch29] [fact=taking]`：你如何取得並移動該財物？
- **RCQ-C31-S-02** `[module=criminal-code-ch29] [fact=possession_understanding]`：你當時如何理解財物的持有人或所有人？
- **RCQ-C31-S-03** `[module=criminal-code-ch29] [fact=disposition]`：取得後你如何保管、使用或處分財物？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C31-W-01** `[module=criminal-code-ch29] [fact=observed_taking]`：你親自看到何人如何取得財物？
- **RCQ-C31-W-02** `[module=criminal-code-ch29] [fact=property_state]`：你最後一次看到財物原狀是在何時？
- **RCQ-C31-W-03** `[module=criminal-code-ch29] [fact=identification]`：你依何種特徵辨識該財物或行為人？

### C32 強盜搶奪 `robbery-snatching`

- `category_id`: `C32-robbery-snatching`
- `source_module`: `criminal-code-ch30`
- `source_refs`: 中華民國刑法第30章
- `sensitivity`: `SENSITIVE_CONDITIONAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C32-V-01** `[module=criminal-code-ch30] [fact=property_taken]`：對方取得或試圖取得何種財物？
- **RCQ-C32-V-02** `[module=criminal-code-ch30] [fact=force_method]`：對方以何種具體動作或言語影響你的行動？
- **RCQ-C32-V-03** `[module=criminal-code-ch30] [fact=control_change]`：財物如何從你的控制移至他人控制？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C32-S-01** `[module=criminal-code-ch30] [fact=own_conduct]`：你對人及財物分別做了哪些動作？
- **RCQ-C32-S-02** `[module=criminal-code-ch30] [fact=means]`：你是否使用物品、言語或肢體力量？
- **RCQ-C32-S-03** `[module=criminal-code-ch30] [fact=property_disposition]`：取得財物後你如何處理？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C32-W-01** `[module=criminal-code-ch30] [fact=observed_force]`：你親自看到哪些對人的言語或動作？
- **RCQ-C32-W-02** `[module=criminal-code-ch30] [fact=observed_taking]`：你親自看到財物如何被取得？
- **RCQ-C32-W-03** `[module=criminal-code-ch30] [fact=escape_route]`：你看到行為人如何離開現場？

### C33 侵占 `embezzlement`

- `category_id`: `C33-embezzlement`
- `source_module`: `criminal-code-ch31`
- `source_refs`: 中華民國刑法第31章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C33-V-01** `[module=criminal-code-ch31] [fact=entrustment]`：你基於何種關係將財物交由對方持有？
- **RCQ-C33-V-02** `[module=criminal-code-ch31] [fact=return_condition]`：雙方原約定何時或在何種條件下返還？
- **RCQ-C33-V-03** `[module=criminal-code-ch31] [fact=disputed_disposition]`：你發現財物被如何使用或處分？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C33-S-01** `[module=criminal-code-ch31] [fact=possession_basis]`：你基於何種關係持有該財物？
- **RCQ-C33-S-02** `[module=criminal-code-ch31] [fact=agreed_scope]`：你如何理解可使用或處分的範圍？
- **RCQ-C33-S-03** `[module=criminal-code-ch31] [fact=actual_disposition]`：你實際如何保管、使用或處分財物？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到交付、保管、返還要求或處分。
- **RCQ-C33-W-01** `[module=criminal-code-ch31] [fact=observed_entrustment]`：你親自看到財物如何交付？
- **RCQ-C33-W-02** `[module=criminal-code-ch31] [fact=agreement]`：你親自聽到何種保管或返還約定？
- **RCQ-C33-W-03** `[module=criminal-code-ch31] [fact=observed_disposition]`：你親自看到財物被如何處理？

### C34 詐欺背信 `fraud-breach-of-trust`

- `category_id`: `C34-fraud-breach-of-trust`
- `source_module`: `criminal-code-ch32`
- `source_refs`: 中華民國刑法第32章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C34-V-01** `[module=criminal-code-ch32] [fact=representation_or_duty]`：對方曾向你表示何種事實或承諾何種處理？
- **RCQ-C34-V-02** `[module=criminal-code-ch32] [fact=reliance_action]`：你因該資訊或受託關係做了何種財產處分？
- **RCQ-C34-V-03** `[module=criminal-code-ch32] [fact=property_difference]`：處分前後的財產狀態有何可計算差異？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C34-S-01** `[module=criminal-code-ch32] [fact=representation]`：你向對方表達了哪些交易或受託內容？
- **RCQ-C34-S-02** `[module=criminal-code-ch32] [fact=information_basis]`：你作成該表示時掌握哪些資料？
- **RCQ-C34-S-03** `[module=criminal-code-ch32] [fact=fund_use]`：你取得財物或權限後如何使用？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人參與說明、簽約、付款、受託執行或帳務處理。
- **RCQ-C34-W-01** `[module=criminal-code-ch32] [fact=heard_representation]`：你親自聽到何種交易說明或受託承諾？
- **RCQ-C34-W-02** `[module=criminal-code-ch32] [fact=observed_disposition]`：你親自看到何種財產處分？
- **RCQ-C34-W-03** `[module=criminal-code-ch32] [fact=accounting_record]`：帳務或履約紀錄如何記載資金用途？

### C35 贓物 `fence`

- `category_id`: `C35-fence`
- `source_module`: `criminal-code-ch34`
- `source_refs`: 中華民國刑法第34章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 原財物權利人或持有人能辨識財物與失去控制的經過。
- **RCQ-C35-V-01** `[module=criminal-code-ch34] [fact=property_identification]`：你依哪些特徵辨識該財物？
- **RCQ-C35-V-02** `[module=criminal-code-ch34] [fact=loss_event]`：你在何種情況下失去對財物的控制？
- **RCQ-C35-V-03** `[module=criminal-code-ch34] [fact=recovery]`：財物後來在何處由何人持有？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C35-S-01** `[module=criminal-code-ch34] [fact=acquisition]`：你從何人以何種方式取得財物？
- **RCQ-C35-S-02** `[module=criminal-code-ch34] [fact=price_or_condition]`：取得財物的價格或交換條件為何？
- **RCQ-C35-S-03** `[module=criminal-code-ch34] [fact=source_knowledge]`：你取得時知道哪些關於財物來源的資訊？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到取得、搬運、寄藏、收買或媒介。
- **RCQ-C35-W-01** `[module=criminal-code-ch34] [fact=observed_transfer]`：你親自看到財物如何交付？
- **RCQ-C35-W-02** `[module=criminal-code-ch34] [fact=heard_source_statement]`：交付時你親自聽到哪些關於來源的說明？
- **RCQ-C35-W-03** `[module=criminal-code-ch34] [fact=price_or_condition]`：你能確認何種價格或交換條件？

### C36 毀損 `damage`

- `category_id`: `C36-damage`
- `source_module`: `criminal-code-ch35`
- `source_refs`: 中華民國刑法第35章
- `sensitivity`: `NORMAL`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-C36-V-01** `[module=criminal-code-ch35] [fact=object_identity]`：受影響的是何種物品、建築或文件？
- **RCQ-C36-V-02** `[module=criminal-code-ch35] [fact=original_state]`：事件前的功能、外觀或可用狀態如何？
- **RCQ-C36-V-03** `[module=criminal-code-ch35] [fact=change]`：事件後出現何種功能或外觀變化？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C36-S-01** `[module=criminal-code-ch35] [fact=own_conduct]`：你對該物品或設施做了哪些動作？
- **RCQ-C36-S-02** `[module=criminal-code-ch35] [fact=authority]`：你認為自己具有何種使用、拆除或處分權限？
- **RCQ-C36-S-03** `[module=criminal-code-ch35] [fact=observed_change]`：行為後你觀察到何種變化？

#### WITNESS

- `applicability`: `APPLICABLE`
- **RCQ-C36-W-01** `[module=criminal-code-ch35] [fact=observed_conduct]`：你親自看到何人對物品做何種動作？
- **RCQ-C36-W-02** `[module=criminal-code-ch35] [fact=before_after]`：你能確認事件前後的狀態差異為何？
- **RCQ-C36-W-03** `[module=criminal-code-ch35] [fact=repair_record]`：檢查、估價或修復紀錄如何記載？

### C37 妨害電腦使用 `computer`

- `category_id`: `C37-computer`
- `source_module`: `criminal-code-ch36`
- `source_refs`: 中華民國刑法第36章
- `sensitivity`: `SENSITIVE_CONDITIONAL`（帳號、憑證及個資）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 系統、帳號、資料或設備的權利人及管理端。
- **RCQ-C37-V-01** `[module=criminal-code-ch36] [fact=system_identity]`：受影響的是哪一個系統、帳號、設備或資料集？
- **RCQ-C37-V-02** `[module=criminal-code-ch36] [fact=authorization_boundary]`：哪些人原本具有何種存取或操作權限？
- **RCQ-C37-V-03** `[module=criminal-code-ch36] [fact=system_change]`：事件前後的功能、資料或可用性有何變化？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-C37-S-01** `[module=criminal-code-ch36] [fact=access_method]`：你以何種帳號、設備或連線方式進入系統？
- **RCQ-C37-S-02** `[module=criminal-code-ch36] [fact=authorization_basis]`：你認為自己具有何種存取或變更權限？
- **RCQ-C37-S-03** `[module=criminal-code-ch36] [fact=operation]`：你在系統內執行了哪些具體操作？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 系統管理、資安、稽核或親自見到設備操作的人員。
- **RCQ-C37-W-01** `[module=criminal-code-ch36] [fact=log_interpretation]`：系統日誌可確認哪些時間、帳號或操作？
- **RCQ-C37-W-02** `[module=criminal-code-ch36] [fact=normal_authorization]`：正常授權與帳號管理流程為何？
- **RCQ-C37-W-03** `[module=criminal-code-ch36] [fact=evidence_preservation]`：數位證據以何種方式擷取與保存？

## 5. 特別法與程序框架（8 類）

### S01 家庭暴力 `domestic-violence`

- `category_id`: `S01-domestic-violence`
- `source_module`: `domestic-violence-prevention-act`
- `source_refs`: 家庭暴力防治法
- `sensitivity`: `SENSITIVE`
- `classification_note`: 本法是家庭暴力防治與程序框架；具體刑事責任仍須連結其他犯罪規定或保護令違反規定。

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-S01-V-01** `[module=domestic-violence-prevention-act] [fact=family_relation]`：你與對方目前或過去的家庭成員關係為何？
- **RCQ-S01-V-02** `[module=domestic-violence-prevention-act] [fact=conduct_pattern]`：請在你願意的範圍內，分次說明對方的身體、精神或經濟控制行為。
- **RCQ-S01-V-03** `[module=domestic-violence-prevention-act] [fact=current_risk]`：目前有哪些立即安全或聯絡風險需要處理？
- **RCQ-S01-V-04** `[module=domestic-violence-prevention-act] [fact=protection_order]`：目前是否有保護令，其有效期間與命令內容為何？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S01-S-01** `[module=domestic-violence-prevention-act] [fact=family_relation]`：你與對方目前或過去的家庭成員關係為何？
- **RCQ-S01-S-02** `[module=domestic-violence-prevention-act] [fact=own_conduct]`：你在各次事件中實際做了哪些事情？
- **RCQ-S01-S-03** `[module=domestic-violence-prevention-act] [fact=control_measure]`：你曾如何管理金錢、通訊、居住或行動安排？
- **RCQ-S01-S-04** `[module=domestic-violence-prevention-act] [fact=order_notice]`：如有保護令，你在何時以何種方式知悉命令內容？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人親自見聞、第一時間接觸，或負責醫療、社政、教育及保護令執行紀錄。
- **RCQ-S01-W-01** `[module=domestic-violence-prevention-act] [fact=personal_observation]`：你親自看到或聽到哪些行為或言語？
- **RCQ-S01-W-02** `[module=domestic-violence-prevention-act] [fact=condition]`：你第一次接觸當事人時，其可觀察狀態如何？
- **RCQ-S01-W-03** `[module=domestic-violence-prevention-act] [fact=first_disclosure]`：當事人第一次說明時使用哪些原話？
- **RCQ-S01-W-04** `[module=domestic-violence-prevention-act] [fact=official_record]`：你依何種職務程序製作何種紀錄？

### S02 兒少保護與性剝削 `child-protection`

- `category_id`: `S02-child-protection`
- `source_module`: `child-welfare-rights-act`、`child-sexual-exploitation-act`
- `source_refs`: 兒童及少年福利與權益保障法；兒童及少年性剝削防制條例
- `sensitivity`: `SENSITIVE`
- `classification_note`: 兒少保護與性剝削為兩個獨立法源模組；共同題僅蒐集年齡、關係、安全與接觸事實，不合併其法律要件。

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-S02-V-01** `[module=child-welfare-rights-act] [fact=age]`：你現在幾歲？
- **RCQ-S02-V-02** `[module=child-welfare-rights-act] [fact=safety_need]`：你現在覺得安全嗎？
- **RCQ-S02-V-03** `[module=child-sexual-exploitation-act] [fact=recruitment_or_exchange]`：有沒有人給你東西，要你去做某件事？
- **RCQ-S02-V-04** `[module=child-sexual-exploitation-act] [fact=content_handling]`：有沒有人拍下或傳送和你有關的私密影像？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S02-S-01** `[module=child-welfare-rights-act] [fact=care_relation]`：你與兒少間有何照顧、監督或其他關係？
- **RCQ-S02-S-02** `[module=child-welfare-rights-act] [fact=own_conduct]`：你對兒少的居住、教育、工作或活動做了哪些安排？
- **RCQ-S02-S-03** `[module=child-sexual-exploitation-act] [fact=benefit_or_arrangement]`：你是否安排金錢、物品或其他利益的交付？
- **RCQ-S02-S-04** `[module=child-sexual-exploitation-act] [fact=content_operation]`：如涉及影像或內容，你執行了哪些拍攝、持有、重製或傳送操作？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 照顧者、通報人、第一時間接觸者、平台或專業人員有親身資料。
- **RCQ-S02-W-01** `[module=child-welfare-rights-act] [fact=care_condition]`：你親自觀察到兒少的照顧或生活狀況為何？
- **RCQ-S02-W-02** `[module=child-welfare-rights-act] [fact=reporting_record]`：你基於何種親身事實作成通報或專業紀錄？
- **RCQ-S02-W-03** `[module=child-sexual-exploitation-act] [fact=first_disclosure]`：兒少第一次說明時使用哪些原話？
- **RCQ-S02-W-04** `[module=child-sexual-exploitation-act] [fact=digital_trace]`：平台或設備紀錄可確認哪些製作、持有或傳送操作？

### S03 性騷擾與性侵害保護 `sexual-harassment`

- `category_id`: `S03-sexual-harassment-protection`
- `source_module`: `sexual-harassment-prevention-act`、`sexual-assault-crime-prevention-act`
- `source_refs`: 性騷擾防治法；性侵害犯罪防治法
- `sensitivity`: `SENSITIVE`
- `classification_note`: 性騷擾事實與性侵害被害保護程序分開。妨害性自主的刑事核心仍使用 C15，不以保護程序題取代。

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-S03-V-01** `[module=sexual-harassment-prevention-act] [fact=unwanted_conduct]`：請在你願意的範圍內說明對方的言語、動作或接觸。
- **RCQ-S03-V-02** `[module=sexual-harassment-prevention-act] [fact=context_or_condition]`：對方有沒有拿你的工作、成績或其他權益作為條件？
- **RCQ-S03-V-03** `[module=sexual-assault-crime-prevention-act] [fact=support_need]`：你現在需要哪一種安全或醫療協助？
- **RCQ-S03-V-04** `[module=sexual-assault-crime-prevention-act] [fact=prior_statement]`：你之前有沒有為這件事做過筆錄或其他紀錄？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S03-S-01** `[module=sexual-harassment-prevention-act] [fact=own_conduct]`：你當時說了哪些話或做了哪些動作？
- **RCQ-S03-S-02** `[module=sexual-harassment-prevention-act] [fact=relationship_or_power]`：你與對方間有何工作、教育、醫療、服務或監督關係？
- **RCQ-S03-S-03** `[module=sexual-harassment-prevention-act] [fact=response_notice]`：你何時以何種方式得知對方的回應或拒絕？
- **RCQ-S03-S-04** `[module=sexual-assault-crime-prevention-act] [fact=no_contact_measure]`：調查期間是否有隔離、禁止接觸或其他程序措施？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人有親身見聞、第一時間接觸或負責保護與調查程序。
- **RCQ-S03-W-01** `[module=sexual-harassment-prevention-act] [fact=personal_observation]`：你親自看到或聽到哪些言語、動作或接觸？
- **RCQ-S03-W-02** `[module=sexual-harassment-prevention-act] [fact=relationship_context]`：你能確認雙方當時具有何種場域或權勢關係？
- **RCQ-S03-W-03** `[module=sexual-assault-crime-prevention-act] [fact=first_disclosure]`：當事人第一次說明時使用哪些原話？
- **RCQ-S03-W-04** `[module=sexual-assault-crime-prevention-act] [fact=protection_record]`：你依何種程序提供保護或製作紀錄？

### S04 跟蹤騷擾 `stalking`

- `category_id`: `S04-stalking`
- `source_module`: `stalking-harassment-prevention-act`
- `source_refs`: 跟蹤騷擾防制法
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-S04-V-01** `[module=stalking-harassment-prevention-act] [fact=repetition]`：請逐次說明對方聯絡、接近、監視或使用你資料的行為。
- **RCQ-S04-V-02** `[module=stalking-harassment-prevention-act] [fact=unwanted_notice]`：你曾以何種方式表達不願被聯絡或接近？
- **RCQ-S04-V-03** `[module=stalking-harassment-prevention-act] [fact=daily_effect]`：事件具體影響你哪一項日常生活或社會活動？
- **RCQ-S04-V-04** `[module=stalking-harassment-prevention-act] [fact=current_risk]`：目前有哪些持續接觸或安全風險？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S04-S-01** `[module=stalking-harassment-prevention-act] [fact=contact_instances]`：請逐次說明你主動聯絡、接近或查詢對方的行為。
- **RCQ-S04-S-02** `[module=stalking-harassment-prevention-act] [fact=response_notice]`：你何時得知對方不願被聯絡或接近？
- **RCQ-S04-S-03** `[module=stalking-harassment-prevention-act] [fact=gender_relation]`：你如何說明該行為與性或性別的關聯？
- **RCQ-S04-S-04** `[module=stalking-harassment-prevention-act] [fact=data_use]`：你如何取得並使用對方的行蹤或個人資料？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到反覆接近、聯絡、守候、資料濫用或負責相關紀錄。
- **RCQ-S04-W-01** `[module=stalking-harassment-prevention-act] [fact=observed_instances]`：你親自見到哪些不同次數的行為？
- **RCQ-S04-W-02** `[module=stalking-harassment-prevention-act] [fact=notice]`：你親自見到當事人如何表達不願意？
- **RCQ-S04-W-03** `[module=stalking-harassment-prevention-act] [fact=daily_effect]`：你親自觀察到哪一項生活或活動變化？
- **RCQ-S04-W-04** `[module=stalking-harassment-prevention-act] [fact=digital_or_site_record]`：哪些通聯、門禁、監視或平台紀錄可供查證？

### S05 人口販運 `trafficking`

- `category_id`: `S05-trafficking`
- `source_module`: `human-trafficking-prevention-act`
- `source_refs`: 人口販運防制法
- `sensitivity`: `SENSITIVE`

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-S05-V-01** `[module=human-trafficking-prevention-act] [fact=recruitment_information]`：招募或安排時，對方如何說明工作、報酬或活動內容？
- **RCQ-S05-V-02** `[module=human-trafficking-prevention-act] [fact=control_method]`：是否有人以暴力、威脅、監控、債務、證件或其他方式限制你？
- **RCQ-S05-V-03** `[module=human-trafficking-prevention-act] [fact=labor_or_activity]`：你實際被安排從事何種工作或活動？
- **RCQ-S05-V-04** `[module=human-trafficking-prevention-act] [fact=compensation]`：實際取得的報酬與原約定有何差異？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S05-S-01** `[module=human-trafficking-prevention-act] [fact=role]`：你在招募、運送、住宿、工作或收款安排中負責何事？
- **RCQ-S05-S-02** `[module=human-trafficking-prevention-act] [fact=control_measure]`：你如何管理證件、債務、通訊、居住或行動？
- **RCQ-S05-S-03** `[module=human-trafficking-prevention-act] [fact=benefit]`：你取得何種費用、抽成或其他利益？
- **RCQ-S05-S-04** `[module=human-trafficking-prevention-act] [fact=age_knowledge]`：如涉及未滿十八歲者，你當時依何資料判斷其年齡？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人參與招募、交通、住宿、工作、付款或第一時間救援。
- **RCQ-S05-W-01** `[module=human-trafficking-prevention-act] [fact=observed_arrangement]`：你親自看到何人安排工作、交通或住宿？
- **RCQ-S05-W-02** `[module=human-trafficking-prevention-act] [fact=observed_control]`：你親自看到哪些限制、監控或證件管理行為？
- **RCQ-S05-W-03** `[module=human-trafficking-prevention-act] [fact=work_condition]`：你能確認哪些工時、工作內容或報酬事實？
- **RCQ-S05-W-04** `[module=human-trafficking-prevention-act] [fact=first_disclosure]`：當事人第一次說明時使用哪些原話？

### S06 性別平等工作與教育 `gender-equality`

- `category_id`: `S06-gender-equality`
- `source_module`: `gender-equality-employment-act`、`gender-equity-education-act`
- `source_refs`: 性別平等工作法；性別平等教育法
- `sensitivity`: `SENSITIVE`
- `classification_note`: 工作場域與教育場域分開路由；兩法的主體、主管機關及調查程序不得混用。

#### VICTIM_OR_AFFECTED

- `applicability`: `APPLICABLE`
- **RCQ-S06-V-01** `[module=gender-equality-employment-act] [fact=employment_relation]`：如屬工作場域，雙方的僱用、求職、指揮或監督關係為何？
- **RCQ-S06-V-02** `[module=gender-equality-employment-act] [fact=employment_effect]`：相關言行具體影響哪一項工作條件或表現？
- **RCQ-S06-V-03** `[module=gender-equity-education-act] [fact=affected_school_role]`：事情發生時，你在學校是什麼身分？
- **RCQ-S06-V-04** `[module=gender-equity-education-act] [fact=education_effect]`：這些話或動作影響了你在學校的哪一項生活？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S06-S-01** `[module=gender-equality-employment-act] [fact=employment_power]`：如屬工作場域，你對對方的工作條件具有何種決定或影響權限？
- **RCQ-S06-S-02** `[module=gender-equality-employment-act] [fact=own_conduct]`：你在工作場域說了哪些話或做了哪些動作？
- **RCQ-S06-S-03** `[module=gender-equity-education-act] [fact=education_role]`：如屬教育場域，你對對方具有何種教學、指導、評鑑或管理關係？
- **RCQ-S06-S-04** `[module=gender-equity-education-act] [fact=own_conduct]`：你在教育場域說了哪些話或做了哪些動作？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人親自見聞，或負責雇主、學校的申訴、通報及調查程序。
- **RCQ-S06-W-01** `[module=gender-equality-employment-act] [fact=employment_context]`：你能確認工作場域中的職務與監督關係為何？
- **RCQ-S06-W-02** `[module=gender-equality-employment-act] [fact=employer_response]`：雇主在何時採取何種處理措施？
- **RCQ-S06-W-03** `[module=gender-equity-education-act] [fact=school_context]`：你能確認教育場域中的人員身分與互動關係為何？
- **RCQ-S06-W-04** `[module=gender-equity-education-act] [fact=school_response]`：學校在何時採取何種通報或處理措施？

### S07 少年事件 `juvenile`

- `category_id`: `S07-juvenile`
- `source_module`: `juvenile-justice-act`
- `source_refs`: 少年事件處理法
- `sensitivity`: `SENSITIVE`
- `classification_note`: 本類是少年保護與程序路由，不是獨立犯罪要件集合。

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 案件有直接受影響人時使用；不得因對方是少年而降低被害端安全與程序保障。
- **RCQ-S07-V-01** `[module=juvenile-justice-act] [fact=event_conduct]`：請說明你親身經歷的具體行為。
- **RCQ-S07-V-02** `[module=juvenile-justice-act] [fact=age_source]`：你如何得知或確認對方的年齡？
- **RCQ-S07-V-03** `[module=juvenile-justice-act] [fact=protection_need]`：目前有哪些安全、隔離或聯絡需求？

#### SUSPECT_OR_ACTOR

- `applicability`: `CONDITIONAL`
- `activation_condition`: 受詢問者為少年時，先完成權利告知、法定代理人或現在保護少年之人通知及少年程序確認。
- **RCQ-S07-S-01** `[module=juvenile-justice-act] [fact=age_identity]`：你現在幾歲？
- **RCQ-S07-S-02** `[module=juvenile-justice-act] [fact=rights_notice]`：剛才說明的權利，有哪裡聽不懂？
- **RCQ-S07-S-03** `[module=juvenile-justice-act] [fact=support_need]`：你現在最希望我們協助哪一件事？

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 親身見聞者、法定代理人、現在保護少年之人或程序承辦人依其身分回答。
- **RCQ-S07-W-01** `[module=juvenile-justice-act] [fact=personal_observation]`：你親自看到或聽到哪些事件事實？
- **RCQ-S07-W-02** `[module=juvenile-justice-act] [fact=care_relation]`：如你負責照顧少年，你與少年具有何種關係？
- **RCQ-S07-W-03** `[module=juvenile-justice-act] [fact=procedure_record]`：如你是承辦人，通知、告知、同行或護送紀錄如何記載？

### S08 毒品危害防制條例 `drugs`

- `category_id`: `S08-drugs`
- `source_module`: `narcotics-hazard-prevention-act`
- `source_refs`: 毒品危害防制條例
- `sensitivity`: `SENSITIVE_CONDITIONAL`（醫療與戒癮資訊）

#### VICTIM_OR_AFFECTED

- `applicability`: `CONDITIONAL`
- `activation_condition`: 有直接受影響人、場所權利人、醫療端或查緝保管端。
- **RCQ-S08-V-01** `[module=narcotics-hazard-prevention-act] [fact=item_identity]`：涉及物品的外觀、包裝、數量與發現位置為何？
- **RCQ-S08-V-02** `[module=narcotics-hazard-prevention-act] [fact=delivery_or_exposure]`：你如何取得、接觸或被交付該物品？
- **RCQ-S08-V-03** `[module=narcotics-hazard-prevention-act] [fact=medical_need]`：目前是否有急性醫療或戒癮協助需求？

#### SUSPECT_OR_ACTOR

- `applicability`: `APPLICABLE`
- **RCQ-S08-S-01** `[module=narcotics-hazard-prevention-act] [fact=handling]`：你曾如何取得、持有、製造、運送或交付該物品？
- **RCQ-S08-S-02** `[module=narcotics-hazard-prevention-act] [fact=substance_knowledge]`：你當時如何理解物品的種類、成分或用途？
- **RCQ-S08-S-03** `[module=narcotics-hazard-prevention-act] [fact=transaction]`：是否有金錢、物品或其他利益的約定或交付？
- **RCQ-S08-S-04** `[module=narcotics-hazard-prevention-act] [fact=consumption]`：如涉及施用，請說明使用時間與方式。

#### WITNESS

- `applicability`: `CONDITIONAL`
- `activation_condition`: 證人見到取得、持有、製造、運送、交付或施用，或負責搜索、扣押及鑑驗。
- **RCQ-S08-W-01** `[module=narcotics-hazard-prevention-act] [fact=observed_handling]`：你親自看到何人如何處理物品？
- **RCQ-S08-W-02** `[module=narcotics-hazard-prevention-act] [fact=observed_transaction]`：你親自看到何種金錢或物品交付？
- **RCQ-S08-W-03** `[module=narcotics-hazard-prevention-act] [fact=custody_chain]`：查獲物的扣押、封緘與送驗流程為何？
- **RCQ-S08-W-04** `[module=narcotics-hazard-prevention-act] [fact=examination]`：鑑驗報告確認何種成分與淨重？
