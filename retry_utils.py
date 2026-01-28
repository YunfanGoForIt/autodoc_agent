#!/usr/bin/env python3
"""重试工具模块"""
import asyncio
import logging
from typing import Callable, TypeVar, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    异步函数重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避系数（每次重试延迟时间乘以这个系数）
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} 失败，已重试 {max_attempts} 次: {e}")
                        raise

                    logger.warning(
                        f"{func.__name__} 失败（尝试 {attempt}/{max_attempts}）: {e}，"
                        f"{current_delay:.1f} 秒后重试..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # 理论上不会到达这里
            raise RuntimeError("重试逻辑错误")

        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    同步函数重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避系数（每次重试延迟时间乘以这个系数）
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import time
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} 失败，已重试 {max_attempts} 次: {e}")
                        raise

                    logger.warning(
                        f"{func.__name__} 失败（尝试 {attempt}/{max_attempts}）: {e}，"
                        f"{current_delay:.1f} 秒后重试..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

            # 理论上不会到达这里
            raise RuntimeError("重试逻辑错误")

        return wrapper
    return decorator
