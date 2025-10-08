import os
import json
import random
import re
import time
from datetime import datetime
import prompts
from llm_api import call_gemini
from utils import convert_name_to_filename

class StoryManager:
    """
    负责管理整个故事创作流程的核心类。
    包括状态管理、情节规划、章节生成与定稿。
    """
    def __init__(self, config, git_manager):
        self.config = config
        self.git = git_manager
        self.api_key = config['gemini_api_key']
        # 状态和文本的加载推迟到 run_cycle 中，以确保在正确的分支上执行
        self.arc_state = None
        self.story_text = ""

    def _load_arc_state(self):
        """读取或初始化故事世界状态"""
        ARC_STATE_FILE = self.config['story_arc_file']
        if os.path.exists(ARC_STATE_FILE):
            with open(ARC_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                # 向后兼容，确保旧的状态文件有completed_movie_arcs
                if "completed_movie_arcs" not in state:
                    state["completed_movie_arcs"] = []
                return state
        return {
            "protagonist_name": "江浩",
            "protagonist_tools": [],
            "current_location": "real_world",
            "real_world_summary": "江浩，一个中国的待业青年，最近失业在家，对未来感到迷茫。故事从他百无聊赖的生活开始。",
            "current_movie_arc": None,
            "completed_movie_arcs": [] # 新增，用于存储已完成的电影世界
        }

    def _save_arc_state(self):
        """保存故事世界状态"""
        ARC_STATE_FILE = self.config['story_arc_file']
        output_dir = os.path.dirname(ARC_STATE_FILE)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(ARC_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.arc_state, f, ensure_ascii=False, indent=4)

    def _load_story_text(self):
        """加载小说全文"""
        NOVEL_FILE = self.config['novel_file_name']
        output_dir = os.path.dirname(NOVEL_FILE)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        if os.path.exists(NOVEL_FILE):
            with open(NOVEL_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def prepare_for_new_story(self):
        """清理所有旧的故事文件，为新故事做准备。"""
        print("\n--- 正在清理环境，准备开始全新故事 ---")
        output_dir = os.path.dirname(self.config['novel_file_name'])
        if output_dir and os.path.exists(output_dir):
            import shutil
            for filename in os.listdir(output_dir):
                file_path = os.path.join(output_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')
        print("环境清理完成。")
        
    def _call_gemini_and_parse_json(self, prompt, max_retries=3):
        """
        调用 Gemini API 期望获得JSON响应，并包含校验和重试逻辑。
        """
        for attempt in range(max_retries):
            print(f"正在尝试第 {attempt + 1}/{max_retries} 次生成和解析JSON...")
            json_str = call_gemini(prompt, self.api_key)
            if not json_str:
                print("API调用未能返回内容，将重试...")
                time.sleep(2) # 短暂暂停后重试
                continue

            try:
                # 更积极地清理字符串，以防AI添加了Markdown标记
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if not match:
                    raise json.JSONDecodeError("响应中未找到有效的JSON结构。", json_str, 0)
                
                cleaned_json_str = match.group(0)
                json_obj = json.loads(cleaned_json_str)
                print("JSON生成和解析成功。")
                return json_obj, cleaned_json_str # 同时返回对象和干净的字符串
            except json.JSONDecodeError as e:
                print(f"警告：JSON解析失败: {e}")
                if attempt < max_retries - 1:
                    print("AI可能返回了不完整的JSON，将重试。")
                else:
                    print("已达到最大重试次数，无法获取有效的JSON。")
                    print("\n--- DEBUG: 最终解析失败的JSON字符串 ---")
                    print(json_str)
                    print("---------------------------------\n")
        return None, None # 所有重试都失败了

    def _plan_new_arc(self):
        """规划一个新的电影世界（大章节），包含审稿和重写流程。"""
        print("\n--- 正在规划新的电影世界 ---")
        
        new_movie = call_gemini(prompts.MOVIE_SELECTION_PROMPT, self.api_key)
        if not new_movie: return None, []

        # --- 大纲初稿 ---
        draft_plan_data, draft_plan_json_str = self._call_gemini_and_parse_json(
            prompts.MOVIE_ANALYSIS_PROMPT.format(movie_name=new_movie)
        )
        if not draft_plan_data: return None, []
        
        # --- 大纲审稿与重写循环 ---
        print("\n--- 开始剧情大纲审稿与重写流程 ---")
        polished_plan_json_str = draft_plan_json_str
        for i in range(self.config['rewrite_cycles']):
            print(f"\n--- 第 {i + 1} / {self.config['rewrite_cycles']} 轮大纲打磨 ---")
            review_prompt = prompts.ARCHITECT_REVIEW_PROMPT.format(movie_plan_draft=polished_plan_json_str)
            feedback = call_gemini(review_prompt, self.api_key)
            if not feedback:
                print("大纲审稿失败，跳过本轮重写。")
                continue
            
            print(f"--- 总编反馈 ---\n{feedback}\n----------------")
            
            rewrite_prompt = prompts.ARCHITECT_REWRITE_PROMPT.format(original_plan=polished_plan_json_str, feedback=feedback)
            
            # 在重写时也使用带校验的调用
            rewritten_plan_data, rewritten_plan_json_str = self._call_gemini_and_parse_json(rewrite_prompt)
            if not rewritten_plan_data:
                print("大纲重写失败，保留上一版本。")
                break
            polished_plan_json_str = rewritten_plan_json_str
        
        print("\n--- 剧情大纲打磨完成 ---")
        
        # 最终解析已经由 _call_gemini_and_parse_json 完成
        final_plan_data, final_plan_str = self._call_gemini_and_parse_json(f"请格式化并返回这个JSON:\n{polished_plan_json_str}")
        if not final_plan_data:
             return None, []

        scenes = final_plan_data.get("scenes", [])
        for scene in scenes:
            scene["summary_before"] = None
            scene["summary_after"] = None
            scene["review_feedback"] = None
            if "emotion_anchor" in scene:
                scene["emotion"] = scene.pop("emotion_anchor")

        arc = {
            "movie_name": new_movie,
            "status": "active",
            "current_scene_index": -1,
            "total_scenes": len(scenes),
            "movie_plan": final_plan_data.get("overall_setting", {}),
            "scenes": scenes
        }
        
        new_profile_paths = []
        PROFILES_DIR = self.config['character_profiles_directory']
        os.makedirs(PROFILES_DIR, exist_ok=True)
        character_pool = final_plan_data.get("character_pool", [])
        for char_data in character_pool:
            char_name = char_data.get("name")
            initial_profile = char_data.get("initial_profile")
            if char_name and initial_profile:
                profile_filename = f"{convert_name_to_filename(char_name)}_profile.md"
                profile_path = os.path.join(PROFILES_DIR, profile_filename)
                with open(profile_path, "w", encoding="utf-8") as f:
                    f.write(initial_profile)
                new_profile_paths.append(profile_path)
        
        print(f"电影《{new_movie}》规划完成，共 {len(arc['scenes'])} 个场景。")
        return arc, new_profile_paths


    def _handle_movie_chapter(self, summary_before):
        """处理电影世界中的一个场景章节"""
        movie_arc = self.arc_state["current_movie_arc"]
        scene_index = movie_arc["current_scene_index"]
        
        if scene_index < 0 or scene_index >= len(movie_arc["scenes"]):
            return None, None
            
        scene_plan = movie_arc["scenes"][scene_index]
        scene_plan["summary_before"] = summary_before
        
        chapter_subtitle = scene_plan["subtitle"]
        emotional_anchor = scene_plan.get("emotion", "未知")
        print(f"\n--- 本章主题 (副标题): {chapter_subtitle} ---")
        print(f"--- 核心情绪锚点: {emotional_anchor} ---")

        is_first_scene = (scene_index == 0)
        movie_plan_str = json.dumps(movie_arc.get('movie_plan', {}), ensure_ascii=False, indent=2)

        meta_narrative_foreshadowing = movie_arc.get('movie_plan', {}).get('meta_narrative_foreshadowing', {})
        trigger_scene = meta_narrative_foreshadowing.get('trigger_scene', -1)
        meta_narrative_instruction = "本章无需展现元叙事感。"
        if scene_plan.get('scene_number') == trigger_scene:
            meta_narrative_instruction = f"**演绎元叙事感:** {meta_narrative_foreshadowing.get('content', '')}"


        if is_first_scene: 
            generation_prompt = prompts.FIRST_CHAPTER_PROMPT_TEMPLATE.format(
                movie_plan=movie_plan_str, movie_name=movie_arc['movie_name'],
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor,
                meta_narrative_instruction=meta_narrative_instruction
            )
            pov_character_name = self.arc_state["protagonist_name"]
            all_profiles_text = "无"
        else: 
            character_names_str = call_gemini(prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_before), self.api_key)
            all_profiles_text = "本章没有特定角色的侧写信息。"
            if character_names_str and character_names_str.lower() != "无":
                character_names = [name.strip() for name in character_names_str.split(',') if name.strip()]
                print(f"识别到出场人物: {character_names}")
                profile_contents = []
                for name in character_names:
                    profile_path = os.path.join(self.config['character_profiles_directory'], f"{convert_name_to_filename(name)}_profile.md")
                    if os.path.exists(profile_path):
                        with open(profile_path, 'r', encoding='utf-8') as f:
                            profile_contents.append(f"--- 角色: {name} ---\n{f.read()}\n")
                if profile_contents: all_profiles_text = "\n".join(profile_contents)
            
            pov_character_name = scene_plan.get("pov_character", self.arc_state["protagonist_name"])
            print(f"\n--- 架构师预设本章视点为: {pov_character_name} ---")

            generation_prompt = prompts.GENERATION_PROMPT_TEMPLATE.format(
                movie_plan=movie_plan_str, character_pov=pov_character_name, 
                summary_text=summary_before, character_profiles_text=all_profiles_text,
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor,
                protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
                meta_narrative_instruction=meta_narrative_instruction
            )

        draft_content = call_gemini(generation_prompt, self.api_key)
        if not draft_content: return None, None

        polished_content = draft_content
        final_feedback = ""
        for i in range(self.config['rewrite_cycles']):
            print(f"\n--- 第 {i + 1} / {self.config['rewrite_cycles']} 轮打磨 ---")
            review_prompt = prompts.REVIEW_PROMPT_TEMPLATE.format(
                chapter_text=polished_content, movie_plan=movie_plan_str,
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
            )
            feedback = call_gemini(review_prompt, self.api_key)
            if not feedback: 
                print("审稿失败，跳过本轮重写。")
                continue
            
            print(f"--- 编辑反馈 ---\n{feedback}\n----------------")
            final_feedback = feedback

            rewrite_prompt = prompts.REWRITE_PROMPT_TEMPLATE.format(
                movie_plan=movie_plan_str, summary_text=summary_before,
                character_profiles_text=all_profiles_text,
                protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
                character_pov=pov_character_name, original_text=polished_content,
                feedback=feedback, chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
            )
            rewritten_content = call_gemini(rewrite_prompt, self.api_key)
            if not rewritten_content:
                print("重写失败，保留上一版本内容。")
                break
            polished_content = rewritten_content
        
        scene_plan["review_feedback"] = final_feedback
        
        return polished_content, pov_character_name

    def _handle_real_world_chapter(self, summary_before):
        """处理现实世界中的一个章节"""
        print("\n--- 开始创作现实世界主线剧情 ---")
        self.arc_state["real_world_summary"] = summary_before
        
        generation_prompt = prompts.REAL_WORLD_GENERATION_PROMPT.format(
            real_world_summary=summary_before,
            protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False)
        )
        
        new_content = call_gemini(generation_prompt, self.api_key)
        pov_character_name = self.arc_state["protagonist_name"]
        
        return new_content, pov_character_name

    def _handle_movie_arc_progression(self, summary_before):
        """处理电影世界中的情节推进"""
        movie_arc = self.arc_state["current_movie_arc"]
        
        if movie_arc["current_scene_index"] >= movie_arc["total_scenes"] - 1:
            print(f"电影《{movie_arc['movie_name']}》已完结，回归现实世界...")
            self.arc_state["current_location"] = "real_world"
            movie_arc["status"] = "completed"
            self.arc_state["completed_movie_arcs"].append(movie_arc)
            self.arc_state["current_movie_arc"] = None

            if movie_arc["movie_name"]:
                new_tool, _ = self._call_gemini_and_parse_json(
                    prompts.TOOL_CREATION_PROMPT.format(movie_name=movie_arc['movie_name'])
                )
                if new_tool and isinstance(new_tool, dict):
                    self.arc_state["protagonist_tools"].append(new_tool)
                    print(f"获得新工具: {new_tool.get('tool_name')}")
                else:
                    print(f"错误：未能为《{movie_arc['movie_name']}》生成有效的纪念品工具。")
            
            new_content, pov_character_name = self._handle_real_world_chapter(summary_before)
            return new_content, pov_character_name, "现实的谜团"
        else:
            movie_arc["current_scene_index"] += 1
            scene_plan = movie_arc["scenes"][movie_arc["current_scene_index"]]
            print(f"\n--- 当前电影:《{movie_arc['movie_name']}》 | 场景 {scene_plan['scene_number']} (第 {scene_plan['day']} 天 - {scene_plan['part_of_day']}) ---")
            new_content, pov_character_name = self._handle_movie_chapter(summary_before)
            return new_content, pov_character_name, scene_plan["subtitle"]

    def _handle_real_world_progression(self):
        """处理现实世界结束，进入新电影世界的情节"""
        print("现实世界剧情暂告一段落，准备进入新的恐怖电影...")
        self.arc_state["current_location"] = "movie_world"
        
        arc, new_profile_paths = self._plan_new_arc()
        if not arc: return None, None, None
        self.arc_state["current_movie_arc"] = arc
        
        self._save_arc_state()
        files_to_commit = [self.config['story_arc_file']] + new_profile_paths
        self.git.commit_and_push(files_to_commit, f"Architect Plan: {self.arc_state['current_movie_arc']['movie_name']}")

        self.arc_state["current_movie_arc"]["current_scene_index"] += 1
        new_content, pov_character_name = self._handle_movie_chapter("无（这是电影世界的第一个场景）")
        chapter_subtitle = self.arc_state["current_movie_arc"]["scenes"][0]["subtitle"]
        return new_content, pov_character_name, chapter_subtitle

    def _finalize_chapter(self, new_content, pov_character_name, chapter_subtitle):
        """将最终章节内容写入文件并提交"""
        NOVEL_FILE = self.config['novel_file_name']
        PROFILES_DIR = self.config['character_profiles_directory']
        
        summary_of_new_content = call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=new_content), self.api_key)
        character_names_str = call_gemini(prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_of_new_content), self.api_key)
        
        updated_profiles_paths = []
        if character_names_str and character_names_str.lower() != '无':
            characters_in_chapter = [name.strip() for name in character_names_str.split(',') if name.strip()]
            print(f"正在为本章出现的角色更新侧写: {characters_in_chapter}")
            
            for char_name in characters_in_chapter:
                profile_filename = f"{convert_name_to_filename(char_name)}_profile.md"
                profile_path = os.path.join(PROFILES_DIR, profile_filename)
                
                existing_profile = ""
                if os.path.exists(profile_path):
                    with open(profile_path, "r", encoding="utf-8") as f: existing_profile = f.read()
                else:
                    movie_name = self.arc_state.get("current_movie_arc", {}).get("movie_name", "未知电影")
                    existing_profile = f"# {char_name} 的角色侧写\n\n- 在《{movie_name}》篇章中首次出场。"

                is_protagonist = (char_name == self.arc_state["protagonist_name"])
                profile_prompt = prompts.PROFILE_UPDATE_PROMPT.format(
                    character_name=char_name, existing_profile=existing_profile, new_content=new_content
                )
                if not is_protagonist:
                    profile_prompt = profile_prompt.replace("背景慢速揭示 (仅限主角):", "")

                updated_profile = call_gemini(profile_prompt, self.api_key)
                if updated_profile:
                    os.makedirs(PROFILES_DIR, exist_ok=True)
                    with open(profile_path, "w", encoding="utf-8") as f: f.write(updated_profile)
                    updated_profiles_paths.append(profile_path)

        next_chapter_number = len(re.findall(r"# 第 (\d+) 章", self.story_text)) + 1
        
        scene_info, current_scene_log = "", None
        if self.arc_state["current_location"] == "movie_world":
            scene = self.arc_state["current_movie_arc"]["scenes"][self.arc_state["current_movie_arc"]["current_scene_index"]]
            scene_info = f"{self.arc_state['current_movie_arc']['movie_name']} - 场景 {scene['scene_number']}"
            current_scene_log = scene
        else:
            scene_info = "现实世界"

        header = f"# 第 {next_chapter_number} 章: {chapter_subtitle} (视点: {pov_character_name})\n\n**地点:** {scene_info}  \n**写作于:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        write_mode = "a" if os.path.exists(NOVEL_FILE) and self.story_text else "w"
        with open(NOVEL_FILE, write_mode, encoding="utf-8") as f:
            if write_mode == 'a':
                f.write("\n" + "---" + "\n\n")
            f.write(header + new_content + "\n")

        with open(NOVEL_FILE, "r", encoding="utf-8") as f: updated_story_text = f.read()
        summary_after = call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=updated_story_text), self.api_key)
        if summary_after and current_scene_log:
            current_scene_log["summary_after"] = summary_after
        elif summary_after and self.arc_state["current_location"] == "real_world":
            self.arc_state["real_world_summary"] = summary_after

        self._save_arc_state()
        files_to_commit = [NOVEL_FILE, self.config['story_arc_file']] + updated_profiles_paths
        self.git.commit_and_push(files_to_commit, f"Chapter {next_chapter_number}: {chapter_subtitle}")

    def run_cycle(self):
        """执行一个完整的创作循环。"""
        if self.git.get_current_branch() != "main":
            if not self.git.switch_to_branch("main"):
                print("错误：无法切换到 'main' 分支，中止执行。")
                return

        os.makedirs(self.config['character_profiles_directory'], exist_ok=True)
        
        self.arc_state = self._load_arc_state()
        self.story_text = self._load_story_text()

        summary_before = "无（这是故事的开篇）" if not self.story_text else call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=self.story_text), self.api_key)
        if not summary_before:
            print("生成事前摘要失败，本轮循环中止。")
            return
        if self.story_text: print(f"\n--- 生成的事前摘要 ---\n{summary_before}\n--------------------")
        
        new_content, pov_character_name, chapter_subtitle = None, None, "现实的谜团"

        if self.arc_state["current_location"] == "movie_world":
            new_content, pov_character_name, chapter_subtitle = self._handle_movie_arc_progression(summary_before)
        elif self.arc_state["current_location"] == "real_world":
            new_content, pov_character_name, chapter_subtitle = self._handle_real_world_progression()

        if not new_content or not pov_character_name:
            print("未能生成有效内容，本轮循环中止。")
            return
            
        print("\n--- 章节打磨完成 ---")
        self._finalize_chapter(new_content, pov_character_name, chapter_subtitle)
        
        print("\n本轮循环完成。")

