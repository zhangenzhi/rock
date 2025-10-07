import re
from pypinyin import pinyin, Style

def convert_name_to_filename(name):
    """将中文名转换为适合做文件名的拼音。"""
    if not name or name == "旁白": return None
    # 将中文名转换为全小写的拼音，用-连接
    return "-".join([item[0] for item in pinyin(name, style=Style.NORMAL)]).lower()

