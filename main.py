import time
import sys
import os
import shutil
from config_loader import load_config
from git_manager import GitManager
from story_manager import StoryManager

def full_reset(git, config):
    """
    执行一个完整的重置，删除本地和远程的main分支，并清空output目录。
    警告：此操作会删除 'main' 分支上的所有故事进度。
    """
    print("\n" + "#"*10 + " 正在执行完整重置 " + "#"*10)
    current_branch = git.get_current_branch()
    if current_branch != 'setup':
        print("错误：完整重置必须在 'setup' 分支上执行。")
        print("请先手动运行 `git checkout setup` 再重试。")
        return False
    
    # 1. 删除Git分支
    print("正在尝试删除 'main' 分支（本地和远程）...")
    git.delete_branch('main') 
    
    # 2. 清理输出目录
    print("正在清理输出目录...")
    output_dir = os.path.dirname(config.get("novel_file_name", "output/"))
    if output_dir and os.path.exists(output_dir):
        try:
            shutil.rmtree(output_dir)
            print(f"已删除目录: {output_dir}")
        except Exception as e:
            print(f"删除目录 {output_dir} 时出错: {e}")
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"已确保 '{output_dir}' 目录存在。")

    print("\n重置命令已执行。")
    print("如果远程删除失败，可能是因为 'main' 是您GitHub仓库中受保护的默认分支。")
    print("在这种情况下，请访问仓库的网页设置，将默认分支临时更改为 'setup'，然后再次运行此重置命令。")
    return True

def main():
    """主执行函数，负责管理整个创作循环。"""
    
    config = load_config(cfg="infinite_fears.yaml")
    # 核心修改：将配置信息传递给 GitManager
    git = GitManager(".", config) 

    print("--- 正在进行启动检查 ---")
    if git.get_current_branch() != "setup":
        print("\n错误：请先手动切换到 'setup' 分支 (git checkout setup) 再运行此脚本。")
        return
    print("启动检查通过，当前在 'setup' 分支。")
    
    story_manager = StoryManager(config, git)

    # --- 环境与分支设置 (集中处理) ---
    if not git.branch_exists("main"):
        story_manager.prepare_for_new_story()
        print("\n'main' 分支不存在，正在创建...")
        if not git.switch_to_branch("main", create_if_not_exists=True):
            print("错误：无法创建 'main' 分支。脚本中止。")
            return
    else:
        print("\n检测到 'main' 分支，正在切换...")
        if not git.switch_to_branch("main"):
            print("错误：无法切换到 'main' 分支。脚本中止。")
            # 切换失败后，安全地回到 setup 分支
            git.switch_to_branch("setup")
            return
    
    print(f"已成功切换到 'main' 分支，准备开始创作循环。")

    # --- 主创作循环 ---
    total_runs = 100 
    for i in range(total_runs):
        print(f"\n{'#'*10} 开始第 {i + 1} / {total_runs} 轮小说创作 {'#'*10}")
        try:
            story_manager.run_cycle()
        except Exception as e:
            print(f"在第 {i+1} 轮执行中发生严重错误: {e}")
        
        if i < total_runs - 1:
            print(f"\n--- 第 {i + 1} 轮结束。程序将休眠30秒... ---")
            time.sleep(30)
    
    print(f"\n{'#'*10} 全部 {total_runs} 轮创作完成 {'#'*10}")
    print("所有创作已完成，切回 'setup' 分支。")
    git.switch_to_branch("setup")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        try:
            config_for_reset = load_config(cfg="infinite_fears.yaml")
            # 核心修改：将配置信息传递给 GitManager
            git_for_reset = GitManager(".", config_for_reset)
            if full_reset(git_for_reset, config_for_reset):
                print("完整重置流程结束。现在可以不带 '--reset' 参数来运行脚本，以开始一个全新的故事。")
        except Exception as e:
            print(f"重置过程中发生错误: {e}")
        exit()

    main()
