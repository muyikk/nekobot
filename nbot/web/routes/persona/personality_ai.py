"""角色卡 AI 生成路由——AI 生成角色卡、状态、立绘。"""
import json
import os
import re
import uuid

from flask import jsonify, request

from nbot.utils.logger import get_logger
from .compile import compile_personality_prompt

_log = get_logger(__name__)


def register_ai_routes(app, server):
    @app.route("/api/personality/ai-generate", methods=["POST"])
    def ai_generate_personality():
        """AI 根据用户描述生成角色卡"""
        data = request.json or {}
        description = (data.get("description") or "").strip()

        if not description:
            return jsonify({"success": False, "error": "请提供角色描述"}), 400

        if not server.ai_client:
            return jsonify({"success": False, "error": "AI 客户端未初始化"}), 503

        system_prompt = """你是一个角色卡生成专家。用户会描述一个角色，你需要根据描述生成一个完整的角色卡JSON。

你必须严格按照以下JSON格式返回（不要包含任何额外的文字说明，只返回JSON）：

{
    "name": "角色名称",
    "description": "简短角色描述（用于卡片显示，20字以内）",
    "avatar": "fas fa-star（FontAwesome图标类名，从以下选择最合适的：fas fa-cat, fas fa-dragon, fas fa-hat-wizard, fas fa-skull, fas fa-robot, fas fa-user-secret, fas fa-user-ninja, fas fa-user-astronaut, fas fa-user-graduate, fas fa-user-tie, fas fa-user, fas fa-crown, fas fa-heart, fas fa-star, fas fa-moon, fas fa-sun, fas fa-fire, fas fa-ghost, fas fa-magic, fas fa-shield-haltered, fas fa-wand-sparkles）",
    "tags": ["标签1", "标签2", "标签3"],
    "basicInfo": "角色的基本资料（身高、年龄、职业、外貌、喜好等），每行一项",
    "personality": "性格特点的详细描述",
    "scenario": "角色的背景故事和世界观设定",
    "firstMessage": "新会话中AI自动发送的第一条消息（要符合角色风格）",
    "exampleDialogues": "<user>用户消息示例\\n<assistant>角色回复示例（要符合角色风格和语气）",
    "responseFormat": "期望的回复格式描述，如：（动作描写）对话内容【心情/附加信息】",
    "rules": ["行为规则1", "行为规则2", "行为规则3"],
    "state": {
        "affection": 50,
        "trust": 50,
        "familiarity": 30,
        "dependency": 30,
        "security": 50,
        "mood": "开心"
    }
}

要求：
1. name 必须有创意且贴合描述
2. tags 至少3个，最多5个
3. basicInfo 要具体详细，包含形象特征
4. personality 要生动、有层次
5. scenario 要有沉浸感
6. firstMessage 要符合角色性格，自然不做作
7. exampleDialogues 至少包含2轮对话示例
8. rules 要覆盖角色行为约束和特色
9. state 中的关系初始值必须根据角色设定合理设置：
   - affection（好感）：根据角色对用户的初始态度设置（0-100）
   - trust（信任）：根据角色对用户的初始信任程度设置（0-100）
   - familiarity（熟悉）：根据角色与用户的初始熟悉度设置（0-100）
   - dependency（依赖）：根据角色对用户的初始依赖程度设置（0-100）
   - security（安全感）：根据角色在关系中的初始安全感设置（0-100）
   - mood（心情）：根据角色当前心情设置
10. 所有字段都用中文填写"""

        try:
            response = server.ai_client.chat_completion(
                model=server.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请根据以下描述创建角色卡：\n\n{description}"},
                ],
                stream=False,
            )

            content = response.choices[0].message.content.strip()

            # 提取 JSON（可能被 markdown 代码块包裹）
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if json_match:
                content = json_match.group(1)

            character = json.loads(content)

            # 填充缺失字段的默认值
            character.setdefault("name", "未命名角色")
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
            # 确保 state 包含所有多维度关系字段
            default_state = {
                "affection": 50,
                "trust": 50,
                "familiarity": 30,
                "dependency": 30,
                "security": 50,
                "mood": "开心"
            }
            ai_state = character.get("state", {})
            if isinstance(ai_state, dict):
                for key, val in default_state.items():
                    ai_state.setdefault(key, val)
                character["state"] = ai_state
            else:
                character["state"] = default_state
            # 立绘图字段 - 由用户后续上传
            character.setdefault("portrait", "")
            character["systemPrompt"] = compile_personality_prompt(character)

            return jsonify({"success": True, "character": character})

        except json.JSONDecodeError as e:
            _log.error(f"AI 生成角色卡 JSON 解析失败: {e}, content: {content[:500] if 'content' in dir() else 'N/A'}")
            return jsonify({"success": False, "error": "AI 生成的角色卡格式有误，请重试"}), 500
        except Exception as e:
            _log.error(f"AI 生成角色卡失败: {e}")
            return jsonify({"success": False, "error": f"生成失败: {str(e)}"}), 500

    @app.route("/api/personality/ai-generate-state", methods=["POST"])
    def ai_generate_state():
        """AI 根据当前角色卡内容生成推荐的状态初始值"""
        data = request.json or {}
        character = data.get("character", {})

        if not server.ai_client:
            return jsonify({"success": False, "error": "AI 客户端未初始化"}), 503

        name = character.get("name", "")
        basic_info = character.get("basicInfo", "")
        personality_desc = character.get("personality", "")
        scenario = character.get("scenario", "")

        if not name:
            return jsonify({"success": False, "error": "角色名称不能为空"}), 400

        system_prompt = """你是一个角色关系分析专家。根据提供的角色卡信息，分析该角色对用户的初始关系状态。

你必须严格按照以下JSON格式返回（不要包含任何额外的文字说明，只返回JSON）：

{
    "affection": 50,
    "trust": 50,
    "familiarity": 30,
    "dependency": 30,
    "security": 50,
    "mood": "开心"
}

各字段含义和设置规则：
- affection（好感，0-100）：角色对用户的初始好感度。陌生人通常30-50，友好角色50-70，敌对角色10-30，亲密关系70-90
- trust（信任，0-100）：角色对用户的初始信任度。初次见面通常20-40，坦诚角色40-60，谨慎角色10-30
- familiarity（熟悉，0-100）：角色与用户的初始熟悉度。初次相遇通常10-30，旧识50-80
- dependency（依赖，0-100）：角色对用户的初始依赖程度。独立角色10-30，粘人角色40-60，极度依赖70-90
- security（安全感，0-100）：角色在关系中的初始安全感。自信角色60-80，不安角色20-40
- mood（心情）：角色当前的心情状态，从以下选择：开心、平静、期待、紧张、害羞、委屈、生气、伤心、困倦、得意

分析要求：
1. 必须基于角色的性格、背景和设定来推断初始关系值
2. 不要所有角色都用默认值，要根据角色特点差异化设置
3. 返回纯JSON，不要任何额外文字"""

        user_prompt = f"""请分析以下角色对用户的初始关系状态：

角色名称：{name}

角色基本资料：
{basic_info or '（未提供）'}

角色性格：
{personality_desc or '（未提供）'}

角色背景：
{scenario or '（未提供）'}

请返回推荐的初始关系状态JSON。"""

        try:
            response = server.ai_client.chat_completion(
                model=server.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
            )

            content = response.choices[0].message.content.strip()

            # 提取 JSON（可能被 markdown 代码块包裹）
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if json_match:
                content = json_match.group(1)

            state = json.loads(content)

            # 验证并填充缺失字段
            default_state = {
                "affection": 50,
                "trust": 50,
                "familiarity": 30,
                "dependency": 30,
                "security": 50,
                "mood": "开心"
            }
            if isinstance(state, dict):
                for key, val in default_state.items():
                    if key not in state:
                        state[key] = val
                    # 数值字段限制在0-100
                    if key != "mood" and isinstance(state[key], (int, float)):
                        state[key] = max(0, min(100, int(state[key])))
                    # mood必须是字符串
                    if key == "mood" and not isinstance(state.get(key), str):
                        state[key] = "开心"
            else:
                state = default_state

            return jsonify({"success": True, "state": state})

        except json.JSONDecodeError as e:
            _log.error(f"AI 生成状态 JSON 解析失败: {e}, content: {content[:500] if 'content' in dir() else 'N/A'}")
            return jsonify({"success": False, "error": "AI 生成的状态格式有误，请重试"}), 500
        except Exception as e:
            _log.error(f"AI 生成状态失败: {e}")
            return jsonify({"success": False, "error": f"生成失败: {str(e)}"}), 500

    @app.route("/api/personality/generate-portrait", methods=["POST"])
    def generate_portrait():
        """使用AI生成角色立绘"""
        data = request.json or {}
        character_name = data.get("character_name", "").strip()
        description = data.get("description", "").strip()
        basic_info = data.get("basic_info", "").strip()
        personality = data.get("personality", "").strip()

        if not character_name:
            return jsonify({"success": False, "error": "请提供角色名称"}), 400

        # 检查是否配置了图片生成模型
        image_gen_config = None
        if hasattr(server, 'active_models_by_purpose'):
            image_gen_model_id = server.active_models_by_purpose.get('image_generation')
            if image_gen_model_id and hasattr(server, 'ai_models'):
                for model in server.ai_models:
                    if model.get('id') == image_gen_model_id:
                        image_gen_config = model
                        break

        if not image_gen_config:
            return jsonify({
                "success": False,
                "need_config": True,
                "error": "未配置图片生成模型，请先在AI配置中添加图片生成模型"
            }), 400

        try:
            # 构建图片生成提示词
            # 获取用户配置的提示词模板，如果没有则使用默认模板
            prompt_template = image_gen_config.get('prompt_template', '').strip()
            if not prompt_template:
                prompt_template = "Create an anime-style character portrait of {character_name}."

            # 替换模板中的占位符
            image_prompt = prompt_template.format(
                character_name=character_name,
                description=description or '',
                personality=personality or '',
                basic_info=basic_info or ''
            )

            # 添加额外的角色信息（如果模板中没有包含）
            additional_info = []
            if basic_info and '{basic_info}' not in prompt_template:
                additional_info.append(f"Appearance: {basic_info}")
            if personality and '{personality}' not in prompt_template:
                additional_info.append(f"Personality: {personality}")
            if description and '{description}' not in prompt_template:
                additional_info.append(f"Description: {description}")

            if additional_info:
                image_prompt += " " + " ".join(additional_info)

            # 添加风格和质量要求（如果模板中没有包含风格相关关键词）
            style_keywords = ['style', 'quality', 'format', 'anime', 'illustration', 'art']
            if not any(keyword in prompt_template.lower() for keyword in style_keywords):
                image_prompt += " Style: High-quality anime illustration, detailed, vibrant colors, professional character art."
                image_prompt += " Format: Portrait orientation, upper body or bust shot, clean background or simple gradient."

            # 调用图片生成API
            import requests
            import os

            api_key = image_gen_config.get('api_key', '')
            # 使用用户输入的完整URL（包含路径后缀）
            full_url = image_gen_config.get('base_url', '')
            model = image_gen_config.get('model', 'dall-e-3')
            # 获取配置的图片尺寸，默认为 1024x1024
            image_size = image_gen_config.get('size', '1024x1024')
            # 火山引擎等需要至少 3686400 像素（约 1920x1920），如果配置的是小尺寸则使用兼容尺寸
            if 'volces' in full_url.lower() or 'ark' in full_url.lower():
                # 火山引擎需要大图片尺寸
                width, height = image_size.split('x')
                pixels = int(width) * int(height)
                if pixels < 3686400:
                    image_size = '1920x1920'  # 使用兼容的最小尺寸

            if not full_url:
                return jsonify({"success": False, "error": "未配置图片生成API地址"}), 400

            # 根据不同provider调用不同的API格式
            provider_type = image_gen_config.get('provider_type', 'openai_compatible')

            if provider_type in ['openai_compatible', 'openai'] or 'openai' in full_url.lower():
                # OpenAI DALL-E API 格式
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": model,
                    "prompt": image_prompt,
                    "n": 1,
                    "size": image_size,
                    "quality": "standard",
                    "response_format": "url"
                }

                response = requests.post(
                    full_url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code != 200:
                    _log.error(f"图片生成API错误: {response.text}")
                    return jsonify({"success": False, "error": f"图片生成失败: {response.text}"}), 500

                result = response.json()
                image_url = result.get("data", [{}])[0].get("url")

            elif provider_type == 'siliconflow' or 'siliconflow' in full_url.lower():
                # SiliconFlow API 格式
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": model,
                    "prompt": image_prompt,
                    "image_size": image_size,
                    "batch_size": 1
                }

                response = requests.post(
                    full_url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code != 200:
                    _log.error(f"图片生成API错误: {response.text}")
                    return jsonify({"success": False, "error": f"图片生成失败: {response.text}"}), 500

                result = response.json()
                image_url = result.get("images", [{}])[0].get("url")

            else:
                # 通用OpenAI兼容格式
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": model,
                    "prompt": image_prompt,
                    "n": 1,
                    "size": image_size
                }

                response = requests.post(
                    full_url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code != 200:
                    _log.error(f"图片生成API错误: {response.text}")
                    return jsonify({"success": False, "error": f"图片生成失败: {response.text}"}), 500

                result = response.json()
                # 尝试多种可能的响应格式
                image_url = result.get("data", [{}])[0].get("url") or result.get("images", [{}])[0].get("url")

            if not image_url:
                return jsonify({"success": False, "error": "未能获取生成的图片URL"}), 500

            # 下载图片并保存到本地
            image_response = requests.get(image_url, timeout=60)
            if image_response.status_code != 200:
                return jsonify({"success": False, "error": "下载生成的图片失败"}), 500

            # 创建上传目录
            upload_dir = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits")
            os.makedirs(upload_dir, exist_ok=True)

            # 生成唯一文件名
            new_filename = f"portrait_ai_{uuid.uuid4().hex[:16]}.png"
            filepath = os.path.join(upload_dir, new_filename)

            # 保存文件
            with open(filepath, 'wb') as f:
                f.write(image_response.content)

            portrait_url = f"/static/uploads/portraits/{new_filename}"
            _log.info(f"AI立绘生成成功: {character_name} -> {portrait_url}")

            return jsonify({
                "success": True,
                "portrait_url": portrait_url,
                "message": "立绘生成成功"
            })

        except requests.exceptions.Timeout:
            _log.error("图片生成请求超时")
            return jsonify({"success": False, "error": "图片生成请求超时，请稍后重试"}), 504
        except Exception as e:
            _log.error(f"AI立绘生成失败: {e}")
            return jsonify({"success": False, "error": f"生成失败: {str(e)}"}), 500
