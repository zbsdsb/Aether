# 仓库协作指南

## 项目结构与模块分工
`src/` 是 FastAPI 后端主目录，其中 `src/services/` 放领域逻辑，`src/api/` 放 HTTP 路由与适配层，`src/models/` 放共享 schema / ORM / Pydantic 模型。`frontend/src/` 是 Vue 3 管理后台，按 `components/`、`features/`、`stores/`、`views/` 分层。数据库迁移文件在 `alembic/versions/`。测试按层级放在 `tests/`（如 `api/`、`services/`、`unit/`、`e2e/`）。`aether-proxy/` 是独立的 Rust 隧道程序，相关改动应尽量局限在该子目录内。

## 构建、测试与开发命令
- `uv sync`：根据 `pyproject.toml` 与 `uv.lock` 安装后端依赖。
- `docker compose -f docker-compose.build.yml up -d postgres redis`：启动本地后端依赖。
- `./dev.sh`：加载 `.env` 并启动带热重载的后端，默认地址 `http://localhost:8084`。
- `uv run pytest` 或 `uv run pytest tests/api/test_admin_provider_routes.py`：运行后端测试。
- `cd frontend && npm install && npm run dev`：启动前端开发服务。
- `cd frontend && npm run type-check && npm run test:run`：Vue / TypeScript 改动的最小前端验证。
- `cd aether-proxy && cargo test`：验证 Rust 代理子项目。

## 编码风格与命名约定
Python 使用 4 空格缩进，遵循 Black / isort 风格，单行长度建议不超过 100 字符。路由文件保持轻薄，业务逻辑优先下沉到 `src/services/*`。Vue 组件使用 `<script setup>`，组件文件名使用 PascalCase；组合式函数与工具函数使用 camelCase，例如 `useProviderFilters.ts`。涉及前端改动时，提交前尽量运行 `cd frontend && npm run lint`。Rust 代码保持 `cargo fmt` 干净。

## 测试要求
后端测试使用 `pytest`；新增测试文件命名为 `test_*.py`，并尽量放在变更对应层级附近。前端测试使用 Vitest + `jsdom`，测试文件命名为 `*.spec.ts`。导入、Provider、异步任务相关改动优先补针对性回归测试，再考虑更大范围重构。如果 API 契约有变化，至少补一条 route 测试和一条 service 测试。

## 提交、发布与 PR 规则
最近历史采用 emoji 风格 Conventional Commit，例如 `✨ feat(import): ...`、`🐛 fix(provider): ...`、`📝 docs(readme): ...`。继续沿用该格式：`<emoji> <type>(scope): 中文摘要`。

PR 说明应包含：
- 用户可见变化是什么
- 实际运行过哪些命令
- 是否涉及迁移或 `.env` 影响
- 若修改了 `frontend/` 或后台页面，附上截图

无关的后端、前端、代理、发布链路改动应拆分成不同 PR。

### Push 与镜像发布补充规则
- 默认不要把“代码已经 `push`”视为这类仓库的最终完成态；如果用户要求同步远端发布结果，必须继续把镜像 / Release 链路跑完。
- 对这个 Fork，GitHub Packages / Releases 是否更新，取决于真实发布 workflow，而不是本地 `docker build`。
- 当用户要求“推到远端并把镜像也更新”时，完成标准应至少覆盖 GitHub Packages 中的这三项：
  - `aether`
  - `aether-base`
  - `aether-proxy`
- 其中：
  - `aether` 与 `aether-base` 由 `.github/workflows/docker-publish.yml` 负责
  - `aether-proxy` 由 `.github/workflows/build-proxy.yml` 负责
- 如果 plain `push` 不会自动触发这些 workflow（例如它们是 tag / `workflow_dispatch` 触发），代理不能停在“已 push”；需要继续补 tag 或手动触发 workflow，直到 Packages / Release 页面出现新的远端产物。
- 若本次改动只涉及主应用但用户明确要求“截图里这些 Packages 都要更新”，也应把 `aether-proxy` 的发布一并纳入交付边界，而不是自行缩小范围。

## 安全与配置提示
不要提交真实 `.env`、生成密钥、备份 JSON 或本地 verify 产物。以 `.env.example` 为基线，本地密钥使用 `python generate_keys.py` 生成。修改 Docker、CI、workflow 时要格外谨慎，因为这个 Fork 有自己的镜像与 Release 发布链路。
