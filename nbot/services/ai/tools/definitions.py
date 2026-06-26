"""工具定义 - 所有 AI 可调用的工具 JSON Schema 定义."""
from typing import List, Dict, Any

# 固定工具 API URL
MINIMAX_VLM_URL = "https://api.minimaxi.com/v1/coding_plan/vlm"

# ========== 内置工具定义 ==========
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "搜索最新新闻。当用户需要获取新闻资讯时使用此工具。可以指定新闻来源。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如'科技'、'体育'、'财经'等，默认为'热点新闻'"
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回的新闻数量，默认5条",
                        "default": 5
                    },
                    "source": {
                        "type": "string",
                        "description": "新闻来源，可选值：'all'(所有源，默认)、'36kr'(36氪-科技创业)、'ithome'(IT之家-科技数码)、'huxiu'(虎嗅-商业科技)、'sspai'(少数派-数码效率)",
                        "enum": ["all", "36kr", "ithome", "huxiu", "sspai"],
                        "default": "all"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气信息。当用户询问天气时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如'北京'、'上海'、'广州'等，默认'北京'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索网页内容。当需要查询网络信息时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "返回结果数量，默认3条",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_date_time",
            "description": "获取当前日期和时间信息。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "发送 HTTP GET 请求获取网页内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要访问的 URL 地址"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_memory",
            "description": "将重要信息保存到记忆管理系统。当用户要求记住某些信息、保存重要内容、记录关键事项时使用此工具。可以保存为长期记忆（永久保存）或短期记忆（自动过期）。记忆会自动关联到当前角色，不同角色的记忆相互隔离。记忆包含标题（简短概括）、摘要（内容要点）和完整内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "记忆的标题，简短概括记忆的主题，如'用户喜好'、'项目需求'、'重要日期'等"
                    },
                    "content": {
                        "type": "string",
                        "description": "要保存的完整记忆内容，详细描述需要记住的信息"
                    },
                    "summary": {
                        "type": "string",
                        "description": "内容摘要，简短描述内容的要点，方便快速回顾（如果不提供，系统会自动从content提取前100字作为摘要）"
                    },
                    "mem_type": {
                        "type": "string",
                        "description": "记忆类型：'long'表示长期记忆（永久保存），'short'表示短期记忆（会在一定时间后自动过期），默认为'long'",
                        "enum": ["long", "short"],
                        "default": "long"
                    },
                    "expire_days": {
                        "type": "integer",
                        "description": "如果是短期记忆，设置过期天数（默认7天），长期记忆可忽略此参数",
                        "default": 7
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "读取已保存的记忆内容。当用户询问之前记住的内容、查询保存的信息、确认记忆中的内容时使用此工具。只返回当前角色的记忆，不同角色的记忆相互隔离。返回的记忆包含标题、摘要和完整内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mem_type": {
                        "type": "string",
                        "description": "记忆类型筛选：'long'表示长期记忆，'short'表示短期记忆，不填则返回当前角色的所有记忆",
                        "enum": ["long", "short"]
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exec_command",
            "description": "执行命令行命令。白名单命令（如 ls, cat, echo 等）直接执行，非白名单命令系统会自动请求用户确认后执行。可通过 Web 管理界面启用或禁用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令行命令，如'ls -la'、'cat file.txt'、'python script.py'等"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "命令超时时间（秒），默认30秒",
                        "default": 30
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "download_file",
            "description": "从 URL 下载文件到工作区。当用户需要下载网络文件、保存图片、下载文档等时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "文件下载链接，如'https://example.com/file.pdf'"
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存的文件名（可选，默认从 URL 中提取）"
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": "工作区 ID（可选，默认使用当前会话的工作区）"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "在思考过程中向用户发送消息，不中断思考流程。当AI需要长时间处理时，可以使用此工具告知用户当前进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要发送给用户的消息内容"
                    },
                    "message_type": {
                        "type": "string",
                        "description": "消息类型：info(普通信息)/progress(进度通知)/warning(警告)/success(成功通知)",
                        "enum": ["info", "progress", "warning", "success"],
                        "default": "info"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_thinking_history",
            "description": "查询当前会话的历史思考记录（thinking_cards）。当需要了解之前使用了哪些工具、获得了什么结果时使用此工具。特别适用于长时间对话中，AI需要回顾之前操作的情况。此工具返回历史消息中的工具调用记录，包括工具名称、参数和完整结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回的历史记录数量限制，默认10条",
                        "default": 10
                    }
                }
            }
        }
    },
]

# ========== 工作区工具定义 ==========
WORKSPACE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "workspace_create_file",
            "description": "在工作区中创建或覆盖一个文件。适用于为用户生成代码、文档、配置文件等场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "文件名（支持子目录，如 'src/main.py'）"
                    },
                    "content": {
                        "type": "string",
                        "description": "文件的文本内容"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_read_file",
            "description": "读取工作区中的文件内容。用于查看用户上传的文件或之前创建的文件。支持按行范围或字符范围读取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要读取的文件名"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "开始行号（从1开始），与 end_line 配合使用可读取指定行范围。例如：start_line=10, end_line=20 表示读取第10到20行。"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "结束行号（包含），需要与 start_line 配合使用。例如：start_line=10, end_line=20 表示读取第10到20行。"
                    },
                    "char_count": {
                        "type": "integer",
                        "description": "读取的字符数量，从文件开头或 start_char 指定位置开始。与 start_char 配合可从任意位置读取指定长度。"
                    },
                    "start_char": {
                        "type": "integer",
                        "description": "从第几个字符开始读取（从0开始）。需要与 char_count 配合使用。例如：start_char=100, char_count=200 表示从第100个字符开始读取200个字符。"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_edit_file",
            "description": "修改工作区中已有文件的部分内容（查找并替换）。适用于修改代码、更新配置等场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要修改的文件名"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    },
                    "old_content": {
                        "type": "string",
                        "description": "要被替换的原始内容片段"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "替换后的新内容"
                    }
                },
                "required": ["filename", "old_content", "new_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_delete_file",
            "description": "删除工作区中的指定文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要删除的文件名"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_list_files",
            "description": "列出工作区中的所有文件。支持列出私有工作区和共享工作区的文件。支持递归列出子目录中的所有文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared", "all"],
                        "description": "工作区类型：'private' 仅列出当前会话私有工作区，'shared' 仅列出共享工作区，'all' 同时列出两者（默认）。"
                    },
                    "path": {
                        "type": "string",
                        "description": "要列出的子目录路径（可选）。例如：'docs' 或 'docs/src'。"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归列出所有子目录中的文件。默认为 false。设置为 true 时，会列出 path 下所有文件夹中的文件，并标注完整路径。"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_send_file",
            "description": "将工作区中的文件发送给用户。当用户需要下载或获取工作区中的文件时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要发送的文件名"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_parse_file",
            "description": "解析工作区中的文件内容。支持 PDF、DOCX、PPT、Excel、代码文件等。自动识别文件类型并提取文本内容。适用于需要理解文档内容的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要解析的文件名"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "最大提取字符数，默认为 50000。避免返回过长内容。",
                        "default": 50000
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_file_info",
            "description": "获取工作区中文件的元数据信息（不解析内容）。返回文件类型、大小、页数/工作表数等基本信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要查询的文件名"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_skill_copy",
            "description": "将指定的 Skill 或 Skill 下的文件复制到工作区。适用于需要将 Skill 代码保存到工作区进行编辑或构建的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "description": "要复制的 Skill ID（如 'search'、'image_search'）"
                    },
                    "filename": {
                        "type": "string",
                        "description": "可选，要复制的 Skill 下的具体文件名。如不指定则复制整个 Skill。"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["private", "shared"],
                        "description": "复制到的工作区类型：'private' 表示当前会话私有工作区，'shared' 表示所有会话共享工作区。默认 'private'。"
                    }
                },
                "required": ["skill_id"]
            }
        }
    }
]
