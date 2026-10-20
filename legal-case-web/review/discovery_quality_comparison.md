# 罪章品質對照測試報告（discovery-only，執行 2026-10-19／整理 2026-10-20）

執行者：agent ｜ 性質：**review-only 品質抽檢**，結果不接入 runtime、不改任何關卡狀態
外部通道：
- **PSUE**（`psue.moj.gov.tw/psiqs/index.jsp`）：已實際連線讀取——查詢表單**驗證碼必填**，依
  人工審核前約束不繞過 → **PSUE 端無法完成自動對照**，僅完成頁面結構確認（與 HG-LR-01
  登記之 `DISCOVERY_ONLY_SCHEMA_UNKNOWN` 一致，限制維持）。
- **tw-legal-rag（TLR）**：5 罪章各 1 查詢、去識別構成要件式查詢、無 keys、無案情。取得了
  全部可引用判決（每章 J1–J3，均為讀入理由全文者）。

**重要治理點**：`app/rules.py` hash `7d785584…` 剛被人工審閱完成並已記錄。本報告找出之
差異**全部只列為候選修改提案**，未動程式碼；任何修改須人工核定後另行走探針→修改→測試→
hash 鏈刷新→再審流程。

---

## 1. 對照方法

| 罪章 | 我方合成句（被害人敘述角度） | 我方 pipeline 輸出（實跑） | tw-legal-rag 查詢語式 |
|---|---|---|---|
| 竊盜 | 有人趁我不注意拿走我放在桌面上的錢包。 | theft(NEED_REVIEW)＋embezzlement＋robbery（related 擴展）；prop action=「取走物品」 | 意圖為自己不法所有趁人不注意竊取他人財物竊盜罪構成要件案例 |
| 侵占 | 店長保管公司公款之後拒不返還。 | embezzlement(NEED_REVIEW)＋robbery＋theft（related）；prop action=「拒不返還」 | 業務上保管他人款項經催討仍拒不返還變易持有為不法所有侵占罪 |
| 詐欺 | 網友叫我匯錢買手機，說好三天到貨，結果東西沒到人也不回覆。 | fraud(NEED_LEGAL_ROUTE_MAPPING) 單一 | 施用詐術使被害人陷於錯誤而匯款交付財物詐欺取財罪 |
| 傷害 | 在夜市跟人發生爭執，對方推我撞到桌子，手臂瘀青。 | injury(NEED_LEGAL_ROUTE_MAPPING) 單一 | 推撞拉扯致人瘀青受傷之傷害罪構成要件 |
| 公然侮辱 | 他在夜市攤位前大聲辱罵我「不要臉的賊」，旁邊很多人都聽到。 | defamation(NEED_LEGAL_ROUTE_MAPPING) 單一 | 公然辱罵貶損人格在不特定人可共見共聞場所之公然侮辱罪 |

## 2. 真實書類の要件語句（只用 bundle `allowed_citations` 內之引述）

| 罪章 | 真實書類判決/檢引用語（節錄原文） | 引用 |
|---|---|---|
| 竊盜 | 「意圖為自己不法所有，基於竊盜之各別犯意，於附表所示之時間、地點，…竊取附表所示之物得手」（臺灣彰化地方法院 111 年度簡 上…263）；「係犯刑法第320條第1項竊盜罪嫌」 | theft J1/J3 |
| 侵占 | 「侵占罪係即成犯，凡對自己持有他人所有物，有變易持有為所有之意思時，即應構成犯罪，縱事後將侵占之物設法歸還，亦無解於罪名之成立」（臺灣高等法院）；「侵占業務上持有物之罪，以其所侵占之他人所有物係因執行業務而持有為構成要件」（臺灣高等法院臺中分院） | embezzle J1/J3 |
| 詐欺 | 「致使…陷於錯誤而依指示…匯款…，受有損害…主觀顯有詐欺取財之犯意，客觀上亦有施用詐術」（臺灣高等法院）；多次匯款「係以單一意思決定…自應評價」（臺灣士林地方法院） | fraud J1/J3 |
| 傷害 | 「經診斷受有右上臂瘀青3×3公分之傷害…有…驗傷診斷書…在卷可稽」（臺灣宜蘭地方法院） | injury J1 |
| 公然侮辱 | 「祗須侮辱行為足使不特定人或多數人得以共見共聞，即行成立（司法院院字第2033、2179號解釋意旨參照）」（臺灣士林地方法院）；「公然侮辱，祗須…共見共聞…所謂『侮辱』，係指侮弄辱罵…為其他輕蔑人格之一切行為屬之」（臺灣臺中地方法院） | insult J1/J2 |

## 3. 品質比對結論

### 一致（我方與書類見解相同方向）
| 面向 | 對照結果 |
|---|---|
| 詐欺三段式 | 我方incident 白話句「匯錢沒到貨」→ 詐欺單一候選；書類「施詐→陷於錯誤→匯款交付」==我方 PROPERTY 路徑俸爭未知之因果語義一致 |
| 傷害證據語義 | 我方證據 facts 有驗傷/診斷證明訊號；書類同以驗傷診斷書為傷害證據 |
| 公然性要件 | 我方 Q-DF309-AUDIENCE（哪些人可能聽見）／element patterns（不特定人、共見共聞）；書類「不特定人或多數人共見共聞」== |
| 侵占持有訊號 | 我方「保管/經手/受託」進持有訊號；書類「因執行業務而持有」== |

### 差異（書類見解 vs 我方）
| # | 差異內容 | 影響 | 建議 |
|---|---|---|---|
| D1 | **財物家族 related 廣擴**：書類竊盜典型只連 §320／§47（加計執行聯結）；我方「拿走錢包」句把 embezzlement、robbery 都帶入候選（雖然 NEED_REVIEW），「侵占」句亦連 robbery/theft | 候選圖題外多，可能增加 Gate 2 誤選風險（待 human 判） | 候選修改（rules.py）：財物 related 擴展可再由「動作型（拿走/偷/武力）vs 持有型（保管/受託）」二分降隣——屬**行為**建議，需人工核定 |
| D2 | **侵占核心概念「變易持有為所有」未建模**：書類指出意圖（不法所有之意思）局最關鍵，且「事後歸還仍成立」；我方 focused 題覆蓋中 intent=UNKNOWN，可能足夠（有 intent 題），但「花用/轉存自己帳戶」等意圖具體化訊號我方無 coverage | 提醒焦點不足 | 候選修改（rules.py coverage 訊號）：補「花用/轉入自己帳戶/沒收歲入所」意圖跡象 coverage，不做任何結論判定 |
| D3 | **書類句式Past合成**：書類含「附表所示」「基於犯意」等套語；我方 intake 面向是口白話敘述，層位不同（設計如此，not bug） | 無方案實影響 | 無修改；唯一提醒：若未來要接真實書類（OCR入案情），套語表達式則需另批審 |
| D4 | **PSUE captcha 鎖** 無法自動對照 | discovery 管道單軌 | 維持 HG-LR-01 登記；不做任何 bypass |

### 穩定性測試結果
- 我方 pipeline 各罪章輸出穩定（有既試 test_generation_stability.py 保證。
- 客觀：我方對同一句反复跑輸出－致（鎖定 test 三輪）」。

## 4. 行動項（全部待人工核定）

1. **D1**：財物 related 降隣方案草案（設計者：agent，待你示意后才動）。
2. **D2**：侵占意圖跡象 coverage 訊號表（動作層，僅 NEED_REVIEW 端）。
3. 兩項程序：任何 rules.py／route_questions.py 改動 = hash 鏈刷新＋ you launch re-review。
4. 問題點留痕：`.audit/project-qa.tsv`。

## 附錄：本報告引用之 bundle citation_ids（全部在 allowed_citations 內）

theft: J1, J2, J3 ／ embezzle: J1, J2, J3 ／ fraud: J1, J2, J3 ／ injury: J1, J2, J3 ／ insult: J1, J2, J3
bundle 原始檔：Windows `%TEMP%\tlr2_*.json`（未入 repo，避免 review-only 資料混進 codebase）。

## 5. E4 終輪全量複測結果（11 章最終對照表；E2 輪審查後已降級修訂）

每章皆以去識別構成要件式查詢取得 TLR bundle（J1–J3 均為讀入理由全文者，可引用），再與修改後的機器輸出逐章比對。

**證據強度（2026-10-20 人工審查後修訂）**：本表證明的是「11 個正例均召回對應主要候選」**（recall）**；
2026-10-20 人工審查以近鄰負例證明 E 輪版本在 precision 上有誤列（表 7／9／10／11 列對應的誤觸、表 1／2／10 列的財物 family 污染），E2 輪已依構成要件（刑法 §305／§328／§335／§135 第 1 項、跟騷法 §3）收緊並實作 D1 三路區辨。本表**不**宣稱全 11 章「無反向矛盾」或章級品質通過；precision 以 `NEAR_MISS_CASES` 五錨點測試及 §5-a 負例表為準，法律要件完整性仍待人工複審（`e2_round_rules_py_review_notes.md`）。

| # | 罪章 | 我方合成句（被害人敘述） | 機器輸出（E2 輪修後；NEED_REVIEW/NEED_LEGAL_ROUTE_MAPPING 僅建立候選方向） | 真實書類要件語句（TLR bundle 語句） | 引用 | 判定 |
|---|---|---|---|---|---|---|
| 1 | 竊盜 | 有人趁我不注意拿走我放在桌面上的錢包。 | theft 單章（D1 三路區辨：不再帶侵占／強盜 related） | 「意圖為自己不法所有，基於竊盜之各別犯意，…竊取附表所示之物得手」；「係犯刑法第320條第1項竊盜罪嫌」 | theft J1/J3 | ✅ 正例召回；財物污染由 D1 移除 |
| 2 | 侵占 | 店長保管公司公款之後拒不返還。 | embezzlement 單章（D1） | 「侵占罪係即成犯，凡對自己持有他人所有物，有變易持有為所有之意思時，即應構成犯罪，縱事後將侵占之物設法歸還，亦無解於罪名之成立」 | embezzle J1 | ✅ 正例召回；E-5 收緊職稱／欠款誤觸 |
| 3 | 詐欺 | 網友叫我匯錢買手機，說好三天到貨，結果東西沒到人也不回覆。 | fraud | 「施用詐術使被害人陷於錯誤而匯款交付財物」；多次匯款「係以單一意思決定」 | fraud J1–J3 | ✅ 正例召回 |
| 4 | 傷害 | 在夜市跟人發生爭執，對方推我撞到桌子，手臂瘀青。 | injury | 「經診斷受有右上臂瘀青3×3公分之傷害…有驗傷診斷書在卷可稽」 | injury J1 | ✅ 正例召回 |
| 5 | 公然侮辱 | 他在夜市攤位前大聲辱罵我「不要臉的賊」，旁邊很多人都聽到。 | defamation | 「不特定人或多數人得以共見共聞，即行成立」；「侮弄辱罵…輕蔑人格」 | insult J1/J2 | ✅ 正例召回 |
| 6 | 毀損 | 他很生氣，把我放在桌上的手機摔在地上，螢幕整個碎掉不能用了。 | damage | 「毀棄、損壞他人之有形之動產…或致令不堪用，足以生損害於公眾或他人」 | damage J1/J3 | ✅ 正例召回 |
| 7 | 恐嚇危害安全 | 他傳訊息給我說「晚上小心一點」，還說他知道我家住哪裡，我很害怕。 | intimidation | 「以加害生命、身體、自由、名譽、財產之事，恐嚇他人者，係指以使人生畏怖心為目的，而通知將加惡害之旨於被害人」 | intimidate J1–J3 | ✅ 正例召回；E-1 收緊後一般提醒（警衛）不誤觸 |
| 8 | 不能安全駕駛 | 他昨天喝了酒之後還自己開車回家，半路撞到路邊電線桿。 | public_danger | 「服用酒類，不能安全駕駛動力交通工具而駕駛之犯行」；「不能安全駕駛，係抽象危險犯，並不以發生具體危險為必要」 | pubdanger J1–J3 | ✅ 正例召回 |
| 9 | 跟蹤騷擾 | 分手後他連續一週每天到我家樓下等我，我已經明確拒絕見面。 | stalking（E-2：需接近＋頻率＋「違反其意願」事實） | 「對特定人反覆或持續為違反其意願…盯梢、守候、尾隨或其他類似方式接近特定人之住所、居所、學校、工作場所」 | stalking J1–J3 | ✅ 正例召回；同事等人近鄰負例不誤觸 |
| 10 | 強盜 | 他對著我說「不交出錢包就捅你」，然後強行把我的手機搶走跑掉。 | robbery（＋intimidation 惡害通知候選；D1 後不再帶侵占／竊盜） | 「以施用強暴、脅迫、藥劑、催眠術或他法等手段而奪取或使人交付財物為構成要件」 | robbery J1–J3 | ✅ 正例召回；E-4 收緊後純威脅無取財不誤觸 |
| 11 | 妨害公務 | 交通警察要我配合酒精測試，我推開他並大聲罵他，阻止他執行職務。 | obstruction | 「對於公務員依法執行職務時，施強暴脅迫為要件…須出於妨害公務之犯意」（刑法 §135 第 1 項） | obstruct J1–J3 | ✅ 正例召回；E-3 收緊後單純辱罵／拒配合不誤觸 |

### 5-a. 人工審查（2026-10-20）近鄰負例錨點（precision）

E 輪版本五反例誤列、E2 輪修正後全部不誤觸，並已固化為回歸測試
`NEAR_MISS_CASES` / `test_near_miss_statute_elements_do_not_create_candidates`：

| 負例 | 缺可言的區辨事實 | E 輪 | E2 輪 |
|---|---|---|---|
| 警衛值勤提醒「晚上要小心」 | §305 惡害通知（只有一般提醒） | ❌ 誤觸 intimidation | ✅ 不觸發 |
| 同事每天在公司等吃飯 | 跟騷法 §3 違反其意願 | ❌ 誤觸 stalking | ✅ 不觸發 |
| 拍照抱怨＋大聲罵警察 | §135 第 1 項 強暴脅迫 | ❌ 誤觸 obstruction | ✅ 不觸發 |
| 威脅公開手機照片 | §328 取財／使人交付 | ❌ 誤觸 robbery | ✅ 不觸發 |
| 會計說客戶不還欠款 | §335 受託持有之他人之物 | ❌ 誤觸 embezzlement | ✅ 不觸發 |

### 探針邊界複驗（E 輪 18 句，全符；E2 輪再驗仍全符）
| 探針句 | 預期 | 實際 |
|---|---|---|
| 恐嚇 V1/V2（小心一點／不敢出門） | intimidation 命中 | ✅ |
| 恐嚇否定句（沒有恐嚇我的意思） | 不觸發 | ✅ |
| 恐嚇新聞句 | bank 關鍵字「恐嚇」直接命中（既有行為，bank 凍結不動） | ✅ |
| 跟蹤 V1/V2/V5（一週每天／門口徘徊／職場等待） | stalking 命中 | ✅ |
| 跟蹤新聞句 / 快遞干擾句 | 不觸發（exclude 生效） | ✅ |
| 搶刀逼現金（robbery-knife） | robbery 命中（E-4 修） | ✅ |
| 妨害公務兩句 | obstruction 命中（E-3 修） | ✅ |
| 侵占「轉入自己帳戶、花用、拒不返還」 | embezzlement 命中（E-5 修） | ✅ |

## 6. 修改清單（E 輪原版 → E2 輪依人工審查修正版；question_bank.json 零變更）

> 下表白底各行為 **E 輪原版**（2026-10-20 人工審查全數 ✗，原文保留）；灰底「E2 修後」為依審查決策修正後現況（見 `e2_round_rules_py_review_notes.md`）。

**E 輪原版（已被 E2 輪修正覆蓋）：**

| 位置 | 修改內容（原版） | 對應差異（原版） | 生效端 |
|---|---|---|---|
| rules.py `_PHRASE_HINTS`（intimidation） | pattern1 補「小心一點／要你小心／會出事／不會放過你／會傷害／傷害你」；pattern2 補「很害怕／不敢出門／家門口／到我家／在門口／不告訴就傷害」；新增新聞類 exclude | intimidation V1/V2 落空 | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（stalking） | pattern1 補「守候／徘徊／守在／等候／等在／到我家／在門口／等在門口」；pattern2 保留頻率詞（反覆/一直/老是/多次/持續/每天/一週/連續）；exclude 補「包裹／外送／快遞／郵件／簽收／派送」 | stalking V1/V2/V5 落空 | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（obstruction，新增） | pattern1「公務員／警察／員警／交警／交通警察／執勤／依法執行／執行職務／查封／封印」；pattern2「推開／攔阻／撞開／阻止／拒絕配合／不配合／強暴／脅迫／毆打／揮打／辱罵／妨害」；exclude 新聞類 | obstruction 兩句落空 | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（robbery） | pattern1 補「威脅／持刀／兇器／行兇／刀械」 | robbery-knife 落空 | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（embezzlement，新增） | pattern1「保管／代管／代收／受託／業務上／出納／財務／會計」；pattern2「拒不返還／不還／占為己有／當作自己的／轉入自己帳戶／花用／侵吞」；exclude 新聞類 | 侵占意圖跡象落空 | NEED_REVIEW 候選層 |
| rules.py `_element_evidence_patterns`（line 130） | 不法所有意圖訊號補「花用／轉入自己帳戶／當作自己的／當成自己的／侵吞／據為己有」 | 書類強調「變易持有為所有」之意圖 | 可檢查元素信號 |

**E2 修後（人工核定 CHANGES_REQUESTED → 依 §305／跟騷法 §3／§135 第1項／§328／§335 收緊）：**

| 位置 | 修改內容（現況） | 對應審查項目 | 生效端 |
|---|---|---|---|
| rules.py `_PHRASE_HINTS`（intimidation） | 收緊為惡害通知具體清單；**刪除** 一般提醒／畏怖／位置詞（E-1 ✗ 修正） | E-1（警衛反例） | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（stalking） | 新增第三必備 pattern＝違反意願事實（拒絕／不要再…）（E-2 ✗ 修正） | E-2（同事等人反例） | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（obstruction） | pattern2 僅保留物理性強暴脅迫；**刪除** 阻止／拒絕配合／辱罵／妨害（E-3 ✗ 修正） | E-3（辱罵反例） | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（robbery） | pattern1＝手段／暴取動作；pattern2＝取財／使人交付；**刪除** 純威脅路徑（E-4 ✗ 修正） | E-4（威脅照片反例） | NEED_REVIEW 候選層 |
| rules.py `_PHRASE_HINTS`（embezzlement） | pattern1＝受託持有關係（**刪除職稱詞**）；pattern2＝變易持有（**刪除泛「不還」**）；exclude 補欠款／借款／貸款（E-5 ✗ 修正） | E-5（客戶欠款反例） | NEED_REVIEW 候選層 |
| rules.py `_element_evidence_patterns`（意圖訊號） | **回退**為僅 `("不法所有",)`，E 輪擴充全部撤銷（E-6 ✗：訊號非純展示，會改變 supported_count／suggested route／ELIGIBLE_CANDIDATE） | E-6 | 可檢查元素信號 |
| rules.py `_property_discriminators`（新增）＋ related 擴展閘門 | D1「B 修正版」三路區辨：theft＝未經同意取走／破壞原持有；embezzlement＝先前合法持有／受託＋變易持有；robbery＝強暴脅迫手段＋奪取或使人交付；缺區辨事實不新增，並撤銷 bank related 帶入的財物 id | D1（人工核定 B 修正版） | related 候選層（不動 crosswalk） |
| rules.py theft structural rule | 補反向語序「財物…遭取走」第一手命中，承接 D1 關閉污染路徑後的零候選破口 | D1 副作用修復 | 主要候選層 |
| `app/legal_semantic_corpus.py` | A-01／A-02／A-06／C-09／C-17 `expected_related` 依 D1 改為 `set()` | D1 行為變更之錨點更新 | corpus 回歸 |
| `docs/evidence/legal_retrieval_human_gate_packet.json` | runtime_surfaces app/rules.py sha 刷新 → `42f63e35…` | rules.py 變更的機械記帳 | hash 鏈節點 1 |
| `docs/evidence/hg_lr_01_provider_contract_review.json` | packet_sha256 刷新 → `9939e7a2…` | 同上 | hash 鏈節點 2 |
| `docs/evidence/hg_lr_02_privacy_security_review.json` | packet_sha256 與 provider_review_sha256 刷新 | 同上 | hash 鏈節點 3 |
| `docs/evidence/hg_rules_py_human_review_record.json` | target_sha256_at_review 機械刷新 → `42f63e35…`（歷史欄位未回填；審查決策另立 `hg_rules_py_e2_correction_record.json`） | 同上 | 審閱記錄目標版本 |

未執行：legal_route_crosswalk（人工審查狀態，禁止 agent 動；D1 已依「B 修正版」在程式碼層實作，crosswalk 人工審查狀態維持不變）。

## 7. 品質穩定性判定（E6 輪修訂）

- **E6 輪（2026-10-20 第五輪複審後）**：第五輪判定 `EXACT_REPRO_PASS / GENERAL_GATE_FAIL`——僅「從未」群納入全域否定標記 ✓；其餘四項 ✗（裸「拒絕過」未綁接觸對象、veto 未含「聲請停止執行」、「使人交付報告」未綁財物、`_sentence_bound_anchor` 未真正逐一列舉 act×anchor）。修復：頻率補語型「拒絕過」／veto 補聲請群／「使人交付」綁定財物對象（hint／gate／D1 契約合一）／`_sentence_bound_anchor` 重寫為逐一列舉配對。修復版 rules.py `9360d5b5…`，pytest 391 passed、前端 22/22。P1 裁定 A（動態 ID 遮罩＋資產 hash 綁定＋重擷取＋擴充覆蓋）；P2 裁定 A（去重／英譯確認／AI_* 映射／跨案件汙染清理後重新抽樣）。勾選項見 `review/1/e2_round_rules_py_review_notes.md` 的 E6 輪修訂區段。

- 決定性：全套 pytest **391 passed**（含 test_legal_retrieval_human_gate_packet hash 鏈自檢＋新增近鄰負例測試）；探針 18 句邊界全符；前端錯誤測試 22/22。
- 正例召回：11 章正例均召回對應主要候選（recall 錨點維持）。
- precision 錨點：人工審查五近鄰負例（§5-a）不誤觸，已固化為回歸測試。
- **已撤回之表述**：E 輪「全 11 章品質通過、無反向矛盾」不成立（人工審查以負例證明 E 輪 precision 缺口）；本報告不再作此宣稱。法律要件完整性（是否涵蓋各章應問之要件）尚無系統性負例覆蓋，待人工複審。
- 限制：PSUE 查詢需必填驗證碼，未繞過，限制已登記（與 HG-LR-01 DISCOVERY_ONLY_SCHEMA_UNKNOWN 一致）；TLR 逐字引文的官方原文一致性仍 UNKNOWN（本輪未逐一重開 33 份原文）。
- D1：已依人工核定「B 修正版」三路區辨實作完成（程式碼層）；crosswalk 未動。

## 附錄：本報告引用之 bundle citation_ids（全部在 allowed_citations 內）

theft: J1, J2, J3 ／ embezzle: J1, J2, J3 ／ fraud: J1, J2, J3 ／ injury: J1, J2, J3 ／ insult: J1, J2, J3 ／ damage: J1, J2, J3 ／ intimidate: J1, J2, J3 ／ pubdanger: J1, J2, J3 ／ stalking: J1, J2, J3 ／ robbery: J1, J2, J3 ／ obstruct: J1, J2, J3

bundle 原始檔：Windows `%TEMP%\tlr2_*.json`（未入 repo，避免 review-only 資料混進 codebase）。

本報告僅為**品質對照與候選修改建議**，不端任何正式法律服務結論、不得接 runtime、不得作為 Gate 2 任何改動編排證據。
