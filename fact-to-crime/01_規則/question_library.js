// question_library.js
// 混合問句方案（C）核心要件規則庫
// v15 R33/R34 審校版：問句以日常用語提問，不含罪名、法律用語、元件名稱
// R33：問句不得含罪名、法律用語、元件名稱
// R34：追問須引用受詢問人自己的用語
// R35：問句目的為取得準確資訊

module.exports = {
  version: "1.1",
  spec_version: "v15",
  review_status: "R33/R34 已審校",
  note: "本檔為「混合問句方案（C）」之核心要件規則庫。非核心要件缺口由 LLM 依 v15 第九節生成。",

  // ===== 通用（跨罪章）=====
  common: {
    free_statement: [
      {
        stage: "A", priority: 1, type: "開放",
        identity_sensitive: ["被害人", "證人", "被告", "關係人"],
        text: "請你按時間順序說明整個事情的經過。"
      },
      {
        stage: "A", priority: 1, type: "開放",
        identity_sensitive: ["被害人", "證人", "被告", "關係人"],
        text: "請你說明當時的情況，不要遺漏任何細節。"
      }
    ],
    open_ending: [
      {
        stage: "C", priority: 7, type: "開放",
        identity_sensitive: ["被害人", "證人", "被告", "關係人"],
        text: "請問你還有其他想補充的地方嗎？"
      },
      {
        stage: "C", priority: 7, type: "開放",
        identity_sensitive: ["被害人", "證人", "被告", "關係人"],
        text: "以上所說的都是真實情況嗎？"
      }
    ],
    evidence_preservation: [
      {
        stage: "E", priority: 2, type: "聚焦",
        identity_sensitive: ["被害人"],
        text: "請問當時有留下什麼東西、照片、影片或訊息嗎？"
      },
      {
        stage: "E", priority: 2, type: "聚焦",
        identity_sensitive: ["被害人"],
        text: "這些東西現在你還留著嗎？放在哪裡？"
      },
      {
        stage: "E", priority: 2, type: "聚焦",
        identity_sensitive: ["被害人", "證人", "被告"],
        text: "當時現場附近有沒有監視器？"
      },
      {
        stage: "E", priority: 2, type: "聚焦",
        identity_sensitive: ["被害人", "證人"],
        text: "當時現場除了你和對方，還有沒有其他人看到？"
      }
    ]
  },

  // ===== 依罪章 =====
  chapters: {
    criminal_221: {
      charge_221: {
        element_questions: {
          "E-221-001": [ // 性交行為發生
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時發生了什麼事？" },
            { stage: "B", priority: 5, type: "封閉", identity_sensitive: ["被害人"], text: "你們兩人有發生性關係嗎？" }
          ],
          "E-221-005": [ // 被害人不能抗拒
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "當時你可以動嗎？你的感受如何？" },
            { stage: "B", priority: 5, type: "封閉", identity_sensitive: ["被害人"], text: "當時你可以拒絕嗎？" }
          ],
          "E-221-006": [ // 直接故意
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時知道對方願不願意嗎？" },
            { stage: "B", priority: 4, type: "封閉", identity_sensitive: ["被告"], text: "你當時知道對方不願意嗎？" }
          ]
        },
        group_questions: {
          "means_221": [
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "當時對方做了什麼動作？請描述。" },
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "當時對方有沒有用手、用東西、或用其他方式壓住你？" }
          ]
        }
      }
    },

    criminal_fraud: {
      charge_fraud: {
        element_questions: {
          "E-FR-001": [ // 施用詐術
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時對方是怎麼跟你說的？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "你剛才提到對方說的那些話，可以再說得詳細一點嗎？" }
          ],
          "E-FR-002": [ // 陷於錯誤並交付
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "當時你為什麼會相信對方並決定付款？" },
            { stage: "B", priority: 5, type: "封閉", identity_sensitive: ["被害人"], text: "付款之前你有懷疑過嗎？" }
          ],
          "E-FR-004": [ // 取得財物
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "你當時是怎麼付款的？付了多少？" }
          ]
        },
        group_questions: {
          "mens_rea_fraud": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時知道對方為什麼要付錢給你嗎？" }
          ]
        }
      }
    },

    criminal_theft_embezzle: {
      charge_theft: {
        element_questions: {
          "E-TE-001": [ // 竊取他人之動產
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述你發現東西不見的情況。" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "請你說明你當時拿走那個東西的經過。" }
          ],
          "E-TE-002": [ // 破壞持有
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "拿之前你有問過店員或別人嗎？" },
            { stage: "B", priority: 5, type: "封閉", identity_sensitive: ["被告"], text: "拿之前你有付錢嗎？" }
          ],
          "E-TE-003": [ // 竊盜之不法所有意圖
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時打算拿那個東西做什麼？" },
            { stage: "B", priority: 4, type: "封閉", identity_sensitive: ["被告"], text: "你知道那個東西是別人的嗎？" }
          ]
        }
      },
      charge_embezzle: {
        element_questions: {
          "E-TE-004": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時是怎麼處理那個東西的？" }
          ],
          "E-TE-006": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時知道那個東西是別人交給你保管的嗎？" }
          ]
        }
      }
    },

    criminal_harm_dv: {
      charge_harm: {
        element_questions: {
          "E-HD-001": [ // 傷害行為
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時對方做了什麼？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時做了什麼？" }
          ],
          "E-HD-002": [ // 傷害之故意
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時為什麼會這樣做？" },
            { stage: "B", priority: 4, type: "封閉", identity_sensitive: ["被告"], text: "你當時知道對方會受傷嗎？" }
          ],
          "E-HD-003": [ // 傷害結果
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "你身上有受傷嗎？有沒有去看醫生？" }
          ]
        }
      },
      charge_harm_dv: {
        element_questions: {
          "E-HD-012": [ // 家暴身分
            { stage: "B", priority: 3, type: "聚焦", identity_sensitive: ["被害人"], text: "你跟對方是什麼關係？認識多久了？" }
          ]
        }
      }
    },

    criminal_defame: {
      charge_insult: {
        element_questions: {
          "E-DF-011": [ // 公然侮辱
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時對方說了什麼話？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時對他說了什麼？" }
          ],
          "E-DF-013": [ // 公開性
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人", "證人"], text: "當時現場還有別人嗎？大概多少人？" }
          ],
          "E-DF-017": [ // 名譽受損
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "這件事之後你有什麼感覺？對你的生活有影響嗎？" }
          ]
        }
      }
    },

    criminal_public_danger: {
      charge_dui: {
        element_questions: {
          "E-PD-001": [ // 酒精濃度
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "警察有沒有請你吹氣測試？結果是多少？" }
          ],
          "E-PD-004": [ // 駕駛動力交通工具
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時騎的是什麼車？要從哪裡去哪裡？" }
          ]
        }
      }
    },

    criminal_traffic: {
      charge_admin_alcohol: {
        element_questions: {
          "E-TR-001": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "警察有沒有請你吹氣測試？" }
          ],
          "E-TR-004": [
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被告"], text: "請你描述你當時開車或騎車的情況。" }
          ]
        }
      },
      charge_hit_and_run: {
        element_questions: {
          "E-TR-006": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時知道對方有受傷嗎？" },
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被告"], text: "為什麼你當時沒有停下來？" }
          ]
        }
      }
    },

    criminal_drugs: {
      charge_use_tier2: {
        element_questions: {
          "E-DR-002": [ // 施用第二級毒品
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時是怎麼使用那個東西的？什麼時候？在哪裡？" }
          ],
          "E-DR-013": [ // 施用毒品之故意
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時知道自己在使用什麼嗎？" }
          ]
        }
      }
    },

    criminal_sexual_harassment: {
      charge_sh_offense: {
        element_questions: {
          "E-SH-001": [ // 性騷擾行為
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時對方做了什麼？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時做了什麼？" }
          ],
          "E-SH-002": [ // 違反意願
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "當時你有說不願意嗎？怎麼說的？" }
          ],
          "E-SH-003": [ // 與性或性別有關
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "你覺得當時那件事讓你感到不舒服嗎？" }
          ]
        }
      }
    },

    criminal_forgery: {
      charge_forgery_private: {
        element_questions: {
          "E-FG-001": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "請你說明這份文件是怎麼來的？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "這份文件上的簽名是你的嗎？" }
          ],
          "E-FG-004": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "這件事對你造成什麼損失？" }
          ],
          "E-FG-005": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時知道這樣做會有問題嗎？" }
          ]
        }
      }
    },

    criminal_gambling: {
      charge_gambling: {
        element_questions: {
          "E-GB-001": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你們當時在做什麼？有沒有玩錢？" }
          ],
          "E-GB-002": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時玩這個是想贏錢嗎？" }
          ],
          "E-GB-003": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你們是用什麼當輸贏的東西？" }
          ]
        }
      }
    },

    criminal_intimidation: {
      charge_threat: {
        element_questions: {
          "E-IN-001": [
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時對方說了什麼話？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "你當時對他說了什麼？" }
          ],
          "E-IN-002": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時說那些話是想讓對方怎樣？" }
          ],
          "E-IN-003": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "聽到那些話之後，你感覺怎麼樣？" }
          ]
        }
      }
    },

    criminal_computer: {
      charge_alter_record: {
        element_questions: {
          "E-CP-002": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "你的帳號資料是怎麼不見的？什麼時候發現？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "請說明你是怎麼登入對方帳號的？" }
          ],
          "E-CP-004": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被害人"], text: "這件事對你造成什麼損失？" }
          ]
        }
      }
    },

    criminal_obscenity: {
      charge_distribute_obscenity: {
        element_questions: {
          "E-OB-003": [
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "請說明你是怎麼傳給別人的？傳了幾次？" }
          ],
          "E-OB-004": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時傳這些是為了什麼？" }
          ]
        }
      }
    },

    criminal_robbery: {
      charge_snatching: {
        element_questions: {
          "E-RB-001": [
            { stage: "B", priority: 5, type: "開放", identity_sensitive: ["被害人"], text: "請你描述當時發生了什麼事？" },
            { stage: "B", priority: 5, type: "聚焦", identity_sensitive: ["被告"], text: "請說明你當時拿走東西的經過。" }
          ],
          "E-RB-002": [
            { stage: "B", priority: 4, type: "開放", identity_sensitive: ["被告"], text: "你當時拿那個東西是想做什麼？" }
          ]
        }
      }
    }
  }
};
