import time
from config_loader import load_config
from git_manager import GitManager
from story_manager import StoryManager

def main():
    """主执行函数，负责管理整个创作循环。"""
    
    # --- 配置加载与初始化 ---
    config = load_config(cfg="./infinite_fears.yaml")
    git = GitManager(".") 

    # --- 启动检查 ---
    print("--- 正在进行启动检查 ---")
    if git.get_current_branch() != "setup":
        print("\n错误：请先手动切换到 'setup' 分支 (git checkout setup) 再运行此脚本。")
        return
    print("启动检查通过，当前在 'setup' 分支。")
    
    # --- 创建并运行故事管理器 ---
    story_manager = StoryManager(config, git)
    story_manager.run_cycle()


if __name__ == "__main__":
    total_runs = 100 
    for i in range(total_runs):
        print(f"\n{'#'*10} 开始第 {i + 1} / {total_runs} 轮小说创作 {'#'*10}")
        try:
            main()
        except Exception as e:
            print(f"在第 {i+1} 轮执行中发生严重错误: {e}")
        
        if i < total_runs - 1:
            print(f"\n--- 第 {i + 1} 轮结束。程序将休眠5分钟... ---")
            time.sleep(30)
    
    print(f"\n{'#'*10} 全部 {total_runs} 轮创作完成 {'#'*10}")

