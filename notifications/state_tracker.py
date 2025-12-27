"""
State tracker for detecting changes in fund data.
"""
import logging
from datetime import datetime, timedelta
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

    def get_fund_trigger_thresholds(self, fund_code: str) -> Optional[Tuple[float, float]]:
        """
        Get custom premium rate thresholds for a specific fund.

        Args:
            fund_code: Fund code

        Returns:
            Tuple of (high_threshold, low_threshold) if custom triggers exist, None otherwise
        """
        session = get_db()
        try:
            triggers = session.query(FundTrigger).filter(
                FundTrigger.fund_code == fund_code,
                FundTrigger.trigger_type.in_(['premium_high', 'premium_low']),
                FundTrigger.enabled == True
            ).all()

            if not triggers:
                return None

            # Extract thresholds
            high_threshold = None
            low_threshold = None

            for trigger in triggers:
                if trigger.trigger_type == 'premium_high' and trigger.threshold_value is not None:
                    high_threshold = trigger.threshold_value
                elif trigger.trigger_type == 'premium_low' and trigger.threshold_value is not None:
                    low_threshold = trigger.threshold_value

            # If no valid thresholds found, return None
            if high_threshold is None and low_threshold is None:
                return None

            # Use defaults for missing thresholds
            if high_threshold is None:
                high_threshold = float(self.config.get('premium_threshold_high', '5.0'))
            if low_threshold is None:
                low_threshold = float(self.config.get('premium_threshold_low', '-5.0'))

            return (high_threshold, low_threshold)

        except Exception as e:
            logger.error(f"Failed to get fund triggers for {fund_code}: {e}")
            return None
        finally:
            session.close()

    def get_debounce_minutes(self) -> int:
        """Get debounce period in minutes."""
        return int(self.config.get('debounce_minutes', '60'))

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
        # Check for custom fund triggers first, fall back to global thresholds
        custom_thresholds = self.get_fund_trigger_thresholds(fund_code)
        if custom_thresholds:
            high_threshold, low_threshold = custom_thresholds
            logger.debug(f"Using custom thresholds for {fund_code}: high={high_threshold}, low={low_threshold}")
        else:
            high_threshold, low_threshold = self.get_thresholds()
            logger.debug(f"Using global thresholds for {fund_code}: high={high_threshold}, low={low_threshold}")

        # Check if current rate exceeds thresholds
        if current_rate > high_threshold:
            alert_type = 'premium_high'
        elif current_rate < low_threshold:
            alert_type = 'premium_low'
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
            'threshold': high_threshold if current_rate > 0 else low_threshold
        }

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
