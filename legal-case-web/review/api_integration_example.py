# -*- coding: utf-8 -*-
"""
API 整合範例：使用 api.hcnsec.cn (model=auto) 生成執法筆錄問句。

提示：
- 本檔案僅為骨架範例，不執行任何真實呼叫。
- 請將 API Key 存放在環境變數 HCNSEC_API_KEY 中，勿寫死在程式碼。
"""

import os
import re
import json
from typing import List, Optional

import requests

API_BASE_URL = "https://api.hcnsec.cn/v1/chat/completions"
MODEL_NAME = "auto"
KNOWLEDGE_BASE_PATH = "./review/knowledge_base_v1.md"
SYSTEM_PROMPT_PATH = "./review/llm_system_prompt_v1.md"


def load_system_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_pair_block(kb_text: str, pair_id: str) -> str:
    """從 knowledge_base_v1.md 中擷取指定 pair_id 的區塊作為 Few-Shot 範例。"""
    # 找到 ## PAIR-xxx 區塊直到下一個 ## 或 EOF
    pattern = re.compile(
        rf"(##\s+{re.escape(pair_id)}:.*?)(?=\n##\s+|\Z)",
        re.DOTALL,
    )
    m = pattern.search(kb_text)
    if not m:
        return ""
    return m.group(1).strip()


def build_few_shot_examples(pair_block: str) -> List[dict]:
    """將取出的 PAIR 區塊轉成 messages 中的 few-shot 範例。"""
    if not pair_block:
        return []
    return [
        {
            "role": "user",
            "content": "以下是該 PAIR 的底層事實問句風格範例，請模仿：\n" + pair_block,
        },
        {
            "role": "assistant",
            "content": "已理解該 PAIR 的問句風格，將依 Core Rules 生成。",
        },
    ]


def generate_questions(case_summary: str, pair_id: str, target_role: str) -> Optional[dict]:
    api_key = os.environ.get("HCNSEC_API_KEY")
    if not api_key:
        raise RuntimeError("缺少環境變數 HCNSEC_API_KEY")

    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
        kb_text = f.read()

    system_prompt = load_system_prompt(SYSTEM_PROMPT_PATH)
    pair_block = extract_pair_block(kb_text, pair_id)
    few_shot = build_few_shot_examples(pair_block)

    user_prompt = (
        f"案情摘要：{case_summary}\n"
        f"候選混淆罪名 (PAIR)：{pair_id}\n"
        f"目標角色：{target_role}\n"
        "請依 System Prompt 生成 3-4 題底層事實問句，並以指定 JSON 格式輸出。"
    )

    messages = [{"role": "system", "content": system_prompt}] + few_shot + [
        {"role": "user", "content": user_prompt}
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
    }

    resp = requests.post(API_BASE_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        print("JSON 解析失敗：", exc)
        print("原始回應：", content)
        return None


def main() -> None:
    result = generate_questions(
        case_summary="甲在咖啡廳趁乙上廁所時，拿未鎖屏手機做 3000 元小額付費儲值。",
        pair_id="PAIR-052",
        target_role="suspect",
    )
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# ---- 免費部署環境 API Key 保護說明 ----
# 1. 絕對不要將 API Key 寫入前端或 repository；使用環境變數 / Secret Manager。
# 2. Vercel：在 Project Settings -> Environment Variables 設定 HCNSEC_API_KEY，
#    前端僅呼叫後端 API route，由後端帶入 Key。
# 3. Hugging Face Spaces：使用 Spaces Secrets (Settings -> Variables and secrets) 設定，
#    應用程式啟動時 os.environ 已包含該值。
# 4. 在地端開發使用 .env + python-dotenv，並將 .env 加入 .gitignore。
