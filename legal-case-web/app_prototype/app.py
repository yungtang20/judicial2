import os
import re
import json
import yaml
import requests
import streamlit as st
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# --- 設定頁面配置 ---
st.set_page_config(
    page_title="JUDICIAL2 筆錄問句生成器 (Prototype)",
    page_icon="⚖️",
    layout="wide"
)

# --- 輔助函數 ---
def load_yaml_data(file_path):
    """載入 YAML 格式的知識庫"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            docs = list(yaml.safe_load_all(f))
            return docs
    except Exception as e:
        st.error(f"載入 YAML 失敗: {e}")
        return []

def extract_pair_options(yaml_docs):
    """從 YAML 中提取可用的 PAIR 選項"""
    options = {}
    for doc in yaml_docs:
        if not doc: continue
        pair_id = doc.get('pair_id')
        if pair_id and pair_id.startswith('PAIR-'):
            cand_a = doc.get('candidate_a', '未知')
            cand_b = doc.get('candidate_b', '未知')
            if not cand_b and 'offense' in doc:
                cand_a = doc.get('offense', '單一罪名')
                cand_b = ""
            label = f"{pair_id}: {cand_a} vs {cand_b}".strip(" vs ")
            options[label] = pair_id
    return dict(sorted(options.items()))

def load_system_prompt(file_path):
    """載入 System Prompt"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        st.error(f"載入 System Prompt 失敗: {e}")
        return ""

def get_few_shot_examples(yaml_docs, target_pair_id):
    """根據選擇的 PAIR ID，提取對應的 neutral_questions 作為 Few-Shot"""
    for doc in yaml_docs:
        if not doc: continue
        if doc.get('pair_id') == target_pair_id:
            questions = doc.get('neutral_questions', [])
            if questions:
                return "\n".join([f"- {q}" for q in questions])
    return "（未找到該 PAIR 的範例問句，請依賴 System Prompt 的通用規則生成）"

def call_llm_api(case_summary, pair_id, target_role, system_prompt, few_shot):
    """呼叫 HCNSEC API"""
    api_key = os.getenv("HCNSEC_API_KEY") or st.session_state.get("api_key_input")

    if not api_key:
        return {"error": "請提供有效的 HCNSEC_API_KEY"}

    user_prompt = (
        f"【案情摘要】\n{case_summary}\n\n"
        f"【候選混淆罪名 (PAIR)】\n{pair_id}\n\n"
        f"【目標角色】\n{target_role}\n\n"
        f"【Few-Shot 風格參考】\n{few_shot}\n\n"
        f"請嚴格遵守 System Prompt 中的 Core Rules，生成 3-4 題底層事實問句，並僅輸出合法的 JSON 格式。"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "auto",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(
            "https://api.hcnsec.cn/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)

        return json.loads(content)
    except requests.exceptions.RequestException as e:
        return {"error": f"API 呼叫失敗: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失敗，模型未嚴格遵守格式: {str(e)}\n原始輸出: {content}"}

# --- 主介面 ---
st.title("⚖️ JUDICIAL2 筆錄問句生成器 (Prototype)")
st.markdown("基於底層事實提取原則，自動生成符合《警察偵查犯罪手冊》標準的筆錄問句。")

with st.sidebar:
    st.header("⚙️ 系統設定")

    env_key = os.getenv("HCNSEC_API_KEY")
    if env_key:
        st.success("✅ 已從環境變數載入 API Key")
    else:
        api_key_input = st.text_input("請輸入 HCNSEC API Key", type="password", key="api_key_input")

    st.markdown("---")
    st.subheader("📂 知識庫路徑設定")
    yaml_path = st.text_input("YAML 知識庫路徑", value="../review/B_master_case_studies.yaml")
    prompt_path = st.text_input("System Prompt 路徑", value="../review/llm_system_prompt_v1.md")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 案件資訊輸入")

    yaml_docs = load_yaml_data(yaml_path)
    if yaml_docs:
        pair_options = extract_pair_options(yaml_docs)
        selected_label = st.selectbox("選擇混淆組合 (PAIR)", options=list(pair_options.keys()))
        selected_pair_id = pair_options[selected_label]
    else:
        st.warning("無法載入 YAML 知識庫，請檢查路徑。")
        selected_pair_id = "PAIR-001"

    target_role = st.radio("目標詢問對象", ["suspect (涉嫌人)", "victim (被害人)"], horizontal=True)

    case_summary = st.text_area(
        "案情摘要 (請盡量提供具體的時間、地點、人物、動作與物品狀態)",
        height=150,
        placeholder="例如：甲在圖書館 K 書中心，看到乙的 iPad 放在桌上，乙去上廁所。甲一時貪玩，拿乙未鎖屏的手機打開超商代碼 App，繳費 3000 元充值自己的遊戲點數。乙回來發現簡訊通知後報警。甲辯稱只是借用手機，沒想那麼多。"
    )

    generate_btn = st.button("🚀 生成底層事實問句", type="primary", use_container_width=True)

with col2:
    st.subheader("🔍 系統除錯資訊")
    if 'yaml_docs' in locals() and yaml_docs:
        st.success(f"✅ 成功載入 {len(yaml_docs)} 筆案例紀錄")

    if generate_btn and case_summary.strip():
        with st.spinner("正在呼叫 LLM 並進行邏輯推演..."):
            system_prompt = load_system_prompt(prompt_path)
            few_shot = get_few_shot_examples(yaml_docs, selected_pair_id)

            result = call_llm_api(case_summary, selected_pair_id, target_role, system_prompt, few_shot)

            if "error" in result:
                st.error(result["error"])
            else:
                st.success("✅ 生成成功！")

                st.markdown("### 生成結果")
                st.json(result)

                result_text = json.dumps(result, ensure_ascii=False, indent=2)
                st.code(result_text, language="json")

                st.markdown("---")
                st.markdown("#### 使用的 Few-Shot 參考:")
                st.info(few_shot)

elif generate_btn:
    st.warning("請先輸入案情摘要！")

st.markdown("---")
st.caption("JUDICIAL2 專案 Prototype | 遵循《警察偵查犯罪手冊》第 120, 127, 128 條規範 | 禁止法條轉寫")
