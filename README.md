# Claude Code API 网关

一个简洁、专注的 OpenAI 兼容 API 网关，专为 Claude Code 设计，支持流式传输。
利用 Claude Code SDK 的使用模式，无需破解令牌凭据。

> **📢 项目说明**: 本项目基于 [codingworkflow/claude-code-api](https://github.com/codingworkflow/claude-code-api) 进行深度改造和优化升级，在保持原有核心功能的基础上，大幅增强了功能特性和用户体验。

## 🚀 升级亮点

### 🔥 核心升级
- **多提供商支持**: 新增支持 Moonshot、BigModel、DeepSeek、Siliconflow 等中国主流 AI 提供商
- **智能模型管理**: 支持 10+ 种模型，包括 Claude 官方模型和中国本土化模型
- **增强的流式传输**: 优化流式响应性能，支持多种流式模式（字符、单词、句子、消息）
- **完整的项目管理**: 新增项目生命周期管理，支持项目创建、删除、查询
- **会话持久化**: 基于 SQLite 的会话管理，支持会话恢复和历史记录

### 🛠️ 技术优化
- **数据库集成**: 新增 SQLite 数据库支持，实现数据持久化存储
- **认证系统**: 完善的 API 密钥认证和速率限制机制
- **结构化日志**: 使用 structlog 实现结构化日志记录，便于监控和调试
- **错误处理**: 统一的错误处理机制，提供详细的错误信息和状态码
- **配置管理**: 基于 Pydantic Settings 的配置管理，支持环境变量和配置文件

### 🌐 多提供商架构
- **提供商注册系统**: 可扩展的提供商注册和管理机制
- **动态配置**: 支持运行时切换不同的 API 提供商
- **故障转移**: 智能的模型故障转移和重试机制
- **成本优化**: 支持不同提供商的成本对比和优化建议

## 🚀 快速开始

使用 Makefile 安装项目或使用 pip/uv。

### Python 实现
```bash
# 克隆并设置
git clone https://github.com/codingworkflow/claude-code-api
cd claude-code-api

# 安装依赖和模块
make install 

# 启动 API 服务器
make start
```

## ⚠️ 限制说明

- 可能存在最大输入限制，低于正常的 "Sonnet 4" 输入，因为 Claude Code 通常不会处理超过 25k 个令牌（尽管上下文是 100k）
- Claude Code 在超过 100k 时会自动压缩上下文
- 目前运行在绕过模式下以避免工具错误
- Claude Code 工具可能需要禁用以避免重叠和后台使用
- 仅在 Linux/Mac 上运行，因为 Claude Code 不在 Windows 上运行（可以使用 WSL）
- 注意 Claude Code 默认访问当前工作区环境/文件夹，并设置为使用绕过模式

### 🔧 Docker 容器中的 Root 权限支持

本项目包含**自动修补功能**，可以在 Docker 容器中以 root 用户运行 Claude CLI：

- ✅ 应用启动时自动检测并移除 Claude CLI 的 root 用户限制
- ✅ 原始文件自动备份为 `cli.js.original`
- ✅ 无需手动操作，开箱即用

详细说明请查看：[Claude CLI Root 权限修补文档](README-Claude-Patcher.md)

## ✨ 功能特性

### 🎯 核心功能（继承自原项目）
- **OpenAI 兼容**: OpenAI API 端点的即插即用替代品
- **流式传输支持**: 实时流式响应
- **简洁设计**: 无过度工程，专注实现
- **Claude Code 集成**: 利用 Claude Code CLI 进行流式输出

### 🆕 新增功能（本版本升级）
- **多模型支持**: 支持 Claude 官方模型和多个中国提供商模型
- **多提供商支持**: 支持 Anthropic、Moonshot、BigModel、DeepSeek、Siliconflow 等
- **项目管理**: 内置项目生命周期管理和会话管理功能
- **数据库支持**: SQLite 数据库存储会话和项目信息
- **认证和限流**: 支持 API 密钥认证和速率限制
- **智能路由**: 根据模型自动选择最优提供商
- **成本监控**: 实时监控 API 调用成本和用量
- **健康检查**: 完善的系统健康状态监控

## 🤖 支持的模型

### 📋 模型对比表

| 提供商 | 模型名称 | 类型 | 特点 | 成本 |
|--------|----------|------|------|------|
| **Anthropic** | `claude-opus-4-20250514` | 官方 | 最强大，复杂推理 | 高 |
| **Anthropic** | `claude-sonnet-4-20250514` | 官方 | 最新 Sonnet，平衡性能 | 中 |
| **Anthropic** | `claude-3-7-sonnet-20250219` | 官方 | 高级任务处理 | 中 |
| **Anthropic** | `claude-3-5-haiku-20241022` | 官方 | 快速且经济 | 低 |
| **Moonshot** | `kimi-k2-turbo-preview` | 中国 | 中文优化，快速响应 | 低 |
| **Moonshot** | `kimi-k2-0905-preview` | 中国 | 中文理解能力强 | 低 |
| **Siliconflow** | `zai-org/GLM-4.5` | 中国 | 多模态支持 | 中 |
| **Siliconflow** | `zai-org/GLM-4.5-Air` | 中国 | 轻量级版本 | 低 |
| **DeepSeek** | `deepseek-chat` | 中国 | 代码生成优化 | 低 |

### 🎯 模型选择建议
- **开发调试**: 推荐 `claude-3-5-haiku-20241022` 或 `kimi-k2-turbo-preview`
- **生产环境**: 推荐 `claude-sonnet-4-20250514` 或 `zai-org/GLM-4.5`
- **复杂任务**: 推荐 `claude-opus-4-20250514`
- **中文场景**: 推荐 `kimi-k2-turbo-preview` 或 `kimi-k2-0905-preview`

## 🛠️ 安装和设置

### 前置要求
- Python 3.10+
- Claude Code CLI 已安装并可访问
- 在 Claude Code 中配置有效的 Anthropic API 密钥（确保在当前目录 src/ 中工作）

### 安装和设置

```bash
# 克隆并设置
git clone https://github.com/codingworkflow/claude-code-api
cd claude-code-api

# 安装依赖
make install

# 运行测试以验证设置
make test

# 启动 API 服务器
make start-dev
```

API 将在以下地址可用：
- **API**: http://localhost:8000
- **文档**: http://localhost:8000/docs  
- **健康检查**: http://localhost:8000/health

## 📋 Makefile 命令

### 核心命令
```bash
make install     # 安装生产依赖
make install-dev # 安装开发依赖  
make test        # 运行所有测试
make start       # 启动 API 服务器（生产）
make start-dev   # 启动 API 服务器（开发模式，支持重载）
```

### 测试
```bash
make test           # 运行所有测试
make test-fast      # 运行测试（跳过慢速测试）
make test-hello     # 使用 Haiku 测试 hello world
make test-health    # 仅测试健康检查
make test-models    # 仅测试模型 API
make test-chat      # 仅测试聊天完成
make quick-test     # 快速验证核心功能
```

### 开发
```bash
make dev-setup      # 完整的开发环境设置
make lint           # 运行代码检查
make format         # 使用 black/isort 格式化代码
make type-check     # 运行类型检查
make clean          # 清理缓存文件
```

### 信息
```bash
make help           # 显示所有可用命令
make models         # 显示支持的 Claude 模型
make info           # 显示项目信息
make check-claude   # 检查 Claude Code CLI 是否可用
```

## 🔌 API 使用

### 聊天完成

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "messages": [
      {"role": "user", "content": "你好！"}
    ]
  }'
```

### 列出模型

```bash
curl http://localhost:8000/v1/models
```

### 流式聊天

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-haiku-20241022", 
    "messages": [
      {"role": "user", "content": "给我讲个笑话"}
    ],
    "stream": true
  }'
```

### 项目管理

```bash
# 创建项目
curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的项目",
    "description": "一个测试项目"
  }'

# 列出项目
curl http://localhost:8000/v1/projects

# 获取项目详情
curl http://localhost:8000/v1/projects/{project_id}
```

### 会话管理

```bash
# 创建会话
curl -X POST http://localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "project-123",
    "title": "我的会话",
    "model": "claude-3-5-haiku-20241022"
  }'

# 列出会话
curl http://localhost:8000/v1/sessions

# 获取会话详情
curl http://localhost:8000/v1/sessions/{session_id}
```

### 提供商信息

```bash
# 获取支持的提供商
curl http://localhost:8000/v1/providers

# 获取模型能力
curl http://localhost:8000/v1/models/capabilities
```

## 🏗️ 项目结构

```
claude-code-api/
├── claude_code_api/
│   ├── main.py              # FastAPI 应用入口
│   ├── api/                 # API 端点
│   │   ├── chat.py          # 聊天完成
│   │   ├── models.py        # 模型 API
│   │   ├── projects.py      # 项目管理
│   │   └── sessions.py      # 会话管理
│   ├── core/                # 核心功能
│   │   ├── auth.py          # 认证中间件
│   │   ├── claude_manager.py # Claude Code 集成
│   │   ├── session_manager.py # 会话管理
│   │   ├── config.py        # 配置管理
│   │   └── database.py      # 数据库层
│   ├── models/              # 数据模型
│   │   ├── claude.py        # Claude 特定模型
│   │   ├── openai.py        # OpenAI 兼容模型
│   │   └── providers.py     # 模型提供商配置
│   ├── utils/               # 工具函数
│   │   ├── streaming.py     # 流式传输支持
│   │   └── parser.py        # 输出解析
│   └── tests/               # 测试套件
├── Makefile                 # 开发命令
├── pyproject.toml          # 项目配置
├── setup.py                # 包设置
└── README.md               # 本文档
```

## 🧪 测试

测试套件验证：
- 健康检查端点
- 模型 API（仅 Claude 模型）
- 使用 Haiku 模型的聊天完成
- Hello world 功能
- OpenAI 兼容性（结构）
- 错误处理

运行特定测试套件：
```bash
make test-hello    # 使用 Haiku 测试 hello world
make test-models   # 测试模型 API
make test-chat     # 测试聊天完成
```

## 💻 开发

### 设置开发环境
```bash
make dev-setup
```

### 代码质量
```bash
make format        # 格式化代码
make lint          # 检查代码规范
make type-check    # 类型检查
```

### 快速验证
```bash
make quick-test    # 测试核心功能
```

## 🚀 部署

### 检查部署就绪性
```bash
make deploy-check
```

### 生产服务器
```bash
make start-prod    # 使用多个工作进程启动
```
使用 http://127.0.0.1:8000/v1 作为 OpenAPI 端点

## ⚙️ 配置

`claude_code_api/core/config.py` 中的关键设置：
- `claude_binary_path`: Claude Code CLI 路径
- `project_root`: 项目根目录
- `database_url`: 数据库连接字符串
- `require_auth`: 启用/禁用认证
- `default_model`: 默认模型
- `claude_base_url`: Claude API 基础 URL
- `claude_api_key`: Claude API 密钥

### 环境变量

```bash
# Claude 配置
export CLAUDE_BINARY_PATH="/usr/local/bin/claude"
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_BASE_URL="https://api.moonshot.cn/anthropic/"

# 服务器配置
export HOST="0.0.0.0"
export PORT="8000"
export DEBUG="false"

# 认证配置
export REQUIRE_AUTH="true"
export API_KEYS="key1,key2,key3"

# 数据库配置
export DATABASE_URL="sqlite:///./claude_api.db"
```

## 🎯 设计原则

### 📋 继承原则（来自原项目）
1. **简洁专注**: 无过度工程，保持代码简洁
2. **流式优先**: 为实时流式传输而构建
3. **OpenAI 兼容**: 即插即用的 API 兼容性
4. **测试驱动**: 全面的测试覆盖

### 🆕 新增原则（本版本优化）
5. **多模型支持**: 支持 Claude 官方模型和中国提供商模型
6. **可扩展性**: 支持多提供商和自定义配置
7. **数据持久化**: 基于数据库的会话和项目管理
8. **智能路由**: 根据模型和成本自动选择最优提供商
9. **监控友好**: 完善的日志记录和健康检查机制
10. **安全优先**: 完善的认证和权限控制

## 🏥 健康检查

```bash
curl http://localhost:8000/health
```

响应：
```json
{
  "status": "healthy",
  "version": "1.0.0", 
  "claude_version": "1.x.x",
  "active_sessions": 0,
  "claude_processes": 0,
  "zombie_processes_cleaned": 0
}
```

## 📊 监控和日志

### 结构化日志
项目使用 `structlog` 进行结构化日志记录：

```python
import structlog
logger = structlog.get_logger()

logger.info(
    "chat_request_received",
    client_id=client_id,
    model=request.model,
    messages=len(request.messages),
    stream=request.stream
)
```

### 日志配置
- 控制台输出：实时显示日志
- JSON 格式：结构化日志用于生产环境
- 文件日志：可选的日志文件输出

## 🔒 安全特性

- **API 密钥认证**: 支持 Bearer token 和 x-api-key 头部
- **速率限制**: 可配置的请求速率限制
- **CORS 支持**: 跨域资源共享配置
- **输入验证**: Pydantic 模型验证所有输入
- **错误处理**: 统一的错误响应格式

## 🌐 多提供商支持

### 支持的提供商
- **Anthropic**: 官方 Claude API
- **Moonshot**: 中国提供商，支持 Kimi 模型
- **BigModel**: 中国提供商
- **DeepSeek**: 中国提供商
- **Siliconflow**: 中国提供商，支持 GLM 模型

### 提供商配置
```python
# 使用特定提供商
provider_config = {
    "ANTHROPIC_BASE_URL": "https://api.moonshot.cn/anthropic/",
    "ANTHROPIC_API_KEY": "your-api-key",
    "ANTHROPIC_MODEL": "kimi-k2-turbo-preview"
}
```

## 📈 性能优化

- **异步处理**: 全异步 I/O 操作
- **连接池**: HTTP 客户端连接池
- **缓存**: 内存缓存频繁查询
- **流式传输**: 实时响应流
- **资源管理**: 自动清理过期会话

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 GNU General Public License v3.0 许可证 - 详见 LICENSE 文件。

## 🙏 致谢

### 原项目
本项目基于 [codingworkflow/claude-code-api](https://github.com/codingworkflow/claude-code-api) 进行深度改造和优化升级。感谢原项目作者的开源贡献，为社区提供了优秀的 Claude Code API 网关基础实现。

### 升级贡献
本版本在原项目基础上进行了以下重大升级：
- **架构重构**: 引入多提供商架构，支持动态切换和故障转移
- **功能增强**: 新增项目管理、会话持久化、认证系统等企业级功能
- **性能优化**: 优化流式传输性能，支持多种流式模式和智能缓冲
- **监控完善**: 集成结构化日志、健康检查、成本监控等运维功能
- **用户体验**: 提供详细的中文文档、配置示例和故障排除指南

### 技术栈升级
- **数据库**: SQLite → 支持会话和项目数据持久化
- **认证**: 无 → API 密钥认证 + 速率限制
- **日志**: 基础日志 → 结构化日志 (structlog)
- **配置**: 硬编码 → Pydantic Settings 配置管理
- **错误处理**: 简单异常 → 统一错误处理机制
- **提供商**: 单一 → 多提供商注册和管理系统

## 🆘 故障排除

### 常见问题

1. **Claude Code CLI 未找到**
   ```bash
   # 检查 Claude 是否安装
   which claude
   claude --version
   
   # 设置环境变量
   export CLAUDE_BINARY_PATH="/path/to/claude"
   ```

2. **API 密钥问题**
   ```bash
   # 检查环境变量
   echo $ANTHROPIC_API_KEY
   
   # 在 Claude Code 中测试
   claude -p "测试消息"
   ```

3. **端口占用**
   ```bash
   # 更改端口
   export PORT="8001"
   make start-dev
   ```

4. **数据库问题**
   ```bash
   # 重置数据库
   rm claude_api.db
   make start-dev
   ```

### 调试模式

```bash
# 启用调试模式
export DEBUG="true"
export LOG_LEVEL="DEBUG"
make start-dev
```

## 📞 支持

如有问题或建议，请：
- 提交 Issue
- 查看文档
- 联系维护者

---

## 📊 项目统计

### 📈 升级对比

| 特性 | 原项目 | 本版本 | 提升 |
|------|--------|--------|------|
| 支持模型数 | 4 个 | 9+ 个 | +125% |
| API 端点 | 3 个 | 8+ 个 | +167% |
| 提供商支持 | 1 个 | 5+ 个 | +400% |
| 数据库支持 | ❌ | ✅ | 新增 |
| 认证系统 | ❌ | ✅ | 新增 |
| 项目管理 | ❌ | ✅ | 新增 |
| 会话持久化 | ❌ | ✅ | 新增 |
| 结构化日志 | ❌ | ✅ | 新增 |
| 健康检查 | 基础 | 完善 | 增强 |
| 文档语言 | 英文 | 中文 | 本土化 |

### 🎯 核心价值
- **兼容性**: 100% 兼容原项目 API，无缝迁移
- **扩展性**: 支持多提供商，降低单一依赖风险
- **可靠性**: 完善的错误处理和故障转移机制
- **可维护性**: 结构化代码和详细文档
- **本土化**: 支持中国主流 AI 提供商，降低使用成本

---

**Claude Code API 网关** - 让 Claude Code 的强大功能通过标准 API 轻松访问！

> 💡 **提示**: 本项目是 [codingworkflow/claude-code-api](https://github.com/codingworkflow/claude-code-api) 的增强版本，在保持原有功能的基础上，大幅提升了功能特性和用户体验。如果您需要基础版本，请访问原项目仓库。