import os
import time
import json
import prompts
import schemas
from llm_api import call_gemini
from utils import convert_name_to_filename

class ParliamentManager:
    """
    (已升级) 负责管理完全基于JSON Schema的议会流程。
    """
    def __init__(self, config, git_manager, api_key, logger):
        self.config = config
        self.git = git_manager
        self.api_key = api_key
        self.logger = logger

    def _call_api_with_schema(self, agent_name, purpose, prompt, schema):
        response_text = call_gemini(prompt, self.api_key, self.logger, agent_name, purpose, response_schema=schema)
        if not response_text: return None
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"错误: Gemini返回的不是有效的JSON。 {e}\n原始返回: {response_text}")
            return None
    
    def _call_api(self, agent_name, purpose, prompt):
        return call_gemini(prompt, self.api_key, self.logger, agent_name, purpose)

    def _get_agent_confirmation(self, agent_role, agent_output):
        output_str = json.dumps(agent_output, ensure_ascii=False, indent=2)
        prompt = prompts.AGENT_CONFIRMATION_PROMPT.format(agent_role=agent_role, agent_output=output_str)
        confirmation = self._call_api("AI助理", f"为 {agent_role} 的输出生成人性化确认信息", prompt)
        if confirmation:
            print(f"\n{confirmation}\n")

    def _get_agent_specific_data(self, role, arc_state):
        print(f"  - 正在为【{role}】准备专属会议资料...")
        if role == "心理分析师":
            profiles_dir = self.config.get('character_profiles_directory', 'output/characters')
            if not os.path.exists(profiles_dir): return "{}"
            
            all_profiles = {}
            for filename in os.listdir(profiles_dir):
                if filename.endswith("_profile.json"):
                    filepath = os.path.join(profiles_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            char_name = filename.replace("_profile.json", "")
                            all_profiles[char_name] = json.load(f)
                        except json.JSONDecodeError:
                            continue
            self.logger.log_read(role, profiles_dir, "为议会准备角色侧写资料")
            return json.dumps(all_profiles, ensure_ascii=False) if all_profiles else "{}"
        
        if role == "文学编辑":
            novel_file = self.config.get('novel_file_name', 'output/infinite_fears.json')
            if not os.path.exists(novel_file): return "{}"
            with open(novel_file, 'r', encoding='utf-8') as f: 
                try:
                    novel_data = json.load(f)
                    last_chapter = novel_data.get("chapters", [])[-1:]
                except json.JSONDecodeError:
                    last_chapter = []
            self.logger.log_read(role, novel_file, "为议会准备最新章节内容")
            return json.dumps({"last_chapter": last_chapter}, ensure_ascii=False)
        
        return json.dumps(arc_state, ensure_ascii=False)

    def hold_meeting(self, arc_state, completed_arc):
        print("\n" + "#"*15 + " 议会开始 " + "#"*15)
        movie_name = completed_arc['movie_name']
        summary_json = json.dumps(arc_state.get("real_world_summary", {}), ensure_ascii=False)
        
        parliament_members = ["心理分析师", "文学编辑", "总编", "悬疑剧编剧"]
        all_member_statements = []
        for role in parliament_members:
            agent_data = self._get_agent_specific_data(role, arc_state)
            prompt = prompts.PARLIAMENT_MEMBER_QUESTIONS_PROMPT.format(
                agent_role=role, movie_name=movie_name, 
                story_summary=summary_json, agent_specific_data=agent_data
            )
            statement = self._call_api_with_schema(role, "在议会上发言 (复盘与提问)", prompt, schemas.PARLIAMENT_MEMBER_SCHEMA)
            if statement:
                all_member_statements.append({"member_role": role, "statement": statement})
            time.sleep(2)

        director_prompt = prompts.PARLIAMENT_DIRECTOR_RESPONSE_PROMPT.format(
            movie_name=movie_name, story_summary=summary_json, 
            all_questions=json.dumps(all_member_statements, ensure_ascii=False)
        )
        meeting_minutes = self._call_api_with_schema("故事导演", "汇总议会发言并撰写会议纪要", director_prompt, schemas.PARLIAMENT_DIRECTOR_SCHEMA)
        if not meeting_minutes: return None, None

        MEETINGS_DIR = "output/meetings"
        os.makedirs(MEETINGS_DIR, exist_ok=True)
        minutes_filepath = os.path.join(MEETINGS_DIR, f"meeting_after_{convert_name_to_filename(movie_name)}.json")
        with open(minutes_filepath, "w", encoding="utf-8") as f:
            json.dump(meeting_minutes, f, ensure_ascii=False, indent=4)
        self.logger.log_write("故事导演", minutes_filepath, f"保存《{movie_name}》的会议纪要")
        
        summary_prompt = prompts.PARLIAMENT_SUMMARY_PROMPT.format(meeting_minutes=json.dumps(meeting_minutes, ensure_ascii=False))
        roadmap_data = self._call_api_with_schema("执行制片人", "从会议纪要中提炼可执行路线图", summary_prompt, schemas.PARLIAMENT_SUMMARY_SCHEMA)
        if roadmap_data:
            self._get_agent_confirmation("执行制片人", roadmap_data)
        
        print("\n" + "#"*15 + " 议会结束 " + "#"*15)
        return roadmap_data, minutes_filepath

