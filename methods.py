"""插件方法实现"""

import time
from typing import Optional

from nekro_agent.api import core
from nekro_agent.api.plugin import SandboxMethodType
from nekro_agent.api.schemas import AgentCtx

from .models import BlockRecord, BlockType
from .plugin import config, plugin
from .utils import (
    apply_block_to_system,
    calculate_expire_time,
    format_time_remaining,
    get_block_data,
    get_block_type_description,
    get_user_by_unique_id,
    remove_block_from_system,
    save_block_data,
)


@plugin.mount_sandbox_method(SandboxMethodType.BEHAVIOR, "屏蔽用户_禁止触发模式")
async def block_user_prevent_trigger(
    _ctx: AgentCtx,
    user_identifier: str,
    reason: str = "未说明原因",
    duration_seconds: Optional[int] = None,
) -> str:
    """屏蔽用户（禁止触发模式）

    当你决定屏蔽某个用户时使用此功能。被屏蔽后，该用户发送的消息你仍能看到（当被其他消息或触发条件唤醒时），但他的消息无法直接唤醒你。
    适用场景：用户频繁@你或刷屏，但你仍想保留观察他的权利。

    Args:
        user_identifier (str): 用户的平台ID
        reason (str): 屏蔽原因，建议说明具体理由
        duration_seconds (int): 屏蔽时长（秒），不传则使用默认值，传None或负数表示永久（需要配置允许）

    Returns:
        str: 操作结果描述
    """
    if not config.ENABLE_PREVENT_TRIGGER:
        return "❌ 禁止触发功能未启用，请联系管理员开启"

    # 处理屏蔽时长
    if duration_seconds is None or duration_seconds < 0:
        if config.ALLOW_PERMANENT_BLOCK:
            is_permanent = True
            expire_time = None
            duration_seconds = None
        else:
            duration_seconds = config.DEFAULT_BLOCK_SECONDS
            is_permanent = False
            expire_time = calculate_expire_time(duration_seconds)
    else:
        is_permanent = False
        expire_time = calculate_expire_time(duration_seconds)

    # 查找用户
    from nekro_agent.models.db_user import DBUser

    user = None
    user_id = None

    user = await DBUser.get_or_none(
        adapter_key=_ctx.adapter_key,
        platform_userid=user_identifier,
    )

    if not user:
        return f"❌ 未找到用户: {user_identifier}"

    user_id = user.unique_id

    # 获取屏蔽数据
    block_data = await get_block_data(_ctx.chat_key)

    # 检查是否已经被屏蔽
    existing_block = block_data.get_block(user_id)
    if existing_block:
        return f"⚠️ 用户 {user.username} 已经被{get_block_type_description(existing_block.block_type)}，无需重复操作"

    # 创建屏蔽记录
    record = BlockRecord(
        user_id=user_id,
        username=user.username,
        block_type=BlockType.PREVENT_TRIGGER,
        reason=reason,
        start_time=int(time.time()),
        expire_time=expire_time,
        is_permanent=is_permanent,
    )

    # 保存到插件数据
    block_data.add_block(record)
    await save_block_data(_ctx.chat_key, block_data)

    # 应用到系统
    success = await apply_block_to_system(user_id, BlockType.PREVENT_TRIGGER, expire_time)

    if not success:
        return f"❌ 屏蔽用户 {user.username} 失败，请稍后重试"

    if is_permanent:
        time_desc = "永久"
        log_time_desc = "永久"
    else:
        # 转换秒数为可读格式
        assert duration_seconds is not None  # 类型保证
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        if hours > 0:
            time_desc = f"{hours}小时" if minutes == 0 else f"{hours}小时{minutes}分钟"
        else:
            time_desc = f"{minutes}分钟"
        log_time_desc = f"{time_desc}({duration_seconds}秒)"

    core.logger.info(
        f"[屏蔽插件] AI在聊天 {_ctx.chat_key} 中屏蔽了用户 {user.username}({user_id}) - 禁止触发模式，时长: {log_time_desc}，原因: {reason}",
    )
    return f"✅ 已将用户 {user.username} 设置为禁止触发模式（时长: {time_desc}）\n原因: {reason}\n效果: 该用户无法直接唤醒我，但我在被其他消息唤醒时仍能看到他的消息"


@plugin.mount_sandbox_method(SandboxMethodType.BEHAVIOR, "屏蔽用户_完全屏蔽模式")
async def block_user_full(
    _ctx: AgentCtx,
    user_identifier: str,
    reason: str = "未说明原因",
    duration_seconds: Optional[int] = None,
) -> str:
    """屏蔽用户（完全屏蔽模式）

    当你决定完全屏蔽某个用户时使用此功能。被屏蔽后，你将完全看不到该用户的任何消息，就像他不存在一样。
    适用场景：用户严重违规、恶意骚扰，或你完全不想看到他的任何消息。

    Args:
        user_identifier (str): 用户的平台ID
        reason (str): 屏蔽原因，建议说明具体理由
        duration_seconds (int): 屏蔽时长（秒），不传则使用默认值，传None或负数表示永久（需要配置允许）

    Returns:
        str: 操作结果描述
    """
    if not config.ENABLE_FULL_BLOCK:
        return "❌ 完全屏蔽功能未启用，请联系管理员开启"

    # 处理屏蔽时长
    if duration_seconds is None or duration_seconds < 0:
        if config.ALLOW_PERMANENT_BLOCK:
            is_permanent = True
            expire_time = None
            duration_seconds = None
        else:
            duration_seconds = config.DEFAULT_BLOCK_SECONDS
            is_permanent = False
            expire_time = calculate_expire_time(duration_seconds)
    else:
        is_permanent = False
        expire_time = calculate_expire_time(duration_seconds)

    # 查找用户
    from nekro_agent.models.db_user import DBUser

    user = None
    user_id = None

    user = await DBUser.get_or_none(
        adapter_key=_ctx.adapter_key,
        platform_userid=user_identifier,
    )

    if not user:
        return f"❌ 未找到用户: {user_identifier}"

    user_id = user.unique_id

    # 获取屏蔽数据
    block_data = await get_block_data(_ctx.chat_key)

    # 检查是否已经被屏蔽
    existing_block = block_data.get_block(user_id)
    if existing_block:
        return f"⚠️ 用户 {user.username} 已经被{get_block_type_description(existing_block.block_type)}，无需重复操作"

    # 创建屏蔽记录
    record = BlockRecord(
        user_id=user_id,
        username=user.username,
        block_type=BlockType.FULL_BLOCK,
        reason=reason,
        start_time=int(time.time()),
        expire_time=expire_time,
        is_permanent=is_permanent,
    )

    # 保存到插件数据
    block_data.add_block(record)
    await save_block_data(_ctx.chat_key, block_data)

    # 应用到系统
    success = await apply_block_to_system(user_id, BlockType.FULL_BLOCK, expire_time)

    if not success:
        return f"❌ 屏蔽用户 {user.username} 失败，请稍后重试"

    if is_permanent:
        time_desc = "永久"
        log_time_desc = "永久"
    else:
        # 转换秒数为可读格式
        assert duration_seconds is not None  # 类型保证
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        if hours > 0:
            time_desc = f"{hours}小时" if minutes == 0 else f"{hours}小时{minutes}分钟"
        else:
            time_desc = f"{minutes}分钟"
        log_time_desc = f"{time_desc}({duration_seconds}秒)"

    core.logger.info(
        f"[屏蔽插件] AI在聊天 {_ctx.chat_key} 中完全屏蔽了用户 {user.username}({user_id})，时长: {log_time_desc}，原因: {reason}",
    )
    return f"✅ 已将用户 {user.username} 设置为完全屏蔽模式（时长: {time_desc}）\n原因: {reason}\n效果: 我将完全看不到该用户的任何消息"


@plugin.mount_sandbox_method(SandboxMethodType.BEHAVIOR, "解除用户屏蔽")
async def unblock_user(_ctx: AgentCtx, user_identifier: str) -> str:
    """解除用户屏蔽

    当你决定解除对某个用户的屏蔽时使用此功能。解除后，该用户可以正常与你交互。

    Args:
        user_identifier (str): 用户的平台ID（如QQ号"12345678"）或唯一标识（如"onebot_v11:12345678"）

    Returns:
        str: 操作结果描述
    """
    # 查找用户
    from nekro_agent.models.db_user import DBUser

    user = None
    user_id = None

    user = await DBUser.get_or_none(
        adapter_key=_ctx.adapter_key,
        platform_userid=user_identifier,
    )

    if not user:
        return f"❌ 未找到用户: {user_identifier}"

    user_id = user.unique_id

    # 获取屏蔽数据
    block_data = await get_block_data(_ctx.chat_key)

    # 检查是否被屏蔽
    block_record = block_data.get_block(user_id)
    if not block_record:
        return f"ℹ️ 用户 {user.username} 当前没有被屏蔽"

    # 从系统移除屏蔽
    success = await remove_block_from_system(user_id, block_record.block_type)

    if not success:
        return f"❌ 解除用户 {user.username} 的屏蔽失败，请稍后重试"

    # 从插件数据移除
    block_data.remove_block(user_id)
    await save_block_data(_ctx.chat_key, block_data)

    core.logger.info(
        f"[屏蔽插件] AI在聊天 {_ctx.chat_key} 中解除了用户 {user.username}({user_id}) 的屏蔽",
    )
    return f"✅ 已解除用户 {user.username} 的屏蔽，他现在可以正常与我交互了"


@plugin.mount_sandbox_method(SandboxMethodType.AGENT, "查看已屏蔽用户列表")
async def list_blocked_users(_ctx: AgentCtx) -> str:
    """查看我当前屏蔽的用户列表

    当你想了解自己屏蔽了哪些用户时使用此功能，会返回详细的屏蔽信息。

    Returns:
        str: 已屏蔽用户的详细信息（包括用户名、屏蔽类型、剩余时间、屏蔽原因）
    """
    block_data = await get_block_data(_ctx.chat_key)

    # 清理过期的插件记录
    # 注意：系统层面的屏蔽会在到期时由DBUser自动解除，这里只是清理插件数据
    current_time = int(time.time())
    cleaned = block_data.cleanup_expired(current_time)
    if cleaned > 0:
        await save_block_data(_ctx.chat_key, block_data)
        core.logger.info(f"[屏蔽插件] 自动清理了 {cleaned} 个过期的屏蔽记录")

    # 获取有效屏蔽记录
    active_blocks = block_data.get_active_blocks(current_time)

    if not active_blocks:
        return "当前没有被屏蔽的用户"

    # 构建详细列表
    lines = ["当前已屏蔽的用户：\n"]
    for idx, (user_id, record) in enumerate(active_blocks.items(), 1):
        time_remaining = format_time_remaining(record.expire_time)
        block_desc = get_block_type_description(record.block_type)
        lines.append(
            f"{idx}. {record.username} ({user_id})\n"
            f"   - 屏蔽类型: {block_desc}\n"
            f"   - 剩余时间: {time_remaining}\n"
            f"   - 屏蔽原因: {record.reason}",
        )

    return "\n".join(lines)


@plugin.mount_prompt_inject_method("block_plugin_status")
async def inject_block_status_prompt(_ctx: AgentCtx) -> str:
    """注入屏蔽插件状态到提示词"""
    try:
        prompt_parts = []

        # 1. 注入插件配置状态
        config_lines = ["User Block Plugin Configuration:"]

        # 功能开关状态
        if config.ENABLE_PREVENT_TRIGGER:
            config_lines.append("  - Prevent Trigger Mode: Enabled")
        if config.ENABLE_FULL_BLOCK:
            config_lines.append("  - Full Block Mode: Enabled")

        # 永久屏蔽权限
        if config.ALLOW_PERMANENT_BLOCK:
            config_lines.append("  - Permanent Block: Allowed")
        else:
            config_lines.append("  - Permanent Block: Not Allowed (use time-limited blocks only)")

        # 时长限制
        max_hours = config.MAX_BLOCK_SECONDS // 3600
        default_hours = config.DEFAULT_BLOCK_SECONDS // 3600
        config_lines.append(f"  - Max Duration: {max_hours}h, Default: {default_hours}h")

        prompt_parts.append("\n".join(config_lines))

        # 2. 注入已屏蔽用户列表
        if config.SHOW_BLOCKED_USERS_IN_PROMPT:
            block_data = await get_block_data(_ctx.chat_key)

            # 清理过期的插件记录
            current_time = int(time.time())
            block_data.cleanup_expired(current_time)
            await save_block_data(_ctx.chat_key, block_data)

            # 获取有效屏蔽记录
            active_blocks = block_data.get_active_blocks(current_time)

            if active_blocks:
                # 限制显示数量
                display_count = min(len(active_blocks), config.MAX_PROMPT_DISPLAY_COUNT)
                display_blocks = list(active_blocks.items())[:display_count]

                # 构建屏蔽用户列表
                block_lines = ["Currently Blocked Users:"]
                for _user_id, record in display_blocks:
                    time_desc = "∞" if record.is_permanent else format_time_remaining(record.expire_time)
                    block_symbol = "🚫" if record.block_type == BlockType.FULL_BLOCK else "🔇"
                    block_lines.append(f"  {block_symbol} {record.username} ({time_desc}) - {record.reason}")

                if len(active_blocks) > display_count:
                    block_lines.append(f"  ... and {len(active_blocks) - display_count} more")

                prompt_parts.append("\n".join(block_lines))

        return "\n\n".join(prompt_parts) if prompt_parts else ""

    except Exception as e:
        core.logger.warning(f"[屏蔽插件] 提示词注入失败: {e}")
        return ""


@plugin.mount_cleanup_method()
async def cleanup():
    """清理方法"""
    core.logger.info("[屏蔽插件] 清理完成")
