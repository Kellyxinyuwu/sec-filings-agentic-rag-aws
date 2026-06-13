# =============================================================================
# Phase 5 Step 1 — SEC RAG API 容器镜像
# =============================================================================
#
# 这个镜像里有什么？
#   - 与 laptop 相同的 app/ 代码（FastAPI + agents + store + OpenSearch 客户端）
#   - pyproject.toml 里声明的所有 Python 依赖（含 sentence-transformers / boto3）
#
# 没有什么？
#   - 没有 .env（密钥运行时注入）
#   - 没有 ~/.aws/credentials（Phase 5 后期用 ECS task role；Step 1 本地可 -v 挂载）
#   - 没有 sec-edgar-filings/（ingest 仍在宿主机跑）
#
# 构建：
#   docker build -t sec-rag-api:local .                    # Mac 本地 smoke (arm64)
#   docker build --platform linux/amd64 -t sec-rag-api:local .  # ECS Fargate 必须 amd64
#   python scripts/ecr_push.py --build                     # 默认 linux/amd64 推 ECR
#
# 运行（Step 1 本地 smoke）：
#   docker rm -f sec-rag-api-smoke 2>/dev/null
#   docker run --rm -p 127.0.0.1:8000:8000 --env-file .env \
#     -v "$HOME/.aws:/root/.aws:ro" \
#     --name sec-rag-api-smoke \
#     sec-rag-api:local
#   # macOS Docker Desktop：显式 127.0.0.1 绑定，避免 -p 8000:8000 不映射
#
# 验证：
#   curl -s http://127.0.0.1:8000/health
#
# =============================================================================

# 与 GitHub Actions CI 一致用 3.11；slim 比 full 小很多
FROM python:3.11-slim

# sentence-transformers 依赖的 PyTorch 需要 OpenMP 运行时库
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- 依赖层（Docker 层缓存）---
# 先只复制安装所需文件；改 app/*.py 时不会触发整段 pip reinstall
COPY pyproject.toml README.md ./
COPY app ./app

# 安装项目 + 运行时依赖（不含 dev 的 pytest/ruff）
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# --- 可选：构建时预下载 MiniLM（减少首次 /retrieve 等 10–30s）---
# 取消下面两行注释会显著增大 build 时间和镜像体积，但 ECS 冷启动更快
# RUN python -c "from sentence_transformers import SentenceTransformer; \
#     SentenceTransformer('all-MiniLM-L6-v2')"

# Python 日志立刻刷到 stdout — CloudWatch / docker logs 能实时看到
ENV PYTHONUNBUFFERED=1
# 标记运行环境（以后 logging / config 可区分 laptop vs container）
ENV APP_ENV=container

# 容器内 uvicorn 必须 0.0.0.0，否则 port mapping / ALB 连不进来
EXPOSE 8000

# 不用 --reload（生产/ECS 不需要热重载）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
