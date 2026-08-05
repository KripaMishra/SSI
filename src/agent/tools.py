import json
from langchain_core.tools import tool
from src.internal.db.vector import query_chroma
from src.internal.db.models import (
    DimGeo, DimSku, DimRep, DimDistributor,
    FactPrimarySales, FactTargets, Promotions, Stockouts,
)
from sqlalchemy import select, func, text
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MODEL_MAP = {
    "dim_geo": DimGeo,
    "dim_sku": DimSku,
    "dim_rep": DimRep,
    "dim_distributor": DimDistributor,
    "fact_primary_sales": FactPrimarySales,
    "fact_targets": FactTargets,
    "promotions": Promotions,
    "stockouts": Stockouts,
}

_JOIN_TABLES = [
    "dim_geo", "dim_sku", "dim_rep", "dim_distributor",
    "fact_primary_sales", "fact_targets", "promotions", "stockouts",
]

_AGG_FUNCS = {
    "SUM": func.sum,
    "AVG": func.avg,
    "COUNT": func.count,
    "MIN": func.min,
    "MAX": func.max,
}


def _get_table_schema():
    lines = []
    for name, model in _MODEL_MAP.items():
        cols = []
        for col in model.__table__.columns:
            pk = "PK" if col.primary_key else ""
            fk_notes = []
            for fk_col in col.foreign_keys:
                fk_notes.append(f"FK->{fk_col.column.table.name}.{fk_col.column.name}")
            tags = " ".join(t for t in [pk] + fk_notes if t)
            cols.append(f"  {col.name}: {col.type} {tags}".strip())
        lines.append(f"\n{name}\n" + "\n".join(cols))
    return "\n".join(lines)


@tool
def search_docs(query: str, top_k: int = 5) -> str:
    """Search the SSI documents vector database. Use for finding relevant documents, emails, reviews, and notes."""
    logger.info("tool:search_docs", extra={"query": query[:100], "top_k": top_k})
    try:
        results = query_chroma(query, n_results=top_k)
        if not results:
            logger.info("tool:search_docs no results", extra={"query": query[:100]})
            return json.dumps({"results": [], "citations": []})

        lines = []
        citations = []
        for r in results:
            meta = r["metadata"]
            doc_id = meta.get("ref", "unknown")
            citations.append(f"vector_db:SSI:{doc_id}")
            lines.append(
                f"[{meta.get('category', '?')} | {doc_id}] "
                f"(distance={r['distance']:.4f}, tags={meta.get('tags', '')})\n"
                f"{r['document'][:600]}"
            )
        logger.info("tool:search_docs found", extra={"count": len(results), "citations": citations})
        return json.dumps({"results": lines, "citations": citations})
    except Exception as e:
        logger.exception("tool:search_docs error", extra={"query": query[:100]})
        return json.dumps({"results": [], "citations": [], "tool_error": str(e)})


@tool
def describe_database() -> str:
    """Describe the relational database schema: tables, columns, types, and foreign key relationships."""
    logger.info("tool:describe_database")
    try:
        schema = _get_table_schema()
        logger.debug("tool:describe_database schema", extra={"tables": list(_MODEL_MAP.keys())})
        return "# Relational Database Schema\n" + schema
    except Exception:
        logger.exception("tool:describe_database error")
        return "Error retrieving schema"


def _row_to_dict(row) -> dict:
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}


def _build_citation(table: str, params: dict) -> str:
    parts = [f"table={table}"]
    for k, v in params.items():
        if v is not None and v != [] and v != {}:
            parts.append(f"{k}={json.dumps(v, default=str) if isinstance(v, (dict, list)) else v}")
    return "relational_db:" + "&".join(parts)


@tool
def query_database(
    table: str,
    columns: list[str] | None = None,
    filters: dict | None = None,
    joins: list[dict] | None = None,
    order_by: list[str] | None = None,
    group_by: list[str] | None = None,
    agg_functions: dict[str, str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Query the relational database using ORM. Supports joins, filters, aggregation, pagination, and ordering.

    Args:
        table: Primary table name. One of: dim_geo, dim_sku, dim_rep, dim_distributor, fact_primary_sales, fact_targets, promotions, stockouts
        columns: List of column names to return (e.g. ["territory", "primary_sales_units"]). Defaults to all columns.
        filters: Dict of column=value conditions (e.g. {"territory": "Mumbai"}). Supports __gt, __gte, __lt, __lte, __ne, __in, __like suffixes (e.g. {"primary_sales_units__gt": 500}).
        joins: List of join specs. Each is a dict: {"table": "dim_sku", "on": {"fact_primary_sales.sku_code": "dim_sku.sku_code"}} or {"table": "dim_sku", "on": "sku_code"} for same-named FK.
        order_by: List of ordering expressions (e.g. ["primary_sales_units DESC", "week_start ASC"]).
        group_by: List of column names to group by (e.g. ["territory"]).
        agg_functions: Aggregation functions for non-grouped columns. Dict of {column_name: "SUM"|"AVG"|"COUNT"|"MIN"|"MAX"} (e.g. {"primary_sales_units": "SUM", "primary_sales_value": "AVG"}).
        limit: Maximum rows to return (default 100, max 1000).
        offset: Number of rows to skip (for pagination).
    """
    logger.info("tool:query_database", extra={
        "table": table, "columns": columns, "filters": filters, "joins": joins,
        "order_by": order_by, "group_by": group_by, "agg_functions": agg_functions,
        "limit": limit, "offset": offset,
    })

    model = _MODEL_MAP.get(table)
    if model is None:
        return json.dumps({"tool_error": f"Unknown table: {table}. Valid: {list(_MODEL_MAP.keys())}", "citations": [], "rows": []})

    limit = min(limit, 1000)

    from src.internal.db.session import get_engine
    from sqlalchemy.orm import Session, joinedload

    engine = get_engine()
    try:
        stmt = select(model)

        if columns:
            orm_cols = [getattr(model, c, None) for c in columns]
            valid_cols = [c for c in orm_cols if c is not None]
            if not valid_cols and columns:
                return json.dumps({"tool_error": f"None of the requested columns exist on {table}", "citations": [], "rows": []})
            stmt = select(*valid_cols)

        if joins:
            for join_spec in joins:
                join_table_name = join_spec.get("table")
                join_model = _MODEL_MAP.get(join_table_name)
                if join_model is None:
                    logger.warning("tool:query_database invalid join table", extra={"join_table": join_table_name})
                    continue
                on_clause = join_spec.get("on")
                if isinstance(on_clause, str):
                    stmt = stmt.join(join_model, getattr(model, on_clause) == getattr(join_model, on_clause))
                elif isinstance(on_clause, dict):
                    conditions = []
                    for left_col, right_col in on_clause.items():
                        left_table_name, left_col_name = left_col.split(".")
                        right_table_name, right_col_name = right_col.split(".")
                        left_model = _MODEL_MAP.get(left_table_name)
                        right_model = _MODEL_MAP.get(right_table_name)
                        if left_model and right_model:
                            conditions.append(getattr(left_model, left_col_name) == getattr(right_model, right_col_name))
                    if conditions:
                        stmt = stmt.join(join_model, conditions[0] if len(conditions) == 1 else conditions)

        if filters:
            for col_name, value in filters.items():
                op = "eq"
                base_col = col_name
                if "__" in col_name:
                    base_col, op = col_name.rsplit("__", 1)
                col = getattr(model, base_col, None)
                if col is not None:
                    if op == "eq":
                        stmt = stmt.where(col == value)
                    elif op == "gt":
                        stmt = stmt.where(col > value)
                    elif op == "gte":
                        stmt = stmt.where(col >= value)
                    elif op == "lt":
                        stmt = stmt.where(col < value)
                    elif op == "lte":
                        stmt = stmt.where(col <= value)
                    elif op == "ne":
                        stmt = stmt.where(col != value)
                    elif op == "in":
                        stmt = stmt.where(col.in_(value if isinstance(value, list) else [value]))
                    elif op == "like":
                        stmt = stmt.where(col.like(value))

        if group_by or agg_functions:
            select_cols = []
            if group_by:
                for col_name in group_by:
                    col = getattr(model, col_name, None)
                    if col is not None:
                        select_cols.append(col)
                        stmt = stmt.group_by(col)
            if agg_functions:
                for col_name, agg_name in agg_functions.items():
                    agg_fn = _AGG_FUNCS.get(agg_name.upper())
                    if agg_fn:
                        col = getattr(model, col_name, None)
                        if col is not None:
                            select_cols.append(agg_fn(col).label(f"{agg_name.lower()}_{col_name}"))
            if select_cols:
                stmt = select(*select_cols)

        if order_by:
            for expr in order_by:
                parts = expr.strip().split()
                col_name = parts[0]
                direction = parts[1].upper() if len(parts) > 1 else "ASC"
                col = getattr(model, col_name, None)
                if col is not None:
                    if direction == "DESC":
                        stmt = stmt.order_by(col.desc())
                    else:
                        stmt = stmt.order_by(col.asc())

        stmt = stmt.limit(limit)
        if offset > 0:
            stmt = stmt.offset(offset)

        with Session(engine) as session:
            result = session.execute(stmt)
            if group_by or agg_functions or (columns and len(columns) != len(model.__table__.columns)):
                rows = [dict(row._mapping) for row in result]
            else:
                scalar_rows = list(result.scalars().all())
                rows = [_row_to_dict(r) for r in scalar_rows] if scalar_rows else []

        citation_params = {
            "columns": columns, "filters": filters, "joins": joins,
            "order_by": order_by, "group_by": group_by,
            "agg_functions": agg_functions, "limit": limit, "offset": offset,
        }
        citations = [f"relational_db:{table}?" + "&".join(f"{k}={json.dumps(v, default=str)}" for k, v in citation_params.items() if v is not None and v != [] and v != {})] if rows else []

        logger.info("tool:query_database success", extra={"rows_returned": len(rows), "citations": citations})
        return json.dumps({"rows": rows, "total": len(rows), "citations": citations}, default=str)
    except Exception as e:
        logger.exception("tool:query_database error", extra={"table": table, "filters": filters})
        return json.dumps({"tool_error": str(e), "citations": [], "rows": []})
    finally:
        engine.dispose()