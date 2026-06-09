import os
import re
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
# LOGGING HELPER
# ─────────────────────────────────────────────

ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

def is_arabic(text):
    return bool(ARABIC_RE.search(text))

def log(msg: str):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

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

    title_rtl = 'dir="rtl" style="text-align:right;' if is_arabic(event['title']) else 'style="'
    preview_rtl = 'dir="rtl" style="text-align:right;' if is_arabic(event['preview']) else 'style="'
    desc_rtl = 'dir="rtl" style="text-align:right;' if is_arabic(event['description']) else 'style="'

    card_is_rtl = is_arabic(event['description']) or is_arabic(event['title'])
    if card_is_rtl:
        card_border = "border-right:3px solid #e8a598;border-left:none;border-radius:12px 0 0 12px;"
    else:
        card_border = "border-left:3px solid #e8a598;border-radius:0 12px 12px 0;"

    return f"""
    <div style="
        {card_border}
        padding: 20px 24px;
        margin-bottom: 32px;
        background: #fffaf8;
    ">
        <h2 {title_rtl}
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

        <div {preview_rtl}
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

        <div {desc_rtl}
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
        log(f"🔄 Attempting to send email to {recipient_name} ({recipient_email})...")
        
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

        log(f"  📧 Subject: {subject}")
        log(f"  ✉️ From: {SMTP_USER}")
        log(f"  ✉️ To: {recipient_email}")

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

        log(f"  📝 Email body prepared")

        # Attach inline images (one per event that has one)
        image_count = 0
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
                image_count += 1
        
        if image_count > 0:
            log(f"  🖼️ Attached {image_count} image(s)")

        log(f"  🔐 Connecting to {SMTP_HOST}:{SMTP_PORT}...")
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            log(f"  ✓ EHLO successful")
            
            server.starttls()
            log(f"  🔒 TLS connection established")
            
            server.login(SMTP_USER, SMTP_PASS)
            log(f"  ✓ Authentication successful")
            
            server.sendmail(SMTP_USER, recipient_email, msg.as_string())
            log(f"  ✓ Email sent successfully")

        log(f"✅ Digest email sent to {recipient_name} ({count} event(s))")
        return True

    except smtplib.SMTPAuthenticationError as ex:
        log(f"❌ AUTHENTICATION ERROR for {recipient_name}: {ex}")
        log(f"   Check SMTP_USER and SMTP_PASS environment variables")
        traceback.print_exc()
        return False
    
    except smtplib.SMTPException as ex:
        log(f"❌ SMTP ERROR for {recipient_name}: {ex}")
        traceback.print_exc()
        return False
    
    except Exception as ex:
        log(f"❌ UNEXPECTED ERROR for {recipient_name}: {ex}")
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

    log("="*60)
    log("🚀 STARTING DAILY REMINDER SCRIPT")
    log("="*60)
    
    today = date.today()
    log(f"📅 Today's date: {today.strftime('%Y-%m-%d (%B %d)')}")

    # Build a month-day pattern, e.g. "%-06-01" → rows with event_date LIKE '%-06-01'
    # Using PostgreSQL EXTRACT via Supabase RPC, or a simpler LIKE on the date string.
    # Supabase exposes PostgREST filters; the safest cross-year approach is to
    # fetch all enabled events and filter in Python (avoids DB-specific functions).

    log("📊 Querying Supabase for all enabled events...")
    
    try:
        res = (
            sb.table('our_events')
            .select('*')
            .eq('enabled', True)
            .execute()
        )
        log(f"  ✓ Query successful, received {len(res.data)} total events")
    except Exception as ex:
        log(f"❌ DATABASE ERROR: Failed to query events: {ex}")
        traceback.print_exc()
        return

    if not res.data:
        log("⚠️ No events in DB.")
        return

    # Filter: same month AND day as today, any year
    matching_rows = [
        row for row in res.data
        if _same_month_day(row['event_date'], today)
    ]

    if not matching_rows:
        log(f"⚠️ No memories found for {today.strftime('%B %d')} (any year).")
        return

    log(f"🎯 Found {len(matching_rows)} matching memory/memories for today:")
    
    # Build event dicts
    events = []
    for i, row in enumerate(matching_rows):
        event_dict = {
            'id':           row['id'],
            'title':        row['event_title'],
            'date':         datetime.strptime(row['event_date'], '%Y-%m-%d').date(),
            'preview':      row['preview_text'],
            'description':  row['description'],
            'image':        row.get('image_data'),
            'reminder_sent': row.get('reminder_sent', False),
        }
        events.append(event_dict)
        log(f"   {i+1}. '{event_dict['title']}' ({event_dict['date'].year})")

    # Sort chronologically so the oldest memory comes first
    events.sort(key=lambda e: e['date'])

    print()
    log(f"📧 SENDING EMAILS TO {len(COUPLE_EMAILS)} RECIPIENTS")
    log("-"*60)
    
    # Send one digest per recipient
    all_sent = True
    send_results = {}
    
    for uname, email in COUPLE_EMAILS.items():
        log(f"\n🔹 Processing recipient: {uname.upper()}")
        log(f"   Email: {email}")
        
        if not email:
            log(f"   ⚠️ SKIPPED: No email address configured")
            send_results[uname] = False
            continue
        
        recipient_name = COUPLE_NAMES.get(uname, uname.title())
        log(f"   Name: {recipient_name}")
        
        ok = send_digest_email(events, email, recipient_name)
        send_results[uname] = ok
        
        if not ok:
            log(f"   ❌ FAILED to send to {uname}")
            all_sent = False
        else:
            log(f"   ✅ SENT to {uname}")

    print()
    log("-"*60)
    log("📋 SEND RESULTS SUMMARY:")
    for uname, success in send_results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        log(f"   {uname.upper()}: {status}")
    
    all_sent = all(send_results.values())
    
    if all_sent:
        log(f"\n✅ All emails sent successfully. Marking events...")
        # Mark reminder_sent on today's exact-date rows only
        # (older anniversary rows stay un-marked so they can resurface next year)
        today_str = str(today)
        marked_count = 0
        
        for event in events:
            if str(event['date']) == today_str and not event['reminder_sent']:
                try:
                    (
                        sb.table('our_events')
                        .update({'reminder_sent': True})
                        .eq('id', event['id'])
                        .execute()
                    )
                    marked_count += 1
                    log(f"   ✓ Marked event '{event['title']}' (ID: {event['id']}) as sent")
                except Exception as ex:
                    log(f"   ❌ Failed to mark event '{event['title']}' (ID: {event['id']}): {ex}")
        
        log(f"   Total marked: {marked_count}/{len(events)}")
    else:
        log(f"\n❌ Not all emails were sent. Skipping reminder_sent update.")
        for uname, success in send_results.items():
            if not success:
                log(f"   - {uname.upper()} failed")
    
    log("="*60)
    log("✅ SCRIPT COMPLETED")
    log("="*60)


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
