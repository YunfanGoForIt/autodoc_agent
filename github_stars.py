#!/usr/bin/env python3
"""GitHub 星标监控模块"""
import os
import httpx
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from retry_utils import async_retry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class GitHubConfig:
    token: str
    api_url: str = "https://api.github.com/user/starred"


class GitHubMonitor:
    def __init__(self, token: str):
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
        }
        self.api_url = "https://api.github.com/user/starred"

    @async_retry(max_attempts=3, delay=2.0, exceptions=(httpx.HTTPError, httpx.HTTPStatusError))
    async def fetch_recent_stars(self, limit: int = 30):
        """获取最近 star 的仓库"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.api_url,
                headers=self.headers,
                params={"per_page": limit, "sort": "created", "direction": "desc"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def fetch_all_stars(self):
        """获取所有 star 的仓库"""
        all_stars = []
        page = 1
        per_page = 100

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    logger.info(f"获取 stars 页面 {page}...")
                    response = await client.get(
                        self.api_url,
                        headers=self.headers,
                        params={"per_page": per_page, "page": page, "sort": "created", "direction": "desc"}
                    )
                    response.raise_for_status()
                    stars = response.json()

                    if not stars:
                        break

                    all_stars.extend(stars)

                    if len(stars) < per_page:
                        break

                    page += 1
                except Exception as e:
                    logger.error(f"获取所有 stars 页面 {page} 失败: {str(e)}")
                    break

        return all_stars

    @async_retry(max_attempts=3, delay=2.0, exceptions=(httpx.HTTPError, httpx.HTTPStatusError))
    async def fetch_repo_readme(self, repo_name: str) -> Optional[str]:
        """获取仓库的 README 内容"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 尝试常见的 README 文件名
            for readme_name in ["README.md", "README.zh.md", "README.zh-CN.md"]:
                url = f"https://api.github.com/repos/{repo_name}/contents/{readme_name}"
                response = await client.get(url, headers=self.headers)

                if response.status_code == 200:
                    data = response.json()
                    import base64
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    logger.info(f"成功获取 README: {repo_name}/{readme_name}")
                    return content
                elif response.status_code == 404:
                    continue

            logger.info(f"未找到 README: {repo_name}")
            return None


async def main():
    """测试脚本"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("请设置 GITHUB_TOKEN 环境变量")
        return

    monitor = GitHubMonitor(token)
    stars = await monitor.fetch_recent_stars(limit=5)
    logger.info(f"获取到 {len(stars)} 个最近 star 的仓库")

    for star in stars[:3]:
        repo_name = star["full_name"]
        logger.info(f"仓库: {repo_name}")
        readme = await monitor.fetch_repo_readme(repo_name)
        if readme:
            logger.info(f"README 长度: {len(readme)} 字符")


if __name__ == "__main__":
    asyncio.run(main())
