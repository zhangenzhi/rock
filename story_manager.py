import os
import json
import time
import shutil
from datetime import datetime
import prompts
import schemas
from llm_api import call_gemini
from utils import convert_name_to_filename
from logger_manager import LoggerManager
from parliament_manager import ParliamentManager

class StoryManager:
    """
    (已升级) 负责管理完全基于JSON Schema的创作流程。
    """
    def __init__(self, config, git_manager):
        self.config = config
        self.git = git_manager
        self.api_key = config['gemini_api_key']
        self.logger = LoggerManager()
        self.parliament = ParliamentManager(config, git_manager, self.api_key, self.logger)
        self.arc_state = None
        self.novel_data = {"chapters": []}

    def prepare_for_new_story(self):
        print("\n--- 正在清理环境，准备开始全新故事 ---")
        output_dir = "output"
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
                print(f"环境清理完成: 已删除 '{output_dir}' 目录及其所有内容。")
            except Exception as e:
                print(f"清理环境时出错: {e}")
        self.logger = LoggerManager()

    def _load_arc_state(self):
        ARC_STATE_FILE = self.config['story_arc_file']
        if os.path.exists(ARC_STATE_FILE):
            self.logger.log_read("StoryManager", ARC_STATE_FILE, "加载故事世界状态")
            with open(ARC_STATE_FILE, 'r', encoding='utf-8') as f:
                try:
                    state = json.load(f)
                    if "completed_movie_arcs" not in state: state["completed_movie_arcs"] = []
                    if "current_real_world_arc" not in state: state["current_real_world_arc"] = None
                    return state
                except json.JSONDecodeError:
                    self.logger.log_error(f"无法解析 story_arc 文件: {ARC_STATE_FILE}。将创建新状态。")
                    return self._get_initial_arc_state()
        return self._get_initial_arc_state()

    def _get_initial_arc_state(self):
        return {
            "protagonist_name": "江浩", "protagonist_tools": [], "current_location": "init_world",
            "real_world_summary": {"summary": "故事的开端。主角江浩是一名中国的普通待业青年。", "next_motivation": "开始第一次电影世界冒险"},
            "current_movie_arc": None, "completed_movie_arcs": [], "current_real_world_arc": None,
            "last_completed_arc": None # 用于会议
        }

    def _save_arc_state(self):
        ARC_STATE_FILE = self.config['story_arc_file']
        os.makedirs(os.path.dirname(ARC_STATE_FILE), exist_ok=True)
        with open(ARC_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.arc_state, f, ensure_ascii=False, indent=4)
        self.logger.log_write("StoryManager", ARC_STATE_FILE, "保存故事世界状态")

    def _load_novel_data(self):
        NOVEL_FILE = self.config['novel_file_name']
        if os.path.exists(NOVEL_FILE):
            self.logger.log_read("StoryManager", NOVEL_FILE, "加载小说全文数据")
            with open(NOVEL_FILE, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    self.logger.log_error(f"无法解析小说文件: {NOVEL_FILE}。将创建新数据。")
                    return {"chapters": []}
        return {"chapters": []}

    def _call_api_with_schema(self, agent_name, purpose, prompt, schema):
        response_text = call_gemini(prompt, self.api_key, self.logger, agent_name, purpose, response_schema=schema)
        if not response_text: return None
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.log_error(f"JSON解析失败 for {agent_name} ({purpose}). Error: {e}. Raw text: {response_text}")
            return None
    
    def _get_agent_confirmation(self, agent_role, agent_output):
        output_str = json.dumps(agent_output, ensure_ascii=False, indent=2)
        prompt = prompt.AGENT_CONFIRMATION_PROMPT.format(agent_role=agent_role, agent_output=output_str)
        confirmation_text = call_gemini(prompt, self.api_key, self.logger, "AI助理", f"为 {agent_role} 的输出生成人性化确认信息")
        if confirmation_text:
            print(f"\n{confirmation_text}\n")

    def _plan_new_movie_arc(self):
        movie_data = self._call_api_with_schema("电影世界架构师", "选择下一部电影", prompts.MOVIE_SELECTION_PROMPT, schemas.MOVIE_SELECTION_SCHEMA)
        if not movie_data or "movie_name" not in movie_data: return None, []
        movie_name = movie_data["movie_name"]

        polished_plan = self._call_api_with_schema("电影世界架构师", f"为《{movie_name}》生成大纲", prompts.MOVIE_ANALYSIS_PROMPT.format(movie_name=movie_name), schemas.MOVIE_ANALYSIS_SCHEMA)
        if not polished_plan: return None, []

        for i in range(self.config['rewrite_cycles']):
            feedback_data = self._call_api_with_schema("总编", f"审查《{movie_name}》大纲 (第 {i+1} 轮)", prompts.ARCHITECT_REVIEW_PROMPT.format(movie_plan_draft=json.dumps(polished_plan, ensure_ascii=False)), schemas.REVIEW_SCHEMA)
            if not feedback_data: continue
            self._get_agent_confirmation("总编", feedback_data)
            
            rewritten_plan = self._call_api_with_schema("电影世界架构师", f"重写《{movie_name}》大纲 (第 {i+1} 轮)", prompts.ARCHITECT_REWRITE_PROMPT.format(original_plan=json.dumps(polished_plan, ensure_ascii=False), feedback=json.dumps(feedback_data, ensure_ascii=False)), schemas.MOVIE_ANALYSIS_SCHEMA)
            if not rewritten_plan: break
            polished_plan = rewritten_plan
        
        self._get_agent_confirmation("电影世界架构师", polished_plan)
        scenes = polished_plan.get("scenes", [])
        arc = {"movie_name": movie_name, "status": "active", "current_scene_index": -1, "total_scenes": len(scenes), "movie_plan": polished_plan.get("overall_setting", {}), "scenes": scenes}
        new_profile_paths = self._create_character_profiles(polished_plan.get("character_pool", []))
        return arc, new_profile_paths

    def _plan_real_world_arc(self, summary_json):
        last_movie_name = self.arc_state["completed_movie_arcs"][-1]['movie_name'] if self.arc_state["completed_movie_arcs"] else "无"
        
        draft_prompt = prompts.REAL_WORLD_ARC_ANALYSIS_PROMPT.format(real_world_summary=json.dumps(summary_json, ensure_ascii=False), protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False), last_movie_name=last_movie_name)
        polished_plan = self._call_api_with_schema("悬疑剧编剧", "规划现实世界章节", draft_prompt, schemas.REAL_WORLD_ARC_ANALYSIS_SCHEMA)
        if not polished_plan: return None, []

        for i in range(self.config['rewrite_cycles']):
            feedback_data = self._call_api_with_schema("悬疑剧总编", f"审查现实大纲 (第 {i+1} 轮)", prompts.REAL_WORLD_ARC_REVIEW_PROMPT.format(real_world_plan_draft=json.dumps(polished_plan, ensure_ascii=False)), schemas.REVIEW_SCHEMA)
            if not feedback_data: continue
            self._get_agent_confirmation("悬疑剧总编", feedback_data)

            rewritten_plan = self._call_api_with_schema("悬疑剧编剧", f"重写现实大纲 (第 {i+1} 轮)", prompts.REAL_WORLD_ARC_REWRITE_PROMPT.format(original_plan=json.dumps(polished_plan, ensure_ascii=False), feedback=json.dumps(feedback_data, ensure_ascii=False)), schemas.REAL_WORLD_ARC_ANALYSIS_SCHEMA)
            if not rewritten_plan: break
            polished_plan = rewritten_plan
        
        self._get_agent_confirmation("悬疑剧编剧", polished_plan)
        scenes = polished_plan.get("scenes", [])
        arc = {"arc_title": polished_plan.get("arc_title", "未命名"), "status": "active", "current_scene_index": -1, "total_scenes": len(scenes), "scenes": scenes}
        new_profile_paths = self._create_character_profiles(polished_plan.get("character_pool", []))
        return arc, new_profile_paths

    def _generate_chapter(self, prompt_params, is_first_chapter_ever=False):
        agent_name = "小说家" if prompt_params.get("is_movie_world", False) else "悬疑小说家"
        chapter_subtitle = prompt_params.get("chapter_subtitle", "无标题")

        if is_first_chapter_ever:
            gen_prompt = prompts.FIRST_CHAPTER_PROMPT_TEMPLATE.format(**prompt_params)
        else:
            gen_prompt = prompts.GENERATION_PROMPT_TEMPLATE.format(**prompt_params)

        polished_content = self._call_api_with_schema(agent_name, f"创作章节初稿: {chapter_subtitle}", gen_prompt, schemas.CHAPTER_GENERATION_SCHEMA)
        if not polished_content: return None

        for i in range(self.config['rewrite_cycles']):
            review_params = {"movie_plan": prompt_params.get("movie_plan", "{}"), "chapter_subtitle": chapter_subtitle, "emotional_anchor": prompt_params.get("emotional_anchor", "未知"), "chapter_text": json.dumps(polished_content, ensure_ascii=False)}
            feedback_data = self._call_api_with_schema("文学编辑", f"审查章节: {chapter_subtitle} (第 {i+1} 轮)", prompts.REVIEW_PROMPT_TEMPLATE.format(**review_params), schemas.REVIEW_SCHEMA)
            if not feedback_data: continue
            self._get_agent_confirmation("文学编辑", feedback_data)
            
            rewrite_params = {**prompt_params, "original_text": json.dumps(polished_content, ensure_ascii=False), "feedback": json.dumps(feedback_data, ensure_ascii=False)}
            rewritten_content = self._call_api_with_schema(agent_name, f"重写章节: {chapter_subtitle} (第 {i+1} 轮)", prompts.REWRITE_PROMPT_TEMPLATE.format(**rewrite_params), schemas.CHAPTER_GENERATION_SCHEMA)
            if not rewritten_content: break
            polished_content = rewritten_content
            
        return polished_content

    def _handle_movie_arc_progression(self, summary_json):
        movie_arc = self.arc_state["current_movie_arc"]
        if movie_arc["current_scene_index"] >= movie_arc["total_scenes"] - 1:
            self.arc_state["current_location"] = "awaiting_meeting" # <-- 核心修改
            movie_arc["status"] = "completed"
            self.arc_state["completed_movie_arcs"].append(movie_arc)
            self.arc_state["last_completed_arc"] = movie_arc # <-- 核心修改
            self.arc_state["current_movie_arc"] = None
            
            tool_data = self._call_api_with_schema("道具设计师", "为主角设计新工具", prompts.TOOL_CREATION_PROMPT.format(movie_name=movie_arc['movie_name']), schemas.TOOL_CREATION_SCHEMA)
            if tool_data:
                self.arc_state["protagonist_tools"].append(tool_data)
                self._get_agent_confirmation("道具设计师", tool_data)
            
            return None # 结束本轮，等待下轮开会
        else:
            movie_arc["current_scene_index"] += 1
            scene_plan = movie_arc["scenes"][movie_arc["current_scene_index"]]
            
            meta_instruction = movie_arc.get("movie_plan", {}).get("meta_narrative_foreshadowing", {}).get("content", "无")
            if scene_plan.get("scene_number") != movie_arc.get("movie_plan", {}).get("meta_narrative_foreshadowing", {}).get("trigger_scene", -1):
                 meta_instruction = "无"

            params = {
                "is_movie_world": True, "chapter_subtitle": scene_plan["subtitle"], "emotional_anchor": scene_plan.get("emotion_anchor", "未知"),
                "movie_plan": json.dumps(movie_arc.get('movie_plan', {}), ensure_ascii=False), "summary_text": json.dumps(summary_json, ensure_ascii=False),
                "character_profiles_text": self._get_character_profiles_text(summary_json), "protagonist_tools": json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
                "character_pov": scene_plan.get("pov_character", self.arc_state["protagonist_name"]), "meta_narrative_instruction": meta_instruction,
                "movie_name": movie_arc['movie_name']
            }
            return self._generate_chapter(params, is_first_chapter_ever=False)
    
    def _handle_real_world_arc_progression(self, summary_json):
        rw_arc = self.arc_state["current_real_world_arc"]
        if rw_arc and rw_arc["current_scene_index"] >= rw_arc["total_scenes"] - 1:
            self.arc_state["current_location"] = "awaiting_meeting" # <-- 核心修改
            rw_arc["status"] = "completed"
            self.arc_state["last_completed_arc"] = rw_arc # <-- 核心修改
            self.arc_state["current_real_world_arc"] = None
            return None # 结束本轮，等待下轮开会
        else:
            rw_arc["current_scene_index"] += 1
            scene_plan = rw_arc["scenes"][rw_arc["current_scene_index"]]
            
            params = {
                "is_movie_world": False, "chapter_subtitle": scene_plan["subtitle"], "emotional_anchor": scene_plan.get("emotion_anchor", "未知"),
                "movie_plan": "{}", "summary_text": json.dumps(summary_json, ensure_ascii=False),
                "character_profiles_text": self._get_character_profiles_text(summary_json), "protagonist_tools": json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
                "character_pov": scene_plan.get("pov_character", self.arc_state["protagonist_name"]), "meta_narrative_instruction": "无"
            }
            return self._generate_chapter(params)

    def _start_new_movie_arc(self, summary_json, is_first_run=False):
        arc, new_profile_paths = self._plan_new_movie_arc()
        if not arc: return None
        
        self.arc_state["current_movie_arc"] = arc
        self.arc_state["current_location"] = "movie_world"
        self._save_arc_state()
        self.git.commit_and_push([self.config['story_arc_file']] + new_profile_paths, f"Architect Plan (Movie): {arc['movie_name']}")
        
        movie_arc = self.arc_state["current_movie_arc"]
        movie_arc["current_scene_index"] += 1
        scene_plan = movie_arc["scenes"][movie_arc["current_scene_index"]]
        
        meta_instruction = movie_arc.get("movie_plan", {}).get("meta_narrative_foreshadowing", {}).get("content", "无")
        if scene_plan.get("scene_number") != movie_arc.get("movie_plan", {}).get("meta_narrative_foreshadowing", {}).get("trigger_scene", -1):
             meta_instruction = "无"

        params = {
            "is_movie_world": True, "chapter_subtitle": scene_plan["subtitle"], "emotional_anchor": scene_plan.get("emotion_anchor", "未知"),
            "movie_plan": json.dumps(movie_arc.get('movie_plan', {}), ensure_ascii=False), "summary_text": json.dumps(summary_json, ensure_ascii=False),
            "character_profiles_text": self._get_character_profiles_text(summary_json, is_first_run), "protagonist_tools": json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
            "character_pov": scene_plan.get("pov_character", self.arc_state["protagonist_name"]), "meta_narrative_instruction": meta_instruction,
            "movie_name": movie_arc['movie_name']
        }
        return self._generate_chapter(params, is_first_chapter_ever=is_first_run)

    def _decide_and_execute_next_step(self, summary_json):
        completed_movies = [arc['movie_name'] for arc in self.arc_state['completed_movie_arcs']]
        prompt = prompts.NEXT_STEP_DECISION_PROMPT.format(real_world_summary=json.dumps(summary_json, ensure_ascii=False), protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False), completed_movies=json.dumps(completed_movies, ensure_ascii=False))
        decision_data = self._call_api_with_schema("故事导演", "决策下一步剧情走向", prompt, schemas.NEXT_STEP_DECISION_SCHEMA)
        if not decision_data: decision_data = {"decision": "REAL_WORLD"}
        self._get_agent_confirmation("故事导演", decision_data)

        if decision_data["decision"] == "REAL_WORLD":
            arc, new_profile_paths = self._plan_real_world_arc(summary_json)
            if not arc: return None
            
            self.arc_state["current_real_world_arc"] = arc
            self.arc_state["current_location"] = "real_world" # <-- 核心修改
            self._save_arc_state()
            self.git.commit_and_push([self.config['story_arc_file']] + new_profile_paths, f"Architect Plan (Real World): {arc['arc_title']}")
            return self._handle_real_world_arc_progression(summary_json)
        else:
            return self._start_new_movie_arc(summary_json)

    def _create_character_profiles(self, character_pool):
        if not character_pool: return []
        new_paths = []
        PROFILES_DIR = self.config['character_profiles_directory']
        os.makedirs(PROFILES_DIR, exist_ok=True)
        for char_data in character_pool:
            char_name = char_data.get("name")
            profile_data = char_data.get("initial_profile")
            if char_name and profile_data:
                path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(char_name)}_profile.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(profile_data, f, ensure_ascii=False, indent=4)
                self.logger.log_write("档案员", path, f"创建角色 {char_name} 的初始侧写")
                new_paths.append(path)
        return new_paths

    def _get_character_profiles_text(self, summary_json, is_first_run=False):
        if is_first_run: return "{}"
        summary_text = summary_json.get("summary", "")
        id_data = self._call_api_with_schema("情报分析师", "从摘要中识别出场人物", prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_text), schemas.CHARACTER_IDENTIFICATION_SCHEMA)
        if not id_data or not id_data.get("characters"): return "{}"
        
        profiles = {}
        PROFILES_DIR = self.config['character_profiles_directory']
        for name in id_data["characters"]:
            profile_path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(name)}_profile.json")
            if os.path.exists(profile_path):
                self.logger.log_read("情报分析师", profile_path, f"为章节生成加载角色 {name} 的侧写")
                with open(profile_path, 'r', encoding='utf-8') as f:
                    try:
                        profiles[name] = json.load(f)
                    except json.JSONDecodeError:
                        self.logger.log_error(f"无法解析角色侧写文件: {profile_path}")
        return json.dumps(profiles, ensure_ascii=False)

    def _finalize_chapter(self, chapter_data):
        print("\n--- [档案员] 正在定稿并归档本章内容 ---")
        NOVEL_FILE = self.config['novel_file_name']
        PROFILES_DIR = self.config['character_profiles_directory']
        
        chapter_text = " ".join(chapter_data.get("paragraphs", []))
        summary_of_new_content = self._call_api_with_schema("故事分析师", "为新章节生成摘要", prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=chapter_text), schemas.SUMMARY_SCHEMA)
        updated_profiles_paths = []
        if summary_of_new_content:
            id_data = self._call_api_with_schema("情报分析师", "从新章节摘要中识别人物", prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_of_new_content.get("summary","")), schemas.CHARACTER_IDENTIFICATION_SCHEMA)
            if id_data and id_data.get("characters"):
                for char_name in id_data["characters"]:
                    profile_path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(char_name)}_profile.json")
                    existing_profile = {}
                    if os.path.exists(profile_path):
                        with open(profile_path, "r", encoding="utf-8") as f: 
                            try:
                                existing_profile = json.load(f)
                            except json.JSONDecodeError:
                                self.logger.log_error(f"无法解析角色侧写文件: {profile_path}")
                    
                    updated_profile = self._call_api_with_schema("心理分析师", f"更新角色 {char_name} 的侧写", prompts.PROFILE_UPDATE_PROMPT.format(character_name=char_name, existing_profile=json.dumps(existing_profile, ensure_ascii=False), new_content=json.dumps(chapter_data, ensure_ascii=False)), schemas.UPDATED_CHARACTER_PROFILE_SCHEMA)
                    if updated_profile:
                        with open(profile_path, "w", encoding="utf-8") as f: json.dump(updated_profile, f, ensure_ascii=False, indent=4)
                        self.logger.log_write("心理分析师", profile_path, f"更新角色 {char_name} 的侧写")
                        updated_profiles_paths.append(profile_path)

        chapter_number = len(self.novel_data["chapters"]) + 1
        
        chapter_meta = {"chapter_number": chapter_number, "title": chapter_data.get("title", "无标题"), "pov_character": chapter_data.get("pov_character", "未知"), "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        final_chapter_obj = {"meta": chapter_meta, "content": chapter_data.get("paragraphs", [])}
        self.novel_data["chapters"].append(final_chapter_obj)
        
        with open(NOVEL_FILE, "w", encoding="utf-8") as f:
            json.dump(self.novel_data, f, ensure_ascii=False, indent=4)
        self.logger.log_write("档案员", NOVEL_FILE, f"写入第 {chapter_number} 章")

        full_text = " ".join(p for chap in self.novel_data["chapters"] for p in chap.get("content",[]))
        summary_json = self._call_api_with_schema("故事分析师", "生成新的全局摘要", prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=full_text[-5000:]), schemas.SUMMARY_SCHEMA)
        if summary_json:
             self.arc_state["real_world_summary"] = summary_json
             self._get_agent_confirmation("故事分析师", summary_json)
        
        self._save_arc_state()
        files_to_commit = [NOVEL_FILE, self.config['story_arc_file']] + updated_profiles_paths
        self.git.commit_and_push(files_to_commit, f"Chapter {chapter_number}: {chapter_meta['title']}")

    def run_cycle(self):
        if self.git.get_current_branch() != "main":
            if not self.git.switch_to_branch("main"):
                print("错误：无法切换到 'main' 分支，中止执行。")
                return
        
        self.arc_state = self._load_arc_state()
        self.novel_data = self._load_novel_data()
        summary_json = self.arc_state.get("real_world_summary")
        print(f"\n--- [系统] 加载当前故事摘要: {summary_json.get('summary')} ---")
        
        new_chapter_data = None
        
        try:
            # 核心修改：将会议调用提升到 run_cycle 层面
            if self.arc_state["current_location"] == "awaiting_meeting":
                print("\n--- [系统] 检测到大章节已完成，即将召开议会 ---")
                last_arc = self.arc_state.get("last_completed_arc")
                if last_arc:
                    roadmap_data, minutes_filepath = self.parliament.hold_meeting(self.arc_state, last_arc)
                    if roadmap_data and minutes_filepath:
                        self.arc_state["parliament_directive"] = roadmap_data
                        self.git.commit_and_push([minutes_filepath, self.config['story_arc_file']], f"Parliament Meeting after '{last_arc.get('movie_name') or last_arc.get('arc_title')}'")
                
                # 会议结束后，直接进入决策流程
                new_chapter_data = self._decide_and_execute_next_step(self.arc_state["real_world_summary"])

            elif self.arc_state["current_location"] == "init_world":
                new_chapter_data = self._start_new_movie_arc(summary_json, is_first_run=True)
            elif self.arc_state["current_location"] == "movie_world":
                new_chapter_data = self._handle_movie_arc_progression(summary_json)
            elif self.arc_state["current_location"] == "real_world":
                new_chapter_data = self._handle_real_world_arc_progression(summary_json)

        except Exception as e:
            self.logger.log_error(f"run_cycle 发生严重错误: {e}")
            raise e

        if not new_chapter_data:
            print("\n本轮循环为状态转换或规划，未生成最终章节。")
            self._save_arc_state() # 确保状态转换被保存
            return
            
        self._finalize_chapter(new_chapter_data)
        print("\n本轮循环完成。")

