"""SQLite database setup, ORM models, and deterministic seed data."""

from __future__ import annotations

import os
import hashlib
import ipaddress
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Generator

from passlib.context import CryptContext
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, LargeBinary, String, Text, create_engine, inspect, select, text
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

DB_INIT_MAX_ATTEMPTS = 3
DB_INIT_RETRY_DELAYS_SECONDS = (0.5, 1.0)


def _validate_mysql_host(host: str | None) -> str:
    """Validate a host before passing it to DNS resolution."""

    normalized_host = (host or "").strip().rstrip(".")
    if not normalized_host:
        raise RuntimeError(
            "MySQL host is empty or invalid. Set MYSQL_HOST to the database hostname only."
        )
    try:
        ipaddress.ip_address(normalized_host)
        return normalized_host
    except ValueError:
        pass

    try:
        ascii_host = normalized_host.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise RuntimeError(
            "MySQL host is invalid. Set MYSQL_HOST to the database hostname only, "
            "without a protocol, port, or database path."
        ) from error
    labels = ascii_host.split(".")
    if (
        len(ascii_host) > 253
        or any(
            not label
            or len(label) > 63
            or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label) is None
            for label in labels
        )
    ):
        raise RuntimeError(
            "MySQL host is invalid. Set MYSQL_HOST to the database hostname only, "
            "without a protocol, port, or database path."
        )
    return ascii_host


def _database_url() -> str | URL:
    """Resolve the configured database URL or PrimeCloud MySQL variables."""

    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        if database_url.startswith("mysql://"):
            return database_url.replace("mysql://", "mysql+pymysql://", 1)
        return database_url

    mysql_host_setting = os.getenv("MYSQL_HOST") or os.getenv("MYSQLHOST")
    if mysql_host_setting:
        mysql_host_setting = mysql_host_setting.strip()
        host_url: URL | None = None
        try:
            if "://" in mysql_host_setting:
                host_url = make_url(mysql_host_setting)
            elif "/" in mysql_host_setting or (
                ":" in mysql_host_setting and not mysql_host_setting.startswith("[")
            ):
                host_url = make_url(f"mysql://{mysql_host_setting}")
        except ArgumentError as error:
            raise RuntimeError(
                "MYSQL_HOST must be a hostname, or a valid host:port/database value."
            ) from error
        if host_url is not None and host_url.database and "/" in host_url.database:
            raise RuntimeError(
                "MYSQL_HOST must contain at most one database path segment; "
                "set the database separately in MYSQL_DATABASE."
            )
        mysql_host = _validate_mysql_host(
            host_url.host if host_url is not None else mysql_host_setting
        )
        mysql_user = os.getenv("MYSQL_USER") or os.getenv("MYSQLUSER")
        mysql_password = os.getenv("MYSQL_PASSWORD")
        if mysql_password is None:
            mysql_password = os.getenv("MYSQLPASSWORD")
        mysql_database = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE")
        port_setting = os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT") or "3306"
        port_text, separator, database_from_port = port_setting.partition("/")
        if not port_text.isdecimal() or not 1 <= int(port_text) <= 65535:
            raise RuntimeError(f"Invalid MySQL port: {port_text!r}")
        if host_url is not None and host_url.port is not None and not (
            os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT")
        ):
            port_text = str(host_url.port)
        if mysql_database is None:
            mysql_database = database_from_port or (
                host_url.database if host_url is not None else None
            )
        missing = [
            name
            for name, value in (
                ("MYSQL_USER", mysql_user),
                ("MYSQL_PASSWORD", mysql_password),
                ("MYSQL_DATABASE", mysql_database),
            )
            if value is None
        ]
        if missing:
            raise RuntimeError(
                f"MySQL configuration is incomplete; missing: {', '.join(missing)}"
            )
        return URL.create(
            "mysql+pymysql",
            username=mysql_user,
            password=mysql_password,
            host=mysql_host,
            port=int(port_text),
            database=mysql_database,
        )

    if os.getenv("APP_ENV", "").lower() == "production":
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL or MYSQL_HOST, MYSQL_USER, "
            "MYSQL_PASSWORD, and MYSQL_DATABASE."
        )
    return "sqlite:///./jenga_consultants.db"


DATABASE_URL = _database_url()

database_backend = (
    DATABASE_URL.get_backend_name()
    if isinstance(DATABASE_URL, URL)
    else make_url(DATABASE_URL).get_backend_name()
)
connect_args = {"check_same_thread": False} if database_backend == "sqlite" else {}
if database_backend == "mysql":
    connect_args.update({"connect_timeout": 10})
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
# PBKDF2 avoids the known passlib/bcrypt backend incompatibility while retaining
# passlib's constant-time verification and configurable work factor.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductDB(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    specifications: Mapped[str] = mapped_column(String(2000), nullable=False)
    price_ksh: Mapped[int] = mapped_column(Integer, nullable=False)


class ProductAccessDB(Base):
    """Explicit catalogue grants; a product without a grant is not retrievable."""

    __tablename__ = "product_access"
    __table_args__ = (
        CheckConstraint("access_level IN ('public', 'engineer')", name="valid_product_access_level"),
    )

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_role: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_used: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)


class SessionDB(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ConversationDB(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ConversationMessageDB(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class MediaDB(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MediaContentDB(Base):
    __tablename__ = "media_content"

    media_id: Mapped[str] = mapped_column(
        ForeignKey("media.id"), primary_key=True
    )
    content: Mapped[bytes] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"),
        nullable=False,
    )


class ReviewRequestDB(Base):
    __tablename__ = "review_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Verify the database connection, create tables, and seed initial data."""

    for attempt in range(1, DB_INIT_MAX_ATTEMPTS + 1):
        try:
            _initialize_database_once()
            return
        except OperationalError as error:
            if attempt == DB_INIT_MAX_ATTEMPTS:
                logger.error(
                    "Database initialization failed after %d attempts (%s). "
                    "Check database DNS, service networking, and connection settings.",
                    attempt,
                    type(error).__name__,
                )
                raise
            delay = DB_INIT_RETRY_DELAYS_SECONDS[attempt - 1]
            logger.warning(
                "Database initialization attempt %d/%d failed (%s); retrying in %.1f seconds.",
                attempt,
                DB_INIT_MAX_ATTEMPTS,
                type(error).__name__,
                delay,
            )
            time.sleep(delay)


def _initialize_database_once() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    had_access_table = inspect(engine).has_table("product_access")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(UserDB).where(UserDB.username == "engineer@jenga.com")) is None:
            db.add_all(
                [
                    UserDB(
                        username="engineer@jenga.com",
                        hashed_password=pwd_context.hash("engineer123"),
                        role="engineer",
                    ),
                    UserDB(
                        username="customer@jenga.com",
                        hashed_password=pwd_context.hash("customer123"),
                        role="customer",
                    ),
                ]
            )
        seed_products = db.scalar(select(ProductDB).where(ProductDB.model_number == "JCG-1000")) is None
        if seed_products:
            db.add_all(
                [
                    ProductDB(
                        category="generator",
                        name="Jenga Genset 1000",
                        model_number="JCG-1000",
                        specifications="1000 kVA, diesel, automatic transfer switch",
                        price_ksh=12500000,
                    ),
                    ProductDB(
                        category="transformer",
                        name="Jenga Dry-Type Transformer",
                        model_number="JCT-500",
                        specifications="500 kVA, 11/0.415 kV, low-noise enclosure",
                        price_ksh=3850000,
                    ),
                    ProductDB(
                        category="solar",
                        name="Jenga Solar Inverter",
                        model_number="JCS-50",
                        specifications="50 kW three-phase hybrid inverter",
                        price_ksh=875000,
                    ),
                ]
            )
        db.flush()
        if not had_access_table or seed_products:
            # One-time upgrade/new-db classification of the known shared demo
            # rows only. Never classify unknown products or overwrite a grant.
            for product in db.scalars(
                select(ProductDB).where(ProductDB.model_number.in_(["JCG-1000", "JCT-500", "JCS-50"]))
            ):
                if db.get(ProductAccessDB, product.id) is None:
                    db.add(ProductAccessDB(product_id=product.id, access_level="public"))
        db.commit()


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for audit records."""

    return datetime.now(timezone.utc)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
