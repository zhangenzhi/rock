import os
from datetime import datetime

class LoggerManager:
    """负责记录所有Agent对静态资料的读写操作。"""
    def __init__(self, log_dir="output/logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        log_date = datetime.now().strftime("%Y-%m-%d")
        self.log_file = os.path.join(self.log_dir, f"story_generation_{log_date}.log")

    def _log(self, message):
        """内部方法，用于写入格式化的日志条目。"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"!!! 写入日志时发生严重错误: {e} !!!")

    def log_read(self, agent_name, file_path, description=""):
        """记录一个读操作。"""
        message = f"READ  | Agent: {agent_name:<20} | File: {file_path:<50} | Desc: {description}"
        self._log(message)
        print(f"  [Log] {agent_name} 读取了 {os.path.basename(file_path)}")

    def log_write(self, agent_name, file_path, description=""):
        """记录一个写操作。"""
        message = f"WRITE | Agent: {agent_name:<20} | File: {file_path:<50} | Desc: {description}"
        self._log(message)
        print(f"  [Log] {agent_name} 写入了 {os.path.basename(file_path)}")

    def log_api_call(self, agent_name, purpose):
        """(新增) 记录一次对Gemini API的调用。"""
        message = f"API   | Agent: {agent_name:<20} | Purpose: {purpose}"
        self._log(message)

