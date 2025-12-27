"""
Email service for sending notification emails.
Supports both SMTP and Amazon SES.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from .models import get_db, NotificationConfig

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications via SMTP or Amazon SES."""

    def __init__(self):
        self.config = {}
        self.ses_client = None
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

    def use_ses(self) -> bool:
        """Check if using Amazon SES instead of SMTP."""
        return self.config.get('email_provider', 'smtp').lower() == 'ses'

    def get_smtp_config(self):
        """Get SMTP configuration."""
        return {
            'host': self.config.get('smtp_host', 'smtp.gmail.com'),
            'port': int(self.config.get('smtp_port', '587')),
            'username': self.config.get('smtp_username', ''),
            'password': self.config.get('smtp_password', ''),
            'from_email': self.config.get('smtp_from_email', ''),
        }

    def get_ses_config(self):
        """Get Amazon SES configuration."""
        return {
            'region': self.config.get('aws_region', 'us-east-1'),
            'access_key': self.config.get('aws_access_key_id', ''),
            'secret_key': self.config.get('aws_secret_access_key', ''),
            'from_email': self.config.get('smtp_from_email', ''),
        }

    def _get_ses_client(self):
        """Get or create SES client."""
        if self.ses_client is None:
            config = self.get_ses_config()
            if config['access_key'] and config['secret_key']:
                self.ses_client = boto3.client(
                    'ses',
                    region_name=config['region'],
                    aws_access_key_id=config['access_key'],
                    aws_secret_access_key=config['secret_key']
                )
            else:
                # Use default credential chain (env vars, ~/.aws/credentials, IAM role)
                self.ses_client = boto3.client('ses', region_name=config['region'])
        return self.ses_client

    async def send_premium_alert(
        self,
        fund_code: str,
        fund_name: str,
        old_rate: float,
        new_rate: float,
        market_price: float,
        nav: float,
        limit_text: str = "",
        recipients: List[str] = None
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
            limit_text: Purchase limit text (e.g., "限10万", "暂停", "不限")
            recipients: List of recipient email addresses

        Returns:
            True if email sent successfully, False otherwise
        """
        # Load config first
        self._load_config()

        if not recipients:
            logger.warning("No recipients provided for premium alert")
            return False

        alert_type = "高溢价" if new_rate > 0 else "高折价"
        threshold = self.config.get('premium_threshold_high', '5.0') if new_rate > 0 else self.config.get('premium_threshold_low', '-5.0')

        # Color scheme based on alert type (using neutral gray)
        if new_rate > 0:
            alert_color = "#4b5563"  # Medium gray for high premium
            alert_bg = "#f3f4f6"
            icon_emoji = "📈"
        else:
            alert_color = "#4b5563"  # Medium gray for high discount
            alert_bg = "#f3f4f6"
            icon_emoji = "📉"

        # Determine purchase limit styling (gray tones)
        limit_badge_color = "#6b7280"  # Default gray
        limit_badge_bg = "#f3f4f6"
        if "暂停" in limit_text:
            limit_badge_color = "#6b7280"  # Gray for suspended
            limit_badge_bg = "#f3f4f6"
        elif "不限" in limit_text:
            limit_badge_color = "#6b7280"  # Gray for unlimited
            limit_badge_bg = "#f3f4f6"
        elif "限" in limit_text:
            limit_badge_color = "#6b7280"  # Gray for limited
            limit_badge_bg = "#f3f4f6"

        subject = f"[QDII Radar] {alert_type}警报: {fund_name} ({fund_code})"

        # HTML body with modern design
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    background-color: #f9fafb;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, {alert_color} 0%, {alert_color}dd 100%);
                    color: white;
                    padding: 32px;
                    text-align: center;
                }}
                .header-icon {{
                    font-size: 48px;
                    margin-bottom: 12px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .header-subtitle {{
                    margin-top: 8px;
                    opacity: 0.95;
                    font-size: 14px;
                }}
                .content {{
                    padding: 32px;
                }}
                .alert-badge {{
                    display: inline-block;
                    background-color: {alert_bg};
                    color: {alert_color};
                    padding: 6px 16px;
                    border-radius: 20px;
                    font-weight: 600;
                    font-size: 14px;
                    margin-bottom: 24px;
                    border: 2px solid {alert_color}33;
                }}
                .fund-info {{
                    background-color: #f8fafc;
                    border-left: 4px solid {alert_color};
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 24px;
                }}
                .fund-info h3 {{
                    margin: 0 0 8px 0;
                    font-size: 20px;
                    color: #111827;
                }}
                .fund-code {{
                    color: #6b7280;
                    font-size: 14px;
                    font-weight: 500;
                    letter-spacing: 0.5px;
                }}
                .data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 24px 0;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
                }}
                .data-table th {{
                    background-color: #f3f4f6;
                    padding: 14px 16px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 600;
                    color: #4b5563;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .data-table td {{
                    padding: 14px 16px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 15px;
                }}
                .data-table tr:hover {{
                    background-color: #f9fafb;
                }}
                .data-table .highlight {{
                    color: {alert_color};
                    font-weight: 700;
                    font-size: 18px;
                }}
                .data-table .label {{
                    font-weight: 500;
                    color: #374151;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 24px;
                    text-align: center;
                    border-top: 1px solid #e5e7eb;
                }}
                .footer-text {{
                    color: #6b7280;
                    font-size: 13px;
                    margin: 0;
                }}
                .timestamp {{
                    color: #9ca3af;
                    font-size: 12px;
                    margin-top: 16px;
                }}
                .change-indicator {{
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                .change-up {{
                    background-color: #f3f4f6;
                    color: #6b7280;
                }}
                .change-down {{
                    background-color: #f3f4f6;
                    color: #6b7280;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-icon">{icon_emoji}</div>
                    <h1>QDII Fund Radar</h1>
                    <div class="header-subtitle">智能监控 · 实时预警</div>
                </div>

                <div class="content">
                    <div class="alert-badge">⚠️ {alert_type}警报</div>

                    <div class="fund-info">
                        <h3>{fund_name}</h3>
                        <div class="fund-code">基金代码: {fund_code}</div>
                    </div>

                    <table class="data-table">
                        <tr>
                            <td class="label">溢价率变化</td>
                            <td>
                                <span class="change-indicator {'change-up' if new_rate > old_rate else 'change-down'}">
                                    {old_rate:.2f}% → {new_rate:.2f}%
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td class="label">触发阈值</td>
                            <td>{threshold}%</td>
                        </tr>
                        <tr>
                            <td class="label">场内价格</td>
                            <td class="highlight">{market_price:.4f}</td>
                        </tr>
                        <tr>
                            <td class="label">净值 (NAV)</td>
                            <td class="highlight">{nav:.4f}</td>
                        </tr>
                        {f'''                        <tr>
                            <td class="label">申购限制</td>
                            <td>
                                <span style="display: inline-block; padding: 4px 12px; background-color: {limit_badge_bg}; color: {limit_badge_color}; border-radius: 6px; font-weight: 600; font-size: 13px;">
                                    {limit_text}
                                </span>
                            </td>
                        </tr>''' if limit_text else ''}
                    </table>

                    <div class="timestamp">📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</div>
                </div>

                <div class="footer">
                    <p class="footer-text">
                        这是由 QDII Fund Radar 自动发送的监控邮件<br>
                        请勿直接回复此邮件
                    </p>
                </div>
            </div>
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
{f'申购限制: {limit_text}' if limit_text else ''}

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
        # Load config first
        self._load_config()

        if not recipients:
            logger.warning("No recipients provided for limit change alert")
            return False

        # Determine change type for styling
        is_opening = "暂停" in old_limit and "暂停" not in new_limit
        is_closing = "暂停" not in old_limit and "暂停" in new_limit
        is_limit_change = not is_opening and not is_closing

        # All gray color scheme
        alert_color = "#4b5563"  # Medium gray
        alert_bg = "#f3f4f6"

        if is_opening:
            icon_emoji = "🔓"
            change_badge = "恢复申购"
        elif is_closing:
            icon_emoji = "🔒"
            change_badge = "暂停申购"
        else:
            icon_emoji = "🔄"
            change_badge = "限额调整"

        subject = f"[QDII Radar] 申购限制变更: {fund_name} ({fund_code})"

        # HTML body with modern design
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    background-color: #f9fafb;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, {alert_color} 0%, {alert_color}dd 100%);
                    color: white;
                    padding: 32px;
                    text-align: center;
                }}
                .header-icon {{
                    font-size: 48px;
                    margin-bottom: 12px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .header-subtitle {{
                    margin-top: 8px;
                    opacity: 0.95;
                    font-size: 14px;
                }}
                .content {{
                    padding: 32px;
                }}
                .alert-badge {{
                    display: inline-block;
                    background-color: {alert_bg};
                    color: {alert_color};
                    padding: 6px 16px;
                    border-radius: 20px;
                    font-weight: 600;
                    font-size: 14px;
                    margin-bottom: 24px;
                    border: 2px solid {alert_color}33;
                }}
                .fund-info {{
                    background-color: #f8fafc;
                    border-left: 4px solid {alert_color};
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 24px;
                }}
                .fund-info h3 {{
                    margin: 0 0 8px 0;
                    font-size: 20px;
                    color: #111827;
                }}
                .fund-code {{
                    color: #6b7280;
                    font-size: 14px;
                    font-weight: 500;
                    letter-spacing: 0.5px;
                }}
                .change-comparison {{
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    margin: 24px 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                    border-radius: 12px;
                }}
                .change-box {{
                    flex: 1;
                    text-align: center;
                    padding: 20px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
                }}
                .change-label {{
                    font-size: 12px;
                    font-weight: 600;
                    color: #6b7280;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 8px;
                }}
                .change-value {{
                    font-size: 24px;
                    font-weight: 700;
                    color: #111827;
                }}
                .change-value.new {{
                    color: {alert_color};
                }}
                .change-arrow {{
                    font-size: 32px;
                    color: #9ca3af;
                }}
                .status-indicator {{
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 16px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    margin-top: 16px;
                }}
                .status-opening {{
                    background-color: #f3f4f6;
                    color: #6b7280;
                }}
                .status-closing {{
                    background-color: #f3f4f6;
                    color: #6b7280;
                }}
                .status-change {{
                    background-color: #f3f4f6;
                    color: #6b7280;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 24px;
                    text-align: center;
                    border-top: 1px solid #e5e7eb;
                }}
                .footer-text {{
                    color: #6b7280;
                    font-size: 13px;
                    margin: 0;
                }}
                .timestamp {{
                    color: #9ca3af;
                    font-size: 12px;
                    margin-top: 16px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-icon">{icon_emoji}</div>
                    <h1>QDII Fund Radar</h1>
                    <div class="header-subtitle">申购限制变更通知</div>
                </div>

                <div class="content">
                    <div class="alert-badge">⚠️ {change_badge}</div>

                    <div class="fund-info">
                        <h3>{fund_name}</h3>
                        <div class="fund-code">基金代码: {fund_code}</div>
                    </div>

                    <div class="change-comparison">
                        <div class="change-box">
                            <div class="change-label">变更前</div>
                            <div class="change-value">{old_limit}</div>
                        </div>
                        <div class="change-arrow">→</div>
                        <div class="change-box">
                            <div class="change-label">变更后</div>
                            <div class="change-value new">{new_limit}</div>
                        </div>
                    </div>

                    <div class="timestamp">📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</div>
                </div>

                <div class="footer">
                    <p class="footer-text">
                        这是由 QDII Fund Radar 自动发送的监控邮件<br>
                        请勿直接回复此邮件
                    </p>
                </div>
            </div>
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
        # Load config first
        self._load_config()

        if not self.is_enabled():
            logger.warning("Email notifications are disabled")
            return False

        subject = "[QDII Radar] 测试邮件"

        # Beautiful test email template
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #059669 0%, #047857 100%);
                    color: white;
                    padding: 48px 32px;
                    text-align: center;
                }}
                .success-icon {{
                    width: 80px;
                    height: 80px;
                    background: white;
                    border-radius: 50%;
                    margin: 0 auto 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 48px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 32px;
                    font-weight: 700;
                }}
                .header-subtitle {{
                    margin-top: 12px;
                    opacity: 0.95;
                    font-size: 16px;
                }}
                .content {{
                    padding: 40px 32px;
                }}
                .success-card {{
                    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
                    border-left: 4px solid #059669;
                    padding: 24px;
                    border-radius: 12px;
                    margin-bottom: 32px;
                    text-align: center;
                }}
                .success-card h2 {{
                    margin: 0 0 8px 0;
                    font-size: 24px;
                    color: #065f46;
                }}
                .success-card p {{
                    margin: 0;
                    color: #047857;
                    font-size: 16px;
                }}
                .feature-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 16px;
                    margin: 32px 0;
                }}
                .feature-item {{
                    background: #f9fafb;
                    padding: 20px;
                    border-radius: 12px;
                    text-align: center;
                }}
                .feature-icon {{
                    font-size: 32px;
                    margin-bottom: 12px;
                }}
                .feature-title {{
                    font-weight: 600;
                    color: #111827;
                    margin-bottom: 4px;
                    font-size: 15px;
                }}
                .feature-desc {{
                    color: #6b7280;
                    font-size: 13px;
                }}
                .divider {{
                    height: 1px;
                    background: linear-gradient(90deg, transparent, #e5e7eb, transparent);
                    margin: 32px 0;
                }}
                .info-section {{
                    background: #f8fafc;
                    padding: 24px;
                    border-radius: 12px;
                    margin-bottom: 24px;
                }}
                .info-section h3 {{
                    margin: 0 0 16px 0;
                    font-size: 18px;
                    color: #111827;
                }}
                .info-list {{
                    margin: 0;
                    padding-left: 20px;
                    color: #4b5563;
                }}
                .info-list li {{
                    margin-bottom: 8px;
                }}
                .footer {{
                    background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
                    padding: 32px;
                    text-align: center;
                    border-top: 1px solid #e5e7eb;
                }}
                .footer-text {{
                    color: #6b7280;
                    font-size: 14px;
                    margin: 0 0 8px 0;
                }}
                .footer-small {{
                    color: #9ca3af;
                    font-size: 12px;
                    margin: 0;
                }}
                .timestamp {{
                    color: #9ca3af;
                    font-size: 12px;
                    margin-top: 24px;
                    padding-top: 24px;
                    border-top: 1px solid #e5e7eb;
                }}
                .brand {{
                    font-weight: 700;
                    color: #059669;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="success-icon">✓</div>
                    <h1>QDII Fund Radar</h1>
                    <div class="header-subtitle">邮件通知系统测试成功</div>
                </div>

                <div class="content">
                    <div class="success-card">
                        <h2>🎉 配置成功！</h2>
                        <p>您的邮件通知系统已正确配置并运行</p>
                    </div>

                    <div class="info-section">
                        <h3>✨ 系统功能</h3>
                        <ul class="info-list">
                            <li><strong>溢价率监控</strong> - 实时监控基金溢价率变化</li>
                            <li><strong>智能预警</strong> - 超过阈值自动发送警报</li>
                            <li><strong>申购跟踪</strong> - 限制变更即时通知</li>
                            <li><strong>多端通知</strong> - 支持多个收件人同时接收</li>
                        </ul>
                    </div>

                    <div class="feature-grid">
                        <div class="feature-item">
                            <div class="feature-icon">📊</div>
                            <div class="feature-title">实时数据</div>
                            <div class="feature-desc">每5分钟自动检查</div>
                        </div>
                        <div class="feature-item">
                            <div class="feature-icon">🔔</div>
                            <div class="feature-title">即时推送</div>
                            <div class="feature-desc">触发后立即发送</div>
                        </div>
                        <div class="feature-item">
                            <div class="feature-icon">🎯</div>
                            <div class="feature-title">精准监控</div>
                            <div class="feature-desc">自定义阈值设置</div>
                        </div>
                        <div class="feature-item">
                            <div class="feature-icon">📧</div>
                            <div class="feature-title">邮件通知</div>
                            <div class="feature-desc">Amazon SES 发送</div>
                        </div>
                    </div>

                    <div class="divider"></div>

                    <div style="text-align: center; color: #6b7280; font-size: 14px;">
                        现在您可以开始使用基金监控功能了！<br>
                        系统将自动检测并发送警报通知。
                    </div>

                    <div class="timestamp">
                        📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
                    </div>
                </div>

                <div class="footer">
                    <p class="footer-text"><span class="brand">QDII Fund Radar</span> - 智能基金监控系统</p>
                    <p class="footer-small">这是一封测试邮件，请勿直接回复</p>
                </div>
            </div>
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
        Send email using SMTP or Amazon SES.

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

        # Use SES if configured
        if self.use_ses():
            return await self._send_email_ses(subject, text_body, html_body, recipients)
        else:
            return await self._send_email_smtp(subject, text_body, html_body, recipients)

    async def _send_email_smtp(
        self,
        subject: str,
        text_body: str,
        html_body: str,
        recipients: List[str]
    ) -> bool:
        """Send email using SMTP."""
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

            logger.info(f"Email sent successfully via SMTP to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False

    async def _send_email_ses(
        self,
        subject: str,
        text_body: str,
        html_body: str,
        recipients: List[str]
    ) -> bool:
        """Send email using Amazon SES."""
        try:
            client = self._get_ses_client()
            config = self.get_ses_config()

            if not config['from_email']:
                logger.error("SES from email not configured")
                return False

            # Build email message for SES
            # SES requires a specific format with the charset specified
            CHARSET = "UTF-8"

            try:
                # Send email using SES
                response = client.send_email(
                    Source=config['from_email'],
                    Destination={'ToAddresses': recipients},
                    Message={
                        'Subject': {'Data': subject, 'Charset': CHARSET},
                        'Body': {
                            'Text': {'Data': text_body, 'Charset': CHARSET},
                            'Html': {'Data': html_body, 'Charset': CHARSET}
                        }
                    }
                )

                message_id = response['MessageId']
                logger.info(f"Email sent successfully via SES to {recipients}. Message ID: {message_id}")
                return True

            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_msg = e.response['Error']['Message']
                logger.error(f"SES client error: {error_code} - {error_msg}")

                # Provide helpful error messages
                if error_code == 'MessageRejected':
                    logger.error("Email rejected by SES. Ensure recipient email is verified.")
                elif error_code == 'InvalidParameterValue':
                    logger.error("Invalid parameter. Ensure from email is verified in SES.")
                elif error_code == 'EmailDisabled':
                    logger.error("Email account is disabled in SES.")

                return False

        except NoCredentialsError:
            logger.error("AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, or configure in settings.")
            return False
        except PartialCredentialsError:
            logger.error("Incomplete AWS credentials. Both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required.")
            return False
        except Exception as e:
            logger.error(f"Failed to send email via SES: {e}")
            return False

    async def verify_smtp_config(self) -> dict:
        """
        Verify email configuration (SMTP or SES) by attempting to connect/send.

        Returns:
            Dict with success status and error message if failed
        """
        if not self.is_enabled():
            return {'success': False, 'error': 'Email notifications are disabled'}

        if self.use_ses():
            return await self._verify_ses_config()
        else:
            return await self._verify_smtp_config()

    async def _verify_smtp_config(self) -> dict:
        """Verify SMTP configuration."""
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

    async def _verify_ses_config(self) -> dict:
        """Verify Amazon SES configuration."""
        try:
            config = self.get_ses_config()

            if not config['from_email']:
                return {'success': False, 'error': 'SES from email not configured'}

            # Try to get SES send quota to verify credentials
            client = self._get_ses_client()
            client.get_send_quota()

            return {'success': True, 'message': 'SES configuration is valid'}

        except NoCredentialsError:
            return {'success': False, 'error': 'AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.'}
        except PartialCredentialsError:
            return {'success': False, 'error': 'Incomplete AWS credentials.'}
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidClientTokenId':
                return {'success': False, 'error': 'Invalid AWS access key ID.'}
            elif error_code == 'SignatureDoesNotMatch':
                return {'success': False, 'error': 'Invalid AWS secret access key.'}
            elif error_code == 'AccessDenied':
                return {'success': False, 'error': 'Access denied. Check IAM permissions for ses:SendEmail.'}
            else:
                return {'success': False, 'error': f"AWS error: {error_code} - {e.response['Error']['Message']}"}
        except Exception as e:
            logger.error(f"SES verification failed: {e}")
            return {'success': False, 'error': str(e)}
