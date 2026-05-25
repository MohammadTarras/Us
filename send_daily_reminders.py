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
    "shahed": "",
    "mohammad": "altarrasm2001@gmail.com"
}

START_DATE = date(2025, 6, 6)

# ─────────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────────

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────
# EMAIL HTML
# ─────────────────────────────────────────────

def build_email_html(event, recipient_name):

    img_html = ""

    if event.get("image") and event["image"].startswith("data:image"):
        img_html = """
        <img src="cid:event_image"
             style="
                width:100%;
                max-width:600px;
                border-radius:14px;
                margin:20px 0;
                display:block;
             ">
        """

    description_html = event['description'].replace("\n", "<br>")

    days = (date.today() - START_DATE).days

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
                A memory for two
            </div>

            <div style="
                margin-top:14px;
                font-size:13px;
                opacity:0.9;
            ">
                ✨ Day {days} together ✨
            </div>
        </div>

        <div style="padding:40px;">

            <div style="
                color:#c9866b;
                font-size:18px;
                margin-bottom:12px;
                font-style:italic;
            ">
                Good morning, {recipient_name} 🌸
            </div>

            <h2 style="
                font-size:30px;
                margin:0;
                color:#3a2e2e;
            ">
                {event['title']}
            </h2>

            <div style="
                color:#b08070;
                margin-top:10px;
                margin-bottom:25px;
                font-size:14px;
                letter-spacing:1px;
            ">
                📅 {event['date'].strftime('%B %d, %Y')}
            </div>

            {img_html}

            <div style="
                font-style:italic;
                color:#7a5c5c;
                line-height:1.8;
                margin-bottom:25px;
                font-size:16px;
            ">
                {event['preview']}
            </div>

            <div style="
                height:1px;
                background:#f0ddd5;
                margin:25px 0;
            "></div>

            <div style="
                line-height:2;
                font-size:16px;
                color:#3a2e2e;
            ">
                {description_html}
            </div>

        </div>

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
# SEND EMAIL
# ─────────────────────────────────────────────

def send_event_email(event, recipient_email, recipient_name):

    try:

        msg = MIMEMultipart('related')

        event_date = event['date']

        if event_date == date.today():
            subject = f"🌸 Today's Memory: {event['title']}"
        else:
            subject = f"❤️ Memory: {event['title']}"

        msg['Subject'] = subject
        msg['From'] = f"M & S ❤️ <{SMTP_USER}>"
        msg['To'] = recipient_email

        alt_part = MIMEMultipart('alternative')
        msg.attach(alt_part)

        html_content = build_email_html(event, recipient_name)

        text_content = f"""
M & S ❤️

{event['title']}

{event['date'].strftime('%B %d, %Y')}

{event['preview']}

{event['description']}
"""

        alt_part.attach(MIMEText(text_content, 'plain', 'utf-8'))
        alt_part.attach(MIMEText(html_content, 'html', 'utf-8'))

        # Inline image
        if event.get("image") and event["image"].startswith("data:image"):

            image_data = event["image"].split(",")[1]
            image_bytes = base64.b64decode(image_data)

            image = MIMEImage(image_bytes)
            image.add_header('Content-ID', '<event_image>')
            image.add_header(
                'Content-Disposition',
                'inline',
                filename='memory.jpg'
            )

            msg.attach(image)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(
                SMTP_USER,
                recipient_email,
                msg.as_string()
            )

        print(f"Sent to {recipient_name}")
        return True

    except Exception as ex:
        print(f"Email error: {ex}")
        traceback.print_exc()
        return False

# ─────────────────────────────────────────────
# DAILY REMINDERS
# ─────────────────────────────────────────────

def send_today_reminders():

    today_str = str(date.today())

    res = (
        sb.table('our_events')
        .select('*')
        .eq('event_date', today_str)
        .eq('enabled', True)
        .eq('reminder_sent', False)
        .execute()
    )

    if not res.data:
        print("No reminders today.")
        return

    for row in res.data:

        event = {
            'id': row['id'],
            'title': row['event_title'],
            'date': datetime.strptime(
                row['event_date'],
                '%Y-%m-%d'
            ).date(),
            'preview': row['preview_text'],
            'description': row['description'],
            'image': row.get('image_data')
        }

        success = True

        for uname, email in COUPLE_EMAILS.items():

            if not email:
                continue

            recipient_name = COUPLE_NAMES.get(
                uname,
                uname.title()
            )

            ok = send_event_email(
                event,
                email,
                recipient_name
            )

            if not ok:
                success = False

        if success:

            (
                sb.table('our_events')
                .update({'reminder_sent': True})
                .eq('id', event['id'])
                .execute()
            )

            print(f"Marked event {event['id']} as sent.")

# ─────────────────────────────────────────────

if __name__ == "__main__":
    send_today_reminders()