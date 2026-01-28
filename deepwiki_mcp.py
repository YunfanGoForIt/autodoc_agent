#!/usr/bin/env python3
"""DeepWiki MCP 客户端 - 获取仓库文档"""
import os
import json
import glob
import logging
import asyncio
from typing import Optional
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv("/www/wwwroot/mcp_deepwiki/.env")


class DeepWikiMCPClient:
    """DeepWiki MCP 客户端"""

    def __init__(self):
        self.base_url = os.getenv("DEEPWIKI_BASE_URL", "http://localhost:3000")
        self.timeout = 300  # 5 分钟超时

    async def fetch_repo_docs(self, repo_name: str, output_dir: str) -> bool:
        """
        从 DeepWiki MCP 获取仓库文档

        Args:
            repo_name: 仓库名称，例如 "owner/repo"
            output_dir: 输出目录

        Returns:
            bool: 是否成功
        """
        logger.info(f"正在从 DeepWiki 获取文档: {repo_name}")

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        try:
            # 这里调用 DeepWiki MCP 的 API
            # 假设有一个简单的 HTTP 接口
            # 实际实现需要根据 DeepWiki MCP 的具体接口调整

            # 方法1: 如果 DeepWiki 有 HTTP API
            # async with httpx.AsyncClient(timeout=self.timeout) as client:
            #     response = await client.post(
            #         f"{self.base_url}/fetch",
            #         json={"repo": repo_name}
            #     )
            #     response.raise_for_status()
            #     docs = response.json()
            #     # 保存文档到 output_dir

            # 方法2: 使用 mcp 代理命令
            cmd = f"mcp call deepwiki fetch-and-save '{repo_name}' '{output_dir}'"
            logger.info(f"执行命令: {cmd}")

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                logger.info(f"成功获取文档: {repo_name}")
                return True
            else:
                logger.error(f"获取文档失败: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"获取文档异常: {e}")
            return False

    def check_local_docs(self, repo_name: str, docs_root: str) -> Optional[str]:
        """
        检查本地是否已有该仓库的文档

        Args:
            repo_name: 仓库名称
            docs_root: 文档根目录

        Returns:
            如果找到，返回文档目录路径；否则返回 None
        """
        safe_name = repo_name.replace("/", "_")
        repo_dir = os.path.join(docs_root, safe_name)

        if os.path.exists(repo_dir):
            # 检查是否有 Overview.md
            overview_files = glob.glob(os.path.join(repo_dir, "*Overview.md"))
            if overview_files:
                logger.info(f"找到本地文档: {repo_dir}")
                return repo_dir

        return None


async def prepare_workspace(repo_name: str, workspace_root: str, docs_root: str) -> str:
    """
    准备工作区
    - 从 DeepWiki MCP 获取文档
    - 从 GitHub 获取 README
    - 组织文件结构

    Args:
        repo_name: 仓库名称
        workspace_root: 工作区根目录
        docs_root: DeepWiki 文档根目录

    Returns:
        工作区路径
    """
    safe_name = repo_name.replace("/", "_")
    work_dir = os.path.join(workspace_root, safe_name)
    os.makedirs(work_dir, exist_ok=True)

    # 1. 检查是否已有 DeepWiki 文档
    mcp_client = DeepWikiMCPClient()
    local_docs = mcp_client.check_local_docs(repo_name, docs_root)

    if not local_docs:
        # 尝试从 MCP 获取
        docs_dir = os.path.join(docs_root, safe_name)
        success = await mcp_client.fetch_repo_docs(repo_name, docs_dir)
        if not success:
            logger.warning(f"无法获取 DeepWiki 文档: {repo_name}")
            return None
        local_docs = docs_dir

    # 2. 复制 Overview.md 到工作区
    overview_files = glob.glob(os.path.join(local_docs, "*Overview.md"))
    if overview_files:
        import shutil
        shutil.copy(overview_files[0], os.path.join(work_dir, "overview.md"))
        logger.info(f"已复制 overview.md")
    else:
        logger.warning(f"未找到 Overview.md: {repo_name}")
        return None

    # 3. 复制其他文档到 docs/ 子目录
    docs_subdir = os.path.join(work_dir, "docs")
    os.makedirs(docs_subdir, exist_ok=True)

    all_md_files = glob.glob(os.path.join(local_docs, "*.md"))
    for md_file in all_md_files:
        if "Overview" not in md_file:
            import shutil
            shutil.copy(md_file, docs_subdir)
            logger.info(f"已复制文档: {os.path.basename(md_file)}")

    return work_dir


async def main():
    """测试脚本"""
    docs_root = "/www/wwwroot/mcp_deepwiki/output"
    workspace_root = "/www/wwwroot/deepwiki_agent/workspace"

    # 测试准备工作区
    work_dir = await prepare_workspace(
        "your-org/repo-name",
        workspace_root,
        docs_root
    )
    if work_dir:
        logger.info(f"工作区准备完成: {work_dir}")


if __name__ == "__main__":
    asyncio.run(main())
