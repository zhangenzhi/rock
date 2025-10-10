import os
import time
import json
import re
import prompts
from llm_api import call_gemini
from utils import convert_name_to_filename

class ParliamentManager:
    """
    一个独立的Agent管理机构，负责在关键节点召开议会，
    进行复盘并为故事的下一阶段制定宏观战略。
    """
    def __init__(self, config, git_manager, api_key, logger):
        self.config = config
        self.git = git_manager
        self.api_key = api_key
        self.logger = logger

    def _get_agent_specific_data(self, role, arc_state):
        """根据Agent的角色，读取并汇总相关的专属资料。"""
        print(f"  - 正在为【{role}】准备专属会议资料...")
        
        if role == "心理分析师":
            profiles_dir = self.config.get('character_profiles_directory', 'output/characters')
            self.logger.log_read(role, profiles_dir, "为议会准备所有角色侧写资料")
            if not os.path.exists(profiles_dir):
                return "（资料缺失：角色侧写目录未找到。）"
            
            all_profiles = []
            for filename in os.listdir(profiles_dir):
                if filename.endswith("_profile.md"):
                    filepath = os.path.join(profiles_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        char_name = filename.replace("_profile.md", "").replace("-", " ").title()
                        all_profiles.append(f"--- 角色: {char_name} ---\n{f.read()}\n")
            
            if not all_profiles:
                return "（暂无角色侧写文件。）"
            return "\n".join(all_profiles)

        if role == "文学编辑":
            novel_file = self.config.get('novel_file_name', 'infinite_fears.md')
            self.logger.log_read(role, novel_file, "为议会准备最新章节内容")
            if not os.path.exists(novel_file):
                return "（资料缺失：小说主文件未找到。）"
            
            with open(novel_file, 'r', encoding='utf-8') as f:
                content = f.read()
                return content[-3000:] if len(content) > 3000 else content

        arc_state_file = self.config.get('story_arc_file', 'output/story_arc.json')
        self.logger.log_read(role, arc_state_file, "为议会准备故事架构与状态资料")
        arc_state_str = json.dumps(arc_state, ensure_ascii=False, indent=2)
        return f"当前的故事架构与状态 (story_arc.json):\n```json\n{arc_state_str}\n```"

    def _call_gemini_and_parse_json(self, prompt, max_retries=3):
        for attempt in range(max_retries):
            json_str = call_gemini(prompt, self.api_key)
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
        confirmation = call_gemini(prompt, self.api_key)
        if confirmation: print(f"\n{confirmation}\n")

    def hold_meeting(self, arc_state, completed_arc):
        """在电影大章节完成后，召开议会，决定未来走向。"""
        print("\n" + "#"*15 + " 议会开始：审阅已完成章节并规划未来 " + "#"*15)

        movie_name = completed_arc['movie_name']
        summary = arc_state.get("real_world_summary", "无")
        
        print("\n--- [议会流程] 各部门成员正在基于专属资料进行复盘和议题提出... ---")
        parliament_members = ["心理分析师", "文学编辑", "总编", "悬疑剧编剧", "电影世界架构师", "道具设计师", "故事分析师"]
        all_questions = []
        for role in parliament_members:
            agent_data = self._get_agent_specific_data(role, arc_state)
            
            prompt = prompts.PARLIAMENT_MEMBER_QUESTIONS_PROMPT.format(
                agent_role=role, movie_name=movie_name, story_summary=summary, agent_specific_data=agent_data
            )
            questions = call_gemini(prompt, self.api_key)
            if questions:
                question_block = f"## 来自【{role}】的发言:\n{questions}\n"
                print(f"  - 已收到来自【{role}】的深度复盘与议题。")
                all_questions.append(question_block)
            time.sleep(2)

        print("\n--- [议会流程] 故事导演正在汇总所有发言并撰写会议纪要... ---")
        director_prompt = prompts.PARLIAMENT_DIRECTOR_RESPONSE_PROMPT.format(
            movie_name=movie_name, story_summary=summary, all_questions="\n---\n".join(all_questions)
        )
        meeting_minutes = call_gemini(director_prompt, self.api_key)
        
        if not meeting_minutes:
            print("错误：导演未能形成会议纪要，议会流程中断。")
            return None, None

        MEETINGS_DIR = "output/meetings"
        os.makedirs(MEETINGS_DIR, exist_ok=True)
        minutes_filename = f"meeting_after_{convert_name_to_filename(movie_name)}.md"
        minutes_filepath = os.path.join(MEETINGS_DIR, minutes_filename)
        with open(minutes_filepath, "w", encoding="utf-8") as f:
            f.write(f"# 关于《{movie_name}》章节的复盘与未来规划会议纪要\n\n{meeting_minutes}")
        self.logger.log_write("故事导演", minutes_filepath, f"保存《{movie_name}》的会议纪要")
        print(f"  - 会议纪要已保存至: {minutes_filepath}")

        print("\n--- [议会流程] 正在根据纪要，形成下一阶段的可执行路线图... ---")
        summary_prompt = prompts.PARLIAMENT_SUMMARY_PROMPT.format(meeting_minutes=meeting_minutes)
        roadmap_data, _ = self._call_gemini_and_parse_json(summary_prompt)

        if roadmap_data: self._get_agent_confirmation("执行制片人", roadmap_data)
        else: print("错误：未能从会议纪要中提炼出有效的执行路线图。")
        
        print("\n" + "#"*15 + " 议会结束 " + "#"*15)
        
        return roadmap_data, minutes_filepath
