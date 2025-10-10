import os
import time
import json
import re
import prompts
from llm_api import call_gemini
from utils import convert_name_to_filename

class ParliamentManager:
    """
    一个独立的Agent管理机构，负责在关键节点召开议会。
    (已升级，支持详细的API调用日志)
    """
    def __init__(self, config, git_manager, api_key, logger):
        self.config = config
        self.git = git_manager
        self.api_key = api_key
        self.logger = logger

    def _call_api(self, agent_name, purpose, prompt):
        """统一的API调用封装"""
        return call_gemini(prompt, self.api_key, self.logger, agent_name, purpose)

    def _call_api_for_json(self, agent_name, purpose, prompt, max_retries=3):
        """统一的JSON API调用封装"""
        for attempt in range(max_retries):
            json_str = self._call_api(agent_name, purpose if attempt == 0 else f"{purpose} (第 {attempt+1} 次尝试)", prompt)
            if not json_str:
                if attempt < max_retries - 1: time.sleep(2)
                continue
            try:
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if not match: raise json.JSONDecodeError("响应中未找到有效的JSON结构。", json_str, 0)
                cleaned_json_str = match.group(0)
                json_obj = json.loads(cleaned_json_str)
                return json_obj, cleaned_json_str
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1: print(f"警告：JSON解析失败: {e}，将重试。")
        return None, None

    def _get_agent_confirmation(self, agent_role, agent_output):
        if isinstance(agent_output, dict):
            agent_output = json.dumps(agent_output, ensure_ascii=False, indent=2)
        
        prompt = prompts.AGENT_CONFIRMATION_PROMPT.format(agent_role=agent_role, agent_output=agent_output)
        confirmation = self._call_api("AI助理", f"为 {agent_role} 的输出生成人性化确认信息", prompt)
        if confirmation:
            print(f"\n{confirmation}\n")

    def _get_agent_specific_data(self, role, arc_state):
        print(f"  - 正在为【{role}】准备专属会议资料...")
        if role == "心理分析师":
            profiles_dir = self.config.get('character_profiles_directory', 'output/characters')
            if not os.path.exists(profiles_dir): return "..."
            all_profiles = []
            for filename in os.listdir(profiles_dir):
                if filename.endswith("_profile.md"):
                    filepath = os.path.join(profiles_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        char_name = filename.replace("_profile.md", "").replace("-", " ").title()
                        all_profiles.append(f"--- 角色: {char_name} ---\n{f.read()}\n")
            self.logger.log_read(role, profiles_dir, "为议会准备角色侧写资料")
            return "\n".join(all_profiles) if all_profiles else "..."
        if role == "文学编辑":
            novel_file = self.config.get('novel_file_name', 'infinite_fears.md')
            if not os.path.exists(novel_file): return "..."
            with open(novel_file, 'r', encoding='utf-8') as f: content = f.read()
            self.logger.log_read(role, novel_file, "为议会准备最新章节内容")
            return content[-3000:]
        arc_state_str = json.dumps(arc_state, ensure_ascii=False, indent=2)
        return f"当前的故事架构与状态 (story_arc.json):\n```json\n{arc_state_str}\n```"

    def hold_meeting(self, arc_state, completed_arc):
        print("\n" + "#"*15 + " 议会开始：审阅已完成章节并规划未来 " + "#"*15)
        movie_name = completed_arc['movie_name']
        summary = arc_state.get("real_world_summary", "无")
        
        parliament_members = ["心理分析师", "文学编辑", "总编", "悬疑剧编剧", "电影世界架构师", "道具设计师", "故事分析师"]
        all_questions = []
        for role in parliament_members:
            agent_data = self._get_agent_specific_data(role, arc_state)
            prompt = prompts.PARLIAMENT_MEMBER_QUESTIONS_PROMPT.format(agent_role=role, movie_name=movie_name, story_summary=summary, agent_specific_data=agent_data)
            questions = self._call_api(role, "在议会上发言 (复盘与提问)", prompt)
            if questions:
                question_block = f"## 来自【{role}】的发言:\n{questions}\n"
                all_questions.append(question_block)
            time.sleep(2)

        director_prompt = prompts.PARLIAMENT_DIRECTOR_RESPONSE_PROMPT.format(movie_name=movie_name, story_summary=summary, all_questions="\n---\n".join(all_questions))
        meeting_minutes = self._call_api("故事导演", "汇总议会发言并撰写会议纪要", director_prompt)
        if not meeting_minutes: return None, None

        MEETINGS_DIR = "output/meetings"; os.makedirs(MEETINGS_DIR, exist_ok=True)
        minutes_filename = f"meeting_after_{convert_name_to_filename(movie_name)}.md"
        minutes_filepath = os.path.join(MEETINGS_DIR, minutes_filename)
        with open(minutes_filepath, "w", encoding="utf-8") as f:
            f.write(f"# 关于《{movie_name}》章节的复盘与未来规划会议纪要\n\n{meeting_minutes}")
        self.logger.log_write("故事导演", minutes_filepath, f"保存《{movie_name}》的会议纪要")
        
        summary_prompt = prompts.PARLIAMENT_SUMMARY_PROMPT.format(meeting_minutes=meeting_minutes)
        roadmap_data, _ = self._call_api_for_json("执行制片人", "从会议纪要中提炼可执行路线图", summary_prompt)
        if roadmap_data:
            self._get_agent_confirmation("执行制片人", roadmap_data)
        
        print("\n" + "#"*15 + " 议会结束 " + "#"*15)
        return roadmap_data, minutes_filepath

