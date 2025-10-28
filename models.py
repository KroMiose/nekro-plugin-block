"""数据模型"""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class BlockType(str, Enum):
    """屏蔽类型"""

    PREVENT_TRIGGER = "prevent_trigger"  # 禁止触发：用户消息可见但无法主动唤醒AI
    FULL_BLOCK = "full_block"  # 完全屏蔽：完全看不到该用户的消息


class BlockRecord(BaseModel):
    """屏蔽记录"""

    user_id: str = Field(description="用户唯一标识 (adapter_key:platform_userid)")
    username: str = Field(description="用户名")
    block_type: BlockType = Field(description="屏蔽类型")
    reason: str = Field(default="", description="屏蔽原因")
    start_time: int = Field(description="开始时间戳")
    expire_time: Optional[int] = Field(default=None, description="到期时间戳，None表示永久")
    is_permanent: bool = Field(default=False, description="是否永久屏蔽")


class BlockData(BaseModel):
    """屏蔽数据存储"""

    blocks: Dict[str, BlockRecord] = Field(
        default_factory=dict,
        description="屏蔽记录字典，key为user_id",
    )

    def add_block(self, record: BlockRecord) -> None:
        """添加屏蔽记录"""
        self.blocks[record.user_id] = record

    def remove_block(self, user_id: str) -> bool:
        """移除屏蔽记录"""
        if user_id in self.blocks:
            del self.blocks[user_id]
            return True
        return False

    def get_block(self, user_id: str) -> Optional[BlockRecord]:
        """获取屏蔽记录"""
        return self.blocks.get(user_id)

    def is_blocked(self, user_id: str) -> bool:
        """检查用户是否被屏蔽"""
        return user_id in self.blocks

    def get_active_blocks(self, current_time: int) -> Dict[str, BlockRecord]:
        """获取所有有效的屏蔽记录"""
        active = {}
        for user_id, record in self.blocks.items():
            if record.is_permanent or (record.expire_time and record.expire_time > current_time):
                active[user_id] = record
        return active

    def cleanup_expired(self, current_time: int) -> int:
        """清理已过期的屏蔽记录，返回清理数量
        注意：这只是清理插件数据的记录，系统层面的屏蔽会在到期时自动解除
        """
        expired_users = []
        for user_id, record in self.blocks.items():
            # 只清理有明确过期时间的非永久屏蔽
            if not record.is_permanent and record.expire_time and record.expire_time <= current_time:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self.blocks[user_id]

        return len(expired_users)


class BlockStats(BaseModel):
    """屏蔽统计信息"""

    total_blocks: int = Field(description="总屏蔽数量")
    prevent_trigger_count: int = Field(description="禁止触发数量")
    full_block_count: int = Field(description="完全屏蔽数量")
    permanent_count: int = Field(description="永久屏蔽数量")

