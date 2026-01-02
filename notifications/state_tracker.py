"""
State tracker for detecting changes in fund data.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy import desc
from .models import get_db, FundState, NotificationHistory, NotificationConfig, EmailRecipient, FundTrigger

logger = logging.getLogger(__name__)


class StateTracker:
    """Track fund states and detect changes for notifications."""

    def __init__(self):
        self.config = {}
        # Don't load config in __init__ to avoid database access before initialization

    def _load_config(self):
        """Load notification configuration from database."""
        session = get_db()
        try:
            configs = session.query(NotificationConfig).all()
            self.config = {c.config_key: c.config_value for c in configs}
        finally:
            session.close()

    def get_thresholds(self) -> Tuple[float, float]:
        """Get premium rate thresholds."""
        high = float(self.config.get('premium_threshold_high', '5.0'))
        low = float(self.config.get('premium_threshold_low', '-5.0'))
        return high, low

    def get_fund_trigger_thresholds(self, fund_code: str, trigger_type: str = 'premium_high') -> Optional[float]:
        """
        Get custom threshold for a specific fund and trigger type.

        Args:
            fund_code: Fund code
            trigger_type: Type of trigger ('premium_high' or 'limit_high')

        Returns:
            Threshold value if custom trigger exists, None otherwise
        """
        session = get_db()
        try:
            trigger = session.query(FundTrigger).filter(
                FundTrigger.fund_code == fund_code,
                FundTrigger.trigger_type == trigger_type,
                FundTrigger.enabled == True
            ).first()

            if trigger and trigger.threshold_value is not None:
                return trigger.threshold_value

            return None

        except Exception as e:
            logger.error(f"Failed to get fund triggers for {fund_code}: {e}")
            return None
        finally:
            session.close()

    def get_debounce_minutes(self) -> int:
        """Get debounce period in minutes."""
        return int(self.config.get('debounce_minutes', '1'))

    def is_within_alert_time_period(self) -> bool:
        """
        Check if current time is within the configured alert time period.

        Returns:
            True if alerts should be sent now, False otherwise
        """
        time_period = self.config.get('alert_time_period', 'all_day')

        if time_period == 'all_day':
            return True

        if time_period == 'trading_hours':
            # Check if current time (Beijing timezone) is within trading hours
            # Trading hours: Trading days only, 9:30-15:00 Beijing time (UTC+8)

            # Get current time in Beijing timezone (UTC+8)
            beijing_tz = timezone(timedelta(hours=8))
            now = datetime.now(beijing_tz)

            # Check if today is a trading day (excludes holidays and weekends)
            try:
                from server import is_trading_day
                today_str = now.strftime('%Y-%m-%d')
                if not is_trading_day(today_str):
                    logger.info(f"Today {today_str} is not a trading day")
                    return False
            except Exception as e:
                logger.warning(f"Failed to check trading day: {e}, allowing alert")

            # Check if time is within 9:30-15:00
            hour = now.hour
            minute = now.minute
            current_minutes = hour * 60 + minute

            start_minutes = 9 * 60 + 30  # 9:30
            end_minutes = 15 * 60       # 15:00

            return start_minutes <= current_minutes < end_minutes

        # Default to allowing alerts
        return True

    def has_limit_change_trigger(self, fund_code: str) -> bool:
        """
        Check if a fund has limit_change trigger enabled.

        Args:
            fund_code: Fund code

        Returns:
            True if limit_change trigger is enabled, False otherwise
        """
        session = get_db()
        try:
            trigger = session.query(FundTrigger).filter(
                FundTrigger.fund_code == fund_code,
                FundTrigger.trigger_type == 'limit_change',
                FundTrigger.enabled == True
            ).first()

            return trigger is not None

        except Exception as e:
            logger.error(f"Failed to check limit_change trigger for {fund_code}: {e}")
            return False
        finally:
            session.close()

    def has_limit_high_trigger(self, fund_code: str) -> bool:
        """
        Check if a fund has limit_high trigger enabled.

        Args:
            fund_code: Fund code

        Returns:
            True if limit_high trigger is enabled, False otherwise
        """
        session = get_db()
        try:
            trigger = session.query(FundTrigger).filter(
                FundTrigger.fund_code == fund_code,
                FundTrigger.trigger_type == 'limit_high',
                FundTrigger.enabled == True
            ).first()

            return trigger is not None

        except Exception as e:
            logger.error(f"Failed to check limit_high trigger for {fund_code}: {e}")
            return False
        finally:
            session.close()

    def has_premium_high_trigger(self, fund_code: str) -> bool:
        """
        Check if a fund has premium_high trigger enabled.

        Args:
            fund_code: Fund code

        Returns:
            True if premium_high trigger is enabled, False otherwise
        """
        session = get_db()
        try:
            trigger = session.query(FundTrigger).filter(
                FundTrigger.fund_code == fund_code,
                FundTrigger.trigger_type == 'premium_high',
                FundTrigger.enabled == True
            ).first()

            return trigger is not None

        except Exception as e:
            logger.error(f"Failed to check premium_high trigger for {fund_code}: {e}")
            return False
        finally:
            session.close()

    def get_active_recipients(self) -> List[str]:
        """Get list of active email recipients."""
        session = get_db()
        try:
            recipients = session.query(EmailRecipient).filter_by(is_active=True).all()
            return [r.email for r in recipients]
        finally:
            session.close()

    async def save_current_state(self, funds: List[Dict]) -> bool:
        """
        Save current fund states to database.

        Args:
            funds: List of fund data dictionaries

        Returns:
            True if saved successfully, False otherwise
        """
        session = get_db()
        try:
            for fund in funds:
                fund_code = fund.get('id') or fund.get('code')
                if not fund_code:
                    continue

                state = FundState(
                    fund_code=fund_code,
                    premium_rate=fund.get('premiumRate', 0),
                    limit_text=fund.get('limitText', ''),
                    market_price=fund.get('marketPrice', 0),
                    valuation=fund.get('valuation', 0)
                )
                session.add(state)

            session.commit()
            logger.info(f"Saved states for {len(funds)} funds")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save fund states: {e}")
            return False
        finally:
            session.close()

    async def get_previous_state(self, fund_code: str, hours_back: int = 1) -> Optional[FundState]:
        """
        Get previous fund state for comparison.

        Args:
            fund_code: Fund code
            hours_back: How many hours back to look

        Returns:
            FundState object or None if not found
        """
        session = get_db()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

            state = session.query(FundState).filter(
                FundState.fund_code == fund_code,
                FundState.timestamp >= cutoff_time
            ).order_by(desc(FundState.timestamp)).first()

            return state

        except Exception as e:
            logger.error(f"Failed to get previous state for {fund_code}: {e}")
            return None
        finally:
            session.close()

    async def detect_premium_threshold_breach(
        self,
        fund_code: str,
        fund_name: str,
        current_rate: float,
        market_price: float,
        nav: float
    ) -> Optional[Dict]:
        """
        Detect if premium rate has breached threshold.

        Args:
            fund_code: Fund code
            fund_name: Fund name
            current_rate: Current premium rate
            market_price: Current market price
            nav: Current NAV

        Returns:
            Dict with alert details if breach detected, None otherwise
        """
        # Check for custom fund trigger first, fall back to global threshold
        custom_threshold = self.get_fund_trigger_thresholds(fund_code)
        high_threshold = custom_threshold if custom_threshold is not None else self.get_thresholds()[0]

        logger.debug(f"Using threshold for {fund_code}: high={high_threshold}")

        # Check if current rate exceeds threshold (only high premium rate)
        if current_rate > high_threshold:
            alert_type = 'premium_high'
        else:
            return None  # No breach

        # Check debounce - don't send if we recently sent same alert
        if await self._should_debounce(fund_code, alert_type):
            logger.info(f"Debouncing {alert_type} alert for {fund_code}")
            return None

        # Get previous state to show change
        prev_state = await self.get_previous_state(fund_code)
        old_rate = prev_state.premium_rate if prev_state else current_rate

        return {
            'fund_code': fund_code,
            'fund_name': fund_name,
            'alert_type': alert_type,
            'old_value': f"{old_rate:.2f}%",
            'new_value': f"{current_rate:.2f}%",
            'market_price': market_price,
            'nav': nav,
            'threshold': high_threshold
        }

    async def detect_premium_low(
        self,
        fund_code: str,
        fund_name: str,
        current_rate: float,
        market_price: float,
        nav: float
    ) -> Optional[Dict]:
        """
        Detect if premium rate has dropped below threshold (good buying opportunity).

        Args:
            fund_code: Fund code
            fund_name: Fund name
            current_rate: Current premium rate
            market_price: Current market price
            nav: Current NAV

        Returns:
            Dict with alert details if rate < threshold, None otherwise
        """
        # Get custom threshold for this fund
        threshold = self.get_fund_trigger_thresholds(fund_code, 'premium_low')
        if threshold is None:
            logger.debug(f"No premium_low trigger configured for {fund_code}")
            return None

        logger.debug(f"Checking premium_low for {fund_code}: current={current_rate}%, threshold={threshold}%")

        # Check if current rate is below threshold (discount opportunity)
        if current_rate < threshold:
            # Check debounce
            if await self._should_debounce(fund_code, 'premium_low'):
                logger.info(f"Debouncing premium_low alert for {fund_code}: recently sent notification")
                return None

            # Get previous state to show change
            prev_state = await self.get_previous_state(fund_code)
            old_rate = prev_state.premium_rate if prev_state else current_rate

            return {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'alert_type': 'premium_low',
                'old_value': f"{old_rate:.2f}%",
                'new_value': f"{current_rate:.2f}%",
                'market_price': market_price,
                'nav': nav,
                'threshold': threshold
            }

        return None

    def has_premium_low_trigger(self, fund_code: str) -> bool:
        """
        Check if a fund has premium_low trigger enabled.

        Args:
            fund_code: Fund code

        Returns:
            True if premium_low trigger is enabled, False otherwise
        """
        session = get_db()
        try:
            trigger = session.query(FundTrigger).filter(
                FundTrigger.fund_code == fund_code,
                FundTrigger.trigger_type == 'premium_low',
                FundTrigger.enabled == True
            ).first()

            return trigger is not None

        except Exception as e:
            logger.error(f"Failed to check premium_low trigger for {fund_code}: {e}")
            return False
        finally:
            session.close()

    async def detect_limit_change(
        self,
        fund_code: str,
        fund_name: str,
        current_limit: str
    ) -> Optional[Dict]:
        """
        Detect if purchase limit has changed.

        Args:
            fund_code: Fund code
            fund_name: Fund name
            current_limit: Current limit text

        Returns:
            Dict with alert details if change detected, None otherwise
        """
        # Get previous state
        prev_state = await self.get_previous_state(fund_code)

        if not prev_state:
            # No previous state, save current but don't alert
            return None

        old_limit = prev_state.limit_text or ''

        # Check if limit has changed
        if old_limit == current_limit:
            return None  # No change

        # Skip notifications for transitions to/from "暂停" (suspended status)
        # We don't want to alert when a fund goes from a limit to suspended or vice versa
        if old_limit == "暂停" or current_limit == "暂停":
            logger.info(f"Skipping limit change notification for {fund_code}: transition to/from suspended status ({old_limit} → {current_limit})")
            return None

        # Check debounce
        if await self._should_debounce(fund_code, 'limit_change'):
            logger.info(f"Debouncing limit_change alert for {fund_code}")
            return None

        return {
            'fund_code': fund_code,
            'fund_name': fund_name,
            'alert_type': 'limit_change',
            'old_value': old_limit,
            'new_value': current_limit
        }

    async def detect_limit_high(
        self,
        fund_code: str,
        fund_name: str,
        current_limit: str
    ) -> Optional[Dict]:
        """
        Detect if purchase limit is higher than threshold (good buying opportunity).

        Args:
            fund_code: Fund code
            fund_name: Fund name
            current_limit: Current limit text

        Returns:
            Dict with alert details if limit > threshold, None otherwise
        """
        # Get previous state
        prev_state = await self.get_previous_state(fund_code)

        # Extract current limit value
        from server import extract_limit_value
        current_limit_value = extract_limit_value(current_limit)

        # Skip if suspended or no limit info
        if current_limit_value <= 0:
            logger.debug(f"Skipping limit_high check for {fund_code}: limit value is {current_limit_value} ({current_limit})")
            return None

        # Get threshold for this fund
        threshold = self.get_fund_trigger_thresholds(fund_code, 'limit_high')
        if threshold is None:
            logger.debug(f"No limit_high trigger configured for {fund_code}")
            return None

        # Check if current limit is higher than threshold
        if current_limit_value > threshold:
            # Check if we should debounce (don't spam if already notified)
            if await self._should_debounce(fund_code, 'limit_high'):
                logger.info(f"Debouncing limit_high alert for {fund_code}: recently sent notification")
                return None

            return {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'alert_type': 'limit_high',
                'old_value': prev_state.limit_text if prev_state else '—',
                'new_value': current_limit,
                'threshold': threshold
            }

        return None

    async def _should_debounce(self, fund_code: str, alert_type: str) -> bool:
        """
        Check if we should debounce (skip) this notification.

        Args:
            fund_code: Fund code
            alert_type: Type of alert

        Returns:
            True if should debounce (skip), False otherwise
        """
        # Reload config to get latest debounce setting
        self._load_config()

        debounce_minutes = self.get_debounce_minutes()
        cutoff_time = datetime.utcnow() - timedelta(minutes=debounce_minutes)

        session = get_db()
        try:
            # Check if we sent a similar alert recently
            recent_alert = session.query(NotificationHistory).filter(
                NotificationHistory.fund_code == fund_code,
                NotificationHistory.alert_type == alert_type,
                NotificationHistory.sent_at >= cutoff_time
            ).first()

            return recent_alert is not None

        except Exception as e:
            logger.error(f"Failed to check debounce for {fund_code}: {e}")
            return False  # On error, don't debounce

        finally:
            session.close()

    async def mark_notification_sent(
        self,
        fund_code: str,
        fund_name: str,
        alert_type: str,
        old_value: str,
        new_value: str,
        recipient_email: str
    ) -> bool:
        """
        Record that a notification was sent.

        Args:
            fund_code: Fund code
            fund_name: Fund name
            alert_type: Type of alert
            old_value: Old value
            new_value: New value
            recipient_email: Recipient email address

        Returns:
            True if recorded successfully, False otherwise
        """
        session = get_db()
        try:
            history = NotificationHistory(
                fund_code=fund_code,
                fund_name=fund_name,
                alert_type=alert_type,
                old_value=old_value,
                new_value=new_value,
                recipient_email=recipient_email
            )
            session.add(history)
            session.commit()

            logger.info(f"Recorded notification: {fund_code} - {alert_type}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to record notification: {e}")
            return False
        finally:
            session.close()

    async def get_notification_history(
        self,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get notification history.

        Args:
            limit: Maximum number of records
            offset: Offset for pagination

        Returns:
            List of notification history dicts
        """
        session = get_db()
        try:
            history = session.query(NotificationHistory).order_by(
                desc(NotificationHistory.sent_at)
            ).limit(limit).offset(offset).all()

            return [
                {
                    'id': h.id,
                    'fund_code': h.fund_code,
                    'fund_name': h.fund_name,
                    'alert_type': h.alert_type,
                    'old_value': h.old_value,
                    'new_value': h.new_value,
                    'sent_at': h.sent_at.isoformat(),
                    'recipient_email': h.recipient_email
                }
                for h in history
            ]

        except Exception as e:
            logger.error(f"Failed to get notification history: {e}")
            return []
        finally:
            session.close()

    async def get_notification_stats(self) -> Dict:
        """
        Get notification statistics.

        Returns:
            Dict with statistics
        """
        session = get_db()
        try:
            # Total sent
            total = session.query(NotificationHistory).count()

            # Today sent
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today = session.query(NotificationHistory).filter(
                NotificationHistory.sent_at >= today_start
            ).count()

            # By type
            by_type = {}
            for h in session.query(NotificationHistory.alert_type).all():
                alert_type = h[0]
                by_type[alert_type] = by_type.get(alert_type, 0) + 1

            return {
                'total_sent': total,
                'today_sent': today,
                'by_type': by_type
            }

        except Exception as e:
            logger.error(f"Failed to get notification stats: {e}")
            return {'total_sent': 0, 'today_sent': 0, 'by_type': {}}
        finally:
            session.close()
