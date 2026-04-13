# AI PaperCraft Studio 系统架构与技术方案

## 1. 文档目标

本文档基于 `AI PaperCraft Studio` 的 PRD，给出一版面向 MVP 到 V1 的系统架构与技术方案，目标是指导产品、前端、后端、算法和 AI coding agent 协同开发。

本文档重点回答以下问题：

- 系统应如何分层与拆分模块
- MVP 推荐使用哪些技术栈
- 从上传图片到导出 PDF 的核心链路如何设计
- 异步任务、对象存储、数据库、算法服务如何协作
- 如何保证结果可制作、系统可观测、后续可扩展

---

## 2. 设计目标与原则

### 2.1 核心目标

系统需要完成一个稳定闭环：

`图片上传 -> 图像预处理 -> 基础模型生成 -> 纸模适配 -> 降面 -> 展开排版 -> 导出 PDF -> 用户预览与下载`

### 2.2 设计原则

- 优先保证“可制作”，而不是追求最强图像到 3D 效果
- 优先实现稳定的任务流水线，再逐步替换或增强算法模块
- 所有重处理环节均以异步任务形式执行，避免前端长连接等待
- 所有中间产物可追踪、可复用、可调试
- 算法模块与业务模块解耦，便于替换不同实现
- 系统先服务 MVP，再保留 V1.1 和 V2 的扩展空间

### 2.3 架构策略

MVP 不建议一开始构建复杂微服务体系。推荐采用：

- 前端单独部署
- 后端 API 服务单独部署
- Worker 异步任务服务单独部署
- 几何与展开逻辑封装为可复用内部模块
- 对象存储、数据库、缓存与队列作为基础设施

这是一种“模块化单体 + 异步任务编排”的架构，适合当前阶段。

---

## 3. 总体架构

## 3.1 架构总览

```text
+--------------------+        +-----------------------+
|      Web Client    | <----> |   Next.js Frontend    |
| Upload / Preview   |        |  SSR + Workbench UI   |
+--------------------+        +-----------+-----------+
                                            |
                                            v
                               +------------+------------+
                               |   API Service           |
                               | Auth / Projects / Tasks |
                               | Upload / Export / Query |
                               +-----+--------------+----+
                                     |              |
                                     |              v
                                     |     +--------+--------+
                                     |     |   PostgreSQL    |
                                     |     | Projects/Tasks  |
                                     |     +-----------------+
                                     |
                                     v
                           +---------+----------+
                           | Queue / Redis      |
                           | Task Dispatch      |
                           +---------+----------+
                                     |
                                     v
                          +----------+-----------+
                          | Worker Service       |
                          | Pipeline Orchestration|
                          +----+----+----+------+
                               |    |    |
                               |    |    v
                               |    |  +-------------------+
                               |    |  | Export Engine     |
                               |    |  | PDF / SVG / PNG   |
                               |    |  +-------------------+
                               |    |
                               |    v
                               |  +-------------------+
                               |  | Geometry Engine   |
                               |  | Repair / Decimate |
                               |  | Unfold / Layout   |
                               |  +-------------------+
                               |
                               v
                      +--------+---------+
                      | Image / 3D Layer |
                      | Segmentation     |
                      | View Estimation  |
                      | Mesh Generation  |
                      +--------+---------+
                               |
                               v
                      +--------+---------+
                      | Object Storage   |
                      | images/artifacts |
                      +------------------+
```

## 3.2 逻辑分层

系统可分为五层：

1. 表现层：Web 前端、上传页、生成中页、工作台、项目列表页
2. 业务接口层：项目管理、任务创建、状态查询、预览与导出 API
3. 编排层：任务状态机、阶段重试、失败回退、产物记录
4. 算法处理层：图像预处理、基础模型、几何修复、降面、展开、排版、导出
5. 基础设施层：数据库、对象存储、缓存、队列、日志、监控

---

## 4. 技术选型建议

## 4.1 前端

推荐技术栈：

- `Next.js 15+`
- `TypeScript`
- `React`
- `Tailwind CSS`
- `shadcn/ui`
- `Radix UI`
- `React Three Fiber`
- `three.js`

推荐原因：

- Next.js 适合同时承载营销首页、登录态页面和工作台
- TypeScript 可与后端共享接口类型
- React Three Fiber 适合 3D 预览和基础交互
- Tailwind + shadcn/ui 能快速交付 MVP，并保留可定制空间

前端职责：

- 上传图片与客户端基础校验
- 创建项目与触发任务
- 展示任务阶段、进度、错误信息
- 展示 3D 预览与图纸预览
- 修改参数并重试生成
- 发起导出、下载文件、查看历史任务

## 4.2 后端 API

推荐技术栈：

- `FastAPI`
- `Pydantic`
- `SQLAlchemy 2.x` 或 `SQLModel`
- `PostgreSQL`
- `Redis`

选择 FastAPI 的原因：

- 对异步接口、文件上传、结构化参数校验较友好
- Python 更适合后续集成图像处理、几何处理、AI 推理模块
- 对算法和工程团队协作成本更低

如果团队已重度使用 TypeScript，也可选：

- `Node.js`
- `NestJS` 或 `Hono`
- `Prisma`
- `BullMQ`

但从当前项目的算法耦合度看，MVP 更推荐 Python 主后端。

## 4.3 任务编排与异步执行

推荐技术栈：

- `Celery + Redis` 作为 MVP 默认方案

可选升级：

- `Temporal`：适合复杂重试、长流程、强可观测性
- `BullMQ`：适合 Node.js 主后端

MVP 建议：

- 先用 Celery 跑通任务状态机
- 将每个阶段拆为独立 task function
- 中间产物和状态写入数据库
- 出错后保留上下文，支持单阶段重试

## 4.4 算法与几何处理

推荐语言与运行环境：

- `Python` 作为图像处理、模型生成和编排主语言
- 部分几何计算可使用 `C++`/`Rust` 扩展或已有库封装

推荐模块能力：

- 图像预处理：`rembg`、`OpenCV`、`Pillow`
- 基础模型生成：优先模板拟合、类别先验、可控 mesh 生成
- 几何处理：`trimesh`、`open3d`、自定义 mesh repair
- 展开排版：自研 `unfold-core` 或接入成熟几何展开算法
- PDF/SVG 导出：`reportlab`、`svglib`、`cairosvg`

建议策略：

- MVP 第一阶段不依赖“通用大模型直接高质量 3D 重建”
- 先做“有限类别 + 稳定可制作结果”的方案
- 将基础模型生成定义为可替换模块，后续可接入外部模型服务

## 4.5 基础设施

推荐组件：

- 数据库：`PostgreSQL`
- 队列/缓存：`Redis`
- 对象存储：`S3 兼容存储`，开发环境可用 `MinIO`
- CDN：生产环境推荐接入
- 鉴权：MVP 可用邮箱验证码或第三方 OAuth
- 监控：`OpenTelemetry + Grafana + Loki` 或托管日志方案

---

## 5. 推荐代码仓结构

推荐采用 monorepo：

```text
apps/
  web/                     # Next.js 前端
services/
  api/                     # FastAPI 后端
  worker/                  # Celery worker / pipeline orchestration
packages/
  shared-types/            # 前后端共享 DTO / schema
  geometry-core/           # mesh repair / decimate / validation
  unfold-core/             # seam cut / flap / net layout
  export-core/             # pdf/svg/png export
docs/
  prd/
  architecture/
infra/
  docker/
  scripts/
```

拆分原则：

- `apps/web` 只负责 UI 与前端逻辑
- `services/api` 只处理 HTTP、鉴权、数据库写入和任务派发
- `services/worker` 负责状态推进与处理流水线
- `packages/*` 封装可测试、可替换的核心能力

---

## 6. 核心业务模块设计

## 6.1 用户与项目模块

职责：

- 用户注册、登录、身份识别
- 创建项目、查询项目列表、查看项目详情
- 保存封面图、最近任务、更新时间

主要表：

- `users`
- `projects`

## 6.2 图片上传模块

职责：

- 校验文件格式、大小、数量
- 生成上传记录
- 将文件写入对象存储
- 返回可供任务使用的 image_id

关键点：

- 限制 `JPG / PNG / WebP`
- 单项目图片数量上限为 `3`
- 服务端做 mime/type 二次校验
- 接入病毒扫描或至少隔离上传存储桶

## 6.3 任务与状态机模块

职责：

- 创建生成任务
- 保存参数快照
- 推进状态机
- 写入阶段耗时与失败信息

推荐状态：

`draft -> queued -> preprocessing -> model_generating -> paperability_optimizing -> decimating -> unfolding -> exporting -> completed / failed / canceled`

关键约束：

- 状态必须单向推进
- 每阶段写入 `started_at` 与 `finished_at`
- 所有失败必须带 `error_code` 和 `error_message`
- 支持 `retry_from_stage`

## 6.4 预览与工作台模块

职责：

- 获取 3D 预览资源
- 获取图纸预览资源
- 展示参数配置
- 提供重新生成与导出能力

工作台三栏建议：

- 左栏：参数面板
- 中栏：3D 预览
- 右栏：图纸预览

## 6.5 导出模块

职责：

- 将展开图纸 JSON 转为 PDF / SVG / PNG
- 附加说明页、页码、拼接编号、折线标记
- 记录导出 Artifact 与文件元数据

V1 必须支持：

- `A4 / A3 PDF`

V1.1 可扩展：

- `SVG`
- `PNG`
- `OBJ / GLB`

---

## 7. 核心流水线设计

## 7.1 阶段定义

### P1 上传校验

输入：

- 原始图片文件

输出：

- 标准化后的 `SourceImage` 记录
- 对象存储原图路径

处理内容：

- 格式校验
- 图片数量校验
- 尺寸与大小校验
- 安全扫描

### P2 图像预处理

输入：

- 原图

输出：

- 抠图结果
- 主体 mask
- 裁剪图
- 清洗图
- 预处理元数据

处理内容：

- 主体检测
- 背景去除
- 主体裁剪
- 视角粗识别
- 简单缺陷修复

### P3 基础模型生成

输入：

- 清洗后的图像与类别参数

输出：

- 基础 mesh
- 预览缩略图

推荐实现思路：

- `pet / bust / object` 分类别处理
- 优先模板拟合、几何先验、类别约束
- 多图输入作为增强模式，而不是强依赖

### P4 纸模适配优化

输入：

- 基础 mesh

输出：

- 结构修复后的 mesh

处理内容：

- 闭合非流形边
- 修复孔洞
- 清除过细部件
- 增强支撑稳定性

### P5 降面

输入：

- 修复后 mesh

输出：

- low poly mesh

约束：

- 目标面数
- 最小边长
- 最小面片面积
- 页数预算
- 关键轮廓保留

### P6 展开排版

输入：

- low poly mesh

输出：

- 图纸页面 JSON
- SVG 中间结果
- 编号关系
- 舌片定义

处理内容：

- 自动切缝
- 展开网片
- 生成山折/谷折/切割线
- 生成舌片
- 进行分页排版

### P7 导出

输入：

- 展开结果与元数据

输出：

- PDF
- 预览图
- 说明页

---

## 7.2 流水线编排建议

采用“编排器 + 阶段执行器”模式：

- API 创建任务后只负责落库与派发
- Worker 中的 orchestrator 控制阶段推进
- 每一阶段封装成独立 handler
- 每一阶段执行完成后写回数据库和 artifact

伪代码示意：

```python
def run_generation_task(task_id: str):
    task = repo.get_task(task_id)
    advance(task, "preprocessing")
    preprocess_result = preprocess_images(task)
    save_artifact(task, preprocess_result)

    advance(task, "model_generating")
    mesh = generate_base_mesh(task, preprocess_result)
    save_artifact(task, mesh)

    advance(task, "paperability_optimizing")
    repaired_mesh = optimize_paperability(mesh, task.params)
    save_artifact(task, repaired_mesh)

    advance(task, "decimating")
    low_poly = decimate_mesh(repaired_mesh, task.params)
    save_artifact(task, low_poly)

    advance(task, "unfolding")
    net = unfold_and_layout(low_poly, task.params)
    save_artifact(task, net)

    advance(task, "exporting")
    exported = export_pdf(net, task.params)
    save_artifact(task, exported)

    complete(task, exported)
```

---

## 8. 数据库与数据模型方案

## 8.1 核心实体

推荐核心表：

- `users`
- `projects`
- `source_images`
- `generation_tasks`
- `param_configs`
- `artifacts`
- `assembly_metadata`
- `task_events`

## 8.2 表设计建议

### users

```sql
id
email
display_name
plan_type
created_at
updated_at
```

### projects

```sql
id
user_id
title
category
status
cover_image_url
latest_task_id
created_at
updated_at
```

### source_images

```sql
id
project_id
storage_url
mime_type
width
height
file_size
sort_order
created_at
```

### generation_tasks

```sql
id
project_id
status
stage
progress
retry_from_stage
error_code
error_message
started_at
finished_at
created_at
updated_at
```

### param_configs

```sql
id
task_id
category
complexity_level
target_poly_count
paper_size
texture_mode
flap_size
max_pages
build_difficulty_mode
created_at
```

### artifacts

```sql
id
task_id
kind
storage_url
mime_type
file_size
width
height
page_count
extra_json
created_at
```

### assembly_metadata

```sql
id
task_id
part_count
page_count
estimated_build_minutes
difficulty_score
warnings_json
created_at
```

### task_events

```sql
id
task_id
stage
event_type
message
payload_json
created_at
```

## 8.3 设计说明

- `generation_tasks` 负责“当前状态”
- `task_events` 负责“阶段轨迹与调试日志”
- `artifacts` 保存所有中间和最终产物
- `param_configs` 使用快照模型，保证历史任务可复现

---

## 9. API 方案

## 9.1 API 风格

推荐：

- 外部接口采用 REST
- 内部模块之间使用 Python service call
- V1 不必引入 GraphQL

原因：

- REST 足够支撑当前页面
- 更适合任务驱动式系统
- 调试成本和接口文档成本更低

## 9.2 核心接口

### 创建项目

`POST /api/projects`

请求体：

```json
{
  "title": "My Cat Model",
  "category": "pet"
}
```

响应：

```json
{
  "project_id": "proj_xxx"
}
```

### 上传图片

`POST /api/projects/{id}/images`

响应：

```json
{
  "image_ids": ["img_1", "img_2"],
  "validation_result": {
    "accepted": 2,
    "rejected": 0
  }
}
```

### 创建任务

`POST /api/projects/{id}/tasks`

请求体：

```json
{
  "complexity_level": "standard",
  "target_poly_count": 300,
  "paper_size": "A4",
  "texture_mode": "color",
  "flap_size": "medium",
  "max_pages": 12,
  "build_difficulty_mode": "easy_first"
}
```

响应：

```json
{
  "task_id": "task_xxx",
  "initial_status": "queued"
}
```

### 查询任务状态

`GET /api/tasks/{id}`

响应：

```json
{
  "status": "unfolding",
  "stage": "unfolding",
  "progress": 78
}
```

失败示例：

```json
{
  "status": "failed",
  "stage": "unfolding",
  "error_code": "UNFOLD_FAILED",
  "error_message": "mesh has non-manifold edges"
}
```

### 获取项目详情

`GET /api/projects/{id}`

### 获取 3D 预览

`GET /api/projects/{id}/preview/3d`

### 获取图纸预览

`GET /api/projects/{id}/preview/net`

### 导出文件

`POST /api/projects/{id}/export`

### 重试任务

`POST /api/projects/{id}/retry`

---

## 10. 对象存储与产物管理

## 10.1 路径规范

建议统一使用：

```text
/users/{user_id}/projects/{project_id}/tasks/{task_id}/
```

示例：

```text
raw/source_1.png
preprocess/mask_1.png
preprocess/clean_1.png
mesh/base.glb
mesh/repaired.glb
mesh/lowpoly.glb
unfold/net.json
unfold/net.svg
export/final.pdf
export/preview_page_1.png
meta/assembly.json
```

## 10.2 Artifact 类型建议

`artifacts.kind` 可定义：

- `source_image`
- `preprocess_mask`
- `preprocess_clean`
- `base_mesh`
- `repaired_mesh`
- `lowpoly_mesh`
- `net_json`
- `net_svg`
- `preview_3d`
- `preview_image`
- `export_pdf`
- `export_png`
- `assembly_metadata`

## 10.3 生命周期建议

MVP 阶段建议：

- 原图长期保存
- 中间产物保留 7 到 30 天
- 最终导出文件长期保存或按套餐策略保存

---

## 11. 前端方案设计

## 11.1 页面结构

### 首页

目标：

- 展示产品价值
- 展示示例成品
- 引导进入创建流程

### 创建项目页

核心元素：

- 图片上传区
- 类型选择
- 复杂度选择
- 纸张尺寸选择
- 创建任务按钮

### 生成中页

核心元素：

- 当前阶段文案
- 进度条
- 失败提示
- 缩略图预览
- 取消任务按钮

### 编辑工作台

核心元素：

- 参数面板
- 3D 模型预览
- 图纸页预览
- 导出按钮
- 再次生成按钮

### 我的项目页

核心元素：

- 项目列表
- 状态标签
- 最近更新时间
- 下载按钮

## 11.2 前端状态管理

推荐：

- 接口请求：`TanStack Query`
- 轻量本地状态：React state
- 任务进度：轮询

MVP 不建议：

- 过早引入复杂全局状态库

## 11.3 预览实现建议

3D 预览：

- 使用 `React Three Fiber`
- 支持旋转、缩放、重置视角
- 渲染低模 mesh 或导出的 glb

图纸预览：

- 优先加载导出的 `pages_json` 或 `svg_url`
- 支持分页切换
- 高亮页码和编号区域

---

## 12. 后端方案设计

## 12.1 API 服务职责

- 提供认证和鉴权
- 提供项目和任务相关接口
- 处理上传凭证或直传逻辑
- 写入数据库
- 将任务派发到队列
- 查询并聚合任务结果

## 12.2 Worker 服务职责

- 消费任务
- 推进状态机
- 调用图像与几何处理模块
- 保存中间产物
- 输出日志与阶段指标

## 12.3 配置管理

推荐环境变量分类：

- 数据库连接
- Redis 连接
- 对象存储配置
- 鉴权配置
- 第三方模型服务密钥
- 文件大小限制
- 任务超时设置

建议统一命名：

```text
DATABASE_URL
REDIS_URL
S3_ENDPOINT
S3_BUCKET
S3_ACCESS_KEY
S3_SECRET_KEY
MAX_UPLOAD_MB
TASK_TIMEOUT_SECONDS
```

---

## 13. 算法与几何引擎方案

## 13.1 总体策略

建议把算法引擎拆成三类能力：

1. 图像理解层
2. mesh 生成与修复层
3. 展开与排版层

MVP 最重要的是第二和第三层稳定。

## 13.2 图像理解层

职责：

- 主体检测
- 抠图
- 视角估计
- 类别辅助判断

建议：

- 不把图像理解结果当成最终真值
- 所有输出都作为基础模型生成的辅助约束

## 13.3 基础模型层

建议路线：

- 宠物头像和 bust 优先采用模板约束生成
- 简单物体可采用轮廓驱动与体块近似
- 多图输入时提升准确性，但系统必须支持单图工作

关键原则：

- 输出 mesh 必须可修复
- 允许“像但不完全写实”
- 不允许复杂细碎结构直接进入展开阶段

## 13.4 纸模适配层

这一层是产品成败关键。

核心职责：

- 封闭网格
- 删除或加粗无法制作的细长结构
- 对尖锐、过薄、小面积区域做保护或裁剪
- 提升后续降面和展开成功率

建议输出可制作性检查指标：

- 最小边长
- 最小面片面积
- 预计页数
- 预计零件数
- 细碎结构计数
- 稳定性评分

## 13.5 降面与展开层

降面需要是“受约束降面”，不是普通 decimation：

- 目标面数只是上限之一
- 还需满足页数预算、拼装难度和轮廓保真度

展开需要显式建模：

- 切割线
- 山折线
- 谷折线
- 舌片边
- 配对编号

排版阶段需考虑：

- A4/A3 可打印边距
- 零件间距
- 页码
- 说明页

---

## 14. 质量控制与兜底策略

## 14.1 可制作性评分

建议定义 `paperability_score`，范围 `0-100`。

可由以下指标组合而成：

- `shape_stability_score`
- `min_piece_area_score`
- `part_count_score`
- `page_budget_score`
- `assembly_complexity_score`

建议先做规则模型，不必一开始训练模型。

## 14.2 自动回退策略

当任一指标超阈值时，执行自动回退：

- 页数超限：降低面数预算
- 零件过碎：提高最小边长与最小面片面积
- 展开失败：重新切缝并使用更保守的展开策略
- 导出失败：复用已有展开结果重新导出

## 14.3 人工可解释反馈

前端错误提示不要只显示系统错误码，应同步给用户行动建议。

例如：

- `PREPROCESS_SUBJECT_NOT_FOUND`
  未识别到清晰主体，请更换背景更干净、主体更居中的图片

- `UNFOLD_FAILED`
  当前模型结构过于复杂，系统建议自动降低复杂度后重试

---

## 15. 安全、合规与权限方案

## 15.1 上传安全

- 白名单文件格式校验
- 文件大小限制
- 对象存储隔离
- 服务端二次校验 mime/type
- 病毒扫描或隔离上传区

## 15.2 数据权限

- 所有项目、任务和产物按 `user_id` 做访问隔离
- 文件访问建议使用签名 URL
- 不直接暴露对象存储公网路径

## 15.3 合规

- 用户协议需说明上传素材版权责任
- 导出文件使用范围需在协议中明确
- 若后续引入社区分享，需增加审核与举报机制

---

## 16. 可观测性方案

## 16.1 日志

所有服务日志必须带：

- `task_id`
- `project_id`
- `user_id`
- `stage`
- `error_code`

## 16.2 指标

建议监控以下指标：

- 上传开始率
- 上传成功率
- 项目创建成功率
- 任务完成率
- 各阶段失败率
- 各阶段平均耗时
- 平均页数
- 平均零件数
- 导出率
- 再编辑率

## 16.3 链路追踪

推荐使用：

- `OpenTelemetry`

至少打通：

- API 请求
- 任务派发
- Worker 阶段执行
- 对象存储读写
- 导出阶段

---

## 17. 部署方案

## 17.1 开发环境

推荐使用 Docker Compose：

- `web`
- `api`
- `worker`
- `postgres`
- `redis`
- `minio`

## 17.2 测试与生产环境

推荐分为：

- Web 前端
- API 服务
- Worker 服务
- 托管 PostgreSQL
- 托管 Redis
- S3 兼容对象存储

部署建议：

- 前端部署在 Vercel 或同类平台
- API 与 Worker 部署在容器平台
- 几何和导出任务建议与 API 分离部署，避免抢占资源

## 17.3 伸缩策略

优先扩容：

- Worker 实例
- 几何处理节点
- 导出节点

API 通常不是性能瓶颈，Worker 才是核心瓶颈。

---

## 18. MVP 实施路径

## 18.1 第一阶段：系统骨架

目标：

- 跑通项目、上传、任务、状态查询

产出：

- Web 基础页面
- API 基础资源
- PostgreSQL 模型
- Redis 队列
- 对象存储接入

## 18.2 第二阶段：Mock 闭环

目标：

- 不接真实算法，先打通异步任务与工作台

产出：

- 假数据进度推进
- 假 3D 预览
- 假图纸页
- PDF 假导出

## 18.3 第三阶段：真实流水线接入

目标：

- 接入图像预处理、基础模型、降面、展开与导出

产出：

- 首个可用 PDF
- 中间产物留存
- 错误码与失败页

## 18.4 第四阶段：质量与稳定性

目标：

- 提升成功率和可制作性

产出：

- 自动回退策略
- 可制作性评分
- 阶段重试
- 验收样例集

---

## 19. 风险与应对

## 19.1 风险一：基础模型质量不稳定

应对：

- 限制输入类别
- 采用模板或先验约束
- 多图仅作为增强能力

## 19.2 风险二：展开成功率低

应对：

- 在展开前增加纸模适配检查
- 引入自动简化回退
- 将展开结果规则化输出

## 19.3 风险三：生成耗时长

应对：

- 全异步化
- 中间结果缓存
- 导出与生成分离

## 19.4 风险四：可用性与解释性不足

应对：

- 前端展示阶段进度和错误建议
- 输出评分、页数、难度和预计时间
- 保留历史任务和参数快照

---

## 20. 推荐结论

针对当前 PRD，推荐采用以下 MVP 技术路线：

- 前端：`Next.js + TypeScript + Tailwind + shadcn/ui + React Three Fiber`
- 后端：`FastAPI + PostgreSQL + Redis`
- 异步任务：`Celery`
- 对象存储：`S3 / MinIO`
- 核心算法：`Python` 主导，按模块封装图像预处理、mesh 修复、受约束降面、展开排版、PDF 导出

整体架构不建议一开始做成复杂微服务，而应采用：

`模块化单体 API + 独立 Worker + 可替换算法核心包`

这是当前阶段性价比最高、最适合 AI coding agent 逐步落地的方案。

---

## 21. 下一步建议

建议下一步按以下顺序继续产出落地文档：

1. 输出详细数据库 schema 设计
2. 输出 API 接口定义文档
3. 输出任务状态机与错误码规范
4. 输出 monorepo 初始化方案
5. 输出 MVP 开发任务拆解表

