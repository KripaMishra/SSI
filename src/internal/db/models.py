from sqlalchemy import Column, String, Float, Integer, Date, ForeignKey
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DimGeo(Base):
    __tablename__ = "dim_geo"
    territory = Column(String, primary_key=True)
    region = Column(String, nullable=False)


class DimSku(Base):
    __tablename__ = "dim_sku"
    sku_code = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    sku_name = Column(String, nullable=False)
    pack_size = Column(String, nullable=False)
    flavour = Column(String, nullable=False)
    tier = Column(String, nullable=False)
    base_mrp = Column(String, nullable=False)


class DimRep(Base):
    __tablename__ = "dim_rep"
    rep_id = Column(String, primary_key=True)
    rep_name = Column(String, nullable=False)
    territory = Column(String, ForeignKey("dim_geo.territory"), nullable=False)


class DimDistributor(Base):
    __tablename__ = "dim_distributor"
    distributor_id = Column(String, primary_key=True)
    distributor_name = Column(String, nullable=False)
    territory = Column(String, ForeignKey("dim_geo.territory"), nullable=False)


class FactPrimarySales(Base):
    __tablename__ = "fact_primary_sales"
    week_start = Column(Date, primary_key=True)
    sku_code = Column(String, ForeignKey("dim_sku.sku_code"), primary_key=True)
    territory = Column(String, ForeignKey("dim_geo.territory"), primary_key=True)
    distributor_id = Column(String, ForeignKey("dim_distributor.distributor_id"), primary_key=True)
    primary_sales_units = Column(Integer, nullable=True)
    primary_sales_value = Column(Float, nullable=False)
    sales_units_flag = Column(String, nullable=False)


class FactTargets(Base):
    __tablename__ = "fact_targets"
    month = Column(Date, primary_key=True)
    material_no = Column(String, ForeignKey("dim_sku.sku_code"), primary_key=True)
    area = Column(String, ForeignKey("dim_geo.territory"), primary_key=True)
    target_value = Column(Float, nullable=False)


class Promotions(Base):
    __tablename__ = "promotions"
    week_start = Column(Date, primary_key=True)
    sku = Column(String, ForeignKey("dim_sku.sku_code"), primary_key=True)
    territory = Column(String, ForeignKey("dim_geo.territory"), primary_key=True)
    promo_type = Column(String, nullable=False)
    promo_discount_pct = Column(Float, nullable=False)


class Stockouts(Base):
    __tablename__ = "stockouts"
    week_start = Column(Date, primary_key=True)
    item_code = Column(String, ForeignKey("dim_sku.sku_code"), primary_key=True)
    territory = Column(String, ForeignKey("dim_geo.territory"), primary_key=True)
    stockout_flag = Column(String, nullable=False)
    stockout_days = Column(Integer, nullable=False)
