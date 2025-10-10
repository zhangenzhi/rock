import os
import time
import json
import prompts
import schemas
from llm_api import call_gemini
from utils import convert_name_to_filename

class ParliamentManager:
    """
    (已升级) 独立的Agent管理机构，负责在关键节点召开议会。
    """
    def __init__(self, config, git_manager, api_key, logger):
        self.config = config
        self.git = git_manager
        self.api_key = api_key
        self.logger = logger

    def _get_agent_specific_data(self, role, arc_state):
        data_source = "N/A"
        
        if role == "心理分析师":
            profiles_dir = self.config.get('character_profiles_directory', 'output/characters')
            data_source = profiles_dir
            if not os.path.exists(profiles_dir): return "（资料缺失：角色侧写目录未找到。）", data_source
            
            all_profiles = []
            for filename in os.listdir(profiles_dir):
                if filename.endswith("_profile.json"):
                    filepath = os.path.join(profiles_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            profile_data = json.load(f)
                            char_name = filename.replace("_profile.json", "").replace("-", " ").title()
                            all_profiles.append(f"--- 角色: {char_name} ---\n{json.dumps(profile_data, ensure_ascii=False, indent=2)}\n")
                        except json.JSONDecodeError:
                            self.logger.log_error(f"议会准备期间，无法解析角色侧写: {filepath}")
            
            if not all_profiles: return "（暂无角色侧写文件。）", data_source
            self.logger.log_read(role, profiles_dir, "为议会准备所有角色侧写")
            return "\n".join(all_profiles), data_source

        if role in ["文学编辑"]:
            novel_file = self.config.get('novel_file_name', 'output/novel.json')
            data_source = novel_file
            if not os.path.exists(novel_file): return "（资料缺失：小说主文件未找到。）", data_source
            
            with open(novel_file, 'r', encoding='utf-8') as f:
                try:
                    novel_data = json.load(f)
                    # 返回最近的章节作为参考
                    last_chapters = novel_data.get("chapters", [])[-2:]
                    self.logger.log_read(role, novel_file, "为议会准备最新章节内容")
                    return json.dumps(last_chapters, ensure_ascii=False, indent=2), data_source
                except json.JSONDecodeError:
                    self.logger.log_error(f"议会准备期间，无法解析小说文件: {novel_file}")
                    return "（小说文件解析失败。）", data_source
        
        arc_state_str = json.dumps(arc_state, ensure_ascii=False, indent=2)
        data_source = self.config.get('story_arc_file', 'output/story_arc.json')
        self.logger.log_read(role, data_source, "为议会准备故事架构状态")
        return f"当前的故事架构与状态 (story_arc.json):\n```json\n{arc_state_str}\n```", data_source

    def _call_api_with_schema(self, agent_name, purpose, prompt, schema):
        response_text = call_gemini(prompt, self.api_key, self.logger, agent_name, purpose, response_schema=schema)
        if not response_text: return None
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.log_error(f"JSON解析失败 for {agent_name} ({purpose}). Error: {e}. Raw text: {response_text}")
            return None

    def hold_meeting(self, arc_state, completed_arc):
        """
        在电影或现实世界大章节完成后，召开议会。
        """
        print("\n" + "#"*15 + " 议会开始：审阅已完成章节并规划未来 " + "#"*15)

        # 核心修改：兼容电影和现实世界两种类型的章节
        arc_name = completed_arc.get('movie_name') or completed_arc.get('arc_title', '未知章节')
        summary = arc_state.get("real_world_summary", {"summary": "无"})
        
        parliament_members = ["心理分析师", "文学编辑", "总编", "悬疑剧编剧", "电影世界架构师", "道具设计师", "故事分析师"]
        all_member_speeches = []
        
        for role in parliament_members:
            agent_data, _ = self._get_agent_specific_data(role, arc_state)
            
            prompt = prompts.PARLIAMENT_MEMBER_QUESTIONS_PROMPT.format(
                agent_role=role, movie_name=arc_name, story_summary=json.dumps(summary, ensure_ascii=False), agent_specific_data=agent_data
            )
            speech_data = self._call_api_with_schema(role, f"在关于《{arc_name}》的议会上发言", prompt, schemas.PARLIAMENT_MEMBER_SCHEMA)
            
            if speech_data:
                all_member_speeches.append({"member_role": role, "speech": speech_data})
            time.sleep(1)

        if not all_member_speeches:
            self.logger.log_error("议会未能收集到任何成员的发言，流程中断。")
            return None, None

        director_prompt = prompt.PARLIAMENT_DIRECTOR_RESPONSE_PROMPT.format(
            movie_name=arc_name, story_summary=json.dumps(summary, ensure_ascii=False), all_questions=json.dumps(all_member_speeches, ensure_ascii=False)
        )
        meeting_minutes = self._call_api_with_schema("故事导演", f"为《{arc_name}》的议会撰写会议纪要", director_prompt, schemas.PARLIAMENT_DIRECTOR_SCHEMA)
        
        if not meeting_minutes:
            self.logger.log_error("导演未能形成会议纪要，议会流程中断。")
            return None, None

        MEETINGS_DIR = "output/meetings"
        os.makedirs(MEETINGS_DIR, exist_ok=True)
        minutes_filename = f"meeting_after_{convert_name_to_filename(arc_name)}.json"
        minutes_filepath = os.path.join(MEETINGS_DIR, minutes_filename)
        with open(minutes_filepath, "w", encoding="utf-8") as f:
            json.dump(meeting_minutes, f, ensure_ascii=False, indent=4)
        self.logger.log_write("故事导演", minutes_filepath, f"保存《{arc_name}》的会议纪要")

        summary_prompt = prompts.PARLIAMENT_SUMMARY_PROMPT.format(meeting_minutes=json.dumps(meeting_minutes, ensure_ascii=False))
        roadmap_data = self._call_api_with_schema("执行制片人", "从会议纪要中提炼路线图", summary_prompt, schemas.PARLIAMENT_SUMMARY_PROMPT)

        if roadmap_data:
            call_gemini(prompt.AGENT_CONFIRMATION_PROMPT.format(agent_role="执行制片人", agent_output=json.dumps(roadmap_data, ensure_ascii=False)), self.api_key, self.logger, "AI助理", "生成路线图确认信息")
        else:
            self.logger.log_error("未能从会议纪要中提炼出有效的执行路线图。")
        
        print("\n" + "#"*15 + " 议会结束 " + "#"*15)
        
        return roadmap_data, minutes_filepath

