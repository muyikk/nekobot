"""角色卡导入导出与立绘管理路由。"""
import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime

from flask import jsonify, request, send_file

from nbot.utils.logger import get_logger
from .compile import compile_personality_prompt

_log = get_logger(__name__)

# 允许的图片扩展名
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def register_io_routes(app, server):
    @app.route("/api/personality/import", methods=["POST"])
    def import_personality():
        """导入角色卡，支持 ZIP 和 JSON 格式"""
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "文件名为空"}), 400

        try:
            filename = file.filename.lower()
            character = None
            portrait_file = None

            # 判断文件类型
            if filename.endswith('.zip'):
                # 处理 ZIP 文件
                zip_data = io.BytesIO(file.read())
                with zipfile.ZipFile(zip_data, 'r') as zf:
                    # 查找 character.json
                    json_file = None
                    for name in zf.namelist():
                        if name.lower() == 'character.json':
                            json_file = name
                            break

                    if not json_file:
                        return jsonify({"success": False, "error": "ZIP 文件中未找到 character.json"}), 400

                    # 读取 JSON
                    character = json.loads(zf.read(json_file).decode('utf-8'))

                    # 查找立绘图片
                    for name in zf.namelist():
                        if name.lower().startswith('portrait.'):
                            portrait_file = zf.read(name)
                            portrait_ext = os.path.splitext(name)[1]
                            break

            elif filename.endswith('.json'):
                # 处理 JSON 文件
                content = file.read().decode("utf-8")
                character = json.loads(content)
            else:
                return jsonify({"success": False, "error": "不支持的文件格式，请上传 .json 或 .zip 文件"}), 400

            # 验证基本字段
            if not character.get("name"):
                return jsonify({"success": False, "error": "角色卡缺少 name 字段"}), 400

            # 如果有立绘图片，上传到服务器
            if portrait_file:
                try:
                    # 创建上传目录
                    upload_dir = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits")
                    os.makedirs(upload_dir, exist_ok=True)

                    # 生成唯一文件名
                    filename = f"portrait_{uuid.uuid4().hex[:16]}{portrait_ext}"
                    filepath = os.path.join(upload_dir, filename)

                    # 保存文件
                    with open(filepath, 'wb') as f:
                        f.write(portrait_file)

                    # 设置立绘 URL
                    character['portrait'] = f"/static/uploads/portraits/{filename}"
                    _log.info(f"立绘导入成功: {filepath}")
                except Exception as e:
                    _log.error(f"立绘导入失败: {e}")
                    # 立绘导入失败不影响整体导入
                    character.setdefault('portrait', '')

            # 填充缺失字段
            character.setdefault("description", "")
            character.setdefault("avatar", "fas fa-user-circle")
            character.setdefault("tags", [])
            character.setdefault("basicInfo", "")
            character.setdefault("personality", "")
            character.setdefault("scenario", "")
            character.setdefault("firstMessage", "")
            character.setdefault("exampleDialogues", "")
            character.setdefault("responseFormat", "")
            character.setdefault("rules", [])
            character.setdefault("state", {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"})
            if not character.get("systemPrompt"):
                character["systemPrompt"] = compile_personality_prompt(character)

            return jsonify({"success": True, "character": character})

        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "文件不是有效的 JSON 格式"}), 400
        except UnicodeDecodeError:
            return jsonify({"success": False, "error": "文件编码不支持，请使用 UTF-8"}), 400
        except zipfile.BadZipFile:
            return jsonify({"success": False, "error": "ZIP 文件损坏或格式不正确"}), 400
        except Exception as e:
            _log.error(f"导入角色卡失败: {e}")
            return jsonify({"success": False, "error": f"导入失败: {str(e)}"}), 500

    @app.route("/api/personality/portrait", methods=["POST"])
    def upload_personality_portrait():
        """上传角色立绘图片，返回图片URL"""
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "文件名为空"}), 400

        if not allowed_image_file(file.filename):
            return jsonify({"success": False, "error": "不支持的文件格式，请上传图片文件"}), 400

        try:
            # 创建上传目录
            upload_dir = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits")
            os.makedirs(upload_dir, exist_ok=True)

            # 生成唯一文件名
            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"portrait_{uuid.uuid4().hex[:16]}.{ext}"
            filepath = os.path.join(upload_dir, filename)

            # 保存文件
            file.save(filepath)

            # 返回图片URL
            image_url = f"/static/uploads/portraits/{filename}"
            _log.info(f"立绘上传成功: {filepath}")

            return jsonify({"success": True, "url": image_url})

        except Exception as e:
            _log.error(f"上传立绘失败: {e}")
            return jsonify({"success": False, "error": f"上传失败: {str(e)}"}), 500

    @app.route("/api/personality/portrait", methods=["DELETE"])
    def delete_personality_portrait():
        """删除角色立绘图片"""
        data = request.json or {}
        portrait_url = data.get("url", "")

        if not portrait_url:
            return jsonify({"success": False, "error": "未提供图片URL"}), 400

        try:
            # 从URL中提取文件名
            if portrait_url.startswith("/static/uploads/portraits/"):
                filename = os.path.basename(portrait_url)
                filepath = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits", filename)

                if os.path.exists(filepath):
                    os.remove(filepath)
                    _log.info(f"立绘删除成功: {filepath}")

            return jsonify({"success": True})

        except Exception as e:
            _log.error(f"删除立绘失败: {e}")
            return jsonify({"success": False, "error": f"删除失败: {str(e)}"}), 500

    @app.route("/api/personality/export", methods=["POST"])
    def export_personality():
        """导出角色卡为 ZIP 文件，包含 JSON 和立绘图片"""
        data = request.json or {}
        character = data.get("character", {})

        if not character.get("name"):
            return jsonify({"success": False, "error": "角色卡缺少名称"}), 400

        try:
            # 创建内存中的 ZIP 文件
            memory_file = io.BytesIO()

            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 1. 添加 JSON 文件（不包含立绘原始数据，只保留 URL）
                character_json = json.dumps(character, ensure_ascii=False, indent=2)
                zf.writestr('character.json', character_json)

                # 2. 如果有立绘图片，添加到 ZIP
                portrait_url = character.get('portrait', '')
                if portrait_url and portrait_url.startswith('/static/'):
                    # 从 URL 获取本地文件路径
                    portrait_path = portrait_url.replace('/static/', '')
                    full_path = os.path.join(server.base_dir, 'nbot', 'web', 'static', portrait_path.replace('static/', ''))

                    if os.path.exists(full_path):
                        # 获取文件扩展名
                        _, ext = os.path.splitext(full_path)
                        # 添加到 ZIP，使用固定名称
                        zf.write(full_path, f'portrait{ext}')

            # 准备响应
            memory_file.seek(0)
            character_name = character.get('name', 'character')
            safe_name = re.sub(r'[^\w\s-]', '', character_name).strip()

            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'{safe_name}_角色卡.zip'
            )

        except Exception as e:
            _log.error(f"导出角色卡失败: {e}")
            return jsonify({"success": False, "error": f"导出失败: {str(e)}"}), 500

    @app.route("/api/personality/export-all", methods=["GET"])
    def export_all_personalities():
        """导出所有自定义角色卡为 ZIP 文件"""
        try:
            # 从文件加载自定义角色预设
            presets_file = os.path.join(server.data_dir, "custom_personality_presets.json")
            if os.path.exists(presets_file):
                try:
                    with open(presets_file, "r", encoding="utf-8") as f:
                        presets = json.load(f)
                except Exception as e:
                    _log.error(f"加载自定义角色卡预设文件失败: {e}")
                    presets = []
            else:
                presets = []

            if not presets:
                return jsonify({"success": False, "error": "没有可导出的角色卡"}), 400

            # 创建内存中的 ZIP 文件
            memory_file = io.BytesIO()

            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for preset in presets:
                    # 构建角色卡数据
                    character = {
                        "name": preset.get("name", ""),
                        "description": preset.get("description", ""),
                        "avatar": preset.get("avatar", "fas fa-user-circle"),
                        "tags": preset.get("tags", []),
                        "systemPrompt": preset.get("systemPrompt", ""),
                        "basicInfo": preset.get("basicInfo", ""),
                        "personality": preset.get("personality", ""),
                        "scenario": preset.get("scenario", ""),
                        "firstMessage": preset.get("firstMessage", ""),
                        "exampleDialogues": preset.get("exampleDialogues", ""),
                        "responseFormat": preset.get("responseFormat", ""),
                        "rules": preset.get("rules", []),
                        "state": preset.get("state", {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"})
                    }

                    # 创建角色专属文件夹名称（安全化文件名）
                    preset_id = preset.get("id", str(uuid.uuid4()))
                    safe_name = re.sub(r'[^\w\s-]', '', preset.get("name", "character")).strip() or f"character_{preset_id}"
                    folder_name = f"{safe_name}_{preset_id}"

                    # 添加 JSON 文件
                    character_json = json.dumps(character, ensure_ascii=False, indent=2)
                    zf.writestr(f'{folder_name}/character.json', character_json)

                    # 如果有立绘图片，添加到 ZIP
                    portrait = preset.get("portrait", "")
                    if portrait and portrait.startswith('/static/'):
                        portrait_path = portrait.replace('/static/', '')
                        full_path = os.path.join(server.base_dir, 'nbot', 'web', 'static', portrait_path.replace('static/', ''))

                        if os.path.exists(full_path):
                            _, ext = os.path.splitext(full_path)
                            zf.write(full_path, f'{folder_name}/portrait{ext}')

            # 准备响应
            memory_file.seek(0)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'全部角色卡_{timestamp}.zip'
            )

        except Exception as e:
            _log.error(f"导出全部角色卡失败: {e}")
            return jsonify({"success": False, "error": f"导出失败: {str(e)}"}), 500

    @app.route("/api/personality/ai-generate-first-message", methods=["POST"])
    def ai_generate_first_message():
        """AI 根据角色设定随机生成开场白"""
        data = request.json or {}

        if not server.ai_client:
            return jsonify({"success": False, "error": "AI 客户端未初始化"}), 503

        name = data.get("name", "")
        basic_info = data.get("basicInfo", "")
        personality = data.get("personality", "")
        scenario = data.get("scenario", "")

        if not name:
            return jsonify({"success": False, "error": "请先填写角色名称"}), 400

        char_context = f"角色名称：{name}"
        if basic_info:
            char_context += f"\n基本信息：{basic_info}"
        if personality:
            char_context += f"\n性格特点：{personality}"
        if scenario:
            char_context += f"\n背景设定：{scenario}"

        try:
            response = server.ai_client.chat_completion(
                model=server.ai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个角色扮演游戏的开场白设计师。根据角色设定，生成一个生动、自然、有画面感的开场白。\n\n"
                            "要求：\n"
                            "- 用括号描写角色的动作、神态（如：（微微一笑）（推了推眼镜））\n"
                            "- 语气要符合角色性格\n"
                            "- 自然口语化，不要朗诵腔\n"
                            "- 30-80字\n"
                            "- 不同风格各不同，不要每次都生成类似的\n"
                            "- 直接返回开场白，不要引号或解释"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"请为以下角色随机生成一个开场白：\n\n{char_context}",
                    },
                ],
                stream=False,
            )

            result = response.choices[0].message.content.strip()
            result = result.strip("\"'「」『』【】()（）")

            return jsonify({"success": True, "firstMessage": result})

        except Exception as e:
            _log.error(f"AI 生成开场白失败: {e}")
            return jsonify({"success": False, "error": f"生成失败: {str(e)}"}), 500

    @app.route("/api/personality/clean-unused-portraits", methods=["POST"])
    def clean_unused_portraits():
        """清理未被任何角色卡使用的立绘文件"""
        try:
            portraits_dir = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits")
            if not os.path.exists(portraits_dir):
                return jsonify({"success": True, "deleted_count": 0, "message": "没有立绘文件需要清理"})

            # 收集所有正在使用的立绘URL
            used_portraits = set()

            # 1. 当前角色的立绘
            current_portrait = server.personality.get("portrait", "")
            if current_portrait:
                used_portraits.add(current_portrait)

            # 2. 自定义角色预设中的立绘
            presets_file = os.path.join(server.data_dir, "custom_personality_presets.json")
            if os.path.exists(presets_file):
                try:
                    with open(presets_file, "r", encoding="utf-8") as f:
                        presets = json.load(f)
                    for preset in presets:
                        portrait = preset.get("portrait", "")
                        if portrait:
                            used_portraits.add(portrait)
                except Exception as e:
                    _log.error(f"加载角色预设文件失败: {e}")

            # 3. 检查会话中的立绘引用（会话可能引用角色立绘）
            if hasattr(server, 'sessions'):
                for session in server.sessions.values():
                    portrait = session.get("sender_portrait", "")
                    if portrait:
                        used_portraits.add(portrait)

            # 扫描立绘目录，找出未使用的文件
            all_portraits = os.listdir(portraits_dir)
            unused_portraits = []
            deleted_count = 0

            for filename in all_portraits:
                if not allowed_image_file(filename):
                    continue

                portrait_url = f"/static/uploads/portraits/{filename}"
                if portrait_url not in used_portraits:
                    filepath = os.path.join(portraits_dir, filename)
                    try:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        deleted_count += 1
                        unused_portraits.append({
                            "filename": filename,
                            "size": file_size
                        })
                        _log.info(f"清理未使用立绘: {filepath}")
                    except Exception as e:
                        _log.error(f"删除立绘失败 {filepath}: {e}")

            total_saved = sum(p["size"] for p in unused_portraits)
            message = f"已清理 {deleted_count} 个未使用的立绘文件，释放 {total_saved / 1024:.1f} KB 空间"

            return jsonify({
                "success": True,
                "deleted_count": deleted_count,
                "total_saved": total_saved,
                "message": message
            })

        except Exception as e:
            _log.error(f"清理未使用立绘失败: {e}")
            return jsonify({"success": False, "error": f"清理失败: {str(e)}"}), 500
