# astrbot_plugin_webhook

在群里用聊天命令创建 Webhook 记录，自动在插件配置项里生成待补信息（token 已生成，地址待补）。

## 指令

```
/webhook add [名称]       生成一条待补记录，token 自动生成
/webhook list             查看所有记录（已补 / 待补）
/webhook fill 名称 地址    直接补全 webhook 地址
/webhook del 名称          删除记录
```

## 流程

1. 群里发 `/webhook add 我的钩子`
2. 插件在配置项 `webhooks` 里新增一条：

   | 字段 | 值 |
   | --- | --- |
   | name | 我的钩子 |
   | webhook_url | （空，待补） |
   | token | 自动生成的随机值 |
   | enabled | true |

3. 打开 WebUI → 插件配置 → Webhooks 列表，编辑该条目的 `webhook_url`
4. 或直接聊天补：`/webhook fill 我的钩子 https://example.com/webhook/xxx`

## 配置

| 键 | 说明 |
| --- | --- |
| `public_base_url` | 生成提示地址用，可留空 |
| `webhooks` | 记录列表，由命令自动维护 |
