import os
import json
import random
from datetime import datetime

import prompts
from llm_api import call_gemini
from git_manager import GitManager
from utils import convert_name_to_filename, extract_all_scene_plans

class StoryManager:
    """负责管理整个故事创作流程的类。"""
    def __init__(self, config):
        self.config = config
        self.api_key = config['gemini_api_key']
        self.git = GitManager()
        self.arc_state = None
        self.story_text = ""

    def run_one_cycle(self):
        """执行一个完整的创作周期（生成一章）。"""
        self._prepare_environment()
        self._load_story_state()
        
        new_content, pov_character_name, chapter_subtitle = self._determine_next_chapter()

        if not new_content or not pov_character_name:
            print("未能生成有效内容，本轮循环中止。")
            self.git.switch_to_branch("setup")
            return
            
        print("\n--- 章节打磨完成 ---")

        self._write_and_commit_chapter(new_content, pov_character_name, chapter_subtitle)
        
        self._update_character_profile(pov_character_name, new_content)

        print("切回 'setup' 分支准备下次运行。")
        self.git.switch_to_branch("setup")
        print("\n本轮循环完成。")

    def _prepare_environment(self):
        """检查并设置Git分支和文件目录。"""
        print("--- 正在进行启动检查 ---")
        if self.git.get_current_branch() != "setup":
            print("\n错误：请先手动切换到 'setup' 分支 (git checkout setup) 再运行此脚本。")
            exit()
        print("启动检查通过，当前在 'setup' 分支。")

        if not self.git.branch_exists("main"):
            self._prepare_for_new_story()
            if not self.git.switch_to_branch("main", create_if_not_exists=True):
                exit("错误：无法创建 'main' 分支。")
        else:
            if not self.git.switch_to_branch("main"):
                exit("错误：无法切换到 'main' 分支。")
        
        if not os.path.exists(self.config['character_profiles_directory']):
            os.makedirs(self.config['character_profiles_directory'])

    def _load_story_state(self):
        """加载或初始化故事状态。"""
        self.arc_state = self._load_arc_state_from_file()
        if os.path.exists(self.config['novel_file_name']):
            with open(self.config['novel_file_name'], "r", encoding="utf-8") as f:
                self.story_text = f.read()

    def _determine_next_chapter(self):
        """状态机：决定是写电影章节还是现实章节。"""
        if self.arc_state["current_location"] == "movie_world":
            movie_arc = self.arc_state["current_movie_arc"]
            if movie_arc["current_scene_index"] >= movie_arc["total_scenes"] - 1:
                return self._transition_to_real_world()
            else:
                return self._handle_movie_chapter()
        elif self.arc_state["current_location"] == "real_world":
            return self._transition_to_movie_world()
        return None, None, None
        
    def _transition_to_real_world(self):
        """处理从电影世界回归现实世界的逻辑。"""
        movie_arc = self.arc_state["current_movie_arc"]
        print(f"电影《{movie_arc['movie_name']}》已完结，回归现实世界...")
        self.arc_state["current_location"] = "real_world"
        movie_arc["status"] = "completed"
        
        if movie_arc["movie_name"]:
            print(f"正在为电影《{movie_arc['movie_name']}》生成纪念品工具...")
            tool_json_str = call_gemini(prompts.TOOL_CREATION_PROMPT.format(movie_name=movie_arc['movie_name']), self.api_key)
            try:
                new_tool = json.loads(tool_json_str)
                self.arc_state["protagonist_tools"].append(new_tool)
                print(f"获得新工具: {new_tool.get('tool_name')}")
            except (json.JSONDecodeError, TypeError):
                print(f"错误：无法解析工具JSON: {tool_json_str}")
        
        new_content, pov_character_name = self._handle_real_world_chapter()
        return new_content, pov_character_name, "现实的谜团"

    def _transition_to_movie_world(self):
        """处理从现实世界进入新电影世界的逻辑。"""
        print("现实世界剧情暂告一段落，准备进入新的恐怖电影...")
        self.arc_state["current_location"] = "movie_world"
        self.arc_state["current_movie_arc"] = self._plan_new_arc()
        if not self.arc_state["current_movie_arc"]: return None, None, None
        
        self._save_arc_state_to_file()
        self.git.commit_and_push([self.config['story_arc_file']], f"Architect Plan: {self.arc_state['current_movie_arc']['movie_name']}")

        self.story_text = "" # 新电影，故事文本为空
        new_content, pov_character_name = self._handle_movie_chapter()
        chapter_subtitle = self.arc_state["current_movie_arc"]["scenes"][0]["subtitle"]
        return new_content, pov_character_name, chapter_subtitle

    def _handle_movie_chapter(self):
        """处理电影世界中的一个场景章节"""
        movie_arc = self.arc_state["current_movie_arc"]
        movie_arc["current_scene_index"] += 1
        scene_index = movie_arc["current_scene_index"]
        scene_plan = movie_arc["scenes"][scene_index]
        
        print(f"\n--- 当前电影:《{movie_arc['movie_name']}》 | 场景 {scene_plan['scene_number']} (第 {scene_plan['day']} 天 - {scene_plan['part_of_day']}) ---")
        
        chapter_subtitle = scene_plan["subtitle"]
        emotional_anchor = scene_plan["emotion"]
        print(f"\n--- 本章主题 (副标题): {chapter_subtitle} ---")
        print(f"--- 核心情绪锚点: {emotional_anchor} ---")

        is_first_scene = (scene_index == 0)
        summary = "无（这是电影世界的第一个场景）" if is_first_scene else call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=self.story_text), self.api_key)
        if not summary: return None, None
        if not is_first_scene: print(f"\n--- 生成的摘要 ---\n{summary}\n--------------------")

        scene_plan["summary"] = summary

        if is_first_scene:
            generation_prompt = prompts.FIRST_CHAPTER_PROMPT_TEMPLATE.format(
                movie_plan=movie_arc['movie_plan'], movie_name=movie_arc['movie_name'],
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
            )
            pov_character_name = self.arc_state["protagonist_name"]
            all_profiles_text = "无"
        else: 
            character_names_str = call_gemini(prompts.CHARACTER_IDENTIFICATION_PROMPT.format(summary_text=summary), self.api_key)
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
            
            pov_character_name = call_gemini(prompts.POV_DECISION_PROMPT.format(summary_text=summary), self.api_key)
            if not pov_character_name: return None, None
            print(f"\n--- AI编辑决定下一章视点为: {pov_character_name} ---")

            generation_prompt = prompts.GENERATION_PROMPT_TEMPLATE.format(
                movie_plan=movie_arc['movie_plan'], character_pov=pov_character_name, 
                summary_text=summary, character_profiles_text=all_profiles_text,
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor,
                protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False)
            )

        draft_content = call_gemini(generation_prompt, self.api_key)
        if not draft_content: return None, None

        polished_content, final_feedback = self._polish_chapter(draft_content, summary, all_profiles_text, pov_character_name, chapter_subtitle, emotional_anchor)
        
        scene_plan["review_feedback"] = final_feedback
        
        return polished_content, pov_character_name

    def _handle_real_world_chapter(self):
        """处理现实世界中的一个章节"""
        print("\n--- 开始创作现实世界主线剧情 ---")
        summary = call_gemini(prompts.SUMMARY_PROMPT_TEMPLATE.format(story_text=self.story_text), self.api_key)
        if not summary: return None, None
        self.arc_state["real_world_summary"] = summary
        
        generation_prompt = prompts.REAL_WORLD_GENERATION_PROMPT.format(
            real_world_summary=summary,
            protagonist_tools=json.dumps(self.arc_state['protagonist_tools'], ensure_ascii=False)
        )
        
        new_content = call_gemini(generation_prompt, self.api_key)
        pov_character_name = self.arc_state["protagonist_name"]
        
        return new_content, pov_character_name

    def _polish_chapter(self, draft_content, summary, all_profiles_text, pov_character_name, chapter_subtitle, emotional_anchor):
        """执行三轮审稿和重写循环。"""
        polished_content = draft_content
        final_feedback = ""
        for i in range(self.config['rewrite_cycles']):
            print(f"\n--- 第 {i + 1} / {self.config['rewrite_cycles']} 轮打磨 ---")
            review_prompt = prompts.REVIEW_PROMPT_TEMPLATE.format(
                chapter_text=polished_content, movie_plan=self.arc_state["current_movie_arc"]['movie_plan'],
                chapter_subtitle=chapter_subtitle, emotional_anchor=emotional_anchor
            )
            feedback = call_gemini(review_prompt, self.api_key)
            if not feedback: 
                print("审稿失败，跳过本轮重写。")
                continue
            
            print(f"--- 编辑反馈 ---\n{feedback}\n----------------")
            final_feedback = feedback

            rewrite_prompt = prompts.REWRITE_PROMPT_TEMPLATE.format(
                movie_plan=self.arc_state["current_movie_arc"]['movie_plan'], summary_text=summary,
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
        return polished_content, final_feedback

    def _write_and_commit_chapter(self, new_content, pov_character_name, chapter_subtitle):
        """将最终章节写入文件并提交到Git。"""
        NOVEL_FILE = self.config['novel_file_name']
        next_chapter_number = len(re.findall(r"第 (\d+) 章", self.story_text)) + 1
        
        scene_info = ""
        if self.arc_state["current_location"] == "movie_world":
            scene = self.arc_state["current_movie_arc"]["scenes"][self.arc_state["current_movie_arc"]["current_scene_index"]]
            scene_info = f"{self.arc_state['current_movie_arc']['movie_name']} - 第 {scene['day']} 天 ({scene['part_of_day']})"
        else:
            scene_info = "现实世界"

        header = f"第 {next_chapter_number} 章: {chapter_subtitle} (视点: {pov_character_name}) | {scene_info}\n写作于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        write_mode = "a" if os.path.exists(NOVEL_FILE) and self.story_text else "w"
        if write_mode == "a":
            with open(NOVEL_FILE, "a", encoding="utf-8") as f: f.write("\n" + "="*20 + "\n\n")
        
        with open(NOVEL_FILE, write_mode, encoding="utf-8") as f:
            f.write(header + new_content + "\n\n")
        
        self._save_arc_state_to_file()
        files_to_commit = [NOVEL_FILE, self.config['story_arc_file']]
        self.git.commit_and_push(files_to_commit, f"Chapter {next_chapter_number}: {chapter_subtitle}")

    def _update_character_profile(self, pov_character_name, new_content):
        """更新角色的侧写文件。"""
        if self.arc_state["current_location"] != "movie_world":
            return

        PROFILES_DIR = self.config['character_profiles_directory']
        profile_filename = f"{convert_name_to_filename(pov_character_name)}_profile.md"
        profile_path = os.path.join(PROFILES_DIR, profile_filename)
        
        existing_profile = ""
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f: 
                existing_profile = f.read()
        else:
            existing_profile = f"# {pov_character_name} 的角色侧写\n\n- 在《{self.arc_state['current_movie_arc']['movie_name']}》篇章中首次出场。"

        is_protagonist = (pov_character_name == self.arc_state["protagonist_name"])
        profile_prompt = prompts.PROFILE_UPDATE_PROMPT.format(
            character_name=pov_character_name, 
            existing_profile=existing_profile, 
            new_content=new_content
        )
        if not is_protagonist:
             profile_prompt = profile_prompt.replace("背景慢速揭示 (仅限主角):", "")

        updated_profile = call_gemini(profile_prompt, self.api_key)
        if updated_profile:
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(updated_profile)
            self.git.commit_and_push([profile_path], f"Update profile for {pov_character_name}")

    def _load_arc_state_from_file(self):
        ARC_STATE_FILE = self.config['story_arc_file']
        if os.path.exists(ARC_STATE_FILE):
            with open(ARC_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "protagonist_name": "江浩",
            "protagonist_tools": [],
            "current_location": "real_world",
            "real_world_summary": "江浩，一个中国的待业青年，最近失业在家，对未来感到迷茫。故事从他百无聊赖的生活开始。",
            "current_movie_arc": None
        }

    def _save_arc_state_to_file(self):
        ARC_STATE_FILE = self.config['story_arc_file']
        with open(ARC_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.arc_state, f, ensure_ascii=False, indent=4)

    def _prepare_for_new_story(self):
        print("\n--- 正在清理环境，准备开始全新故事 ---")
        protected_branches = ["main", "setup"]
        all_branches = self.git.list_all_branches()
        for branch in all_branches:
            if branch not in protected_branches:
                self.git.delete_branch(branch)
        
        if os.path.exists(self.config['novel_file_name']): os.remove(self.config['novel_file_name'])
        if os.path.exists(self.config['story_arc_file']): os.remove(self.config['story_arc_file'])
        if os.path.exists(self.config['character_profiles_directory']):
            import shutil
            shutil.rmtree(self.config['character_profiles_directory'])
        print("环境清理完成。")

    def _plan_new_arc(self):
        print("\n--- 正在规划新的电影世界 ---")
        new_movie = call_gemini(prompts.MOVIE_SELECTION_PROMPT, self.api_key)
        if not new_movie: return None

        movie_plan_text = call_gemini(prompts.MOVIE_ANALYSIS_PROMPT.format(movie_name=new_movie, duration="10-15"), self.api_key)
        if not movie_plan_text: return None
        
        scenes = extract_all_scene_plans(movie_plan_text)
        if not scenes:
            print("错误：无法从规划文档中解析出任何场景。")
            return None

        arc = {
            "movie_name": new_movie,
            "status": "active",
            "current_scene_index": -1,
            "total_scenes": len(scenes),
            "movie_plan": movie_plan_text, 
            "scenes": scenes
        }
        
        print(f"电影《{new_movie}》规划完成，共 {len(scenes)} 个场景。")
        return arc
