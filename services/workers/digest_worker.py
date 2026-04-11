"""
Weekly Digest worker — M9.

Invoked by EventBridge Scheduler weekly (not a Step Functions worker).
Queries DynamoDB for topics published in the last 7 days, assembles an HTML
email, sends it via Amazon SES, and writes a NOTIF record to DynamoDB.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3

_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env.local")
except ImportError:
    pass

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
_AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
_SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "")
_OWNER_EMAIL = os.environ.get("OWNER_EMAIL", _SES_SENDER)
_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "https://example.com")


def _table():
    return boto3.resource("dynamodb", region_name=_AWS_REGION).Table(_TABLE_NAME)


def _ses():
    return boto3.client("sesv2", region_name=_AWS_REGION)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _published_since(cutoff_iso: str) -> list[dict]:
    """
    Scan for PUBLISHED_VERSION entities updated on or after cutoff.
    Returns list of topic records sorted by published_at descending.
    """
    from boto3.dynamodb.conditions import Attr
    resp = _table().scan(
        FilterExpression=(
            Attr("ENTITY_TYPE").eq("PUBLISHED_VERSION") &
            Attr("published_at").gte(cutoff_iso)
        ),
        ProjectionExpression="topic_id, #ver, title, published_at, release_notes, word_count",
        ExpressionAttributeNames={"#ver": "version"},
    )
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: x.get("published_at", ""), reverse=True)


def _build_html(topics: list[dict], week_of: str) -> str:
    rows = ""
    for t in topics:
        title = t.get("title", "Untitled")
        version = t.get("version", "")
        slug = title.lower().replace(" ", "-").replace("'", "")
        url = f"{_SITE_URL}/topics/{slug}"
        pub_date = ""
        raw = t.get("published_at", "")
        if raw:
            try:
                pub_date = datetime.fromisoformat(raw).strftime("%B %d, %Y")
            except ValueError:
                pub_date = raw
        notes = t.get("release_notes") or ""
        word_count = t.get("word_count", 0)
        rows += f"""
        <tr>
          <td style="padding:14px 0;border-bottom:1px solid #e5e7eb;">
            <a href="{url}" style="font-size:16px;font-weight:600;color:#111827;text-decoration:none;">{title}</a>
            <span style="display:inline-block;margin-left:8px;background:#ede9fe;color:#7c3aed;
                         border-radius:4px;padding:2px 7px;font-size:12px;font-weight:600;">{version}</span>
            <div style="font-size:13px;color:#6b7280;margin-top:4px;">
              {pub_date} · {int(word_count):,} words
            </div>
            {f'<div style="font-size:13px;color:#374151;margin-top:6px;font-style:italic;">{notes}</div>' if notes else ''}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:0;background:#f9fafb;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;
           border:1px solid #e5e7eb;overflow:hidden;">
      <tr>
        <td style="background:#111827;padding:24px 32px;">
          <span style="color:#fff;font-size:20px;font-weight:700;">📖 Ebook Weekly Digest</span>
          <div style="color:#9ca3af;font-size:13px;margin-top:4px;">Week of {week_of}</div>
        </td>
      </tr>
      <tr>
        <td style="padding:24px 32px;">
          <p style="color:#374151;font-size:15px;margin:0 0 20px;">
            {len(topics)} chapter{"s" if len(topics) != 1 else ""} published or updated this week:
          </p>
          <table width="100%" cellpadding="0" cellspacing="0">
            {rows}
          </table>
          <p style="margin-top:28px;">
            <a href="{_SITE_URL}" style="display:inline-block;background:#111827;color:#fff;
               border-radius:6px;padding:10px 22px;text-decoration:none;font-size:14px;font-weight:500;">
              View all chapters →
            </a>
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:16px 32px;border-top:1px solid #e5e7eb;background:#f9fafb;">
          <p style="font-size:12px;color:#9ca3af;margin:0;">
            You're receiving this because you're the owner of this ebook.
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _build_text(topics: list[dict], week_of: str) -> str:
    lines = [f"Ebook Weekly Digest — Week of {week_of}", "", f"{len(topics)} update(s) this week:", ""]
    for t in topics:
        title = t.get("title", "Untitled")
        version = t.get("version", "")
        slug = title.lower().replace(" ", "-").replace("'", "")
        url = f"{_SITE_URL}/topics/{slug}"
        pub_date = t.get("published_at", "")[:10]
        notes = t.get("release_notes") or ""
        lines.append(f"• {title} [{version}] — {pub_date}")
        lines.append(f"  {url}")
        if notes:
            lines.append(f"  {notes}")
        lines.append("")
    return "\n".join(lines)


def handler(event: dict, context: Any) -> dict:
    if not _SES_SENDER or not _OWNER_EMAIL:
        print("SES_SENDER_EMAIL / OWNER_EMAIL not set — skipping digest.")
        return {"status": "SKIPPED", "reason": "email not configured"}

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat()
    week_of = now.strftime("%B %d, %Y")

    topics = _published_since(cutoff)
    if not topics:
        print("No topics published in the last 7 days — skipping digest.")
        return {"status": "SKIPPED", "reason": "no_new_content", "topics_included": 0}

    html_body = _build_html(topics, week_of)
    text_body = _build_text(topics, week_of)
    subject = f"Weekly Digest: {len(topics)} chapter update{'s' if len(topics) != 1 else ''}"

    _ses().send_email(
        FromEmailAddress=_SES_SENDER,
        Destination={"ToAddresses": [_OWNER_EMAIL]},
        Content={
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html":  {"Data": html_body,  "Charset": "UTF-8"},
                },
            }
        },
    )

    # Write notification log
    now_iso = _utc_now()
    notif_id = str(uuid4())
    _table().put_item(Item={
        "PK": f"NOTIF#{_OWNER_EMAIL}",
        "SK": f"TS#{now_iso}",
        "ENTITY_TYPE": "NOTIFICATION",
        "notif_id": notif_id,
        "recipient": _OWNER_EMAIL,
        "subject": subject,
        "topics_included": len(topics),
        "sent_at": now_iso,
        "CREATED_AT": now_iso,
    })

    print(f"Digest sent to {_OWNER_EMAIL}: {len(topics)} topics.")
    return {
        "status": "SENT",
        "recipient": _OWNER_EMAIL,
        "topics_included": len(topics),
        "sent_at": now_iso,
    }
