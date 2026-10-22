// 產生 lawbank_reasoning_flow.json（階段一 4.1 五層關聯）
// 輸入：lb_clean.json（法源原始擷取）
// 輸出：reasoning-flow/data/lawbank_reasoning_flow.json
const fs = require("fs");
const path = require("path");

const RAW_DIR = process.env.RAW_DIR || require("path").join(__dirname, "..", "raw");
const CLEAN_FILE = process.env.LB_CLEAN || require("path").join(RAW_DIR, "lb_clean.json");
const OUT =
  process.env.OUT_FILE || require("path").join(__dirname, "..", "data", "lawbank_reasoning_flow.json");
const clean = JSON.parse(fs.readFileSync(CLEAN_FILE, "utf8"));

/* ---------- 工具 ---------- */
const byTag = (t) => clean.judgments.filter((j) => (j.tags || []).includes(t));
const keyHolding = (j) => (j.holding_key || [])[0] || null;

/** 由判解字號推算西元年（民國年 + 1911）。台灣裁判字號之「年度」為民國年。 */
function toADYear(caseRef) {
  const m = (caseRef || "").match(/(\d{2,3})年度/);
  if (!m) return null;
  const roc = Number(m[1]);
  // 三位數（如 111、110）為民國年；兩位數（如 86、99）為民國年
  return roc + 1911;
}

/** 從判解中挑出要旨含指定關鍵片語者，依「最高法院優先、精選裁判優先、要旨完整度」排序 */
function pick(judgments, matcher, limit) {
  const hits = judgments.filter((j) => {
    const t = (j.holding_key || []).join(" ") + " " + (j.holding_snippet || "");
    return matcher(t);
  });
  const scored = hits.map((j) => {
    let score = 0;
    if (j.case_ref && /^最高法院/.test(j.case_ref)) score += 100;
    if (j.case_ref && /臺灣高等法院|高雄高分院|臺中高分院|臺灣高等法院.*分院/.test(j.case_ref)) score += 40;
    if (j.status && /精選裁判/.test(j.status)) score += 20;
    if (j.status && /已確定/.test(j.status)) score += 10;
    score += Math.min(20, ((j.holding_key || [])[0] || "").length / 20);
    return { ...j, _score: score };
  });
  scored.sort((a, b) => b._score - a._score);
  return scored.slice(0, limit).map((j) => ({
    case_ref: j.case_ref,
    case_ref_text: j.case_ref_text,
    holding_summary: keyHolding(j),
    court_level: (j.case_ref || "").match(/^[^0-9]+/)?.[0]?.trim() || null,
    year: toADYear(j.case_ref),
    year_roc: (j.case_ref || "").match(/(\d{2,3})年度/)?.[1] || null,
    status: j.status,
    cited_count: j.cited_count,
    source_url: j.case_link,
    status_flag: "extracted",
  }));
}

/* ---------- 1. 法條層 → 構成要件 ---------- */
const statuteOf = (lno) => clean.statutes.find((s) => s.lno === lno);

const statuteDecomposition = [
  {
    statute_id: "§320_I",
    statute_name: "竊盜罪",
    source_url: statuteOf("320")?.url,
    article_text: statuteOf("320")?.article_text,
    elements: [
      {
        element_id: "e_theft_intent",
        discriminating: false,
        fact_patterns: ["想要","要拿","想拿","打算","企圖","想據為己有","想佔有","想取得","意圖"],
        critical: true,
        element_name: "不法所有之意圖",
        definition: "意圖為自己或第三人不法之所有。",
        search_tags: ["不法所有", "意圖", "竊取"],
      },
      {
        element_id: "e_theft_taking",
        discriminating: true,
        fact_patterns: ["偷","竊","摸走","未經同意","未經被害人同意","趁被害人不在","趁沒人注意","順手拿","摸走後"],
        critical: true,
        element_name: "竊取他人動產",
        definition: "未使用強暴、脅迫等方法，於被害人不知情下取走其動產。",
        search_tags: ["竊取", "動產", "秘密", "不被察覺"],
      },
      {
        element_id: "e_theft_object",
        discriminating: false,
        fact_patterns: ["現金","手機","財物卡","皮夾","包","珠寶","金錶","物品","財物","手提包"],
        critical: true,
        element_name: "客體為他人動產",
        definition: "標的須為他人之動產。",
        search_tags: ["動產", "他人", "財物"],
      },
    ],
  },
  {
    statute_id: "§321_I",
    statute_name: "竊盜罪之加重事由",
    source_url: statuteOf("321")?.url,
    article_text: statuteOf("321")?.article_text,
    elements: [
      {
        element_id: "e_agg_circumstance",
        discriminating: false,
        fact_patterns: ["攜帶凶器","攜帶兇器","隨身帶著刀","口袋有刀","背包有刀","腰間","藏刀","凶器","三人以上","三人","三人共同","住宅內","住家內","房子裡","毀越","門窗","鐵窗","災害之際","颱風","火車上","捷運上","公車上","車站"],
        critical: false,
        element_name: "加重情狀（§321 I 各款）",
        definition: "犯竊盜罪而有 §321 I 所列情形之一（住宅或建築物內、攜帶兇器、三人以上共同、毀越門窗或安全設備、災害之際或公共運輸工具內等）。",
        search_tags: ["攜帶兇器", "住宅", "三人以上", "毀越", "災害之際", "公共運輸工具"],
      },
    ],
  },
  {
    statute_id: "§325_I",
    statute_name: "搶奪罪",
    source_url: statuteOf("325")?.url,
    article_text: statuteOf("325")?.article_text,
    elements: [
      {
        element_id: "e_robbery_intent",
        discriminating: false,
        fact_patterns: ["搶","要搶","想搶","打算搶","圖謀","想拿","想取","貪","想賺","打算拿"],
        critical: true,
        element_name: "不法所有之意圖",
        definition: "意圖為自己或第三人不法之所有。",
        search_tags: ["不法所有", "意圖"],
      },
      {
        element_id: "e_robbery_snatch",
        discriminating: true,
        fact_patterns: ["突然","趁","順手","拔走","扯下","抓了就跑","不知不覺","一把","猛然","隨手"],
        critical: true,
        element_name: "乘人不備公然掠取",
        definition: "以突然之手段乘人不備公然掠取他人動產，未對人施以強暴、脅迫致不能抗拒。",
        search_tags: ["乘人不備", "公然", "掠取", "搶奪"],
      },
    ],
  },
  {
    statute_id: "§326_I",
    statute_name: "搶奪罪之加重事由",
    source_url: statuteOf("326")?.url,
    article_text: statuteOf("326")?.article_text,
    elements: [
      {
        element_id: "e_agg_circumstance",
        discriminating: false,
        fact_patterns: ["攜帶凶器","攜帶兇器","隨身帶著刀","口袋有刀","背包有刀","腰間","藏刀","凶器","三人以上","三人","三人共同","住宅內","住家內","房子裡","毀越","門窗","鐵窗","災害之際","颱風","火車上","捷運上","公車上","車站"],
        critical: false,
        element_name: "加重情狀（§321 I 各款）",
        definition: "犯搶奪罪而有 §321 I 各款情形之一。",
        search_tags: ["攜帶兇器", "住宅", "三人以上"],
      },
    ],
  },
  {
    statute_id: "§328_I",
    statute_name: "強盜罪",
    source_url: statuteOf("328")?.url,
    article_text: statuteOf("328")?.article_text,
    elements: [
      {
        element_id: "e_coercion",
        discriminating: true,
        fact_patterns: ["持刀","拿刀","揮刀","刀指","棍","鐵棍","打","拳","踢","推","拉住","掐","抱住","堵住","攔住","威脅","恐嚇","吼","兇器","拿出刀","亮刀"],
        critical: true,
        element_name: "強暴、脅迫、藥劑、催眠術或他法",
        definition: "以強暴、脅迫、藥劑、催眠術或他法等不法方法對被害人施壓。",
        search_tags: ["強暴", "脅迫", "藥劑", "催眠術", "他法", "手持", "持刀"],
      },
      {
        element_id: "e_irresistible",
        discriminating: true,
        fact_patterns: ["害怕","恐懼","嚇","不敢","不敢動","不敢反抗","不敢抗拒","不能動","動不了","跑不了","求助","喊叫","畏縮","發抖","僵住","無法抗拒","心生畏懼","嚇到","腿軟","不敢出聲"],
        critical: true,
        element_name: "至使不能抗拒",
        definition:
          "所謂「至使不能抗拒」，係指行為人所施用之強暴、脅迫等不法行為，就當時之具體事實，予以客觀之判斷，足使被害人身體上或精神上達於不能或顯難抗拒之程度而言；不以被害人之主觀意思為準，亦不以被害人完全喪失抗拒能力為要件。",
        search_tags: ["不能抗拒", "顯難抗拒", "意思自由", "具體事實", "客觀判斷"],
      },
      {
        element_id: "e_taking_or_delivery",
        discriminating: true,
        fact_patterns: ["拿走","取走","搶走","交出","交付","遞給","遞上","塞給","交給","搶去","交予","放到他手上","放到桌上","遞過去"],
        critical: true,
        element_name: "取他人之物或使其交付",
        definition: "以強制方法取走他人之物，或使被害人交付他人之物。",
        search_tags: ["取他人之物", "使其交付", "交付", "取走", "強取"],
      },
      {
        element_id: "e_robbery_intent",
        discriminating: false,
        fact_patterns: ["搶","要搶","想搶","打算搶","圖謀","想拿","想取","貪","想賺","打算拿"],
        critical: true,
        element_name: "不法所有之意圖",
        definition: "意圖為自己或第三人不法之所有。",
        search_tags: ["不法所有", "意圖"],
      },
    ],
  },
  {
    statute_id: "§328_II",
    statute_name: "強盜罪（取得財產上不法利益）",
    source_url: statuteOf("328")?.url,
    elements: [
      {
        element_id: "e_illegal_benefit",
        discriminating: true,
        fact_patterns: ["利益","得利","讓第三人","脫離","好處","便宜"],
        critical: false,
        element_name: "得財產上不法之利益或使第三人得之",
        definition: "以前項方法得財產上不法之利益或使第三人得之者，亦同。",
        search_tags: ["財產上不法利益", "第三人得之"],
      },
    ],
  },
  {
    statute_id: "§329",
    statute_name: "準強盜罪",
    source_url: statuteOf("329")?.url,
    article_text: statuteOf("329")?.article_text,
    elements: [
      {
        element_id: "e_preceding_offense",
        discriminating: true,
        fact_patterns: ["先前偷","之前偷","剛才偷","原本要偷","先前搶","之前搶","剛才搶","原本要搶","為防止","怕被抓","為掩護","為躲藏","不想被發現"],
        critical: true,
        element_name: "前行為須為竊盜或搶奪",
        definition: "竊盜或搶奪。",
        search_tags: ["竊盜", "搶奪", "前行為"],
      },
      {
        element_id: "e_motive",
        discriminating: true,
        fact_patterns: ["贓物","怕被追","怕被抓","怕警察","要逃","逃跑","躲起來","藏起來","湮滅","銷毀","掩護","脫免","怕被抓到"],
        critical: true,
        element_name: "動機為防護贓物、脫免逮捕或湮滅罪證",
        definition: "因防護贓物、脫免逮捕或湮滅罪證。",
        search_tags: ["防護贓物", "脫免逮捕", "湮滅罪證"],
      },
      {
        element_id: "e_ond_the_spot",
        discriminating: true,
        fact_patterns: ["當場對","現場對","立刻對","隨即對","馬上對","轉身對","回頭對","搶回","爭奪","追上去","當下推","隨即打","立刻打","轉身打"],
        critical: true,
        element_name: "當場施以強暴脅迫",
        definition: "而當場施以強暴脅迫者。",
        search_tags: ["當場", "強暴脅迫", "追捕"],
      },
    ],
  },
  {
    statute_id: "§330_I",
    statute_name: "強盜罪之加重事由",
    source_url: statuteOf("330")?.url,
    article_text: statuteOf("330")?.article_text,
    elements: [
      {
        element_id: "e_agg_circumstance",
        discriminating: false,
        fact_patterns: ["攜帶凶器","攜帶兇器","隨身帶著刀","口袋有刀","背包有刀","腰間","藏刀","凶器","三人以上","三人","三人共同","住宅內","住家內","房子裡","毀越","門窗","鐵窗","災害之際","颱風","火車上","捷運上","公車上","車站"],
        critical: false,
        element_name: "加重情狀（§321 I 各款）",
        definition: "犯強盜罪而有 §321 I 各款情形之一。",
        search_tags: ["攜帶兇器", "住宅", "三人以上", "毀越"],
      },
    ],
  },
  {
    statute_id: "§346_I",
    statute_name: "恐嚇取財罪",
    source_url: statuteOf("346")?.url,
    article_text: statuteOf("346")?.article_text,
    elements: [
      {
        element_id: "e_threat",
        discriminating: true,
        fact_patterns: ["揚言","威脅","恐嚇","說要","喊你","罵","亮刀","亮出刀","拿著刀說","叫嚣","叫囂","說要報復","說要弄死"],
        critical: true,
        element_name: "恐嚇",
        definition:
          "所謂之「恐嚇」，係指以加害生命、身體、自由、名譽、財產之事通知他人，使其發生畏怖心理；其告知方式並無限制，無論口頭、書面、言語或肢體動作均屬之；且須在客觀上足以一般人產生畏怖心理。",
        search_tags: ["恐嚇", "畏怖", "惡害告知", "將來惡害", "威脅"],
      },
      {
        element_id: "e_delivery_by_fear",
        discriminating: true,
        fact_patterns: ["害怕","恐懼","嚇","畏懼","不敢","擔心","怕","驚恐","恐慌"],
        critical: true,
        element_name: "使人交付（基於畏懼）",
        definition: "以恐嚇使人將本人或第三人之物交付。",
        search_tags: ["使人交付", "交付", "心生畏懼", "恐懼"],
      },
      {
        element_id: "e_robbery_intent",
        discriminating: false,
        fact_patterns: ["搶","要搶","想搶","打算搶","圖謀","想拿","想取","貪","想賺","打算拿"],
        critical: true,
        element_name: "不法所有之意圖",
        definition: "意圖為自己或第三人不法之所有。",
        search_tags: ["不法所有", "意圖"],
      },
    ],
  },
];

/* ---------- 2. 要件層 → 判解層 ---------- */
const all = clean.judgments;

// 關鍵判解：指定其必置於哪個要件群，並以擷取到的要旨原文填入
const KEY_JUDGMENTS = {
  "最高法院111年度台上字2060號刑事判決": "e_irresistible",
  "最高法院86年度台上字5174號刑事判決": "e_delivery_by_fear",
  "最高法院104年度台上字290號刑事判決": "e_robbery_snatch",
  "最高法院107年度台上字586號刑事判決": "e_irresistible",
  "最高法院99年度台上字7594號刑事判決": "e_irresistible",
  "最高法院101年度台上字3376號刑事判決": "e_irresistible",
};

const elementToJudgment = [
  {
    element_id: "e_irresistible",
    judgment_refs: pick(all, (t) => t.includes("不能抗拒") && (t.includes("客觀") || t.includes("具體事實")), 12),
  },
  {
    element_id: "e_coercion",
    judgment_refs: pick(
      all,
      (t) =>
        (t.includes("強暴") || t.includes("脅迫") || t.includes("強制")) &&
        (t.includes("方法") || t.includes("手段") || t.includes("不法行為") || t.includes("施用")),
      6,
    ),
  },
  {
    element_id: "e_taking_or_delivery",
    judgment_refs: pick(
      all,
      (t) =>
        // 排除其他罪之判準（詐欺、侵占等）與搶奪之判準（另立要件）
        !t.includes("詐欺") &&
        !t.includes("侵占") &&
        !t.includes("使用竊盜") &&
        !t.includes("乘人不備") &&
        (t.includes("使人交付") ||
          t.includes("強取") ||
          t.includes("取他人之物") ||
          (t.includes("交付") && (t.includes("強盜") || t.includes("強取")))),
      6,
    ),
  },
  {
    element_id: "e_threat",
    judgment_refs: pick(all, (t) => t.includes("恐嚇") && (t.includes("畏懼") || t.includes("畏怖") || t.includes("惡害")), 8),
  },
  {
    element_id: "e_delivery_by_fear",
    judgment_refs: pick(all, (t) => t.includes("心生畏懼") || t.includes("心生畏怖") || t.includes("畏懼之程度"), 6),
  },
  {
    element_id: "e_robbery_intent",
    judgment_refs: pick(
      all,
      (t) =>
        // 判準要旨須同時含「意圖」與「不法所有」，且排除其他罪之判準
        (t.includes("意圖") || t.includes("意慾")) &&
        (t.includes("不法所有") || t.includes("不法之所有")) &&
        !t.includes("恐嚇") &&
        !t.includes("使用竊盜") &&
        !t.includes("詐欺"),
      5,
    ),
  },
  {
    element_id: "e_theft_taking",
    judgment_refs: pick(all, (t) => t.includes("竊取") || t.includes("使用竊盜"), 4),
  },
  {
    element_id: "e_robbery_snatch",
    judgment_refs: pick(all, (t) => t.includes("乘人不備") || t.includes("公然攫取"), 4),
  },
  {
    element_id: "e_ond_the_spot",
    judgment_refs: pick(all, (t) => t.includes("當場") && (t.includes("強暴") || t.includes("脅迫")), 4),
  },
  {
    element_id: "e_motive",
    judgment_refs: pick(all, (t) => t.includes("防護贓物") || t.includes("湮滅罪證") || t.includes("脫免逮捕"), 3),
    extraction_status: "needs_external",
    note: "本次以要件關鍵字擷取，未涵蓋準強盜（§329）之判解；此要件與判解之對應待另行擷取。",
  },
];

// 若某要件因排除律而無任何對應判解，誠實標記為 needs_external，不得放寬條件硬湊
for (const grp of elementToJudgment) {
  if (grp.judgment_refs.length === 0 && !grp.extraction_status) {
    grp.extraction_status = "needs_external";
    grp.note =
      "本次擷取之判解中未篩得可對應該要件之判準要旨；此要件與判解之對應待另行擷取或人工確認。";
  }
}

// 確保關鍵判解確實出現在其指定要件群（避免引用未登錄之字號）
{
  const allRefs = elementToJudgment.flatMap((g) => g.judgment_refs);
  for (const [cref, eid] of Object.entries(KEY_JUDGMENTS)) {
    if (allRefs.some((r) => r.case_ref === cref)) continue;
    const grp = elementToJudgment.find((g) => g.element_id === eid);
    const src = clean.judgments.find((j) => j.case_ref === cref);
    if (!grp || !src) {
      throw new Error("關鍵判解未擷取到：" + cref);
    }
    grp.judgment_refs.unshift({
      case_ref: cref,
      case_ref_text: src.case_ref_text,
      holding_summary: (src.holding_key || [])[0] || null,
      court_level: (cref.match(/^[^0-9]+/) || [""])[0].trim() || null,
      year: toADYear(cref),
      year_roc: (cref.match(/(\d{2,3})年度/) || [, ""])[1],
      status: src.status,
      cited_count: src.cited_count,
      source_url: src.case_link,
      status_flag: "extracted",
      is_key_judgment: true,
    });
  }
}

/* ---------- 3. 判解層 → 爭點層 ---------- */
// 爭點文字在此定義一次，judgment_to_issue 與 issue_to_scholarship 共用同一字串，以確保可逐字回溯
const ISSUE = {
  irresistible:
    "「至使不能抗拒」之判斷基準：應依當時具體事實為客觀判斷，以一般人處於同一情境時其意思自由是否受壓制為準，非以被害人主觀上是否覺得害怕為準。",
  robberyVsThreat:
    "強盜罪「不能抗拒」與恐嚇取財罪「心生畏懼」之區分：被害人尚有幾分自由意思、社會一般通念上僅心生畏怖而未達不能抗拒程度者，屬恐嚇取財而非強盜。",
  snatchVsRobbery:
    "搶奪與強盜之區分：乘人不備公然掠取為搶奪；施用強暴脅迫至使不能抗拒而取財者為強盜。",
};

const judgmentToIssue = [
  {
    case_ref: "最高法院111年度台上字2060號刑事判決",
    issue: ISSUE.irresistible,
    court_reasoning:
      "所謂「至使不能抗拒」，係指行為人所施用之強暴、脅迫等手段，就當時之具體事實，予以客觀之判斷，足使一般人身體上或精神上達於不能或顯難抗拒之程度而言，不以被害人之主觀意思為準，亦不以被害人完全喪失抗拒能力為要件。",
    factors: [
      "當時之具體事實（武器種類、距離、場合、被害人身心狀況）",
      "一般人置於同一情境時意思自由是否受壓制",
      "不以被害人主觀感受為準",
      "不要求被害人完全喪失抗拒能力，達顯難抗拒即足",
    ],
    case_ref_verified: true,
  },
  {
    case_ref: "最高法院86年度台上字5174號刑事判決",
    issue: ISSUE.robberyVsThreat,
    court_reasoning:
      "所稱之恐嚇，係指以危害通知他人，使該他人主觀上生畏怖之行為，此項危害之通知，非僅限於將來之危害，其於現時以危害相加者，亦應包括在內，故對被害人施以強暴、脅迫，倘被害人尚有幾分自由意思，在社會一般通念上，僅心生畏怖而未達不能抗拒之程度者，仍屬恐嚇取財而非強盜。",
    factors: [
      "被害人是否尚存自由意思（是否仍能抗拒、是否仍有選擇餘地）",
      "社會一般通念之判斷",
      "危害係將來發生或現時相加",
      "被害人主觀心生畏怖不等於客觀不能抗拒",
    ],
    case_ref_verified: true,
  },
  {
    case_ref: "最高法院104年度台上字290號刑事判決",
    issue: ISSUE.snatchVsRobbery,
    court_reasoning:
      "再按搶奪與強盜，雖同具不法得財之意思，然搶奪係乘人不備，公然掠取人之財物，如係施用強暴脅迫，至使不能抗拒而取財物者，即為強盜罪。",
    factors: [
      "是否乘人不備、公然掠取（搶奪）",
      "是否施用強暴脅迫致不能抗拒（強盜）",
      "取財之同時性",
    ],
    case_ref_verified: true,
  },
  {
    case_ref: "最高法院107年度台上字586號刑事判決",
    issue: "判斷不能抗拒之基準：應依一般人在同一情況下其意思自由是否因此受壓制為斷，不以被害人之主觀意思為準。",
    court_reasoning:
      "所謂「不能抗拒」，係指行為人所為之強暴、脅迫等不法行為，就當時之具體事實，予以客觀之判斷，足使被害人身體上或精神上達於不能或顯難抗拒之程度而言，亦即應依一般人在同一情況下，其意思自由是否因此受壓制為斷，不以被害人之主觀意思為準。",
    factors: [
      "一般人在同一情況下之意思自由是否受壓制",
      "具體事實之綜合判斷",
      "被害人主觀意思非判斷基準",
    ],
    case_ref_verified: true,
  },
  {
    case_ref: "最高法院99年度台上字7594號刑事判決",
    issue: "「不能抗拒」之程度要求：在事實上已達於使被害人無法抗拒或不能抗拒之程度。",
    court_reasoning:
      "所稱至使不能抗拒，係指行為人所施之強暴、脅迫等不法行為，在事實上已達於使被害人無法抗拒或不能抗拒之程度而言。",
    factors: ["事實上已達無法抗拒或不能抗拒之程度", "強暴脅迫之具體實施情形"],
    case_ref_verified: true,
  },
  {
    case_ref: "最高法院101年度台上字3376號刑事判決",
    issue: "「客觀上」判斷之要求：在客觀上足使被害人喪失意思自由並達於不能抗拒之程度。",
    court_reasoning:
      "所謂至使不能抗拒，係指行為人所施用之強暴、脅迫等非法方法，在「客觀上」足使被害人喪失意思自由，並達於不能抗拒之程度者而言。",
    factors: ["客觀上足使喪失意思自由", "須達不能抗拒之程度"],
    case_ref_verified: true,
  },
];

/* ---------- 4. 爭點層 → 學說層 ---------- */
const issueToScholarship = [
  {
    issue: ISSUE.irresistible,
    scholarship_views: [
      {
        view: "客觀判斷說（本系統主要依據）：不能抗拒之判斷以一般人置於同一情境時之感受為基準，須被害人於當時具體事實下已達身體上或精神上不能或顯難抗拒之程度。",
        orientation: "通說",
        source_hint: "最高法院111年度台上字2060號、107年度台上字586號、110年度台上字2679號等裁判一致採此判準",
        status: "extracted",
      },
      {
        view: "被害人主觀說（被否定之立場）：以被害人主觀上是否感到恐懼或放棄抵抗為判斷依據。此說於最高法院裁判中明確被排除。",
        orientation: "少數／否定",
        source_hint: "最高法院111年度台上字2060號（明載「不以被害人之主觀意思為準」）、107年度台上字586號",
        status: "extracted",
      },
    ],
  },
  {
    issue: ISSUE.robberyVsThreat,
    scholarship_views: [
      {
        view: "自由意思餘地說：以被害人是否尚存自由意思（仍能抗拒或仍有選擇餘地）為強盜與恐嚇取財之分水嶺，僅達心生畏怖而未至不能抗拒者，構成恐嚇取財。",
        orientation: "通說",
        source_hint: "最高法院86年度台上字5174號刑事判決",
        status: "extracted",
      },
      {
        view: "客觀判斷說（相對說）：兩罪之區別仍應回歸「不能抗拒」之客觀判準，以一般人於同一情境下之意思自由是否受壓制為斷，被害人是否自承恐懼不具決定性。",
        orientation: "學說／實務補充",
        source_hint: "最高法院107年度台上字586號（一般人同一情況下之意思自由是否受壓制）",
        status: "extracted",
      },
    ],
  },
  {
    issue: ISSUE.snatchVsRobbery,
    scholarship_views: [
      {
        view: "手段區分說：兩罪之別在於取財之手段與被害人能否抗拒；搶奪不對人施壓，強盜以強暴脅迫致不能抗拒。",
        orientation: "通說",
        source_hint: "最高法院104年度台上字290號刑事判決",
        status: "extracted",
      },
    ],
  },
];

/* ---------- 5. 推理路徑 ---------- */
const reasoningPaths = [
  {
    path_id: "p_robbery_vs_threat",
    required_triggers: ["e_coercion", "e_taking_or_delivery"],
    required_triggers_note: "本路徑被視為適用之事實型態，須下列要件於敘事中同時受陳述；其餘 trigger_elements 為細分參考。",
    fact_pattern: "行為人持刀（或以其他手段）向被害人威脅並要求交付財物，被害人因恐懼而交付。",
    trigger_elements: ["e_coercion", "e_irresistible", "e_taking_or_delivery", "e_threat", "e_illegal_benefit"],
    candidate_statutes: ["§328_I", "§328_II", "§346_I"],
    distinguishing_elements: ["e_irresistible", "e_delivery_by_fear"],
    key_judgments: [
      "最高法院111年度台上字2060號刑事判決",
      "最高法院86年度台上字5174號刑事判決",
      "最高法院107年度台上字586號刑事判決",
    ],
    key_issues: [ISSUE.irresistible, ISSUE.robberyVsThreat],
    note: "本路徑僅為候選法條之推理對照，不作任何成立與否之認定。",
  },
  {
    path_id: "p_snatch_vs_robbery",
    required_triggers: ["e_robbery_snatch"],
    required_triggers_note: "本路徑被視為適用之事實型態，須下列要件於敘事中同時受陳述；其餘 trigger_elements 為細分參考。",
    fact_pattern: "行為人趁被害人未注意時突然取走其隨身財物，被害人當場才發覺。",
    trigger_elements: ["e_robbery_snatch", "e_theft_taking", "e_robbery_intent"],
    candidate_statutes: ["§325_I", "§320_I", "§328_I"],
    distinguishing_elements: ["e_robbery_snatch", "e_coercion", "e_irresistible"],
    key_judgments: ["最高法院104年度台上字290號刑事判決"],
    key_issues: [ISSUE.snatchVsRobbery],
    note: "本路徑僅為候選法條之推理對照，不作任何成立與否之認定。",
  },
  {
    path_id: "p_qualified_robbery",
    required_triggers: ["e_preceding_offense", "e_ond_the_spot"],
    required_triggers_note: "本路徑被視為適用之事實型態，須下列要件於敘事中同時受陳述；其餘 trigger_elements 為細分參考。",
    fact_pattern: "行為人先竊取或搶奪財物，嗣後為防止追捕、湮滅贓物或脫免逮捕而當場施以強暴脅迫。",
    trigger_elements: ["e_preceding_offense", "e_motive", "e_ond_the_spot", "e_coercion"],
    candidate_statutes: ["§329", "§328_I"],
    distinguishing_elements: ["e_preceding_offense", "e_motive", "e_ond_the_spot"],
    key_judgments: [],
    key_issues: [],
    note: "本路徑僅為候選法條之推理對照，不作任何成立與否之認定。",
  },
];

/* ---------- 6. 檢索字詞建議 ---------- */
const searchWordRecommendations = [
  {
    input_term: "持刀威脅",
    recommended_terms: ["強暴", "脅迫", "不能抗拒", "強盜", "恐嚇", "顯難抗拒"],
    maps_to_elements: ["e_coercion", "e_irresistible", "e_threat"],
  },
  {
    input_term: "被害人害怕所以交付",
    recommended_terms: ["不能抗拒", "心生畏懼", "畏怖心理", "恐嚇", "意思自由", "客觀判斷"],
    maps_to_elements: ["e_irresistible", "e_delivery_by_fear", "e_threat"],
  },
  {
    input_term: "搶了就跑",
    recommended_terms: ["乘人不備", "公然", "搶奪", "竊盜", "竊取"],
    maps_to_elements: ["e_robbery_snatch", "e_theft_taking"],
  },
  {
    input_term: "被搶後追上去",
    recommended_terms: ["當場", "防護贓物", "脫免逮捕", "湮滅罪證", "準強盜"],
    maps_to_elements: ["e_ond_the_spot", "e_motive", "e_preceding_offense"],
  },
  {
    input_term: "攜帶武器",
    recommended_terms: ["攜帶兇器", "凶器", "凶器種類", "加重事由", "三人以上"],
    maps_to_elements: ["e_agg_circumstance"],
  },
];

/* ---------- 產出 ---------- */
const flow = {
  flow_id: "lawbank_reasoning_flow_v1",
  source_note: "mixed",
  generated_at: new Date().toISOString(),
  extraction_summary: {
    source_site: "法源法律網 lawbank.com.tw（會員登入擷取）",
    statutes_extracted: clean.statutes.length,
    judgments_scanned: clean.judgments.length,
    judgments_matched: elementToJudgment.reduce((a, e) => a + e.judgment_refs.length, 0),
    treatises_scanned: clean.treatises.length,
    interpretations_extracted: clean.interpretations.reduce((a, i) => a + i.rows.length, 0),
    coverage_note:
      "判解要旨取自法源司法判解（FJ）查詢結果列表之要旨欄位（<em> 標示之要旨核心），未進入 fyjud 裁判書全文（該單元需另行授權，帳號無閱覽權限）。",
  },
  statute_decomposition: statuteDecomposition,
  element_to_judgment: elementToJudgment,
  judgment_to_issue: judgmentToIssue,
  issue_to_scholarship: issueToScholarship,
  reasoning_paths: reasoningPaths,
  search_word_recommendations: searchWordRecommendations,
  quotation_policy: {
    note:
      "本檔中 holding_summary、court_reasoning、definition 等欄位為法源原文（法院要旨或條文）或依原文改寫之引述，可能含法院原話之斷定性語詞（此為引述，非本系統之斷定）。本系統自身之判斷一律不得出現斷定性語詞；免責語與候選性說明亦一併排除於禁語檢查之外。禁語清單見 tools/validate_reasoning_flow.py 之 FORBIDDEN_WORDS。",
    quotation_fields: [
      "statute_decomposition[].elements[].definition",
      "statute_decomposition[].article_text",
      "element_to_judgment[].judgment_refs[].holding_summary",
      "judgment_to_issue[].court_reasoning",
      "issue_to_scholarship[].scholarship_views[].view",
    ],
    system_authored_fields: [
      "reasoning_paths[].note",
      "extraction_gaps[].description",
      "extraction_gaps[].impact",
    ],
  },
  extraction_gaps: [
    {
      gap_id: "g_fyjud",
      description:
        "裁判書全文（七段式裁判摘要）未能擷取：fyjud.lawbank.com.tw 需獨立授權，此帳號登入後該單元顯示「閱讀權限已滿額／僅供付費會員閱讀」。目前判解層僅有要旨欄位文字。",
      impact: "judgment_to_issue 的法院心證係由要旨推得，未經全文核對。",
      status: "needs_external",
    },
    {
      gap_id: "g_fint",
      description:
        "行政函釋未能取得與本罪群相關者：FINT 以關鍵字檢索，命中結果多為不相干機關之公告，與刑法§328/§329/§346 相關之函釋要旨尚待以條文關聯路徑擷取。",
      impact: "issue_to_scholarship 之學說層目前僅有判解與法學論著條目，缺行政函釋觀點。",
      status: "needs_external",
    },
    {
      gap_id: "g_article_full",
      description:
        "各要件所對應之全部判解（§328 關聯原判例 46 件、精選裁判 355 件）僅擷取其中符合要件關鍵者，非法源頁面所列全量。",
      impact: "要件與判解之對應為代表性取樣，非窮盡。",
      status: "inferred",
    },
  ],
  output_flags: {
    extracted: "原文有",
    needs_external: "需外部檢索驗證",
    inferred: "由關聯結構推得",
  },
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(flow, null, 2), "utf8");
console.log("WROTE", OUT);
console.log("statute_decomposition:", flow.statute_decomposition.length);
console.log("element_to_judgment:", flow.element_to_judgment.length, "groups /", flow.element_to_judgment.reduce((a, e) => a + e.judgment_refs.length, 0), "refs");
console.log("judgment_to_issue:", flow.judgment_to_issue.length);
console.log("issue_to_scholarship:", flow.issue_to_scholarship.length);
console.log("reasoning_paths:", flow.reasoning_paths.length);
console.log("extraction_gaps:", flow.extraction_gaps.length);
