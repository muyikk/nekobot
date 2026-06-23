# /jm 命令上传失败修复设计

**日期**: 2026-06-23
**状态**: 已批准，待实施
**作者**: NekoBot 维护者

## 背景

用户报告 `/jm <漫画ID>` 命令存在 bug：jmcomic 下载并合并 PDF 完成后（`cache/pdf/<id>.pdf` 存在），机器人没有把文件上传到群/私聊，而是向用户回复了"漫画已下载，但发送已关闭喵~"。

经静态分析 `nbot/commands.py` 中 `handle_jmcomic` 和 `download_and_send_comic`，发现以下真实代码缺陷：

### 缺陷 1：`asyncio.gather` 被误用为后台任务

`handle_jmcomic` 在 line 1192 使用了：
```python
await asyncio.gather(download_and_send_comic(comic_id, msg, is_group))
```

`asyncio.gather` 会**同步等待**所有传入的 coroutine 完成。注释 "创建后台任务" 误导开发者。这导致：
- 整个下载+上传流程会阻塞 `handle_jmcomic`
- 一旦中途中断（如 Bot 重启、网络断开），用户命令的"上下文"丢失
- 异常只会被外层 `try/except` 笼统捕获

### 缺陷 2：`download_and_send_comic` 没有任何日志

整个函数（line 1206-1295）没有任何 `_log.info/debug/warning` 调用。这导致：
- 一旦上传失败，问题无法排查
- 只能依赖 jmcomic 自己的日志和 ncatbot 的 API 错误信息
- 用户看到"已下载但未上传"时，无法判断是 jm_send 关闭、上传 API 失败、还是其他原因

### 缺陷 3：`jm_send` 关闭时的行为不友好

line 1245-1259 中，如果 `jm_send` 关闭，函数会**静默 return** 且只告诉用户"漫画已下载，但发送已关闭喵~"，没有：
- 告知文件实际保存在哪里
- 告知如何开启 jm_send
- 告知如何重新触发上传

### 缺陷 4：上传 API 调用没有独立错误处理

line 1267-1277 中 `bot.api.post_group_file` / `upload_private_file` 调用没有 try/except。如果上传失败，会被外层 except 笼统捕获并按"部分下载失败"处理，掩盖了真实错误（上传 API 失败而非下载失败）。

## 目标

修复以上四个缺陷，让 `/jm` 命令：
1. **可观察**：每个关键步骤都有日志
2. **可靠**：jm_send 开关被异常/状态污染时不会阻断上传
3. **可恢复**：jm_send 关闭时给用户明确指引（文件位置、如何重发）
4. **健壮**：上传失败有独立的错误处理和日志

非目标：
- 不重构 `download_and_send_comic` 为独立类（YAGNI）
- 不修改 jmcomic 集成方式
- 不调整 SwitchManager 逻辑

## 方案概述

采用**方案 B：防御式重构**，仅修改 `nbot/commands.py`：

### 修改 1：`handle_jmcomic` (line 1190-1198)

将 `await asyncio.gather(...)` 改为 `asyncio.create_task(...)`，让 `download_and_send_comic` 真正成为后台任务。

```python
# 旧
try:
    await asyncio.gather(download_and_send_comic(comic_id, msg, is_group))
except Exception as e:
    error_msg = f"下载漫画失败喵~: {str(e)}"
    if is_group:
        await msg.reply(text=error_msg)
    else:
        await bot.api.post_private_msg(msg.user_id, text=error_msg)

# 新
task = asyncio.create_task(download_and_send_comic(comic_id, msg, is_group))
_log.info(f"已创建后台任务下载漫画 {comic_id}, task={task}")
# handle_jmcomic 立即返回；下载/上传中的异常由 asyncio 记录
```

### 修改 2：`download_and_send_comic` (line 1206-1295)

在关键步骤添加 `_log` 调用，并将 jm_send 关闭时的"静默 return"改为"提示用户 + 给出文件路径"。

```python
async def download_and_send_comic(comic_id, msg, is_group):
    _log.info(f"[jm] 开始下载漫画 {comic_id}, is_group={is_group}, user={msg.user_id}, group={msg.group_id}")
    try:
        # ... 现有下载逻辑 ...

        # 文件路径检查
        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF文件未生成：{file_path}")
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        _log.info(f"[jm] PDF 文件已生成: {file_path}, 大小={file_size_mb:.2f}MB")

        # ... 现有加密、邮件逻辑 ...

        # jm_send 检查 [CHANGED]
        jm_send_on = switch.get_switch_state(
            'jm_send',
            group_id=str(msg.group_id) if is_group else None,
            user_id=str(msg.user_id) if not is_group else None,
        )
        _log.info(f"[jm] jm_send 状态: {jm_send_on}, comic_id={comic_id}")
        if not jm_send_on:
            _log.warning(f"[jm] jm_send 关闭，跳过上传 {comic_id}。文件保留在: {file_path}")
            text = (
                f"漫画已下载，但发送已关闭喵~\n"
                f"文件：{comic_id}.pdf ({file_size_mb:.2f}MB) 已保留\n"
                f"需要发送请让管理员执行 /jm_send on 后重新触发"
            )
            if is_group:
                await msg.reply(text=text)
            else:
                await bot.api.post_private_msg(msg.user_id, text=text)
            return

        # 上传 [CHANGED: 独立 try/except + 日志]
        file_text = f"文件大小：{file_size_mb:.2f} MB，正在上传喵~"
        success_text = f"漫画 {comic_id} 下载完成喵~"

        if is_group:
            if switch.get_switch_state('jm_send_user', group_id=str(msg.group_id)):
                await bot.api.post_private_msg(msg.user_id, text=file_text)
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
                await bot.api.post_private_msg(msg.user_id, text=success_text)
            else:
                await msg.reply(text=file_text)
                try:
                    await bot.api.post_group_file(msg.group_id, file=file_path)
                    _log.info(f"[jm] post_group_file 成功: {file_path} → group {msg.group_id}")
                except Exception as e:
                    _log.error(f"[jm] post_group_file 失败: {e}", exc_info=True)
                    raise
                await msg.reply(text=success_text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=file_text)
            try:
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
                _log.info(f"[jm] upload_private_file 成功: {file_path} → user {msg.user_id}")
            except Exception as e:
                _log.error(f"[jm] upload_private_file 失败: {e}", exc_info=True)
                raise
            await bot.api.post_private_msg(msg.user_id, text=success_text)

    except Exception as e:
        _log.error(f"[jm] download_and_send_comic 异常: comic_id={comic_id}, error={e}", exc_info=True)
        # 保留原有错误处理逻辑（line 1279-1294）
        ...
```

## 错误处理矩阵

| 场景 | 旧行为 | 新行为 |
|------|--------|--------|
| 下载失败 | _log 未记录；外层 except 笼统捕获 | _log.error 记录完整堆栈 |
| PDF 未生成 | raise FileNotFoundError；外层 except | raise + _log.error 记录路径 |
| 加密失败 | 仅 ImportError 提示；其他异常被外层捕获 | 同上，但外层有 _log 记录 |
| 邮件失败 | _log.error + email_error 变量 | 保持不变 |
| jm_send 关闭 | "漫画已下载，但发送已关闭喵~" | 文件路径 + 开启提示 |
| post_group_file 失败 | 被外层 except 捕获，提示"部分下载失败" | 独立 try/except，_log.error 记录 + 外层 except |
| upload_private_file 失败 | 同上 | 同上 |
| asyncio.create_task 抛出 | 不存在（旧版 await gather） | 未捕获的 task exception 由 asyncio 记录 |

## 关键文件

- `nbot/commands.py` — 唯一修改文件
  - `handle_jmcomic` (line 1106-1204) — 改 `asyncio.gather` 为 `create_task`
  - `download_and_send_comic` (line 1206-1295) — 加日志 + 改 jm_send 分支 + 独立 try/except 上传

## 验证方案

### 单元式验证

```python
# REPL 验证
import importlib
import nbot.commands as cmds
importlib.reload(cmds)

# 模拟开关状态
cmds.switch.group_switches = {}  # 清理以确保使用默认
cmds.switch.user_switches = {}

# 验证 jm_send 默认值
assert cmds.switch.get_switch_state('jm_send') == True
```

### 端到端验证

1. **重启 Bot**，让新代码生效
2. **群聊场景**（群 1103022698）：
   - 发 `/jm 1447589`（PDF 已存在）→ 走"已存在"分支立即上传
   - 发 `/jm <不存在的 ID>` → 应看到 `[jm] 开始下载` 和 `未找到漫画` 错误
3. **私聊场景**：
   - 发 `/jm 1447589` → 走"已存在"分支立即上传
4. **日志验证**：检查 `logs/bot_*.log` 中是否包含 `[jm]` 前缀的日志记录
5. **回归验证**：
   - 私聊和群聊都正常
   - jm_send OFF 时显示新提示文本
   - PDF 已存在分支行为不变

### 回归测试清单

- [ ] 群聊 `/jm <已存在 PDF>` 正常上传
- [ ] 群聊 `/jm <新 PDF>` 下载完成后正常上传
- [ ] 私聊 `/jm <已存在 PDF>` 正常上传
- [ ] 私聊 `/jm <新 PDF>` 下载完成后正常上传
- [ ] jm_send 关闭时显示新提示
- [ ] jm_send_user 开启时私聊用户能收到文件
- [ ] 上传 API 失败时有错误日志

## 实施范围

预估修改：
- `handle_jmcomic`: 4 行 → 5 行（+1 行 create_task + log）
- `download_and_send_comic`: ~85 行 → ~110 行（+25 行日志和错误处理）

总修改：~30 行新增，无删除现有功能。
