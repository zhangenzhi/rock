import os
import subprocess

class GitManager:
    """封装所有Git操作的模块"""
    def __init__(self, repo_path="."):
        self.repo_path = repo_path
        if not os.path.isdir(os.path.join(repo_path, '.git')):
            raise EnvironmentError("错误：当前目录不是一个有效的Git仓库。")

    def _run_command(self, command, suppress_errors=False):
        try:
            result = subprocess.run(command, cwd=self.repo_path, check=True, capture_output=True, text=True, encoding='utf-8')
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                print(f"Git命令执行失败: {e.stderr.strip()}")
            return None

    def get_current_branch(self):
        return self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    def branch_exists(self, branch_name):
        local_exists = self._run_command(["git", "branch", "--list", branch_name], suppress_errors=True)
        remote_exists = self._run_command(["git", "branch", "-r", "--list", f"origin/{branch_name}"], suppress_errors=True)
        return bool(local_exists or remote_exists)

    def list_all_branches(self):
        local_branches_raw = self._run_command(["git", "branch"])
        remote_branches_raw = self._run_command(["git", "branch", "-r"])
        branches = set()
        if local_branches_raw:
            for line in local_branches_raw.split('\n'):
                branches.add(line.strip().replace("* ", ""))
        if remote_branches_raw:
            for line in remote_branches_raw.split('\n'):
                branch_name = line.strip().replace("origin/", "")
                if "->" not in branch_name:
                    branches.add(branch_name)
        return list(branches)

    def delete_branch(self, branch_name):
        print(f"正在删除分支: {branch_name}")
        self._run_command(["git", "branch", "-D", branch_name], suppress_errors=True)
        self._run_command(["git", "push", "origin", "--delete", branch_name], suppress_errors=True)

    def switch_to_branch(self, branch_name, create_if_not_exists=False):
        if self.get_current_branch() == branch_name: return True
        if self.branch_exists(branch_name):
            print(f"切换到已存在的分支: {branch_name}")
            return self._run_command(["git", "checkout", branch_name]) is not None
        elif create_if_not_exists:
            print(f"正在创建并切换到新分支: {branch_name}")
            return self._run_command(["git", "checkout", "-b", branch_name]) is not None
        return False

    def commit_and_push(self, file_paths, message):
        branch = self.get_current_branch()
        if not branch: return
        print(f"\n--- 正在向分支 '{branch}' 提交并推送 ---")
        for file_path in file_paths:
             if os.path.exists(file_path):
                self._run_command(["git", "add", file_path])
        self._run_command(["git", "commit", "-m", message])
        self._run_command(["git", "push", "--set-upstream", "origin", branch])
        print(f"成功将更改推送到 origin/{branch}")
