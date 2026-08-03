# 校园社团智能管理系统

基于 Django + Vue 3 的全栈 Web 应用，为校园社团提供成员管理、招新、帖子交流、AI 辅助等一站式服务。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.12、Django 5.2、MySQL 8 |
| 前端 | Vue 3（Composition API）、Element Plus、Vite |
| 认证 | Django Session + HttpOnly Cookie |
| AI | DeepSeek API（在线调用，不持久化历史） |
| 测试 | pytest（后端）、Vitest（前端） |
| 包管理 | uv（Python）、npm（Node.js） |

## 环境要求

| 工具 | 最低版本 |
|------|----------|
| Python | 3.12 |
| uv | 0.11+ |
| Node.js | 22.12+ |
| npm | 10 |
| Docker Desktop | 任意近期版本 |
| MySQL 镜像 | `mysql:8` |

## 1. 初始化本地配置

在 `code/` 目录复制环境变量示例，然后按实际情况修改秘密值：

```powershell
Copy-Item .env.example .env
```

**`.env` 文件说明：**

### MySQL 数据库

| 变量 | 说明 | 示例 |
|------|------|------|
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | 自行设置 |
| `MYSQL_DATABASE` | 数据库名 | `student_club` |
| `MYSQL_USER` | 应用数据库用户 | `student_club_app` |
| `MYSQL_PASSWORD` | 应用数据库密码 | 自行设置 |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_HOST` | MySQL 主机 | `127.0.0.1` |
| `TZ` | 时区 | `Asia/Shanghai` |

### Django

| 变量 | 说明 | 示例 |
|------|------|------|
| `DJANGO_SECRET_KEY` | Django 密钥（用于 Session 签名等） | 自行生成 |
| `DJANGO_DEBUG` | 调试模式 | `true`（开发）/ `false`（生产） |
| `DJANGO_ALLOWED_HOSTS` | 允许的主机名 | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 信任的跨域来源（已不使用 CSRF） | `http://localhost:5174` |

### DeepSeek AI

| 变量 | 说明 | 示例 |
|------|------|------|
| `DEEPSEEK_API_URL` | DeepSeek API 完整端点 | `https://api.deepseek.com/v1/chat/completions` |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 从 DeepSeek 平台获取 |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-chat` |
| `AI_MAX_CONTENT_CHARS` | AI 单次最大输入字符数 | `8000` |

> ⚠️ `.env` 已被 `.gitignore` 忽略，**不得提交到版本库**。

## 2. 启动 MySQL

```powershell
docker compose up -d
docker compose ps   # 确认容器运行中
```

MySQL 只监听 `127.0.0.1:3306`，数据保存在独立命名卷 `student-club-mysql-data`。

停止容器：

```powershell
docker compose stop     # 暂停
docker compose down -v  # 删除容器和数据卷
```

## 3. 初始化并启动后端

```powershell
cd backend
uv sync                                         # 安装依赖
uv run python manage.py migrate                 # 执行数据库迁移
uv run python manage.py create_admin            # 创建管理员账号
uv run python manage.py runserver 127.0.0.1:8000
```

管理员创建命令会提示输入用户名和密码，或通过参数指定：

```powershell
uv run python manage.py create_admin --username admin --password YourPassword123
```

后端使用 Django Session + `HttpOnly` 会话 Cookie 认证，不使用 Bearer Token。已移除 CSRF 防护（本地毕业设计项目，无实际跨站威胁）。

## 4. 初始化并启动前端

另开一个终端：

```powershell
cd frontend
npm ci              # 安装依赖
npm run dev         # 启动开发服务器
```

浏览器访问 `http://127.0.0.1:5173`（如 5173 被占用会自动切换到 5174）。Vite 将 `/api` 和 `/media` 请求代理到 `http://127.0.0.1:8000`。

## 5. 验证命令

### 后端

```powershell
cd backend
uv run python manage.py check                          # 系统检查
uv run python manage.py makemigrations --check --dry-run # 迁移一致性
uv run pytest                                           # 全量测试（541 项）
uv run pip-audit                                        # 依赖安全审计
```

### 前端

```powershell
cd frontend
npm test                              # 单元测试
npm run type-check                    # TypeScript 类型检查
npm run build                         # 生产构建
npm audit --audit-level=high          # 依赖安全审计
```

### 项目根目录敏感值扫描

```powershell
# Windows PowerShell
Get-ChildItem -Recurse -Include *.py,*.vue,*.ts,*.md | Select-String -Pattern "sk-[a-zA-Z0-9]{20,}" -SimpleMatch
```

## 6. 项目结构

```
code/
├── .env.example              # 环境变量示例
├── .env                      # 本地配置（不提交）
├── .gitignore
├── compose.yaml              # Docker MySQL
├── README.md
│
├── backend/
│   ├── config/               # Django 配置、URL 路由
│   ├── core/                 # 统一响应、异常处理
│   ├── users/                # 用户模型、认证、管理员用户管理
│   ├── clubs/                # 核心业务（社团、成员、招新、帖子、AI 等）
│   ├── tests/                # 全量测试（21 个文件，541 项）
│   ├── media/                # 上传文件（Logo）
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── api/              # API 请求层（auth.ts、clubs.ts）
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── views/            # 页面组件（28 个）
│   │   ├── composables/      # 组合式函数
│   │   ├── App.vue           # 根组件 + 路由分发
│   │   └── main.ts           # 入口
│   └── package.json
│
└── docs/
    ├── 需求问答-修改版(严格按要求修改).md   # 唯一需求基线
    ├── 阶段一_系统设计/                   # 设计文档
    └── 阶段二_开发计划/                   # 实现说明与验收记录
```

## 7. 功能清单

### 用户与认证
- [x] 学生注册、登录（Session + HttpOnly Cookie）
- [x] 本人资料查看与修改
- [x] 管理员查看学生列表、重置密码
- [x] 管理员停用/恢复学生账号（含最后负责人保护）

### 社团管理
- [x] 管理员创建社团（指定初始负责人 + Logo 上传）
- [x] 管理员和负责人维护社团资料
- [x] 管理员增减负责人（最后有效负责人保护）
- [x] 管理员注销社团

### 招新与入社
- [x] 负责人发布、修改、提前结束招新
- [x] 学生查看有效招新、提交入社申请
- [x] 负责人审核申请（通过/拒绝）
- [x] 入社申请结果通知

### 成员关系
- [x] 学生主动退出社团
- [x] 负责人移除普通成员
- [x] 历史成员关系保留

### 内容交流
- [x] 公告：负责人发布/修改/置顶/删除，成员查看
- [x] 帖子：成员发布/查看，负责人置顶
- [x] 回复：成员回复帖子，作者收到通知
- [x] 点赞：成员点赞/取消点赞帖子
- [x] 逻辑删除：作者/负责人/管理员按权限删除

### 评价与反馈
- [x] 社团评价：成员提交/修改，管理员查看
- [x] 意见反馈：成员提交，负责人处理
- [x] 内容举报：成员举报，负责人处理并通知

### AI 功能
- [x] 帖子 AI：总结/提取观点/基于帖子问答
- [x] AI 文档生成：负责人生成公告/招新/介绍草稿

### 数据概览
- [x] 管理员工作台：用户总数、正常社团数
- [x] 负责人概览：6 项统计数据
- [x] 学生概览：加入社团数、入社申请记录

## 8. 角色与页面

| 角色 | 可访问页面 |
|------|-----------|
| 未登录 | `/register` 注册、`/login` 登录 |
| 学生 | `/student` 个人中心、`/student/clubs` 社团浏览、社团详情、招新、申请、评价、反馈、通知、资料编辑、我的社团 |
| 负责人 | `/leader/clubs/:id` 工作台（概览 + 招新 + 公告 + 帖子 + 成员 + 申请 + 反馈 + 举报 + AI 文档） |
| 管理员 | `/admin` 工作台、`/admin/users` 用户管理、`/admin/clubs` 社团管理、`/admin/recruitments` 招新记录、`/admin/applications` 入社申请、`/admin/memberships` 成员关系、`/admin/evaluations` 全部评价、`/admin/posts` 全部帖子、`/admin/replies` 全部回复 |

## 9. API 概览

共计 69 个 API 端点，统一使用 `{ code, message, data }` 响应格式，列表接口统一 `{ items, page, page_size, total }`。

完整 API 设计见 `docs/阶段一_系统设计/05_API接口设计.md`。

## 10. 当前已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| Element Plus 全量引入导致包体积 > 500 kB | 生产部署时首屏加载偏大 | 可优化为按需引入 |
| MySQL 并发测试偶发死锁 | 仅测试环境偶现，不影响正常使用 | 非阻塞 |
| 管理员创建社团时学生选择列表上限 100 条 | 大量学生时需滚动分页查找 | 可优化 |
| 本地开发密码强度较低 | 仅开发环境 | 不影响 |
| AI 功能依赖外部 DeepSeek API | 无网络或欠费时 AI 功能不可用 | 优雅降级 |

## 11. 设计文档

- 需求基线：`docs/需求问答-修改版(严格按要求修改).md`
- 角色权限矩阵：`docs/阶段一_系统设计/01_角色权限矩阵.md`
- 数据库设计：`docs/阶段一_系统设计/03_数据库概念设计.md`、`04_数据库逻辑设计.md`
- API 设计：`docs/阶段一_系统设计/05_API接口设计.md`
- 页面路由设计：`docs/阶段一_系统设计/06_页面菜单与路由设计.md`
- 开发计划与验收记录：`docs/阶段二_开发计划/01_垂直切片清单与逐片验收记录.md`
- 各切片实现说明：`docs/阶段二_开发计划/02_S00_*.md` ~ `17_S20_*.md`
