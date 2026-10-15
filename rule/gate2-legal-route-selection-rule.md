# Gate 2 法律路由人工選擇規則

## 目的

候選罪章與法律路由是不同層次的資料。候選罪章是調查方向；法律路由是該方向下需人工檢查的條文、程序或保護措施範圍。兩者不得合併成單一欄位，也不得被表示為犯罪成立結論。

## 寫入契約

1. `offense_ids` 與 `legal_route_ids` 必須在同一次 Gate 2 操作中原子提交。
2. 承辦人必須明確確認已檢視法律路由；未確認時不得建立問句。
3. 法律路由可以選零個、單個或多個，但須遵守 crosswalk 的 `selection_policy`。
4. 系統必須拒絕未知、重複、已排除、停用或不屬於已選候選罪章的 route ID。
5. 舊案件缺少路由資料時標示 `LEGACY_MISSING`，不得自動猜測或補選。

## 問句覆蓋聲明

目前 child route 僅作為問句的法律脈絡快照。問句仍來自 parent offense 題包，因此必須同時標示：

- `coverage_status: PARENT_PACK_ONLY`
- `coverage_claim: NONE`
- `human_review_required: true`

在特定 child route 的題包完成來源核對、角色核對、非引導性檢查及人工審核前，不得標示為 route-specific coverage complete。

## 失效與快照

- Gate 1 事實、案件角色、候選罪章或 crosswalk 版本變更時，路由檢視及其下游問答必須失效。
- 路由改選時不得沿用舊回答。
- Gate 2 核准時須再次驗證 route 與 parent offense 的關係及 crosswalk 版本。
- 正式筆錄快照應保存當時的候選罪章、法律路由、crosswalk 版本及覆蓋聲明。

## 人工 Gate

法律路由選擇只代表承辦人確認後續調查範圍，不代表構成要件成立、犯罪成立、程序一定適用或專用公司範本已完成載入。
