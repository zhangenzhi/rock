import re
from pypinyin import pinyin, Style

def convert_name_to_filename(name):
    """将中文名转换为适合做文件名的拼音。"""
    if not name or name == "旁白": return "narrator"
    return "-".join([item[0] for item in pinyin(name, style=Style.NORMAL)]).lower()

import pyautogui
import pyperclip
import time
import random
import pypinyin
import jieba
import re
import platform

def read_file_content(filepath):
    """读取指定文件的内容。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误：文件 '{filepath}' 未找到。")
        return None
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return None

def simulate_typing_macos(text):
    """
    第一步：尽可能真实地模拟键盘输入（macOS优化版）。
    """
    print("--- 第一步：开始真实键盘模拟输入 ---")
    words = jieba.cut(text)
    for word in words:
        word = word.strip()
        if not word:
            if '\n' in text[text.find(word):text.find(word)+len(word)+1]: # 简陋地处理换行
                 pyautogui.press('enter')
            continue

        if re.search('[\u4e00-\u9fff]+', word):
            pinyin_str = "".join(pypinyin.lazy_pinyin(word))
            pyautogui.typewrite(pinyin_str, interval=random.uniform(0.01, 0.05))
            time.sleep(0.1)
            pyautogui.press('space')
        else:
            # 对于非中文，逐字输入以增加真实感
            for char in word:
                pyautogui.typewrite(char)
                time.sleep(random.uniform(0.02, 0.08))
            # 按空格确认非字母数字的输入
            if not word.isalnum():
                pyautogui.press('space')

        time.sleep(random.uniform(0.1, 0.3))
    print("--- 第一步：键盘模拟输入完成 ---")


def proofread_and_correct(original_text):
    """
    第二步：校对并修正。
    """
    print("\n--- 第二步：开始校对与修正 ---")
    
    # 确定快捷键
    select_all_key = 'command'
    
    # 1. 全选并复制应用内的文本
    print("正在获取已输入的文本...")
    pyautogui.hotkey(select_all_key, 'a')
    time.sleep(0.5) # 等待UI响应
    pyautogui.hotkey(select_all_key, 'c')
    time.sleep(0.5) # 等待剪贴板更新
    
    typed_text = pyperclip.paste()
    
    # 2. 比较
    # 我们需要对文本进行一些清理，因为输入过程可能会产生额外的空格或换行差异
    cleaned_original = "".join(original_text.split())
    cleaned_typed = "".join(typed_text.split())

    if cleaned_original == cleaned_typed:
        print("校验通过！输入内容与原文一致。")
        # 取消全选状态
        pyautogui.press('right')
    else:
        print("校验发现不一致！正在通过剪贴板进行修正...")
        # 3. 如果不一致，使用剪贴板粘贴正确原文
        # 此时文本已被全选，直接粘贴即可覆盖
        pyperclip.copy(original_text)
        pyautogui.hotkey(select_all_key, 'v')
        print("修正完成！")

# --- 主程序 ---
if __name__ == "__main__":
    markdown_filepath = './output/daily_updates.md'
    
    original_content = read_file_content(markdown_filepath)

    if original_content:
        # 重要的准备步骤提示
        print("############################################################")
        print("### 警告：程序即将开始，请在倒计时结束前完成以下操作： ###")
        print("### 1. 将光标点击到您想输入的空白文本框中。        ###")
        print("### 2. 将系统输入法切换为“拼音 - 简体”。      ###")
        print("### 3. 确保输入法处于中文模式（图标为“拼”）。      ###")
        print("############################################################")
        
        for i in range(8, 0, -1):
            print(f"程序将在 {i} 秒后开始...", end="\r", flush=True)
            time.sleep(1)
        print("\n")

        # 执行第一步
        simulate_typing_macos(original_content)
        
        # 等待片刻，确保所有输入都已完成
        time.sleep(2) 
        
        # 执行第二步
        proofread_and_correct(original_content)

        print("\n所有操作已完成。")
    else:
        print("因无法读取文件内容，程序已退出。")