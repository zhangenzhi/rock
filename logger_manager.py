import os
from datetime import datetime

class LoggerManager:
    """负责记录所有Agent对静态资料的读写操作。"""
    def __init__(self, log_dir="output/logs"):
        """
        初始化日志管理器，创建日志目录和当天的日志文件。
        """
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
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
            print(f"写入日志失败: {e}")

    def log_read(self, agent_name, file_path, description=""):
        """记录一个读操作。"""
        message = f"READ  | Agent: {agent_name:<20} | File: {file_path:<50} | Desc: {description}"
        self._log(message)
        # 为了保持控制台清晰，日志记录操作本身不再重复打印到控制台
        print(f"  [Log] {agent_name} 读取了 {os.path.basename(file_path)}")

    def log_write(self, agent_name, file_path, description=""):
        """记录一个写操作。"""
        message = f"WRITE | Agent: {agent_name:<20} | File: {file_path:<50} | Desc: {description}"
        self._log(message)
        print(f"  [Log] {agent_name} 写入了 {os.path.basename(file_path)}")