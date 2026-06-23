# /jm 上传失败修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `/jm <漫画ID>` 命令在 PDF 生成后不自动上传文件的 bug，提升可观察性和可恢复性。

**Architecture:** 单文件修改 `nbot/commands.py`。三处修改：(1) `handle_jmcomic` 用 `asyncio.create_task` 替代 `asyncio.gather` 让任务真正异步；(2) `download_and_send_comic` 加 `_log` 让每个关键步骤可观察；(3) jm_send 关闭时给用户文件路径和重发指引，上传 API 失败时独立记录错误。

**Tech Stack:** Python 3.13, asyncio, ncatbot (现有依赖), jmcomic (现有依赖), pikepdf (现有依赖)

## Global Constraints

- 仅修改 `nbot/commands.py`（spec §"关键文件"）
- 不修改 SwitchManager 逻辑（spec §"非目标"）
- 不重构为独立类（YAGNI，spec §"非目标"）
- 现有 `/jm` 命令的 help_text、category、admin_show 不变（保持命令注册兼容性）
- 修改后 `switches.json` 格式不变
- 所有 `_log` 调用使用现有 `_log = get_log()` 实例
- 文件路径处理仍使用 `normalize_file_path()` 和 `load_address()` 现有工具

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `nbot/commands.py` | Modify | `/jm` 命令入口 `handle_jmcomic` + 后台任务 `download_and_send_comic` |

无需新增文件。无需创建测试文件（项目无单元测试基础设施，端到端验证通过重启 Bot + 实际发送 `/jm` 命令完成）。

---

### Task 1: 修改 `handle_jmcomic` 使用 `asyncio.create_task`

**Files:**
- Modify: `nbot/commands.py:1190-1198`

**Step 1: 定位待修改代码块**

打开 `nbot/commands.py`，跳到 line 1190-1198，找到以下代码：

```python
        # 创建后台任务
        try:
            await asyncio.gather(download_and_send_comic(comic_id, msg, is_group))
        except Exception as e:
            error_msg = f"下载漫画失败喵~: {str(e)}"
            if is_group:
                await msg.reply(text=error_msg)
            else:
                await bot.api.post_private_msg(msg.user_id, text=error_msg)
```

**Step 2: 替换为新代码**

将上面 9 行代码替换为以下 2 行：

```python
        # 创建真正的后台任务（不再 await，handle_jmcomic 立即返回）
        task = asyncio.create_task(download_and_send_comic(comic_id, msg, is_group))
        _log.info(f"[jm] 已创建后台任务下载漫画 {comic_id}, task={task}")
```

**注意**：外层 `try/except` 被删除——因为我们不再 `await`，task 内的异常会作为未捕获异常由 asyncio 记录（这正是我们想要的可观察性）。`handle_jmcomic` 现在立即返回，不会阻塞。

**Step 3: 验证语法**

```bash
python3 -c "import ast; ast.parse(open('nbot/commands.py').read())"
```

期望输出：无（语法正确）。如果报错，检查 line 1190-1198 的缩进是否正确（应为 8 空格缩进，与 `match:` 同级）。

**Step 4: Commit**

```bash
git add nbot/commands.py
git commit -m "refactor(jm): use asyncio.create_task for true background download"
```

---

### Task 2: 在 `download_and_send_comic` 入口和下载完成后加日志

**Files:**
- Modify: `nbot/commands.py:1206-1221`

**Step 1: 定位待修改代码块**

在 `nbot/commands.py` 找到 `download_and_send_comic` 函数（line 1206 开头），定位到以下代码：

```python
async def download_and_send_comic(comic_id, msg, is_group):
    try:
        # 在线程池中执行阻塞操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda:
            jmcomic.download_album(
                comic_id,
                jmcomic.create_option_by_file('./resources/config/option.yml')
            )
        )

        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))

        # 检查文件是否真正生成
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF文件未生成：{file_path}")
```

**Step 2: 在函数入口加日志**

在 `async def download_and_send_comic(comic_id, msg, is_group):` 后**第一行**（`try:` 之前）添加：

```python
    _log.info(f"[jm] 开始下载漫画 {comic_id}, is_group={is_group}, user={msg.user_id}, group={msg.group_id}")
```

修改后函数开头应为：

```python
async def download_and_send_comic(comic_id, msg, is_group):
    _log.info(f"[jm] 开始下载漫画 {comic_id}, is_group={is_group}, user={msg.user_id}, group={msg.group_id}")
    try:
        # 在线程池中执行阻塞操作
        ...
```

**Step 3: 在下载完成后加日志**

在 `await loop.run_in_executor(...)` 块**之后**、`file_path = ...` 之前，添加：

```python
        _log.info(f"[jm] jmcomic.download_album 完成: {comic_id}")
```

**Step 4: 在 PDF 文件检查后加日志**

定位到：

```python
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF文件未生成：{file_path}")
```

将 `raise` 之后、`encrypt_needed = ...` 之前，添加：

```python
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        _log.info(f"[jm] PDF 文件已生成: {file_path}, 大小={file_size_mb:.2f}MB")
```

注意：`file_size_mb` 变量需要在后续任务中复用（上传分支需要），所以这里先创建。

**Step 5: 验证语法**

```bash
python3 -c "import ast; ast.parse(open('nbot/commands.py').read())"
```

期望输出：无。

**Step 6: Commit**

```bash
git add nbot/commands.py
git commit -m "feat(jm): add logging to download_and_send_comic"
```

---

### Task 3: 改造 jm_send 关闭时的行为（添加文件路径和重发提示）

**Files:**
- Modify: `nbot/commands.py:1245-1259`

**Step 1: 定位待修改代码块**

在 `nbot/commands.py` 找到以下代码（line 1245-1259）：

```python
        if not switch.get_switch_state('jm_send', group_id=str(msg.group_id) if is_group else None,user_id=str(msg.user_id) if not is_group else None):
            text = "漫画已下载，但发送已关闭喵~"
            if email_sent:
                text = "漫画已下载，并已发送到你的邮箱喵~"
            elif email_error is not None:
                err_msg = str(email_error)
                if "552" in err_msg or "mailsize limit" in err_msg.lower():
                    text = "漫画已下载，但发送到邮箱失败喵~，原因是邮件大小超过邮箱限制喵~"
                else:
                    text = "漫画已下载，但发送到邮箱失败喵~，请检查邮箱配置或稍后重试喵~"
            if is_group:
                await msg.reply(text=text)
            else:
                await bot.api.post_private_msg(msg.user_id, text=text)
            return
```

**Step 2: 替换为新代码**

将上面 15 行代码替换为：

```python
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
            if email_sent:
                text = f"漫画已下载，并已发送到你的邮箱喵~（文件 {file_size_mb:.2f}MB）"
            elif email_error is not None:
                err_msg = str(email_error)
                if "552" in err_msg or "mailsize limit" in err_msg.lower():
                    text = f"漫画已下载，但发送到邮箱失败喵~，原因是邮件大小超过邮箱限制喵~（文件 {file_size_mb:.2f}MB 已保留）"
                else:
                    text = f"漫画已下载，但发送到邮箱失败喵~，请检查邮箱配置或稍后重试喵~（文件 {file_size_mb:.2f}MB 已保留）"
            if is_group:
                await msg.reply(text=text)
            else:
                await bot.api.post_private_msg(msg.user_id, text=text)
            return
```

**注意**：
- `file_size_mb` 是 Task 2 中创建并填充的变量
- 保留了原有的 `email_sent` / `email_error` 优先级（这些变量在更早的代码中定义）
- 改进了所有三种情况下的提示文本，包含文件大小信息

**Step 3: 验证语法**

```bash
python3 -c "import ast; ast.parse(open('nbot/commands.py').read())"
```

期望输出：无。

**Step 4: Commit**

```bash
git add nbot/commands.py
git commit -m "feat(jm): improve jm_send off message with file path and retry hint"
```

---

### Task 4: 为上传 API 调用添加独立 try/except 和日志

**Files:**
- Modify: `nbot/commands.py:1265-1280`

**Step 1: 定位待修改代码块**

在 `nbot/commands.py` 找到以下代码（line 1265-1280，`Task 3` 修改后的位置）：

```python
        if is_group:
            if switch.get_switch_state('jm_send_user', group_id=str(msg.group_id)):
                await bot.api.post_private_msg(msg.user_id, text=file_text)
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
                await bot.api.post_private_msg(msg.user_id, text=success_text)
            else:
                await msg.reply(text=file_text)
                await bot.api.post_group_file(msg.group_id, file=file_path)
                await msg.reply(text=success_text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=file_text)
            await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
            await bot.api.post_private_msg(msg.user_id, text=success_text)
```

**Step 2: 替换为新代码**

将上面 13 行代码替换为：

```python
        if is_group:
            if switch.get_switch_state('jm_send_user', group_id=str(msg.group_id)):
                await bot.api.post_private_msg(msg.user_id, text=file_text)
                try:
                    await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
                    _log.info(f"[jm] upload_private_file 成功: {file_path} → user {msg.user_id}")
                except Exception as e:
                    _log.error(f"[jm] upload_private_file 失败: {e}", exc_info=True)
                    raise
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
```

**注意**：
- 所有三个上传 API 调用点（群聊私信、群聊群文件、私聊私信）都包裹了 try/except
- 失败时 `_log.error` 记录完整堆栈，然后 `raise` 让外层 except 处理
- 成功时 `_log.info` 记录上传目标和文件路径

**Step 3: 验证语法**

```bash
python3 -c "import ast; ast.parse(open('nbot/commands.py').read())"
```

期望输出：无。

**Step 4: Commit**

```bash
git add nbot/commands.py
git commit -m "feat(jm): add independent try/except and logging to upload API calls"
```

---

### Task 5: 在外层 except 添加完整异常日志

**Files:**
- Modify: `nbot/commands.py:1280-1295`

**Step 1: 定位待修改代码块**

在 `nbot/commands.py` 找到以下代码（line 1280 附近，`download_and_send_comic` 的外层 except 分支）：

```python
    except Exception as e:
        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))
        error_msg = f"下载失败喵~: {str(e)}"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
            file_text = f"文件大小：{file_size:.2f} MB，正在上传喵~"
            if is_group:
                await msg.reply(text="部分下载失败了喵~，正在发送剩余的文件喵~\n"+file_text)
                await bot.api.post_group_file(msg.group_id, file=file_path)
            else:
                await bot.api.post_private_msg(msg.user_id, text="部分下载失败了喵~，正在发送剩余的文件喵~\n"+file_text)
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
```

**Step 2: 在 except 块开头加日志**

在 `except Exception as e:` 后**第一行**（`file_path = ...` 之前）添加：

```python
        _log.error(f"[jm] download_and_send_comic 异常: comic_id={comic_id}, error={e}", exc_info=True)
```

修改后 except 块开头应为：

```python
    except Exception as e:
        _log.error(f"[jm] download_and_send_comic 异常: comic_id={comic_id}, error={e}", exc_info=True)
        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))
        error_msg = f"下载失败喵~: {str(e)}"
        ...
```

**Step 3: 验证语法**

```bash
python3 -c "import ast; ast.parse(open('nbot/commands.py').read())"
```

期望输出：无。

**Step 4: Commit**

```bash
git add nbot/commands.py
git commit -m "feat(jm): log full exception in download_and_send_comic except block"
```

---

### Task 6: 端到端验证

**Files:** 无（验证任务）

**Step 1: 重启 Bot**

停止当前运行的 Bot 进程（如果正在运行），然后启动：

```bash
cd /Users/feewee009/myCode/nekobot
# 假设使用原有的启动方式，例如：
python3 bot.py
```

期望输出：Bot 正常启动并连接 NapCat。

**Step 2: 测试 PDF 已存在分支（群聊 1103022698）**

在群 1103022698 发送：
```
/jm 1447589
```

期望：
- 用户立即收到"已开始下载漫画ID：1447589，下载完成后会自动通知喵~"消息
- 因为 PDF 已存在，应自动进入"已存在"分支（line 1132-1151），不需要后台任务
- 群聊收到 "该漫画已存在喵~..." 消息和 PDF 文件

**Step 3: 测试 PDF 已存在分支（私聊）**

私聊 Bot 发送：
```
/jm 1447589
```

期望：
- 用户立即收到"已开始下载漫画ID：1447589..."消息
- 私聊收到 "该漫画已存在喵~..." 消息和 PDF 文件

**Step 4: 检查日志**

```bash
ls -lt /Users/feewee009/myCode/nekobot/logs/bot_*.log | head -1
```

取出最新日志，搜索 jm 相关条目：

```bash
LOG=$(ls -t /Users/feewee009/myCode/nekobot/logs/bot_*.log | head -1)
grep "\[jm\]" "$LOG" | tail -20
```

期望：能看到 `[jm] 已创建后台任务下载漫画` 之类的日志条目（如果走后台任务）或普通的命令处理日志（如果走已存在分支）。

**Step 5: 测试 jm_send 关闭时的新提示（群聊）**

让管理员在群 1103022698 执行：
```
/jm_send off
```

期望：收到"群组发送漫画已 关闭 喵~"。

然后在群发送：
```
/jm 1447589
```

期望：用户收到"已开始下载..."消息。然后约几秒后收到：

```
漫画已下载，但发送已关闭喵~
文件：1447589.pdf (86.37MB) 已保留
需要发送请让管理员执行 /jm_send on 后重新触发
```

注意：实际文件大小可能不同（取决于 `cache/pdf/1447589.pdf` 实际大小）。

**Step 6: 恢复 jm_send**

让管理员执行：
```
/jm_send on
```

期望：收到"群组发送漫画已 开启 喵~"。

**Step 7: 提交验证完成记录**

无代码修改。在 plan 文件中追加验证结果（手动添加或作为 PR 描述）：

```markdown
## 验证结果
- [x] 群聊 /jm <已存在 PDF> 正常上传
- [x] 私聊 /jm <已存在 PDF> 正常上传
- [x] jm_send 关闭时显示新提示
- [x] 日志中包含 [jm] 前缀的记录
```

**Step 8: 验证完成 Commit（如有文档修改）**

```bash
git add docs/superpowers/plans/2026-06-23-jm-upload-fix.md
git commit -m "docs(plan): mark jm upload fix verification complete"
```

如果 plan 文件无修改，跳过此步。

---

## Self-Review

**1. Spec coverage:**
- §缺陷 1 (asyncio.gather) → Task 1
- §缺陷 2 (无日志) → Task 2 + Task 4 + Task 5
- §缺陷 3 (jm_send 不友好) → Task 3
- §缺陷 4 (上传无错误处理) → Task 4
- §错误处理矩阵 → Task 3 (jm_send off 行) + Task 4 (上传失败行)
- §验证方案 → Task 6

无 gap。

**2. Placeholder scan:** 无 "TBD" / "TODO" / "类似 Task N"。所有代码块都完整。

**3. Type consistency:**
- `file_size_mb` 在 Task 2 中创建，在 Task 3、Task 4 中复用 ✓
- `comic_id` 在所有 Task 中使用，作为 `download_and_send_comic` 的参数 ✓
- `msg`, `is_group` 在所有 Task 中作为参数传递 ✓
- `bot.api.post_group_file` / `bot.api.upload_private_file` 调用与现有 ncatbot API 签名一致 ✓
- `switch.get_switch_state('jm_send', group_id=..., user_id=...)` 调用与现有 SwitchManager.get_switch_state 签名一致 ✓

无类型不一致。
