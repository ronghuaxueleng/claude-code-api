FROM ronghuaxueleng/python-nodejs

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV TZ=Asia/Shanghai

# Claude Code API 配置
ENV CLAUDE_BINARY_PATH=/usr/local/bin/claude
ENV HOST=0.0.0.0
ENV PORT=8091
ENV DEBUG=false
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=console

# Anthropic 相关环境变量
ENV ANTHROPIC_BASE_URL=""
ENV ANTHROPIC_API_KEY=""
ENV ANTHROPIC_AUTH_TOKEN=""
ENV ANTHROPIC_MODEL="claude-sonnet-4-5-20250929"

# 数据库配置
ENV DATABASE_URL="sqlite:///./claude_api.db"

# 认证配置
ENV REQUIRE_AUTH=false
ENV API_KEYS=""

# 项目配置
ENV PROJECT_ROOT=/app/projects
ENV MAX_CONCURRENT_SESSIONS=10

RUN rm -rf /etc/apt/sources.list.d/*
RUN echo "deb http://mirrors.aliyun.com/debian/  bookworm main non-free contrib" > /etc/apt/sources.list  && \
    echo "deb http://mirrors.aliyun.com/debian/  bookworm-updates main non-free contrib" >> /etc/apt/sources.list  && \
    echo "deb http://mirrors.aliyun.com/debian/  bookworm-backports main non-free contrib" >> /etc/apt/sources.list  && \
    echo "deb http://mirrors.aliyun.com/debian-security/  bookworm-security main non-free contrib" >> /etc/apt/sources.list

# 更新包管理器并安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    software-properties-common \
    gnupg2 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 删除导致 PEP 668 错误的配置文件
RUN rm -f /usr/lib/python*/EXTERNALLY-MANAGED

# 验证 Python 版本（需要 Python 3.10+）
RUN python --version && python3 --version

# 升级 pip
RUN python -m pip install --upgrade pip setuptools wheel

# 配置 pip 使用阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 配置 npm 使用淘宝镜像源并增加超时时间
RUN npm config set registry https://registry.npmmirror.com/ && \
    npm config set fetch-timeout 300000 && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000

# 安装 Claude CLI (全局安装，带重试机制)
RUN npm install -g @anthropic-ai/claude-code || \
    (sleep 5 && npm install -g @anthropic-ai/claude-code) || \
    (sleep 10 && npm install -g @anthropic-ai/claude-code --registry https://registry.npmjs.org/)

# 验证 Claude CLI 安装
RUN claude --version

# 注意：应用启动时会自动检测并移除 Claude CLI 的 root 用户限制
# 这使得在 Docker 容器中以 root 用户运行时可以使用 --dangerously-skip-permissions
# 原始文件会自动备份为 cli.js.original

# 复制项目文件
COPY pyproject.toml setup.py README.md ./
COPY claude_code_api/ ./claude_code_api/

# 复制 Claude 配置文件（如果存在）
COPY CLAUDE.local.md ./ 2>/dev/null || true

# 安装项目依赖（使用 setup.py）
RUN python -m pip install --no-cache-dir -e .

# 验证关键依赖安装
RUN python -c "import fastapi; print('FastAPI version:', fastapi.__version__)"
RUN python -c "import uvicorn; print('Uvicorn version:', uvicorn.__version__)"
RUN python -c "import pydantic; print('Pydantic version:', pydantic.__version__)"
RUN python -c "import structlog; print('Structlog installed successfully')"
RUN python -c "import sqlalchemy; print('SQLAlchemy installed successfully')"
RUN python -c "import aiosqlite; print('Aiosqlite installed successfully')"

# 创建必要的目录
RUN mkdir -p /app/logs /app/projects /app/sessions

# 设置 Claude CLI 相关环境变量
ENV HOME=/root
ENV XDG_CONFIG_HOME=/root/.config
ENV XDG_DATA_HOME=/root/.local/share

# 创建 Claude 配置目录
RUN mkdir -p $XDG_CONFIG_HOME/claude $XDG_DATA_HOME/claude

# 暴露端口
EXPOSE 8091

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8091/health || exit 1

# 启动命令 - 使用 uvicorn 直接启动 FastAPI 应用
CMD ["python", "-m", "uvicorn", "claude_code_api.main:app", "--host", "0.0.0.0", "--port", "8091", "--log-level", "info"]