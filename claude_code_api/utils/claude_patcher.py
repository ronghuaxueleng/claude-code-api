"""Claude CLI Root Check Patcher - 移除 root 用户限制"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

# 要删除的代码片段（压缩格式 - 来自 Claude CLI）
ROOT_CHECK_PATTERN = r'if\(process\.platform!=="win32"&&typeof process\.getuid==="function"&&process\.getuid\(\)===0&&!process\.env\.IS_SANDBOX\)console\.error\("--dangerously-skip-permissions cannot be used with root/sudo privileges for security reasons"\),process\.exit\(1\)'


class ClaudePatcher:
    """Claude CLI 补丁管理器 - 自动移除 root 权限检查"""

    def __init__(self, claude_binary_path: str):
        self.claude_binary_path = Path(claude_binary_path)
        self.cli_js_path: Optional[Path] = None
        self.is_patched = False

    def find_cli_js(self) -> Optional[Path]:
        """查找 Claude CLI 的实际 cli.js 文件路径"""

        # 检查是否是软链接
        if self.claude_binary_path.is_symlink():
            real_path = self.claude_binary_path.resolve()
            logger.info(f"Claude 是软链接，实际路径: {real_path}")
        else:
            real_path = self.claude_binary_path

        # 常见的 cli.js 路径模式
        search_patterns = [
            # 通过软链接解析
            real_path,
            # npm 全局安装路径
            real_path.parent.parent / 'lib' / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js',
            Path('/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js'),
            Path('/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js'),
            # 通过 npm 查询
            self._find_via_npm(),
        ]

        for path in search_patterns:
            if path and path.exists() and path.suffix == '.js':
                logger.info(f"找到 Claude CLI 文件: {path}")
                return path

        logger.warning("未找到 Claude CLI 的 cli.js 文件")
        return None

    def _find_via_npm(self) -> Optional[Path]:
        """通过 npm 查询 Claude CLI 路径"""
        try:
            result = subprocess.run(
                ['npm', 'root', '-g'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                npm_root = result.stdout.strip()
                cli_path = Path(npm_root) / '@anthropic-ai' / 'claude-code' / 'cli.js'
                if cli_path.exists():
                    return cli_path
        except Exception as e:
            logger.debug(f"通过 npm 查询失败: {e}")
        return None

    def check_if_patched(self, cli_path: Path) -> bool:
        """检查文件是否已经被修补（移除了 root 检查）"""
        try:
            with open(cli_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 检查是否包含 root 检查代码
                if re.search(ROOT_CHECK_PATTERN, content):
                    return False  # 未修补
                elif '--dangerously-skip-permissions cannot be used with root/sudo' in content:
                    return False  # 存在相关代码但格式可能不同
                else:
                    return True  # 已修补或不存在该检查
        except Exception as e:
            logger.error(f"检查文件时出错: {e}")
            return False

    def create_backup(self, cli_path: Path) -> bool:
        """创建文件备份"""
        backup_path = cli_path.with_suffix('.js.original')

        # 如果备份已存在，跳过
        if backup_path.exists():
            logger.info(f"备份文件已存在: {backup_path}")
            return True

        try:
            shutil.copy2(cli_path, backup_path)
            logger.info(f"✓ 已创建备份: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return False

    def patch_cli_file(self, cli_path: Path) -> bool:
        """修补 CLI 文件，移除 root 权限检查"""
        try:
            # 读取文件内容
            with open(cli_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 记录原始长度
            original_length = len(content)

            # 移除 root 检查代码
            patched_content = re.sub(ROOT_CHECK_PATTERN, '', content)

            # 如果内容有变化，说明找到并移除了代码
            if len(patched_content) < original_length:
                # 写回文件
                with open(cli_path, 'w', encoding='utf-8') as f:
                    f.write(patched_content)

                removed_chars = original_length - len(patched_content)
                logger.info(f"✓ 已移除 root 检查代码 (删除 {removed_chars} 字符)")
                return True
            else:
                logger.info("文件中未找到需要移除的 root 检查代码")
                return True  # 没有需要修补的内容也算成功

        except Exception as e:
            logger.error(f"修补文件失败: {e}")
            return False

    def auto_patch(self) -> bool:
        """自动检测并修补 Claude CLI"""
        logger.info("开始检查 Claude CLI root 权限限制...")

        # 1. 查找 cli.js 文件
        cli_path = self.find_cli_js()
        if not cli_path:
            logger.warning("无法找到 Claude CLI 文件，跳过修补")
            return False

        self.cli_js_path = cli_path

        # 2. 检查是否已修补
        if self.check_if_patched(cli_path):
            logger.info("✓ Claude CLI 已修补或无需修补")
            self.is_patched = True
            return True

        # 3. 需要修补 - 先创建备份
        logger.info("检测到 root 权限限制，准备移除...")
        if not self.create_backup(cli_path):
            logger.error("创建备份失败，取消修补")
            return False

        # 4. 执行修补
        if self.patch_cli_file(cli_path):
            logger.info("✓ Claude CLI root 权限限制已成功移除")
            self.is_patched = True
            return True
        else:
            logger.error("修补失败")
            return False

    def restore_original(self) -> bool:
        """恢复原始文件（从备份）"""
        if not self.cli_js_path:
            logger.error("未知 CLI 文件路径，无法恢复")
            return False

        backup_path = self.cli_js_path.with_suffix('.js.original')
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return False

        try:
            shutil.copy2(backup_path, self.cli_js_path)
            logger.info(f"✓ 已从备份恢复原始文件: {self.cli_js_path}")
            self.is_patched = False
            return True
        except Exception as e:
            logger.error(f"恢复文件失败: {e}")
            return False


# 全局实例（延迟初始化）
_patcher_instance: Optional[ClaudePatcher] = None


def get_patcher(claude_binary_path: str) -> ClaudePatcher:
    """获取或创建 Patcher 实例"""
    global _patcher_instance
    if _patcher_instance is None:
        _patcher_instance = ClaudePatcher(claude_binary_path)
    return _patcher_instance


def auto_patch_claude(claude_binary_path: str) -> bool:
    """
    自动修补 Claude CLI，移除 root 权限限制

    Args:
        claude_binary_path: Claude 二进制文件路径

    Returns:
        bool: 修补是否成功
    """
    patcher = get_patcher(claude_binary_path)
    return patcher.auto_patch()


def restore_claude_original(claude_binary_path: str) -> bool:
    """
    恢复 Claude CLI 原始文件

    Args:
        claude_binary_path: Claude 二进制文件路径

    Returns:
        bool: 恢复是否成功
    """
    patcher = get_patcher(claude_binary_path)
    return patcher.restore_original()
