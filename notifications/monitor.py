"""
Background monitor for periodic fund data checks and notifications.
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from .models import get_db, NotificationConfig
from .state_tracker import StateTracker
from .email_service import EmailService

logger = logging.getLogger(__name__)


class NotificationMonitor:
    """Background monitor for checking fund data and sending notifications."""

    def __init__(self):
        self.running = False
        self.task = None
        self.tracker = None  # Will be initialized in initialize()
        self.email_service = None  # Will be initialized in initialize()
        self.last_check_time = None
        self.config = {}

    def _load_config(self):
        """Load monitoring configuration from database."""
        session = get_db()
        try:
            configs = session.query(NotificationConfig).all()
            self.config = {c.config_key: c.config_value for c in configs}
        finally:
            session.close()

    def is_enabled(self) -> bool:
        """Check if monitoring is enabled."""
        self._load_config()
        return self.config.get('smtp_enabled', 'false').lower() == 'true'

    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is enabled (separate from email enabled)."""
        self._load_config()
        return self.config.get('monitoring_enabled', 'true').lower() == 'true'

    def get_check_interval(self) -> int:
        """Get check interval in seconds."""
        self._load_config()
        return int(self.config.get('check_interval_seconds', '180'))

    async def initialize(self):
        """Initialize the monitor (load config, etc)."""
        logger.info("Initializing notification monitor")
        self.tracker = StateTracker()
        self.email_service = EmailService()
        self._load_config()

    async def start_monitoring(self):
        """Start the background monitoring task."""
        if self.running:
            logger.warning("Monitor is already running")
            return

        if not self.is_enabled():
            logger.warning("Cannot start monitoring: email notifications are disabled")
            return False

        self.running = True
        self.task = asyncio.create_task(self._monitoring_loop())
        logger.info("Notification monitoring started")
        return True

    async def stop_monitoring(self):
        """Stop the background monitoring task."""
        if not self.running:
            logger.warning("Monitor is not running")
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.task = None
        logger.info("Notification monitoring stopped")

    def _should_enforce_trading_days(self) -> bool:
        """Check if trading day enforcement should be applied (release mode)."""
        import os
        # Check if running in release/production mode
        # You can set an environment variable or check other indicators
        return os.getenv('ENVIRONMENT', 'development').lower() in ['production', 'release']

    def _is_trading_day(self) -> bool:
        """Check if today is a trading day."""
        try:
            from server import is_trading_day
            from datetime import datetime

            today = datetime.now().strftime('%Y-%m-%d')
            return is_trading_day(today)
        except Exception as e:
            logger.error(f"Failed to check trading day: {e}")
            return True  # Assume trading day on error

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        logger.info("Monitoring loop started")

        while self.running:
            try:
                # Check if monitoring is enabled via config
                if not self.is_monitoring_enabled():
                    logger.info("Monitoring is disabled in config, skipping check")
                    # Sleep for a shorter interval before checking again
                    for _ in range(30):  # Check every 30 seconds
                        if not self.running:
                            break
                        await asyncio.sleep(1)
                    continue

                # Check if we should skip on non-trading days (release mode)
                if self._should_enforce_trading_days():
                    if not self._is_trading_day():
                        logger.info("Today is not a trading day, skipping monitoring check")
                        # Sleep until next trading day check
                        interval = self.get_check_interval()
                        for _ in range(interval):
                            if not self.running:
                                break
                            await asyncio.sleep(1)
                        continue

                await self.check_all_funds()
                self.last_check_time = datetime.utcnow()

            except Exception as e:
                logger.error(f"Error during monitoring check: {e}", exc_info=True)

            # Wait for next interval
            interval = self.get_check_interval()
            logger.info(f"Next check in {interval} seconds")

            # Sleep in small increments to check running status
            for _ in range(interval):
                if not self.running:
                    break
                await asyncio.sleep(1)

        logger.info("Monitoring loop stopped")

    async def check_all_funds(self):
        """
        Check all funds for alerts and send notifications.
        This is called periodically by the monitoring loop.
        """
        logger.info("Checking monitored funds for alerts...")

        # Import here to avoid circular dependency
        from server import get_qdii_funds

        try:
            # Fetch current fund data
            funds = await get_qdii_funds()

            if not funds:
                logger.warning("No fund data available")
                return

            # Get list of monitored funds from database
            session = get_db()
            try:
                from .models import MonitoredFund
                monitored_funds = session.query(MonitoredFund).filter_by(enabled=True).all()
                monitored_codes = {f.fund_code for f in monitored_funds}
            finally:
                session.close()

            if not monitored_codes:
                logger.info("No funds are currently monitored")
                return

            logger.info(f"Monitoring {len(monitored_codes)} funds: {monitored_codes}")

            # Get active recipients
            recipients = self.tracker.get_active_recipients()
            if not recipients:
                logger.warning("No active email recipients configured")
                return

            alerts_sent = 0

            # Filter to only check monitored funds
            monitored_funds_list = [f for f in funds if f.get('id') in monitored_codes]

            # Check each monitored fund for premium rate breaches
            for fund in monitored_funds_list:
                fund_code = fund.get('id') or fund.get('code')
                fund_name = fund.get('name', '')
                premium_rate = fund.get('premiumRate', 0)
                market_price = fund.get('marketPrice', 0)
                nav = fund.get('valuation', 0)  # Note: NAV is stored in valuation field
                limit_text = fund.get('limitText', '')

                # Skip if not LOF fund (no real-time data)
                if market_price == 0:
                    continue

                # Check premium rate threshold
                alert = await self.tracker.detect_premium_threshold_breach(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    current_rate=premium_rate,
                    market_price=market_price,
                    nav=nav
                )

                if alert:
                    # Check if current time is within alert time period
                    if not self.tracker.is_within_alert_time_period():
                        logger.info(f"Skipping premium alert for {fund_code}: outside configured time period")
                        continue

                    success = await self.email_service.send_premium_alert(
                        fund_code=alert['fund_code'],
                        fund_name=alert['fund_name'],
                        old_rate=float(alert['old_value'].replace('%', '')),
                        new_rate=float(alert['new_value'].replace('%', '')),
                        market_price=alert['market_price'],
                        nav=alert['nav'],
                        limit_text=limit_text,
                        threshold=alert.get('threshold'),
                        recipients=recipients
                    )

                    if success:
                        await self.tracker.mark_notification_sent(
                            fund_code=alert['fund_code'],
                            fund_name=alert['fund_name'],
                            alert_type=alert['alert_type'],
                            old_value=alert['old_value'],
                            new_value=alert['new_value'],
                            recipient_email=', '.join(recipients)
                        )
                        alerts_sent += 1
                        logger.info(f"Premium alert sent for {fund_code}")

            # Check each monitored fund for limit changes
            # DISABLED: Limit change email notifications are disabled per user request
            # for fund in monitored_funds_list:
            #     fund_code = fund.get('id') or fund.get('code')
            #     fund_name = fund.get('name', '')
            #     limit_text = fund.get('limitText', '')
            #
            #     # Only check limit change if the fund has limit_change trigger enabled
            #     if not self.tracker.has_limit_change_trigger(fund_code):
            #         logger.debug(f"Skipping limit change check for {fund_code}: no trigger enabled")
            #         continue
            #
            #     # Check limit change
            #     alert = await self.tracker.detect_limit_change(
            #         fund_code=fund_code,
            #         fund_name=fund_name,
            #         current_limit=limit_text
            #     )
            #
            #     if alert:
            #         # Check if current time is within alert time period
            #         if not self.tracker.is_within_alert_time_period():
            #             logger.info(f"Skipping limit change alert for {fund_code}: outside configured time period")
            #             continue
            #
            #         success = await self.email_service.send_limit_change_alert(
            #             fund_code=alert['fund_code'],
            #             fund_name=alert['fund_name'],
            #             old_limit=alert['old_value'],
            #             new_limit=alert['new_value'],
            #             recipients=recipients
            #         )
            #
            #         if success:
            #             await self.tracker.mark_notification_sent(
            #                 fund_code=alert['fund_code'],
            #                 fund_name=alert['fund_name'],
            #                 alert_type=alert['alert_type'],
            #                 old_value=alert['old_value'],
            #                 new_value=alert['new_value'],
            #                 recipient_email=', '.join(recipients)
            #             )
            #             alerts_sent += 1
            #             logger.info(f"Limit change alert sent for {fund_code}")

            # Check each monitored fund for limit_high (purchase limit higher than threshold)
            for fund in monitored_funds_list:
                fund_code = fund.get('id') or fund.get('code')
                fund_name = fund.get('name', '')
                limit_text = fund.get('limitText', '')

                # Only check limit_high if the fund has limit_high trigger enabled
                if not self.tracker.has_limit_high_trigger(fund_code):
                    logger.debug(f"Skipping limit_high check for {fund_code}: no trigger enabled")
                    continue

                # Check if limit is higher than threshold
                alert = await self.tracker.detect_limit_high(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    current_limit=limit_text
                )

                if alert:
                    # Check if current time is within alert time period
                    if not self.tracker.is_within_alert_time_period():
                        logger.info(f"Skipping limit_high alert for {fund_code}: outside configured time period")
                        continue

                    success = await self.email_service.send_limit_high_alert(
                        fund_code=alert['fund_code'],
                        fund_name=alert['fund_name'],
                        old_limit=alert['old_value'],
                        new_limit=alert['new_value'],
                        threshold=alert['threshold'],
                        recipients=recipients
                    )

                    if success:
                        await self.tracker.mark_notification_sent(
                            fund_code=alert['fund_code'],
                            fund_name=alert['fund_name'],
                            alert_type=alert['alert_type'],
                            old_value=alert['old_value'],
                            new_value=alert['new_value'],
                            recipient_email=', '.join(recipients)
                        )
                        alerts_sent += 1
                        logger.info(f"Limit_high alert sent for {fund_code}")

            # Check each monitored fund for premium_low (premium below threshold - good buying opportunity)
            for fund in monitored_funds_list:
                fund_code = fund.get('id') or fund.get('code')
                fund_name = fund.get('name', '')
                premium_rate = fund.get('premiumRate', 0)
                market_price = fund.get('marketPrice', 0)
                nav = fund.get('valuation', 0)
                limit_text = fund.get('limitText', '')

                # Only check premium_low if the fund has premium_low trigger enabled
                if not self.tracker.has_premium_low_trigger(fund_code):
                    logger.debug(f"Skipping premium_low check for {fund_code}: no trigger enabled")
                    continue

                # Check if premium is below threshold
                alert = await self.tracker.detect_premium_low(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    current_rate=premium_rate,
                    market_price=market_price,
                    nav=nav
                )

                if alert:
                    # Check if current time is within alert time period
                    if not self.tracker.is_within_alert_time_period():
                        logger.info(f"Skipping premium_low alert for {fund_code}: outside configured time period")
                        continue

                    success = await self.email_service.send_premium_low_alert(
                        fund_code=alert['fund_code'],
                        fund_name=alert['fund_name'],
                        old_rate=float(alert['old_value'].replace('%', '')),
                        new_rate=float(alert['new_value'].replace('%', '')),
                        market_price=alert['market_price'],
                        nav=alert['nav'],
                        limit_text=limit_text,
                        threshold=alert['threshold'],
                        recipients=recipients
                    )

                    if success:
                        await self.tracker.mark_notification_sent(
                            fund_code=alert['fund_code'],
                            fund_name=alert['fund_name'],
                            alert_type=alert['alert_type'],
                            old_value=alert['old_value'],
                            new_value=alert['new_value'],
                            recipient_email=', '.join(recipients)
                        )
                        alerts_sent += 1
                        logger.info(f"Premium_low alert sent for {fund_code}")

            # Save current states for monitored funds only
            await self.tracker.save_current_state(monitored_funds_list)

            logger.info(f"Check completed: {alerts_sent} alerts sent")

        except Exception as e:
            logger.error(f"Failed to check funds: {e}", exc_info=True)

    def get_status(self) -> Dict:
        """
        Get current monitoring status.

        Returns:
            Dict with status information
        """
        return {
            'is_running': self.running,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'check_interval_seconds': self.get_check_interval(),
            'enabled': self.is_enabled()
        }


# Global monitor instance
monitor = NotificationMonitor()
