<p align="center">
  <img src="frontend/public/aether_adaptive.svg" width="120" height="120" alt="Aether Logo">
</p>

<h1 align="center">Aether</h1>

<p align="center">
  <strong>基于原版 Aether 的公开 Fork，可直接用于自托管部署与二次维护</strong><br>
  支持 Claude / OpenAI / Gemini 及其 CLI 客户端的统一接入、格式转换、正反向代理与多提供商治理
</p>

<p align="center">
  <a href="#项目定位">项目定位</a> •
  <a href="#与原-aether-的不同点">与原 Aether 的不同点</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#部署方式">部署方式</a> •
  <a href="#注意事项">注意事项</a>
</p>

---

## 项目定位

本仓库是 [`fawney19/Aether`](https://github.com/fawney19/Aether) 的公开 Fork，当前维护目标不是替代上游，而是在保留上游能力模型的前提下，提供一个可以直接部署、直接发布、直接继续做自定义维护的分发版本。

如果你是第一次接触 Aether，建议先理解它的核心定位：

- 自托管 AI API 网关
- 统一接入 Claude / OpenAI / Gemini 等不同协议和客户端
- 支持多提供商、多账号、多 Key 的管理与调度
- 提供反向代理、格式转换、认证治理和运维能力

如果你更关心原始设计背景、功能演进和通用说明，优先阅读上游仓库和上游 README：

- 原项目仓库: <https://github.com/fawney19/Aether>
- 原项目 README: <https://github.com/fawney19/Aether/blob/master/README.md>

## 与原 Aether 的不同点

这个 Fork 当前和原版 Aether 的主要差异点如下：

1. 发布链路独立

   本仓库已经打通自己的 GitHub Releases 和 GitHub Container Registry 发布流程，不再依赖上游仓库的发布命名空间。

   当前 Fork 的发布入口：

   - 仓库地址: <https://github.com/zbsdsb/Aether>
   - Releases: <https://github.com/zbsdsb/Aether/releases>
   - 容器镜像命名空间: `ghcr.io/zbsdsb/*`

2. 部署入口面向 Fork 使用者

   原仓库的 README 更多是围绕上游主仓展开；本 README 会明确说明：

   - 从哪个仓库克隆
   - 预构建镜像该用哪个命名空间
   - 升级和回滚时应引用哪个镜像
   - 上游资料应该去哪里看

3. 维护目标不同

   原项目以作者主仓持续演进为主；本 Fork 更偏向“可直接部署 + 可直接二次改造 + 可保留自用差异”的维护方式。

4. 文档职责重新划分

   - 上游 README 负责原始项目背景、能力说明和长期参考
   - 本 README 负责 Fork 的定位、部署方法和使用注意事项

## 快速开始

如果你只是想把这个 Fork 快速跑起来，建议直接使用预构建镜像。

```bash
git clone https://github.com/zbsdsb/Aether.git
cd Aether

cp .env.example .env
python generate_keys.py

# 把 generate_keys.py 生成的密钥写入 .env
# 同时补齐管理员账号、数据库密码、Redis 密码等必填项

export APP_IMAGE=ghcr.io/zbsdsb/aether:latest
docker compose pull
docker compose up -d
```

默认访问地址示例：

- Web UI: `http://<your-host>:8084`
- 应用端口由 `APP_PORT` 控制，默认是 `8084`

## 部署方式

### 1. Docker Compose，推荐

适合希望直接使用 Fork 发布产物的场景。

```bash
# 1. 克隆 Fork
git clone https://github.com/zbsdsb/Aether.git
cd Aether

# 2. 初始化配置
cp .env.example .env
python generate_keys.py

# 3. 编辑 .env
# 必填：DB_PASSWORD / REDIS_PASSWORD / JWT_SECRET_KEY / ENCRYPTION_KEY
#      ADMIN_EMAIL / ADMIN_USERNAME / ADMIN_PASSWORD

# 4. 指定 Fork 的镜像
export APP_IMAGE=ghcr.io/zbsdsb/aether:latest

# 5. 拉取并启动
docker compose pull
docker compose up -d
```

如果你希望固定到某个发布版本，也可以把 `latest` 换成明确 tag，例如：

```bash
export APP_IMAGE=ghcr.io/zbsdsb/aether:<release-tag>
docker compose pull
docker compose up -d
```

### 2. 本地构建部署

适合你已经在这个 Fork 上做了自己的代码修改，想直接从本地源码构建。

```bash
git clone https://github.com/zbsdsb/Aether.git
cd Aether

cp .env.example .env
python generate_keys.py

git pull
./deploy.sh
```

### 3. 本地开发

适合前后端联调、调试、继续开发功能。

```bash
# 启动依赖
docker compose -f docker-compose.build.yml up -d postgres redis

# 后端
uv sync
./dev.sh

# 前端
cd frontend
npm install
npm run dev
```

## Aether Hub / Aether Proxy

本仓库除了主应用外，还包含两个配套组件：

- `aether-hub`
- `aether-proxy`

### Aether Proxy

`aether-proxy` 适合部署在海外 VPS 或其他网络出口节点，用于给 Aether 实例中转 API 流量。

你可以通过以下入口获取：

- Proxy Release 页面: <https://github.com/zbsdsb/Aether/releases>
- Proxy 说明文档: [aether-proxy/README.md](aether-proxy/README.md)

### Aether Hub

`aether-hub` 当前主要作为配套构建/分发组件存在，已在 Fork 中独立发布：

- Hub Release 页面: <https://github.com/zbsdsb/Aether/releases>

对于普通 Docker Compose 使用者，通常不需要单独手工部署 `aether-hub`。

## 环境变量

### 必填配置

| 变量 | 说明 |
|------|------|
| `DB_PASSWORD` | PostgreSQL 数据库密码 |
| `REDIS_PASSWORD` | Redis 密码 |
| `JWT_SECRET_KEY` | JWT 签名密钥，使用 `generate_keys.py` 生成 |
| `ENCRYPTION_KEY` | API Key 加密密钥，更换后通常需要重新配置 Provider Key |
| `ADMIN_EMAIL` | 初始管理员邮箱 |
| `ADMIN_USERNAME` | 初始管理员用户名 |
| `ADMIN_PASSWORD` | 初始管理员密码 |

### 常用可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | `8084` | Web / API 暴露端口 |
| `API_KEY_PREFIX` | `sk` | 平台生成的 API Key 前缀 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `GUNICORN_WORKERS` | `2` | Gunicorn worker 数 |
| `DB_PORT` | `5432` | PostgreSQL 端口 |
| `REDIS_PORT` | `6379` | Redis 端口 |

## 升级与回滚

### 升级前备份，强烈建议

```bash
docker compose exec postgres pg_dump -U postgres aether | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### 使用 Fork 镜像升级

```bash
export APP_IMAGE=ghcr.io/zbsdsb/aether:latest
docker compose pull
docker compose up -d
```

### 使用指定版本回滚

```bash
docker compose stop app

# 恢复数据库（推荐使用备份）
docker compose exec -T postgres psql -U postgres -c "DROP DATABASE aether; CREATE DATABASE aether;"
gunzip < backup_xxx.sql.gz | docker compose exec -T postgres psql -U postgres -d aether

# 切回指定版本镜像
export APP_IMAGE=ghcr.io/zbsdsb/aether:<release-tag>
docker compose up -d
```

如果你更习惯按 digest 回滚，也可以先记录当前镜像的 RepoDigest：

```bash
docker inspect ghcr.io/zbsdsb/aether:latest --format '{{index .RepoDigests 0}}'
```

## 注意事项

1. 本仓库不是原作者主仓

   如果你需要追踪原始设计、上游更新、原作者发布动态，请直接查看：

   - <https://github.com/fawney19/Aether>
   - <https://github.com/fawney19/Aether/blob/master/README.md>

2. 部署时请明确镜像来源

   Fork 的预构建镜像命名空间是：

   - `ghcr.io/zbsdsb/aether`
   - `ghcr.io/zbsdsb/aether-proxy`

   不要默认继续沿用上游 README 中的 `ghcr.io/fawney19/*`。

3. 主应用发布依赖 Hub Release

   这个 Fork 的主应用镜像发布流程会先读取最新的 `hub-v*` release；因此如果你后续自己改 CI 或自己发版，需要先确保 `hub` 发布存在。

4. 首次部署必须先生成密钥

   `JWT_SECRET_KEY` 和 `ENCRYPTION_KEY` 不建议手写；优先用 `python generate_keys.py` 生成，再写回 `.env`。

5. 升级前先备份数据库

   即使镜像升级本身可回退，数据库迁移也未必天然可逆。生产环境务必先做 `pg_dump`。

6. Proxy 是可选组件

   如果你的 Aether 实例本身已经具备合适的出网能力，不一定需要额外部署 `aether-proxy`。

## 许可证

本项目采用 [Aether 非商业开源许可证](LICENSE)。允许个人学习、教育研究、非盈利组织及企业内部非盈利性质的使用；禁止用于盈利目的。商业使用请联系获取商业许可。

## 联系作者

当前 Fork 仓库地址：

- <https://github.com/zbsdsb/Aether>

如需了解原项目作者信息，请参考上游仓库中的相关说明和资源文件。
