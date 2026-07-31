# 校园社团智能管理系统

当前完成阶段二切片 S00：Docker MySQL、Django 后端骨架、Vue 3 前端骨架及基础验证工具。

## 环境要求

- Python 3.12
- uv 0.11 或更高版本
- Node.js 22.12 或更高版本
- npm 10
- Docker Desktop
- 本机已存在 `mysql:8` 镜像

## 1. 初始化本地配置

在 `code/` 目录复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

然后修改 `.env` 中的以下秘密值：

- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `DJANGO_SECRET_KEY`

`.env` 已被 `.gitignore` 忽略，不得提交。

## 2. 启动 MySQL

```powershell
docker compose up -d
docker compose ps
```

MySQL 只监听 `127.0.0.1:3306`，数据保存在独立命名卷 `student-club-mysql-data`。

停止容器：

```powershell
docker compose stop
```

## 3. 初始化并启动后端

```powershell
Set-Location backend
uv sync
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

后端使用 Django Session、`HttpOnly` 会话 Cookie，不使用 Bearer Token。

## 4. 初始化并启动前端

另开一个终端：

```powershell
Set-Location frontend
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 会把 `/api` 请求代理到 `http://127.0.0.1:8000`。

## 5. 验证命令

后端：

```powershell
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
uv run pip-audit
```

前端：

```powershell
npm test
npm run type-check
npm run build
npm audit --audit-level=high
```

## 当前范围

S00 不包含注册、登录、业务页面、社团或其他业务实体。
