from __future__ import annotations

from dataclasses import dataclass

import psycopg2


@dataclass
class IndexStat:
    tablename: str
    indexname: str
    idx_scan: int
    idx_tup_read: int
    idx_tup_fetch: int
    size_kb: int

    @property
    def label(self) -> str:
        return f"{self.idx_scan:,} scans / {self.size_kb:,}kB"


def get_index_stats(conn_string: str) -> tuple[list[IndexStat], list[str]]:
    conn = psycopg2.connect(conn_string, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  t.relname AS tablename,
                  i.relname AS indexname,
                  s.idx_scan,
                  s.idx_tup_read,
                  s.idx_tup_fetch,
                  pg_relation_size(i.oid) / 1024 AS size_kb
                FROM pg_stat_user_indexes s
                JOIN pg_class i ON i.oid = s.indexrelid
                JOIN pg_class t ON t.oid = s.indrelid
                ORDER BY s.idx_scan ASC
            """)
            rows = cur.fetchall()

        stats = [IndexStat(*r) for r in rows]

        unused = [
            f"{s.tablename}.{s.indexname}"
            for s in stats
            if s.idx_scan == 0
        ]

        return stats, unused
    finally:
        conn.close()


def get_seq_scans_by_table(conn_string: str, threshold: int = 1000) -> list[tuple[str, int]]:
    conn = psycopg2.connect(conn_string, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT relname, seq_scan
                FROM pg_stat_user_tables
                WHERE seq_scan > %s
                ORDER BY seq_scan DESC
            """, (threshold,))
            return cur.fetchall()
    finally:
        conn.close()