import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from supabase import create_client
import hashlib
import time
import re
import secrets
import base64
from PIL import Image
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import traceback
from functools import wraps
from io import BytesIO
import calendar
import json

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

color_map = {
    "shahed": "#e65e5e",
    "mohammad": "#80ceff"
}

COUPLE_NAMES = {"shahed": "Shahed", "mohammad": "Mohammad"}
COUPLE_EMAILS = {
    "shahed":   "shahedsobbahi@gmail.com",   # ← replace
    "mohammad": "altarrasm2001@gmail.com"  # ← replace
}
SMTP_HOST    = "smtp.gmail.com"
SMTP_PORT    = 587
SMTP_USER    = "ms.memories2026@gmail.com"   # ← replace
SMTP_PASS    = "exhs uvrk gxxy xytz"      # ← replace
START_DATE   = date(2025, 6, 6)

st.set_page_config(
    page_title="M & S ❤️",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL  = "https://qvkrvidkgzscjycbmdxu.supabase.co"
SUPABASE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF2a3J2aWRrZ3pzY2p5Y2JtZHh1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY4ODY5OTQsImV4cCI6MjA3MjQ2Mjk5NH0.HHAwIvBpxJeAJUpyI0KemV9Et1mezv5Tli-qB1n1PGI"

@st.cache_resource(ttl=3600)
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def cache_db_operation(ttl=300, key_prefix="db"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}_{func.__name__}_{hash(str(args)+str(kwargs))}"
            if cache_key in st.session_state:
                cached_data, timestamp = st.session_state[cache_key]
                if time.time() - timestamp < ttl:
                    return cached_data
            result = func(*args, **kwargs)
            st.session_state[cache_key] = (result, time.time())
            return result
        return wrapper
    return decorator

# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_session_token():
    return secrets.token_urlsafe(32)

def save_session_token(username, token):
    try:
        sb = init_supabase()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        sb.table('user_sessions').delete().eq('username', username).execute()
        sb.table('user_sessions').insert({'username': username, 'session_token': token, 'expires_at': expires_at}).execute()
        return True
    except Exception:
        return False

def verify_session_token(token):
    try:
        sb = init_supabase()
        res = sb.table('user_sessions').select('*').eq('session_token', token).execute()
        if not res.data:
            return None
        session = res.data[0]
        exp = session['expires_at']
        if exp.endswith('Z'):
            exp = datetime.fromisoformat(exp.replace('Z', '+00:00'))
        elif '+' in exp:
            exp = datetime.fromisoformat(exp)
        else:
            exp = datetime.fromisoformat(exp).replace(tzinfo=timezone.utc)
        if exp > datetime.now(timezone.utc):
            user_res = sb.table('users').select('*').eq('username', session['username']).execute()
            if user_res.data:
                return user_res.data[0]
        else:
            sb.table('user_sessions').delete().eq('session_token', token).execute()
        return None
    except Exception:
        return None

def authenticate_user(username, password):
    try:
        sb = init_supabase()
        hashed = hash_password(password)
        res = sb.table('users').select('*').eq('username', username).eq('password_hash', hashed).execute()
        if res.data:
            user = res.data[0]
            token = generate_session_token()
            if save_session_token(username, token):
                st.query_params.update({'session_token': token})
                try:
                    sb.table('logins').insert({'username': username}).execute()
                except Exception:
                    pass
                return True, user
        return False, None
    except Exception:
        return False, None

def logout():
    try:
        sb = init_supabase()
        token = st.query_params.get('session_token')
        if token:
            sb.table('user_sessions').delete().eq('session_token', token).execute()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    st.query_params.clear()
    st.rerun()

def check_session_from_url():
    if 'session_token' in st.query_params:
        token = st.query_params['session_token']
        user = verify_session_token(token)
        if user:
            st.session_state.authenticated = True
            st.session_state.user = user
            return True
        else:
            st.query_params.clear()
            st.session_state.authenticated = False
            st.session_state.user = None
    return False

# ─────────────────────────────────────────────────────────────────────────────
# IMAGE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def encode_image_to_base64(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        if image.width > 1200:
            ratio = 1200 / image.width
            image = image.resize((1200, int(image.height * ratio)), Image.Resampling.LANCZOS)
        if image.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            bg.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = bg
        buf = io.BytesIO()
        image.save(buf, format='JPEG', quality=85, optimize=True)
        buf.seek(0)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.read()).decode()}"
    except Exception as e:
        st.error(f"Image error: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE EVENTS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False, max_entries=50)
def load_events_from_db(username):
    try:
        sb = init_supabase()
        res = sb.table('our_events').select('*').eq('enabled', True).order('event_date', desc=True).execute()
        events = []
        for e in res.data:
            events.append({
                'id': e['id'],
                'title': e['event_title'],
                'date': datetime.strptime(e['event_date'], '%Y-%m-%d').date(),
                'preview': e['preview_text'],
                'description': e['description'],
                'image': e.get('image_data'),
                'reminder_sent': e.get('reminder_sent', False),
            })
        return events
    except Exception as ex:
        st.error(f"Error loading events: {ex}")
        return []

def clear_events_cache():
    load_events_from_db.clear()
    for k in [k for k in st.session_state.keys() if k.startswith("db_load_events")]:
        del st.session_state[k]
    st.session_state.selected_event = None
    st.session_state.selected_event_id = None
    st.session_state.edit_event_id = None

def save_event_to_db(title, event_date, preview, description, username, image_base64=None, send_today=False):
    try:
        sb = init_supabase()
        data = {
            'event_title': title,
            'event_date': str(event_date),
            'preview_text': preview,
            'description': description,
            'reminder_sent': False,
        }
        if image_base64:
            data['image_data'] = image_base64
        sb.table('our_events').insert(data).execute()
        clear_events_cache()
        return True
    except Exception as ex:
        st.error(f"Error saving: {ex}")
        return False

def update_event_in_db(event_id, title, event_date, preview, description, username, image_base64=None):
    try:
        sb = init_supabase()
        data = {
            'event_title': title,
            'event_date': str(event_date),
            'preview_text': preview,
            'description': description,
        }
        if image_base64 is not None:
            data['image_data'] = image_base64
        sb.table('our_events').update(data).eq('id', event_id).execute()
        clear_events_cache()
        return True
    except Exception as ex:
        st.error(f"Error updating: {ex}")
        return False

def delete_event_from_db(event_id, username):
    try:
        sb = init_supabase()
        sb.table('our_events').update({"enabled": False}).eq('id', event_id).execute()
        clear_events_cache()
        return True
    except Exception as ex:
        st.error(f"Error deleting: {ex}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def _build_event_block(event, index):
    """Single event card inside the digest email."""
    img_html = ""
    if event.get("image") and event["image"].startswith("data:image"):
        img_html = f"""
        <img src="cid:event_image_{index}"
             style="width:100%;max-width:560px;border-radius:12px;
                    margin:16px 0;display:block;">
        """
    description_html = event['description'].replace("\n", "<br>")
    year_label = f"<span style='color:#b08070;font-size:13px;'>({event['date'].year})</span>"
    title_rtl = 'dir="rtl" style="text-align:right;' if is_arabic(event['title']) else 'style="'
    preview_rtl = 'dir="rtl" style="text-align:right;' if is_arabic(event['preview']) else 'style="'
    desc_rtl = 'dir="rtl" style="text-align:right;' if is_arabic(event['description']) else 'style="'
    # Use border-right instead of border-left for RTL content
    card_is_rtl = is_arabic(event['description']) or is_arabic(event['title'])
    if card_is_rtl:
        card_border = "border-right:3px solid #e8a598;border-left:none;border-radius:12px 0 0 12px;"
    else:
        card_border = "border-left:3px solid #e8a598;border-radius:0 12px 12px 0;"
    return f"""
    <div style="{card_border}padding:20px 24px;margin-bottom:32px;
                background:#fffaf8;">
        <h2 {title_rtl}font-size:22px;margin:0 0 4px 0;color:#3a2e2e;">
            {event['title']} {year_label}
        </h2>
        <div style="color:#b08070;font-size:13px;letter-spacing:1px;margin-bottom:14px;">
            📅 {event['date'].strftime('%B %d, %Y')}
        </div>
        {img_html}
        <div {preview_rtl}font-style:italic;color:#7a5c5c;line-height:1.8;
                    margin-bottom:16px;font-size:15px;">
            {event['preview']}
        </div>
        <div style="height:1px;background:#f0ddd5;margin:16px 0;"></div>
        <div {desc_rtl}line-height:2;font-size:15px;color:#3a2e2e;">
            {description_html}
        </div>
    </div>
    """


def _build_digest_html(events, recipient_name, sender_name=None):
    """Full digest email HTML — one email, all matching memories."""
    today      = date.today()
    days       = (today - START_DATE).days
    date_label = today.strftime('%B %d')
    count      = len(events)
    count_label = "One memory" if count == 1 else f"{count} memories"
    blocks = "".join(_build_event_block(e, i) for i, e in enumerate(events))

    if sender_name:
        subtitle = "A shared memory"
        intro_text = f"""{sender_name} wanted to remind you about this memory with all love 💕"""
    else:
        subtitle = "On this day through the years"
        intro_text = f"""{count_label} happened on <strong>{date_label}</strong> across the years.
        Here they all are, just for you:"""

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:30px;background:#fdf6f0;font-family:Georgia,serif;color:#3a2e2e;">
<div style="max-width:650px;margin:auto;background:white;border-radius:20px;
            overflow:hidden;border:1px solid #f0ddd5;">

  <div style="background:linear-gradient(135deg,#c9866b,#e8a598);padding:40px;
              text-align:center;color:white;">
    <div style="font-size:28px;">❤️ 🌸 ❤️</div>
    <h1 style="margin:10px 0 0 0;font-size:32px;font-weight:400;">M &amp; S</h1>
    <div style="opacity:0.9;margin-top:8px;font-style:italic;">{subtitle}</div>
    <div style="margin-top:14px;font-size:13px;opacity:0.9;">✨ Day {days} together · {date_label} ✨</div>
  </div>

  <div style="padding:36px 40px 10px;">
    <div style="color:#c9866b;font-size:18px;margin-bottom:8px;font-style:italic;">
        Good morning, {recipient_name} 🌸
    </div>
    <p style="font-size:15px;color:#7a5c5c;margin:0 0 28px 0;line-height:1.8;">
        {intro_text}
    </p>
    {blocks}
  </div>

  <div style="background:#fdf0ea;padding:25px;text-align:center;color:#b08070;font-size:14px;">
    Sent with love from M &amp; S ❤️
  </div>
</div>
</body>
</html>"""


def _send_digest_smtp(events, recipient_email, recipient_name, sender_name=None):
    """Low-level: build and send the digest MIME message."""
    try:
        msg = MIMEMultipart('related')
        today      = date.today()
        date_label = today.strftime('%B %d')
        count      = len(events)

        if sender_name:
            subject = f"🌸 {sender_name} shared a memory: {events[0]['title']}"
        elif count == 1:
            subject = f"🌸 On This Day: {events[0]['title']}"
        else:
            subject = f"❤️ On This Day ({date_label}) — {count} memories"

        msg['Subject'] = subject
        msg['From']    = f"M & S ❤️ <{SMTP_USER}>"
        msg['To']      = recipient_email

        alt_part = MIMEMultipart('alternative')
        msg.attach(alt_part)

        # Plain text fallback
        if sender_name:
            lines = [f"M & S ❤️ — {sender_name} wanted to remind you about this memory with all love\n"]
        else:
            lines = [f"M & S ❤️ — Memories for {date_label}\n"]
        for e in events:
            lines.append(
                f"\n{'─'*40}\n{e['title']} ({e['date'].year})\n"
                f"{e['date'].strftime('%B %d, %Y')}\n\n{e['preview']}\n\n{e['description']}\n"
            )
        alt_part.attach(MIMEText("\n".join(lines), 'plain', 'utf-8'))
        alt_part.attach(MIMEText(_build_digest_html(events, recipient_name, sender_name=sender_name), 'html', 'utf-8'))

        # Inline images — one CID per event
        for i, event in enumerate(events):
            if event.get("image") and event["image"].startswith("data:image"):
                image_bytes = base64.b64decode(event["image"].split(",")[1])
                img_mime = MIMEImage(image_bytes)
                img_mime.add_header('Content-ID', f'<event_image_{i}>')
                img_mime.add_header('Content-Disposition', 'inline', filename=f'memory_{i}.jpg')
                msg.attach(img_mime)

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


def _same_month_day(date_str: str, ref: date) -> bool:
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        return d.month == ref.month and d.day == ref.day
    except ValueError:
        return False


def _already_sent_this_year(row: dict, today: date) -> bool:
    lrd = row.get('last_reminder_date')
    if lrd:
        try:
            sent_date = datetime.strptime(lrd, '%Y-%m-%d').date()
            return sent_date.year == today.year
        except ValueError:
            pass

    if row.get('reminder_sent'):
        try:
            event_date = datetime.strptime(row['event_date'], '%Y-%m-%d').date()
            return event_date.year == today.year
        except ValueError:
            pass

    return False


def send_today_reminders(force: bool = False):
    try:
        sb  = init_supabase()
        today = date.today()

        res = sb.table('our_events').select('*').eq('enabled', True).execute()
        if not res.data:
            return 0

        matching = [
            r for r in res.data
            if _same_month_day(r['event_date'], today)
            and (force or not _already_sent_this_year(r, today))
        ]

        if not matching:
            return 0

        events = sorted([
            {
                'id':          r['id'],
                'title':       r['event_title'],
                'date':        datetime.strptime(r['event_date'], '%Y-%m-%d').date(),
                'preview':     r['preview_text'],
                'description': r['description'],
                'image':       r.get('image_data'),
            }
            for r in matching
        ], key=lambda e: e['date'])

        all_ok = True
        for uname, email in COUPLE_EMAILS.items():
            if not email:
                continue
            name = COUPLE_NAMES.get(uname, uname.title())
            if not _send_digest_smtp(events, email, name):
                all_ok = False

        if all_ok:
            today_str = str(today)
            for event in events:
                sb.table('our_events').update(
                    {'last_reminder_date': today_str, 'reminder_sent': True}
                ).eq('id', event['id']).execute()

        return len(events)

    except Exception as ex:
        print(f"Reminder error: {ex}")
        traceback.print_exc()
        return 0


def send_event_email_now(event, sender_username=None):
    sender_name = COUPLE_NAMES.get(sender_username, "Someone") if sender_username else "Someone"
    results = {}
    for uname, email in COUPLE_EMAILS.items():
        if not email:
            continue
        name = COUPLE_NAMES.get(uname, uname.title())
        results[name] = _send_digest_smtp([event], email, name, sender_name=sender_name)
    return results

# ─────────────────────────────────────────────────────────────────────────────
# PDF EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_memories_to_pdf(events, export_type="selected"):
    """Export memories to a beautifully formatted PDF using fpdf2."""
    try:
        from fpdf import FPDF
        import os
        import tempfile

        # Page dimensions in mm (Letter size)
        PAGE_W = 215.9
        MARGIN = 20
        CONTENT_W = PAGE_W - 2 * MARGIN

        pdf = FPDF(format='letter')
        pdf.set_auto_page_break(auto=True, margin=20)

        # ── Register fonts ──────────────────────────────────────────────
        font_registered = False
        registered_styles = set()
        font_candidates = [
            ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf',
             'C:/Windows/Fonts/ariali.ttf'),
            ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'),
            ('/usr/share/fonts/truetype/freefont/FreeSans.ttf',
             '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
             '/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf'),
            ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
             '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
             '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'),
        ]
        for regular, bold, italic in font_candidates:
            if os.path.exists(regular):
                pdf.add_font('Body', '', regular)
                registered_styles.add('')
                if os.path.exists(bold):
                    pdf.add_font('Body', 'B', bold)
                    registered_styles.add('B')
                if os.path.exists(italic):
                    pdf.add_font('Body', 'I', italic)
                    registered_styles.add('I')
                font_registered = True
                break

        emoji_font_candidates = [
            'C:/Windows/Fonts/seguiemj.ttf',
            # Symbola — monochrome outline font, works reliably with fpdf2
            '/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf',
            '/usr/share/fonts/truetype/symbola/Symbola.ttf',
            '/usr/share/fonts/truetype/Symbola.ttf',
            # NotoColorEmoji — may not work with fpdf2 (COLR/CBDT format)
            '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',
            '/usr/share/fonts/truetype/noto-color-emoji/NotoColorEmoji.ttf',
            '/usr/share/fonts/noto-color-emoji/NotoColorEmoji.ttf',
        ]
        emoji_font_name = None
        for ef in emoji_font_candidates:
            if os.path.exists(ef):
                try:
                    pdf.add_font('Emoji', '', ef)
                    emoji_font_name = 'Emoji'
                    break
                except Exception:
                    continue

        # Last resort: search system for any usable emoji/symbol font
        if not emoji_font_name:
            try:
                import subprocess
                result = subprocess.run(
                    ['fc-list', ':style=Regular', 'file'],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines():
                    path = line.strip().rstrip(':')
                    if path.endswith('.ttf') and any(
                        k in path.lower()
                        for k in ['symbola', 'emoji', 'noto']
                    ):
                        try:
                            pdf.add_font('Emoji', '', path)
                            emoji_font_name = 'Emoji'
                            break
                        except Exception:
                            continue
            except Exception:
                pass

        body_font = 'Body' if font_registered else 'Helvetica'

        # Set emoji font as fallback so multi_cell auto-switches for emoji
        if emoji_font_name:
            pdf.set_fallback_fonts([emoji_font_name])

        # Replace emojis with text equivalents when no emoji font is available
        def _safe_text(text):
            if emoji_font_name or not text:
                return text
            import re
            # Common emoji replacements
            replacements = {
                '❤️': '<3', '❤': '<3', '💕': '<3<3', '💖': '<3',
                '💗': '<3', '💘': '<3', '💝': '<3', '🥰': '<3',
                '😍': '<3', '🌸': '*', '🌷': '*', '✨': '*',
                '📅': '-', '🌹': '@>->--',
            }
            for emoji, replacement in replacements.items():
                text = text.replace(emoji, replacement)
            # Remove any remaining emoji/non-BMP characters
            text = re.sub(
                r'[\U0001F000-\U0001FFFF\u2600-\u27BF\u2700-\u27BF'
                r'\uFE00-\uFE0F\u200D\u2764\u2665\u2763'
                r'\U0001F300-\U0001F9FF\U0001FA00-\U0001FA6F]+',
                '', text
            )
            return text.strip()

        # Enable text shaping (uharfbuzz) for native Arabic RTL + ligatures.
        # Test that uharfbuzz actually works before enabling —
        # set_text_shaping(True) can succeed but HarfBuzzFont may fail later.
        text_shaping_ok = False
        try:
            import uharfbuzz as _hb
            # Verify HarfBuzzFont subclass can be created
            _test_face = _hb.Face(_hb.Blob(b'\x00' * 12), 0)
            type('_HBF', (_hb.Font,), {})(_test_face)
            pdf.set_text_shaping(True)
            text_shaping_ok = True
        except Exception:
            pass

        # Fallback: reshape Arabic manually if uharfbuzz is not available
        def _reshape_arabic_fallback(text):
            if text_shaping_ok or not ARABIC_RE.search(text):
                return text
            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                lines = text.split('\n')
                processed = []
                for line in lines:
                    if ARABIC_RE.search(line):
                        reshaped = arabic_reshaper.reshape(line)
                        processed.append(get_display(reshaped))
                    else:
                        processed.append(line)
                return '\n'.join(processed)
            except ImportError:
                return text

        # ── Helper: write a text block ──────────────────────────────────
        def write_text(text, font_size=11, bold=False, italic=False,
                       color=(58, 46, 46), align='', line_height=1.6):
            style = ''
            if bold:
                style += 'B'
            if italic:
                style += 'I'
            # Fall back to available styles if requested style not registered
            if font_registered and style not in registered_styles:
                if 'B' in style and 'B' in registered_styles:
                    style = 'B'
                elif 'I' in style and 'I' in registered_styles:
                    style = 'I'
                else:
                    style = ''

            # Auto-detect RTL for alignment
            if not align and is_arabic(text):
                align = 'R'

            # Strip unsupported emojis if no emoji font available
            text = _safe_text(text)
            # Apply Arabic reshaping fallback if text_shaping unavailable
            text = _reshape_arabic_fallback(text)

            lh = font_size * line_height * 0.352778

            pdf.set_text_color(*color)
            pdf.set_font(body_font, style, font_size)

            pdf.multi_cell(
                w=CONTENT_W, h=lh,
                text=text, align=align or 'L',
                new_x='LMARGIN', new_y='NEXT'
            )

        # ── Cover page ──────────────────────────────────────────────────
        pdf.add_page()
        pdf.ln(30)

        # Title — fallback font handles emoji automatically
        pdf.set_font(body_font, 'B', 28)
        pdf.set_text_color(58, 46, 46)
        pdf.cell(w=CONTENT_W, h=12, text=_safe_text('❤️ M & S ❤️'), align='C')
        pdf.ln(14)

        # Subtitle
        today = date.today()
        days = (today - START_DATE).days
        pdf.set_font(body_font, '', 12)
        pdf.set_text_color(138, 111, 111)
        pdf.cell(w=CONTENT_W, h=7, text='Our Beautiful Memories', align='C')
        pdf.ln(8)
        pdf.cell(w=CONTENT_W, h=7, text=f'Day {days} Together', align='C')
        pdf.ln(15)

        # Decorative line
        pdf.set_draw_color(212, 133, 122)
        pdf.set_line_width(0.5)
        center_x = PAGE_W / 2
        pdf.line(center_x - 30, pdf.get_y(), center_x + 30, pdf.get_y())
        pdf.ln(10)

        # ── Memory pages ────────────────────────────────────────────────
        for i, event in enumerate(events):
            pdf.add_page()

            formatted_date = event['date'].strftime('%B %d, %Y')

            # Event title
            write_text(event['title'], font_size=16, bold=True,
                       color=(201, 134, 107))

            # Date — centered below title
            pdf.ln(2)
            pdf.set_font(body_font, '', 10)
            pdf.set_text_color(176, 128, 112)
            pdf.cell(w=CONTENT_W, h=5, text=_safe_text(f'📅 {formatted_date}'), align='C')
            pdf.ln(8)

            # Image
            if event.get('image') and event['image'].startswith('data:image'):
                try:
                    img_data = base64.b64decode(event['image'].split(',')[1])
                    pil_img = Image.open(BytesIO(img_data))
                    img_w, img_h = pil_img.size
                    aspect = img_w / img_h

                    max_w_mm = CONTENT_W
                    max_h_mm = 100
                    if aspect > (max_w_mm / max_h_mm):
                        display_w = max_w_mm
                        display_h = max_w_mm / aspect
                    else:
                        display_h = max_h_mm
                        display_w = max_h_mm * aspect

                    # Save to temp file for fpdf2
                    tmp = tempfile.NamedTemporaryFile(
                        suffix='.png', delete=False)
                    pil_img.save(tmp, format='PNG')
                    tmp.close()

                    x = MARGIN + (CONTENT_W - display_w) / 2
                    pdf.image(tmp.name, x=x, w=display_w, h=display_h)
                    pdf.ln(5)

                    os.remove(tmp.name)
                except Exception:
                    pass

            # Preview
            if event.get('preview'):
                pdf.ln(3)
                write_text(event['preview'], font_size=11, italic=True,
                           color=(138, 111, 111))
                pdf.ln(3)

            # Decorative separator
            pdf.set_draw_color(232, 180, 173)
            pdf.set_line_width(0.3)
            pdf.line(MARGIN + 20, pdf.get_y(),
                     PAGE_W - MARGIN - 20, pdf.get_y())
            pdf.ln(5)

            # Description
            if event.get('description'):
                for line in event['description'].split('\n'):
                    if line.strip():
                        write_text(line, font_size=11, color=(58, 46, 46))
                    else:
                        pdf.ln(3)

        # Output to buffer
        buffer = BytesIO()
        pdf_bytes = pdf.output()
        buffer.write(pdf_bytes)
        buffer.seek(0)
        return buffer

    except Exception as e:
        st.error(f"PDF export error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ─────────────────────────────────────────────────────────────────────────────
# FILTERING & SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def filter_events(events, search_query="", date_from=None, date_to=None):
    """Filter events by search query and date range."""
    filtered = events
    
    # Search filter
    if search_query.strip():
        query = search_query.lower()
        filtered = [e for e in filtered if 
                   query in e['title'].lower() or 
                   query in e['preview'].lower() or
                   query in e['description'].lower()]
    
    # Date range filter
    if date_from:
        filtered = [e for e in filtered if e['date'] >= date_from]
    if date_to:
        filtered = [e for e in filtered if e['date'] <= date_to]
    
    return filtered

# ─────────────────────────────────────────────────────────────────────────────
# JAVASCRIPT & CSS
# ─────────────────────────────────────────────────────────────────────────────

def inject_js():
    """Inject JavaScript for floating petals, scroll-reveal animations, and calendar interactions."""
    st.markdown("""
<script>
(function() {
  function rescueSidebarToggle() {
    const candidates = Array.from(document.querySelectorAll('button, [role="button"]'));
    candidates.forEach((el) => {
      const label = [
        el.getAttribute('data-testid') || '',
        el.getAttribute('aria-label') || '',
        el.getAttribute('title') || '',
        el.innerText || ''
      ].join(' ').toLowerCase();

      if (!/(sidebar|navigation|nav|menu)/.test(label)) return;

      el.style.setProperty('display', 'flex', 'important');
      el.style.setProperty('visibility', 'visible', 'important');
      el.style.setProperty('opacity', '1', 'important');
      el.style.setProperty('position', 'fixed', 'important');
      el.style.setProperty('top', '0.75rem', 'important');
      el.style.setProperty('left', '0.75rem', 'important');
      el.style.setProperty('z-index', '1001', 'important');
      el.style.setProperty('pointer-events', 'auto', 'important');
    });
  }

  function createPetals() {
    if (document.getElementById('petal-canvas')) return;
    const canvas = document.createElement('canvas');
    canvas.id = 'petal-canvas';
    canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;opacity:0.55;';
    document.body.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    let W = canvas.width  = window.innerWidth;
    let H = canvas.height = window.innerHeight;
    window.addEventListener('resize', () => { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; });

    const emojis = ['🌸','❤️','✨','🌷','💕'];
    const petals = Array.from({length: 18}, () => ({
      x: Math.random() * W,
      y: Math.random() * H - H,
      size: 10 + Math.random() * 14,
      speed: 0.4 + Math.random() * 0.7,
      drift: (Math.random() - 0.5) * 0.6,
      rot: Math.random() * Math.PI * 2,
      rotSpeed: (Math.random() - 0.5) * 0.03,
      emoji: emojis[Math.floor(Math.random() * emojis.length)],
      opacity: 0.3 + Math.random() * 0.5,
    }));

    function draw() {
      ctx.clearRect(0, 0, W, H);
      petals.forEach(p => {
        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.font = p.size + 'px serif';
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillText(p.emoji, -p.size/2, p.size/2);
        ctx.restore();
        p.y += p.speed;
        p.x += p.drift + Math.sin(p.y * 0.012) * 0.4;
        p.rot += p.rotSpeed;
        if (p.y > H + 30) { p.y = -30; p.x = Math.random() * W; }
      });
      requestAnimationFrame(draw);
    }
    draw();
  }

  function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.style.opacity = '1';
          e.target.style.transform = 'translateY(0)';
        }
      });
    }, { threshold: 0.08 });

    document.querySelectorAll('.event-card, .gallery-item').forEach(el => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(28px)';
      el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      observer.observe(el);
    });
  }

  function init() {
    createPetals();
    initScrollReveal();
    rescueSidebarToggle();
    const mo = new MutationObserver(() => {
      initScrollReveal();
      rescueSidebarToggle();
    });
    const target = document.querySelector('.main') || document.body;
    mo.observe(target, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    setTimeout(init, 200);
  }
})();
</script>
""", unsafe_allow_html=True)


def inject_css():
    st.markdown("""
<style>

/* ───────────────── STREAMLIT CLEANUP ───────────────── */

#MainMenu,
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stSidebarNav"] {
    display: none !important;
    visibility: hidden !important;
}

/* Keep Streamlit header mounted so the mobile sidebar toggle still works. */
header,
[data-testid="stHeader"] {
    background: transparent !important;
    box-shadow: none !important;
}

button[kind="header"]:not([data-testid="collapsedControl"]):not([aria-label*="sidebar" i]):not([title*="sidebar" i]):not([aria-label*="navigation" i]):not([title*="navigation" i]):not([aria-label*="menu" i]):not([title*="menu" i]) {
    display: none !important;
    visibility: hidden !important;
}

/* Sidebar is visible — styled below */

.stApp {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

.block-container {
    padding-top: 0rem !important;
}

@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400;1,600&family=Lato:wght@300;400;700&family=Cairo:wght@300;400;600&display=swap');

:root {
  --cream:    #fdf8f3;
  --warm:     #f5ede3;
  --rose:     #d4857a;
  --rose-deep:#b8625a;
  --blush:    #e8b4ad;
  --gold:     #c9866b;
  --text:     #3a2e2e;
  --muted:    #8a6f6f;
  --border:   #e8d8d0;
  --card-bg:  #fffaf7;
  --sidebar:  #fef3ec;
}

/* ─── KEYFRAMES ─────────────────────────────────────── */
@keyframes heartbeat {
  0%,100% { transform: scale(1); }
  14%     { transform: scale(1.18); }
  28%     { transform: scale(1); }
  42%     { transform: scale(1.12); }
  70%     { transform: scale(1); }
}
@keyframes fadeSlideUp {
  from { opacity:0; transform:translateY(30px); }
  to   { opacity:1; transform:translateY(0); }
}
@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
@keyframes pulseGlow {
  0%,100% { box-shadow: 0 4px 20px rgba(212,133,122,0.25); }
  50%     { box-shadow: 0 6px 36px rgba(212,133,122,0.55), 0 0 0 6px rgba(212,133,122,0.08); }
}
@keyframes float {
  0%,100% { transform: translateY(0px); }
  50%     { transform: translateY(-7px); }
}
@keyframes rotateSlow {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
@keyframes glowBorder {
  0%,100% { border-color: var(--blush); }
  50%     { border-color: var(--rose); box-shadow: 0 0 18px rgba(212,133,122,0.3); }
}
@keyframes counterPop {
  0%   { transform: scale(0.85); opacity:0; }
  60%  { transform: scale(1.08); }
  100% { transform: scale(1);    opacity:1; }
}
@keyframes twinkle {
  0%,100% { opacity:0.2; transform:scale(0.8); }
  50%     { opacity:1;   transform:scale(1.2); }
}

/* Reset & base */
.main .block-container { padding-top:1.5rem; padding-bottom:3rem; max-width:900px; }
html, body, [class*="css"] { font-family: 'Lato', 'Cairo', sans-serif; }

/* Noise grain overlay */
.main::before {
  content:"";
  position:fixed;
  inset:0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  pointer-events:none;
  z-index:9999;
  opacity:0.4;
}

/* Page background — subtle warm radial gradient */
.stApp {
  background:
    radial-gradient(ellipse at 20% 10%, rgba(232,180,173,0.18) 0%, transparent 55%),
    radial-gradient(ellipse at 80% 90%, rgba(201,134,107,0.12) 0%, transparent 55%),
    var(--cream);
}

/* ─── SIDEBAR ───────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #fff5f0 0%, var(--sidebar) 100%) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding-top: 1rem !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* Sidebar collapse/expand toggle button styling */
[data-testid="collapsedControl"],
button[kind="header"][aria-label*="sidebar" i],
button[kind="header"][title*="sidebar" i],
button[kind="header"][aria-label*="navigation" i],
button[kind="header"][title*="navigation" i],
button[kind="header"][aria-label*="menu" i],
button[kind="header"][title*="menu" i] {
  color: var(--rose) !important;
  display: flex !important;
  visibility: visible !important;
  position: fixed !important;
  top: 0.75rem !important;
  left: 0.75rem !important;
  z-index: 1001 !important;
}
[data-testid="collapsedControl"] svg,
button[kind="header"][aria-label*="sidebar" i] svg,
button[kind="header"][title*="sidebar" i] svg,
button[kind="header"][aria-label*="navigation" i] svg,
button[kind="header"][title*="navigation" i] svg,
button[kind="header"][aria-label*="menu" i] svg,
button[kind="header"][title*="menu" i] svg {
  stroke: var(--rose) !important;
}

/* Mobile sidebar */
@media (max-width: 768px) {
  [data-testid="stSidebar"] {
    z-index: 999 !important;
  }
  [data-testid="collapsedControl"] {
    display: block !important;
  }
  .main .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
}

.sidebar-logo {
  text-align:center;
  padding: 1.8rem 1rem 1rem;
  position:relative;
}
.sidebar-logo::after {
  content:"";
  display:block;
  width:60%;
  height:1px;
  background: linear-gradient(90deg, transparent, var(--blush), transparent);
  margin:.8rem auto 0;
}
.sidebar-logo .logo-heart {
  font-size: 2.8rem;
  line-height: 1;
  display:block;
  margin-bottom:.5rem;
  animation: heartbeat 2.8s ease-in-out infinite;
  filter: drop-shadow(0 2px 8px rgba(212,133,122,0.4));
}
.sidebar-logo h2 {
  font-family: 'Playfair Display', serif;
  font-size: 1.7rem;
  font-weight: 700;
  color: var(--rose) !important;
  margin:0;
  letter-spacing:.5px;
  text-shadow: 0 2px 12px rgba(212,133,122,0.2);
}
.sidebar-logo .tagline {
  font-size:.75rem;
  color: var(--muted) !important;
  letter-spacing:2px;
  text-transform:uppercase;
  margin-top:.3rem;
}

.days-counter {
  background: linear-gradient(135deg, #d4857a 0%, #c9866b 50%, #e8a598 100%);
  background-size: 200% 100%;
  border-radius: 16px;
  padding: 1.1rem 1.2rem;
  text-align: center;
  margin: .8rem 1rem;
  animation: pulseGlow 3.5s ease-in-out infinite;
  position:relative;
  overflow:hidden;
}
.days-counter::before {
  content:"";
  position:absolute;
  inset:0;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%);
  background-size:400px 100%;
  animation: shimmer 3s infinite linear;
}
.days-counter .days-num {
  font-family: 'Playfair Display', serif;
  font-size: 2.6rem;
  font-weight: 700;
  color: #fff;
  line-height: 1;
  display:block;
  text-shadow: 0 2px 10px rgba(0,0,0,0.15);
  position:relative;
}
.days-counter .days-label {
  font-size:.76rem;
  color:rgba(255,255,255,.9);
  letter-spacing:1.2px;
  text-transform:uppercase;
  display:block;
  margin-top:.35rem;
  position:relative;
}

.user-pill {
  margin:.5rem 1rem;
  background: rgba(255,255,255,0.8);
  border: 1px solid var(--border);
  border-radius: 30px;
  padding: .5rem 1rem;
  text-align:center;
  font-size:.85rem;
  color: var(--muted) !important;
  backdrop-filter: blur(8px);
  transition: border-color .3s, box-shadow .3s;
}
.user-pill:hover {
  border-color: var(--blush);
  box-shadow: 0 2px 12px rgba(212,133,122,0.15);
}
.user-pill strong { color: var(--rose) !important; }

/* ─── MAIN HEADER ───────────────────────────────────── */
.page-hero {
  text-align: center;
  padding: 2.8rem 1rem 2rem;
  position: relative;
  animation: fadeSlideUp 0.7s ease both;
}
.page-hero::before {
  content:"✨";
  position:absolute;
  top:1rem; left:18%;
  font-size:1.1rem;
  animation: twinkle 2.4s ease-in-out infinite;
  animation-delay:0s;
}
.page-hero::after {
  content:"";
  display:block;
  width:100px;
  height:2px;
  background: linear-gradient(90deg, transparent, var(--rose), transparent);
  margin:1.1rem auto 0;
}
.page-hero h1 {
  font-family: 'Playfair Display', serif;
  font-size: clamp(2.2rem, 5vw, 3.2rem);
  font-weight: 700;
  color: var(--text);
  margin: 0;
  letter-spacing:-.5px;
  line-height:1.15;
}
.page-hero h1 em {
  color: var(--rose);
  font-style: italic;
  background: linear-gradient(135deg, var(--rose), var(--gold));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.page-hero p {
  color: var(--muted);
  font-size: 1rem;
  margin-top:.6rem;
  letter-spacing:.5px;
}

.hero-deco {
  position:absolute;
  pointer-events:none;
  font-size:1.4rem;
  animation: float 4s ease-in-out infinite;
}

/* ─── EVENT CARDS ───────────────────────────────────── */
.event-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  overflow:hidden;
  margin-bottom: 1.2rem;
  transition: transform .28s cubic-bezier(.34,1.56,.64,1), box-shadow .28s ease, border-color .28s ease;
  display:flex;
  flex-direction:row;
  align-items:stretch;
  position:relative;
}
.event-card::before {
  content:"";
  position:absolute;
  left:0; top:0; bottom:0;
  width:3px;
  background: linear-gradient(180deg, var(--rose), var(--gold));
  opacity:0;
  transition: opacity .25s;
  border-radius:3px 0 0 3px;
}
.event-card:hover {
  transform: translateY(-4px);
  border-color: var(--blush);
  box-shadow: 0 12px 32px rgba(212,133,122,0.2);
}
.event-card:hover::before {
  opacity:1;
}
.event-card-thumb {
  width:200px;
  min-width:200px;
  height:180px;
  background:#f0e8e0;
  display:flex;
  align-items:center;
  justify-content:center;
  overflow:hidden;
  position:relative;
}
.event-card-thumb img {
  width:100%;
  height:100%;
  object-fit:cover;
}
.thumb-placeholder {
  font-size:3.5rem;
  opacity:0.4;
}
.event-card-body {
  flex:1;
  padding:1.3rem;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
}
.card-title {
  font-family:'Playfair Display',serif;
  font-size:1.25rem;
  font-weight:600;
  color:var(--text);
  margin-bottom:.4rem;
  line-height:1.3;
}
.card-date {
  font-size:.85rem;
  color:var(--muted);
  margin-bottom:.8rem;
  letter-spacing:.3px;
}
.card-preview {
  color:var(--text);
  font-size:.95rem;
  line-height:1.55;
  opacity:0.9;
  flex:1;
}

/* ─── GALLERY VIEW ───────────────────────────────────── */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.2rem;
  margin: 2rem 0;
}

.gallery-item {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  background: var(--card-bg);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: transform .28s cubic-bezier(.34,1.56,.64,1), box-shadow .28s ease;
  aspect-ratio: 1;
}

.gallery-item:hover {
  transform: translateY(-6px) scale(1.02);
  box-shadow: 0 12px 32px rgba(212,133,122,0.25);
  border-color: var(--blush);
}

.gallery-item-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gallery-item-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
  background: linear-gradient(135deg, #fdf0ea 0%, #fffaf7 100%);
  opacity: 0.6;
}

.gallery-item-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 0%, rgba(58,46,46,0.6) 100%);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 1rem;
  opacity: 0;
  transition: opacity .28s;
}

.gallery-item:hover .gallery-item-overlay {
  opacity: 1;
}

.gallery-item-title {
  color: white;
  font-weight: 600;
  font-size: 0.9rem;
  line-height: 1.2;
}

/* ─── CALENDAR ───────────────────────────────────── */
.calendar-container {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.5rem;
  margin: 1.5rem 0;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.calendar-header h3 {
  font-family: 'Playfair Display', serif;
  color: var(--text);
  margin: 0;
  font-size: 1.3rem;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.3rem;
}

.calendar-day-header {
  text-align: center;
  font-weight: 600;
  font-size: 0.75rem;
  color: var(--muted);
  padding: 0.5rem 0;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.calendar-day {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all .2s;
  background: white;
  color: var(--text);
}

.calendar-day.empty {
  background: transparent;
  cursor: default;
}

.calendar-day.has-event {
  background: linear-gradient(135deg, #d4857a 0%, #c9866b 100%);
  color: white;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(212,133,122,0.3);
  position: relative;
  overflow: hidden;
}

.calendar-day.has-event-img {
  background-size: cover !important;
  background-position: center !important;
  background-repeat: no-repeat !important;
}

.cal-img-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(160deg, rgba(180,80,70,0.45) 0%, rgba(80,30,20,0.55) 100%);
  border-radius: inherit;
  pointer-events: none;
}

.cal-day-num {
  position: relative;
  z-index: 1;
  font-weight: 700;
  text-shadow: 0 1px 4px rgba(0,0,0,0.5);
  font-size: 0.9rem;
}

.calendar-day.has-event:not(.has-event-img) .cal-day-num {
  text-shadow: none;
}

.calendar-day.has-event:hover {
  box-shadow: 0 6px 16px rgba(212,133,122,0.5);
  transform: scale(1.08);
}

.calendar-day:not(.empty):not(.has-event):hover {
  border-color: var(--blush);
  background: #fef3ec;
}

.cal-badge {
  position: absolute;
  top: 3px;
  right: 3px;
  background: #fff;
  color: var(--rose-deep);
  font-size: 0.6rem;
  font-weight: 700;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  z-index: 2;
}

/* ───── CALENDAR CLICKABLE INTERACTION ───── */
.calendar-day-clickable {
  cursor: pointer !important;
  position: relative;
  transition: transform .2s cubic-bezier(.34,1.56,.64,1),
              box-shadow .2s ease !important;
}

.calendar-day-clickable:hover {
  transform: scale(1.08) !important;
  box-shadow: 0 6px 16px rgba(212,133,122,0.5) !important;
}

.calendar-day-clickable:active {
  transform: scale(0.96) !important;
}

/* ─── SEARCH & FILTER BOX ───────────────────────────────── */
.search-filter-box {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.filter-label {
  font-weight: 600;
  color: var(--text);
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ─── BUTTONS ───────────────────────────────── */
.stButton button[kind="primary"] {
  background: linear-gradient(135deg, #d4857a 0%, #c9866b 100%) !important;
  color: white !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: transform .2s, box-shadow .2s, background .2s !important;
  box-shadow: 0 4px 15px rgba(212,133,122,0.3) !important;
}
.stButton button[kind="primary"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 24px rgba(212,133,122,0.4) !important;
}
.stButton button[kind="primary"]:active {
  transform: translateY(0) !important;
}

.stButton button[kind="secondary"] {
  background: transparent !important;
  color: var(--rose) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: border-color .2s, background .2s, box-shadow .2s !important;
}
.stButton button[kind="secondary"]:hover {
  background:var(--warm) !important;
  border-color:var(--rose) !important;
  transform:translateY(-2px) !important;
  box-shadow: 0 6px 18px rgba(212,133,122,0.18) !important;
}

/* Inputs — warm focus glow */
.stTextInput input, .stTextArea textarea, .stDateInput input, .stSelectbox select {
  border-radius: 12px !important;
  border: 1.5px solid var(--border) !important;
  background: #fffbf8 !important;
  font-family: 'Lato', sans-serif !important;
  color: var(--text) !important;
  transition: border-color .2s, box-shadow .2s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stDateInput input:focus, .stSelectbox select:focus {
  border-color: var(--rose) !important;
  box-shadow: 0 0 0 3px rgba(212,133,122,0.15) !important;
  outline:none !important;
}

/* ─── SECTION DIVIDER ───────────────────────────────── */
.section-divider {
  text-align:center;
  margin:2rem 0 1.5rem;
  position:relative;
}
.section-divider::before {
  content:"";
  position:absolute;
  top:50%;
  left:0; right:0;
  height:1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
}
.section-divider span {
  background:var(--cream);
  padding:0 1rem;
  position:relative;
  font-size:.73rem;
  letter-spacing:2.5px;
  text-transform:uppercase;
  color:var(--muted);
}

/* ─── EMAIL SEND BOX ────────────────────────────────── */
.email-box {
  background: linear-gradient(135deg, #fff5f3 0%, #fdf0ea 100%);
  border: 1px solid var(--blush);
  border-radius:16px;
  padding:1rem 1.3rem;
  margin-top:1rem;
  display:flex;
  align-items:center;
  gap:.9rem;
  font-size:.88rem;
  color:var(--muted);
  transition: box-shadow .3s;
}
.email-box:hover {
  box-shadow: 0 4px 20px rgba(232,180,173,0.25);
}
.email-box .email-icon {
  font-size:1.5rem;
  flex-shrink:0;
  animation: float 3.5s ease-in-out infinite;
}

/* Pagination */
.pagination-row {
  display:flex;
  align-items:center;
  justify-content:center;
  gap:1rem;
  margin:1rem 0;
  font-size:.88rem;
  color:var(--muted);
}

/* Scrollbar */
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background: var(--cream); }
::-webkit-scrollbar-thumb {
  background: var(--blush);
  border-radius:10px;
}
::-webkit-scrollbar-thumb:hover { background: var(--rose); }

/* Selection */
::selection {
  background: rgba(212,133,122,0.2);
  color: var(--rose-deep);
}

/* ─── DETAIL VIEW ───────────────────────────────────── */
.detail-hero {
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 1rem;
  position: relative;
  height: 300px;
}
.detail-hero-img, .detail-hero-img-placeholder {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
}
.detail-hero-img-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fdf0ea 0%, #fffaf7 100%);
  font-size: 4rem;
  opacity: 0.5;
}
.detail-meta {
  background: var(--warm);
  padding: 1.5rem;
  border-radius: 12px;
  margin-bottom: 1rem;
}
.detail-title {
  font-family: 'Playfair Display', serif;
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.5rem;
}
.detail-date {
  font-size: 0.9rem;
  color: var(--muted);
  margin-bottom: 0.8rem;
}
.detail-preview {
  font-style: italic;
  color: var(--text);
  font-size: 1rem;
  line-height: 1.6;
}
.detail-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
  margin: 1.5rem 0;
}
.detail-body {
  color: var(--text);
  font-size: 1rem;
  line-height: 1.8;
  padding: 0 0.5rem;
}
.arabic {
  direction: rtl;
  text-align: right;
}
.card-title.arabic, .card-preview.arabic {
  direction: rtl;
  text-align: right;
}
.detail-title.arabic, .detail-preview.arabic {
  direction: rtl;
  text-align: right;
}

/* ─── LOGIN CARD ───────────────────────────────────── */
.login-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 3rem 2rem;
  box-shadow: 0 20px 60px rgba(0,0,0,0.08);
}
.login-hearts {
  font-size: 3.5rem;
  margin-bottom: 1rem;
  animation: heartbeat 2.8s ease-in-out infinite;
  filter: drop-shadow(0 2px 12px rgba(212,133,122,0.3));
}
.login-card h1 {
  font-family: 'Playfair Display', serif;
  font-size: 2.8rem;
  color: var(--text);
  margin: 0.8rem 0 0.3rem;
  font-weight: 700;
}
.login-card .subtitle {
  color: var(--muted);
  font-size: 1rem;
  margin-bottom: 1.5rem;
}
.counter-display {
  background: linear-gradient(135deg, #e8a598 0%, #c9866b 100%);
  border-radius: 16px;
  padding: 1.5rem;
  text-align: center;
  margin: 1.5rem 0;
  color: white;
}
.big-num {
  display: block;
  font-family: 'Playfair Display', serif;
  font-size: 3.2rem;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 0.5rem;
}
.small-text {
  display: block;
  font-size: 0.9rem;
  opacity: 0.95;
  letter-spacing: 0.5px;
}

/* ─── MOBILE SIDEBAR MENU ──────────────────────────────── */
/* Using Streamlit buttons - no custom HTML CSS needed */

@media (max-width:600px) {
  .event-card { flex-direction:column; }
  .event-card-thumb { width:100%; min-width:100%; height:170px; }
  .detail-body { padding:0 1rem 1.5rem; }
  .detail-meta { padding:1.2rem 1rem; }
  .login-card { padding:2rem 1.5rem; }
  .gallery-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.8rem; }
  .calendar-grid { gap: 0.2rem; }
  .detail-hero { height: 200px; }
  .filter-label { font-size: 0.8rem; }
  .search-filter-box { padding: 1rem; }
  
  .main .block-container { padding-top: 1rem; max-width: 100%; }
}
</style>
""", unsafe_allow_html=True)
    inject_js()

# ─────────────────────────────────────────────────────────────────────────────
# ARABIC DETECTION
# ─────────────────────────────────────────────────────────────────────────────

ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

def is_arabic(text):
    return bool(ARABIC_RE.search(text))

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def init_session():
    defaults = {
        'authenticated': False,
        'user': None,
        'selected_event': None,
        'selected_event_id': None,  # ID-based selection (used by calendar)
        'show_add_form': False,
        'edit_event_id': None,
        'event_page': 0,
        'counter_animated': False,
        'view_mode': 'timeline',  # 'timeline' or 'gallery'
        'search_query': '',
        'filter_date_from': None,
        'filter_date_to': None,
        'show_filters': False,
        'calendar_month': None,
        'cal_picker_day': None,  # day number when multi-event popup is open
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

def login_page():
    today = date.today()
    days = (today - START_DATE).days

    inject_css()

    # Hide sidebar on login page
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<div class="login-hearts">❤️</div>', unsafe_allow_html=True)
        st.markdown('<h1>M & S</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">A private journal for two</p>', unsafe_allow_html=True)

        placeholder = st.empty()
        placeholder.markdown(f"""
        <div class="counter-display">
            <span class="big-num">{days}</span>
            <span class="small-text">days of knowing each other 🌸</span>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("", placeholder="Username")
            password = st.text_input("", type="password", placeholder="Password")
            submitted = st.form_submit_button("Enter our world →", type="primary", use_container_width=True)
            if submitted:
                if username and password:
                    with st.spinner(""):
                        ok, user = authenticate_user(username, password)
                        if ok:
                            st.session_state.authenticated = True
                            st.session_state.user = user
                            st.session_state.counter_animated = False
                            st.rerun()
                        else:
                            st.error("Hmm, those credentials don't match. Try again?")
                else:
                    st.error("Please fill in both fields.")

        st.markdown('</div>', unsafe_allow_html=True)



def display_sidebar():
    today = date.today()
    days = (today - START_DATE).days
    username = st.session_state.user.get('username', '').lower()
    display_name = COUPLE_NAMES.get(username, username.title())

    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-logo">
            <span class="logo-heart">❤️</span>
            <h2>M & S</h2>
            <div class="tagline">Mohammad & Shahed</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="days-counter">
            <span class="days-num">{days}</span>
            <span class="days-label">days of us 🌸</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="user-pill">
            Welcome back, <strong>{display_name}</strong> ✨
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        if st.button("➕  Add Memory", type="primary", use_container_width=True, key="sidebar_add_memory"):
            st.session_state.show_add_form = True
            st.session_state.selected_event = None
            st.session_state.edit_event_id = None
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # View mode toggle
        st.markdown("**📋 View Mode**")
        view_col1, view_col2 = st.columns(2)
        with view_col1:
            if st.button("📅 Timeline", 
                        type="primary" if st.session_state.view_mode == 'timeline' else "secondary",
                        use_container_width=True, key="sidebar_timeline"):
                st.session_state.view_mode = 'timeline'
                st.rerun()
        with view_col2:
            if st.button("🖼️ Gallery", 
                        type="primary" if st.session_state.view_mode == 'gallery' else "secondary",
                        use_container_width=True, key="sidebar_gallery"):
                st.session_state.view_mode = 'gallery'
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Daily reminder
        st.markdown("**📬 Today's Memories**")
        st.caption("Send all memories from this day (any year) to both of you.")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Send", use_container_width=True, type="primary", key="sidebar_send"):
                with st.spinner("Sending..."):
                    n = send_today_reminders(force=False)
                    if n:
                        st.success(f"✉️ {n} memory/memories sent!")
                    else:
                        st.info("Already sent today — use Resend to send again.")
        with col_b:
            if st.button("Resend", use_container_width=True, key="sidebar_resend"):
                with st.spinner("Resending..."):
                    n = send_today_reminders(force=True)
                    if n:
                        st.success(f"✉️ Resent {n} memory/memories!")
                    else:
                        st.info("No memories found for today's date.")

        st.markdown("---")

        if st.button("🚪  Sign out", use_container_width=True, key="sidebar_logout"):
            logout()


def display_search_filter():
    """Display search and filter controls."""
    st.markdown('<div class="search-filter-box">', unsafe_allow_html=True)
    
    st.markdown("**🔍 Search & Filter**")
    
    # Search input
    search_col = st.columns([1])[0]
    with search_col:
        st.session_state.search_query = st.text_input(
            "Search memories",
            value=st.session_state.search_query,
            placeholder="Search by title, preview, or description...",
            label_visibility="collapsed"
        )
    
    # Toggle filters
    if st.button("⚙️ " + ("Hide" if st.session_state.show_filters else "Show") + " Filters"):
        st.session_state.show_filters = not st.session_state.show_filters
        st.rerun()
    
    # Advanced filters
    if st.session_state.show_filters:
        st.markdown("**Date Range**")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.filter_date_from = st.date_input(
                "From",
                value=st.session_state.filter_date_from,
                label_visibility="collapsed"
            )
        with col2:
            st.session_state.filter_date_to = st.date_input(
                "To",
                value=st.session_state.filter_date_to,
                label_visibility="collapsed"
            )
        
        # Clear filters button
        if st.button("Clear Filters"):
            st.session_state.search_query = ""
            st.session_state.filter_date_from = None
            st.session_state.filter_date_to = None
            st.session_state.show_filters = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)


def display_event_card(event, index, global_index):
    """Render one event card with view/edit buttons."""
    formatted_date = event['date'].strftime('%B %d, %Y')
    tid = event['id']

    thumb_html = ""
    if event.get('image'):
        thumb_html = f'<img src="{event["image"]}" />'
    else:
        thumb_html = '<div class="thumb-placeholder">🌸</div>'

    card_title_cls = "arabic" if is_arabic(event['title']) else ""
    card_preview_cls = "arabic" if is_arabic(event['preview']) else ""
    st.markdown(f"""
    <div class="event-card">
        <div class="event-card-thumb">{thumb_html}</div>
        <div class="event-card-body">
            <div class="card-title {card_title_cls}">{event['title']}</div>
            <div class="card-date">📅 {formatted_date}</div>
            <div class="card-preview {card_preview_cls}">{event['preview']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Read →", key=f"view_{tid}_{global_index}", type="primary", use_container_width=True):
            st.session_state.selected_event = global_index
            st.session_state.edit_event_id = None
            st.rerun()
    with c2:
        if st.button("Edit", key=f"edit_{tid}_{global_index}", type="secondary", use_container_width=True):
            st.session_state.selected_event = global_index
            st.session_state.edit_event_id = tid
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)


def display_gallery_view(events):
    """Display events in a responsive gallery grid."""
    if not events:
        st.info("No memories to display.")
        return
    
    cols = st.columns(3)
    for idx, event in enumerate(events):
        col = cols[idx % 3]
        with col:
            formatted_date = event['date'].strftime('%b %d, %Y')
            
            # Create clickable gallery item
            if event.get('image'):
                st.markdown(f"""
                <div class="gallery-item" onclick="document.getElementById('gallery-click-{event['id']}').click()">
                    <img class="gallery-item-image" src="{event['image']}" alt="{event['title']}">
                    <div class="gallery-item-overlay">
                        <div class="gallery-item-title">{event['title']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="gallery-item" onclick="document.getElementById('gallery-click-{event['id']}').click()">
                    <div class="gallery-item-placeholder">🌸</div>
                    <div class="gallery-item-overlay">
                        <div class="gallery-item-title">{event['title']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Hidden button to handle click
            if st.button("View", key=f"gallery_{event['id']}", use_container_width=True):
                # Find the index of this event in the original list
                all_events = load_events_from_db(st.session_state.user['username'])
                filtered_events = filter_events(all_events, 
                                               st.session_state.search_query,
                                               st.session_state.filter_date_from,
                                               st.session_state.filter_date_to)
                try:
                    event_index = filtered_events.index(event)
                    st.session_state.selected_event = event_index
                    st.session_state.edit_event_id = None
                    st.rerun()
                except ValueError:
                    pass


@st.dialog("Choose a Memory")
def _show_event_picker_dialog(day_num, evs, month_num):
    """Popup dialog to pick from multiple events on the same day."""
    month_name_short = calendar.month_abbr[month_num]
    st.markdown(
        f"<p style='color:var(--muted);font-size:0.9rem;margin-bottom:0.5rem;'>"
        f"You have <strong>{len(evs)}</strong> memories on "
        f"<strong>{month_name_short} {day_num}</strong></p>",
        unsafe_allow_html=True
    )
    for ev in evs:
        yr = ev['date'].strftime('%Y')
        col_img, col_btn = st.columns([0.12, 1])
        with col_img:
            if ev.get('image'):
                st.markdown(
                    f"<img src='{ev['image']}' style='width:42px;height:42px;"
                    f"border-radius:8px;object-fit:cover;margin-top:4px;'>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "<div style='width:42px;height:42px;border-radius:8px;"
                    "background:linear-gradient(135deg,#d4857a,#c9866b);"
                    "display:flex;align-items:center;justify-content:center;"
                    "color:#fff;font-size:1.2rem;margin-top:4px;'>🌸</div>",
                    unsafe_allow_html=True
                )
        with col_btn:
            if st.button(
                f"{ev['title']}  ·  {yr}",
                key=f"cal_pick_{ev['id']}",
                use_container_width=True,
            ):
                st.session_state.selected_event_id = ev['id']
                st.session_state.selected_event = None
                st.session_state.edit_event_id = None
                st.session_state.cal_picker_day = None
                st.rerun()


def display_calendar_view(events):
    """Birthday-style calendar: matches events by month+day across all years."""
    if not events:
        st.info("No memories to display.")
        return

    # Initialize calendar month if not set (no year needed — birthday style)
    if st.session_state.calendar_month is None:
        st.session_state.calendar_month = date.today().month

    # Month navigation (no year — cycles through 12 months)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Prev", key="cal_prev"):
            st.session_state.calendar_month -= 1
            if st.session_state.calendar_month < 1:
                st.session_state.calendar_month = 12
            st.session_state.cal_picker_day = None
            st.rerun()
    with col2:
        month_name = calendar.month_name[st.session_state.calendar_month]
        st.markdown(
            f"<div style='text-align:center;font-size:1.1rem;color:var(--text);'>"
            f"<strong>{month_name}</strong></div>",
            unsafe_allow_html=True
        )
    with col3:
        if st.button("Next →", key="cal_next"):
            st.session_state.calendar_month += 1
            if st.session_state.calendar_month > 12:
                st.session_state.calendar_month = 1
            st.session_state.cal_picker_day = None
            st.rerun()

    # Build day -> list of events for the current month (across ALL years)
    day_events = {}  # day_num -> [ev, ev, ...]
    for ev in events:
        if ev['date'].month == st.session_state.calendar_month:
            day = ev['date'].day
            if day not in day_events:
                day_events[day] = []
            day_events[day].append(ev)

    # Sort each day's events by date descending (latest first)
    for day in day_events:
        day_events[day].sort(key=lambda e: e['date'], reverse=True)

    # Use current year for the calendar grid layout
    display_year = date.today().year
    cal = calendar.monthcalendar(display_year, st.session_state.calendar_month)

    # Build HTML calendar grid
    today = date.today()
    calendar_html = '<div class="calendar-grid">'

    for day_name in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
        calendar_html += f'<div class="calendar-day-header">{day_name}</div>'

    for week in cal:
        for day in week:
            if day == 0:
                calendar_html += '<div class="calendar-day empty"></div>'
            elif day in day_events:
                evs = day_events[day]
                latest = evs[0]  # latest event (for display)
                safe_title = latest['title'].replace('"', '&quot;')
                is_today = (day == today.day
                            and st.session_state.calendar_month == today.month)
                today_cls = ' is-today' if is_today else ''
                count = len(evs)
                badge = f'<span class="cal-badge">{count}</span>' if count > 1 else ''
                if latest.get('image'):
                    img = latest['image']
                    calendar_html += (
                        f'<div class="calendar-day has-event has-event-img calendar-day-clickable{today_cls}" '
                        f'data-cal-day="{day}" '
                        f'style="background-image:url(\'{img}\');" '
                        f'title="{safe_title}">'
                        f'<div class="cal-img-overlay"></div>'
                        f'<span class="cal-day-num">{day}</span>'
                        f'{badge}'
                        f'</div>'
                    )
                else:
                    calendar_html += (
                        f'<div class="calendar-day has-event calendar-day-clickable{today_cls}" '
                        f'data-cal-day="{day}" '
                        f'title="{safe_title}">'
                        f'<span class="cal-day-num">{day}</span>'
                        f'{badge}'
                        f'</div>'
                    )
            else:
                is_today = (day == today.day
                            and st.session_state.calendar_month == today.month)
                today_cls = ' is-today' if is_today else ''
                calendar_html += f'<div class="calendar-day{today_cls}">{day}</div>'

    calendar_html += '</div>'
    st.markdown(calendar_html, unsafe_allow_html=True)

    # Hidden buttons: one per day that has events.
    # Single-event days go straight to that event.
    # Multi-event days open a picker popup.
    has_buttons = False
    cal_btn_container = st.container()
    with cal_btn_container:
        for day_num in sorted(day_events.keys()):
            has_buttons = True
            evs = day_events[day_num]
            if len(evs) == 1:
                # Single event — direct open
                if st.button(f"_cal_day_{day_num}", key=f"cal_hd_{day_num}"):
                    st.session_state.selected_event_id = evs[0]['id']
                    st.session_state.selected_event = None
                    st.session_state.edit_event_id = None
                    st.session_state.cal_picker_day = None
                    st.rerun()
            else:
                # Multiple events — open picker
                if st.button(f"_cal_day_{day_num}", key=f"cal_hd_{day_num}"):
                    st.session_state.cal_picker_day = day_num
                    st.rerun()

    if has_buttons:
        import streamlit.components.v1 as components
        components.html("""
        <script>
        (function() {
          var doc = window.parent.document;

          function hideCalButtons() {
            doc.querySelectorAll('button').forEach(function(btn) {
              if (btn.textContent.trim().indexOf('_cal_day_') === 0) {
                btn.style.position = 'absolute';
                btn.style.left = '-9999px';
                btn.style.height = '0';
                btn.style.overflow = 'hidden';
                btn.style.opacity = '0';
                btn.style.pointerEvents = 'none';
              }
            });
          }

          function wireClicks() {
            doc.querySelectorAll('[data-cal-day]').forEach(function(cell) {
              if (cell._calWired) return;
              cell._calWired = true;
              cell.style.cursor = 'pointer';
              cell.addEventListener('click', function() {
                var dayNum = cell.getAttribute('data-cal-day');
                var buttons = doc.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                  if (buttons[i].textContent.trim() === '_cal_day_' + dayNum) {
                    buttons[i].click();
                    return;
                  }
                }
              });
            });
          }

          function init() {
            hideCalButtons();
            wireClicks();
          }

          init();
          new MutationObserver(init).observe(doc.body, {childList:true, subtree:true});
        })();
        </script>
        """, height=0)

    # Show multi-event picker dialog if a multi-event day was clicked
    if st.session_state.cal_picker_day is not None:
        picker_day = st.session_state.cal_picker_day
        if picker_day in day_events:
            _show_event_picker_dialog(
                picker_day,
                day_events[picker_day],
                st.session_state.calendar_month,
            )


def display_event_detail(event):
    """Render full event detail view."""
    title_cls = "arabic" if is_arabic(event["title"]) else ""
    preview_cls = "arabic" if is_arabic(event["preview"]) else ""
    body_cls = "arabic" if is_arabic(event["description"]) else ""
    formatted_date = event['date'].strftime('%B %d, %Y')

    # Hero image / placeholder
    if event.get('image'):
        st.markdown(f'<div class="detail-hero"><img class="detail-hero-img" src="{event["image"]}" alt="{event["title"]}" />', unsafe_allow_html=True)
    else:
        st.markdown('<div class="detail-hero"><div class="detail-hero-img-placeholder">🌸</div>', unsafe_allow_html=True)

    st.markdown(f"""
        <div class="detail-meta">
            <div class="detail-title {title_cls}">{event['title']}</div>
            <div class="detail-date">📅 {formatted_date}</div>
            <div class="detail-preview {preview_cls}">{event['preview']}</div>
        </div>
        <div class="detail-divider"></div>
        <div class="detail-body {body_cls}">{event['description']}</div>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons
    st.markdown("<br>", unsafe_allow_html=True)
    
    action_col1, action_col2, action_col3 = st.columns(3)
    
    with action_col1:
        if st.button("✉️ Share Memory", use_container_width=True, type="secondary"):
            with st.spinner("Sending..."):
                results = send_event_email_now(event, sender_username=st.session_state.get('user'))
                success_count = sum(1 for v in results.values() if v)
                if success_count > 0:
                    st.success(f"✉️ Memory sent to {success_count} person/people!")
                else:
                    st.error("Could not send the memory.")
    
    with action_col2:
        if st.button("📥 Export to PDF", use_container_width=True, type="secondary"):
            pdf_buffer = export_memories_to_pdf([event], "single")
            if pdf_buffer:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_buffer,
                    file_name=f"memory_{event['date'].strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf"
                )
    
    with action_col3:
        if st.button("✏️ Edit", use_container_width=True, type="secondary"):
            st.session_state.edit_event_id = event['id']
            st.rerun()


def add_event_form():
    """Form to add a new memory."""
    st.markdown("<h3 style='color:var(--text);font-family:\"Playfair Display\",serif;'>Add New Memory ✨</h3>", unsafe_allow_html=True)

    with st.form("add_event_form"):
        title = st.text_input("Memory Title *", placeholder="Give this memory a name...")
        preview = st.text_area("Preview (2-3 lines) *", placeholder="A short teaser of this memory...", height=68)
        event_date = st.date_input("Date *", value=date.today())
        description = st.text_area("Full Story *", placeholder="Tell us everything... what happened, how you felt, why it matters...", height=180)

        new_image = st.file_uploader("Photo (optional)", type=['png','jpg','jpeg'])
        if new_image:
            st.image(new_image, caption="Preview", use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Save Memory", type="primary", use_container_width=True)
        with c2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            st.session_state.show_add_form = False
            st.rerun()

        if save:
            if title and preview and description:
                img_b64 = None
                if new_image:
                    img_b64 = encode_image_to_base64(new_image)
                ok = save_event_to_db(title, event_date, preview, description, st.session_state.user['username'], img_b64)
                if ok:
                    st.success("✨ Memory saved!")
                    st.session_state.show_add_form = False
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Please fill in all required fields.")


def edit_event_form(event):
    """Form to edit an existing memory."""
    st.markdown(f"<h3 style='color:var(--text);font-family:\"Playfair Display\",serif;'>Edit Memory: {event['title']}</h3>", unsafe_allow_html=True)

    with st.form("edit_event_form"):
        title = st.text_input("Title", value=event.get('title', ''))
        preview = st.text_area("Preview", value=event.get('preview', ''), height=100)
        event_date = st.date_input("Date", value=event.get('date', date.today()))
        description = st.text_area("Full Story", value=event.get('description', ''), height=200)

        remove_img = False
        if event.get('image'):
            st.markdown("**Current photo:**")
            st.image(event['image'], width=280)
            remove_img = st.checkbox("Remove current photo")

        new_image = st.file_uploader("Replace photo (optional)", type=['png','jpg','jpeg'])
        if new_image:
            st.image(new_image, caption="New photo preview", use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
        with c2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)

    # Handle save / cancel results (outside form so rerun works cleanly)
    if cancel:
        st.session_state.edit_event_id = None
        st.rerun()

    if save:
        if title and preview and description:
            img_b64 = None
            if new_image:
                img_b64 = encode_image_to_base64(new_image) or event.get('image')
            elif remove_img:
                img_b64 = ""
            else:
                img_b64 = event.get('image')
            ok = update_event_in_db(event['id'], title, event_date, preview, description, st.session_state.user['username'], img_b64)
            if ok:
                st.success("✅ Memory updated!")
                st.session_state.edit_event_id = None
                time.sleep(1)
                st.rerun()
        else:
            st.error("Please fill in all required fields.")

    # Delete section — lives outside the form so st.checkbox works
    st.markdown("---")
    st.markdown("**⚠️ Danger Zone**")
    confirmed = st.checkbox("Confirm deletion — this cannot be undone", key="confirm_del")
    if st.button("🗑️ Delete Memory", type="secondary", disabled=not confirmed):
        ok = delete_event_from_db(event['id'], st.session_state.user['username'])
        if ok:
            st.success("Memory removed.")
            st.session_state.edit_event_id = None
            st.session_state.selected_event = None
            time.sleep(1)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────────────────────

def show_events_page():
    EVENTS_PER_PAGE = 8
    
    st.markdown("""
    <div class="page-hero">
        <h1>Our <em>Memories</em></h1>
        <p>Every moment we've chosen to remember ✨</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        all_events = load_events_from_db(st.session_state.user['username'])

    # Display search and filters
    display_search_filter()

    # Apply filters
    filtered_events = filter_events(all_events, 
                                    st.session_state.search_query,
                                    st.session_state.filter_date_from,
                                    st.session_state.filter_date_to)

    # Show result count if filtering
    if st.session_state.search_query or st.session_state.filter_date_from or st.session_state.filter_date_to:
        st.markdown(f"<p style='color:var(--muted);font-size:0.9rem;margin-bottom:1rem;'>Found <strong>{len(filtered_events)}</strong> memory/memories</p>", unsafe_allow_html=True)

    # ── Add form ─────────────────────────────────────────────────────────────
    if st.session_state.show_add_form:
        if st.button("← Back", type="secondary"):
            st.session_state.show_add_form = False
            st.rerun()
        add_event_form()
        return

    # ── Detail / edit view ──────────────────────────────────────────────────
    # Support both index-based (timeline/gallery) and ID-based (calendar) selection
    if st.session_state.selected_event_id is not None:
        # Resolve ID to the event object directly
        event_by_id = next((e for e in filtered_events if e['id'] == st.session_state.selected_event_id), None)
        if event_by_id is None:
            # Event not in current filter, search all events
            all_ev = load_events_from_db(st.session_state.user['username'])
            event_by_id = next((e for e in all_ev if e['id'] == st.session_state.selected_event_id), None)
        if event_by_id:
            if st.button("← Back to memories", key="back_from_cal", type="secondary"):
                st.session_state.selected_event_id = None
                st.session_state.edit_event_id = None
                st.rerun()
            if st.session_state.edit_event_id == event_by_id['id']:
                edit_event_form(event_by_id)
            else:
                display_event_detail(event_by_id)
            return
        else:
            st.session_state.selected_event_id = None

    if st.session_state.selected_event is not None:
        idx = st.session_state.selected_event
        if idx < len(filtered_events):
            if st.button("← Back to memories", type="secondary"):
                st.session_state.selected_event = None
                st.session_state.selected_event_id = None
                st.session_state.edit_event_id = None
                st.rerun()

            event = filtered_events[idx]
            if st.session_state.edit_event_id == event['id']:
                edit_event_form(event)
            else:
                display_event_detail(event)
            return
        else:
            st.session_state.selected_event = None

    # ── Empty state ──────────────────────────────────────────────────────────
    if not filtered_events:
        if not all_events:
            st.markdown("""
            <div style="text-align:center;padding:4rem 2rem;color:#b08070;">
                <div style="font-size:3rem;margin-bottom:1rem;">🌸</div>
                <h3 style="font-family:'Playfair Display',serif;color:#3a2e2e;">Start your story</h3>
                <p>Add your first memory using the button in the sidebar.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No memories match your search. Try adjusting your filters!")
        return

    # ── Gallery View ─────────────────────────────────────────────────────────
    if st.session_state.view_mode == 'gallery':
        display_gallery_view(filtered_events)
        return

    # ── Calendar View (option in sidebar or separate tab) ────────────────────
    tab1, tab2 = st.tabs(["📅 Timeline", "🗓️ Calendar"])
    
    with tab1:
        # ── Timeline View ────────────────────────────────────────────────────
        total = len(filtered_events)
        total_pages = max(1, (total + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE)

        if st.session_state.event_page >= total_pages:
            st.session_state.event_page = max(0, total_pages - 1)

        # Pagination top
        page = st.session_state.event_page
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("← Prev", disabled=page == 0, use_container_width=True):
                st.session_state.event_page -= 1
                st.rerun()
        with c2:
            st.markdown(f"<div style='text-align:center;color:#b08070;font-size:.85rem;padding:.5rem 0;'>Page {page+1} of {total_pages} · {total} memories</div>", unsafe_allow_html=True)
        with c3:
            if st.button("Next →", disabled=page >= total_pages-1, use_container_width=True):
                st.session_state.event_page += 1
                st.rerun()

        st.markdown('<div class="timeline-header"><span>📅</span> Timeline</div>', unsafe_allow_html=True)

        start = page * EVENTS_PER_PAGE
        page_events = filtered_events[start : start + EVENTS_PER_PAGE]

        for i, event in enumerate(page_events):
            display_event_card(event, i, start + i)

        # Pagination bottom
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("← Prev ", disabled=page == 0, use_container_width=True):
                st.session_state.event_page -= 1
                st.rerun()
        with c3:
            if st.button("Next → ", disabled=page >= total_pages-1, use_container_width=True):
                st.session_state.event_page += 1
                st.rerun()
    
    with tab2:
        display_calendar_view(filtered_events)


# ─────────────────────────────────────────────────────────────────────────────
# WELCOME ANIMATION
# ─────────────────────────────────────────────────────────────────────────────

def welcome_animation():
    # Hide sidebar during welcome animation
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    today = date.today()
    days = (today - START_DATE).days
    username = st.session_state.user.get('username', '').lower()
    display_name = COUPLE_NAMES.get(username, username.title())

    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        st.markdown(f"""
        <div style="text-align:center;padding:3rem 0 1rem;">
            <div style="font-size:2.5rem;margin-bottom:1rem;">❤️</div>
            <h2 style="font-family:'Playfair Display',serif;color:#3a2e2e;font-size:1.8rem;font-weight:400;">
                Welcome back, <em style="color:#d4857a;">{display_name}</em>
            </h2>
        </div>
        """, unsafe_allow_html=True)

        ph = st.empty()
        for i in range(days + 1):
            ph.markdown(f"""
            <div class="counter-display">
                <span class="big-num">{i}</span>
                <span class="small-text">days of knowing each other 🌸</span>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.008)

        time.sleep(1.5)

    st.session_state.counter_animated = True
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    init_session()
    inject_css()
    check_session_from_url()

    if not st.session_state.authenticated or not st.session_state.user:
        login_page()
        return

    # Handle calendar click arriving via URL param (?cal_event=<id>).
    # Must be resolved here — before the animation gate — because a full-page
    # reload resets counter_animated, and session state would be lost otherwise.
    cal_event_param = st.query_params.get('cal_event')
    if cal_event_param:
        try:
            st.session_state.selected_event_id = int(cal_event_param)
        except (ValueError, TypeError):
            st.session_state.selected_event_id = cal_event_param
        st.session_state.selected_event = None
        st.session_state.edit_event_id = None
        st.session_state.counter_animated = True   # skip the welcome animation
        st.query_params.pop('cal_event')

    if not st.session_state.counter_animated:
        welcome_animation()
        return

    # Auto-send daily reminders once per session at startup (skips if already sent today)
    if 'reminder_checked' not in st.session_state:
        st.session_state.reminder_checked = True
        try:
            send_today_reminders(force=False)
        except Exception:
            pass

    # Show left sidebar (works on both desktop and mobile)
    display_sidebar()
    show_events_page()


if __name__ == "__main__":
    main()
