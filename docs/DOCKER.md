# Docker Compose 部署

需要 Docker Engine 与 Docker Compose 插件。镜像构建会自动打包前端，不需要宿主机安装 Node.js、npm 或 Python。应用使用单个 Uvicorn worker，后台续期提醒与 Web 同时启动。

## 在新服务器部署

进入包含 Dockerfile 和 compose.yml 的 simkeep 目录，准备配置：

```bash
test -f .env || cp .env.example .env
chmod 600 .env
```

编辑 `.env`，将 `SIMKEEP_PUBLIC_URL` 改为实际访问地址，例如 `http://服务器IP:5180`。`SIMKEEP_PORT` 控制宿主机端口，默认 5180；改端口时同步修改公网地址。保持 HTTP 时使用 `SIMKEEP_SECURE_COOKIES=0`。每个用户登录网页的“通知设置”，点击“配置 Telegram / 配置邮件”保存自己的凭据；不需要修改 `.env` 或重启。`.env` 中的通知凭据仅作为可选公共默认服务。

```bash
docker compose up -d --build --wait
docker compose ps
```

访问 `http://服务器IP:5180/`，首次使用创建自己的账号。服务器防火墙需要允许选定的 TCP 端口。

默认 Compose 项目名为 `simkeep`，持久化卷为 `simkeep_simkeep-data`，数据库位于容器 `/app/data/simkeep.db`。保持项目名即可复用同一个卷。容器重启、镜像更新及普通 `docker compose down` 都会保留卷；`docker compose down -v` 会删除数据卷。

## 更新、配置与日志

更新代码并重新构建镜像：

```bash
docker compose up -d --build --wait
```

修改 `.env` 后重建容器加载新配置：

```bash
docker compose up -d --force-recreate --wait web
```

仅执行 `docker compose restart` 不会加载修改后的环境配置。日常查看或重启：

```bash
docker compose logs --tail=100 web
docker compose restart web
docker compose ps
```

容器设置 `unless-stopped` 自动重启，Docker 服务需要随服务器启动。镜像以 UID / GID 10001 运行，根文件系统只读，数据卷和临时目录可写。健康检查访问 `/api/health`，日志最多保留三份，每份 10 MB。`.env`、数据库、备份与测试文件均不进入镜像或公开静态目录。

## 备份

使用 SQLite backup API 获取一致的数据库备份：

```bash
docker compose exec web python scripts/backup.py
docker compose cp web:/app/data/backups ./docker-backups
```

备份保存在卷中的 `/app/data/backups/`，第二条命令复制到宿主机。复制出的备份包含账号、卡片、余额、历史、渠道设置以及用户在网页保存的 Bot Token / SMTP 密码，应存放在受保护的位置。迁移到另一台服务器时同时保留 `.env`，其中的可选公共服务密钥不在数据库备份中。个人配置会随数据卷或数据库备份一起恢复；旧版备份没有配置表时，应用启动自动补建。

## 恢复或导入已有 SQLite

先创建当前库备份，再停止应用。将选定的一致备份命名为当前项目目录下的 `restore.db`。不要直接复制运行中的主数据库而遗漏 WAL。

```bash
docker compose stop web
docker compose run --rm --no-deps -T --entrypoint python web scripts/restore.py --replace < restore.db
docker compose up -d --wait
```

恢复容器以应用用户读取标准输入，不需要 root 或修改宿主机备份权限。它检查数据库完整性与 SIMKEEP 表结构，临时生成恢复库后替换；未传 --replace 时会拒绝覆盖现有库。恢复容器只执行数据库操作，不启动提醒进程。使用 `docker compose -p 其他项目名` 时，以上所有命令也须带相同项目名。

## 从其他运行方式迁移

先用 SQLite backup API 创建一致性备份，保留原运行配置，然后停止旧进程。使用上面的“恢复或导入已有 SQLite”步骤导入 Docker 命名卷，再启动 web 容器。确认数据与通知设置后停用旧服务的自动启动；Docker 启动后的新数据以容器数据卷为准。

同一份 Telegram Bot 配置只运行一个提醒进程。不要同时运行旧服务和 Docker 容器，以免重复消费 Telegram 更新或重复安排提醒。
