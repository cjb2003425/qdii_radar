"""
SQLAlchemy models for notification system database.
"""
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class FundState(Base):
    """Track historical fund data for change detection."""
    __tablename__ = 'fund_states'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    premium_rate = Column(Float)
    limit_text = Column(String(100))
    market_price = Column(Float)
    valuation = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<FundState(code={self.fund_code}, premium={self.premium_rate}, time={self.timestamp})>"


class NotificationHistory(Base):
    """Log of all sent notifications."""
    __tablename__ = 'notification_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    fund_name = Column(String(100), nullable=False)
    alert_type = Column(String(50), nullable=False)  # 'premium_high', 'premium_low', 'limit_change'
    old_value = Column(Text)
    new_value = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    recipient_email = Column(String(255))

    def __repr__(self):
        return f"<NotificationHistory(fund={self.fund_code}, type={self.alert_type}, time={self.sent_at})>"


class NotificationConfig(Base):
    """Key-value configuration storage."""
    __tablename__ = 'notification_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<NotificationConfig(key={self.config_key}, value={self.config_value})>"


class EmailRecipient(Base):
    """Email recipients for notifications."""
    __tablename__ = 'email_recipients'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<EmailRecipient(email={self.email}, active={self.is_active})>"


class MonitoredFund(Base):
    """Funds that are enabled for monitoring."""
    __tablename__ = 'monitored_funds'

    fund_code = Column(String(20), primary_key=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MonitoredFund(code={self.fund_code}, enabled={self.enabled})>"


class FundTrigger(Base):
    """User-defined triggers for specific funds."""
    __tablename__ = 'fund_triggers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    trigger_type = Column(String(50), nullable=False)  # 'premium_high', 'premium_low', 'limit_change'
    threshold_value = Column(Float, nullable=True)  # e.g., 5.0 for premium rate
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<FundTrigger(fund={self.fund_code}, type={self.trigger_type}, threshold={self.threshold_value})>"


class HistoricalNavCache(Base):
    """Cache for historical NAV data to calculate 1-year percentage change."""
    __tablename__ = 'historical_nav_cache'

    fund_code = Column(String(20), primary_key=True, nullable=False)
    nav_1_year_ago = Column(Float, nullable=True)  # NAV value from ~1 year ago
    percentage_change = Column(Float, nullable=False, default=0)  # 1-year percentage change
    days_calculated = Column(Integer, nullable=False, default=0)  # Actual trading days found
    cached_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<HistoricalNavCache(code={self.fund_code}, change={self.percentage_change}%, days={self.days_calculated})>"


# Database setup
DATABASE_URL = "sqlite:///data/notifications.db"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")

        # Insert default configuration
        session = SessionLocal()
        try:
            default_configs = [
                ('smtp_enabled', 'false'),
                ('monitoring_enabled', 'true'),
                ('smtp_host', 'smtp.gmail.com'),
                ('smtp_port', '587'),
                ('smtp_username', ''),
                ('smtp_password', ''),
                ('smtp_from_email', ''),
                ('check_interval_seconds', '180'),
                ('premium_threshold_high', '5.0'),
                ('premium_threshold_low', '-5.0'),
                ('debounce_minutes', '1'),
                ('alert_time_period', 'all_day'),
            ]

            for key, value in default_configs:
                existing = session.query(NotificationConfig).filter_by(config_key=key).first()
                if not existing:
                    config = NotificationConfig(config_key=key, config_value=value)
                    session.add(config)
                else:
                    # Update existing config to ensure latest defaults
                    existing.config_value = value

            session.commit()
            logger.info("Default configuration inserted")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to insert default config: {e}")
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


def get_db():
    """Get database session."""
    session = SessionLocal()
    try:
        return session
    except Exception as e:
        session.close()
        logger.error(f"Failed to create database session: {e}")
        raise
