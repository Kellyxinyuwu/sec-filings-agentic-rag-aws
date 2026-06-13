#!/usr/bin/env python3
"""
Phase 5 Step 9 — full E2E on ALB (health, retrieve, golden /chat, REFUSE).

Reads tests/golden_queries.yaml (same cases as local NOTICE checklist).

用法（repo 根）：
    python scripts/alb_e2e.py
    python scripts/alb_e2e.py --base-url http://<alb-dns>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import boto3
import yaml
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_FILE = REPO_ROOT / "tests" / "golden_queries.yaml"
DEFAULT_REGION = "us-east-1"
STACK_NAME = "SecRagStack"


def _alb_url_from_stack(cfn, stack_name: str) -> str:
    resp = cfn.describe_stacks(StackName=stack_name)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    url = outputs.get("AlbUrl", "").strip()
    if not url:
        dns = outputs.get("AlbDnsName", "").strip()
        url = f"http://{dns}" if dns else ""
    if not url:
        raise ValueError(f"AlbUrl not in stack {stack_name}")
    return url.rstrip("/")


def _curl_json(method: str, url: str, body: dict | None = None, *, timeout: int = 180) -> tuple[int, dict | str, int]:
    cmd = ["curl", "-s", "--max-time", str(timeout), "-w", "\n__HTTP_CODE__:%{http_code}", "-X", method, url]
    if body is not None:
        cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(body)])
    cp = subprocess.run(cmd, capture_output=True, text=True)
    raw = cp.stdout if cp.stdout else cp.stderr
    http_code = 0
    if "__HTTP_CODE__:" in raw:
        body_text, _, code_part = raw.rpartition("\n__HTTP_CODE__:")
        http_code = int(code_part.strip() or "0")
        raw = body_text
    if http_code and http_code >= 400:
        return 1, raw or f"HTTP {http_code}", http_code
    if cp.returncode != 0 and http_code == 0:
        return cp.returncode, raw, http_code
    try:
        return 0, json.loads(raw), http_code
    except json.JSONDecodeError:
        return 0, raw, http_code


def _verifier_ok(data: dict, intent: str | None = None) -> bool:
    steps = data.get("agent_steps") or []
    if not steps:
        return False
    detail = steps[-1].get("detail") or ""
    if detail.startswith("fail-closed:") or "invalid citations" in detail:
        return False
    if intent == "refuse":
        return "refuse intent" in detail
    if detail == "citations ok" or detail.startswith("pass after retry:"):
        return True
    return False


def _check_chat_case(case_id: str, data: dict, expect: dict) -> list[str]:
    errors: list[str] = []
    plan = data.get("plan") or {}
    evidence = data.get("evidence") or []
    answer = (data.get("answer") or "").strip()

    intent = expect.get("intent")
    if intent and plan.get("intent") != intent:
        errors.append(f"{case_id}: intent want {intent!r} got {plan.get('intent')!r}")

    if expect.get("verifier_pass") and not _verifier_ok(data, intent=intent or plan.get("intent")):
        steps = data.get("agent_steps") or []
        detail = steps[-1].get("detail") if steps else "no steps"
        errors.append(f"{case_id}: verifier want 'citations ok' got {detail!r}")

    if "evidence_min" in expect:
        minimum = int(expect["evidence_min"])
        if len(evidence) < minimum:
            errors.append(f"{case_id}: evidence want >={minimum} got {len(evidence)}")

    if "evidence_count" in expect:
        want = int(expect["evidence_count"])
        if len(evidence) != want:
            errors.append(f"{case_id}: evidence want {want} got {len(evidence)}")

    prefixes = expect.get("answer_prefix")
    if prefixes and not answer.startswith(prefixes):
        errors.append(f"{case_id}: answer should start with {prefixes!r}")

    for needle in expect.get("answer_contains_any") or []:
        if needle.lower() not in answer.lower():
            errors.append(f"{case_id}: answer missing {needle!r}")
            break

    return errors


def _load_golden(path: Path) -> tuple[list[dict], list[dict]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("golden_queries") or []), list(data.get("refuse_samples") or [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 ALB E2E (golden_queries.yaml)")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack", default=STACK_NAME)
    parser.add_argument("--base-url", default="", help="skip CFN lookup if set")
    parser.add_argument("--golden-file", type=Path, default=GOLDEN_FILE)
    parser.add_argument("--skip-retrieve", action="store_true")
    args = parser.parse_args()

    if args.base_url.strip():
        base = args.base_url.strip().rstrip("/")
    else:
        cfn = boto3.client("cloudformation", region_name=args.region)
        try:
            base = _alb_url_from_stack(cfn, args.stack)
        except (ClientError, ValueError) as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

    golden, refuse = _load_golden(args.golden_file)
    print(f"ALB E2E: {base}")
    print(f"Spec: {args.golden_file.name} ({len(golden)} QA + {len(refuse)} REFUSE)")
    failures: list[str] = []

    code, health, http = _curl_json("GET", f"{base}/health", timeout=30)
    if code != 0 or not isinstance(health, dict):
        print(f"FAIL /health (HTTP {http}): {health}", file=sys.stderr)
        return 1
    print(f"OK /health status={health.get('status')} vector_backend={health.get('vector_backend')}")
    if health.get("status") != "ok":
        failures.append("/health: status not ok")

    if not args.skip_retrieve:
        code, retrieve, http = _curl_json(
            "POST",
            f"{base}/retrieve",
            {"query": "risk factors", "ticker": "AAPL", "top_k": 3},
            timeout=120,
        )
        if code != 0 or not isinstance(retrieve, dict):
            print(f"FAIL /retrieve (HTTP {http}): {retrieve}", file=sys.stderr)
            return 1
        chunks = retrieve.get("chunks") or []
        if not chunks:
            failures.append("/retrieve: empty chunks")
        else:
            print(f"OK /retrieve {len(chunks)} chunk(s) top={chunks[0].get('chunk_id', '?')}")

    for case in golden:
        case_id = case.get("id", "?")
        query = case["query"]
        ticker = case.get("ticker", "AAPL")
        print(f"\n--- chat QA [{case_id}] ---")
        code, data, http = _curl_json(
            "POST",
            f"{base}/chat",
            {"query": query, "ticker": ticker},
            timeout=180,
        )
        if code != 0 or not isinstance(data, dict):
            failures.append(f"{case_id}: HTTP {http} {data}")
            print(f"FAIL [{case_id}]")
            continue
        errs = _check_chat_case(case_id, data, case.get("expect") or {})
        if errs:
            failures.extend(errs)
            print(f"FAIL [{case_id}]: {'; '.join(errs)}")
        else:
            ev = len(data.get("evidence") or [])
            print(f"OK [{case_id}] intent={data.get('plan', {}).get('intent')} evidence={ev}")

    for case in refuse:
        case_id = case.get("id", "?")
        query = case["query"]
        print(f"\n--- chat REFUSE [{case_id}] ---")
        code, data, http = _curl_json("POST", f"{base}/chat", {"query": query}, timeout=60)
        if code != 0 or not isinstance(data, dict):
            failures.append(f"{case_id}: HTTP {http} {data}")
            print(f"FAIL [{case_id}]")
            continue
        errs = _check_chat_case(case_id, data, case.get("expect") or {})
        if errs:
            failures.extend(errs)
            print(f"FAIL [{case_id}]: {'; '.join(errs)}")
        else:
            print(f"OK [{case_id}] intent={data.get('plan', {}).get('intent')}")

    print()
    if failures:
        print(f"E2E FAIL ({len(failures)} issue(s)):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("E2E OK: health + retrieve + golden QA + REFUSE passed on ALB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
