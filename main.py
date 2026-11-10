"""Webhook 接收插件：服务端填 AstrBot 地址，按 /webhook/<event> 推送到绑定会话。"""

from __future__ import annotations

import json
from typing import Any

from aiohttp import web

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr


EVENT_KEYS = {
    "approved-post": "approved_post",
    "approved-comment": "approved_comment",
    "pending-post": "pending_post",
    "pending-comment": "pending_comment",
}

class WebhookPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.runner: web.AppRunner | None = None
        self.port = 0

    async def initialize(self) -> None:
        host = str(self.config.get("host") or "0.0.0.0")
        port = int(self.config.get("port") or 6199)
        app = web.Application()
        configured = self.config.get("events") or {}
        for event, key in EVENT_KEYS.items():
            if isinstance(configured, dict) and configured.get(key, False):
                app.router.add_post(f"/webhook/{event}", self.handle)
                logger.info("[webhook] 已启用 /webhook/%s", event)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        for offset in range(30):
            candidate = port + offset
            try:
                await web.TCPSite(self.runner, host, candidate).start()
                self.port = candidate
                logger.info("[webhook] 监听 %s:%s", host, candidate)
                break
            except OSError:
                logger.warning("[webhook] 端口 %s 被占用，尝试下一个", candidate)
        if not self.port:
            logger.error("[webhook] 30 个端口都被占用，启动失败")

    async def terminate(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()

    # -- 配置 ---------------------------------------------------------------
    def hooks(self) -> list[dict]:
        raw = self.config.get("webhooks")
        return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []

    def save(self) -> None:
        try:
            self.config["webhooks"] = self.hooks()
            self.config.save_config()
        except Exception as exc:
            logger.warning("[webhook] 保存失败：%s", exc)

    def find(self, name: str) -> dict | None:
        for item in self.hooks():
            if str(item.get("name") or "") == name:
                return item
        return None

    def find_by_token(self, token: str) -> dict | None:
        if not token:
            return None
        for item in self.hooks():
            if item.get("enabled", True) and str(item.get("token") or "") == token:
                return item
        return None

    # -- HTTP ---------------------------------------------------------------
    @staticmethod
    def _token(request: web.Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return (
            request.headers.get("X-Webhook-Token")
            or request.query.get("token")
            or ""
        ).strip()

    @staticmethod
    def _format(event: str, data: Any) -> str:
        if not isinstance(data, dict):
            data = {"content": str(data)}
        post = data.get("post") if isinstance(data.get("post"), dict) else {}
        comment = data.get("comment") if isinstance(data.get("comment"), dict) else {}

        def pick(*values: Any) -> str:
            for value in values:
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""

        title = pick(data.get("title"), post.get("title"), data.get("subject"))
        content = pick(data.get("content"), comment.get("content"), data.get("text"))
        url = pick(data.get("url"), data.get("link"), post.get("url"))
        author = pick(data.get("author"), comment.get("author"), post.get("author"))
        if len(content) > 300:
            content = content[:300] + "…"
        lines = [f"【{event}】"]
        if title:
            lines.append(title)
        if author:
            lines.append(f"作者：{author}")
        if content:
            lines.append(content)
        if url:
            lines.append(url)
        if len(lines) == 1:
            lines.append(json.dumps(data, ensure_ascii=False)[:300])
        return "\n".join(lines)

    async def handle(self, request: web.Request) -> web.Response:
        event = request.match_info.get("event", "")
        item = self.find_by_token(self._token(request))
        if item is None:
            logger.warning("[webhook] token 无效（event=%s）", event)
            return web.json_response({"ok": False, "error": "invalid token"}, status=401)
        data: Any = {}
        if request.can_read_body:
            try:
                if request.content_type == "application/json":
                    data = await request.json()
                else:
                    data = dict(await request.post())
            except Exception:
                data = {}
        session = str(item.get("session") or "").strip()
        if not session:
            return web.json_response({"ok": False, "error": "no session"}, status=400)
        try:
            await self.context.send_message(
                session, MessageChain([Plain(self._format(event, data))])
            )
        except Exception as exc:
            logger.warning("[webhook] 转发失败：%s", exc)
            return web.json_response({"ok": False, "error": str(exc)}, status=500)
        logger.info("[webhook] %s -> %s", event, session[:30])
        return web.json_response({"ok": True})

    # -- 指令 ---------------------------------------------------------------
    @filter.command("webhook")
    async def webhook(self, event: AstrMessageEvent, args: GreedyStr):
        parts = str(args or "").strip().split()
        sub = parts[0].lower() if parts else "add"
        if sub == "add":
            name = parts[1] if len(parts) > 1 else f"hook-{len(self.hooks()) + 1}"
            if self.find(name):
                await event.send(MessageChain([Plain(f"已存在：{name}")]))
                return
            hooks = self.hooks()
            hooks.append(
                {
                    "__template_key": "hook",
                    "name": name,
                    "session": event.unified_msg_origin,
                    "token": "",
                    "enabled": True,
                }
            )
            self.config["webhooks"] = hooks
            self.save()
            base = str(
                self.config.get("public_base_url")
                or f"http://{self.config.get('host') or '127.0.0.1'}:{self.port or 16199}"
            )
            await event.send(
                MessageChain(
                    [
                        Plain(
                            f"已创建：{name}\n绑定会话：{event.unified_msg_origin}\n"
                            "token 待补：/webhook set 名称 <token>\n"
                            f"服务端「Koishi 地址」填：{base}"
                        )
                    ]
                )
            )
            return
        if sub == "set":
            if len(parts) < 3:
                await event.send(MessageChain([Plain("用法：/webhook set <名称> <token>")]))
                return
            item = self.find(parts[1])
            if item is None:
                await event.send(MessageChain([Plain(f"没有找到：{parts[1]}")]))
                return
            item["token"] = parts[2]
            self.save()
            await event.send(MessageChain([Plain(f"已写入 {parts[1]} 的 token")]))
            return
        if sub == "list":
            hooks = self.hooks()
            if not hooks:
                await event.send(MessageChain([Plain("暂无记录")]))
                return
            lines = ["Webhook 记录："]
            for item in hooks:
                token = str(item.get("token") or "")
                lines.append(
                    f"- {item.get('name')} token={'已填' if token else '待补'} 会话={item.get('session')}"
                )
            await event.send(MessageChain([Plain("\n".join(lines))]))
            return
        if sub == "del":
            if len(parts) < 2:
                await event.send(MessageChain([Plain("用法：/webhook del <名称>")]))
                return
            item = self.find(parts[1])
            if item is None:
                await event.send(MessageChain([Plain(f"没有找到：{parts[1]}")]))
                return
            self.config["webhooks"] = [h for h in self.hooks() if h is not item]
            self.save()
            await event.send(MessageChain([Plain(f"已删除：{parts[1]}")]))
            return
        await event.send(
            MessageChain([Plain("用法：/webhook add|set|list|del")])
        )
