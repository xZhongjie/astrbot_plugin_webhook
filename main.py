"""Webhook 配置插件。

在群里发送 /webhook add 即可在插件配置项的 webhooks 列表里新增一条记录：
  * 自动生成 token
  * webhook_url 留空，作为“待补信息”
之后在 WebUI 配置里补地址，或用 /webhook fill 直接补。
"""

from __future__ import annotations

from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr


class WebhookConfigPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

    # -- 配置项读写 ---------------------------------------------------------
    def hooks(self) -> list[dict]:
        raw = self.config.get("webhooks")
        if not isinstance(raw, list):
            raw = []
        return [item for item in raw if isinstance(item, dict)]

    def save(self) -> None:
        try:
            self.config["webhooks"] = self.hooks()
            self.config.save_config()
        except Exception as exc:
            logger.warning("[webhook] 保存配置失败：%s", exc)

    def find(self, name: str) -> dict | None:
        for item in self.hooks():
            if str(item.get("name") or "") == name:
                return item
        return None

    def base_url(self) -> str:
        base = str(self.config.get("public_base_url") or "").strip().rstrip("/")
        if base:
            return base
        return "https://请填写你的域名"

    # -- 指令 ---------------------------------------------------------------
    @filter.command("webhook")
    async def webhook(self, event: AstrMessageEvent, args: GreedyStr):
        parts = str(args or "").strip().split()
        sub = parts[0].lower() if parts else "add"

        if sub == "add":
            name = parts[1] if len(parts) > 1 else f"hook-{len(self.hooks()) + 1}"
            if self.find(name):
                await event.send(MessageChain([Plain(f"已存在同名记录：{name}")]))
                return
            item = {
                "__template_key": "hook",
                "name": name,
                "webhook_url": "",
                "token": "",
                "enabled": True,
            }
            hooks = self.hooks()
            hooks.append(item)
            self.config["webhooks"] = hooks
            self.save()
            await event.send(
                MessageChain(
                    [
                        Plain(
                            f"已创建待补记录：{name}\n"
                            "webhook_url 和 token 均为空，等待补充。\n"
                            "补法一：WebUI 插件配置 → webhooks → 编辑该条目\n"
                            f"补法二：/webhook fill {name} <地址> <你的token>"
                        )
                    ]
                )
            )
            return

        if sub == "list":
            hooks = self.hooks()
            if not hooks:
                await event.send(MessageChain([Plain("暂无 Webhook 记录，发送 /webhook add 创建")]))
                return
            lines = ["Webhook 记录："]
            for item in hooks:
                name = item.get("name") or "?"
                url = str(item.get("webhook_url") or "").strip()
                token = str(item.get("token") or "")
                has_token = bool(str(item.get("token") or ""))
                state = "已补" if (url and has_token) else "待补"
                lines.append(
                    f"- {name} [{state}] token={'已填' if token else '（空）'} url={url or '（空）'}"
                )
            await event.send(MessageChain([Plain("\n".join(lines))]))
            return

        if sub == "fill":
            if len(parts) < 3:
                await event.send(MessageChain([Plain("用法：/webhook fill <名称> <地址> [token]")]))
                return
            name, url = parts[1], parts[2]
            token = parts[3] if len(parts) > 3 else ""
            item = self.find(name)
            if item is None:
                await event.send(MessageChain([Plain(f"没有找到记录：{name}")]))
                return
            item["webhook_url"] = url
            if token:
                item["token"] = token
            self.save()
            await event.send(MessageChain([Plain(f"已补全 {name} 的 webhook 地址{'和 token' if token else ''}")]))
            return

        if sub == "del":
            if len(parts) < 2:
                await event.send(MessageChain([Plain("用法：/webhook del <名称>")]))
                return
            name = parts[1]
            item = self.find(name)
            if item is None:
                await event.send(MessageChain([Plain(f"没有找到记录：{name}")]))
                return
            hooks = [h for h in self.hooks() if h is not item]
            self.config["webhooks"] = hooks
            self.save()
            await event.send(MessageChain([Plain(f"已删除：{name}")]))
            return

        await event.send(
            MessageChain(
                [
                    Plain(
                        "用法：\n"
                        "/webhook add [名称]   生成待补记录（token 自动生成）\n"
                        "/webhook list         查看记录\n"
                        "/webhook fill 名称 地址  补 webhook 地址\n"
                        "/webhook del 名称     删除"
                    )
                ]
            )
        )
