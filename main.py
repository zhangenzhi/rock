import time
import random
from config_loader import load_config
from story_manager import StoryManager

if __name__ == "__main__":
    # 加载配置
    config = load_config(cfg="infinite_fears.yaml")
    
    # 设定总运行轮次
    total_runs = 100 
    
    # 开始主创作循环
    for i in range(total_runs):
        print(f"\n{'#'*10} 开始第 {i + 1} / {total_runs} 轮小说创作 {'#'*10}")
        try:
            # 创建一个故事管理器实例并运行一个创作周期
            story_manager = StoryManager(config)
            story_manager.run_one_cycle()
        except Exception as e:
            print(f"在第 {i+1} 轮执行中发生严重错误: {e}")
        
        # 如果不是最后一轮，则休眠
        if i < total_runs - 1:
            print(f"\n--- 第 {i + 1} 轮结束。程序将休眠5分钟... ---")
            time.sleep(300)
    
    print(f"\n{'#'*10} 全部 {total_runs} 轮创作完成 {'#'*10}")
