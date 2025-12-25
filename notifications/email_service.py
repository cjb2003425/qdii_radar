"""
Email service for sending notification emails.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime
from typing import List
from .models import get_db, NotificationConfig

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications."""

    def __init__(self):
        self.config = {}
        # Don't load config in __init__ to avoid database access before initialization

    def _load_config(self):
        """Load email configuration from database."""
        session = get_db()
        try:
            configs = session.query(NotificationConfig).all()
            self.config = {c.config_key: c.config_value for c in configs}
        finally:
            session.close()

    def is_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return self.config.get('smtp_enabled', 'false').lower() == 'true'

    def get_smtp_config(self):
        """Get SMTP configuration."""
        return {
            'host': self.config.get('smtp_host', 'smtp.gmail.com'),
            'port': int(self.config.get('smtp_port', '587')),
            'username': self.config.get('smtp_username', ''),
            'password': self.config.get('smtp_password', ''),
            'from_email': self.config.get('smtp_from_email', ''),
        }

    async def send_premium_alert(
        self,
        fund_code: str,
        fund_name: str,
        old_rate: float,
        new_rate: float,
        market_price: float,
        nav: float,
        recipients: List[str]
    ) -> bool:
        """
        Send premium rate threshold breach alert.

        Args:
            fund_code: Fund code
            fund_name: Fund name
            old_rate: Previous premium rate
            new_rate: Current premium rate
            market_price: Current market price
            nav: Current NAV
            recipients: List of recipient email addresses

        Returns:
            True if email sent successfully, False otherwise
        """
        if not recipients:
            logger.warning("No recipients provided for premium alert")
            return False

        alert_type = "高溢价" if new_rate > 0 else "高折价"
        threshold = self.config.get('premium_threshold_high', '5.0') if new_rate > 0 else self.config.get('premium_threshold_low', '-5.0')

        subject = f"[QDII Radar] {alert_type}警报: {fund_name} ({fund_code})"

        # HTML body
        html_body = f"""
        <html>
        <body>
            <h2>{alert_type}警报</h2>
            <p><strong>基金名称:</strong> {fund_name}</p>
            <p><strong>基金代码:</strong> {fund_code}</p>
            <p><strong>警报类型:</strong> {alert_type}</p>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><td>之前溢价率:</td><td>{old_rate:.2f}%</td></tr>
                <tr><td>当前溢价率:</td><td><strong>{new_rate:.2f}%</strong></td></tr>
                <tr><td>阈值:</td><td>{threshold}%</td></tr>
                <tr><td>场内价格:</td><td>{market_price:.4f}</td></tr>
                <tr><td>净值:</td><td>{nav:.4f}</td></tr>
            </table>
            <p><em>时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
            <hr>
            <p><small>这是一封自动发送的邮件，请勿回复。</small></p>
        </body>
        </html>
        """

        # Plain text body
        text_body = f"""
{alert_type}警报

基金名称: {fund_name}
基金代码: {fund_code}
警报类型: {alert_type}

之前溢价率: {old_rate:.2f}%
当前溢价率: {new_rate:.2f}%
阈值: {threshold}%
场内价格: {market_price:.4f}
净值: {nav:.4f}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
这是一封自动发送的邮件，请勿回复。
        """.strip()

        return await self._send_email(subject, text_body, html_body, recipients)

    async def send_limit_change_alert(
        self,
        fund_code: str,
        fund_name: str,
        old_limit: str,
        new_limit: str,
        recipients: List[str]
    ) -> bool:
        """
        Send purchase limit change alert.

        Args:
            fund_code: Fund code
            fund_name: Fund name
            old_limit: Previous limit text
            new_limit: Current limit text
            recipients: List of recipient email addresses

        Returns:
            True if email sent successfully, False otherwise
        """
        if not recipients:
            logger.warning("No recipients provided for limit change alert")
            return False

        subject = f"[QDII Radar] 申购限制变更: {fund_name} ({fund_code})"

        # HTML body
        html_body = f"""
        <html>
        <body>
            <h2>申购限制变更通知</h2>
            <p><strong>基金名称:</strong> {fund_name}</p>
            <p><strong>基金代码:</strong> {fund_code}</p>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><td>之前状态:</td><td>{old_limit}</td></tr>
                <tr><td>当前状态:</td><td><strong>{new_limit}</strong></td></tr>
            </table>
            <p><em>时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
            <hr>
            <p><small>这是一封自动发送的邮件，请勿回复。</small></p>
        </body>
        </html>
        """

        # Plain text body
        text_body = f"""
申购限制变更通知

基金名称: {fund_name}
基金代码: {fund_code}

之前状态: {old_limit}
当前状态: {new_limit}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
这是一封自动发送的邮件，请勿回复。
        """.strip()

        return await self._send_email(subject, text_body, html_body, recipients)

    async def send_test_email(self, recipient: str) -> bool:
        """
        Send a test email to verify SMTP configuration.

        Args:
            recipient: Recipient email address

        Returns:
            True if email sent successfully, False otherwise
        """
        subject = "[QDII Radar] 测试邮件"

        html_body = f"""
        <html>
        <body>
            <h2>测试邮件</h2>
            <p>这是一封测试邮件，用于验证您的SMTP配置是否正确。</p>
            <p>如果您收到这封邮件，说明邮件通知功能已经配置成功！</p>
            <p><em>时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
            <hr>
            <p><small>QDII Fund Radar</small></p>
        </body>
        </html>
        """

        text_body = f"""
测试邮件

这是一封测试邮件，用于验证您的SMTP配置是否正确。
如果您收到这封邮件，说明邮件通知功能已经配置成功！

时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
QDII Fund Radar
        """.strip()

        return await self._send_email(subject, text_body, html_body, [recipient])

    async def _send_email(
        self,
        subject: str,
        text_body: str,
        html_body: str,
        recipients: List[str]
    ) -> bool:
        """
        Send email using SMTP.

        Args:
            subject: Email subject
            text_body: Plain text body
            html_body: HTML body
            recipients: List of recipient email addresses

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.warning("Email notifications are disabled")
            return False

        try:
            config = self.get_smtp_config()

            if not config['username'] or not config['password']:
                logger.error("SMTP username or password not configured")
                return False

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr(('QDII Fund Radar', config['from_email'] or config['username']))
            msg['To'] = ', '.join(recipients)

            # Attach both plain text and HTML versions
            part1 = MIMEText(text_body, 'plain', 'utf-8')
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(config['host'], config['port']) as server:
                server.starttls()  # Secure the connection
                server.login(config['username'], config['password'])
                server.send_message(msg)

            logger.info(f"Email sent successfully to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def verify_smtp_config(self) -> dict:
        """
        Verify SMTP configuration by attempting to connect.

        Returns:
            Dict with success status and error message if failed
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Email notifications are disabled'}

        try:
            config = self.get_smtp_config()

            if not config['username'] or not config['password']:
                return {'success': False, 'error': 'SMTP username or password not configured'}

            with smtplib.SMTP(config['host'], config['port'], timeout=10) as server:
                server.starttls()
                server.login(config['username'], config['password'])

            return {'success': True, 'message': 'SMTP configuration is valid'}

        except Exception as e:
            logger.error(f"SMTP verification failed: {e}")
            return {'success': False, 'error': str(e)}
