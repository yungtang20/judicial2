# 分析報告：case_ambiguous

> 本報告僅列示候選法律路徑與事實缺口，不作任何罪名成立與否之認定。候選罪名未經排序。

> 【主體不明警示】敘事中之當事人未明確或存在未解析之指代，須先確認所指何人及各人角色。
> 【階段不明警示】財物交付或取走之狀態未敘明，須先確認事件進行至何階段。

## 一、事實解構

| 面向 | 狀態 | 敘事內容 |
|---|---|---|
| 主體 | 指代不明或未敘明 | — |
| 交付狀態 | 未敘明 | — |
| 人 | 未敘明 | — |
| 事 | 已敘明 | 後來、就 |
| 時 | 未敘明 | — |
| 地 | 未敘明 | — |
| 物 | 未敘明 | — |
| 價值 | 未敘明 | — |
| 補強 | 未敘明 | — |
| 行為 | 已敘明 | 搶 |
| 因果 | 已敘明 | 後來、嚇 |

## 二、候選罪名群組（未排序）

| 條號 | 罪名 | 觸發之區別性要件 | 說明 |
|---|---|---|---|
| §328_I | 強盜罪 | e_irresistible | 候選，未排序，未作成立與否之判斷 |
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
| §328_I | 強暴、脅迫、藥劑、催眠術或他法（e_coercion） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |
| §328_I | 至使不能抗拒（e_irresistible） | 基本要件 | 因指代不明無法判斷 | 要件詞彙出現，但敘事中存在未解析之指代，須先確認所指何人。 | 嚇、不敢、不敢動、僵住 |
| §328_I | 取他人之物或使其交付（e_taking_or_delivery） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |
| §328_I | 不法所有之意圖（e_robbery_intent） | 基本要件 | 因指代不明無法判斷 | 要件詞彙出現，但敘事中存在未解析之指代，須先確認所指何人。 | 搶、要搶 |
| §346_I | 恐嚇（e_threat） | 基本要件 | 明顯欠缺 | 基本要件詞彙未見於敘事。 | — |
| §346_I | 使人交付（基於畏懼）（e_delivery_by_fear） | 基本要件 | 因指代不明無法判斷 | 要件詞彙出現，但敘事中存在未解析之指代，須先確認所指何人。 | 嚇、不敢 |
| §346_I | 不法所有之意圖（e_robbery_intent） | 基本要件 | 因指代不明無法判斷 | 要件詞彙出現，但敘事中存在未解析之指代，須先確認所指何人。 | 搶、要搶 |

## 五、缺口清單

| gap_id | 類型 | 缺口描述 | 影響之要件 | 建議問法 |
|---|---|---|---|---|
| g1 | 事實缺口 | 敘事中出現未解析之指代（他、對方、對方），須確認各指代所指之人及其角色。 | e_irresistible、e_robbery_intent、e_delivery_by_fear | 請說明本案當事人為何人（姓名或可辨識之特徵），以及其與本事件之關係。 |
| g2 | 事實缺口 | 財物交付或取走之狀態未敘明（未敘明），須確認是否已交付、取走或未交付。 | e_irresistible、e_taking_or_delivery、e_delivery_by_fear | 當時財物實際上是由你交付、由對方取走，還是尚未交付？請說明。 |
| g3 | 要件缺口 | 缺少「強暴、脅迫、藥劑、催眠術或他法」之具體事實（e_coercion），致 §328_I 之該要件無法判斷。 | e_coercion | 請就「強暴、脅迫、藥劑、催眠術或他法」補充說明具體經過。 |
| g4 | 要件缺口 | 「至使不能抗拒」（e_irresistible）因敘事中指代不明而無法判斷，致 §328_I 該要件之認定前提不足。 | e_irresistible | 請說明前述各指代所指之人及其角色。 |
| g5 | 要件缺口 | 缺少「取他人之物或使其交付」之具體事實（e_taking_or_delivery），致 §328_I 之該要件無法判斷。 | e_taking_or_delivery | 請就「取他人之物或使其交付」補充說明具體經過。 |
| g6 | 要件缺口 | 「不法所有之意圖」（e_robbery_intent）因敘事中指代不明而無法判斷，致 §328_I 該要件之認定前提不足。 | e_robbery_intent | 請說明前述各指代所指之人及其角色。 |
| g7 | 要件缺口 | 缺少「恐嚇」之具體事實（e_threat），致 §346_I 之該要件無法判斷。 | e_threat | 請就「恐嚇」補充說明具體經過。 |
| g8 | 要件缺口 | 「使人交付（基於畏懼）」（e_delivery_by_fear）因敘事中指代不明而無法判斷，致 §346_I 該要件之認定前提不足。 | e_delivery_by_fear | 請說明前述各指代所指之人及其角色。 |
| g9 | 要件缺口 | 「不法所有之意圖」（e_robbery_intent）因敘事中指代不明而無法判斷，致 §346_I 該要件之認定前提不足。 | e_robbery_intent | 請說明前述各指代所指之人及其角色。 |
| g10 | 事實缺口 | 事實面向「人」於敘事中未見記載。 | — | 請說明本案當事人之身分、關係與可辨識之特徵。 |
| g11 | 事實缺口 | 事實面向「時」於敘事中未見記載。 | — | 請說明事件發生的日期與時點。 |
| g12 | 事實缺口 | 事實面向「地」於敘事中未見記載。 | — | 請說明事件發生的地點。 |
| g13 | 事實缺口 | 事實面向「物」於敘事中未見記載。 | — | 請逐項說明涉及之財物名稱、數量與特徵。 |
| g14 | 事實缺口 | 事實面向「價值」於敘事中未見記載。 | — | 請說明各項財物的價值及其認定依據。 |
| g15 | 事實缺口 | 事實面向「補強」於敘事中未見記載。 | — | 請說明可佐證本事件之情形（監視器、影像、目擊者、報案紀錄等）及其保存狀況。 |

## 六、gap_list

```json
[
  {
    "gap_id": "g1",
    "type": "fact",
    "description": "敘事中出現未解析之指代（他、對方、對方），須確認各指代所指之人及其角色。",
    "affects_elements": [
      "e_irresistible",
      "e_robbery_intent",
      "e_delivery_by_fear"
    ]
  },
  {
    "gap_id": "g2",
    "type": "fact",
    "description": "財物交付或取走之狀態未敘明（未敘明），須確認是否已交付、取走或未交付。",
    "affects_elements": [
      "e_irresistible",
      "e_taking_or_delivery",
      "e_delivery_by_fear"
    ]
  },
  {
    "gap_id": "g3",
    "type": "element",
    "description": "缺少「強暴、脅迫、藥劑、催眠術或他法」之具體事實（e_coercion），致 §328_I 之該要件無法判斷。",
    "affects_elements": [
      "e_coercion"
    ]
  },
  {
    "gap_id": "g4",
    "type": "element",
    "description": "「至使不能抗拒」（e_irresistible）因敘事中指代不明而無法判斷，致 §328_I 該要件之認定前提不足。",
    "affects_elements": [
      "e_irresistible"
    ]
  },
  {
    "gap_id": "g5",
    "type": "element",
    "description": "缺少「取他人之物或使其交付」之具體事實（e_taking_or_delivery），致 §328_I 之該要件無法判斷。",
    "affects_elements": [
      "e_taking_or_delivery"
    ]
  },
  {
    "gap_id": "g6",
    "type": "element",
    "description": "「不法所有之意圖」（e_robbery_intent）因敘事中指代不明而無法判斷，致 §328_I 該要件之認定前提不足。",
    "affects_elements": [
      "e_robbery_intent"
    ]
  },
  {
    "gap_id": "g7",
    "type": "element",
    "description": "缺少「恐嚇」之具體事實（e_threat），致 §346_I 之該要件無法判斷。",
    "affects_elements": [
      "e_threat"
    ]
  },
  {
    "gap_id": "g8",
    "type": "element",
    "description": "「使人交付（基於畏懼）」（e_delivery_by_fear）因敘事中指代不明而無法判斷，致 §346_I 該要件之認定前提不足。",
    "affects_elements": [
      "e_delivery_by_fear"
    ]
  },
  {
    "gap_id": "g9",
    "type": "element",
    "description": "「不法所有之意圖」（e_robbery_intent）因敘事中指代不明而無法判斷，致 §346_I 該要件之認定前提不足。",
    "affects_elements": [
      "e_robbery_intent"
    ]
  },
  {
    "gap_id": "g10",
    "type": "fact",
    "description": "事實面向「人」於敘事中未見記載。",
    "affects_elements": []
  },
  {
    "gap_id": "g11",
    "type": "fact",
    "description": "事實面向「時」於敘事中未見記載。",
    "affects_elements": []
  },
  {
    "gap_id": "g12",
    "type": "fact",
    "description": "事實面向「地」於敘事中未見記載。",
    "affects_elements": []
  },
  {
    "gap_id": "g13",
    "type": "fact",
    "description": "事實面向「物」於敘事中未見記載。",
    "affects_elements": []
  },
  {
    "gap_id": "g14",
    "type": "fact",
    "description": "事實面向「價值」於敘事中未見記載。",
    "affects_elements": []
  },
  {
    "gap_id": "g15",
    "type": "fact",
    "description": "事實面向「補強」於敘事中未見記載。",
    "affects_elements": []
  }
]
```
