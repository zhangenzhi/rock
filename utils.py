import re
from pypinyin import pinyin, Style

def convert_name_to_filename(name):
    """将中文名转换为适合Git分支的拼音名"""
    if not name or name == "旁白": return None
    # 将中文名转换为全小写的拼音，用-连接，更适合做文件名
    return "-".join([item[0] for item in pinyin(name, style=Style.NORMAL)]).lower()

def extract_all_scene_plans(movie_plan_text):
    """从电影规划文档中提取所有场景的计划 (更稳健的版本)。"""
    scenes = []
    try:
        # 查找所有场景标题的位置
        header_pattern = r"\*\*?场景\s*(\d+)\s*\(第\s*(\d+)\s*天(?: - (.*?))?\):\s*\[?(.*?)\]?"
        matches = list(re.finditer(header_pattern, movie_plan_text))

        for i, match in enumerate(matches):
            # 获取当前场景块的文本
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(movie_plan_text)
            block = movie_plan_text[start_pos:end_pos]

            # 在块内查找情绪锚点 (使用更具弹性的正则表达式)
            emotion_match = re.search(r"\*?\*?情绪锚点\*\*?:\s*(.*)", block)
            if emotion_match:
                scenes.append({
                    "scene_number": int(match.group(1)),
                    "day": int(match.group(2)),
                    "part_of_day": match.group(3).strip() if match.group(3) else "全天",
                    "subtitle": match.group(4).strip().replace('*','').replace('`',''),
                    "emotion": emotion_match.group(1).strip().rstrip('.。'),
                    "summary": None,
                    "review_feedback": None
                })

    except Exception as e:
        print(f"解析场景计划时出错: {e}")
    
    # 如果解析失败，打印原始文本以供调试
    if not scenes:
        print("\n--- DEBUG: 解析失败的规划文档 ---")
        print(movie_plan_text)
        print("---------------------------------\n")

    return scenes

