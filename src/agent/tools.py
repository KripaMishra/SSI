import json
from langchain_core.tools import tool
from src.internal.db.vector import query_chroma
from src.internal.db.models import (
    DimGeo, DimSku, DimRep, DimDistributor,
    FactPrimarySales, FactTargets, Promotions, Stockouts,
)
from sqlalchemy import select
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
        return json.dumps({"results": [], "citations": [], "error": str(e)})


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
    """Convert an ORM row to a plain dict."""
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}


@tool
def query_database(table: str, filters: dict | None = None, limit: int = 100) -> str:
    """Query the relational database using ORM. Specify the table name and optional filter conditions.

    Args:
        table: One of: dim_geo, dim_sku, dim_rep, dim_distributor, fact_primary_sales, fact_targets, promotions, stockouts
        filters: Optional dict of column=value conditions (e.g. {"territory": "Mumbai", "sku": "SC-004"})
        limit: Maximum rows to return (default 100, max 1000)
    """
    logger.info("tool:query_database", extra={"table": table, "filters": filters, "limit": limit})

    model = _MODEL_MAP.get(table)
    if model is None:
        return json.dumps({"error": f"Unknown table: {table}. Valid: {list(_MODEL_MAP.keys())}", "citations": []})

    limit = min(limit, 1000)

    from src.internal.db.session import get_engine
    from sqlalchemy.orm import Session

    engine = get_engine()
    try:
        stmt = select(model)
        if filters:
            for col_name, value in filters.items():
                col = getattr(model, col_name, None)
                if col is not None:
                    stmt = stmt.where(col == value)
        stmt = stmt.limit(limit)

        with Session(engine) as session:
            rows = list(session.execute(stmt).scalars().all())

        result_rows = [_row_to_dict(r) for r in rows]
        citations = [f"relational_db:{table}"] if result_rows else []

        logger.info("tool:query_database success", extra={"rows_returned": len(result_rows), "citations": citations})
        return json.dumps({"rows": result_rows, "total": len(result_rows), "citations": citations}, default=str)
    except Exception as e:
        logger.exception("tool:query_database error", extra={"table": table, "filters": filters})
        return json.dumps({"error": str(e), "citations": []})
    finally:
        engine.dispose()