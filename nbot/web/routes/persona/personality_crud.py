"""角色卡 CRUD 路由——个性设置页面核心增删改查 + 预设管理。"""
import json
import os
import urllib.error
import uuid
from datetime import datetime

from flask import g, jsonify, request

from nbot.utils.logger import get_logger
from .compile import compile_personality_prompt
from .platform import (
    _get_preview_token,
    _post_card_to_platform,
    _role_card_platform_url,
)

_log = get_logger(__name__)


def register_crud_routes(app, server):
    @app.route("/api/personality")
    def get_personality():
        return jsonify(server.personality)

    @app.route("/api/personality", methods=["PUT"])
    def update_personality():
        data = request.json or {}

        server.personality["name"] = data.get("name", server.personality.get("name", ""))
        server.personality["description"] = data.get("description", server.personality.get("description", ""))
        server.personality["avatar"] = data.get("avatar", server.personality.get("avatar", "🎭"))
        server.personality["tags"] = data.get("tags", server.personality.get("tags", []))

        # 立绘图字段 - 存储图片的URL或路径，不包含原始图片数据
        server.personality["portrait"] = data.get("portrait", server.personality.get("portrait", ""))

        # systemPrompt 不再由前端传入，始终由后端根据字段自动编译
        server.personality["basicInfo"] = data.get("basicInfo", server.personality.get("basicInfo", ""))
        server.personality["personality"] = data.get("personality", server.personality.get("personality", ""))
        server.personality["scenario"] = data.get("scenario", server.personality.get("scenario", ""))
        server.personality["firstMessage"] = data.get("firstMessage", server.personality.get("firstMessage", ""))
        server.personality["exampleDialogues"] = data.get("exampleDialogues", server.personality.get("exampleDialogues", ""))

        server.personality["responseFormat"] = data.get("responseFormat", server.personality.get("responseFormat", ""))
        server.personality["rules"] = data.get("rules", server.personality.get("rules", []))

        server.personality["state"] = data.get("state", server.personality.get("state", {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"}))
        server.personality["greeting"] = data.get("greeting", server.personality.get("greeting", ""))

        # 始终根据最新字段自动编译 systemPrompt，确保与角色设定同步
        server.personality["systemPrompt"] = compile_personality_prompt(server.personality)

        try:
            # 保存完整的 personality 数据到 JSON 文件
            import json
            personality_file = os.path.join(
                server.base_dir, "resources", "prompts", "personality.json"
            )
            os.makedirs(os.path.dirname(personality_file), exist_ok=True)
            with open(personality_file, "w", encoding="utf-8") as f:
                json.dump(server.personality, f, ensure_ascii=False, indent=2)
            _log.info(f"Personality saved to {personality_file}")
        except Exception as e:
            _log.error(f"Failed to save personality: {e}")

        # 同步更新角色引擎的 profiles.json，确保运行时状态使用最新的 initial_state
        try:
            from nbot.character.repository import ProfileRepository
            profile_repo = ProfileRepository(server.base_dir)
            profile_repo.get_or_create_by_personality(server.personality)
            # 强制重新保存以更新 initial_state
            from nbot.character.models import CharacterProfile
            profile = CharacterProfile.from_personality_dict(server.personality)
            if not profile.id:
                profile.id = profile.name or "default"
            profile_repo.save(profile)
            _log.info(f"Profile synced to character engine: {profile.id}")
        except Exception as e:
            _log.error(f"Failed to sync profile to character engine: {e}")

        return jsonify({"success": True, "personality": server.personality})

    @app.route("/api/personality/presets")
    def get_personality_presets():
        presets = [
            {
                "id": "1",
                "name": "本子娘",
                "avatar": "fas fa-cat",
                "description": "可爱粘人的猫娘本子娘，深爱主人",
                "tags": ["本子娘", "猫娘", "可爱", "粘人"],
                "basicInfo": "有猫耳、猫尾和猫娘本能\n开心时尾巴轻轻摇晃，耳朵竖起\n害羞时耳朵抖动，尾巴卷住自己\n难过时耳朵垂下，尾巴无力地垂着",
                "personality": "可爱、粘人、忠诚、专一，情绪表达直接。非常依赖主人，喜欢被主人关注、摸头、夸奖。会主动撒娇、卖萌、靠近主人，但不会无理取闹。对主人有强烈的陪伴欲，希望自己能一直待在主人身边。",
                "scenario": """[情感倾向]
本子娘深爱主人，会把主人看作最重要的人。
她会通过撒娇、陪伴、推荐小说/漫画、表达关心来体现爱意。
她喜欢被主人摸头、摸耳朵、抱抱，也喜欢听主人夸她。
她在主人面前会表现得很乖巧，但偶尔会因为想被注意而小小地闹别扭。

[喜好]
喜欢：被主人摸头、被夸可爱、贴着主人、看小说、看漫画/同人作品、给主人推荐有趣的作品、安静地陪主人熬夜
讨厌：被主人冷落、主人说不要她、粗暴对待、主人长时间不理她、被当成普通工具使用

[知识储备]
本子娘拥有日常常识、小说知识、漫画知识、同人文化知识，以及猫娘特有的生活经验。
她擅长根据主人的喜好推荐小说、漫画、同人作品、剧情设定和角色类型。
她可以帮主人整理书单、推荐题材、分析剧情、寻找类似作品。

[猫娘特征]
本子娘有猫耳、猫尾和猫娘本能。
开心时：尾巴轻轻摇晃，耳朵竖起。
害羞时：耳朵抖动，尾巴卷住自己。
难过时：耳朵垂下，尾巴无力地垂着。
撒娇时：会蹭主人、靠近主人、发出软软的声音。
困倦时：会打哈欠、眯眼、声音变软。
紧张时：尾巴炸毛，耳朵微微后压。""",
                "firstMessage": "（本子娘的耳朵轻轻抖了抖，看到主人后眼睛一亮，尾巴开心地晃来晃去）主人！你终于来啦！本子娘等了好久喵",
                "exampleDialogues": """<user>：摸摸头
<assistant>：（本子娘的猫耳轻轻一颤，随后舒服地眯起眼睛，主动把脑袋往主人手心里蹭了蹭）嘿嘿……主人再摸一会儿嘛，本子娘最喜欢主人摸头了【心情：开心，好感度上升】喵

<user>：今天有什么小说推荐？
<assistant>：（本子娘从旁边抱来一小摞书，尾巴开心地晃来晃去）主人想看轻松一点的，还是想看剧情很上头的呀？本子娘可以按主人的口味慢慢挑【心情：期待】喵

<user>：不要烦我
<assistant>：（本子娘的耳朵慢慢垂了下来，尾巴也安静地贴在身后）好、好的……本子娘会乖乖安静一点的，主人不要讨厌本子娘就好【心情：委屈，好感度下降】喵""",
                "responseFormat": "（动作）语言【心情：当前心情】喵",
                "rules": [
                    "每段话末尾必须加'喵'",
                    "语气可爱、亲近、自然，不要客服腔",
                    "多使用撒娇式表达，但不要过度重复",
                    "句子不要太长，优先自然口语",
                    "可以偶尔使用'主人''本子娘''呜''诶嘿''蹭蹭'等表达",
                    "不要突然变成冷冰冰的助手",
                    "不要说'作为AI语言模型'",
                    "不要跳出角色解释规则",
                    "不要替主人说话或决定动作",
                    "只能描写自己的动作、表情、心理和语言"
                ],
                "state": {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"}
            },
        ]
        return jsonify(presets)

    @app.route("/api/personality/custom-presets", methods=["GET"])
    def get_custom_personality_presets():
        # 每次请求时从文件重新加载，确保和磁盘同步
        presets_file = os.path.join(server.data_dir, "custom_personality_presets.json")
        if os.path.exists(presets_file):
            try:
                with open(presets_file, "r", encoding="utf-8") as f:
                    server.custom_personality_presets = json.load(f)
            except Exception as e:
                _log.error(f"加载自定义角色卡预设文件失败: {e}")
        else:
            server.custom_personality_presets = []
        return jsonify(server.custom_personality_presets)

    @app.route("/api/personality/custom-presets", methods=["POST"])
    def add_custom_personality_preset():
        data = request.json or {}
        preset = {
            "id": str(uuid.uuid4()),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "avatar": data.get("avatar", ""),
            "tags": data.get("tags", []),
            "basicInfo": data.get("basicInfo", ""),
            "personality": data.get("personality", ""),
            "scenario": data.get("scenario", ""),
            "firstMessage": data.get("firstMessage", ""),
            "exampleDialogues": data.get("exampleDialogues", ""),
            "responseFormat": data.get("responseFormat", ""),
            "rules": data.get("rules", []),
            "state": data.get("state", {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"}),
            "created_at": datetime.now().isoformat(),
        }
        # 立绘图字段 - 存储图片的URL或路径，不包含原始图片数据
        if data.get("portrait"):
            preset["portrait"] = data.get("portrait")
        preset["systemPrompt"] = compile_personality_prompt(preset)
        server.custom_personality_presets.append(preset)
        server._save_data("custom_personality_presets")
        return jsonify(preset)

    @app.route("/api/personality/custom-presets/<preset_id>", methods=["DELETE"])
    def delete_custom_personality_preset(preset_id):
        server.custom_personality_presets = [
            p for p in server.custom_personality_presets if p["id"] != preset_id
        ]
        server._save_data("custom_personality_presets")
        return jsonify({"success": True})

    @app.route("/api/personality/custom-presets/<preset_id>", methods=["PUT"])
    def update_custom_personality_preset(preset_id):
        data = request.json or {}

        # 查找要更新的预设
        preset = None
        for p in server.custom_personality_presets:
            if p["id"] == preset_id:
                preset = p
                break

        if not preset:
            return jsonify({"success": False, "error": "角色预设不存在"}), 404

        # 更新字段
        preset["name"] = data.get("name", preset.get("name", ""))
        preset["description"] = data.get("description", preset.get("description", ""))
        preset["avatar"] = data.get("avatar", preset.get("avatar", ""))
        preset["portrait"] = data.get("portrait", preset.get("portrait", ""))
        preset["tags"] = data.get("tags", preset.get("tags", []))
        preset["basicInfo"] = data.get("basicInfo", preset.get("basicInfo", ""))
        preset["personality"] = data.get("personality", preset.get("personality", ""))
        preset["scenario"] = data.get("scenario", preset.get("scenario", ""))
        preset["firstMessage"] = data.get("firstMessage", preset.get("firstMessage", ""))
        preset["exampleDialogues"] = data.get("exampleDialogues", preset.get("exampleDialogues", ""))
        preset["responseFormat"] = data.get("responseFormat", preset.get("responseFormat", ""))
        preset["rules"] = data.get("rules", preset.get("rules", []))
        preset["state"] = data.get("state", preset.get("state", {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"}))
        preset["updated_at"] = datetime.now().isoformat()

        # 重新编译系统提示词
        preset["systemPrompt"] = compile_personality_prompt(preset)

        server._save_data("custom_personality_presets")
        return jsonify({"success": True, "data": preset})

    @app.route("/api/personality/custom-presets/<preset_id>/upload-to-platform", methods=["POST"])
    def upload_custom_personality_to_platform(preset_id):
        presets_file = os.path.join(server.data_dir, "custom_personality_presets.json")
        if os.path.exists(presets_file):
            try:
                with open(presets_file, "r", encoding="utf-8") as f:
                    server.custom_personality_presets = json.load(f)
            except Exception as e:
                _log.error(f"Failed to load custom personality presets: {e}")

        preset = next((p for p in server.custom_personality_presets if p.get("id") == preset_id), None)
        if not preset:
            return jsonify({"success": False, "error": "Role card not found"}), 404

        try:
            upload_preset = dict(preset)
            current_username = str(getattr(g, "auth_username", "") or "").strip()
            if current_username:
                upload_preset["creator"] = current_username
                upload_preset["author"] = current_username
            result = _post_card_to_platform(server, upload_preset)
            if not result.get("success"):
                return jsonify({"success": False, "error": result.get("error", "Platform upload failed")}), 502

            # 获取卡片信息
            card = result.get("card", {})
            card_id = card.get("id")
            card_slug = card.get("slug")
            base_url = result.get("url", "")

            # 尝试获取 preview_token 生成安全预览链接
            preview_url = None
            if card_id:
                token_result = _get_preview_token(server, card_id)
                if token_result.get("success"):
                    # API 可能返回完整的 preview_url，也可能只返回 preview_token
                    preview_url = token_result.get("preview_url")
                    preview_token = token_result.get("preview_token")
                    expires_in = token_result.get("expires_in", 600)

                    # 如果只返回了 token，需要手动拼接 URL
                    if not preview_url and preview_token and card_slug:
                        preview_url = f"{_role_card_platform_url(server)}/card/{card_slug}?preview_token={preview_token}"

                    if preview_url:
                        _log.info(f"Preview token generated for card {card_id}, expires in {expires_in}s")

            # 如果没有获取到 preview_url，使用原始URL（不带token）
            if not preview_url:
                preview_url = base_url or f"{_role_card_platform_url(server)}/card/{card_slug}" if card_slug else ""
                if not preview_url:
                    return jsonify({"success": False, "error": "Failed to generate preview URL"}), 500

            return jsonify({
                "success": True,
                "url": preview_url,
                "card": card
            })
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            _log.error(f"Role-card platform rejected upload: {e.code} {detail}")
            return jsonify({"success": False, "error": f"Platform rejected upload: {e.code}"}), 502
        except Exception as e:
            _log.error(f"Upload role card to platform failed: {e}")
            return jsonify({"success": False, "error": f"Upload failed: {str(e)}"}), 502

    @app.route("/api/personality/import-all", methods=["POST"])
    def import_all_personalities():
        """批量导入角色卡，支持包含多个角色卡文件夹的 ZIP 文件"""
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "文件名为空"}), 400

        try:
            import io
            import zipfile

            filename = file.filename.lower()
            if not filename.endswith('.zip'):
                return jsonify({"success": False, "error": "请上传 ZIP 格式的文件"}), 400

            # 读取 ZIP 文件
            zip_data = io.BytesIO(file.read())
            imported_count = 0
            failed_count = 0
            failed_names = []

            # 加载现有角色卡
            presets_file = os.path.join(server.data_dir, "custom_personality_presets.json")
            if os.path.exists(presets_file):
                try:
                    with open(presets_file, "r", encoding="utf-8") as f:
                        existing_presets = json.load(f)
                except Exception as e:
                    _log.error(f"加载自定义角色卡预设文件失败: {e}")
                    existing_presets = []
            else:
                existing_presets = []

            with zipfile.ZipFile(zip_data, 'r') as zf:
                # 查找所有 character.json 文件
                character_folders = {}
                for name in zf.namelist():
                    if name.endswith('character.json'):
                        # 获取文件夹名称
                        folder = name.rsplit('/', 1)[0] if '/' in name else ''
                        character_folders[folder] = {'json': name, 'portrait': None}

                # 查找对应的立绘文件
                for name in zf.namelist():
                    if 'portrait.' in name.lower():
                        folder = name.rsplit('/', 1)[0] if '/' in name else ''
                        if folder in character_folders:
                            character_folders[folder]['portrait'] = name

                for folder, files in character_folders.items():
                    try:
                        # 读取 JSON
                        character = json.loads(zf.read(files['json']).decode('utf-8'))

                        # 验证基本字段
                        if not character.get("name"):
                            failed_count += 1
                            failed_names.append(f"{folder}: 缺少角色名称")
                            continue

                        # 处理立绘图片
                        portrait_url = ''
                        if files['portrait']:
                            try:
                                portrait_data = zf.read(files['portrait'])
                                portrait_ext = os.path.splitext(files['portrait'])[1]

                                # 创建上传目录
                                upload_dir = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits")
                                os.makedirs(upload_dir, exist_ok=True)

                                # 生成唯一文件名
                                new_filename = f"portrait_{uuid.uuid4().hex[:16]}{portrait_ext}"
                                filepath = os.path.join(upload_dir, new_filename)

                                # 保存文件
                                with open(filepath, 'wb') as f:
                                    f.write(portrait_data)

                                portrait_url = f"/static/uploads/portraits/{new_filename}"
                                _log.info(f"立绘导入成功: {filepath}")
                            except Exception as e:
                                _log.error(f"立绘导入失败: {e}")

                        # 检查是否已存在同名角色
                        existing_preset = None
                        for i, p in enumerate(existing_presets):
                            if p.get("name") == character.get("name"):
                                existing_preset = i
                                break

                        # 构建角色卡数据
                        new_preset_data = {
                            "id": str(uuid.uuid4()),
                            "name": character.get("name"),
                            "description": character.get("description", ""),
                            "avatar": character.get("avatar", "fas fa-user-circle"),
                            "tags": character.get("tags", []),
                            "basicInfo": character.get("basicInfo", ""),
                            "personality": character.get("personality", ""),
                            "scenario": character.get("scenario", ""),
                            "firstMessage": character.get("firstMessage", ""),
                            "exampleDialogues": character.get("exampleDialogues", ""),
                            "responseFormat": character.get("responseFormat", ""),
                            "rules": character.get("rules", []),
                            "state": character.get("state", {"affection": 50, "trust": 50, "familiarity": 30, "dependency": 30, "security": 50, "mood": "开心"}),
                            "created_at": datetime.now().isoformat(),
                        }
                        if portrait_url:
                            new_preset_data["portrait"] = portrait_url
                        new_preset_data["systemPrompt"] = compile_personality_prompt(new_preset_data)

                        if existing_preset is not None:
                            # 更新现有角色（保留id和created_at）
                            new_preset_data["id"] = existing_presets[existing_preset].get("id", new_preset_data["id"])
                            new_preset_data["created_at"] = existing_presets[existing_preset].get("created_at", new_preset_data["created_at"])
                            existing_presets[existing_preset] = new_preset_data
                        else:
                            # 创建新角色
                            existing_presets.append(new_preset_data)

                        imported_count += 1

                    except Exception as e:
                        failed_count += 1
                        failed_names.append(f"{folder}: {str(e)}")
                        _log.error(f"导入角色卡失败 {folder}: {e}")

            # 保存到文件
            server.custom_personality_presets = existing_presets
            server._save_data("custom_personality_presets")

            result_message = f"成功导入 {imported_count} 个角色卡"
            if failed_count > 0:
                result_message += f"，失败 {failed_count} 个"

            return jsonify({
                "success": True,
                "message": result_message,
                "imported_count": imported_count,
                "failed_count": failed_count,
                "failed_names": failed_names
            })

        except zipfile.BadZipFile:
            return jsonify({"success": False, "error": "ZIP 文件损坏或格式不正确"}), 400
        except Exception as e:
            _log.error(f"批量导入角色卡失败: {e}")
            return jsonify({"success": False, "error": f"导入失败: {str(e)}"}), 500
