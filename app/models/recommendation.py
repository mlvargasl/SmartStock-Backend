from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    forecast_date: Mapped[date] = mapped_column(Date, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    author = relationship("User", lazy="joined")
    items: Mapped[list["RecommendationItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="RecommendationItem.id")


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"
    __table_args__ = (
        UniqueConstraint("recommendation_id", "product_id", name="uq_recommendation_product"),
        CheckConstraint("predicted_units >= 0 AND final_units >= 0", name="ck_recommendation_quantities"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(150))
    predicted_units: Mapped[int] = mapped_column(Integer)
    final_units: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(500))


class RecommendationChange(Base):
    __tablename__ = "recommendation_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_item_id: Mapped[int] = mapped_column(ForeignKey("recommendation_items.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    previous_units: Mapped[int] = mapped_column(Integer)
    new_units: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductionConfirmation(Base):
    __tablename__ = "production_confirmations"
    id: Mapped[int] = mapped_column(primary_key=True)
    production_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), nullable=False)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ingredients: Mapped[list] = mapped_column(JSON, nullable=False)
    products: Mapped[list | None] = mapped_column(JSON, nullable=True)
