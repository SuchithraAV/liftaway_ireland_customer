from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Date, ForeignKey, Text, TypeDecorator, CHAR, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import uuid
import enum


# Cross-dialect GUID type: uses Postgres' UUID when available, otherwise CHAR(36)
class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses Postgresql's UUID type, otherwise stores as CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        # store as string on other dialects
        return str(value)

    def process_result_value(self, value, dialect):
        return value

class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    COMPANY = "company"

class IssueStatus(str, enum.Enum):
    AWAITING_PAYMENT = "awaiting_payment"
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class IssuePaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PAID = "paid"

class Customer(Base):
    __tablename__ = "customers"
    
    # Use a cross-dialect GUID type so the models work on Postgres and MySQL
    class GUID(TypeDecorator):
        """Platform-independent GUID type.

        Uses Postgresql's UUID type, otherwise stores as CHAR(36).
        """
        impl = CHAR
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == 'postgresql':
                return dialect.type_descriptor(PG_UUID(as_uuid=True))
            else:
                return dialect.type_descriptor(CHAR(36))

        def process_bind_param(self, value, dialect):
            if value is None:
                return value
            if dialect.name == 'postgresql':
                return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
            # store as string on other dialects
            return str(value)

        def process_result_value(self, value, dialect):
            return value

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    address = Column(Text, nullable=False)
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    mobile_otp = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    date_joined = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships

class Driver(Base):
    __tablename__ = "drivers"
    
    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == 'postgresql':
                return dialect.type_descriptor(PG_UUID(as_uuid=True))
            else:
                return dialect.type_descriptor(CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return value
            if dialect.name == 'postgresql':
                return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return value
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    stripe_account_id = Column(String(255), nullable=True)
    date_joined = Column(DateTime(timezone=True), server_default=func.now())

class Admin(Base):
    __tablename__ = "admins"
    
    # Use a cross-dialect GUID type so the models work on Postgres and MySQL
    class GUID(TypeDecorator):
        """Platform-independent GUID type.

        Uses Postgresql's UUID type, otherwise stores as CHAR(36).
        """
        impl = CHAR
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == 'postgresql':
                return dialect.type_descriptor(PG_UUID(as_uuid=True))
            else:
                return dialect.type_descriptor(CHAR(36))

        def process_bind_param(self, value, dialect):
            if value is None:
                return value
            if dialect.name == 'postgresql':
                return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
            # store as string on other dialects
            return str(value)

        def process_result_value(self, value, dialect):
            return value

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    mobile_otp = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    date_joined = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    owned_companies = relationship("Company", back_populates="owner")

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    address = Column(Text)
    contact_number = Column(String(20))
    email = Column(String(255))
    
    # Location for "mechanic shed"
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    
    owner_id = Column(GUID(), ForeignKey("admins.id"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    owner = relationship("Admin", foreign_keys=[owner_id], back_populates="owned_companies")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    image_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    issues = relationship("Issue", back_populates="category")

class Issue(Base):
    __tablename__ = "issues"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(GUID(), ForeignKey("customers.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    description = Column(Text, nullable=False)
    pickup_location = Column(String(500), nullable=False)
    images = Column(JSON, nullable=False)  # Store array of image URLs as JSON
    assigned_driver_id = Column(GUID(), ForeignKey("drivers.id"), nullable=True)
    # Store driver location as a single string "lat,lng" for easy display in customer API
    driver_location = Column(String(100), nullable=True)
    _status = Column("status", String(20), default="awaiting_payment", nullable=False)
    otp_code = Column(String(6), nullable=False)
    payment_amount = Column(DECIMAL(10, 2), nullable=False)
    negotiated_price = Column(DECIMAL(10, 2), nullable=True)
    negotiated_status = Column(String(20), default="none", nullable=False)  # none, pending, accepted, rejected
    _payment_status = Column("payment_status", String(10), default="unpaid", nullable=False)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @property
    def status(self):
        return self._status.lower() if self._status else "pending"
    
    @status.setter
    def status(self, value):
        if hasattr(value, 'value'):
            self._status = value.value.lower()
        else:
            self._status = str(value).lower()
    
    @property
    def payment_status(self):
        return self._payment_status.lower() if self._payment_status else "unpaid"
    
    @payment_status.setter
    def payment_status(self, value):
        if hasattr(value, 'value'):
            self._payment_status = value.value.lower()
        else:
            self._payment_status = str(value).lower()
    
    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    category = relationship("Category", back_populates="issues")
    assigned_driver = relationship("Driver", foreign_keys=[assigned_driver_id])
    earnings = relationship("DriverEarning", back_populates="issue")
    rating = relationship("IssueRating", back_populates="issue", uselist=False)

class DriverEarning(Base):
    __tablename__ = "driver_earnings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(GUID(), ForeignKey("drivers.id"), nullable=False)
    issue_id = Column(GUID(), ForeignKey("issues.id"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    jobs_done = Column(Integer, default=1)
    amount = Column(DECIMAL(10, 2), nullable=False)
    stripe_transfer_id = Column(String(255), nullable=True)
    payout_status = Column(String(20), default="pending", nullable=False)
    
    # Relationships
    driver = relationship("Driver", foreign_keys=[driver_id])
    issue = relationship("Issue", back_populates="earnings")

class IssueRating(Base):
    __tablename__ = "issue_ratings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(GUID(), ForeignKey("issues.id"), nullable=False)
    customer_id = Column(GUID(), ForeignKey("customers.id"), nullable=False)
    driver_id = Column(GUID(), ForeignKey("drivers.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    issue = relationship("Issue", back_populates="rating")
    customer = relationship("Customer", foreign_keys=[customer_id])
    driver = relationship("Driver", foreign_keys=[driver_id])


class ChatMessage(Base):
    """Chat messages between customer and driver for an issue"""
    __tablename__ = "chat_messages"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    issue_id = Column(GUID(), ForeignKey("issues.id"), nullable=False, index=True)
    sender_id = Column(GUID(), nullable=False)  # Can be customer_id or driver_id
    sender_type = Column(String(20), nullable=False)  # "customer" or "driver"
    encrypted_text = Column(Text, nullable=False)  # Store encrypted message
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    issue = relationship("Issue", foreign_keys=[issue_id])


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), nullable=False, index=True)
    user_type = Column(String(20), nullable=False)  # 'customer' or 'driver'
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship helpers can be added if needed
