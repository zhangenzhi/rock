import os
import yaml

def load_config(cfg="book_names.yaml"):
    """加载YAML配置文件。如果文件不存在，则创建一个模板并退出。"""
    CONFIG_DIR = "configs"
    CONFIG_FILE = os.path.join(CONFIG_DIR, cfg)
    
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

    if not os.path.exists(CONFIG_FILE):
        print(f"配置文件 '{CONFIG_FILE}' 未找到。正在创建一个模板文件。")
        print("请在新创建的文件中填入您的 Gemini API 密钥后重新运行。")
        default_config = {
            "gemini_api_key": "在此处粘贴您的GEMINI_API_KEY",
            "novel_file_name": "无限恐怖.txt",
            "character_profiles_directory": "characters",
            "story_arc_file": "story_arc.json",
            "rewrite_cycles": 3
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True, sort_keys=False)
        # 退出以便用户填写配置
        exit()

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        if not config.get("gemini_api_key") or "在此处粘贴您" in config.get("gemini_api_key"):
             print(f"错误：请在 '{CONFIG_FILE}' 文件中提供有效的 Gemini API 密钥。")
             exit()
        return config
