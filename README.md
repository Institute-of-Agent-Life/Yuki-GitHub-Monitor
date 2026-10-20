# Yuki GitHub Monitor

Yuki 的 GitHub 仓库监控插件。定时读取仓库事件，把中文摘要、Push / Release 卡片和可选的 Agent 任务投递到 Yuki 的群聊或私聊。

本仓库从 [Yuki](https://github.com/YuanYeYouTao/Yuki) 的 `plugins/github-monitor` 独立提取，保留原插件历史和 AGPL-3.0-only 许可证。插件 ID 仍为 `github-monitor`，迁移代码目录不更换已保存的配置、队列、授权或通知回执。

## 功能

- 同时监控多个公开或私有仓库，并向多个目标投递。
- 支持 Push、Pull Request、Issue、Comment、Review、Release、Discussion、Fork、Star。
- Push 和 Release 生成 1200×630 PNG 卡片；其他事件使用中文文本摘要。
- 首次启用建立当前基线；条件请求、事件去重和持久队列保留原游标与目标快照。
- 已接纳队列逐步排空，不必等待下一次 GitHub 轮询；已完成目标沿原回执恢复。
- 可选择让 Yuki 处理事件，也可只发送文本和卡片。

## 运行要求

- Python 3.12，Yuki `>=3.9.0,<4.0`，Plugin API `7.0`。
- Host 可以访问 `api.github.com`，并提供 Pillow、时区资料和中文字体。Yuki 镜像已包含这些依赖。
- 公开仓库可匿名读取。私有仓库需要可读取目标仓库的 GitHub Token；推荐 Fine-grained Token，仅授权所需仓库的 Metadata / Contents 读取权限。

## 安装

在 **Yuki Host** 的插件目录中克隆本仓库，目录内应直接包含 `plugin.toml` 和 `github_monitor/`：

```bash
git clone https://github.com/Institute-of-Agent-Life/Yuki-GitHub-Monitor.git plugins/github-monitor
```

已有内置版本时，在停 Bot 后用此仓库替换原代码目录，保留 Host 的数据和配置。不要同时加载两份 `github-monitor`。容器运行用户须能读取源码、遍历目录；插件目录挂载仍沿 Host 的现有部署配置。

归档解包若受到 `umask 077` 影响，可只修正代码目录的读取和遍历权限：

```bash
chmod a+rx plugins/github-monitor
chmod -R a+rX plugins/github-monitor/github_monitor
chmod a+r plugins/github-monitor/plugin.toml plugins/github-monitor/doctor.py
```

Token 继续保存在 Host Secret 配置中，不放入上述源码目录。

在 **Host 的 `.env`** 配置：

```dotenv
PLUGIN_SYSTEM_ENABLED=true
PLUGIN_DIRECT_COMMAND_BINDINGS={"/github":"github-monitor:github"}
YUKI_PLUGIN__GITHUB_MONITOR__GITHUB_TOKEN=github_pat_replace_with_your_token
```

Token 可省略。已有直达命令时，将 `/github` 合并进原 JSON。真实 Token 由 Host Secret 通道提供，不存入本仓库、插件普通配置或聊天消息。

更新环境或挂载后，按 Host 部署流程只重启 Bot，再执行在线管理命令。

Host 在线管理 CLI 使用环境中的 `YUKI_CONTROL_CREDENTIAL`，`ADMIN_API_URL` 指向实际管理 API；凭据不要放在命令行参数中。在 Host 环境执行：

```bash
yuki plugin validate plugins/github-monitor
yuki plugin discover
yuki plugin inspect github-monitor
yuki plugin approve github-monitor --permission background.worker --permission network.http.allowlisted --permission storage.private --permission plugin.config.read --permission plugin.config.write --permission command.register --permission notification.publish --permission notification.agent --permission media.artifact.create
yuki plugin enable github-monitor
yuki plugin doctor github-monitor
```

批准的九项权限与 `plugin.toml` 一致。权限分别用于后台轮询、GitHub 只读 HTTP、插件私有状态、配置读写、命令注册、确定性通知、可选 Agent 任务和卡片媒体。仅启用所需并已审阅的权限；更新后若 Host 要求重新批准，按实际 Manifest 批准。

## 添加订阅

命令由 Host 的 Person 超级管理员执行。`target_id` 使用 **内部 Space / Person ID**，不接受 QQ / TG 群号或账号来代替人物身份：

```text
/github add owner/repo group:<Space-ID>
/github add owner/repo private:<Person-ID>
```

同一仓库可添加多个目标。群 topic 或同一人物的多个私聊入口可显式指定原 Conversation：

```text
/github add owner/repo group:<Space-ID>:conversation:<Conversation-ID>
/github add owner/repo private:<Person-ID>:conversation:<Conversation-ID>
```

省略 Conversation 时，Host 使用当前或唯一真实入口；有多个候选时需明确选择。Host 决定平台和物理路由，插件不另存 QQ / TG 发送链。已入队请求保持原入口、来源和回执。

## 命令

| 命令 | 作用 |
| --- | --- |
| `/github status` | 仓库、轮询、失败、限额和 Outbox 状态 |
| `/github repos` | 仓库、启停状态和目标 |
| `/github add owner/repo group:<Space-ID>` | 添加群目标 |
| `/github add owner/repo private:<Person-ID>` | 添加私聊目标 |
| `/github remove owner/repo group:<Space-ID>` | 移除群目标 |
| `/github remove owner/repo private:<Person-ID>` | 移除私聊目标 |
| `/github pause owner/repo` | 暂停轮询和队列排空，保留原状态 |
| `/github resume owner/repo` | 恢复轮询和排空 |
| `/github sync owner/repo baseline` | 显式重新建立当前基线 |
| `/github sync owner/repo replay_recent` | 显式回放最近事件 |
| `/github test owner/repo` | 发送本地合成 Push 通知，不访问 GitHub、不推进真实游标 |
| `/github events owner/repo` | 当前允许的事件类型 |
| `/github rate-limit` | 最近 GitHub API 限额 |
| `/github outbox` | 通知与后台任务状态 |

`test` 和 `replay_recent` 都会发送真实通知。日常排障使用 `status`、`outbox` 和只读观察。`sync` 在原队列未完成或存在 gap 时保留原事实，不删除旧请求追赶新事件。

## 配置与观察

Host 使用插件注册的配置 schema：

```bash
yuki plugin configuration github-monitor
yuki plugin configure github-monitor config.json --revision <原版本>
yuki plugin observe github-monitor --limit 10
```

`config.json` 格式为 `{"scope_type":"global","owner_id":null,"values":{...}}`；先读当前配置和 revision，再按 schema 修改。`observe` 只读本地队列、游标、诊断和 Host 通知状态，不访问 GitHub，也不返回已准备通知的正文。

| 配置 | 默认值 | 含义 |
| --- | --- | --- |
| `repositories` | `[]` | 仓库订阅及每个目标的策略 |
| `poll_interval_seconds` | `60` | GitHub 轮询间隔 |
| `max_events_per_poll` | `50` | 每轮队列处理量 |
| `coalesce` | `true` | 合并可合批的相邻 Create / Delete / Watch / Fork |
| `request_timeout_seconds` | `20` | GitHub HTTP 超时 |

完整字段、默认值和校验以 [`github_monitor/config.py`](github_monitor/config.py) 的 `GitHubMonitorConfig` / `RepositorySubscription` 为准。订阅可过滤事件类型、分支、Actor、Bot、Draft PR；每个目标分别设置 `send_text`、`send_card`、`ask_agent`。

## 队列与回执

GitHub event ID、accepted / committed cursor、原始事件指纹、pending / inflight 和原目标快照保存在 Host 的插件状态中。队列严格按原事件顺序处理，相邻合批不改变原成员 ID。

准备好的请求在首次发送前冻结目标、正文、媒体、Agent intent 和幂等键。首次尝试后恢复同一请求；媒体过期或当前订阅变化不会抢在原 Host 回执之前拒绝恢复。结果不确定的发送保留 `uncertain`，不盲目重发。`yuki plugin retry-outbox` 也沿 Host 的原回执规则处理。

GitHub 客户端只读取 `api.github.com`。401 表示 Token 无效；403 / 429 按权限和限额处理。卡片只用本地字体与图形，不下载远程图片或字体。Agent 任务经 Host 的统一后台执行入口运行。

## 离线队列 doctor

doctor 读取 Host 数据库中的队列与通知计数。先停止 Bot 和其他写库 worker，明确传入实际数据库 URL；相对路径按 **当前工作目录** 解析，不读取 Host `.env`、不导入 Host 配置类：

```bash
uv run python doctor.py --database-url sqlite+aiosqlite:////absolute/path/to/qq_ai_bot.db
```

Compose 环境沿原挂载运行，并用实际数据库路径替换示例：

```bash
docker compose run --rm --no-deps --entrypoint python bot \
  /app/plugins/github-monitor/doctor.py \
  --database-url sqlite+aiosqlite:////app/data/qq_ai_bot.db
```

普通检查使用 SQLite `mode=ro`，路径不存在时不会创建空库，只输出无正文计数。若从旧队列首次导入，可在同样停写条件下显式加 `--apply-legacy-import`；只在新 queue 缺失时写入确定性导入结果，保留旧行、游标和通知身份。

非零退出码表示报告中仍有待处理事项，需结合原队列和回执处理；它不是要求取消所有未完成工作的升级门槛。Host 的 `yuki plugin doctor github-monitor` 检查安装状态，与此停写队列诊断用途不同。

## 独立开发与验证

```bash
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python doctor.py --help
```

当前 SDK 7.0 随 `yuki` 分发，本仓库 dev 依赖固定到 Yuki `ed1615e145daf75bcc002762a27e93f7ebfa818b` 源码归档，由 `uv.lock` 锁定；不复制 SDK、不引用父目录或本机 Host 源码。运行时使用实际 Host 提供的 SDK。CI 在干净环境安装同一依赖；pytest 包含公开 SDK 的完整加载、注册、启动、停止契约测试，不需要 Host 人格或数据库配置。测试使用 SDK Fake Host，不需要 Token，不调用真实 GitHub、模型或聊天发送。

## 许可证

AGPL-3.0-only。原始版权与来源见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
