import os
import json
import re
import time
import shutil
from datetime import datetime
import prompts
from llm_api import call_gemini
from utils import convert_name_to_filename
from logger_manager import LoggerManager
from parliament_manager import ParliamentManager

class StoryManager:
    """
    负责管理整个故事创作流程的核心类。
    (已升级，支持详细的API调用日志)
    """
    def __init__(self, config, git_manager):
        self.config = config
        self.git = git_manager
        self.api_key = config['gemini_api_key']
        self.logger = LoggerManager()
        self.parliament = ParliamentManager(config, git_manager, self.api_key, self.logger)
        self.arc_state = None
        self.story_text = ""

    # ... (prepare_for_new_story, _load_arc_state, _save_arc_state, _load_story_text 不变) ...
    def prepare_for_new_story(self):
        print("\n--- 正在清理环境，准备开始全新故事 ---")
        output_dir = "output"
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
                print(f"环境清理完成: 已删除 '{output_dir}' 目录及其所有内容。")
            except Exception as e:
                print(f"清理环境时出错: {e}")
        else:
            print("环境已是干净状态，无需清理。")
        # 重新创建logger实例以确保目录存在
        self.logger = LoggerManager()

    def _load_arc_state(self):
        ARC_STATE_FILE = self.config['story_arc_file']
        if os.path.exists(ARC_STATE_FILE):
            self.logger.log_read("StoryManager", ARC_STATE_FILE, "加载故事世界状态")
            with open(ARC_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                if "completed_movie_arcs" not in state: state["completed_movie_arcs"] = []
                if "current_real_world_arc" not in state: state["current_real_world_arc"] = None
                return state
        return {
            "protagonist_name": "江浩", "protagonist_tools": [], "current_location": "init_world",
            "real_world_summary": "故事的开端。主角江浩是一名中国的普通待业青年。",
            "current_movie_arc": None, "completed_movie_arcs": [], "current_real_world_arc": None
        }

    def _save_arc_state(self):
        ARC_STATE_FILE = self.config['story_arc_file']
        output_dir = os.path.dirname(ARC_STATE_FILE)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(ARC_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.arc_state, f, ensure_ascii=False, indent=4)
        self.logger.log_write("StoryManager", ARC_STATE_FILE, "保存故事世界状态")

    def _load_story_text(self):
        NOVEL_FILE = self.config['novel_file_name']
        output_dir = os.path.dirname(NOVEL_FILE)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        if os.path.exists(NOVEL_FILE):
            self.logger.log_read("StoryManager", NOVEL_FILE, "加载小说全文")
            with open(NOVEL_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return ""

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
        
        prompt = prompts.AGENT_CONFIRMATION_PROMPT.format(
            agent_role=agent_role, agent_output=agent_output
        )
        confirmation = self._call_api("AI助理", f"为 {agent_role} 的输出生成人性化确认信息", prompt)
        if confirmation:
            print(f"\n{confirmation}\n")

    def _plan_new_movie_arc(self):
        print("\n--- [电影世界架构师] 开始规划新的电影世界 ---")
        WORK_DIR = "output/temp/movie_arc_planning"; os.makedirs(WORK_DIR, exist_ok=True)
        movie_name_file = os.path.join(WORK_DIR, "00_movie_name.txt")
        
        if os.path.exists(movie_name_file):
            with open(movie_name_file, 'r', encoding='utf-8') as f: movie_name = f.read()
        else:
            movie_name = self._call_api("电影世界架构师", "选择下一部电影", prompts.MOVIE_SELECTION_PROMPT)
            if not movie_name: return None, []
            with open(movie_name_file, 'w', encoding='utf-8') as f: f.write(movie_name)

        draft_plan_file = os.path.join(WORK_DIR, "01_draft_plan.json")
        if os.path.exists(draft_plan_file):
            with open(draft_plan_file, 'r', encoding='utf-8') as f: draft_plan_json_str = f.read()
        else:
            _, draft_plan_json_str = self._call_api_for_json("电影世界架构师", f"为《{movie_name}》生成大纲初稿", prompts.MOVIE_ANALYSIS_PROMPT.format(movie_name=movie_name))
            if not draft_plan_json_str: return None, []
            with open(draft_plan_file, 'w', encoding='utf-8') as f: f.write(draft_plan_json_str)

        polished_plan_json_str = draft_plan_json_str
        for i in range(self.config['rewrite_cycles']):
            cycle = i + 1
            rewrite_file = os.path.join(WORK_DIR, f"02_rewrite_{cycle}.json")
            if os.path.exists(rewrite_file):
                with open(rewrite_file, 'r', encoding='utf-8') as f: polished_plan_json_str = f.read()
                continue
            
            feedback = self._call_api("总编", f"审查《{movie_name}》大纲 (第 {cycle} 轮)", prompts.ARCHITECT_REVIEW_PROMPT.format(movie_plan_draft=polished_plan_json_str))
            if not feedback: continue
            self._get_agent_confirmation("总编", feedback)
            
            _, rewritten_plan_json_str = self._call_api_for_json("电影世界架构师", f"重写《{movie_name}》大纲 (第 {cycle} 轮)", prompts.ARCHITECT_REWRITE_PROMPT.format(original_plan=polished_plan_json_str, feedback=feedback))
            if not rewritten_plan_json_str: break
            
            polished_plan_json_str = rewritten_plan_json_str
            with open(rewrite_file, 'w', encoding='utf-8') as f: f.write(polished_plan_json_str)
        
        final_plan_data, _ = self._call_api_for_json("系统工具", "格式化最终电影大纲JSON", f"请格式化并返回这个JSON:\n{polished_plan_json_str}")
        if not final_plan_data: return None, []
        self._get_agent_confirmation("电影世界架构师", final_plan_data)

        scenes = final_plan_data.get("scenes", [])
        arc = {"movie_name": movie_name, "status": "active", "current_scene_index": -1, "total_scenes": len(scenes), "movie_plan": final_plan_data.get("overall_setting", {}), "scenes": scenes}
        new_profile_paths = self._create_character_profiles(final_plan_data.get("character_pool", []))
        shutil.rmtree(WORK_DIR)
        return arc, new_profile_paths

    def _plan_real_world_arc(self, summary_before):
        print("\n--- [悬疑剧编剧] 开始规划现实世界主线 ---")
        last_movie_name = self.arc_state["completed_movie_arcs"][-1]['movie_name'] if self.arc_state["completed_movie_arcs"] else "无"
        
        draft_prompt = prompts.REAL_WORLD_ARC_ANALYSIS_PROMPT.format(
            real_world_summary=summary_before, protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
            last_movie_name=last_movie_name)
        _, polished_plan_json_str = self._call_api_for_json("悬疑剧编剧", "规划现实世界章节", draft_prompt)
        if not polished_plan_json_str: return None, []

        for i in range(self.config['rewrite_cycles']):
            cycle = i + 1
            feedback = self._call_api("悬疑剧总编", f"审查现实大纲 (第 {cycle} 轮)", prompts.REAL_WORLD_ARC_REVIEW_PROMPT.format(real_world_plan_draft=polished_plan_json_str))
            if not feedback: continue
            self._get_agent_confirmation("悬疑剧总编", feedback)

            _, rewritten_plan_json_str = self._call_api_for_json("悬疑剧编剧", f"重写现实大纲 (第 {cycle} 轮)", prompts.REAL_WORLD_ARC_REWRITE_PROMPT.format(original_plan=polished_plan_json_str, feedback=feedback))
            if not rewritten_plan_json_str: break
            polished_plan_json_str = rewritten_plan_json_str
        
        final_plan_data, _ = self._call_api_for_json("系统工具", "格式化最终现实大纲JSON", f"请格式化并返回这个JSON:\n{polished_plan_json_str}")
        if not final_plan_data: return None, []
        self._get_agent_confirmation("悬疑剧编剧", final_plan_data)

        scenes = final_plan_data.get("scenes", [])
        arc = {"arc_title": final_plan_data.get("arc_title", "未命名"), "status": "active", "current_scene_index": -1, "total_scenes": len(scenes), "scenes": scenes}
        new_profile_paths = self._create_character_profiles(final_plan_data.get("character_pool", []))
        return arc, new_profile_paths

    def _generate_movie_chapter(self, movie_arc, summary_before, is_first_chapter_ever=False):
        scene_index = movie_arc["current_scene_index"]
        scene_plan = movie_arc["scenes"][scene_index]
        chapter_subtitle = scene_plan["subtitle"]
        
        WORK_DIR = f"output/temp/chapter_{len(re.findall(r'# 第', self.story_text)) + 1}"; os.makedirs(WORK_DIR, exist_ok=True)
        gen_prompt = self._build_generation_prompt(movie_arc, scene_plan, summary_before, is_first_chapter_ever)

        draft_file = os.path.join(WORK_DIR, "01_draft.txt")
        if os.path.exists(draft_file):
            with open(draft_file, 'r', encoding='utf-8') as f: polished_content = f.read()
        else:
            polished_content = self._call_api("小说家", f"创作章节初稿: {chapter_subtitle}", gen_prompt)
            if not polished_content: return None, None, None
            with open(draft_file, 'w', encoding='utf-8') as f: f.write(polished_content)
        
        for i in range(self.config['rewrite_cycles']):
            cycle = i + 1
            rewrite_file = os.path.join(WORK_DIR, f"02_rewrite_{cycle}.txt")
            if os.path.exists(rewrite_file):
                 with open(rewrite_file, 'r', encoding='utf-8') as f: polished_content = f.read()
                 continue
            
            feedback = self._call_api("文学编辑", f"审查章节: {chapter_subtitle} (第 {cycle} 轮)", prompts.REVIEW_PROMPT_TEMPLATE.format(chapter_text=polished_content, movie_plan=json.dumps(movie_arc.get('movie_plan', {})), chapter_subtitle=chapter_subtitle, emotional_anchor=scene_plan.get("emotion", "未知")))
            if not feedback: continue
            self._get_agent_confirmation("文学编辑", feedback)

            all_profiles_text = "无" if is_first_chapter_ever else self._get_character_profiles_text(summary_before)
            rewrite_prompt = prompts.REWRITE_PROMPT_TEMPLATE.format(movie_plan=json.dumps(movie_arc.get('movie_plan', {})), summary_text=summary_before, character_profiles_text=all_profiles_text, protagonist_tools=json.dumps(self.arc_state['protagonist_tools']), character_pov=scene_plan.get("pov_character"), original_text=polished_content, feedback=feedback, chapter_subtitle=chapter_subtitle, emotional_anchor=scene_plan.get("emotion", "未知"))
            rewritten_content = self._call_api("小说家", f"重写章节: {chapter_subtitle} (第 {cycle} 轮)", rewrite_prompt)
            
            if rewritten_content:
                polished_content = rewritten_content
                with open(rewrite_file, 'w', encoding='utf-8') as f: f.write(polished_content)

        shutil.rmtree(WORK_DIR)
        return polished_content, scene_plan.get("pov_character", self.arc_state["protagonist_name"]), chapter_subtitle

    # ... ( _build_generation_prompt 和 _generate_real_world_chapter 类似地添加API调用日志) ...
    def _build_generation_prompt(self, movie_arc, scene_plan, summary_before, is_first_chapter_ever):
        movie_plan_str = json.dumps(movie_arc.get('movie_plan', {}), ensure_ascii=False, indent=2)
        meta_foreshadowing = movie_arc.get('movie_plan', {}).get('meta_narrative_foreshadowing', {})
        meta_instruction = "本章无需展现元叙事感。"
        if scene_plan.get('scene_number') == meta_foreshadowing.get('trigger_scene', -1):
            meta_instruction = f"**演绎元叙事感:** {meta_foreshadowing.get('content', '')}"
        if is_first_chapter_ever:
            return prompts.FIRST_CHAPTER_PROMPT_TEMPLATE.format(movie_plan=movie_plan_str, movie_name=movie_arc['movie_name'], chapter_subtitle=scene_plan["subtitle"], emotional_anchor=scene_plan.get("emotion", "未知"), meta_narrative_instruction=meta_instruction)
        else:
            return prompts.GENERATION_PROMPT_TEMPLATE.format(movie_plan=movie_plan_str, character_pov=scene_plan.get("pov_character", self.arc_state["protagonist_name"]), summary_text=summary_before, character_profiles_text=self._get_character_profiles_text(summary_before), chapter_subtitle=scene_plan["subtitle"], emotional_anchor=scene_plan.get("emotion", "未知"), protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False), meta_narrative_instruction=meta_instruction)

    def _generate_real_world_chapter(self, rw_arc, summary_before):
        scene_index = rw_arc["current_scene_index"]
        scene_plan = rw_arc["scenes"][scene_index]
        chapter_subtitle = scene_plan["subtitle"]
        pov_character_name = scene_plan.get("pov_character", self.arc_state["protagonist_name"])
        gen_prompt = prompts.REAL_WORLD_GENERATION_PROMPT.format(summary_text=summary_before, protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False), chapter_subtitle=chapter_subtitle, synopsis=scene_plan['synopsis'], emotion_anchor=scene_plan.get("emotion_anchor", "未知"), character_pov=pov_character_name)
        new_content = self._call_api("悬疑小说家", f"创作现实章节: {chapter_subtitle}", gen_prompt)
        return new_content, pov_character_name, chapter_subtitle

    def _handle_movie_arc_progression(self, summary_before):
        movie_arc = self.arc_state["current_movie_arc"]
        if movie_arc["current_scene_index"] >= movie_arc["total_scenes"] - 1:
            print(f"\n电影《{movie_arc['movie_name']}》已完结，回归现实世界...")
            roadmap_data, minutes_filepath = self.parliament.hold_meeting(self.arc_state, movie_arc)
            if roadmap_data and minutes_filepath:
                self.arc_state["parliament_directive"] = roadmap_data
                self._save_arc_state()
                self.git.commit_and_push([minutes_filepath, self.config['story_arc_file']], f"Parliament Meeting after '{movie_arc['movie_name']}'")
            
            self.arc_state["current_location"] = "real_world"
            movie_arc["status"] = "completed"
            self.arc_state["completed_movie_arcs"].append(movie_arc)
            self.arc_state["current_movie_arc"] = None
            
            tool_data, _ = self._call_api_for_json("道具设计师", f"为《{movie_arc['movie_name']}》设计纪念道具", prompts.TOOL_CREATION_PROMPT.format(movie_name=movie_arc['movie_name']))
            if tool_data and isinstance(tool_data, dict):
                self.arc_state["protagonist_tools"].append(tool_data)
                self._get_agent_confirmation("道具设计师", tool_data)
            return None, None, None
        else:
            movie_arc["current_scene_index"] += 1
            return self._generate_movie_chapter(movie_arc, summary_before)

    def _handle_real_world_arc_progression(self, summary_before):
        rw_arc = self.arc_state["current_real_world_arc"]
        rw_arc["current_scene_index"] += 1
        return self._generate_real_world_chapter(rw_arc, summary_before)

    def _start_new_movie_arc(self, summary_before, is_first_run=False):
        arc, new_profile_paths = self._plan_new_movie_arc()
        if not arc: return None, None, None
        self.arc_state["current_movie_arc"] = arc
        self.arc_state["current_location"] = "movie_world"
        self._save_arc_state()
        self.git.commit_and_push([self.config['story_arc_file']] + new_profile_paths, f"Architect Plan (Movie): {arc['movie_name']}")
        arc["current_scene_index"] += 1
        return self._generate_movie_chapter(arc, summary_before, is_first_chapter_ever=is_first_run)

    def _decide_and_execute_next_step(self, summary_before):
        print("\n--- [故事导演] 开始决策下一步剧情走向 ---")
        completed_movies_list = [arc['movie_name'] for arc in self.arc_state['completed_movie_arcs']]
        prompt = prompts.NEXT_STEP_DECISION_PROMPT.format(real_world_summary=summary_before, protagonist_tools=json.dumps(self.arc_state['protagonist_tools']), completed_movies=json.dumps(completed_movies_list))
        decision_data, _ = self._call_api_for_json("故事导演", "决策下一步剧情走向", prompt)
        if not decision_data or "decision" not in decision_data:
            decision_data = {"decision": "REAL_WORLD", "reasoning": "决策失败，默认选项。"}
        self._get_agent_confirmation("故事导演", decision_data)

        if decision_data["decision"] == "REAL_WORLD":
            arc, new_profile_paths = self._plan_real_world_arc(summary_before)
            if not arc: return None, None, None
            self.arc_state["current_real_world_arc"] = arc
            self._save_arc_state()
            self.git.commit_and_push([self.config['story_arc_file']] + new_profile_paths, f"Architect Plan (Real World): {arc['arc_title']}")
            return self._handle_real_world_arc_progression(summary_before)
        else:
            return self._start_new_movie_arc(summary_before)

    def _create_character_profiles(self, character_pool):
        if not character_pool: return []
        new_profile_paths = []
        PROFILES_DIR = self.config['character_profiles_directory']; os.makedirs(PROFILES_DIR, exist_ok=True)
        for char_data in character_pool:
            char_name, initial_profile = char_data.get("name"), char_data.get("initial_profile")
            if char_name and initial_profile:
                profile_path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(char_name)}_profile.md")
                with open(profile_path, "w", encoding="utf-8") as f: f.write(initial_profile)
                self.logger.log_write("档案员", profile_path, f"创建角色 {char_name} 的初始侧写")
                new_profile_paths.append(profile_path)
        return new_profile_paths

    def _get_character_profiles_text(self, summary_text):
        character_names_str = self._call_api("情报分析师", "从摘要中识别角色", prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_text))
        if not character_names_str or character_names_str.lower() == "无": return "..."
        
        character_names = [name.strip() for name in character_names_str.split(',') if name.strip()]
        profile_contents = []
        PROFILES_DIR = self.config['character_profiles_directory']
        for name in character_names:
            profile_path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(name)}_profile.md")
            if os.path.exists(profile_path):
                self.logger.log_read("情报分析师", profile_path, f"为章节生成加载角色 {name} 的侧写")
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile_contents.append(f"--- 角色: {name} ---\n{f.read()}\n")
        return "\n".join(profile_contents) if profile_contents else "..."

    def _finalize_chapter(self, new_content, pov_character_name, chapter_subtitle):
        print("\n--- [档案员] 正在定稿并归档本章内容 ---")
        NOVEL_FILE = self.config['novel_file_name']
        PROFILES_DIR = self.config['character_profiles_directory']
        
        summary_of_new_content = self._call_api("故事分析师", "总结新章节内容", prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=new_content))
        updated_profiles_paths = []
        if summary_of_new_content:
            character_names_str = self._call_api("情报分析师", "识别新章节出场角色", prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_of_new_content))
            if character_names_str and character_names_str.lower() != '无':
                for char_name in [name.strip() for name in character_names_str.split(',') if name.strip()]:
                    profile_path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(char_name)}_profile.md")
                    existing_profile = ""
                    if os.path.exists(profile_path):
                        with open(profile_path, "r", encoding="utf-8") as f: existing_profile = f.read()
                    
                    updated_profile = self._call_api("心理分析师", f"更新角色 {char_name} 的侧写", prompts.PROFILE_UPDATE_PROMPT.format(character_name=char_name, existing_profile=existing_profile, new_content=new_content))
                    if updated_profile:
                        with open(profile_path, "w", encoding="utf-8") as f: f.write(updated_profile)
                        self.logger.log_write("心理分析师", profile_path, f"更新角色 {char_name} 的侧写")
                        updated_profiles_paths.append(profile_path)

        next_chapter_number = len(re.findall(r"# 第 (\d+) 章", self.story_text)) + 1
        location_info = "..." # Simplified location logic for brevity
        header = f"# 第 {next_chapter_number} 章: {chapter_subtitle} (视点: {pov_character_name})\n\n**地点:** {location_info} \n**写作于:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        write_mode = "a" if self.story_text else "w"
        with open(NOVEL_FILE, write_mode, encoding="utf-8") as f:
            if write_mode == 'a': f.write("\n\n---\n\n")
            f.write(header + new_content + "\n")
        self.logger.log_write("小说家", NOVEL_FILE, f"写入第 {next_chapter_number} 章")

        with open(NOVEL_FILE, "r", encoding="utf-8") as f: self.story_text = f.read()
        summary_after = self._call_api("故事分析师", "生成新的全局摘要", prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=self.story_text))
        if summary_after:
             self.arc_state["real_world_summary"] = summary_after
             self._get_agent_confirmation("故事分析师", f"已生成新的全局摘要，当前核心悬念是：{summary_after.split('。')[0]}。")

        self._save_arc_state()
        files_to_commit = [NOVEL_FILE, self.config['story_arc_file']] + updated_profiles_paths
        self.git.commit_and_push(files_to_commit, f"Chapter {next_chapter_number}: {chapter_subtitle}")

    def run_cycle(self):
        if self.git.get_current_branch() != "main":
            if not self.git.switch_to_branch("main"): return
        os.makedirs(self.config['character_profiles_directory'], exist_ok=True)
        self.arc_state = self._load_arc_state()
        self.story_text = self._load_story_text()
        summary_before = self.arc_state.get("real_world_summary", "...")
        print(f"\n--- [系统] 加载当前故事摘要 ---\n{summary_before}\n--------------------")
        
        new_content, pov_character_name, chapter_subtitle = None, None, None
        
        if self.arc_state["current_location"] == "init_world":
            new_content, pov_character_name, chapter_subtitle = self._start_new_movie_arc(summary_before, is_first_run=True)
        elif self.arc_state["current_location"] == "movie_world":
            new_content, pov_character_name, chapter_subtitle = self._handle_movie_arc_progression(summary_before)
            if not new_content:
                 new_content, pov_character_name, chapter_subtitle = self._decide_and_execute_next_step(self.arc_state["real_world_summary"])
        elif self.arc_state["current_location"] == "real_world":
            rw_arc = self.arc_state.get("current_real_world_arc")
            if rw_arc and rw_arc["current_scene_index"] < rw_arc["total_scenes"] - 1:
                new_content, pov_character_name, chapter_subtitle = self._handle_real_world_arc_progression(summary_before)
            else:
                if rw_arc: self.arc_state["current_real_world_arc"] = None
                new_content, pov_character_name, chapter_subtitle = self._decide_and_execute_next_step(summary_before)

        if not new_content:
            print("\n本轮循环为状态转换或规划，未生成最终章节。")
            return
            
        self._finalize_chapter(new_content, pov_character_name, chapter_subtitle)
        print("\n本轮循环完成。")

