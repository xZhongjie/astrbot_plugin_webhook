# astrbot_plugin_webhook

接收评论/文章系统的 Webhook，转发到绑定的群。

## 服务端怎么填

服务端的「Koishi 地址」填**基地址**：

```
http://AstrBot所在服务器IP:6199
```

服务端会自动拼接：

```
/webhook/approved-post
/webhook/approved-comment
/webhook/pending-post
/webhook/pending-comment
```

不需要填路径。

## 使用步骤

1. 服务端页面创建令牌，复制 token
2. 在要接收通知的群里发：
   ```
   /webhook add 评论通知
   ```
3. 填入 token：
   ```
   /webhook set 评论通知 服务端生成的token
   ```
4. 服务端「Koishi 地址」填 `http://IP:6199`
5. 服务端配置 webhook 事件

## 请求鉴权

兼容三种：

- `Authorization: Bearer <token>`
- `X-Webhook-Token: <token>`
- `?token=<token>`

请求体支持 JSON / 表单，会提取 `title`、`content`、`url`、`author` 等字段。

## 配置

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `host` | `0.0.0.0` | 监听地址 |
| `port` | `6199` | 监听端口 |
| `public_base_url` | 空 | 对外展示地址 |
| `webhooks` | [] | 记录列表 |

## 注意

- 端口要在防火墙/安全组放行
- Docker 部署注意端口映射
- token 泄露后 `/webhook del` 删除
