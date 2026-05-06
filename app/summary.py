import logging
import re
from urllib.parse import quote

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Template

from app.config import settings
from app.db.models import Email

log = logging.getLogger(__name__)


def _extract_email(sender: str) -> str:
    match = re.search(r"<(.+?)>", sender)
    return match.group(1) if match else sender


def _gmail_compose_url(sender: str, subject: str, body: str) -> str:
    to = _extract_email(sender)
    re_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
    return (
        f"https://mail.google.com/mail/u/0/?view=cm"
        f"&to={quote(to)}"
        f"&su={quote(re_subject)}"
        f"&body={quote(body)}"
    )


_HTML = Template("""\
<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #333;">
  <h2 style="color: #333; margin-bottom: 4px;">Email Triage Summary</h2>
  <p style="color: #888; margin-top: 0;">
    {{ action|length }} need replies &nbsp;·&nbsp;
    {{ important|length }} important &nbsp;·&nbsp;
    {{ informational|length }} informational &nbsp;·&nbsp;
    {{ newsletter_count }} newsletters &nbsp;·&nbsp;
    {{ spam_count }} spam
  </p>

  {% if action %}
  <h3 style="color: #c0392b; border-bottom: 2px solid #f5c6cb; padding-bottom: 6px;">Reply Required</h3>
  {% for email in action %}
  <div style="border: 1px solid #f5c6cb; border-radius: 6px; padding: 16px; margin-bottom: 16px; background: #fff8f8;">
    <p style="margin: 0 0 2px 0;"><strong>From:</strong> {{ email.sender }}</p>
    <p style="margin: 0 0 2px 0;"><strong>Subject:</strong> {{ email.subject }}</p>
    <p style="margin: 0 0 12px 0; color: #888; font-size: 13px;">{{ email.classification_reason }}</p>
    {% if email.suggested_reply %}
    <div style="background: #f0f4ff; border-left: 3px solid #4a90e2; padding: 12px; border-radius: 0 4px 4px 0; margin-bottom: 12px;">
      <p style="margin: 0 0 6px 0; font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Suggested Reply</p>
      <p style="margin: 0; white-space: pre-wrap; font-size: 14px;">{{ email.suggested_reply }}</p>
    </div>
    <a href="{{ email.gmail_url }}"
       style="display: inline-block; background: #4a90e2; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: 500;">
      Edit &amp; Send in Gmail →
    </a>
    {% endif %}
  </div>
  {% endfor %}
  {% endif %}

  {% if important %}
  <h3 style="color: #e67e22; border-bottom: 2px solid #fdebd0; padding-bottom: 6px; margin-top: 28px;">Important</h3>
  {% for email in important %}
  <div style="border: 1px solid #fdebd0; border-radius: 6px; padding: 12px 16px; margin-bottom: 8px; background: #fffdf8;">
    <p style="margin: 0 0 2px 0;"><strong>From:</strong> {{ email.sender }}</p>
    <p style="margin: 0 0 2px 0;"><strong>Subject:</strong> {{ email.subject }}</p>
    <p style="margin: 0; color: #888; font-size: 13px;">{{ email.classification_reason }}</p>
  </div>
  {% endfor %}
  {% endif %}

  {% if informational %}
  <h3 style="color: #555; border-bottom: 1px solid #eee; padding-bottom: 6px; margin-top: 28px;">Informational</h3>
  {% for email in informational %}
  <div style="border: 1px solid #eee; border-radius: 6px; padding: 10px 16px; margin-bottom: 6px;">
    <p style="margin: 0 0 2px 0;"><strong>From:</strong> {{ email.sender }}</p>
    <p style="margin: 0 0 2px 0;"><strong>Subject:</strong> {{ email.subject }}</p>
    <p style="margin: 0; color: #aaa; font-size: 13px;">{{ email.classification_reason }}</p>
  </div>
  {% endfor %}
  {% endif %}

  {% if newsletter_count or spam_count %}
  <p style="color: #bbb; font-size: 13px; margin-top: 24px;">
    {{ newsletter_count }} newsletter(s) and {{ spam_count }} spam filtered out.
  </p>
  {% endif %}
</body>
</html>
""")


async def send_summary(all_emails: list[Email]) -> None:
    action = [e for e in all_emails if e.classification == "action"]
    important = [e for e in all_emails if e.classification == "important"]
    informational = [e for e in all_emails if e.classification == "informational"]
    newsletter_count = sum(1 for e in all_emails if e.classification == "newsletter")
    spam_count = sum(1 for e in all_emails if e.classification == "spam")

    if not action and not important:
        log.info("Nothing actionable — skipping summary.")
        return

    # Attach Gmail compose URLs to action emails
    for e in action:
        if e.suggested_reply:
            e.gmail_url = _gmail_compose_url(e.sender, e.subject, e.suggested_reply)
        else:
            e.gmail_url = ""

    if not settings.smtp_host:
        log.info("SMTP not configured — %d action, %d important, %d informational.",
                 len(action), len(important), len(informational))
        return

    html_body = _HTML.render(
        action=action,
        important=important,
        informational=informational,
        newsletter_count=newsletter_count,
        spam_count=spam_count,
    )

    subject_parts = []
    if action:
        subject_parts.append(f"{len(action)} need replies")
    if important:
        subject_parts.append(f"{len(important)} important")
    email_subject = "Email Triage — " + ", ".join(subject_parts)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_subject
    msg["From"] = settings.summary_email_from or settings.smtp_user
    msg["To"] = settings.summary_email_to
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )
    log.info("Summary sent — %d action, %d important, %d informational, %d newsletters, %d spam.",
             len(action), len(important), len(informational), newsletter_count, spam_count)
