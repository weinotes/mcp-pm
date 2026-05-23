"""Language support for mcp-pm Web UI.

Multi-language support with English (default) and Chinese (zh-CN).
New languages can be added by extending TRANSLATIONS with more keys.
"""

from __future__ import annotations

import contextvars

# Current language - set per-request via middleware
current_lang: contextvars.ContextVar[str] = contextvars.ContextVar("current_lang", default="en")

# All translations: lang_code -> { english_key: translated_text }
ALL_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {},  # English is identity - _() returns the key itself
    "zh-CN": {
        "mcp-pm Dashboard": "mcp-pm 控制面板",
        "Dashboard": "控制面板",
        "Servers": "服务器",
        "Config": "配置",
        "Logs": "日志",
        "Install": "安装",
        "Overview of your MCP server ecosystem": "MCP 服务器生态系统概览",
        "Install New Server": "安装新服务器",
        "Refresh": "刷新",
        "Installed Servers": "已安装服务器",
        "View all →": "查看全部 →",
        "Tools": "工具",
        "Online": "在线",
        "Uptime": "运行时长",
        "Since last restart": "自上次重启",
        "No Servers Installed": "暂无已安装服务器",
        "Get started by installing your first MCP server.": "马上安装你的第一个 MCP 服务器。",
        "Browse Registry": "浏览注册中心",
        "Quick Actions": "快捷操作",
        "Install a Server": "安装服务器",
        "Browse or search the MCP registry": "浏览或搜索 MCP 注册中心",
        "Edit Configuration": "编辑配置",
        "View and edit config.yaml": "查看和编辑 config.yaml",
        "View Logs": "查看日志",
        "Monitor real-time server activity": "实时监控服务器活动",
        "System Info": "系统信息",
        "Version": "版本",
        "Total Tools": "工具总数",
        "Config Path": "配置路径",
        "Configuration": "配置",
        "View and edit mcp-pm configuration": "查看和编辑 mcp-pm 配置",
        "config.yaml": "config.yaml",
        "Save": "保存",
        "Import Configuration": "导入配置",
        "Upload & Apply": "上传并应用",
        "Config Keys": "配置键值",
        "Key": "键",
        "Value": "值",
        "null": "无",
        "Install Server": "安装服务器",
        "Discover and install MCP servers from the registry": "从注册中心发现并安装 MCP 服务器",
        "Search": "搜索",
        "Popular Servers": "热门服务器",
        "Manual Install": "手动安装",
        "Source URL": "来源地址",
        "Source Type": "来源类型",
        "Auto-detect": "自动检测",
        "Git": "Git",
        "Pip": "Pip",
        "NPM": "NPM",
        "Docker": "Docker",
        "Custom Name (optional)": "自定义名称（可选）",
        "Real-time server activity log": "服务器实时活动日志",
        "Waiting for log entries...": "等待日志条目...",
        "Manage all installed MCP servers": "管理所有已安装的 MCP 服务器",
        "Status": "状态",
        "Name": "名称",
        "Type": "类型",
        "Source": "来源",
        "Actions": "操作",
        "Description": "描述",
        "Required": "必需",
        "required": "必需",
        "optional": "可选",
        "No parameters": "无参数",
        "No tools discovered for this server, or server not running.": "未发现该服务器的工具，或服务器未运行。",
        "Back to Servers": "返回服务器列表",
        "← Back to Servers": "← 返回服务器列表",
        "Parameters": "参数",
        "Test Tool": "测试工具",
        "to test this tool.": "来测试此工具。",
        "Run": "运行",
        "All Systems Go": "一切正常",
        "server(s) contributing": "个服务器贡献中",
        "tools": "个工具",
        "Restart": "重启",
        "No description": "暂无描述",
        "Format JSON": "格式化 JSON",
        "Language": "语言",
        "English": "English",
        "中文": "中文",
    },
}

# Language display names
LANG_NAMES: dict[str, str] = {
    "en": "English",
    "zh-CN": "中文",
}


def _(text: str) -> str:
    """Translate text to the current language.

    Usage in Jinja2 templates: {{ _("Dashboard") }}
    Falls back to English (the key itself) if no translation exists.
    """
    lang = current_lang.get()
    if lang == "en" or lang not in ALL_TRANSLATIONS:
        return text
    return ALL_TRANSLATIONS[lang].get(text, text)


def set_language(lang: str) -> None:
    """Set the current language for this request context."""
    if lang in ALL_TRANSLATIONS:
        current_lang.set(lang)
    else:
        current_lang.set("en")


def get_language() -> str:
    """Get the current language code."""
    return current_lang.get()


def get_language_name(lang: str | None = None) -> str:
    """Get the display name for a language code."""
    return LANG_NAMES.get(lang or get_language(), lang or "en")
