# API 接口设计

## 文档信息

- **文档目的**：在已通过的权限、状态和数据库设计范围内，定义面向 Vue 3 与 Django 前后端分离场景的 API 路径、调用权限、请求字段、成功响应字段、业务错误及写操作副作用，作为后续前后端实现依据。
- **唯一需求基线**：`E:\Work\Student_club\all_\需求问答-修改版(严格按要求修改).md`。
- **编写与验收依据**：`00_阶段一任务指引_供新智能体.md`。
- **权限依据**：`01_角色权限矩阵.md`。
- **状态依据**：`02_业务状态与状态流转.md`。
- **数据依据**：`03_数据库概念设计.md`、`04_数据库逻辑设计.md`。
- **当前状态**：已通过。
- **依赖关系**：本文件严格承接 `01`—`04` 已定义的权限、状态、13 个业务实体和字段边界；`06_页面菜单与路由设计.md` 应使用本文件定义的接口，不得在页面设计中另行增加业务操作。

## 1. 设计范围与边界

### 1.1 接口模块

本文件只设计任务指引规定的 14 个模块：

1. 认证与个人资料。
2. 管理员用户管理。
3. 社团公开查询与管理员管理。
4. 负责人身份管理与社团成员管理。
5. 招新与入社申请。
6. 公告。
7. 帖子、回复、点赞和删除。
8. 站内通知。
9. 社团评价。
10. 意见反馈。
11. 内容举报和负责人处理。
12. 帖子 AI。
13. AI 文档生成。
14. 管理员、负责人和学生数据概览。

不设计活动、聊天、社团分类维护、头像、附件、帖子分类、帖子或回复修改、回复点赞、通知已读、学生找回密码、负责人转让、管理员审核入社申请、管理员处理反馈或举报、“我的举报”、评价审核、AI 历史、审计日志、已注销社团恢复及需求外统计接口。

### 1.2 路径与数据来源

- 基础路径统一写作 `/api`；是否增加版本前缀属于实现约定，不在本文件擅自确定。
- `{user_id}`、`{club_id}`、`{membership_id}`、`{recruitment_id}`、`{application_id}`、`{announcement_id}`、`{post_id}`、`{reply_id}`、`{evaluation_id}`、`{feedback_id}` 和 `{report_id}` 均为路径参数。
- 当前用户、当前时间、资源所属社团和系统生成状态一律由服务端取得，不能信任请求体重复提交的同名字段。
- 服务端必须从目标资源反查真实所属社团，再进行社团状态、成员状态和社团身份校验，不能只校验前端传入的 `club_id`。
- 除社团 Logo 上传外，请求和响应均使用 JSON。Logo 是需求规定的必填上传内容，因此创建或修改 Logo 的接口使用 `multipart/form-data`，但不新增独立图片、附件或上传记录实体。
- 所有响应中的关联对象名称、用户名、动态招新状态、计数和“本人是否点赞”等内容均为现有表关联查询或实时计算结果，不新增数据库字段。

### 1.3 列表、路径参数和查询参数

- 列表接口只返回调用者有权查看的记录；越权记录不能先返回再依靠前端过滤。
- 本文不增加需求之外的搜索、排序、趋势或筛选能力。管理员已有“查看全部记录”或负责人已有“查看负责社团记录”的接口，可以使用已有持久化状态进行基础过滤。
- `include_deleted=true` 只用于系统管理员或对应社团负责人查看帖子、回复的逻辑删除历史；普通成员传入时必须拒绝或忽略且不得返回已删除内容。
- 招新展示状态由服务端实时计算；前端不得另行计算或提交展示状态。
- 所有列表接口统一使用页码分页：查询参数为 `page`、`page_size`，分页响应字段见第 18 节；分页字段属于传输包装，不进入业务实体。

### 1.4 写操作的一般规则

- `POST` 用于创建记录或执行不能用普通字段修改表达的业务动作。
- `PATCH` 只允许修改接口明确列出的字段；未列字段必须拒绝。
- 公告、帖子和回复的 `DELETE` 表示逻辑删除；不物理删除记录。
- 取消帖子点赞的 `DELETE` 只删除当前点赞关系，这是需求明确允许的物理删除。
- 通过申请、拒绝申请、发布回复、处理举报等需要通知副作用的操作，主业务与通知必须同时成功或同时失败。
- 创建社团、停用学生、添加或取消负责人、调整招新人数、提交或通过申请等并发敏感操作，必须按照 `04` 的事务与联合校验要求执行。调整招新人数与通过申请必须锁定同一招新记录并重新统计已通过人数，不能各自依据旧计数提交。

## 2. 权限校验与公共响应字段

### 2.1 权限校验顺序

每次请求至少按以下顺序校验：

1. 是否已认证。
2. 平台角色是否匹配；学生账号是否正常。
3. 目标资源是否存在，并从目标资源反查所属社团。
4. 当前业务属于公开业务、社团内部业务还是系统管理业务。
5. 社团状态、成员状态、社团身份和目标资源状态是否满足操作要求。
6. 最后负责人、招新容量、申请重复、点赞唯一和评价唯一等业务约束是否满足。
7. 写操作及其规定副作用能否在同一事务中完成。

### 2.2 资源字段集合

所有成功和失败响应统一使用 `code`、`message`、`data` 包装。下列字段集合用于避免逐接口重复罗列；接口表中的“成功响应字段”均描述 `data` 内的业务字段。

| 字段集合 | 成功响应字段 |
|---|---|
| `SelfUser` | `id`、`username`、`platform_role`、`account_status`、`registered_at`、`name`、`phone`、`major_class`、`grade` |
| `AdminStudent` | `id`、`username`、`platform_role`、`account_status`、`registered_at`、`name`、`phone`、`major_class`、`grade`；永不返回 `password_hash` |
| `Club` | `id`、`name`、`category`、`introduction`、`logo`、`created_at`、`status` |
| `MembershipForAdmin` | `id`、`user`（`id`、`username`、`name`、`phone`、`major_class`、`grade`、`account_status`）、`club`（`id`、`name`、`status`）、`member_status`、`club_role` |
| `MembershipForLeader` | `id`、`user`（`id`、`username`、`name`、`phone`、`major_class`、`grade`、`account_status`）、`club_id`、`member_status`、`club_role`；只用于本人负责社团的当前在社成员 |
| `MyMembership` | `id`、`club`（`id`、`name`、`category`、`logo`、`status`）、`member_status`、`club_role` |
| `Recruitment` | `id`、`title`、`introduction`、`requirements`、`capacity`、`start_time`、`end_time`、`club_id`、`publisher`（`id`、`username`）、`published_at`、`ended_early`、`display_status`、`approved_count`；后两项实时计算 |
| `JoinApplication` | `id`、`applicant_id`、`applicant_name_snapshot`、`applicant_major_class_snapshot`、`club`（`id`、`name`）、`recruitment`（`id`、`title`）、`reason`、`applied_at`、`status`；不包含手机号 |
| `Announcement` | `id`、`title`、`content`、`club_id`、`publisher`（`id`、`username`）、`published_at`、`is_pinned`、`status` |
| `Post` | `id`、`title`、`content`、`club_id`、`author`（`id`、`username`）、`is_pinned`、`status`、`like_count`、`liked_by_me`；后两项实时计算 |
| `Reply` | `id`、`post_id`、`author`（`id`、`username`）、`content`、`status` |
| `Notification` | `id`、`type`、`content`；只返回当前接收人的通知，不返回或接受接收人修改 |
| `ClubEvaluation` | `id`、`user`（`id`、`username`）、`club`（`id`、`name`）、`membership_id`、`rating`、`comment` |
| `Feedback` | `id`、`submitter`（`id`、`username`）、`club`（`id`、`name`）、`content`、`submitted_at`、`status`、`processing_note` |
| `ContentReport` | `id`、`reporter`（`id`、`username`）、`reason`、`post_id`、`reply_id`、`status`、`processing_note`、`target`；`target` 只投影原帖子或回复的 `id`、`content`、`status`、作者 `id` 与 `username`，帖子目标另含 `title` |

`ContentReport.target` 不保存为举报快照，始终从原帖子或回复读取。负责人可以在举报处理场景查看本人负责社团内已逻辑删除的目标；系统管理员没有举报列表权限。

### 2.3 公共错误

| HTTP 状态 | 错误码 | 含义 |
|---:|---|---|
| `400` | `INVALID_REQUEST` | 请求结构错误、字段不允许或必填字段缺失 |
| `401` | `UNAUTHENTICATED` | 未登录、登录会话无效或凭据错误 |
| `403` | `ACCOUNT_DISABLED` | 学生账号已停用 |
| `403` | `CSRF_FAILED` | 非安全方法缺少或提交了无效 CSRF 令牌 |
| `403` | `FORBIDDEN` | 平台角色或业务权限不允许 |
| `403` | `NOT_CLUB_MEMBER` | 当前用户从未是目标社团成员 |
| `403` | `MEMBERSHIP_INACTIVE` | 成员状态为已退出或已移除 |
| `403` | `NOT_CLUB_LEADER` | 不是目标社团当前有效负责人 |
| `409` | `CLUB_CANCELLED` | 社团已注销，当前业务已停止 |
| `404` | `RESOURCE_NOT_FOUND` | 资源不存在；学生越权访问内部内容时也可统一使用，避免泄露 |
| `409` | `RESOURCE_DELETED` | 资源已逻辑删除且当前操作不允许继续 |
| `422` | `VALIDATION_ERROR` | 字段值不符合既有业务枚举、范围或前后关系 |

各接口表只列除上述公共错误外最主要的业务错误。

## 3. 认证与个人资料

### 3.1 模块规则

- 未登录用户只可注册或登录。
- 注册只创建平台角色为学生用户、账号状态为正常的账号；客户端不能提交平台角色、账号状态或注册时间。
- 登录只接受用户名和密码；不设计验证码、邮箱、手机号、第三方登录或学生找回密码。
- 学生只可修改姓名、手机号、专业班级和年级。
- 使用 Django 服务端会话认证；会话标识通过 `HttpOnly` Cookie 保存，所有非安全方法必须通过 CSRF 校验。
- 未登录前端先调用 CSRF 初始化接口取得令牌，再提交登录或注册；该令牌只用于请求防护，不形成业务字段或令牌表。

### 3.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/auth/csrf` | 未登录或已登录用户 | 无 | `csrf_token`；同时按 Django 配置初始化 CSRF Cookie | 公共错误 |
| `POST /api/auth/register` | 未登录用户 | `username`、`password`、`name`、`phone`、`major_class`、`grade` | 新建的 `SelfUser` | `USERNAME_EXISTS`；资料字段不完整 |
| `POST /api/auth/login` | 未登录用户 | `username`、`password` | 当前 `SelfUser`；服务端创建会话并通过 `Set-Cookie` 写入 `HttpOnly` 会话 Cookie | `INVALID_CREDENTIALS`；`ACCOUNT_DISABLED` |
| `GET /api/me/profile` | 已登录学生 | 无 | 当前 `SelfUser` | 公共错误 |
| `PATCH /api/me/profile` | 已登录且账号正常的学生 | 可选提交 `name`、`phone`、`major_class`、`grade` 中至少一项 | 更新后的 `SelfUser` | 提交 `username`、`platform_role`、`account_status`、`registered_at` 或头像字段时 `INVALID_REQUEST` |

本版不使用 Bearer Token，因此不设计令牌签发、刷新、黑名单或前端令牌保存；仍不新增需求未要求的登出或学生修改密码接口。

## 4. 管理员用户管理

### 4.1 模块规则

- 只管理学生用户，不把系统管理员账号作为学生管理对象。
- 停用学生前必须检查其负责的全部正常社团；任一社团会失去最后有效负责人时，整次操作失败。
- 恢复账号只恢复登录资格，不修改任何成员状态或社团身份。
- 重置密码不提供给学生本人，不返回明文密码或密码哈希。

### 4.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/admin/users` | 系统管理员 | 无 | `items: AdminStudent[]` | 公共错误 |
| `PATCH /api/admin/users/{user_id}/status` | 系统管理员 | `account_status`：`正常` 或 `已停用` | 更新后的 `AdminStudent` | `NOT_STUDENT_USER`；`LAST_EFFECTIVE_LEADER` |
| `POST /api/admin/users/{user_id}/reset-password` | 系统管理员 | `new_password` | `user_id` | `NOT_STUDENT_USER`；新密码不符合基础校验 |

不设计删除用户、修改学生资料、修改学生平台角色或查询密码的接口。

## 5. 社团公开查询与管理员管理

### 5.1 模块规则

- 学生公开列表和详情只返回正常社团；不要求当前用户是该社团成员。
- 系统管理员列表返回正常和已注销社团。
- 创建社团必须一次提交至少一个初始负责人用户 ID；服务端在同一事务中创建社团和对应“在社、负责人”成员关系。
- 初始负责人必须是账号正常的学生。
- 负责人只能修改本人负责的正常社团的简介和 Logo。
- 社团名称必须唯一；创建和修改时均校验重名，并由数据库唯一约束处理并发竞争。
- 注销后不恢复，不修改历史成员或内容状态。

### 5.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/clubs` | 已登录且账号正常的学生；系统管理员 | 无 | 所有调用者均得到正常社团 `items: Club[]`；管理员需要已注销记录时使用管理员专用列表接口 | 公共错误 |
| `GET /api/clubs/{club_id}` | 已登录且账号正常的学生；系统管理员 | 无 | 学生只得到正常社团 `Club`；系统管理员可得到正常或已注销社团 `Club` | 学生访问已注销社团时 `RESOURCE_NOT_FOUND` |
| `GET /api/admin/clubs` | 系统管理员 | 无 | 正常及已注销社团 `items: Club[]` | 公共错误 |
| `POST /api/admin/clubs` | 系统管理员 | `name`、`category`、`introduction`、`logo`、`leader_user_ids`；`leader_user_ids` 至少一项且不得重复 | 新建 `Club`、`leaders: MembershipForAdmin[]` | `CLUB_NAME_EXISTS`；`INVALID_CLUB_CATEGORY`；`LOGO_REQUIRED`；`INITIAL_LEADER_REQUIRED`；`INITIAL_LEADER_INVALID` |
| `PATCH /api/admin/clubs/{club_id}` | 系统管理员 | 可选提交 `name`、`category`、`introduction`、`logo` 中至少一项 | 更新后的 `Club` | `CLUB_NAME_EXISTS`；`CLUB_CANCELLED`；`INVALID_CLUB_CATEGORY` |
| `POST /api/admin/clubs/{club_id}/cancel` | 系统管理员 | 无 | 更新后的 `Club`，其中 `status=已注销` | `CLUB_ALREADY_CANCELLED` |
| `PATCH /api/leader/clubs/{club_id}` | 对应社团当前有效负责人 | 可选提交 `introduction`、`logo` 中至少一项 | 更新后的 `Club` | 提交名称、类别、状态或负责人名单时 `INVALID_REQUEST`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |

创建和修改 Logo 使用 `multipart/form-data`。服务端把上传成功后的存储标识写入 `club.logo`，不建立独立上传业务接口。

## 6. 负责人身份与社团成员管理

### 6.1 模块规则

- 系统管理员可以查看全部成员记录。
- 负责人只可查看本人负责的正常社团当前在社成员；该列表是负责人查看成员手机号的唯一社团业务场景。
- 社团创建后，系统管理员只能把当前“在社、普通成员”且账号正常的学生添加为负责人。
- 取消负责人身份后，只把目标身份改为普通成员；不能使正常社团失去最后有效负责人。
- 普通成员可以本人退出；负责人不能直接退出。
- 对应社团负责人只能移除当前在社普通成员，不能移除负责人；系统管理员不移除普通成员。
- 退出或移除不新增时间、原因、操作人字段。

### 6.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/admin/memberships` | 系统管理员 | 无 | `items: MembershipForAdmin[]` | 公共错误 |
| `GET /api/leader/clubs/{club_id}/members` | 对应社团当前有效负责人 | 无 | 当前在社成员 `items: MembershipForLeader[]` | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `GET /api/me/memberships` | 已登录学生 | 无 | 本人所有当前及历史关系 `items: MyMembership[]` | 公共错误 |
| `POST /api/admin/clubs/{club_id}/leaders` | 系统管理员 | `membership_id` | 更新后的 `MembershipForAdmin`，其中 `club_role=负责人` | `CLUB_CANCELLED`；`MEMBERSHIP_NOT_ACTIVE`；`MEMBERSHIP_NOT_ORDINARY`；`ACCOUNT_DISABLED` |
| `DELETE /api/admin/clubs/{club_id}/leaders/{membership_id}` | 系统管理员 | 无 | 更新后的 `MembershipForAdmin`，其中 `club_role=普通成员`、`member_status=在社` | `NOT_CURRENT_LEADER`；`LAST_EFFECTIVE_LEADER`；`CLUB_CANCELLED` |
| `POST /api/me/memberships/{membership_id}/exit` | 当前成员本人 | 无 | 更新后的 `MyMembership`，其中 `member_status=已退出` | `LEADER_CANNOT_EXIT`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `POST /api/leader/memberships/{membership_id}/remove` | 目标社团当前有效负责人 | 无 | `id`、`user_id`、`club_id`、`member_status=已移除`、`club_role=普通成员` | `NOT_CLUB_LEADER`；`TARGET_IS_LEADER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |

不设计负责人本人添加、取消或转让负责人身份的接口，也不设计系统管理员直接移除普通成员的接口。

## 7. 招新与入社申请

### 7.1 招新模块规则

- 面向学生的公开招新接口只返回正常社团的招新；提交申请仍必须要求动态状态为进行中。
- 系统管理员只能查看全部招新记录。
- 负责人只能创建、修改、调整或提前结束本人负责的正常社团招新。
- `display_status` 依次按“提前结束或超过结束时间、已满、未开始、进行中”实时计算，不能在请求中提交。
- `capacity` 必须是正整数；`start_time < end_time`。
- 修改只允许尚未结束的招新；调整后人数不得小于当前已通过人数。容量调整必须与申请通过锁定同一招新记录，并在写入前重新统计已通过人数，防止并发下调容量和通过申请造成超额。
- 提前结束只能把 `ended_early` 从 `0` 变为 `1`，不提供恢复。

### 7.2 招新接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/clubs/{club_id}/recruitments` | 已登录且账号正常的学生；系统管理员 | 无 | 所有调用者均得到正常社团中动态状态不是“已结束”的有效公开招新 `items: Recruitment[]`；管理员需要全部历史时使用管理员专用列表接口 | `CLUB_CANCELLED` |
| `GET /api/admin/recruitments` | 系统管理员 | 无 | 全部历史招新 `items: Recruitment[]` | 公共错误 |
| `GET /api/leader/clubs/{club_id}/recruitments` | 对应社团当前有效负责人 | 无 | 本社团全部招新 `items: Recruitment[]` | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `POST /api/leader/clubs/{club_id}/recruitments` | 对应社团当前有效负责人 | `title`、`introduction`、`requirements`、`capacity`、`start_time`、`end_time` | 新建 `Recruitment` | `INVALID_CAPACITY`；`INVALID_TIME_RANGE`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `PATCH /api/leader/recruitments/{recruitment_id}` | 目标招新所属社团当前有效负责人 | 可选提交 `title`、`introduction`、`requirements`、`capacity`、`start_time`、`end_time` 中至少一项 | 更新后的 `Recruitment` | `RECRUITMENT_ENDED`；`CAPACITY_BELOW_APPROVED`；`INVALID_TIME_RANGE`；`NOT_CLUB_LEADER` |
| `POST /api/leader/recruitments/{recruitment_id}/end` | 目标招新所属社团当前有效负责人 | 无 | 更新后的 `Recruitment`，其中 `ended_early=1`、`display_status=已结束` | `RECRUITMENT_ENDED`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |

### 7.3 入社申请模块规则

- 学生提交时只填写申请理由；申请人、姓名快照、专业班级快照、社团、招新、申请时间和初始状态均由服务端取得。
- 不保存或展示手机号快照。
- 当前已在社的学生不能申请；同一招新下不能同时有多条待审核申请。
- 被拒绝后只能申请同一社团后续发布的新招新。
- 只有对应社团当前有效负责人可以通过或拒绝申请。
- 系统管理员只查看，不审核、不纠正状态。
- 招新结束后可以继续审核既有待审核申请；通过时仍须重新检查申请人账号、社团和容量。
- 通过时申请、成员关系和通知必须原子完成；拒绝时申请和通知必须原子完成。

### 7.4 入社申请接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/recruitments/{recruitment_id}/applications` | 已登录且账号正常、当前不在目标社团的学生 | `reason` | 新建 `JoinApplication`，其中 `status=待审核` | `RECRUITMENT_NOT_STARTED`；`RECRUITMENT_FULL`；`RECRUITMENT_ENDED`；`ALREADY_CLUB_MEMBER`；`PENDING_APPLICATION_EXISTS`；`NOT_LATER_RECRUITMENT` |
| `GET /api/me/join-applications` | 已登录学生 | 无 | 本人全部申请 `items: JoinApplication[]` | 公共错误 |
| `GET /api/leader/clubs/{club_id}/join-applications` | 对应社团当前有效负责人 | 无 | 本社团申请 `items: JoinApplication[]`；不含手机号 | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `POST /api/leader/join-applications/{application_id}/approve` | 目标申请所属社团当前有效负责人 | 无 | 更新后的 `JoinApplication`；`membership`（`id`、`user_id`、`club_id`、`member_status=在社`、`club_role=普通成员`） | `APPLICATION_NOT_PENDING`；`APPLICANT_DISABLED`；`ALREADY_CLUB_MEMBER`；`RECRUITMENT_FULL`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `POST /api/leader/join-applications/{application_id}/reject` | 目标申请所属社团当前有效负责人 | 无 | 更新后的 `JoinApplication`，其中 `status=已拒绝` | `APPLICATION_NOT_PENDING`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `GET /api/admin/join-applications` | 系统管理员 | 无 | 全部历史申请 `items: JoinApplication[]`；不提供状态修改能力 | 公共错误 |

`approve` 成功时，不存在成员关系则创建“在社、普通成员”；存在已退出或已移除关系则恢复原记录为“在社、普通成员”。接口不返回或保存审核人、审核时间、审核说明或成员结果外键。

## 8. 公告

### 8.1 模块规则

- 学生必须是正常社团当前在社成员，才能查看正常公告。
- 只有对应社团当前有效负责人可以发布、修改、置顶、取消置顶和逻辑删除公告。
- 基础版请求只接受纯文本标题、正文和置顶标记；不接受图片或附件。
- 公告删除后普通成员不可见，不提供恢复。
- 系统管理员只在已注销社团历史查看场景查看公告，不取得发布、修改、置顶或删除权限。

### 8.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/clubs/{club_id}/announcements` | 目标社团当前在社普通成员或负责人 | 无 | 正常公告 `items: Announcement[]` | `NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `GET /api/admin/clubs/{club_id}/announcements` | 系统管理员 | 无 | 仅在目标社团已注销的历史查看场景，返回该社团正常及已删除公告 `items: Announcement[]` | 目标社团仍为正常时 `FORBIDDEN` |
| `POST /api/leader/clubs/{club_id}/announcements` | 对应社团当前有效负责人 | `title`、`content`、可选 `is_pinned` | 新建 `Announcement` | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `PATCH /api/leader/announcements/{announcement_id}` | 公告所属社团当前有效负责人 | 可选提交 `title`、`content`、`is_pinned` 中至少一项 | 更新后的 `Announcement` | `ANNOUNCEMENT_DELETED`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `DELETE /api/leader/announcements/{announcement_id}` | 公告所属社团当前有效负责人 | 无 | `id`、`status=已删除` | `ANNOUNCEMENT_DELETED`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |

## 9. 帖子、回复、点赞和删除

### 9.1 模块规则

- 正常社团当前在社成员可以查看、发布帖子和直接回复帖子。
- 帖子只有标题和正文，发布后不能修改；回复只有正文，发布后不能修改。
- 回复全部直接关联帖子并平级展示，不接受父回复 ID。
- 作者当前仍有目标社团内部权限时可以逻辑删除本人内容。
- 对应社团负责人可置顶帖子，并逻辑删除本人负责的正常社团内容。
- 系统管理员可查看和逻辑删除全部帖子、回复，不要求成员关系。
- 普通成员看不到已删除内容；父帖删除后，其回复停止展示但回复状态不批量修改。
- 只支持帖子点赞；点赞关系唯一，取消点赞时删除本人点赞关系。
- `Post.like_count` 和 `Post.liked_by_me` 实时查询，不新增计数或点赞状态字段。
- 帖子标题必填且最多 255 字，帖子正文必填且最多 5000 字；回复内容必填且最多 1000 字，超限统一返回带字段信息的 `VALIDATION_ERROR`。
- 帖子列表中置顶帖子优先展示；置顶组和普通组内部均按帖子自增 `id` 倒序，“最新”判断不增加发布时间字段。

### 9.2 帖子接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/clubs/{club_id}/posts` | 目标社团当前在社普通成员或负责人 | 无 | 正常帖子 `items: Post[]`；负责人以内容管理身份请求 `include_deleted=true` 时可包含本社团已删除帖子 | `NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `GET /api/posts/{post_id}` | 有权查看目标帖子的当前在社成员；对应负责人可在内容管理或举报处理场景查看已删除目标 | 无 | `Post` | `RESOURCE_NOT_FOUND`；`RESOURCE_DELETED`；`CLUB_CANCELLED` |
| `POST /api/clubs/{club_id}/posts` | 目标社团当前在社普通成员或负责人 | `title`、`content` | 新建 `Post` | `NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `PATCH /api/leader/posts/{post_id}/pin` | 帖子所属社团当前有效负责人 | `is_pinned` | 更新后的 `Post` | `POST_DELETED`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `DELETE /api/posts/{post_id}` | 当前仍有内部权限的作者；对应社团当前有效负责人；系统管理员 | 无 | `id`、`status=已删除` | `POST_DELETED`；作者不再具有内部权限时 `MEMBERSHIP_INACTIVE`；负责人目标社团不匹配时 `NOT_CLUB_LEADER` |
| `GET /api/admin/posts` | 系统管理员 | 无 | 全部正常及已删除帖子 `items: Post[]` | 公共错误 |

不设计帖子 `PATCH` 内容接口、帖子分类、图片或附件字段。

### 9.3 回复接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/posts/{post_id}/replies` | 有权查看正常父帖的当前在社成员；对应负责人可在内容管理或举报处理场景查看已删除父帖下保留的回复及已删除回复 | 无 | 普通成员得到正常回复 `items: Reply[]`；负责人请求 `include_deleted=true` 时可包含本社团已删除回复 | 普通成员访问已删除父帖时 `RESOURCE_NOT_FOUND`；`CLUB_CANCELLED` |
| `POST /api/posts/{post_id}/replies` | 有权查看正常父帖的当前在社普通成员或负责人 | `content` | 新建 `Reply` | `POST_DELETED`；`NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED`；通知与回复不能同时完成 |
| `DELETE /api/replies/{reply_id}` | 当前仍有内部权限且父帖仍可访问的作者；对应社团当前有效负责人；系统管理员 | 无 | `id`、`status=已删除` | `REPLY_DELETED`；作者删除时父帖已删除则 `POST_DELETED`；作者不再具有内部权限时 `MEMBERSHIP_INACTIVE`；负责人目标社团不匹配时 `NOT_CLUB_LEADER` |
| `GET /api/admin/replies` | 系统管理员 | 无 | 全部正常及已删除回复 `items: Reply[]` | 公共错误 |

发布回复成功时生成“有人回复了我的帖子”通知。接口不接受目标回复 ID，不设计回复修改、嵌套回复、回复图片、附件或点赞。

### 9.4 帖子点赞接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/posts/{post_id}/like` | 有权查看正常帖子的当前在社普通成员或负责人 | 无 | `post_id`、实时 `like_count`、`liked_by_me=true` | `POST_DELETED`；`DUPLICATE_LIKE`；`NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `DELETE /api/posts/{post_id}/like` | 已点赞且仍有权访问目标帖子的当前在社成员本人 | 无 | `post_id`、实时 `like_count`、`liked_by_me=false` | `LIKE_NOT_FOUND`；`POST_DELETED`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |

## 10. 站内通知

### 10.1 模块规则

- 只允许学生查看本人通知。
- 通知只有三种类型：有人回复了我的帖子、我的举报已经处理、我的入社申请已经审核。
- 不设计已读状态、标记已读、删除通知、通知详情、业务对象关联或点击跳转。
- 通知没有创建时间字段，因此接口不返回通知时间。

### 10.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/me/notifications` | 已登录学生本人 | 无 | 本人通知 `items: Notification[]` | 公共错误 |

## 11. 社团评价

### 11.1 模块规则

- 正常社团当前在社成员，包括负责人，可以提交一至五星实名评价，文字评价可空。
- 同一成员关系只保留一条评价；创建重复评价时返回业务错误，不创建第二条记录。
- 只有本人仍在社且社团正常时可以修改评价。
- 退出、移除、账号停用或社团注销后保留历史评价，本人仍可从个人记录查看，但不能新增或修改。
- 系统管理员只查看全部评价，不修改、删除或审核。
- 不提供本社团评价列表给负责人，不增加平均评分、分布或筛选。

### 11.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/clubs/{club_id}/evaluations` | 目标正常社团当前在社普通成员或负责人 | `rating`、可选 `comment` | 新建 `ClubEvaluation` | `DUPLICATE_EVALUATION`；`INVALID_RATING`；`NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `GET /api/me/evaluations` | 已登录学生本人 | 无 | 本人当前及历史评价 `items: ClubEvaluation[]` | 公共错误 |
| `PATCH /api/me/evaluations/{evaluation_id}` | 评价本人，且仍为目标正常社团当前在社成员 | 可选提交 `rating`、`comment` 中至少一项 | 更新后的 `ClubEvaluation` | `NOT_EVALUATION_OWNER`；`INVALID_RATING`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `GET /api/admin/evaluations` | 系统管理员 | 无 | 全部评价 `items: ClubEvaluation[]` | 公共错误 |

不设计评价删除、审核、匿名或负责人评价统计接口。

## 12. 意见反馈

### 12.1 模块规则

- 正常社团当前在社成员只填写反馈内容；提交人、社团、提交时间和待处理状态由服务端生成。
- 学生可查看本人当前及历史反馈和处理结果。
- 只有对应社团当前有效负责人可以查看和处理反馈。
- 处理时 `processing_note` 可选，未提供或为空不阻止处理；状态从待处理变为已处理后不回退。
- 系统管理员不能查看或处理反馈。
- 反馈处理不生成站内通知。

### 12.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/clubs/{club_id}/feedback` | 目标正常社团当前在社普通成员或负责人 | `content` | 新建 `Feedback`，其中 `status=待处理` | `NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `GET /api/me/feedback` | 已登录学生本人 | 无 | 本人当前及历史反馈 `items: Feedback[]` | 公共错误 |
| `GET /api/leader/clubs/{club_id}/feedback` | 对应社团当前有效负责人 | 无 | 本社团反馈 `items: Feedback[]` | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `POST /api/leader/feedback/{feedback_id}/process` | 反馈所属社团当前有效负责人 | `processing_note`（可选） | 更新后的 `Feedback`，其中 `status=已处理`；未填写处理说明时 `processing_note=null` | `FEEDBACK_ALREADY_PROCESSED`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED` |

## 13. 内容举报与负责人处理

### 13.1 模块规则

- 当前在社成员只能举报本人当前有权查看的正常帖子或正常回复。
- 帖子举报和回复举报使用不同目标路径，请求体只提交举报理由，避免客户端同时提交两个目标。
- 举报所属社团从目标内容反查，不在请求或数据库中重复提交 `club_id`。
- 不保存内容快照。
- 只有目标内容所属社团当前有效负责人可以查看和处理举报。
- 处理说明必填；结论只能是已采纳或未采纳。
- `delete_target` 是处理动作参数，不保存为举报字段。只有 `status=已采纳` 时才允许为 `true`，负责人按既有权限在同一处理流程中逻辑删除目标内容；`status=未采纳` 时必须为 `false`，不得改变内容状态。
- 已采纳不自动等于内容已删除；为 `false` 时只更新举报结论。
- 处理举报与生成“我的举报已经处理”通知必须同时成功。
- 系统管理员不能查看举报列表、处理举报或修改举报状态。
- 不设计“我的举报”列表或详情接口。

### 13.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/posts/{post_id}/reports` | 有权查看目标正常帖子的当前在社普通成员或负责人 | `reason` | 新建 `ContentReport`，其中仅 `post_id` 非空、`status=待处理` | `POST_DELETED`；`NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `POST /api/replies/{reply_id}/reports` | 有权查看目标正常回复的当前在社普通成员或负责人 | `reason` | 新建 `ContentReport`，其中仅 `reply_id` 非空、`status=待处理` | `REPLY_DELETED`；`POST_DELETED`；`NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED` |
| `GET /api/leader/clubs/{club_id}/reports` | 对应社团当前有效负责人 | 无 | 本社团举报 `items: ContentReport[]`，含按权限读取的原目标 | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `POST /api/leader/reports/{report_id}/process` | 举报目标所属社团当前有效负责人 | `status`：`已采纳` 或 `未采纳`；`processing_note`；`delete_target`：布尔值，且未采纳时必须为 `false` | 更新后的 `ContentReport`；若执行删除则另返回目标的 `id`、`status=已删除`；目标此前已删除时保持原状态并继续完成举报处理 | `REPORT_ALREADY_PROCESSED`；`PROCESSING_NOTE_REQUIRED`；`INVALID_REPORT_STATUS`；未采纳却请求删除时 `INVALID_DELETE_DECISION`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED`；通知与处理不能同时完成 |

`delete_target=true` 只允许对应社团负责人删除目标社团的内容。该参数不增加自动违规识别、自动处罚或举报与删除状态绑定功能。

## 14. 帖子 AI

### 14.1 模块规则

- 只有有权查看当前正常帖子的在社成员可以调用。
- 服务端只读取当前帖子标题、正文和当前用户有权查看的正常回复。
- 不读取其他帖子、其他社团、已删除内容或用户敏感资料。
- 每次请求相互独立，只发送当前帖子内容和本次任务；不保存问题、上下文、回答或调用记录。
- `operation` 只允许总结、提取主要观点和根据当前内容问答。
- 问答信息不足时，回答必须说明“根据当前帖子内容无法确定”。
- 超长上下文按系统配置上限截断；截断仍是成功响应，不是 DeepSeek 调用失败。
- DeepSeek 密钥、模型名和请求参数只放在后端环境配置中；请求体不接受模型名或模型参数，响应也不返回这些配置。

### 14.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/posts/{post_id}/ai` | 有权查看目标正常帖子的当前在社普通成员或负责人 | `operation`：`总结`、`提取主要观点`、`问答`；当且仅当为问答时提交 `question` | `answer`、`truncated`；截断时另返回 `warning=内容较长，本次回答可能未包含全部回复` | `INVALID_AI_OPERATION`；`QUESTION_REQUIRED`；`POST_DELETED`；`NOT_CLUB_MEMBER`；`MEMBERSHIP_INACTIVE`；`CLUB_CANCELLED`；`DEEPSEEK_CALL_FAILED` |

`DEEPSEEK_CALL_FAILED` 使用 `502`，向前端返回明确失败提示，但不得改变帖子、回复或其他业务数据。

## 15. AI 文档生成

### 15.1 模块规则

- 只有对应正常社团当前有效负责人可以生成。
- 文档类型只允许社团公告、招新文案和社团介绍。
- 输入项均来自需求基线；服务端可以补充当前社团名称和简介，但不能读取其他社团数据。
- 每次请求都可重新调用生成，不需要独立“重新生成”接口。
- 只返回纯文本草稿，不自动发布或覆盖公告、招新或社团介绍。
- 不保存输入、草稿或生成历史，不新增 AI 业务表。
- 不实现单独敏感内容识别或自动违规处理。

### 15.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `POST /api/leader/clubs/{club_id}/ai-documents` | 对应社团当前有效负责人 | `document_type`：`社团公告`、`招新文案`、`社团介绍`；可选 `title_or_topic`、`main_content`、`audience`、`time`、`location`、`contact`、`expected_length`、`style`、`additional_requirements` | `draft` | `INVALID_DOCUMENT_TYPE`；`NOT_CLUB_LEADER`；`CLUB_CANCELLED`；`DEEPSEEK_CALL_FAILED` |

生成结果不返回历史 ID、发布状态或目标业务对象 ID，因为本功能不持久化且不能自动发布。

## 16. 数据概览

### 16.1 模块规则

- 所有指标实时查询，不保存统计表或计数字段。
- 系统管理员只查看用户总数和正常社团数。
- 负责人先选择本人负责的正常社团，只查看该社团六项规定指标。
- 学生只查看本人当前加入正常社团数量和本人入社申请记录。
- 不增加趋势、排行、活跃度、平均评分、评分分布或图表数据。
- “当前招新数”只统计当前动态展示状态不是已结束的招新；其他数量严格使用需求规定的状态条件。
- `post_count` 只统计 `status=正常` 的帖子，不包含已逻辑删除帖子。

### 16.2 接口

| HTTP 方法与路径 | 允许调用者 | 请求体字段 | 成功响应字段 | 主要业务错误 |
|---|---|---|---|---|
| `GET /api/admin/overview` | 系统管理员 | 无 | `user_count`、`normal_club_count` | 公共错误 |
| `GET /api/leader/clubs/{club_id}/overview` | 对应正常社团当前有效负责人 | 无 | `active_member_count`、`pending_application_count`、`current_recruitment_count`、`post_count`、`pending_feedback_count`、`pending_report_count` | `NOT_CLUB_LEADER`；`CLUB_CANCELLED` |
| `GET /api/me/overview` | 已登录学生本人 | 无 | `joined_normal_club_count`、`join_applications: JoinApplication[]` | 公共错误 |

`post_count` 按 `club_id` 和 `status=正常` 实时统计，不保存统计结果。

## 17. 主要错误与接口映射

| 必须覆盖的错误场景 | 错误码 | 主要出现接口 |
|---|---|---|
| 账号已停用 | `ACCOUNT_DISABLED` | 登录及全部学生受保护接口 |
| 社团已注销 | `CLUB_CANCELLED` | 社团公开业务、内部业务、负责人业务和 AI |
| 不是社团成员 | `NOT_CLUB_MEMBER` | 公告、帖子、回复、点赞、评价、反馈、举报和帖子 AI |
| 成员已退出或已移除 | `MEMBERSHIP_INACTIVE` | 全部社团内部业务 |
| 不是对应社团负责人 | `NOT_CLUB_LEADER` | 负责人管理接口 |
| 操作会使正常社团无有效负责人 | `LAST_EFFECTIVE_LEADER` | 停用学生、取消负责人身份 |
| 招新未开始 | `RECRUITMENT_NOT_STARTED` | 提交申请 |
| 招新已满 | `RECRUITMENT_FULL` | 提交申请、通过申请 |
| 招新已结束 | `RECRUITMENT_ENDED` | 提交申请、修改或再次结束招新 |
| 入社申请重复 | `PENDING_APPLICATION_EXISTS` | 提交申请 |
| 审核时容量刚好已满 | `RECRUITMENT_FULL` | 通过申请 |
| 内容已删除或无权查看 | `RESOURCE_DELETED` 或 `RESOURCE_NOT_FOUND` | 内容查看、交互、举报和帖子 AI |
| 重复点赞 | `DUPLICATE_LIKE` | 点赞帖子 |
| 重复评价 | `DUPLICATE_EVALUATION` | 提交评价 |
| 社团名称重复 | `CLUB_NAME_EXISTS` | 创建社团、管理员修改社团名称 |
| 帖子或回复内容超长 | `VALIDATION_ERROR` | 发布帖子、发布回复 |
| DeepSeek 调用失败 | `DEEPSEEK_CALL_FAILED` | 帖子 AI、AI 文档生成 |

对学生访问其他社团内部资源的情况，可以统一返回 `RESOURCE_NOT_FOUND`，避免泄露资源是否存在；服务端日志可记录实际拒绝原因，但第一版不新增审计日志业务实体或接口。

## 18. 用户已确认的接口层约定与实现说明

以下约定由用户于 2026-07-28 确认，并已同步到本文件各模块。它们是后续前后端实现的统一接口契约。

### 18.1 认证方式

**已确认方案**：使用 Django 服务端会话、`HttpOnly` Cookie 和 CSRF 防护。

推荐理由：

- 登录状态由后端控制，适合本项目的账号停用即时校验。
- 不需要新增令牌刷新、令牌黑名单或令牌持久化业务。
- DeepSeek 密钥和认证凭据均不暴露给前端脚本。
- 浏览器自动携带会话 Cookie；前端不在 `localStorage`、`sessionStorage` 或普通 Cookie 中保存认证令牌。
- 前端先调用 `GET /api/auth/csrf` 初始化令牌；`POST`、`PATCH`、`DELETE` 等非安全方法必须按 Django CSRF 机制携带有效令牌，失败时返回 `CSRF_FAILED`。

若前后端最终跨站部署，需要一并确认 Cookie、CSRF 和跨域配置；本文件不绑定具体第三方认证库版本。

### 18.2 统一响应格式

**已确认方案**：

- 成功：`code=SUCCESS`、`message`、`data`。
- 失败：`code`、`message`、`data=null`。

其中 `code` 使用本文定义的稳定错误码，`message` 用于前端显示，业务数据只放在 `data`。这些是传输包装字段，不进入 13 张业务表。

### 18.3 分页格式

**已确认方案**：列表请求使用 `page`、`page_size`；响应 `data` 内使用 `items`、`page`、`page_size`、`total`。这些是传输字段，不保存到数据库。

- `page` 默认 `1`，必须为大于或等于 `1` 的整数。
- `page_size` 默认 `20`，必须为 `1`—`100` 的整数。
- 参数非法时返回 `VALIDATION_ERROR`；空列表仍返回完整分页结构，其中 `items=[]`、`total=0`。

### 18.4 其他已确认约束与第一版边界

1. **社团名称唯一**：创建和管理员修改社团名称时处理 `CLUB_NAME_EXISTS`。
2. **帖子和回复最大输入长度**：帖子标题 255 字、帖子正文 5000 字、回复内容 1000 字，前后端使用相同字符上限。
3. **公告和帖子图片**：属于时间允许再完善，本版不设计对应请求字段或接口。
4. **DeepSeek 模型及请求参数**：放在后端环境配置中，API 不向前端暴露模型选择、参数或密钥。
5. **帖子数量统计口径**：负责人概览只统计状态为正常的帖子。
6. **“最新帖子列表”的排序依据**：以帖子自增 `id` 倒序表达发布先后，不增加发布时间字段；置顶帖子优先展示，同组内按 `id` 倒序。

## 19. 明确禁止的接口

- 学生自助找回密码、邮箱验证码、手机验证码、第三方登录。
- 删除用户、删除社团、恢复已注销社团。
- 学生申请创建社团、社团注销申请或审核。
- 社团分类新增、修改、删除。
- 负责人自行添加、取消或转让负责人。
- 系统管理员直接移除普通成员。
- 系统管理员通过、拒绝、纠正或补录入社申请结果。
- 入社申请撤回、重新打开或保存审核人、审核时间、审核说明。
- 公告阅读状态、公告附件或当前版本公告图片。
- 修改帖子、修改回复、回复指定回复、多层回复、回复点赞。
- 普通成员查看已删除内容；内容恢复或物理清理。
- 通知已读、删除、详情、业务跳转或通用对象关联。
- 评价删除、审核、匿名、负责人查看评价列表或评价统计。
- 系统管理员查看或处理意见反馈、内容举报。
- “我的举报”列表、详情或本人举报记录查询。
- AI 历史、复杂分段总结、向量检索、全社团知识库、AI 自动发布或 AI 自动处理违规内容。
- 需求范围外的统计、趋势、排行、活跃度和复杂图表数据。
- 审计日志、状态历史、操作人、操作时间、删除原因等需求外接口。

## 20. API 设计验收核对

- [x] 14 个规定模块均有对应接口，未增加需求外业务模块。
- [x] 每个接口均明确 HTTP 方法、路径、允许调用者、请求体字段、成功响应字段和主要业务错误。
- [x] 公开业务、成员业务、负责人业务和系统管理业务的边界清楚，所有权限以服务端校验为准。
- [x] 每个业务请求字段均映射到 `04` 既有字段、当前操作上下文或需求明确规定的非持久化 AI 输入。
- [x] 没有增加业务实体、持久化字段、审计字段、状态历史或统计缓存。
- [x] 创建社团与初始负责人、申请审核与成员恢复、通知副作用和最后负责人保护均明确要求事务与并发复查。
- [x] 系统管理员只能查看入社申请，不能审核或修改申请状态。
- [x] 意见反馈和内容举报只由对应社团负责人查看和处理；反馈处理说明可选，举报处理说明必填。
- [x] 举报处理可以按明确动作参数删除原内容，但举报结论与内容删除状态仍分别表达。
- [x] 帖子和回复不可修改，只逻辑删除；只支持帖子点赞。
- [x] 通知只含三种规定类型，没有已读状态或业务对象关联。
- [x] 帖子 AI 截断作为成功提示，DeepSeek 实际调用失败才作为错误。
- [x] AI 问答和文档草稿均不持久化，AI 不自动发布或处理违规内容。
- [x] 管理员、负责人和学生概览只返回需求规定的统计项。
- [x] 认证、统一响应、分页、社团名称唯一性、内容长度、DeepSeek 配置、帖子统计口径和最新帖子排序均已按用户决定落地。
