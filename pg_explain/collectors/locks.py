from __future__ import annotations

from dataclasses import dataclass

import psycopg2


@dataclass
class LockInfo:
    pid: int
    datname: str | None
    relname: str | None
    locktype: str
    mode: str
    granted: bool
    wait_event: str | None
    query: str | None
    age_seconds: int | None


def get_current_locks(conn_string: str) -> list[LockInfo]:
    conn = psycopg2.connect(conn_string, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  l.pid,
                  d.datname,
                  c.relname,
                  l.locktype,
                  l.mode,
                  l.granted,
                  a.wait_event,
                  a.query,
                  CASE
                    WHEN a.state_change IS NOT NULL
                    THEN EXTRACT(EPOCH FROM now() - a.state_change)::int
                  END AS age_seconds
                FROM pg_locks l
                LEFT JOIN pg_database d ON l.database = d.oid
                LEFT JOIN pg_class c ON l.relation = c.oid
                LEFT JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE a.pid IS NOT NULL
                  AND a.pid <> pg_backend_pid()
                ORDER BY a.state_change NULLS LAST
            """)
            return [LockInfo(*r) for r in cur.fetchall()]
    finally:
        conn.close()


@dataclass
class ActiveQuery:
    pid: int
    query: str
    duration_ms: float
    state: str
    wait_event: str | None
    backend_type: str


def get_active_queries(conn_string: str) -> list[ActiveQuery]:
    conn = psycopg2.connect(conn_string, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  pid,
                  query,
                  EXTRACT(EPOCH FROM now() - query_start) * 1000 AS duration_ms,
                  state,
                  wait_event,
                  backend_type
                FROM pg_stat_activity
                WHERE state = 'active'
                  AND pid <> pg_backend_pid()
                  AND query NOT LIKE '%pg_stat_activity%'
                ORDER BY duration_ms DESC
            """)
            return [ActiveQuery(*r) for r in cur.fetchall()]
    finally:
        conn.close()