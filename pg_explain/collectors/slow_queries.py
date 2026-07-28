from __future__ import annotations

from dataclasses import dataclass, field

import psycopg2


@dataclass
class SlowQuery:
    query: str
    total_time_ms: float
    calls: int
    mean_time_ms: float
    rows: int
    shared_blks_hit: int
    shared_blks_read: int

    @property
    def label(self) -> str:
        return (
            f"{self.total_time_ms / 1000:.1f}s total / "
            f"{self.calls} calls / "
            f"{self.mean_time_ms:.1f}ms avg"
        )


def get_slow_queries(conn_string: str, top_n: int = 5) -> list[SlowQuery]:
    try:
        conn = psycopg2.connect(conn_string, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT query,
                       total_exec_time,
                       calls,
                       mean_exec_time,
                       rows,
                       shared_blks_hit,
                       shared_blks_read
                FROM pg_stat_statements
                WHERE calls > 0
                ORDER BY total_exec_time DESC
                LIMIT %s
            """, (top_n,))
            return [
                SlowQuery(
                    query=r[0][:120],
                    total_time_ms=r[1],
                    calls=r[2],
                    mean_time_ms=r[3],
                    rows=r[4],
                    shared_blks_hit=r[5],
                    shared_blks_read=r[6],
                )
                for r in cur.fetchall()
            ]
    except (psycopg2.Error, Exception) as e:
        raise RuntimeError(f"pg_stat_statements not available: {e}")