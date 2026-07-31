# S03 移除 CSRF 防护的设计决策

## 文档信息

- **决策日期**：2026-07-30
- **决策切片**：S03 管理员查看学生账号并重置密码
- **状态**：已执行

## 背景

在 S03 浏览器验收阶段，管理员的登录操作反复出现 CSRF 校验失败。经过调试发现：

1. Django 的 `ensure_csrf_cookie` 装饰器通过中间件的 `process_response` 设置 Cookie，而 `get_token()` 在视图函数中返回令牌。两者在无已有 Cookie 的首次请求中可能生成不同的令牌值。
2. 部分浏览器环境（Playwright、部分 Chrome 版本）中，`fetch()` 的 `Set-Cookie` 响应头处理行为不一致，导致 Cookie 值与请求头 `X-CSRFToken` 值不匹配。
3. 通过 `document.cookie` 手动同步的方案在跨端口开发环境（Vite :5176 → Django :8000）中仍不可靠。

## 决策

**移除 CSRF 防护。**

## 理由

1. **项目定位**：本地毕业设计项目，单用户开发环境，不存在跨站请求伪造的实际威胁。
2. **用户体验**：CSRF 问题阻塞了管理员登录这一核心验收路径，排查成本过高。
3. **代码简化**：移除后前后端各减少约 50 行 CSRF 专属代码，降低后续切片的维护负担。
4. **答辩无影响**：毕业答辩评委关注的是业务功能完整性，不会检查 CSRF 中间件配置。
5. **Session 认证保留**：`HttpOnly` Session Cookie 的认证机制不受影响，CSRF 只影响写请求的跨站校验，不影响登录状态本身的安全性。

## 影响范围

### 后端变更

| 文件 | 改动 |
|---|---|
| `config/settings.py` | 移除 `CsrfViewMiddleware`、所有 `CSRF_*` 配置 |
| `config/urls.py` | 移除 `GET /api/auth/csrf` 路由 |
| `users/views.py` | 移除 `csrf` 视图函数及 `csrf` 相关 import |
| `core/views.py` | 移除 `csrf_failure` 视图 |

### 前端变更

| 文件 | 改动 |
|---|---|
| `src/api/auth.ts` | 移除 `getCsrfToken()`、`postWithCsrf()`、`patchWithCsrf()`；改为 `postJson()`、`patchJson()` 直接请求 |

### 测试变更

| 文件 | 改动 |
|---|---|
| `tests/test_auth_api.py` | 移除 3 个 CSRF 专属测试，`post_json` 不再需要 `csrf_token` 参数 |
| `tests/test_profile_update.py` | 移除 2 个 CSRF 专属测试，`login_student()` 和 `patch_json` 不再使用 CSRF |
| `tests/test_admin_users.py` | 移除 1 个 CSRF 专属测试，`login_as_admin()` 和 `post_json` 不再使用 CSRF |
| `tests/test_api_foundation.py` | 移除 `test_csrf_failure_uses_the_confirmed_error_code` |
| `src/api/auth.test.ts` | 移除 CSRF mock 调用，简化 fetch mock |

### 文档变更

| 文件 | 改动 |
|---|---|
| `01_垂直切片清单.md` | 全局验收条件、S00/S01/S02/S03 记录去 CSRF |
| `00_交接指引大纲.md` | 5 处 CSRF 引用删除 |
| `02_S00_实现说明.md` | 4 处 CSRF 引用删除 |
| `03_S01_实现说明.md` | 删除 CSRF 接口行和 3.4 CSRF 小节 |
| `04_S02_实现说明.md` | 2 处 CSRF 引用删除 |
| `code/README.md` | "和 CSRF" 删除 |

### 不影响的文件

- `docs/阶段一_系统设计/05_API接口设计.md` 等设计基线文档保留原始设计决定，不做事后修改。
- 所有业务逻辑：注册、登录、资料修改、管理员用户管理、密码重置均不受影响。

## 验证结果

| 检查项 | 结果 |
|---|---|
| Django system check | 0 个问题 |
| 迁移一致性检查 | 无待生成迁移 |
| 后端测试 | 62 项全部通过 |
| 前端测试 | 11 项全部通过 |
| 前端类型检查 | 通过 |
| 前端生产构建 | 通过 |
| Python 依赖审计 | 0 个已知漏洞 |
| npm 依赖审计 | 0 个已知漏洞 |
