"""
AWS client factories — S3 and OpenSearch Serverless (AOSS).

Phase 4 这个文件干什么？
-----------------------
  把「怎么连 AWS」集中在一处，避免 ingest / store / scripts 里到处写 boto3。

  本文件只负责：
    1. 读 config（settings）里的 bucket、endpoint、region
    2. 创建 S3 客户端（Step 2 上传 filing 用）
    3. 创建 OpenSearch Serverless 客户端（Step 4 写入/检索向量用）

  本文件不负责：
    - 算 embedding（仍在 store.py + 本地 MiniLM）
    - 调 LLM（仍在 llm_mantle.py）
    - agent 逻辑

为什么 import 本文件不会立刻连 AWS？
------------------------------------
  只有调用 get_s3_client() / get_opensearch_client() 时才会创建 Session、签名。
  pytest 只测 vector_backend() 等纯函数时，不会触发网络。

鉴权方式
--------
  boto3 默认凭证链（按顺序尝试）：
    1. 环境变量 AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
    2. ~/.aws/credentials
    3. AWS_PROFILE 指向的 profile（SSO 登录后常用）

  OpenSearch Serverless 不是用用户名密码，而是用 IAM 凭证做 SigV4 签名，
  服务名必须是 "aoss"（和经典 OpenSearch 域名的 "es" 不同）。
"""

from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import urlparse

import boto3
import structlog
from botocore.client import BaseClient
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from app.config import settings

log = structlog.get_logger()

# OpenSearch *Serverless* 的 SigV4 service name（固定字符串，不能写成 "es"）
OPENSEARCH_SERVERLESS_SERVICE = "aoss"


# ---------------------------------------------------------------------------
# 后端选择 — store.py / ingest 将来根据这些决定写 pgvector 还是 OpenSearch
# ---------------------------------------------------------------------------


def vector_backend() -> str:
    """
    当前向量检索走哪条后端：local（pgvector）或 opensearch。

    对应 .env 的 VECTOR_BACKEND；统一转小写，避免 Local / OPENSEARCH 大小写踩坑。
    """
    return settings.vector_backend.strip().lower()


def use_opensearch() -> bool:
    """True → retrieve 应走 OpenSearch（Phase 4 Step 6 接好 store 后生效）。"""
    return vector_backend() == "opensearch"


def use_local_pgvector() -> bool:
    """True → 仍用 Phase 1 的 Docker pgvector（默认，保证 Phase 3 行为不变）。"""
    return vector_backend() == "local"


# ---------------------------------------------------------------------------
# 配置校验 — 在真正调 AWS 之前 fail fast，错误信息更清楚
# ---------------------------------------------------------------------------


def parse_opensearch_host(endpoint: str) -> str:
    """
    从 .env 的 OPENSEARCH_ENDPOINT 解析出纯 hostname。

    控制台可能复制两种格式：
      - https://abc123.us-east-1.aoss.amazonaws.com
      - abc123.us-east-1.aoss.amazonaws.com

    opensearch-py 的 hosts 参数只要 hostname（port 我们固定 443）。
    """
    endpoint = endpoint.strip()
    if not endpoint:
        raise ValueError("OPENSEARCH_ENDPOINT is empty")
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        if not parsed.hostname:
            raise ValueError(f"Invalid OPENSEARCH_ENDPOINT: {endpoint!r}")
        return parsed.hostname
    return endpoint.rstrip("/")


# AWS S3 bucket naming (simplified check before boto3 ParamValidationError)
_S3_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")


def require_s3_bucket() -> str:
    """
    Step 2 上传前必须有合法 bucket 名。

    空字符串或文档占位符（中文说明文字）时立刻报错，比 boto3 的 ParamValidationError 更易懂。
    真 bucket 名示例：kelly-sec-rag-filings-2026（全小写、全球唯一、在 S3 控制台创建）
    """
    bucket = settings.s3_bucket.strip()
    if not bucket:
        raise ValueError(
            "S3_BUCKET is empty — set a real bucket name in .env (Phase 4 Step 2)"
        )
    if not _S3_BUCKET_RE.match(bucket):
        raise ValueError(
            f"S3_BUCKET={bucket!r} is not a valid S3 bucket name. "
            "Use lowercase letters, numbers, and hyphens only (e.g. kelly-sec-rag-filings-2026). "
            "Create the bucket in AWS S3 console (us-east-1) first — do not paste tutorial placeholder text."
        )
    return bucket


def require_opensearch_endpoint() -> str:
    """Step 3+ 连 OpenSearch 前必须有 endpoint。"""
    return parse_opensearch_host(settings.opensearch_endpoint)


def is_opensearch_configured() -> bool:
    """OPENSEARCH_ENDPOINT 非空才启用云索引（pytest 默认空 → 不调 AWS）。"""
    return bool(settings.opensearch_endpoint.strip())


# ---------------------------------------------------------------------------
# boto3 Session — 所有 AWS 客户端共享 region（和 settings.aws_region 一致）
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_boto3_session() -> boto3.Session:
    """
    缓存一个 Session，避免每次 get_s3_client 都重新读磁盘凭证。

    lru_cache：进程内只建一次；测试里用 clear_aws_client_cache() 清掉。
    """
    log.debug("boto3_session", region=settings.aws_region)
    return boto3.Session(region_name=settings.aws_region)


def get_s3_client() -> BaseClient:
    """
    返回 boto3 S3 client。

    Step 2 用途示例：put_object 上传 raw filing；list_objects_v2 列前缀。
    不在本函数里做 upload — 只负责「拿到合法 client」。
    """
    return get_boto3_session().client("s3")


# ---------------------------------------------------------------------------
# OpenSearch Serverless — HTTPS + IAM SigV4（无 master user / password）
# ---------------------------------------------------------------------------


def _opensearch_aws4auth() -> AWS4Auth:
    """
    为 OpenSearch Serverless 构造 AWS4 签名头。

    流程：
      1. 从 Session 取当前 IAM 凭证（含临时 session token 时一并带上）
      2. 用 requests-aws4auth 包成 opensearch-py 需要的 http_auth

    若本地没配 AWS 凭证（没 aws configure / 没 AWS_PROFILE），这里会报错。
    """
    session = get_boto3_session()
    credentials = session.get_credentials()
    if credentials is None:
        raise ValueError(
            "No AWS credentials for OpenSearch — configure AWS_PROFILE or access keys"
        )
    frozen = credentials.get_frozen_credentials()
    return AWS4Auth(
        frozen.access_key,
        frozen.secret_key,
        settings.aws_region,
        OPENSEARCH_SERVERLESS_SERVICE,
        session_token=frozen.token,
    )


def get_opensearch_client() -> OpenSearch:
    """
    返回 opensearch-py 客户端，用于 index / search / bulk。

    约定：
      - 端口 443 + TLS（Serverless 要求）
      - index 名在 settings.opensearch_index（默认 sec-chunks）
      - 向量维度 384 在 index mapping 里定义（Step 3），与 MiniLM 一致

    pytest 里 patch OpenSearch 类即可，不会真连云端。
    """
    host = require_opensearch_endpoint()
    log.debug("opensearch_client", host=host, index=settings.opensearch_index)
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=_opensearch_aws4auth(),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=settings.opensearch_timeout_seconds,
    )


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------


def clear_aws_client_cache() -> None:
    """pytest fixture 用 — 每个测试前清 Session 缓存，避免测试间污染。"""
    get_boto3_session.cache_clear()
