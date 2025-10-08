import os
import json
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
        self.arc_state = None
        self.story_text = ""

    def _load_arc_state(self):
        """
        读取或初始化故事世界状态。
        新增对 current_real_world_arc 的支持。
        """
        ARC_STATE_FILE = self.config['story_arc_file']
        if os.path.exists(ARC_STATE_FILE):
            with open(ARC_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                # 向后兼容，确保旧的状态文件有必要的新字段
                if "completed_movie_arcs" not in state:
                    state["completed_movie_arcs"] = []
                if "current_real_world_arc" not in state:
                    state["current_real_world_arc"] = None
                return state
        # 初始化一个全新的故事状态
        return {
            "protagonist_name": "江浩",
            "protagonist_tools": [],
            "current_location": "real_world",
            "real_world_summary": "江浩，一个中国的待业青年，最近失业在家，对未来感到迷茫。故事从他百无聊赖的生活开始。",
            "current_movie_arc": None,
            "completed_movie_arcs": [],
            "current_real_world_arc": None # 新增：用于追踪现实世界章节计划
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
            shutil.rmtree(output_dir)
        print("环境清理完成。")
        
    def _call_gemini_and_parse_json(self, prompt, max_retries=3):
        """调用 Gemini API 期望获得JSON响应，并包含校验和重试逻辑。"""
        for attempt in range(max_retries):
            print(f"正在尝试第 {attempt + 1}/{max_retries} 次生成和解析JSON...")
            json_str = call_gemini(prompt, self.api_key)
            if not json_str:
                print("API调用未能返回内容，将重试...")
                time.sleep(2)
                continue
            try:
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if not match:
                    raise json.JSONDecodeError("响应中未找到有效的JSON结构。", json_str, 0)
                cleaned_json_str = match.group(0)
                json_obj = json.loads(cleaned_json_str)
                print("JSON生成和解析成功。")
                return json_obj, cleaned_json_str
            except json.JSONDecodeError as e:
                print(f"警告：JSON解析失败: {e}")
                if attempt < max_retries - 1:
                    print("AI可能返回了不完整的JSON，将重试。")
                else:
                    print("已达到最大重试次数，无法获取有效的JSON。")
                    print("\n--- DEBUG: 最终解析失败的JSON字符串 ---\n" + json_str + "\n---------------------------------\n")
        return None, None

    # --- 规划模块 ---
    def _plan_new_movie_arc(self):
        """规划一个全新的电影世界大章节。"""
        print("\n--- 正在规划新的电影世界 ---")
        movie_name = call_gemini(prompts.MOVIE_SELECTION_PROMPT, self.api_key)
        if not movie_name: return None, []
        
        draft_plan_data, draft_plan_json_str = self._call_gemini_and_parse_json(
            prompts.MOVIE_ANALYSIS_PROMPT.format(movie_name=movie_name)
        )
        if not draft_plan_data: return None, []
        
        print("\n--- 开始电影剧情大纲审稿与重写流程 ---")
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
            rewritten_plan_data, rewritten_plan_json_str = self._call_gemini_and_parse_json(rewrite_prompt)
            if not rewritten_plan_data:
                print("大纲重写失败，保留上一版本。")
                break
            polished_plan_json_str = rewritten_plan_json_str
        
        final_plan_data, _ = self._call_gemini_and_parse_json(f"请格式化并返回这个JSON:\n{polished_plan_json_str}")
        if not final_plan_data: return None, []

        scenes = final_plan_data.get("scenes", [])
        arc = {
            "movie_name": movie_name, "status": "active", "current_scene_index": -1,
            "total_scenes": len(scenes), "movie_plan": final_plan_data.get("overall_setting", {}),
            "scenes": scenes
        }
        
        new_profile_paths = self._create_character_profiles(final_plan_data.get("character_pool", []))
        print(f"电影《{movie_name}》规划完成，共 {len(arc['scenes'])} 个场景。")
        return arc, new_profile_paths

    def _plan_real_world_arc(self, summary_before):
        """(已升级) 为现实世界规划章节，并加入审稿重写循环。"""
        print("\n--- 架构师正在规划接下来的现实世界主线剧情 ---")
        last_movie = self.arc_state["completed_movie_arcs"][-1] if self.arc_state["completed_movie_arcs"] else {"movie_name": "无"}
        
        # 1. 生成初稿
        draft_prompt = prompts.REAL_WORLD_ARC_ANALYSIS_PROMPT.format(
            real_world_summary=summary_before,
            protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
            last_movie_name=last_movie['movie_name']
        )
        draft_plan_data, draft_plan_json_str = self._call_gemini_and_parse_json(draft_prompt)
        if not draft_plan_data:
            print("错误：现实世界章节规划初稿生成失败。")
            return None, []

        # 2. 开始审稿与重写循环
        print("\n--- 开始现实世界主线大纲审稿与重写流程 ---")
        polished_plan_json_str = draft_plan_json_str
        for i in range(self.config['rewrite_cycles']):
            print(f"\n--- 第 {i + 1} / {self.config['rewrite_cycles']} 轮现实大纲打磨 ---")
            review_prompt = prompts.REAL_WORLD_ARC_REVIEW_PROMPT.format(real_world_plan_draft=polished_plan_json_str)
            feedback = call_gemini(review_prompt, self.api_key)
            if not feedback:
                print("现实大纲审稿失败，跳过本轮重写。")
                continue
            
            print(f"--- 总编反馈 ---\n{feedback}\n----------------")
            
            rewrite_prompt = prompts.REAL_WORLD_ARC_REWRITE_PROMPT.format(original_plan=polished_plan_json_str, feedback=feedback)
            rewritten_plan_data, rewritten_plan_json_str = self._call_gemini_and_parse_json(rewrite_prompt)
            if not rewritten_plan_data:
                print("现实大纲重写失败，保留上一版本。")
                break
            polished_plan_json_str = rewritten_plan_json_str

        # 3. 解析最终版本
        final_plan_data, _ = self._call_gemini_and_parse_json(f"请格式化并返回这个JSON:\n{polished_plan_json_str}")
        if not final_plan_data:
            print("错误：无法解析最终的现实世界章节规划。")
            return None, []
        
        scenes = final_plan_data.get("scenes", [])
        arc = {
            "arc_title": final_plan_data.get("arc_title", "未命名现实章节"),
            "status": "active", "current_scene_index": -1, "total_scenes": len(scenes),
            "scenes": scenes
        }
        self.arc_state["current_real_world_arc"] = arc
        new_profile_paths = self._create_character_profiles(final_plan_data.get("character_pool", []))
        
        print(f"现实世界章节《{arc['arc_title']}》规划完成，共 {len(scenes)} 个场景。")
        return arc, new_profile_paths

    # --- 章节生成模块 ---
    def _generate_movie_chapter(self, movie_arc, summary_before):
        """生成电影世界中的一个场景章节。"""
        scene_index = movie_arc["current_scene_index"]
        scene_plan = movie_arc["scenes"][scene_index]
        chapter_subtitle, emotional_anchor = scene_plan["subtitle"], scene_plan.get("emotion", "未知")
        print(f"\n--- 本章主题: {chapter_subtitle} | 核心情绪: {emotional_anchor} ---")

        movie_plan_str = json.dumps(movie_arc.get('movie_plan', {}), ensure_ascii=False, indent=2)
        meta_foreshadowing = movie_arc.get('movie_plan', {}).get('meta_narrative_foreshadowing', {})
        meta_instruction = "本章无需展现元叙事感。"
        if scene_plan.get('scene_number') == meta_foreshadowing.get('trigger_scene', -1):
            meta_instruction = f"**演绎元叙事感:** {meta_foreshadowing.get('content', '')}"

        pov_character_name = scene_plan.get("pov_character", self.arc_state["protagonist_name"])
        print(f"--- 架构师预设本章视点为: {pov_character_name} ---")

        all_profiles_text = self._get_character_profiles_text(summary_before)

        if scene_index == 0:
            gen_prompt = prompts.FIRST_CHAPTER_PROMPT_TEMPLATE.format(
                movie_plan=movie_plan_str, movie_name=movie_arc['movie_name'], chapter_subtitle=chapter_subtitle,
                emotional_anchor=emotional_anchor, meta_narrative_instruction=meta_instruction
            )
        else:
            gen_prompt = prompts.GENERATION_PROMPT_TEMPLATE.format(
                movie_plan=movie_plan_str, character_pov=pov_character_name, summary_text=summary_before,
                character_profiles_text=all_profiles_text, chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor,
                protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
                meta_narrative_instruction=meta_instruction
            )

        draft_content = call_gemini(gen_prompt, self.api_key)
        if not draft_content: return None, None, None

        # --- 章节打磨循环 ---
        polished_content = draft_content
        for i in range(self.config['rewrite_cycles']):
            print(f"\n--- 第 {i + 1} / {self.config['rewrite_cycles']} 轮章节打磨 ---")
            review_prompt = prompts.REVIEW_PROMPT_TEMPLATE.format(chapter_text=polished_content, movie_plan=movie_plan_str, chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor)
            feedback = call_gemini(review_prompt, self.api_key)
            if not feedback:
                print("审稿失败，跳过本轮重写。")
                continue
            print(f"--- 编辑反馈 ---\n{feedback}\n----------------")
            rewrite_prompt = prompts.REWRITE_PROMPT_TEMPLATE.format(
                movie_plan=movie_plan_str, summary_text=summary_before, character_profiles_text=all_profiles_text,
                protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
                character_pov=pov_character_name, original_text=polished_content, feedback=feedback,
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
            )
            rewritten_content = call_gemini(rewrite_prompt, self.api_key)
            if rewritten_content: polished_content = rewritten_content
        
        return polished_content, pov_character_name, chapter_subtitle

    def _generate_real_world_chapter(self, rw_arc, summary_before):
        """生成现实世界中的一个场景章节。"""
        scene_index = rw_arc["current_scene_index"]
        scene_plan = rw_arc["scenes"][scene_index]
        chapter_subtitle = scene_plan["subtitle"]
        emotional_anchor = scene_plan.get("emotion_anchor", "未知")
        pov_character_name = scene_plan.get("pov_character", self.arc_state["protagonist_name"])

        print(f"\n--- 现实世界章节: {chapter_subtitle} | 视点: {pov_character_name} ---")

        gen_prompt = prompts.REAL_WORLD_GENERATION_PROMPT.format(
            summary_text=summary_before,
            protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
            chapter_subtitle=chapter_subtitle,
            synopsis=scene_plan['synopsis'],
            emotion_anchor=emotional_anchor,
            character_pov=pov_character_name
        )
        new_content = call_gemini(gen_prompt, self.api_key)
        return new_content, pov_character_name, chapter_subtitle
    
    # --- 流程控制模块 ---
    def _handle_movie_arc_progression(self, summary_before):
        """处理电影世界中的情节推进。"""
        movie_arc = self.arc_state["current_movie_arc"]
        
        if movie_arc["current_scene_index"] >= movie_arc["total_scenes"] - 1:
            print(f"电影《{movie_arc['movie_name']}》已完结，回归现实世界...")
            self.arc_state["current_location"] = "real_world"
            movie_arc["status"] = "completed"
            self.arc_state["completed_movie_arcs"].append(movie_arc)
            self.arc_state["current_movie_arc"] = None
            
            if movie_arc["movie_name"]:
                new_tool, _ = self._call_gemini_and_parse_json(prompts.TOOL_CREATION_PROMPT.format(movie_name=movie_arc['movie_name']))
                if new_tool and isinstance(new_tool, dict):
                    self.arc_state["protagonist_tools"].append(new_tool)
                    print(f"主角获得新工具: {new_tool.get('tool_name')}")
            
            return None, None, None # 返回空，表示一个流程结束，主循环将调用导演
        else:
            movie_arc["current_scene_index"] += 1
            scene_plan = movie_arc["scenes"][movie_arc["current_scene_index"]]
            print(f"\n--- 当前电影:《{movie_arc['movie_name']}》 | 场景 {scene_plan.get('scene_number', movie_arc['current_scene_index'] + 1)} ---")
            return self._generate_movie_chapter(movie_arc, summary_before)

    def _handle_real_world_arc_progression(self, summary_before):
        """处理现实世界规划章节的情节推进。"""
        rw_arc = self.arc_state["current_real_world_arc"]
        rw_arc["current_scene_index"] += 1
        return self._generate_real_world_chapter(rw_arc, summary_before)

    def _decide_and_execute_next_step(self, summary_before):
        """'故事导演'进行决策，并执行下一步动作。"""
        print("\n--- '故事导演' 正在决策下一步剧情走向 ---")
        
        completed_movies_list = [arc['movie_name'] for arc in self.arc_state['completed_movie_arcs']]
        prompt = prompts.NEXT_STEP_DECISION_PROMPT.format(
            real_world_summary=summary_before,
            protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False),
            completed_movies=json.dumps(completed_movies_list, ensure_ascii=False)
        )
        decision_data, _ = self._call_gemini_and_parse_json(prompt)

        if not decision_data or "decision" not in decision_data:
            print("导演决策失败，默认继续现实世界剧情。")
            decision_data = {"decision": "REAL_WORLD", "reasoning": "决策失败，默认选项。"}

        print(f"--- 导演决策: {decision_data['decision']} | 理由: {decision_data['reasoning']} ---")

        if decision_data["decision"] == "REAL_WORLD":
            arc, new_profile_paths = self._plan_real_world_arc(summary_before)
            if not arc: return None, None, None
            self._save_arc_state()
            self.git.commit_and_push([self.config['story_arc_file']] + new_profile_paths, f"Architect Plan (Real World): {arc['arc_title']}")
            return self._handle_real_world_arc_progression(summary_before)
        else: # decision == "MOVIE_WORLD"
            return self._start_new_movie_arc(summary_before)

    def _start_new_movie_arc(self, summary_before):
        """开始一个新的电影世界。"""
        print("现实世界剧情暂告一段落，准备进入新的恐怖电影...")
        arc, new_profile_paths = self._plan_new_movie_arc()
        if not arc: return None, None, None
        
        self.arc_state["current_movie_arc"] = arc
        self.arc_state["current_location"] = "movie_world"
        
        self._save_arc_state()
        self.git.commit_and_push([self.config['story_arc_file']] + new_profile_paths, f"Architect Plan (Movie): {arc['movie_name']}")
        
        arc["current_scene_index"] += 1
        return self._generate_movie_chapter(arc, "无（这是电影世界的第一个场景）")
    
    # --- 辅助与收尾模块 ---
    def _create_character_profiles(self, character_pool):
        """根据规划创建角色档案文件。"""
        new_profile_paths = []
        PROFILES_DIR = self.config['character_profiles_directory']
        os.makedirs(PROFILES_DIR, exist_ok=True)
        for char_data in character_pool:
            char_name = char_data.get("name")
            initial_profile = char_data.get("initial_profile")
            if char_name and initial_profile:
                profile_filename = f"{convert_name_to_filename(char_name)}_profile.md"
                profile_path = os.path.join(PROFILES_DIR, profile_filename)
                with open(profile_path, "w", encoding="utf-8") as f:
                    f.write(initial_profile)
                new_profile_paths.append(profile_path)
        return new_profile_paths

    def _get_character_profiles_text(self, summary_text):
        """根据摘要识别角色并加载其档案文本。"""
        character_names_str = call_gemini(prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_text), self.api_key)
        if not character_names_str or character_names_str.lower() == "无":
            return "本章没有特定角色的侧写信息。"
        
        character_names = [name.strip() for name in character_names_str.split(',') if name.strip()]
        print(f"识别到出场人物: {character_names}")
        profile_contents = []
        for name in character_names:
            profile_path = os.path.join(self.config['character_profiles_directory'], f"{convert_name_to_filename(name)}_profile.md")
            if os.path.exists(profile_path):
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile_contents.append(f"--- 角色: {name} ---\n{f.read()}\n")
        return "\n".join(profile_contents) if profile_contents else "未找到任何相关角色的侧写文件。"

    def _finalize_chapter(self, new_content, pov_character_name, chapter_subtitle):
        """将最终章节内容写入文件、更新角色档案并提交到Git。"""
        print("\n--- 正在定稿本章内容 ---")
        NOVEL_FILE = self.config['novel_file_name']
        PROFILES_DIR = self.config['character_profiles_directory']
        
        summary_of_new_content = call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=new_content), self.api_key)
        updated_profiles_paths = []
        if summary_of_new_content:
            character_names_str = call_gemini(prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary_of_new_content), self.api_key)
            if character_names_str and character_names_str.lower() != '无':
                for char_name in [name.strip() for name in character_names_str.split(',') if name.strip()]:
                    profile_path = os.path.join(PROFILES_DIR, f"{convert_name_to_filename(char_name)}_profile.md")
                    existing_profile = ""
                    if os.path.exists(profile_path):
                        with open(profile_path, "r", encoding="utf-8") as f: existing_profile = f.read()
                    
                    profile_prompt = prompts.PROFILE_UPDATE_PROMPT.format(character_name=char_name, existing_profile=existing_profile, new_content=new_content)
                    updated_profile = call_gemini(profile_prompt, self.api_key)
                    if updated_profile:
                        with open(profile_path, "w", encoding="utf-8") as f: f.write(updated_profile)
                        updated_profiles_paths.append(profile_path)

        next_chapter_number = len(re.findall(r"# 第 (\d+) 章", self.story_text)) + 1
        location_info = "现实世界"
        if self.arc_state["current_location"] == "movie_world":
            movie_arc = self.arc_state["current_movie_arc"]
            scene = movie_arc["scenes"][movie_arc["current_scene_index"]]
            location_info = f"{movie_arc['movie_name']} - 场景 {scene.get('scene_number', movie_arc['current_scene_index'] + 1)}"
        
        header = f"# 第 {next_chapter_number} 章: {chapter_subtitle} (视点: {pov_character_name})\n\n**地点:** {location_info}  \n**写作于:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        write_mode = "a" if self.story_text else "w"
        with open(NOVEL_FILE, write_mode, encoding="utf-8") as f:
            if write_mode == 'a': f.write("\n\n---\n\n")
            f.write(header + new_content + "\n")

        with open(NOVEL_FILE, "r", encoding="utf-8") as f: updated_story_text = f.read()
        summary_after = call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=updated_story_text), self.api_key)
        if summary_after:
             self.arc_state["real_world_summary"] = summary_after

        self._save_arc_state()
        
        files_to_commit = [NOVEL_FILE, self.config['story_arc_file']] + updated_profiles_paths
        self.git.commit_and_push(files_to_commit, f"Chapter {next_chapter_number}: {chapter_subtitle}")

    def run_cycle(self):
        """执行一个完整的创作循环，包含动态决策。"""
        if self.git.get_current_branch() != "main":
            if not self.git.switch_to_branch("main"):
                print("错误：无法切换到 'main' 分支，中止执行。")
                return

        os.makedirs(self.config['character_profiles_directory'], exist_ok=True)
        self.arc_state = self._load_arc_state()
        self.story_text = self._load_story_text()

        summary_before = self.arc_state.get("real_world_summary", "无（这是故事的开篇）")
        print(f"\n--- 加载当前故事摘要 ---\n{summary_before}\n--------------------")
        
        new_content, pov_character_name, chapter_subtitle = None, None, None

        if self.arc_state["current_location"] == "movie_world":
            new_content, pov_character_name, chapter_subtitle = self._handle_movie_arc_progression(summary_before)
            if not new_content: # 电影世界结束，进入决策流程
                 new_content, pov_character_name, chapter_subtitle = self._decide_and_execute_next_step(summary_before)
        
        elif self.arc_state["current_location"] == "real_world":
            rw_arc = self.arc_state.get("current_real_world_arc")
            if rw_arc and rw_arc["current_scene_index"] < rw_arc["total_scenes"] - 1:
                # 继续执行已有的现实世界计划
                new_content, pov_character_name, chapter_subtitle = self._handle_real_world_arc_progression(summary_before)
            else:
                # 现实计划不存在或已结束，调用导演决策
                if rw_arc: self.arc_state["current_real_world_arc"] = None # 清理已完成的计划
                new_content, pov_character_name, chapter_subtitle = self._decide_and_execute_next_step(summary_before)

        if not new_content:
            print("本轮循环为状态转换或规划，未生成最终章节。请检查日志。")
            return
            
        print("\n--- 章节生成完毕 ---")
        self._finalize_chapter(new_content, pov_character_name, chapter_subtitle)
        print("\n本轮循环完成。")

