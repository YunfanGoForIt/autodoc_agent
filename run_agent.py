#!/usr/bin/env python3
"""DeepWiki Agent - 主流程脚本"""
import os
import sys
import json
import logging
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from github_stars import GitHubMonitor
from deepwiki_mcp import prepare_workspace
from feishu_notifier import FeishuNotifier
from retry_utils import sync_retry

# 加载环境变量（从当前目录的 .env 文件）
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# 加载环境变量（从当前目录的 .env 文件）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# 配置日志
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"deepwiki_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8', delay=True)
    ]
)
logger = logging.getLogger(__name__)

# 配置
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# 项目目录下的路径
APP_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.join(APP_DIR, "workspace")
DOCS_ROOT = os.path.join(APP_DIR, "docs")
FINAL_OUTPUT_DIR = os.path.join(APP_DIR, "final_docs")
STATE_FILE = os.path.join(APP_DIR, "state.json")
# Syncthing 同步目录
SYNCTHING_DIR = os.path.join(os.path.expanduser("~"), "syncthing", "gitwiki")

# 轮询配置（秒）
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))  # 默认 1 分钟


def load_state() -> Dict[str, Any]:
    """加载状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"processed_repos": {}, "last_sync": None}


def save_state(state: Dict[str, Any]):
    """保存状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


async def fetch_readme(repo_name: str, github_monitor: GitHubMonitor) -> str:
    """获取 README 内容"""
    readme = await github_monitor.fetch_repo_readme(repo_name)
    if readme:
        return readme
    return ""


def run_claude_agent(work_dir: str) -> bool:
    """
    使用 Claude -p 模式运行文档精炼

    Args:
        work_dir: 工作区目录

    Returns:
        bool: 是否成功
    """
    logger.info(f"启动 Claude Agent 处理: {work_dir}")

    # 读取 CLAUDE.md 模板
    claude_md_path = os.path.join(APP_DIR, "CLAUDE.md")
    with open(claude_md_path, "r") as f:
        prompt_template = f.read()

    # 替换工作目录占位符
    prompt = prompt_template.replace("{WORK_DIR}", work_dir)

    # 保存 prompt 到临时文件
    prompt_file = os.path.join(work_dir, ".prompt.txt")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    try:
        success = _execute_claude_with_retry(work_dir, prompt_file)
        return success
    finally:
        # 清理临时文件
        if os.path.exists(prompt_file):
            os.remove(prompt_file)


@sync_retry(max_attempts=3, delay=5.0, exceptions=(subprocess.TimeoutExpired, OSError))
def _execute_claude_with_retry(work_dir: str, prompt_file: str) -> bool:
    """
    执行 Claude 命令（带重试）

    Args:
        work_dir: 工作区目录
        prompt_file: 临时 prompt 文件路径

    Returns:
        bool: 是否成功
    """
    logger.info(f"执行 Claude 命令（工作区: {work_dir}）")

    # 使用 shell 重定向来传递 prompt（直接以当前用户运行）
    shell_cmd = f"cat {prompt_file} | /usr/bin/claude -p --dangerously-skip-permissions"

    result = subprocess.run(
        shell_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=1800,  # 30 分钟超时
        cwd=work_dir  # 在工作区目录中执行
    )

    if result.returncode == 0:
        logger.info(f"Claude Agent 执行成功")

        # 保存输出到日志文件
        output_log = os.path.join(work_dir, "claude_output.log")
        with open(output_log, "w") as f:
            f.write(result.stdout)
        logger.info(f"输出已保存到: {output_log}")

        return True
    else:
        logger.error(f"Claude Agent 执行失败 (返回码: {result.returncode})")
        logger.error(f"错误输出:\n{result.stderr}")

        # 保存错误输出
        error_log = os.path.join(work_dir, "claude_error.log")
        with open(error_log, "w") as f:
            f.write(result.stderr)
        logger.error(f"错误已保存到: {error_log}")

        # 抛出异常以触发重试
        raise subprocess.CalledProcessError(result.returncode, shell_cmd, result.stderr)


async def process_repo(repo_data: Dict[str, Any], github_monitor: GitHubMonitor, feishu_notifier: FeishuNotifier) -> bool:
    """
    处理单个仓库

    Args:
        repo_data: 仓库数据（需包含 full_name, id, description 等）
        github_monitor: GitHub 监控器
        feishu_notifier: 飞书通知器

    Returns:
        bool: 是否成功
    """
    repo_name = repo_data["full_name"]
    description = repo_data.get("description", "")

    logger.info(f"=" * 60)
    logger.info(f"开始处理仓库: {repo_name}")
    logger.info(f"描述: {description}")
    logger.info(f"=" * 60)

    try:
        # 1. 准备工作区
        work_dir = await prepare_workspace(
            repo_name,
            WORKSPACE_ROOT,
            DOCS_ROOT
        )

        if not work_dir:
            logger.error(f"工作区准备失败: {repo_name}")
            return False

        # 2. 获取 README
        readme = await fetch_readme(repo_name, github_monitor)
        readme_path = os.path.join(work_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write(readme)
        logger.info(f"已保存 README: {readme_path}")

        # 3. 运行 Claude Agent 进行文档精炼
        success = run_claude_agent(work_dir)

        if success:
            # 4. 保存最终文档
            final_file = os.path.join(work_dir, "final.md")
            if os.path.exists(final_file):
                # 读取 AI 生成的标题
                title_file = os.path.join(work_dir, "title.txt")
                ai_title = ""
                if os.path.exists(title_file):
                    with open(title_file, "r", encoding="utf-8") as f:
                        ai_title = f.read().strip()
                    logger.info(f"AI 生成标题: {ai_title}")

                # 生成最终文件名
                safe_name = repo_name.replace("/", "_")

                # 清理标题中的非法字符
                def sanitize_filename(name):
                    invalid_chars = '<>:"/\\|?*'
                    for char in invalid_chars:
                        name = name.replace(char, '_')
                    return name

                # 文件名格式：repo_name_title.md 或 repo_name.md
                if ai_title:
                    ai_title_clean = sanitize_filename(ai_title)
                    final_filename = f"{safe_name}_{ai_title_clean}.md"
                else:
                    final_filename = f"{safe_name}.md"

                # 读取原始内容
                with open(final_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # 添加元数据到文档开头
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                metadata = f"""---
title: {ai_title if ai_title else repo_name}
repo: {repo_name}
generated_at: {timestamp}
---

"""
                final_content = metadata + content

                # 保存到最终位置
                final_dest = os.path.join(FINAL_OUTPUT_DIR, final_filename)
                os.makedirs(FINAL_OUTPUT_DIR, exist_ok=True)

                with open(final_dest, "w", encoding="utf-8") as f:
                    f.write(final_content)

                logger.info(f"最终文档已保存: {final_dest}")

                # 同步到 Syncthing 目录
                try:
                    os.makedirs(SYNCTHING_DIR, exist_ok=True)
                    syncthing_dest = os.path.join(SYNCTHING_DIR, final_filename)
                    with open(syncthing_dest, "w", encoding="utf-8") as f:
                        f.write(final_content)
                    logger.info(f"文档已同步至 Syncthing: {syncthing_dest}")
                except Exception as e:
                    logger.warning(f"同步到 Syncthing 失败: {e}")

                # 发送飞书通知
                await feishu_notifier.send_success(
                    repo_name=repo_name,
                    title=ai_title if ai_title else repo_name,
                    file_path=final_dest,
                    description=description
                )

                return True
            else:
                logger.warning(f"未找到 final.md: {work_dir}")
                return False
        else:
            return False

    except Exception as e:
        error_msg = str(e)
        logger.error(f"处理仓库失败 [{repo_name}]: {error_msg}")

        # 发送飞书错误通知
        await feishu_notifier.send_error(repo_name, error_msg)

        return False


async def retry_failed_repos(github_monitor: GitHubMonitor, feishu_notifier: FeishuNotifier):
    """重试所有失败的仓库"""
    state = load_state()
    processed = state.get("processed_repos", {})

    # 找出所有 failed 状态的仓库
    failed_repos = [
        (repo_id, info) for repo_id, info in processed.items()
        if info.get("status") == "failed"
    ]

    if not failed_repos:
        return

    logger.info(f"发现 {len(failed_repos)} 个失败仓库，开始重试...")

    for repo_id, info in failed_repos:
        repo_name = info.get("repo_name")
        if not repo_name:
            continue

        logger.info(f"重试失败仓库: {repo_name}")

        # 从 GitHub 获取仓库信息
        try:
            repo_data = await github_monitor.get_repo_info(repo_name)
        except Exception as e:
            logger.error(f"获取仓库信息失败: {repo_name}, {e}")
            continue

        # 处理仓库
        success = await process_repo(repo_data, github_monitor, feishu_notifier)

        # 更新状态
        processed[repo_id] = {
            "repo_name": repo_name,
            "status": "success" if success else "failed",
            "timestamp": datetime.now().isoformat()
        }
        save_state({"processed_repos": processed, "last_sync": datetime.now().isoformat()})

        if success:
            logger.info(f"重试成功: {repo_name}")
        else:
            logger.error(f"重试仍失败: {repo_name}")

        # 避免 API 限流
        await asyncio.sleep(2)


async def process_all_stars():
    """
    处理所有历史星标仓库（存量解析）
    用于 --all 参数，遍历所有 star 的仓库并处理
    """
    if not GITHUB_TOKEN:
        logger.error("请设置 GITHUB_TOKEN 环境变量")
        return

    github_monitor = GitHubMonitor(GITHUB_TOKEN)
    feishu_notifier = FeishuNotifier()

    # 获取所有 star 的仓库
    logger.info("获取所有历史星标仓库...")
    all_stars = await github_monitor.fetch_all_stars()
    logger.info(f"共获取 {len(all_stars)} 个星标仓库")

    # 加载状态
    state = load_state()
    processed = state.get("processed_repos", {})

    success_count = 0
    fail_count = 0
    skip_count = 0

    for star in all_stars:
        repo_id = str(star["id"])
        repo_name = star["full_name"]

        # 跳过已成功的
        if repo_id in processed and processed[repo_id].get("status") == "success":
            logger.debug(f"跳过已处理: {repo_name}")
            skip_count += 1
            continue

        # 处理仓库
        success = await process_repo(star, github_monitor, feishu_notifier)

        # 更新状态
        processed[repo_id] = {
            "repo_name": repo_name,
            "status": "success" if success else "failed",
            "timestamp": datetime.now().isoformat()
        }
        save_state({"processed_repos": processed, "last_sync": datetime.now().isoformat()})

        if success:
            logger.info(f"成功处理: {repo_name}")
            success_count += 1
        else:
            logger.error(f"处理失败: {repo_name}")
            fail_count += 1

        # 避免 API 限流
        await asyncio.sleep(2)

    logger.info("=" * 60)
    logger.info("存量解析完成!")
    logger.info(f"成功: {success_count}, 失败: {fail_count}, 跳过: {skip_count}")
    logger.info("=" * 60)


async def sync_new_stars():
    """同步新的 star 仓库"""
    if not GITHUB_TOKEN:
        logger.error("请设置 GITHUB_TOKEN 环境变量")
        return

    github_monitor = GitHubMonitor(GITHUB_TOKEN)
    feishu_notifier = FeishuNotifier()  # 初始化飞书通知器

    # 重试失败的仓库
    await retry_failed_repos(github_monitor, feishu_notifier)

    # 获取最近的 stars
    logger.info("获取最近的 GitHub stars...")
    stars = await github_monitor.fetch_recent_stars(limit=10)
    logger.info(f"发现 {len(stars)} 个最近 star 的仓库")

    # 加载状态
    state = load_state()
    processed = state.get("processed_repos", {})

    # 处理每个仓库
    for star in stars:
        repo_id = str(star["id"])
        repo_name = star["full_name"]

        # 跳过已成功处理的（failed 状态允许重试）
        if repo_id in processed and processed[repo_id].get("status") == "success":
            logger.info(f"跳过已处理: {repo_name}")
            continue

        # 处理仓库（传入 feishu_notifier）
        success = await process_repo(star, github_monitor, feishu_notifier)

        # 更新状态
        processed[repo_id] = {
            "repo_name": repo_name,
            "status": "success" if success else "failed",
            "timestamp": datetime.now().isoformat()
        }
        save_state({"processed_repos": processed, "last_sync": datetime.now().isoformat()})

        if success:
            logger.info(f"成功处理: {repo_name}")
        else:
            logger.error(f"处理失败: {repo_name}")


async def main(mode: str = "poll"):
    """
    主函数

    Args:
        mode: 运行模式
            - "poll": 轮询模式（默认），定期检查新 stars + 重试失败
            - "all": 存量模式，处理所有历史 stars 后进入轮询
    """
    logger.info("=" * 60)
    logger.info("DeepWiki Agent 启动")
    logger.info(f"运行模式: {mode}")
    logger.info(f"轮询间隔: {POLL_INTERVAL} 秒")
    logger.info("=" * 60)

    if mode == "all":
        # 先处理所有历史 stars
        await process_all_stars()

    iteration = 0
    while True:
        iteration += 1
        logger.info(f"\n{'=' * 60}")
        logger.info(f"第 {iteration} 次轮询")
        logger.info(f"{'=' * 60}\n")

        try:
            await sync_new_stars()
        except Exception as e:
            logger.error(f"轮询执行出错: {e}")

        logger.info(f"\n本次轮询完成，等待 {POLL_INTERVAL} 秒后下次轮询...")
        logger.info(f"下次执行时间: {datetime.fromtimestamp(datetime.now().timestamp() + POLL_INTERVAL).strftime('%Y-%m-%d %H:%M:%S')}\n")

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # 解析命令行参数
    mode = "poll"
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--all", "-a"]:
            mode = "all"
        elif sys.argv[1] in ["--help", "-h"]:
            print("用法: python run_agent.py [选项]")
            print("选项:")
            print("  --all, -a    处理所有历史星标仓库后开始轮询")
            print("  --help, -h   显示此帮助信息")
            print("  无参数       直接开始轮询模式")
            sys.exit(0)

    asyncio.run(main(mode))
