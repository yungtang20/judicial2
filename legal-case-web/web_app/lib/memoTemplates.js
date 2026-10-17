export const MEMO_TEMPLATES = {
  victim: `被害人條陳
○○所報告
一、受理案由：○○○（受理）
二、發生時間：年月日時分
三、發生地點：
四、報案時間：年月日時分
五、案情摘要：{{SUMMARY}}

六、後續處置：
（一）依規定陳報（證明單案號：{{CASE_NO}}、婦幼案號：{{VICTIM_CODE}}、165案號：{{FRAUD_NO}}）
（二）本案管轄：
（三）處理員警：警員 ○○○。`,

  "suspect": `涉嫌人條陳，有被害人版
○○所報告
一、受理案由：○○○（破獲）
二、發生時間：年月日時分
三、發生地點：
四、報案時間：年月日時分
五、破獲時間：年月日時分
六、案情摘要：{{SUMMARY}}

七、後續處置：
（一）依規定陳報（證明單案號：{{CASE_NO}}、婦幼案號：{{VICTIM_CODE}}、165案號：{{FRAUD_NO}}）
（二）警方依規定受理後，調閱店家及公家道路監視器影像，尋線找到嫌疑人並聯繫嫌疑人至所說明，嫌於警詢筆錄中表示，其他內容詳如筆錄，函送偵查隊續辦。
（三）處理員警：警員 ○○○。`,

  "suspect-transfer": `涉嫌人條陳，無被害人版
○○○所報告
一、查獲案由：○○○（破獲）
二、查獲時間：年月日時分
三、查獲地點：年月日時分
四、案情摘要：{{SUMMARY}}

五、處理員警：警員 ○○○。`
};

export function buildMemo(templateType, caseSummary, caseNo = {}) {
  const tpl = MEMO_TEMPLATES[templateType] || MEMO_TEMPLATES.victim;
  const summary = String(caseSummary || "").slice(0, 100);
  const caseNoText = [
    caseNo.caseNo ? `證明單案號：${caseNo.caseNo}` : "證明單案號：",
    caseNo.victimCode ? `婦幼案號：${caseNo.victimCode}` : "婦幼案號：",
    caseNo.fraudNo ? `165案號：${caseNo.fraudNo}` : "165案號：",
  ].join("、 ");
  return tpl
    .replace("{{SUMMARY}}", summary)
    .replace("{{CASE_NO}}", caseNo.caseNo || "")
    .replace("{{VICTIM_CODE}}", caseNo.victimCode || "")
    .replace("{{FRAUD_NO}}", caseNo.fraudNo || "")
    .replace("（證明單案號：、、165案號：）", `(${caseNoText})`);
}
