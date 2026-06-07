"""Search helpers for SQLite notes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from src.domain.entities.note import Note, NoteFilter


@dataclass(frozen=True)
class SearchBuildContext:
    cursor: object
    filter_criteria: NoteFilter
    conditions: list[str]
    params: list[Any]


class SQLiteNoteSearchMixin:
    def search(self, filter_criteria: NoteFilter) -> Tuple[List[Note], int]:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            query, query_params = self._build_search_query(cursor, filter_criteria)
            cursor.execute(query, query_params)
            rows = cursor.fetchall()
            total_count = int(rows[0]["total_count"]) if rows else 0
            notes = [self._row_to_note(dict(row)) for row in rows]
            return notes, total_count

    def count(self, filter_criteria: NoteFilter) -> int:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            query, params = self._build_count_query(cursor, filter_criteria)
            cursor.execute(query, params)
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def _build_search_query(self, cursor, filter_criteria: NoteFilter) -> Tuple[str, List[Any]]:
        conditions, params = self._build_filter_conditions(filter_criteria, include_search=False)
        context = SearchBuildContext(cursor, filter_criteria, conditions, params)
        order_clause, fts_query = self._resolve_search_strategy(context)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        if fts_query:
            return self._fts_search_query(where_clause, order_clause), (
                [fts_query] + list(params) + [filter_criteria.limit, filter_criteria.offset]
            )
        return self._plain_search_query(where_clause, order_clause), (
            list(params) + [filter_criteria.limit, filter_criteria.offset]
        )

    def _resolve_search_strategy(self, context: SearchBuildContext):
        order_clause = "notes.timestamp DESC"
        search_query = (context.filter_criteria.search_query or "").strip()
        if not search_query:
            return order_clause, None
        candidate_fts_query = self._build_fts_query(search_query)
        if candidate_fts_query and self._notes_fts_exists(context.cursor):
            return "rank ASC, notes.timestamp DESC", candidate_fts_query
        self._append_like_search(context.conditions, context.params, search_query)
        return order_clause, None

    @staticmethod
    def _append_like_search(conditions, params, search_query) -> None:
        conditions.append("(notes.message_text LIKE ? OR notes.source_name LIKE ?)")
        pattern = f"%{search_query}%"
        params.extend([pattern, pattern])

    @staticmethod
    def _fts_search_query(where_clause: str, order_clause: str) -> str:
        return f"""SELECT notes.*, f.rank AS rank, COUNT(*) OVER() AS total_count
        FROM (
            SELECT rowid AS note_id, bm25(notes_fts) AS rank
            FROM notes_fts
            WHERE notes_fts MATCH ?
        ) AS f
        JOIN notes ON notes.id = f.note_id
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?"""

    @staticmethod
    def _plain_search_query(where_clause: str, order_clause: str) -> str:
        return f"""SELECT notes.*, COUNT(*) OVER() AS total_count
        FROM notes
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?"""

    def _build_count_query(self, cursor, filter_criteria: NoteFilter) -> Tuple[str, List[Any]]:
        conditions, params = self._build_filter_conditions(filter_criteria, include_search=False)
        search_query = (filter_criteria.search_query or "").strip()
        if search_query:
            fts_query = self._build_fts_query(search_query)
            if fts_query and self._notes_fts_exists(cursor):
                return self._fts_count_query(conditions), [fts_query] + list(params)
            self._append_like_search(conditions, params, search_query)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return f"SELECT COUNT(*) FROM notes WHERE {where_clause}", params

    @staticmethod
    def _fts_count_query(conditions) -> str:
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return (
            "SELECT COUNT(*) FROM (SELECT notes.id FROM notes_fts "
            "JOIN notes ON notes.id = notes_fts.rowid "
            f"WHERE notes_fts MATCH ? AND {where_clause})"
        )

    def _build_filter_conditions(
        self,
        filter_criteria: NoteFilter,
        include_search: bool = True,
    ) -> Tuple[List[str], List[Any]]:
        conditions = []
        params = []
        self._append_basic_filters(conditions, params, filter_criteria)
        if include_search and filter_criteria.search_query:
            self._append_like_search(conditions, params, filter_criteria.search_query)
        return conditions, params

    @staticmethod
    def _append_basic_filters(conditions, params, filter_criteria: NoteFilter) -> None:
        if filter_criteria.user_id is not None:
            conditions.append("notes.user_id = ?")
            params.append(filter_criteria.user_id)
        if filter_criteria.source_chat_id is not None:
            conditions.append("notes.source_chat_id = ?")
            params.append(filter_criteria.source_chat_id)
        if filter_criteria.favorite_only:
            conditions.append("notes.is_favorite = 1")
        if filter_criteria.date_from:
            conditions.append("notes.timestamp >= ?")
            params.append(f"{filter_criteria.date_from} 00:00:00")
        if filter_criteria.date_to:
            conditions.append("notes.timestamp <= ?")
            params.append(f"{filter_criteria.date_to} 23:59:59")

    @staticmethod
    def _notes_fts_exists(cursor) -> bool:
        try:
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts' LIMIT 1")
            return cursor.fetchone() is not None
        except Exception:
            return False

    def _build_fts_query(self, search_query: str) -> Optional[str]:
        regex = self._regex()
        tokens = regex.findall(r"[0-9A-Za-z\u4e00-\u9fff]+", search_query)
        normalized = _normalize_search_tokens(tokens)
        if not normalized or _has_cjk_token(normalized, regex):
            return None
        return " AND ".join(f"{term}*" if len(term) >= 2 else term for term in normalized)


def _normalize_search_tokens(tokens) -> list[str]:
    normalized = []
    seen = set()
    for token in tokens:
        term = token.strip()
        key = term.lower()
        if not term or key in seen:
            continue
        seen.add(key)
        normalized.append(term)
    return normalized


def _has_cjk_token(tokens, regex) -> bool:
    cjk_pattern = regex.compile(r"[\u4e00-\u9fff]")
    return any(cjk_pattern.search(term) for term in tokens)
