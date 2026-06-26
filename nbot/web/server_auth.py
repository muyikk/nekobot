"""Web 服务器认证相关方法。

提供登录 Token 管理、密码验证、限流检查等认证能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from flask import jsonify, request, g

from nbot.utils.logger import get_logger
from nbot.web.secure_store import write_secure_json

_log = get_logger(__name__)


class AuthMixin:
    """认证相关方法 mixin。"""

    # 期望被混入的类拥有以下属性：
    # data_dir, web_password, _web_password_is_hash, login_tokens,
    # token_expire_days, _login_fail_records, _login_rate_limit, _login_rate_window

    @staticmethod
    def _hash_token(token: str) -> str:
        """将明文 token 进行 SHA-256 哈希，用于安全存储。"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _generate_login_token(self, username: str) -> str:
        """生成登录 Token。

        Args:
            username: 用户名。

        Returns:
            token 字符串（明文，仅此一次返回）。
        """
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)

        now = datetime.now()
        expires_at = now + timedelta(days=self.token_expire_days)

        self.login_tokens[token_hash] = {
            "username": username,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        _log.info(f"[Auth] 生成登录 Token: username={username}, expires={expires_at}")
        self._save_login_tokens()
        return token

    def _validate_login_token(self, token: str) -> Optional[str]:
        """验证登录 Token。

        Args:
            token: token 明文字符串。

        Returns:
            验证成功返回用户名，失败返回 None。
        """
        token_hash = self._hash_token(token)
        if not token_hash or token_hash not in self.login_tokens:
            return None

        token_info = self.login_tokens[token_hash]
        expires_at = datetime.fromisoformat(token_info["expires_at"])
        if datetime.now() > expires_at:
            del self.login_tokens[token_hash]
            _log.info(f"[Auth] Token 已过期: username={token_info['username']}")
            return None

        return token_info["username"]

    def _cleanup_expired_tokens(self):
        """清理过期的 Token。"""
        now = datetime.now()
        expired_hashes = [
            token_hash
            for token_hash, info in self.login_tokens.items()
            if datetime.fromisoformat(info["expires_at"]) < now
        ]

        for token_hash in expired_hashes:
            del self.login_tokens[token_hash]

        if expired_hashes:
            _log.info(f"[Auth] 清理了 {len(expired_hashes)} 个过期的 Token")
            self._save_login_tokens()

    def _save_login_tokens(self):
        """保存登录 Token 到文件（仅存储 hash，不含明文 token）。"""
        try:
            login_tokens_file = __import__("os").path.join(self.data_dir, "login_tokens.json")
            write_secure_json(login_tokens_file, self.data_dir, self.login_tokens)
        except Exception as e:
            _log.error(f"[Auth] 保存登录 Token 失败: {e}")

    def _check_login_rate_limit(self, ip: str) -> Optional[int]:
        """检查 IP 是否超过登录失败限流。

        Returns:
            None 表示允许登录，整数表示需等待的秒数。
        """
        now = time.time()
        record = self._login_fail_records.get(ip)

        if record is None:
            return None

        if now - record["first_fail"] > self._login_rate_window:
            del self._login_fail_records[ip]
            return None

        if record["count"] >= self._login_rate_limit:
            remaining = int(self._login_rate_window - (now - record["first_fail"]))
            return max(remaining, 1)

        return None

    def _record_login_failure(self, ip: str):
        """记录一次登录失败。"""
        now = time.time()
        record = self._login_fail_records.get(ip)

        if record is None or now - record["first_fail"] > self._login_rate_window:
            self._login_fail_records[ip] = {"count": 1, "first_fail": now}
        else:
            record["count"] += 1

    def _reset_login_failures(self, ip: str):
        """登录成功后清除该 IP 的失败记录。"""
        self._login_fail_records.pop(ip, None)

    def _verify_password(self, password: str) -> bool:
        """验证密码，支持明文和 bcrypt 哈希两种模式。

        bcrypt 哈希格式: $2b$12$... 或 $2a$12$...
        明文密码直接使用 secrets.compare_digest 安全比较。
        """
        stored = self.web_password
        if not stored or not password:
            return False

        if self._web_password_is_hash:
            try:
                import bcrypt
                return bcrypt.checkpw(
                    password.encode("utf-8"), stored.encode("utf-8")
                )
            except ImportError:
                _log.warning("[Auth] bcrypt 未安装，回退到明文比较")
                return secrets.compare_digest(password, stored)
            except Exception as e:
                _log.error(f"[Auth] bcrypt 验证异常: {e}")
                return False
        else:
            return secrets.compare_digest(password, stored)

    def _extract_request_token(self) -> str:
        """从请求中提取认证 token。"""
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()

        header_token = (
            request.headers.get("X-Auth-Token", "").strip()
            or request.headers.get("X-Token", "").strip()
        )
        if header_token:
            return header_token

        cookie_token = request.cookies.get("nbot_auth_token", "").strip()
        if cookie_token:
            return cookie_token

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            body_token = ""
            if request.is_json:
                data = request.get_json(silent=True) or {}
                body_token = str(data.get("token", "")).strip()
            if not body_token:
                body_token = request.form.get("token", "").strip()
            if body_token:
                return body_token

        return ""

    def _register_auth_middleware(self):
        """为所有私有 API 路由启用登录 token 保护。"""
        public_api_paths = {
            "/api/login",
            "/api/verify-token",
            "/api/startup-status",
        }

        @self.app.before_request
        def _enforce_api_auth():
            if request.method == "OPTIONS":
                return None

            path = request.path or ""
            if not path.startswith("/api/"):
                return None

            if path in public_api_paths:
                return None
            if path.startswith("/api/channels/telegram/") and path.endswith("/webhook"):
                return None

            token = self._extract_request_token()
            username = self._validate_login_token(token)
            if not username:
                return jsonify(
                    {
                        "success": False,
                        "error": "Unauthorized",
                        "message": "Login required",
                    }
                ), 401

            g.auth_username = username
            g.auth_token = token
            return None
