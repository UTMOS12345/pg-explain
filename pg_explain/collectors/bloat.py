from __future__ import annotations

from dataclasses import dataclass

import psycopg2


@dataclass
class BloatStat:
    tablename: str
    size_bytes: int
    bloat_bytes: int
    bloat_pct: float

    @property
    def size_display(self) -> str:
        return _fmt_bytes(self.size_bytes)

    @property
    def waste_display(self) -> str:
        return _fmt_bytes(self.bloat_bytes)


def _fmt_bytes(b: int) -> str:
    if b >= 1 << 30:
        return f"{b / (1 << 30):.1f} GB"
    if b >= 1 << 20:
        return f"{b / (1 << 20):.1f} MB"
    if b >= 1 << 10:
        return f"{b / (1 << 10):.1f} kB"
    return f"{b} B"


def estimate_bloat(conn_string: str, top_n: int = 10) -> list[BloatStat]:
    conn = psycopg2.connect(conn_string, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  relname,
                  pg_table_size(oid) AS size_bytes,
                  pg_table_size(oid) - pg_relation_size(oid) AS bloat_bytes,
                  CASE
                    WHEN pg_table_size(oid) > 0
                    THEN ROUND(
                      (pg_table_size(oid) - pg_relation_size(oid))::numeric
                      / pg_table_size(oid) * 100, 1
                    )
                    ELSE 0
                  END AS bloat_pct
                FROM pg_class
                WHERE relkind = 'r'
                  AND relpages > 0
                ORDER BY bloat_bytes DESC
                LIMIT %s
            """, (top_n,))
            return [BloatStat(*r) for r in cur.fetchall()]
    finally:
        conn.close()