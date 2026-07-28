from __future__ import annotations

import json
import sys

import psycopg2

from pg_explain.config import DbConfig


def _ensure_json_str(val) -> str:
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)


def execute_explain(cfg: DbConfig, query: str, timeout_ms: int = 30000) -> str:
    conn = psycopg2.connect(cfg.conn_string, connect_timeout=10)
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (timeout_ms,))
            cur.execute(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) %s" % query
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("EXPLAIN returned no rows")
            return _ensure_json_str(row[0])
    finally:
        conn.close()


def execute_explain_estimate(cfg: DbConfig, query: str) -> str:
    conn = psycopg2.connect(cfg.conn_string, connect_timeout=10)
    try:
        with conn.cursor() as cur:
            cur.execute("EXPLAIN (FORMAT JSON) %s" % query)
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("EXPLAIN returned no rows")
            return _ensure_json_str(row[0])
    finally:
        conn.close()


def read_plan_from_file(path: str) -> str:
    with open(path) as f:
        content = f.read().strip()
    if content.startswith("["):
        return content
    start = content.find("[")
    if start == -1:
        raise ValueError("No JSON array found in EXPLAIN output")
    end = content.rfind("]") + 1
    return content[start:end]


def read_plan_from_stdin() -> str:
    content = sys.stdin.read().strip()
    if not content:
        raise ValueError("No input received from stdin")
    if content.startswith("["):
        return content
    start = content.find("[")
    if start == -1:
        raise ValueError("No JSON array found in stdin")
    end = content.rfind("]") + 1
    return content[start:end]


def test_connection(cfg: DbConfig) -> str:
    conn = psycopg2.connect(cfg.conn_string, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            return cur.fetchone()[0]
    finally:
        conn.close()