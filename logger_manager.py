import os
from datetime import datetime

class LoggerManager:
    """负责记录所有Agent对静态资料的读写操作。"""
    def __init__(self, log_dir="output/logs"):
        self.log_dir = log_dir
        # 核心修复：确保日志目录在初始化时就存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 使用当前日期作为日志文件名
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
            # 如果日志本身写入失败，打印到控制台
            print(f"CRITICAL: 日志写入失败: {e}")
            print(f"CRITICAL: 原始日志信息: {log_entry}")

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
        """记录一次API调用。"""
        message = f"API   | Agent: {agent_name:<20} | Purpose: {purpose}"
        self._log(message)
        # 终端同步打印
        print(f"\n--- [API Call] Agent: {agent_name} | Purpose: {purpose} ---")
        
    def log_error(self, message):
        """记录一个错误信息。"""
        error_message = f"ERROR | {message}"
        self._log(error_message)
        # 终端同步打印
        print(f"  [Error] {message}")