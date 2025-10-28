"""插件配置和元数据"""

from pydantic import Field

from nekro_agent.api.plugin import ConfigBase, NekroPlugin

# 创建插件实例
plugin = NekroPlugin(
    name="用户屏蔽管理",
    module_name="nekro_plugin_block",
    description="AI主动屏蔽用户的插件，支持禁止触发和完全屏蔽两种模式",
    version="1.0.0",
    author="NekroAgent",
    url="https://github.com/KroMiose/nekro-agent",
    support_adapter=[],
)


@plugin.mount_config()
class BlockConfig(ConfigBase):
    """用户屏蔽配置"""

    ENABLE_PREVENT_TRIGGER: bool = Field(
        default=True,
        title="启用禁止触发功能",
        description="允许AI使用'禁止触发'模式屏蔽用户（用户消息仍可见但无法直接唤醒AI）",
    )

    ENABLE_FULL_BLOCK: bool = Field(
        default=True,
        title="启用完全屏蔽功能",
        description="允许AI使用'完全屏蔽'模式屏蔽用户（完全看不到该用户的消息）",
    )

    MAX_BLOCK_SECONDS: int = Field(
        default=259200,
        title="最大屏蔽时长（秒）",
        description="单次屏蔽的最大时长限制（秒），0表示无限制。默认259200秒=72小时",
        ge=0,
        le=2592000,
    )

    DEFAULT_BLOCK_SECONDS: int = Field(
        default=86400,
        title="默认屏蔽时长（秒）",
        description="当AI未指定屏蔽时长时使用的默认值（秒）。默认86400秒=24小时",
        ge=60,
        le=604800,
    )

    ALLOW_PERMANENT_BLOCK: bool = Field(
        default=False,
        title="允许永久屏蔽",
        description="允许AI设置永久屏蔽（不会自动解除）",
    )

    SHOW_BLOCKED_USERS_IN_PROMPT: bool = Field(
        default=True,
        title="在提示词中显示屏蔽用户",
        description="将当前屏蔽的用户列表注入到AI的系统提示词中",
    )

    MAX_PROMPT_DISPLAY_COUNT: int = Field(
        default=5,
        title="提示词中最多显示用户数",
        description="在系统提示词中最多显示多少个被屏蔽的用户",
        ge=1,
        le=20,
    )


# 获取配置实例
config: BlockConfig = plugin.get_config(BlockConfig)

