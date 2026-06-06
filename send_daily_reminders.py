import os
import smtplib
import base64
import traceback
from datetime import datetime, date
from supabase import create_client

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]

COUPLE_NAMES = {
    "shahed": "Shahed",
    "mohammad": "Mohammad"
}

COUPLE_EMAILS = {
    "shahed": "shahedsobbahi@gmail.com",
    "mohammad": "altarrasm2001@gmail.com"
}

START_DATE = date(2025, 6, 6)

# ─────────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────────

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────
# EMAIL HTML — DIGEST (multiple events)
# ─────────────────────────────────────────────

def build_event_block(event, index):
    """Builds the HTML block for a single event inside the digest."""

    img_html = ""
    img_cid = f"event_image_{index}"

    if event.get("image") and event["image"].startswith("data:image"):
        img_html = f"""
        <img src="cid:{img_cid}"
             style="
                width:100%;
                max-width:560px;
                border-radius:12px;
                margin:16px 0;
                display:block;
             ">
        """

    description_html = event['description'].replace("\n", "<br>")

    year_label = f"<span style='color:#b08070;font-size:13px;'>({event['date'].year})</span>"

    return f"""
    <div style="
        border-left: 3px solid #e8a598;
        padding: 20px 24px;
        margin-bottom: 32px;
        background: #fffaf8;
        border-radius: 0 12px 12px 0;
    ">
        <h2 style="
            font-size:22px;
            margin:0 0 4px 0;
            color:#3a2e2e;
        ">
            {event['title']} {year_label}
        </h2>

        <div style="
            color:#b08070;
            font-size:13px;
            letter-spacing:1px;
            margin-bottom:14px;
        ">
            📅 {event['date'].strftime('%B %d, %Y')}
        </div>

        {img_html}

        <div style="
            font-style:italic;
            color:#7a5c5c;
            line-height:1.8;
            margin-bottom:16px;
            font-size:15px;
        ">
            {event['preview']}
        </div>

        <div style="
            height:1px;
            background:#f0ddd5;
            margin:16px 0;
        "></div>

        <div style="
            line-height:2;
            font-size:15px;
            color:#3a2e2e;
        ">
            {description_html}
        </div>
    </div>
    """


def build_digest_email_html(events, recipient_name):
    """Builds a full digest HTML email for all events sharing today's month/day."""

    today = date.today()
    days = (today - START_DATE).days
    date_label = today.strftime('%B %d')

    event_blocks_html = "".join(
        build_event_block(e, i) for i, e in enumerate(events)
    )

    count_label = (
        "One memory" if len(events) == 1
        else f"{len(events)} memories"
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="
        margin:0;
        padding:30px;
        background:#fdf6f0;
        font-family:Georgia,serif;
        color:#3a2e2e;
    ">

    <div style="
        max-width:650px;
        margin:auto;
        background:white;
        border-radius:20px;
        overflow:hidden;
        border:1px solid #f0ddd5;
    ">

        <!-- Header -->
        <div style="
            background:linear-gradient(135deg,#c9866b,#e8a598);
            padding:40px;
            text-align:center;
            color:white;
        ">
            <div style="font-size:28px;">❤️ 🌸 ❤️</div>

            <h1 style="
                margin:10px 0 0 0;
                font-size:32px;
                font-weight:400;
            ">
                M & S
            </h1>

            <div style="
                opacity:0.9;
                margin-top:8px;
                font-style:italic;
            ">
                On this day through the years
            </div>

            <div style="
                margin-top:14px;
                font-size:13px;
                opacity:0.9;
            ">
                ✨ Day {days} together · {date_label} ✨
            </div>
        </div>

        <!-- Intro -->
        <div style="padding:36px 40px 10px;">

            <div style="
                color:#c9866b;
                font-size:18px;
                margin-bottom:8px;
                font-style:italic;
            ">
                Good morning, {recipient_name} 🌸
            </div>

            <p style="
                font-size:15px;
                color:#7a5c5c;
                margin:0 0 28px 0;
                line-height:1.8;
            ">
                {count_label} happened on <strong>{date_label}</strong> across the years.
                Here they all are, just for you:
            </p>

            {event_blocks_html}

        </div>

        <!-- Footer -->
        <div style="
            background:#fdf0ea;
            padding:25px;
            text-align:center;
            color:#b08070;
            font-size:14px;
        ">
            Sent with love from M & S ❤️
        </div>

    </div>

    </body>
    </html>
    """


# ─────────────────────────────────────────────
# SEND DIGEST EMAIL
# ─────────────────────────────────────────────

def send_digest_email(events, recipient_email, recipient_name):
    """Send one digest email containing all events that share today's month/day."""

    try:
        msg = MIMEMultipart('related')

        today = date.today()
        date_label = today.strftime('%B %d')
        count = len(events)

        if count == 1:
            subject = f"🌸 On This Day: {events[0]['title']}"
        else:
            subject = f"❤️ On This Day ({date_label}) — {count} memories"

        msg['Subject'] = subject
        msg['From']    = f"M & S ❤️ <{SMTP_USER}>"
        msg['To']      = recipient_email

        alt_part = MIMEMultipart('alternative')
        msg.attach(alt_part)

        # Plain-text fallback
        plain_parts = [f"M & S ❤️ — Memories for {date_label}\n"]
        for e in events:
            plain_parts.append(
                f"\n{'─'*40}\n"
                f"{e['title']} ({e['date'].year})\n"
                f"{e['date'].strftime('%B %d, %Y')}\n\n"
                f"{e['preview']}\n\n"
                f"{e['description']}\n"
            )
        text_content = "\n".join(plain_parts)

        html_content = build_digest_email_html(events, recipient_name)

        alt_part.attach(MIMEText(text_content, 'plain', 'utf-8'))
        alt_part.attach(MIMEText(html_content, 'html', 'utf-8'))

        # Attach inline images (one per event that has one)
        for i, event in enumerate(events):
            if event.get("image") and event["image"].startswith("data:image"):
                image_data  = event["image"].split(",")[1]
                image_bytes = base64.b64decode(image_data)

                image = MIMEImage(image_bytes)
                image.add_header('Content-ID', f'<event_image_{i}>')
                image.add_header(
                    'Content-Disposition',
                    'inline',
                    filename=f'memory_{i}.jpg'
                )
                msg.attach(image)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient_email, msg.as_string())

        print(f"Digest sent to {recipient_name} ({count} event(s))")
        return True

    except Exception as ex:
        print(f"Email error for {recipient_name}: {ex}")
        traceback.print_exc()
        return False


# ─────────────────────────────────────────────
# DAILY REMINDERS — "On This Day" across years
# ─────────────────────────────────────────────

def send_today_reminders():
    """
    Fetch all enabled events whose month+day matches today (any year),
    bundle them into a single digest email per recipient, then mark each
    event's reminder_sent flag only for today's exact date record.
    """

    today = date.today()

    # Build a month-day pattern, e.g. "%-06-01" → rows with event_date LIKE '%-06-01'
    # Using PostgreSQL EXTRACT via Supabase RPC, or a simpler LIKE on the date string.
    # Supabase exposes PostgREST filters; the safest cross-year approach is to
    # fetch all enabled events and filter in Python (avoids DB-specific functions).

    res = (
        sb.table('our_events')
        .select('*')
        .eq('enabled', True)
        .execute()
    )

    if not res.data:
        print("No events in DB.")
        return

    # Filter: same month AND day as today, any year
    matching_rows = [
        row for row in res.data
        if _same_month_day(row['event_date'], today)
    ]

    if not matching_rows:
        print(f"No memories found for {today.strftime('%B %d')} (any year).")
        return

    # Build event dicts
    events = []
    for row in matching_rows:
        events.append({
            'id':           row['id'],
            'title':        row['event_title'],
            'date':         datetime.strptime(row['event_date'], '%Y-%m-%d').date(),
            'preview':      row['preview_text'],
            'description':  row['description'],
            'image':        row.get('image_data'),
            'reminder_sent': row.get('reminder_sent', False),
        })

    # Sort chronologically so the oldest memory comes first
    events.sort(key=lambda e: e['date'])

    print(
        f"Found {len(events)} memory/memories for "
        f"{today.strftime('%B %d')}: "
        + ", ".join(f"'{e['title']}' ({e['date'].year})" for e in events)
    )

    # Send one digest per recipient
    all_sent = True
    for uname, email in COUPLE_EMAILS.items():
        if not email:
            continue
        recipient_name = COUPLE_NAMES.get(uname, uname.title())
        ok = send_digest_email(events, email, recipient_name)
        if not ok:
            all_sent = False

    # Mark reminder_sent on today's exact-date rows only
    # (older anniversary rows stay un-marked so they can resurface next year)
    if all_sent:
        today_str = str(today)
        for event in events:
            if str(event['date']) == today_str and not event['reminder_sent']:
                (
                    sb.table('our_events')
                    .update({'reminder_sent': True})
                    .eq('id', event['id'])
                    .execute()
                )
                print(f"Marked event {event['id']} as sent.")


def _same_month_day(date_str: str, ref: date) -> bool:
    """Return True if date_str (YYYY-MM-DD) has the same month and day as ref."""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        return d.month == ref.month and d.day == ref.day
    except ValueError:
        return False


# ─────────────────────────────────────────────

if __name__ == "__main__":
    send_today_reminders()
