# 分析報告：case_partial

> 本報告僅列示候選法律路徑與事實缺口，不作任何罪名成立與否之認定。候選罪名未經排序。

> 【階段不明警示】財物交付或取走之狀態未敘明，須先確認事件進行至何階段。

## 一、事實解構

| 面向 | 狀態 | 敘事內容 |
|---|---|---|
| 主體 | 已敘明 | 被害人、○○、林、男子 |
| 交付狀態 | 未敘明 | — |
| 人 | 已敘明 | 被害人、○○、林、男子 |
| 事 | 已敘明 | 事後、隨後、就 |
| 時 | 已敘明 | 晚上 |
| 地 | 已敘明 | 市場 |
| 物 | 未敘明 | — |
| 價值 | 未敘明 | — |
| 補強 | 已敘明 | 報警 |
| 行為 | 已敘明 | 打、推 |
| 因果 | 已敘明 | 害怕 |

## 二、候選罪名群組（未排序）

| 條號 | 罪名 | 觸發之區別性要件 | 說明 |
|---|---|---|---|
| §328_I | 強盜罪 | e_coercion、e_irresistible | 候選，未排序，未作成立與否之判斷 |
| §346_I | 恐嚇取財罪 | e_delivery_by_fear | 候選，未排序，未作成立與否之判斷 |

> 候選群組依 flow.statute_decomposition 之原順序列出，未依可能性排序。

> 目前尚無完整符合之 reasoning_paths 事實型態；候選群組係依部分命中之型態補足，請先釐清事實後重新分析。

## 三、四庫模擬檢索

| 資料庫 | 狀態 | 檢索筆數 | 說明 |
|---|---|---|---|
| 法規 | 模擬檢索（資料已登錄） | 2 | 資料來源：lawbank_reasoning_flow.json 之 statute_decomposition（已登錄之刑法條文）。 |
| 判解 | 模擬檢索（資料已登錄） | 42 | 資料來源：element_to_judgment 之要旨欄位。裁判書全文未取得（fyjud 需另行授權），故僅有要旨。 |
| 行政函釋 | 需外部檢索 | 0 | 法源行政函釋單元與本罪群相關之要旨尚未取得（見 extraction_gaps 之 g_fint），本項為待外部檢索。 |
| 法學論著 | 模擬檢索（資料已登錄） | 3 | 資料來源：issue_to_scholarship 之 source_hint 所載論著條目。 |

## 四、要件檢核

| 條號 | 要件 | 性質 | 狀態 | 判斷理由 | 命中詞彙 |
|---|---|---|---|---|---|
| §328_I | 強暴、脅迫、藥劑、催眠術或他法（e_coercion） | 基本要件 | 已具備 | 要件詞彙已出現於敘事。 | 打、推、攔住 |
| §328_I | 至使不能抗拒（e_irresistible） | 基本要件 | 已具備 | 要件詞彙已出現於敘事。 | 害怕 |
| §328_I | 取他人之物或使其交付（e_taking_or_delivery） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |
| §328_I | 不法所有之意圖（e_robbery_intent） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |
| §346_I | 恐嚇（e_threat） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |
| §346_I | 使人交付（基於畏懼）（e_delivery_by_fear） | 基本要件 | 已具備 | 要件詞彙已出現於敘事。 | 害怕、怕 |
| §346_I | 不法所有之意圖（e_robbery_intent） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |

## 五、缺口清單

| gap_id | 類型 | 缺口描述 | 影響之要件 | 建議問法 |
|---|---|---|---|---|
| g1 | 事實缺口 | 財物交付或取走之狀態未敘明（未敘明），須確認是否已交付、取走或未交付。 | e_irresistible、e_taking_or_delivery、e_delivery_by_fear | 當時財物實際上是由你交付、由對方取走，還是尚未交付？請說明。 |
| g2 | 要件缺口 | 缺少「取他人之物或使其交付」之具體事實（e_taking_or_delivery），致 §328_I 之該要件無法判斷。 | e_taking_or_delivery | 請就「取他人之物或使其交付」補充說明具體經過。 |
| g3 | 要件缺口 | 缺少「不法所有之意圖」之具體事實（e_robbery_intent），致 §328_I 之該要件無法判斷。 | e_robbery_intent | 請就「不法所有之意圖」補充說明具體經過。 |
| g4 | 要件缺口 | 缺少「恐嚇」之具體事實（e_threat），致 §346_I 之該要件無法判斷。 | e_threat | 請就「恐嚇」補充說明具體經過。 |
| g5 | 要件缺口 | 缺少「不法所有之意圖」之具體事實（e_robbery_intent），致 §346_I 之該要件無法判斷。 | e_robbery_intent | 請就「不法所有之意圖」補充說明具體經過。 |
| g6 | 事實缺口 | 事實面向「物」於敘事中未見記載。 | — | 請逐項說明涉及之財物名稱、數量與特徵。 |
| g7 | 事實缺口 | 事實面向「價值」於敘事中未見記載。 | — | 請說明各項財物的價值及其認定依據。 |

## 六、gap_list

```json
[
  {
    "gap_id": "g1",
    "type": "fact",
    "description": "財物交付或取走之狀態未敘明（未敘明），須確認是否已交付、取走或未交付。",
    "affects_elements": [
      "e_irresistible",
      "e_taking_or_delivery",
      "e_delivery_by_fear"
    ]
  },
  {
    "gap_id": "g2",
    "type": "element",
    "description": "缺少「取他人之物或使其交付」之具體事實（e_taking_or_delivery），致 §328_I 之該要件無法判斷。",
    "affects_elements": [
      "e_taking_or_delivery"
    ]
  },
  {
    "gap_id": "g3",
    "type": "element",
    "description": "缺少「不法所有之意圖」之具體事實（e_robbery_intent），致 §328_I 之該要件無法判斷。",
    "affects_elements": [
      "e_robbery_intent"
    ]
  },
  {
    "gap_id": "g4",
    "type": "element",
    "description": "缺少「恐嚇」之具體事實（e_threat），致 §346_I 之該要件無法判斷。",
    "affects_elements": [
      "e_threat"
    ]
  },
  {
    "gap_id": "g5",
    "type": "element",
    "description": "缺少「不法所有之意圖」之具體事實（e_robbery_intent），致 §346_I 之該要件無法判斷。",
    "affects_elements": [
      "e_robbery_intent"
    ]
  },
  {
    "gap_id": "g6",
    "type": "fact",
    "description": "事實面向「物」於敘事中未見記載。",
    "affects_elements": []
  },
  {
    "gap_id": "g7",
    "type": "fact",
    "description": "事實面向「價值」於敘事中未見記載。",
    "affects_elements": []
  }
]
```
