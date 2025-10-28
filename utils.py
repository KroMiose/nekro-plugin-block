"""工具函数"""

import time
from datetime import datetime
from typing import Optional, cast

from nekro_agent.api.schemas import AgentCtx
from nekro_agent.models.db_user import DBUser

from .models import BlockData, BlockRecord, BlockType
from .plugin import config, plugin

store = plugin.store


async def get_block_data(chat_key: str) -> BlockData:
    """获取屏蔽数据"""
    data = await store.get(chat_key=chat_key, store_key="blocks")
    if data:
        return BlockData.model_validate_json(data)
    return BlockData()


async def save_block_data(chat_key: str, data: BlockData) -> None:
    """保存屏蔽数据"""
    await store.set(chat_key=chat_key, store_key="blocks", value=data.model_dump_json())


async def get_user_by_unique_id(unique_id: str) -> Optional[DBUser]:
    """根据唯一标识获取用户

    Args:
        unique_id: 格式为 "adapter_key:platform_userid"
    """
    try:
        parts = unique_id.split(":", 1)
        if len(parts) != 2:
            return None
        adapter_key, platform_userid = parts
        return await DBUser.get_by_union_id(adapter_key, platform_userid)
    except Exception:
        return None


def format_time_remaining(expire_time: Optional[int]) -> str:
    """格式化剩余时间"""
    if expire_time is None:
        return "永久"

    current_time = int(time.time())
    remaining_seconds = expire_time - current_time

    if remaining_seconds <= 0:
        return "已过期"

    days = remaining_seconds // 86400
    hours = (remaining_seconds % 86400) // 3600
    minutes = (remaining_seconds % 3600) // 60

    if days > 0:
        return f"{days}天{hours}小时"
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def calculate_expire_time(seconds: Optional[int]) -> Optional[int]:
    """计算到期时间戳

    Args:
        seconds: 屏蔽秒数，None表示永久

    Returns:
        时间戳，None表示永久
    """
    if seconds is None:
        return None

    # 应用最大时长限制
    if config.MAX_BLOCK_SECONDS > 0:
        seconds = min(seconds, config.MAX_BLOCK_SECONDS)

    current_time = int(time.time())
    return current_time + seconds


def get_block_type_description(block_type: BlockType) -> str:
    """获取屏蔽类型的描述"""
    descriptions = {
        BlockType.PREVENT_TRIGGER: "禁止触发（可见但无法主动唤醒）",
        BlockType.FULL_BLOCK: "完全屏蔽（完全不可见）",
    }
    return descriptions.get(block_type, str(block_type))


async def apply_block_to_system(
    user_id: str,
    block_type: BlockType,
    expire_time: Optional[int],
) -> bool:
    """将屏蔽应用到系统层面

    Args:
        user_id: 用户唯一标识
        block_type: 屏蔽类型
        expire_time: 到期时间戳

    Returns:
        是否成功
    """
    try:
        user = await get_user_by_unique_id(user_id)
        if not user:
            return False

        # 转换时间戳为datetime
        expire_datetime: Optional[datetime] = None
        if expire_time:
            expire_datetime = datetime.fromtimestamp(expire_time)

        if block_type == BlockType.PREVENT_TRIGGER:
            # 设置禁止触发
            user.prevent_trigger_until = cast(datetime, expire_datetime)
        else:
            # BlockType.FULL_BLOCK - 设置完全屏蔽（封禁）
            user.ban_until = cast(datetime, expire_datetime)

        await user.save()
    except Exception:
        return False
    else:
        return True


async def remove_block_from_system(user_id: str, block_type: BlockType) -> bool:
    """从系统层面移除屏蔽

    Args:
        user_id: 用户唯一标识
        block_type: 屏蔽类型

    Returns:
        是否成功
    """
    try:
        user = await get_user_by_unique_id(user_id)
        if not user:
            return False

        # 使用cast处理类型检查，虽然赋值None但字段定义允许null
        if block_type == BlockType.PREVENT_TRIGGER:
            user.prevent_trigger_until = cast(datetime, None)
        else:
            # BlockType.FULL_BLOCK
            user.ban_until = cast(datetime, None)

        await user.save()
    except Exception:
        return False
    else:
        return True
