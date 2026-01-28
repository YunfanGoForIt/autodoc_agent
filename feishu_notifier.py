#!/usr/bin/env python3
"""飞书通知模块"""
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书 Webhook 通知器"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")
        if not self.webhook_url or self.webhook_url == "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_URL":
            logger.warning("FEISHU_WEBHOOK_URL 未配置，飞书通知将被禁用")

    async def send_success(
        self,
        repo_name: str,
        title: str,
        file_path: str,
        description: str = ""
    ):
        """发送成功通知"""
        if not self.webhook_url or self.webhook_url.endswith("YOUR_WEBHOOK_URL"):
            return

        # 构建消息内容
        text = f"""✅ 文档生成成功

仓库: {repo_name}
标题: {title}
描述: {description or '无'}
文件路径: {file_path}"""

        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"飞书通知已发送: {repo_name}")
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")

    async def send_error(
        self,
        repo_name: str,
        error_message: str
    ):
        """发送错误通知"""
        if not self.webhook_url or self.webhook_url.endswith("YOUR_WEBHOOK_URL"):
            return

        # 构建消息内容
        text = f"""❌ 文档生成失败

仓库: {repo_name}
错误信息: {error_message}"""

        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"飞书错误通知已发送: {repo_name}")
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")


# 使用示例
async def main():
    # 测试发送通知
    notifier = FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_URL")
    await notifier.send_success(
        repo_name="test/repo",
        title="测试项目",
        file_path="/path/to/file.md",
        description="这是一个测试项目"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
