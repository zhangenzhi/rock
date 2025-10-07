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
        # 使用更灵活的模式来分割场景块，它会查找以"场景"或"**场景"开头的行
        scene_blocks = re.split(r'\n\s*(?=\*?\*?场景\s*\d+)', movie_plan_text)
        
        for block in scene_blocks:
            if not block.strip() or "场景" not in block:
                continue

            # 为每个信息定义更具弹性的正则表达式
            header_pattern = r"场景\s*(\d+)\s*\(第\s*(\d+)\s*天(?: - (.*?))?\):\s*\[?(.*?)\]?"
            emotion_pattern = r"情绪锚.点:\s*(.*)"

            # 在块内查找匹配项
            header_match = re.search(header_pattern, block)
            emotion_match = re.search(emotion_pattern, block)

            if header_match and emotion_match:
                # 清理捕获到的副标题，移除潜在的Markdown字符
                subtitle = header_match.group(4).strip().replace('*','').replace('`','')
                
                # 清理捕获到的情绪，移除潜在的Markdown字符和结尾的标点
                emotion = emotion_match.group(1).strip().rstrip('.。')

                scenes.append({
                    "scene_number": int(header_match.group(1)),
                    "day": int(header_match.group(2)),
                    "part_of_day": header_match.group(3).strip() if header_match.group(3) else "全天",
                    "subtitle": subtitle,
                    "emotion": emotion,
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

