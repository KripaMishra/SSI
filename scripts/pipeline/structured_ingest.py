import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from datetime import datetime
import pandas as pd
from src.internal.db.session import init_db, get_session
from src.internal.db.models import (
    DimGeo, DimSku, DimRep, DimDistributor,
    FactPrimarySales, FactTargets, Promotions, Stockouts,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

CLEAN = Path(__file__).resolve().parents[2] / "cleaned"


def _parse_date(val: str):
    return datetime.strptime(val.strip(), "%Y-%m-%d").date()


def _parse_yearmonth(val: str):
    return datetime.strptime(val.strip(), "%Y-%m").date()


def ingest():
    logger.info("starting structured ingest", extra={"clean_dir": str(CLEAN)})
    engine = init_db()
    session = get_session(engine)

    dim_geo_df = pd.read_csv(CLEAN / "dim_geo.csv", dtype=str)
    for _, row in dim_geo_df.iterrows():
        session.add(DimGeo(territory=row["territory"], region=row["region"]))
    session.commit()
    logger.info("dim_geo ingested", extra={"rows": len(dim_geo_df)})

    dim_sku_df = pd.read_csv(CLEAN / "dim_sku.csv", dtype=str)
    for _, row in dim_sku_df.iterrows():
        session.add(DimSku(
            sku_code=row["sku_code"], category=row["category"],
            brand=row["brand"], sku_name=row["sku_name"],
            pack_size=row["pack_size"], flavour=row["flavour"],
            tier=row["tier"], base_mrp=row["base_mrp"],
        ))
    session.commit()
    logger.info("dim_sku ingested", extra={"rows": len(dim_sku_df)})

    dim_rep_df = pd.read_csv(CLEAN / "dim_rep.csv", dtype=str)
    for _, row in dim_rep_df.iterrows():
        session.add(DimRep(rep_id=row["rep_id"], rep_name=row["rep_name"], territory=row["territory"]))
    session.commit()
    logger.info("dim_rep ingested", extra={"rows": len(dim_rep_df)})

    dim_dist_df = pd.read_csv(CLEAN / "dim_distributor.csv", dtype=str)
    for _, row in dim_dist_df.iterrows():
        session.add(DimDistributor(
            distributor_id=row["distributor_id"],
            distributor_name=row["distributor_name"],
            territory=row["territory"],
        ))
    session.commit()
    logger.info("dim_distributor ingested", extra={"rows": len(dim_dist_df)})

    cols = ["week_start", "sku_code", "territory", "distributor_id", "primary_sales_units", "primary_sales_value", "sales_units_flag"]
    total_sales = 0
    for chunk_idx, chunk in enumerate(pd.read_csv(CLEAN / "fact_primary_sales.csv", dtype=str, usecols=cols, chunksize=5000)):
        for _, row in chunk.iterrows():
            session.add(FactPrimarySales(
                week_start=_parse_date(row["week_start"]),
                sku_code=row["sku_code"], territory=row["territory"],
                distributor_id=row["distributor_id"],
                primary_sales_units=int(float(row["primary_sales_units"])) if pd.notna(row["primary_sales_units"]) else None,
                primary_sales_value=float(row["primary_sales_value"]),
                sales_units_flag=row["sales_units_flag"],
            ))
        session.commit()
        total_sales += len(chunk)
        logger.debug("fact_primary_sales chunk committed", extra={"chunk": chunk_idx, "rows": len(chunk), "total_so_far": total_sales})
    logger.info("fact_primary_sales ingested", extra={"total_rows": total_sales})

    fact_targs_df = pd.read_csv(CLEAN / "fact_targets.csv", dtype=str)
    for _, row in fact_targs_df.iterrows():
        session.add(FactTargets(
            month=_parse_yearmonth(row["month"]),
            material_no=row["material_no"], area=row["area"],
            target_value=float(row["target_value"]),
        ))
    session.commit()
    logger.info("fact_targets ingested", extra={"rows": len(fact_targs_df)})

    promos_df = pd.read_csv(CLEAN / "promotions.csv", dtype=str)
    for _, row in promos_df.iterrows():
        session.add(Promotions(
            week_start=_parse_date(row["week_start"]),
            sku=row["sku"], territory=row["territory"],
            promo_type=row["promo_type"],
            promo_discount_pct=float(row["promo_discount_pct"]),
        ))
    session.commit()
    logger.info("promotions ingested", extra={"rows": len(promos_df)})

    stocks_df = pd.read_csv(CLEAN / "stockouts.csv", dtype=str)
    for _, row in stocks_df.iterrows():
        session.add(Stockouts(
            week_start=_parse_date(row["week_start"]),
            item_code=row["item_code"], territory=row["territory"],
            stockout_flag=row["stockout_flag"],
            stockout_days=int(row["stockout_days"]),
        ))
    session.commit()
    logger.info("stockouts ingested", extra={"rows": len(stocks_df)})

    session.close()
    logger.info("structured ingest complete")


def setup():
    init_db()
    logger.info("database setup complete (tables created)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Structured DB pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("setup", help="Create tables only")
    subparsers.add_parser("ingest", help="Create tables and ingest all CSVs")
    args = parser.parse_args()
    if args.command == "setup":
        setup()
    elif args.command == "ingest":
        ingest()