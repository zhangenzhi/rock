import requests
import json

def call_gemini(prompt, api_key, logger, agent_name, purpose, response_schema=None):
    """
    (已升级) 调用 Gemini API 并获取生成的内容。
    支持通过 responseSchema 强制执行JSON输出。
    """
    print(f"\n--- [API Call] Agent: {agent_name} | Purpose: {purpose} ---")
    if logger:
        logger.log_api_call(agent_name, purpose)
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    
    generation_config = {
        "temperature": 0.7,
        "topK": 1,
        "topP": 1,
        "maxOutputTokens": 8192
    }
    
    # --- 核心修改：启用JSON Schema模式 ---
    if response_schema:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = response_schema

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        response_data = response.json()
        
        if "candidates" in response_data and response_data["candidates"]:
            candidate = response_data["candidates"][0]
            if candidate.get('finishReason') == 'SAFETY':
                print("错误：内容因安全设置被 Gemini API 阻止。")
                if 'safetyRatings' in candidate:
                    print("安全评级:", candidate['safetyRatings'])
                return None
            if "content" in candidate and "parts" in candidate["content"] and candidate["content"]["parts"]:
                return candidate["content"]["parts"][0].get("text", "").strip()
        
        print(f"错误：Gemini API响应格式不正确或内容为空。\n响应内容: {response_data}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"错误：Gemini API 请求失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应状态码: {e.response.status_code}")
            try:
                error_details = e.response.json()
                print(f"响应内容: {json.dumps(error_details, ensure_ascii=False, indent=2)}")
            except json.JSONDecodeError:
                print(f"响应内容 (非JSON): {e.response.text}")
        return None

