// 可同時於 Node（CommonJS）與瀏覽器（掛載至 window.RF.<Name>）載入。
//
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.RF = root.RF || {};
    root.RF.analyzer = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
"use strict";

/* ============================================================
   詞彙表
   ============================================================ */

// 可辨識之主體（姓名、角色、稱謂）
const SUBJECT_TOKENS = [
  "被害人", "行為人", "涉嫌人", "○○", "某甲", "某乙", "王", "李", "陳", "林", "黃", "張",
  "男子", "女子", "少年", "少女", "本人", "雙方", "店家", "店員", "朋友", "同事", "鄰居",
];

// 指代用語：出現時若此前未建立對應主體，視為指代不明
const REFERENTIAL_TOKENS = [
  "他", "她", "它", "其", "該人", "該男子", "該女子", "該女", "該男", "對方", "雙方",
  "二人", "三人", "他們", "她們", "兩人", "三人以上", "某人", "該批", "該車",
];

// 已交付之表徵
const DELIVERED_TOKENS = [
  "已交付", "交付了", "交出", "交給", "付給", "交付財物", "收下", "交予", "把財物交",
  "將財物交", "被迫交付", "交付給", "交予對方",
];

// 已取走之表徵
const TAKEN_TOKENS = [
  "取走", "拿走", "搶走", "奪走", "帶走", "取得財物", "取去", "取走了",
];

// 僅有要求／脅迫，未見交付之表徵
const DEMAND_ONLY_TOKENS = [
  "要求", "逼", "命令", "叫", "強迫", "威脅", "恐嚇", "持刀", "拿刀", "持械",
  "要你交", "要對方交", "伸手", "拉扯",
];

// 存在被害人之表徵
const VICTIM_TOKENS = [
  "被害人", "被害", "受害", "遭", "被搶", "被偷", "損失", "受傷", "報警", "報案", "告訴",
];
// 明確無被害人之表徵（查獲、持有、攜帶等）
const NO_VICTIM_TOKENS = [
  "查獲", "現場查獲", "持有", "攜帶", "現行犯", "起出", "扣押", "搜索", "無人報案",
];
// 已破獲／到案之表徵
const SOLVED_TOKENS = [
  "破獲", "查獲", "到案", "說明", "現行犯", "移送", "拘捕", "逮捕", "偵辦", "帶回",
];

/* ============================================================
   工具
   ============================================================ */
function splitSentences(text) {
  return String(text || "")
    .split(/[。；;\n]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

function hasAny(text, tokens) {
  return tokens.some((t) => text.includes(t));
}

/** 找出所有命中之標籤 */
function matchTags(text, tags) {
  const hit = [];
  for (const t of tags || []) {
    if (t && text.includes(t)) hit.push(t);
  }
  return hit;
}

/** 依標籤命中數量給出證據強度 */
function evidenceStrength(hitCount, totalTags) {
  if (!totalTags) return 0;
  return hitCount / totalTags;
}

/* ============================================================
   1. 事實解構
   ============================================================ */
function decomposeFacts(factsText) {
  const sentences = splitSentences(factsText);
  const text = sentences.join("。");

  // （a）主體
  const subjectHits = matchTags(text, SUBJECT_TOKENS);
  // （b）指代
  const referentialHits = [];
  for (const token of REFERENTIAL_TOKENS) {
    let idx = text.indexOf(token);
    while (idx !== -1) {
      // 前文是否已有可辨識之主體（出現在此指代之前）
      const before = text.slice(0, idx);
      const hasAntecedent = SUBJECT_TOKENS.some((s) => before.includes(s));
      referentialHits.push({ token, index: idx, has_antecedent: hasAntecedent });
      idx = text.indexOf(token, idx + token.length);
    }
  }
  const ambiguousRefs = referentialHits.filter((r) => !r.has_antecedent);
  const subjectIdentified = subjectHits.length > 0 && ambiguousRefs.length === 0;

  // （c）交付狀態
  let deliveryStatus = "未敘明";
  let deliveryEvidence = null;
  if (hasAny(text, DELIVERED_TOKENS)) {
    deliveryStatus = "已交付";
    deliveryEvidence = DELIVERED_TOKENS.filter((t) => text.includes(t));
  } else if (hasAny(text, TAKEN_TOKENS)) {
    deliveryStatus = "已取走";
    deliveryEvidence = TAKEN_TOKENS.filter((t) => text.includes(t));
  } else if (hasAny(text, DEMAND_ONLY_TOKENS)) {
    deliveryStatus = "僅有要求或脅迫，交付與否未敘明";
    deliveryEvidence = DEMAND_ONLY_TOKENS.filter((t) => text.includes(t));
  }

  // （e）有無被害人、是否已破獲（供條陳模板選擇）
  let hasVictim = null;
  let hasVictimEvidence = [];
  if (hasAny(text, NO_VICTIM_TOKENS)) {
    hasVictim = false;
    hasVictimEvidence = NO_VICTIM_TOKENS.filter((t) => text.includes(t));
  } else if (hasAny(text, VICTIM_TOKENS)) {
    hasVictim = true;
    hasVictimEvidence = VICTIM_TOKENS.filter((t) => text.includes(t));
  }
  const isSolved = hasAny(text, SOLVED_TOKENS);
  const isSolvedEvidence = SOLVED_TOKENS.filter((t) => text.includes(t));

  // （f）事實面向之已敘明情形（用於缺口清單）
  const aspectTags = {
    人: SUBJECT_TOKENS,
    事: ["然後", "之後", "事後", "當時", "接著", "隨後", "期間", "經過", "過程", "發生了", "做了", "開始", "結束", "後來", "隨即", "緊接", "才", "就", "隨即"],
    時: ["時", "分", "點", "早上", "中午", "下午", "晚上", "凌晨", "昨天", "今日", "今日凌晨"],
    地: ["路", "街", "巷", "號", "店", "超商", "公園", "住處", "停車場", "騎樓", "市場"],
    物: ["現金", "手機", "財物卡", "皮夾", "包", "珠寶", "金紙", "車", "機車", "戒指", "金錶"],
    價值: ["價值", "多少元", "價格", "估價", "新臺幣", "幾元", "幾千", "幾百", "金額", "市價"],
    補強: ["監視器", "影像", "錄影", "照片", "目擊", "證人", "報警", "報案", "調閱", "扣押", "搜索", " whereabouts", "通聯紀錄"],
    行為: ["持", "拿", "打", "推", "拉", "掐", "吼", "威脅", "要求", "交付", "搶", "偷", "拿著"],
    因果: ["因為", "所以", "導致", "因此", "致使", "後來", "之後", "反應", "抗拒", "害怕", "嚇"],
  };
  const aspects = {};
  for (const [k, toks] of Object.entries(aspectTags)) {
    aspects[k] = matchTags(text, toks);
  }

  return {
    sentences,
    text,
    subject: { identified: subjectIdentified, hits: subjectHits },
    referential: { total: referentialHits.length, ambiguous: ambiguousRefs },
    delivery: { status: deliveryStatus, evidence: deliveryEvidence },
    victim: { present: hasVictim, evidence: hasVictimEvidence },
    solved: { yes: isSolved, evidence: isSolvedEvidence },
    aspects,
  };
}

/* ============================================================
   2. 候選罪名群組（不排序、不認定）
   ============================================================ */
function buildCandidates(flow, decomp) {
  const text = decomp.text;
  const statutes = flow.statu_decomposition || flow.statute_decomposition || [];

  // 逐一法條計算要件命中情形
  // fact_patterns 為「事實偵測用」情境詞彙（敘事中出現即表示該面向已受陳述）；
  // search_tags 為「法源檢索用」判準詞彙。兩者用途不同，檢核以 fact_patterns 為準。
  const perStatute = statutes.map((st) => {
    const elements = (st.elements || []).map((el) => {
      const patterns = el.fact_patterns && el.fact_patterns.length ? el.fact_patterns : el.search_tags;
      const hits = matchTags(text, patterns);
      const legalHits = matchTags(text, el.search_tags);
      return {
        element_id: el.element_id,
        element_name: el.element_name,
        hits,
        legal_hits: legalHits,
        critical: el.critical !== false,
        // 區別性要件：命中該項方足以將此法條列為候選。
        // 共用性要件（如不法所有之意圖、他人動產）於多數財產犯罪通用，命中不具區別力。
        discriminating: el.discriminating === true,
      };
    });
    const anyHit = elements.some((e) => e.hits.length > 0);
    const anyDiscHit = elements.some((e) => e.discriminating && e.hits.length > 0);
    return { statute: st, elements, anyHit, anyDiscHit };
  });

  // 依 reasoning_paths 觸發（事實型態 → 候選法條）
  // 路徑須其 required_triggers 全部受陳述，方視為該事實型態已具備。
  const pathTriggers = (flow.reasoning_paths || []).map((p) => {
    const required = p.required_triggers || [];
    const trigHits = (p.trigger_elements || []).map((eid) => {
      let el = null;
      for (const x of perStatute) {
        const found = x.elements.find((e) => e.element_id === eid);
        if (found) { el = found; break; }
      }
      return { element_id: eid, hits: el ? el.hits : [] };
    });
    const requiredStatus = required.map((eid) => {
      const h = trigHits.find((t) => t.element_id === eid);
      return { element_id: eid, hit: !!(h && h.hits.length > 0) };
    });
    const triggered = requiredStatus.length > 0 && requiredStatus.every((r) => r.hit);
    const partialCount = requiredStatus.filter((r) => r.hit).length;
    return { path: p, trigHits, requiredStatus, triggered, partialCount };
  });

  const candidateIds = new Set();
  const triggeredPaths = [];
  for (const p of pathTriggers) {
    if (!p.triggered) continue;
    triggeredPaths.push(p);
    for (const cs of p.path.candidate_statutes || []) candidateIds.add(cs);
  }
  // 命中區別性要件者亦列為候選
  for (const x of perStatute) {
    if (x.anyDiscHit) candidateIds.add(x.statute.statute_id);
  }

  // 候選不足兩個時（事實尚未成形），取區別性要件命中數最多之路徑之候選法條，
  // 以維持對照性；此時報告將顯示大量要件明顯欠缺。
  let fallbackUsed = false;
  if (candidateIds.size < 2) {
    const ranked = [...pathTriggers].sort((a, b) => b.partialCount - a.partialCount);
    for (const p of ranked) {
      if (candidateIds.size >= 2) break;
      for (const cs of p.path.candidate_statutes || []) candidateIds.add(cs);
      fallbackUsed = true;
    }
  }
  if (candidateIds.size < 2) {
    for (const x of perStatute) candidateIds.add(x.statute.statute_id);
  }

  // 依 statute_decomposition 原順序輸出（不排序）
  const candidates = statutes
    .filter((st) => candidateIds.has(st.statute_id))
    .map((st) => {
      const x = perStatute.find((y) => y.statute.statute_id === st.statute_id);
      return { statute_id: st.statute_id, statute_name: st.statute_name, elements: x.elements };
    });

  return { candidates, perStatute, pathTriggers, triggeredPaths, fallbackUsed };
}

/* ============================================================
   3. 四庫模擬檢索
   ============================================================ */
function simulateRetrieval(flow, candidates) {
  const e2j = flow.element_to_judgment || [];
  const candidateElementIds = new Set();
  for (const c of candidates) for (const e of c.elements) candidateElementIds.add(e.element_id);

  const 法規 = {
    library: "法規",
    status: "simulated",
    note: "資料來源：lawbank_reasoning_flow.json 之 statute_decomposition（已登錄之刑法條文）。",
    items: candidates.map((c) => ({
      ref: c.statute_id,
      title: c.statute_name,
      detail: "已登錄條文與要件結構。",
    })),
  };

  const 判解 = {
    library: "判解",
    status: "simulated",
    note: "資料來源：element_to_judgment 之要旨欄位。裁判書全文未取得（fyjud 需另行授權），故僅有要旨。",
    items: [],
  };
  for (const grp of e2j) {
    if (!candidateElementIds.has(grp.element_id)) continue;
    for (const ref of grp.judgment_refs || []) {
      判解.items.push({
        ref: ref.case_ref,
        title: ref.case_ref,
        detail: (ref.holding_summary || "").slice(0, 80),
        element_id: grp.element_id,
      });
    }
  }

  const 函釋 = {
    library: "行政函釋",
    status: "needs_external",
    note: "法源行政函釋單元與本罪群相關之要旨尚未取得（見 extraction_gaps 之 g_fint），本項為待外部檢索。",
    items: [],
  };

  const 論著 = {
    library: "法學論著",
    status: "simulated",
    note: "資料來源：issue_to_scholarship 之 source_hint 所載論著條目。",
    items: (flow.issue_to_scholarship || []).map((s) => ({
      ref: (s.scholarship_views || [])[0]?.source_hint || "",
      title: s.issue,
      detail: (s.scholarship_views || []).map((v) => `${v.orientation}：${v.view}`).join(" / ").slice(0, 80),
    })),
  };

  return [法規, 判解, 函釋, 論著];
}

/* ============================================================
   4. 要件檢核
   ============================================================ */
function checkElements(candidates, decomp) {
  const rows = [];
  for (const c of candidates) {
    for (const el of c.elements) {
      const critical = el.critical !== false;
      let status;
      let reason;
      if (el.hits.length > 0) {
        // 有命中：若命中所在語句含未解析之指代，則無法判斷
        const ambiguous = decomp.referential.ambiguous.length > 0;
        status = ambiguous ? "因指代不明無法判斷" : "已具備";
        reason = ambiguous
          ? "要件詞彙出現，但敘事中存在未解析之指代，須先確認所指何人。"
          : "要件詞彙已出現於敘事。";
      } else if (critical) {
        status = "明顯欠缺";
        reason = "基本要件詞彙未見於敘事。";
      } else {
        status = "待確認";
        reason = "非基本要件，敘事未提及，尚待確認。";
      }
      rows.push({
        statute_id: c.statute_id,
        statute_name: c.statute_name,
        element_id: el.element_id,
        element_name: el.element_name,
        critical,
        status,
        reason,
        matched_tags: el.hits,
      });
    }
  }
  return rows;
}

/* ============================================================
   5. 缺口清單與 gap_list
   ============================================================ */
function buildGaps(elementRows, decomp, candidates) {
  const gaps = [];
  let n = 0;
  const nextId = () => "g" + ++n;

  // （a）主體不明
  if (!decomp.subject.identified) {
    gaps.push({
      gap_id: nextId(),
      type: "fact",
      description: decomp.referential.ambiguous.length
        ? "敘事中出現未解析之指代（" +
            decomp.referential.ambiguous.map((r) => r.token).slice(0, 4).join("、") +
            "），須確認各指代所指之人及其角色。"
        : "敘事未載明明確之行為人或被害人，須補明當事人身分。",
      affects_elements: Array.from(
        new Set(
          elementRows
            .filter((r) => r.status === "因指代不明無法判斷")
            .map((r) => r.element_id)
        )
      ),
      question_hint:
        "請說明本案當事人為何人（姓名或可辨識之特徵），以及其與本事件之關係。",
    });
  }

  // （b）交付狀態不明
  if (decomp.delivery.status === "僅有要求或脅迫，交付與否未敘明" || decomp.delivery.status === "未敘明") {
    const affects = elementRows
      .filter((r) => ["e_taking_or_delivery", "e_delivery_by_fear", "e_irresistible"].includes(r.element_id))
      .map((r) => r.element_id);
    gaps.push({
      gap_id: nextId(),
      type: "fact",
      description:
        "財物交付或取走之狀態未敘明（" +
        decomp.delivery.status +
        "），須確認是否已交付、取走或未交付。",
      affects_elements: affects,
      question_hint: "當時財物實際上是由你交付、由對方取走，還是尚未交付？請說明。",
    });
  }

  // （c）要件缺口：逐項說明「缺哪項事實導致哪個要件無法判斷」
  for (const r of elementRows) {
    if (r.status === "已具備") continue;
    const affects = [r.element_id];
    if (r.status === "明顯欠缺") {
      gaps.push({
        gap_id: nextId(),
        type: "element",
        description:
          "缺少「" +
          r.element_name +
          "」之具體事實（" +
          r.element_id +
          "），致 " +
          r.statute_id +
          " 之該要件無法判斷。",
        affects_elements: affects,
        question_hint: `請就「${r.element_name}」補充說明具體經過。`,
      });
    } else if (r.status === "待確認") {
      gaps.push({
        gap_id: nextId(),
        type: "element",
        description:
          "「" +
          r.element_name +
          "」（" +
          r.element_id +
          "）之情形未敘明，致 " +
          r.statute_id +
          " 該要件尚待確認。",
        affects_elements: affects,
        question_hint: `請確認「${r.element_name}」之情形為何。`,
      });
    } else {
      gaps.push({
        gap_id: nextId(),
        type: "element",
        description:
          "「" +
          r.element_name +
          "」（" +
          r.element_id +
          "）因敘事中指代不明而無法判斷，致 " +
          r.statute_id +
          " 該要件之認定前提不足。",
        affects_elements: affects,
        question_hint: "請說明前述各指代所指之人及其角色。",
      });
    }
  }

  // （d）事實面向缺口（人、事、時、地、物、行為、因果）
  const ASPECT_QUESTIONS = {
    人: "請說明本案當事人之身分、關係與可辨識之特徵。",
    事: "請依時間順序說明事件經過。",
    時: "請說明事件發生的日期與時點。",
    地: "請說明事件發生的地點。",
    物: "請逐項說明涉及之財物名稱、數量與特徵。",
    價值: "請說明各項財物的價值及其認定依據。",
    補強: "請說明可佐證本事件之情形（監視器、影像、目擊者、報案紀錄等）及其保存狀況。",
    行為: "請說明雙方當時所為之具體動作或言語。",
    因果: "請說明事件之原因與結果間之關聯。",
  };
  for (const [aspect, hits] of Object.entries(decomp.aspects)) {
    if (hits.length > 0) continue;
    gaps.push({
      gap_id: nextId(),
      type: "fact",
      description: "事實面向「" + aspect + "」於敘事中未見記載。",
      affects_elements: [],
      question_hint: ASPECT_QUESTIONS[aspect] || "請補充說明。",
    });
  }

  return gaps;
}

/* ============================================================
   6. Markdown 組裝
   ============================================================ */
function mdEscape(s) {
  return String(s == null ? "" : s).replace(/\|/g, "\\|");
}

function buildMarkdown(flow, facts, decomp, cand, retrieval, elementRows, gaps) {
  const L = [];
  const caseId = facts.case_id || "(未命名案件)";

  L.push("# 分析報告：" + caseId);
  L.push("");
  L.push("> 本報告僅列示候選法律路徑與事實缺口，不作任何罪名成立與否之認定。候選罪名未經排序。");
  L.push("");

  // 警示
  const warnings = [];
  if (!decomp.subject.identified) {
    warnings.push(
      "【主體不明警示】敘事中之當事人未明確或存在未解析之指代，須先確認所指何人及各人角色。"
    );
  }
  if (
    decomp.delivery.status === "僅有要求或脅迫，交付與否未敘明" ||
    decomp.delivery.status === "未敘明"
  ) {
    warnings.push(
      "【階段不明警示】財物交付或取走之狀態未敘明，須先確認事件進行至何階段。"
    );
  }
  if (warnings.length) {
    for (const w of warnings) L.push("> " + w);
    L.push("");
  }

  // 1. 事實解構表
  L.push("## 一、事實解構");
  L.push("");
  L.push("| 面向 | 狀態 | 敘事內容 |");
  L.push("|---|---|---|");
  const st = decomp.subject;
  L.push(
    "| 主體 | " +
      (st.identified ? "已敘明" : "指代不明或未敘明") +
      " | " +
      mdEscape(st.hits.join("、") || "—") +
      " |"
  );
  L.push(
    "| 交付狀態 | " +
      mdEscape(decomp.delivery.status) +
      " | " +
      mdEscape((decomp.delivery.evidence || []).join("、") || "—") +
      " |"
  );
  for (const [aspect, hits] of Object.entries(decomp.aspects)) {
    L.push(
      "| " +
        aspect +
        " | " +
        (hits.length ? "已敘明" : "未敘明") +
        " | " +
        mdEscape(hits.join("、") || "—") +
        " |"
    );
  }
  L.push("");

  // 2. 候選罪名群組
  L.push("## 二、候選罪名群組（未排序）");
  L.push("");
  L.push("| 條號 | 罪名 | 觸發之區別性要件 | 說明 |");
  L.push("|---|---|---|---|");
  for (const c of cand.candidates) {
    const trig = c.elements.filter((e) => e.discriminating && e.hits.length > 0).map((e) => e.element_id);
    L.push(
      "| " +
        mdEscape(c.statute_id) +
        " | " +
        mdEscape(c.statute_name) +
        " | " +
        mdEscape(trig.join("、") || "—") +
        " | 候選，未排序，未作成立與否之判斷 |"
    );
  }
  L.push("");
  L.push("> 候選群組依 flow.statute_decomposition 之原順序列出，未依可能性排序。");
  L.push("");
  if (cand.triggeredPaths.length) {
    L.push(
      "> 已符合之事實型態（reasoning_paths）：" +
        cand.triggeredPaths.map((p) => p.path.path_id).join("、") +
        "。"
    );
  } else {
    L.push(
      "> 目前尚無完整符合之 reasoning_paths 事實型態；候選群組係依部分命中之型態補足，請先釐清事實後重新分析。"
    );
  }
  L.push("");

  // 3. 四庫模擬檢索
  L.push("## 三、四庫模擬檢索");
  L.push("");
  L.push("| 資料庫 | 狀態 | 檢索筆數 | 說明 |");
  L.push("|---|---|---|---|");
  for (const r of retrieval) {
    L.push(
      "| " +
        r.library +
        " | " +
        (r.status === "simulated" ? "模擬檢索（資料已登錄）" : "需外部檢索") +
        " | " +
        r.items.length +
        " | " +
        mdEscape(r.note) +
        " |"
    );
  }
  L.push("");

  // 4. 要件檢核表
  L.push("## 四、要件檢核");
  L.push("");
  L.push("| 條號 | 要件 | 性質 | 狀態 | 判斷理由 | 命中詞彙 |");
  L.push("|---|---|---|---|---|---|");
  for (const r of elementRows) {
    L.push(
      "| " +
        mdEscape(r.statute_id) +
        " | " +
        mdEscape(r.element_name) +
        "（" +
        mdEscape(r.element_id) +
        "） | " +
        (r.critical ? "基本要件" : "非基本要件") +
        " | " +
        r.status +
        " | " +
        mdEscape(r.reason) +
        " | " +
        mdEscape(r.matched_tags.join("、") || "—") +
        " |"
    );
  }
  L.push("");

  // 5. 缺口清單
  L.push("## 五、缺口清單");
  L.push("");
  L.push("| gap_id | 類型 | 缺口描述 | 影響之要件 | 建議問法 |");
  L.push("|---|---|---|---|---|");
  for (const g of gaps) {
    L.push(
      "| " +
        mdEscape(g.gap_id) +
        " | " +
        (g.type === "fact" ? "事實缺口" : "要件缺口") +
        " | " +
        mdEscape(g.description) +
        " | " +
        mdEscape(g.affects_elements.join("、") || "—") +
        " | " +
        mdEscape(g.question_hint || "—") +
        " |"
    );
  }
  L.push("");

  // 6. gap_list JSON
  L.push("## 六、gap_list");
  L.push("");
  L.push("```json");
  L.push(
    JSON.stringify(
      gaps.map((g) => ({
        gap_id: g.gap_id,
        type: g.type,
        description: g.description,
        affects_elements: g.affects_elements,
      })),
      null,
      2
    )
  );
  L.push("```");
  L.push("");

  return L.join("\n");
}

/* ============================================================
   主入口
   ============================================================ */
function analyze(facts, flow) {
  const factsText = facts.facts_text || facts.text || "";
  const decomp = decomposeFacts(factsText);
  const cand = buildCandidates(flow, decomp);
  const retrieval = simulateRetrieval(flow, cand.candidates);
  const elementRows = checkElements(cand.candidates, decomp);
  const gaps = buildGaps(elementRows, decomp, cand.candidates);
  const markdown = buildMarkdown(flow, facts, decomp, cand, retrieval, elementRows, gaps);

  return {
    markdown,
    gap_list: gaps.map((g) => ({
      gap_id: g.gap_id,
      type: g.type,
      description: g.description,
      affects_elements: g.affects_elements,
      question_hint: g.question_hint,
    })),
    meta: {
      case_id: facts.case_id || null,
      subject_identified: decomp.subject.identified,
      delivery_status: decomp.delivery.status,
      ambiguous_referentials: decomp.referential.ambiguous.map((r) => r.token),
      candidate_statutes: cand.candidates.map((c) => c.statute_id),
      has_victim: decomp.victim.present,
      has_victim_evidence: decomp.victim.evidence,
      is_solved: decomp.solved.yes,
      is_solved_evidence: decomp.solved.evidence,
      element_count: elementRows.length,
      gap_count: gaps.length,
      triggered_paths: cand.triggeredPaths.map((p) => p.path.path_id),
      candidate_fallback_used: !!cand.fallbackUsed,
      partial_path_matches: cand.pathTriggers
        .filter((p) => !p.triggered && p.partialCount > 0)
        .map((p) => ({ path_id: p.path.path_id, matched: p.partialCount, required: p.requiredStatus.length })),
    },
  };
}

return { analyze, decomposeFacts, buildCandidates, checkElements, buildGaps, buildMarkdown };
});
