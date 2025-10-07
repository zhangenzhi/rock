import os
import requests
import json
import subprocess
import time
import re
from datetime import datetime
from pypinyin import pinyin, Style

# --- 前置要求 ---
# 请确保已安装 pypinyin: pip install pypinyin

# --- 配置部分 (Configuration) ---
# OLLAMA_API_URL = "http://localhost:11434/api/generate" # 已被Gemini API替代
# MODEL_NAME = "gpt-oss:20b" # 已被Gemini API替代
NOVEL_FILE = "无限恐怖.txt"
REPO_PATH = "."
SUMMARY_CHAR_COUNT = 300
PROFILES_DIR = "characters"
ARC_STATE_FILE = "story_arc.json" # 用于管理故事“大章节”状态的文件
REWRITE_CYCLES = 3 # 设置重写打磨的轮次

# --- 提示模板 (Prompt Templates) ---

# === 电影世界规划 (Arc Planning) Prompts ===
MOVIE_SELECTION_PROMPT = """
你是一位恐怖电影大师。请为故事主角选择下一部要穿越的经典恐怖电影。
主角是一名普通人，没有超能力。请选择一个适合普通人生存挑战的电影。
请只返回电影的中文名称，不要添加任何解释。
"""

# *** 升级版：编剧现在需要制定每日剧情大纲 ***
MOVIE_ANALYSIS_PROMPT = """
你是一位顶级的电影编剧和世界构建师。你将为小说的一个新篇章（大章节）做框架规划。
主角是一名**普通人**，他将穿越到恐怖电影《{movie_name}》中，并在其中生存 {duration} 天。

你的任务是输出一份**每日剧情大纲**，这份大纲将作为后续所有章节写作的蓝图。

**大纲必须包含以下部分:**
1.  **整体设定:**
    * **恐怖内核分析:** 电影的核心恐怖来源是什么？
    * **场景氛围:** 描述这个世界的主要场景和整体氛围。
    * **关键新人物:** 设计1-3名原创NPC，描述他们的姓名、性格及在剧情中的**具体作用**（例如：推动主线、情感担当、制造悬念等）。
2.  **每日剧情大纲 (Day-by-Day Outline):**
    * 请为从第1天到第{duration}天的**每一天**都进行规划。
    * 每一天的规划格式必须如下:
        **第 X 天: [当日副标题/核心事件]**
        * **剧情梗概:** 简要描述今天会发生的主要事件。
        * **角色视角:** 提示在这些事件中，关键角色（主角或NPC）可能会有的反应或视角。
        * **情绪锚点:** 定义本章需要着重营造的核心情绪（例如：紧张、悬疑、短暂的安逸、绝望、搞笑、激动）。

这份规划文档将是AI写手创作每一章节的**唯一**剧本。请确保情节连贯，张力十足。
"""

TOOL_CREATION_PROMPT = """
你是一位注重现实逻辑的道具设计师。主角（一名普通人）刚刚在恐怖电影《{movie_name}》的世界中成功存活下来。
根据规则，他可以带出一件具有纪念意义的**非超自然**工具。

你的任务是设计这件工具。请遵循以下严格规则：
1.  **绝对普通:** 工具不能是魔法物品或高科技产品。
2.  **功能合理:** 工具可以有巧妙的用途，但不能超出其物理限制。
3.  **来源合理:** 工具必须是电影《{movie_name}》世界中合乎逻辑存在的物品。

请返回一个JSON对象，格式如下：
{{
  "tool_name": "工具名称",
  "description": "对工具外观和来源的详细描述。",
  "potential_use": "在未来的恐怖世界中，这个普通工具可能发挥的创造性作用。"
}}
"""

# === 章节生成与打磨 (Chapter Generation & Polishing) Prompts ===

# --- 初稿生成 ---
FIRST_CHAPTER_PROMPT_TEMPLATE = """
你是一位才华横溢、写作风格细腻客观的中文小说家。你的任务是根据**预设的剧本**，完成小说中第一天的故事章节。主角是一名**普通人**。

**今日剧本 (必须严格遵守):**
1.  **本章主题 (副标题):** "{chapter_subtitle}"
2.  **核心情绪锚点:** "{emotional_anchor}"
3.  **世界观设定:** {movie_plan}

**写作要求:**
-   **核心任务：演绎剧本:** 你的写作必须完全服务于**今日剧本**。所有情节都必须围绕**副标题**展开，并且全力渲染出预设的**核心情绪锚点**。
-   **开篇情节:** 故事从主角在一个无聊的下午观看电影《{movie_name}》，然后意外穿越到这个电影世界中开始。
-   **建立悬念与行动:** 让主角立即面临一个具体的、需要做出反应的小冲突或谜题，以此推动故事的第一个行动。
-   **注入内心驱动力:** 通过简短的内心独白、疑问或瞬间的权衡，来揭示主角**为什么**会做出这个决定。
-   **格式:** 请直接开始创作正文，不要添加任何评论。
"""

GENERATION_PROMPT_TEMPLATE = """
你是一位才华横溢、写作风格细腻客观的中文小说家。你的任务是根据**预设的剧本**，完成小说中一天的故事章节。主角是一名**普通人**。

**今日剧本 (必须严格遵守):**
1.  **本章主题 (副标题):** "{chapter_subtitle}"
2.  **核心情绪锚点:** "{emotional_anchor}"
3.  **世界观设定:** {movie_plan}

**其他背景资料:**
4.  **故事摘要:** "{summary_text}"
5.  **本章出场人物侧写:**
{character_profiles_text}
6.  **主角携带的工具:** {protagonist_tools}

**写作要求:**
-   **核心任务：演绎剧本:** 你的写作必须完全服务于**今日剧本**。所有情节、发现和角色互动都必须围绕**副标题**展开，并且全力渲染出预设的**核心情绪锚点**。
-   **角色互动与功能:** 重点描写角色之间的互动。确保每个角色的行为和对话都符合他们在世界观设定中的**具体作用**。
-   **注入内心驱动力:** 在描述角色的行动时，通过简短的内心独白、疑问或权衡，来揭示他们**为什么**会做出这个决定。
-   **叙事视点:** 请严格根据以上背景资料，从角色“{character_pov}”的视点续写。
-   **格式:** 请直接开始创作，不要重复摘要或添加任何评论。
"""

# --- 审稿与重写 ---
REVIEW_PROMPT_TEMPLATE = """
你是一位极其严苛的文学编辑。你的任务是审查以下小说章节的初稿，并提出尖锐、具体、可操作的修改意见。

**本章剧本 (必须遵守):**
1.  **世界观设定:** {movie_plan}
2.  **本章主题 (副标题):** "{chapter_subtitle}"
3.  **核心情绪锚点:** "{emotional_anchor}"

**审查标准:**
1.  **剧本吻合度:** 章节内容是否紧扣**副标题**？是否成功营造了预设的**核心情绪锚点**？
2.  **世界观一致性:** 内容是否严格遵循了世界观设定？
3.  **情节推进:** 故事的核心情节是否向前发展了？还是角色在原地踏步？
4.  **思行平衡:** 角色的内心思考和外部行动是否平衡？
5.  **内容重复:** 是否有重复的句子、描述或感受？

**章节初稿:**
---
{chapter_text}
---

请根据以上标准，输出一份简洁的、要点式的中文修改意见列表。
"""

REWRITE_PROMPT_TEMPLATE = """
你是一位顶级的小说家，正在根据编辑的意见修改自己的作品。
你的任务是重写以下章节，必须严格遵循并解决编辑提出的所有修改意见，同时保留故事的核心情节和所有原始背景设定。

**原始背景资料 (不可更改):**
1.  **今日剧本:**
    * **主题 (副标题):** "{chapter_subtitle}"
    * **核心情绪锚点:** "{emotional_anchor}"
    * **世界观设定:** {movie_plan}
2.  **其他背景:**
    * **故事摘要:** "{summary_text}"
    * **本章出场人物侧写:** {character_profiles_text}
    * **主角携带的工具:** {protagonist_tools}
    * **叙事视点:** {character_pov}

**章节初稿:**
---
{original_text}
---

**编辑的修改意见 (必须解决):**
---
{feedback}
---

请现在输出经过你精心打磨后的、全新的章节正文。不要包含任何解释。
"""

# === 其他 Prompts ===
SUMMARY_PROMPT_TEMPLATE = f"""
作为一名专业的故事分析师，你的任务是为以下文本创作一份简洁的摘要。摘要长度应约为 {SUMMARY_CHAR_COUNT} 字。
它必须捕捉到主要角色、关键情节、近期事件以及故事当前的氛围。这份摘要将作为后续所有决策的唯一依据。

这是需要总结的文本：
---
{'{story_text}'}
---
你的中文精炼摘要：
"""

CHARACTER_IDENTIFICATION_PROMPT = """
你是一位敏锐的文学评论家。请仔细阅读以下故事摘要，并列出其中提及或暗示将要出现的**所有**主要角色的名字。
请只返回用逗号分隔的角色名列表（例如：张三,李四,王五），不要添加任何其他解释。如果不存在明确角色，请返回“无”。

故事摘要：
"{summary_text}"

角色名列表：
"""

POV_DECISION_PROMPT = """
你是一位经验丰富的编辑。根据以下的故事摘要，请决定下一章最适合从哪个角色的视点（POV）来叙述，这样能最大化戏剧冲突和故事吸引力。
请只返回一个角色的名字，不要添加任何解释。如果时机不合适，请返回“旁白”。

故事摘要：
"{summary_text}"

下一章的叙事视点角色名：
"""

PROFILE_UPDATE_PROMPT = """
你是一位深刻的心理分析师。请更新角色“{character_name}”的侧写档案。主角的成长被严格限制在普通人范围内。
请基于角色的旧档案和新章节内容，生成一份全新的档案，包含对以下几点的认知和评判：
1.  对自己的看法（作为普通人的能力、动机、恐惧、目标）。
2.  对其他关键角色的具体行为和事件的看法。
3.  对当前所处环境和近期发生的关键事件的理解与评判。

[旧的侧写档案内容开始]
{existing_profile}
[旧的侧写档案内容结束]

[最新章节内容（从此角色视点）开始]
{new_chapter_content}
[最新章节内容（从此角色视点）结束]

请输出完整、更新后的角色“{character_name}”的Markdown格式侧写档案：
"""

# --- Git操作模块 ---
class GitManager:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        if not os.path.isdir(os.path.join(repo_path, '.git')):
            raise EnvironmentError("错误：当前目录不是一个有效的Git仓库。")

    def _run_command(self, command, suppress_errors=False):
        try:
            result = subprocess.run(command, cwd=self.repo_path, check=True, capture_output=True, text=True, encoding='utf-8')
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                print(f"Git命令执行失败: {e.stderr.strip()}")
            return None

    def get_current_branch(self):
        return self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    def branch_exists(self, branch_name):
        local_exists = self._run_command(["git", "branch", "--list", branch_name], suppress_errors=True)
        remote_exists = self._run_command(["git", "branch", "-r", "--list", f"origin/{branch_name}"], suppress_errors=True)
        return bool(local_exists or remote_exists)

    def list_all_branches(self):
        local_branches_raw = self._run_command(["git", "branch"])
        remote_branches_raw = self._run_command(["git", "branch", "-r"])
        branches = set()
        if local_branches_raw:
            for line in local_branches_raw.split('\n'):
                branches.add(line.strip().replace("* ", ""))
        if remote_branches_raw:
            for line in remote_branches_raw.split('\n'):
                branch_name = line.strip().replace("origin/", "")
                if "->" not in branch_name:
                    branches.add(branch_name)
        return list(branches)

    def delete_branch(self, branch_name):
        print(f"正在删除分支: {branch_name}")
        self._run_command(["git", "branch", "-D", branch_name], suppress_errors=True)
        self._run_command(["git", "push", "origin", "--delete", branch_name], suppress_errors=True)

    def read_file_from_branch(self, branch_name, file_path):
        print(f"正在从分支 '{branch_name}' 读取文件 '{file_path}'...")
        content = self._run_command(["git", "show", f"{branch_name}:{file_path}"], suppress_errors=True)
        if content is not None: return content
        content_remote = self._run_command(["git", "show", f"origin/{branch_name}:{file_path}"], suppress_errors=True)
        if content_remote is not None: return content_remote
        print(f"警告：在本地和远程分支'{branch_name}'上都无法读取文件 '{file_path}'。")
        return None

    def switch_to_branch(self, branch_name, create_if_not_exists=False):
        if self.get_current_branch() == branch_name: return True
        if self.branch_exists(branch_name):
            print(f"切换到已存在的分支: {branch_name}")
            return self._run_command(["git", "checkout", branch_name]) is not None
        elif create_if_not_exists:
            return self._run_command(["git", "checkout", "-b", branch_name]) is not None
        return False

    def commit_and_push(self, file_paths, message):
        branch = self.get_current_branch()
        if not branch: return
        print(f"\n--- 正在向分支 '{branch}' 提交并推送 ---")
        for file_path in file_paths:
             self._run_command(["git", "add", file_path])
        self._run_command(["git", "commit", "-m", message])
        self._run_command(["git", "push", "--set-upstream", "origin", branch])
        print(f"成功将更改推送到 origin/{branch}")

# --- 核心逻辑 ---
def call_gemini(prompt):
    """调用 Gemini API 并获取生成的内容。"""
    print(f"\n--- 正在调用 Gemini 模型: gemini-2.5-flash-preview-05-20 ---")
    
    # 注意：在Canvas环境中，API密钥将自动提供。本地测试时，请在此处填入您的密钥。
    api_key = "" 
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.8,
            "topK": 1,
            "topP": 1,
            "maxOutputTokens": 8192,
        },
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
            if "content" in candidate and "parts" in candidate["content"] and candidate["content"]["parts"]:
                return candidate["content"]["parts"][0].get("text", "").strip()
        
        print("错误：Gemini API响应格式不正确或内容为空。")
        print("响应内容:", response_data)
        return None

    except requests.exceptions.RequestException as e:
        print(f"错误：Gemini API 请求失败: {e}")
        if e.response:
            print(f"响应状态码: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
        return None


def convert_name_to_branch(name):
    if not name or name == "旁白": return None
    return "-".join([item[0] for item in pinyin(name, style=Style.NORMAL)])

def load_arc_state():
    if os.path.exists(ARC_STATE_FILE):
        with open(ARC_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"current_movie": None, "day": 0, "max_days": 0, "movie_plan": None, "protagonist_tools": []}

def save_arc_state(state):
    with open(ARC_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def prepare_for_new_story(git):
    """清理所有旧的故事文件和分支，为新故事做准备。"""
    print("\n--- 正在清理环境，准备开始全新故事 ---")
    
    protected_branches = ["main", "setup"]
    all_branches = git.list_all_branches()
    for branch in all_branches:
        if branch not in protected_branches:
            git.delete_branch(branch)
    
    if os.path.exists(NOVEL_FILE): os.remove(NOVEL_FILE)
    if os.path.exists(ARC_STATE_FILE): os.remove(ARC_STATE_FILE)
    if os.path.exists(PROFILES_DIR):
        import shutil
        shutil.rmtree(PROFILES_DIR)
    print("环境清理完成。")

def plan_new_arc(arc_state):
    print("\n--- 正在规划新的电影世界 ---")
    if arc_state["current_movie"]:
        print(f"正在为电影《{arc_state['current_movie']}》生成纪念品工具...")
        tool_json_str = call_gemini(TOOL_CREATION_PROMPT.format(movie_name=arc_state['current_movie']))
        try:
            new_tool = json.loads(tool_json_str)
            arc_state["protagonist_tools"].append(new_tool)
            print(f"获得新工具: {new_tool.get('tool_name')}")
        except (json.JSONDecodeError, TypeError):
            print(f"错误：无法解析工具JSON: {tool_json_str}")

    new_movie = call_gemini(MOVIE_SELECTION_PROMPT)
    if not new_movie: return None
    arc_state["current_movie"] = new_movie
    print(f"已选择新电影: {new_movie}")

    duration = random.randint(10, 15)
    movie_plan = call_gemini(MOVIE_ANALYSIS_PROMPT.format(movie_name=new_movie, duration=duration))
    if not movie_plan: return None
    arc_state["movie_plan"] = movie_plan
    
    arc_state["day"] = 1
    arc_state["max_days"] = duration
    print(f"电影《{new_movie}》规划完成，需生存 {duration} 天。")
    return arc_state

def extract_daily_plan(movie_plan, day):
    """从电影规划文档中提取指定某一天的计划（副标题和情绪锚点）。"""
    try:
        pattern = re.compile(rf"第\s*{day}\s*天:\s*(.*?)\n.*?情绪锚点:\s*(.*?)(?:\n|\Z)", re.DOTALL)
        match = pattern.search(movie_plan)
        if match:
            subtitle = match.group(1).strip()
            emotion = match.group(2).strip()
            return {"subtitle": subtitle, "emotion": emotion}
    except Exception as e:
        print(f"解析每日计划时出错: {e}")
    return {"subtitle": "未知的发展", "emotion": "悬疑"}

def main():
    import random
    git = GitManager(REPO_PATH)

    print("--- 正在进行启动检查 ---")
    if git.get_current_branch() != "setup":
        print("\n错误：请先手动切换到 'setup' 分支 (git checkout setup) 再运行此脚本。")
        return
    print("启动检查通过，当前在 'setup' 分支。")

    if not git.branch_exists("main"):
        prepare_for_new_story(git)
        print("\n正在创建 'main' 分支用于存放故事...")
        if not git.switch_to_branch("main", create_if_not_exists=True): return
    else:
        if not git.switch_to_branch("main"): return
    
    if not os.path.exists(PROFILES_DIR): os.makedirs(PROFILES_DIR)

    arc_state = load_arc_state()
    if not arc_state.get("current_movie") or arc_state["day"] >= arc_state["max_days"]:
        arc_state = plan_new_arc(arc_state)
        if not arc_state: return
    else:
        arc_state["day"] += 1
    save_arc_state(arc_state)
    print(f"\n--- 当前电影:《{arc_state['current_movie']}》 | 第 {arc_state['day']} / {arc_state['max_days']} 天 ---")

    story_text = ""
    if os.path.exists(NOVEL_FILE):
        with open(NOVEL_FILE, "r", encoding="utf-8") as f: story_text = f.read()
    
    # --- 故事生成与打磨 ---
    summary = "无（这是故事的开篇）" if not story_text else call_gemini(SUMMARY_PROMPT_TEMPLATE.format(story_text=story_text))
    if not summary: return
    if story_text: print(f"\n--- 生成的摘要 ---\n{summary}\n--------------------")

    daily_plan = extract_daily_plan(arc_state['movie_plan'], arc_state['day'])
    chapter_subtitle = daily_plan['subtitle']
    emotional_anchor = daily_plan['emotion']
    print(f"\n--- 本章主题 (副标题): {chapter_subtitle} ---")
    print(f"--- 核心情绪锚点: {emotional_anchor} ---")
    
    if not story_text:
        generation_prompt = FIRST_CHAPTER_PROMPT_TEMPLATE.format(
            movie_plan=arc_state['movie_plan'], movie_name=arc_state['current_movie'],
            chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
        )
        pov_character_name = "主角"
        all_profiles_text = "无"
    else:
        character_names_str = call_gemini(CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary))
        all_profiles_text = "本章没有特定角色的侧写信息。"
        if character_names_str and character_names_str.lower() != "无":
            character_names = [name.strip() for name in character_names_str.split(',') if name.strip()]
            print(f"识别到出场人物: {character_names}")
            profile_contents = []
            for name in character_names:
                branch_name = convert_name_to_branch(name)
                if branch_name and git.branch_exists(branch_name):
                    profile_path = os.path.join(PROFILES_DIR, f"{branch_name}_profile.md").replace("\\", "/")
                    content = git.read_file_from_branch(branch_name, profile_path)
                    if content: profile_contents.append(f"--- 角色: {name} ---\n{content}\n")
            if profile_contents: all_profiles_text = "\n".join(profile_contents)
        
        pov_character_name = call_gemini(POV_DECISION_PROMPT.format(summary_text=summary))
        if not pov_character_name: return
        print(f"\n--- AI编辑决定下一章视点为: {pov_character_name} ---")

        generation_prompt = GENERATION_PROMPT_TEMPLATE.format(
            movie_plan=arc_state['movie_plan'], character_pov=pov_character_name, 
            summary_text=summary, character_profiles_text=all_profiles_text,
            chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor,
            protagonist_tools=json.dumps(arc_state['protagonist_tools'], ensure_ascii=False)
        )
    
    draft_content = call_gemini(generation_prompt)
    if not draft_content: return
    
    # --- 三轮审稿与重写循环 ---
    print("\n--- 开始三轮审稿与重写流程 ---")
    polished_content = draft_content
    for i in range(REWRITE_CYCLES):
        print(f"\n--- 第 {i + 1} / {REWRITE_CYCLES} 轮打磨 ---")
        review_prompt = REVIEW_PROMPT_TEMPLATE.format(
            chapter_text=polished_content, movie_plan=arc_state['movie_plan'],
            chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
        )
        feedback = call_gemini(review_prompt)
        if not feedback: 
            print("审稿失败，跳过本轮重写。")
            continue
        
        print(f"--- 编辑反馈 ---\n{feedback}\n----------------")

        rewrite_prompt = REWRITE_PROMPT_TEMPLATE.format(
            movie_plan=arc_state['movie_plan'], summary_text=summary,
            character_profiles_text=all_profiles_text,
            protagonist_tools=json.dumps(arc_state['protagonist_tools'], ensure_ascii=False),
            character_pov=pov_character_name, original_text=polished_content,
            feedback=feedback, chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
        )
        rewritten_content = call_gemini(rewrite_prompt)
        if not rewritten_content:
            print("重写失败，保留上一版本内容。")
            break
        polished_content = rewritten_content
    
    new_content = polished_content
    print("\n--- 章节打磨完成 ---")

    # --- 文件写入与提交 ---
    next_chapter_number = len(re.findall(r"第 (\d+) 章", story_text)) + 1
    header = f"第 {next_chapter_number} 章: {chapter_subtitle} (视点: {pov_character_name}) | {arc_state['current_movie']} - 第 {arc_state['day']} 天\n写作于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    write_mode = "w" if next_chapter_number == 1 else "a"
    if write_mode == "a":
        with open(NOVEL_FILE, "a", encoding="utf-8") as f: f.write("\n" + "="*20 + "\n\n")

    with open(NOVEL_FILE, write_mode, encoding="utf-8") as f:
        f.write(header + new_content + "\n\n")
    
    git.commit_and_push([NOVEL_FILE, ARC_STATE_FILE], f"Chapter {next_chapter_number}: {chapter_subtitle}")

    # --- 角色侧写更新 ---
    character_branch = convert_name_to_branch(pov_character_name)
    if not character_branch:
        git.switch_to_branch("setup")
        return

    if not git.switch_to_branch(character_branch, create_if_not_exists=True):
        git.switch_to_branch("setup")
        return
        
    profile_path = os.path.join(PROFILES_DIR, f"{pov_character_name.lower()}_profile.md") # Use pov_character_name for profile path
    existing_profile = ""
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f: existing_profile = f.read()
    else:
        existing_profile = f"# {pov_character_name} 的角色侧写\n\n- 在《{arc_state['current_movie']}》篇章中首次出场。"

    profile_prompt = PROFILE_UPDATE_PROMPT.format(
        character_name=pov_character_name, existing_profile=existing_profile, new_chapter_content=new_content
    )
    updated_profile = call_gemini(profile_prompt)

    if updated_profile:
        with open(profile_path, "w", encoding="utf-8") as f: f.write(updated_profile)
        git.commit_and_push([profile_path], f"Update profile for {pov_character_name} after Chapter {next_chapter_number}")
    
    print("侧写更新完成，切回 'setup' 分支准备下次运行。")
    git.switch_to_branch("setup")
    print("\n本轮循环完成。")

if __name__ == "__main__":
    import random
    total_runs = 100
    for i in range(total_runs):
        print(f"\n{'#'*10} 开始第 {i + 1} / {total_runs} 轮小说创作 {'#'*10}")
        try:
            main()
        except Exception as e:
            print(f"在第 {i+1} 轮执行中发生严重错误: {e}")
        
        if i < total_runs - 1:
            print(f"\n--- 第 {i + 1} 轮结束。程序将休眠5分钟... ---")
            time.sleep(3)
    
    print(f"\n{'#'*10} 全部 {total_runs} 轮创作完成 {'#'*10}")

