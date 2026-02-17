"""
Waste Management Models
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, ForeignKey, Text, DECIMAL, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
from core.models import GUID
import uuid
import enum

class LoadType(str, enum.Enum):
    MINIMUM = "minimum"
    QUARTER = "quarter"
    HALF = "half"
    THREE_QUARTER = "three_quarter"
    FULL = "full"

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class PaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    REFUNDED = "refunded"

class PricingSlab(Base):
    """UK Waste Removal Pricing Structure"""
    __tablename__ = "pricing_slabs"
    
    id = Column(Integer, primary_key=True)
    load_type = Column(String(20), nullable=False)  # minimum, quarter, half, three_quarter, full
    weight_min_kg = Column(Integer, nullable=False)
    weight_max_kg = Column(Integer, nullable=False)
    time_min_minutes = Column(Integer, nullable=False)
    time_max_minutes = Column(Integer, nullable=False)
    price_min_gbp = Column(DECIMAL(10, 2), nullable=False)
    price_max_gbp = Column(DECIMAL(10, 2), nullable=False)
    avg_price_gbp = Column(DECIMAL(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WasteJob(Base):
    """Waste Collection Job"""
    __tablename__ = "waste_jobs"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(GUID(), ForeignKey("customers.id"), nullable=False)
    driver_id = Column(GUID(), ForeignKey("drivers.id"), nullable=True)
    
    # Job Details
    load_type = Column(String(20), nullable=False)
    estimated_weight_kg = Column(Integer, nullable=False)
    estimated_time_minutes = Column(Integer, nullable=False)
    pickup_address = Column(Text, nullable=False)
    pickup_postcode = Column(String(10), nullable=False)
    pickup_lat = Column(DECIMAL(10, 7), nullable=True)
    pickup_lng = Column(DECIMAL(10, 7), nullable=True)
    waste_description = Column(Text, nullable=False)
    waste_images = Column(JSON, nullable=True)
    
    # Pricing (immutable once set)
    customer_price_gbp = Column(DECIMAL(10, 2), nullable=False)
    driver_price_gbp = Column(DECIMAL(10, 2), nullable=False)
    platform_fee_gbp = Column(DECIMAL(10, 2), nullable=False)
    ai_predicted_price = Column(DECIMAL(10, 2), nullable=True)
    specialist_waste_fee = Column(DECIMAL(10, 2), default=0)
    
    # Status
    status = Column(String(20), default="pending")
    payment_status = Column(String(20), default="unpaid")
    stripe_payment_intent_id = Column(String(255), nullable=True)
    completion_otp = Column(String(6), nullable=True)
    
    # Timestamps
    scheduled_pickup_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    driver = relationship("Driver", foreign_keys=[driver_id])

class DriverDailyEarnings(Base):
    """Driver Daily Earnings Summary"""
    __tablename__ = "driver_daily_earnings"
    
    id = Column(Integer, primary_key=True)
    driver_id = Column(GUID(), ForeignKey("drivers.id"), nullable=False)
    date = Column(Date, nullable=False)
    jobs_completed = Column(Integer, default=0)
    total_earnings_gbp = Column(DECIMAL(10, 2), default=0)
    total_customer_payments = Column(DECIMAL(10, 2), default=0)
    platform_fees_deducted = Column(DECIMAL(10, 2), default=0)
    payout_status = Column(String(20), default="pending")
    stripe_payout_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('driver_id', 'date', name='unique_driver_daily_earnings'),)
    
    # Relationships
    driver = relationship("Driver", foreign_keys=[driver_id])

class PlatformDailyRevenue(Base):
    """Platform Daily Revenue Summary"""
    __tablename__ = "platform_daily_revenue"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    total_jobs = Column(Integer, default=0)
    total_revenue_gbp = Column(DECIMAL(10, 2), default=0)
    total_customer_payments = Column(DECIMAL(10, 2), default=0)
    total_driver_payouts = Column(DECIMAL(10, 2), default=0)
    platform_fees_collected = Column(DECIMAL(10, 2), default=0)
    withdrawal_status = Column(String(20), default="available")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('date', name='unique_platform_daily_revenue'),)

class JobTransaction(Base):
    """Immutable Audit Trail for All Job Transactions"""
    __tablename__ = "job_transactions"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id = Column(GUID(), ForeignKey("waste_jobs.id"), nullable=False)
    transaction_type = Column(String(30), nullable=False)  # customer_payment, driver_payout, platform_fee
    amount_gbp = Column(DECIMAL(10, 2), nullable=False)
    stripe_reference = Column(String(255), nullable=True)
    status = Column(String(20), default="pending")
    extra_data = Column(JSON, nullable=True)  # Renamed from metadata (reserved word)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("WasteJob", foreign_keys=[job_id])