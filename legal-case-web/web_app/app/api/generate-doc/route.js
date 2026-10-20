import { Document, Packer, Paragraph, TextRun } from "docx";
import { VICTIM_GENERIC, SUSPECT_GENERIC } from "../../../lib/templates";
import { buildMemo } from "../../../lib/memoTemplates";

export async function POST(req) {
  try {
    const body = await req.json();
    const templateType = body.templateType || "victim";
    const caseSummary = typeof body.caseSummary === "string" ? body.caseSummary : "";
    const supplemental = Array.isArray(body.supplemental) ? body.supplemental : [];
    const caseNumber = body.caseNumber && typeof body.caseNumber === "object" ? body.caseNumber : {};

    if (!["victim", "suspect", "suspect-transfer"].includes(templateType)) {
      return Response.json({ error: "不支援的筆錄範本。" }, { status: 400, headers: { "Cache-Control": "no-store" } });
    }
    if (!caseSummary.trim() || supplemental.length > 100 || supplemental.some((item) =>
      !item || typeof item.q !== "string" || typeof item.a !== "string"
    )) {
      return Response.json({ error: "案情摘要或問答資料格式不正確。" }, { status: 400, headers: { "Cache-Control": "no-store" } });
    }

    const isSuspect = templateType === "suspect" || templateType === "suspect-transfer";
    const generic = isSuspect ? SUSPECT_GENERIC : VICTIM_GENERIC;
    const requiredHeading = isSuspect ? "通用涉嫌人筆錄" : "通用被害人筆錄";

    const memo = buildMemo(templateType, caseSummary, caseNumber);

    const doc = new Document({
      sections: [{
        properties: {},
        children: [
          new Paragraph({ children: [new TextRun({ text: `JUDICIAL2 ${requiredHeading} (自動生成)`, bold: true })], spacing: { after: 120 } }),
          new Paragraph({ children: [new TextRun({ text: "案情摘要：" })], spacing: { after: 120 } }),
          new Paragraph({ children: [new TextRun({ text: caseSummary })], spacing: { after: 240 } }),
          new Paragraph({ children: [new TextRun({ text: "一、通用問句 (範本內容保留)" })], spacing: { after: 120 } }),
          ...generic.map((q) => new Paragraph({ children: [new TextRun({ text: `問：${q}` })], spacing: { after: 60 } })),
          new Paragraph({ children: [new TextRun({ text: "答：" })], spacing: { after: 240 } }),
          new Paragraph({ children: [new TextRun({ text: "二、補充/核心問句與回答" })], spacing: { after: 120 } }),
          ...supplemental.flatMap(({ q, a }) => [
            new Paragraph({ children: [new TextRun({ text: `問：${q}` })], spacing: { after: 60 } }),
            new Paragraph({ children: [new TextRun({ text: `答：${a || "（未填）"}` })], spacing: { after: 120 } }),
          ]),
          new Paragraph({ children: [new TextRun({ text: "以上內容是否為你自由意識下所為之陳述？" })], spacing: { after: 120 } }),
          new Paragraph({ children: [new TextRun({ text: "以上所述是否實在，有無其他意見補充？" })], spacing: { after: 240 } }),
          new Paragraph({ children: [new TextRun({ text: "受詢問人：________  詢問人：________  紀錄人：________" })], spacing: { after: 240 } }),
          new Paragraph({ children: [new TextRun({ text: "------------- 區隔線 -------------" })], spacing: { after: 240 } }),
          new Paragraph({ children: [new TextRun({ text: "條陳：", bold: true })], spacing: { after: 120 } }),
          ...memo.split("\n").map((line) => new Paragraph({ children: [new TextRun({ text: line })], spacing: { after: 60 } })),
        ],
      }],
    });

    const buffer = await Packer.toBuffer(doc);
    const base64 = buffer.toString("base64");
    return Response.json({ ok: true, base64 }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "文件產生失敗，請檢查輸入資料後重試。" }, { status: 500, headers: { "Cache-Control": "no-store" } });
  }
}
