# 條陳與問句產出：case_ambiguous

> 本文件為模擬產出，內容待承辦人核實。所有罪名均為候選，不認定犯罪成立。

## 一、模板選擇

| 項目 | 內容 |
|---|---|
| 模板 | 被害人條陳（victim_report） |
| 選擇依據 | 有被害人且未破獲 → 被害人條陳（受理案由） |
| 有無被害人 | 有 |
| 是否已破獲 | 否 |
| 主體是否特定 | 否 |

## 二、問句清單

### 對相對人（被害人）（10 句）

| id | question | maps_to | note |
|---|---|---|---|
| GEN-C-01 | 當時對方以何種方式、施加於何處？你的身體或心理感受到什麼樣的狀態？ | e_irresistible、e_coercion、gap_category:行為、e_robbery_intent、e_delivery_by_fear | 對應缺口 g1；範本 q_relative_coercion_degree；並對應缺口 g2；並對應缺口 g4 |
| GEN-C-02 | 當時（具體情境），你看到／聽到什麼？請依順序說明。 | e_coercion、gap_category:事 | 對應缺口 g3；範本 q_relative_perception |
| GEN-C-03 | 遭取走或被要求交付的財物有哪些？請逐項說明名稱、數量、特徵與價值認定依據。 | e_taking_or_delivery、e_robbery_intent、gap_category:物 | 對應缺口 g5；範本 q_relative_property；並對應缺口 g6；並對應缺口 g9；並對應缺口 g13 |
| GEN-C-04 | 對方當時說了什麼或做了什麼？請逐項說明其內容、表達方式與發生順序。 | e_threat、e_coercion、gap_category:行為 | 對應缺口 g7；範本 q_relative_threat_content |
| GEN-C-05 | 當時你的處境為何？有哪些選項是你當下仍能選擇的？ | e_delivery_by_fear、e_irresistible、gap_category:因果 | 對應缺口 g8；範本 q_relative_freedom_of_choice |
| GEN-C-06 | 你對行為人的身分或可供辨識的特徵掌握哪些資料？請說明。 | gap_category:人 | 對應缺口 g10；範本 q_relative_suspect_id |
| GEN-C-07 | 事件的時間與地點為何？請說明最初、最後及各重要節點。 | gap_category:時、gap_category:地 | 對應缺口 g11；範本 q_relative_timeline；並對應缺口 g12 |
| GEN-C-08 | 請說明各項財物的價值及其認定依據。 | gap:g14 | 對應缺口 g14；依缺口建議問法 |
| GEN-C-09 | 現場或附近有哪些可佐證之處（如監視器、影像等）？請說明其位置與保存情形。 | gap_category:補強 | 對應缺口 g15；範本 q_relative_evidence |
| GEN-C-10 | 請用自己的話說明事情從開始到結束的經過。 | gap_category:事 | 角色基礎問句（每次詢問必問） |

## 三、條陳填充表

| 欄位 ID | 標籤 | 填充內容 | 狀態 |
|---|---|---|---|
| header_office | 報告單位抬頭 | ○○所 | 保留原文佔位 |
| case_reason | 受理案由 | （主體待確認） | 主體待確認 |
| occurred_time | 發生時間 | （待補） | 未敘明，待補 |
| occurred_location | 發生地點 | （待補） | 未敘明，待補 |
| report_time | 報案時間 | （待補） | 未敘明，待補 |
| case_summary | 案情摘要 | （主體待確認） | 主體待確認 |
| follow_up_header | 後續處置標題 | 六、後續處置： | 固定文字 |
| filing_report | 依規定陳報 | （一）依規定陳報（證明單案號：、婦幼案號：、165案號：) | 固定文字（案號空位保留原樣） |
| jurisdiction | 本案管轄 | （主體待確認） | 主體待確認 |
| handling_officer | 處理員警 | （待補） | 未敘明，待補 |

## 四、匯出用純文字

```text
被害人條陳
○○所報告
一、受理案由：（主體待確認）
二、發生時間：（待補）
三、發生地點：（待補）
四、報案時間：（待補）
五、案情摘要：
（主體待確認）
六、後續處置：
（一）依規定陳報（證明單案號：、婦幼案號：、165案號：)
（二）本案管轄：（主體待確認）
（三）處理員警：警員 （待補）。

模擬填充，不構成正式文書。
所有罪名均為候選，不認定犯罪成立。
```
