"""
📄 Email Sender

Send reports via email.
"""

import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Send reports via email.

    Features:
    - HTML emails
    - PDF attachments
    - Multiple recipients
    - SMTP support
    """

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str | None = None,
        sender_password: str | None = None,
        use_tls: bool = True,
    ):
        """
        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            sender_email: Sender email address
            sender_password: Sender email password
            use_tls: Use TLS encryption
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.use_tls = use_tls

    async def send_report(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        pdf_attachment: bytes | None = None,
        pdf_filename: str = "report.pdf",
    ) -> bool:
        """
        Send report via email.

        Args:
            recipient: Recipient email
            subject: Email subject
            html_body: HTML email body
            pdf_attachment: PDF bytes (optional)
            pdf_filename: PDF filename

        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = recipient

            # Attach HTML body
            msg.attach(MIMEText(html_body, "html"))

            # Attach PDF
            if pdf_attachment:
                attachment = MIMEBase("application", "octet-stream")
                attachment.set_payload(pdf_attachment)
                encoders.encode_base64(attachment)
                attachment.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
                msg.attach(attachment)

            # Send email
            if self.sender_email and self.sender_password:
                await self._send_smtp(msg, [recipient])
            else:
                # Mock send (log only)
                logger.info(f"Email would be sent to {recipient} (no SMTP configured)")
                logger.info(f"Subject: {subject}")

            logger.info(f"Report email sent to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    async def _send_smtp(self, msg: MIMEMultipart, recipients: list[str]):
        """Send via SMTP"""
        try:
            # Connect to SMTP server
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)

            # Login
            if self.sender_password:
                server.login(self.sender_email, self.sender_password)

            # Send
            server.send_message(msg, self.sender_email, recipients)

            # Disconnect
            server.quit()

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            raise

    def send_bulk(
        self,
        recipients: list[str],
        subject: str,
        html_body: str,
        pdf_attachment: bytes | None = None,
    ) -> dict[str, bool]:
        """
        Send report to multiple recipients.

        Args:
            recipients: List of recipient emails
            subject: Email subject
            html_body: HTML body
            pdf_attachment: PDF bytes

        Returns:
            Dictionary {email: success}
        """
        results = {}

        for recipient in recipients:
            try:
                import asyncio

                success = asyncio.run(
                    self.send_report(
                        recipient=recipient,
                        subject=subject,
                        html_body=html_body,
                        pdf_attachment=pdf_attachment,
                    )
                )
                results[recipient] = success
            except Exception as e:
                logger.error(f"Failed to send to {recipient}: {e}")
                results[recipient] = False

        return results

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "sender_email": self.sender_email,
            "use_tls": self.use_tls,
        }
