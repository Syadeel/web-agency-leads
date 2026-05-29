"""
OS[Outreach Suit] — Cold Outreach Automation

Reads pending leads from Supabase, sends personalized outreach via:
  1. Email (SMTP / SendGrid / Gmail API)
  2. WhatsApp (via WhatsApp Business API or ClickSend)
  3. SMS (via Twilio or ClickSend)

Usage:
    python outreach.py                           # Dry run (just shows what would happen)
    python outreach.py --send-email              # Actually send emails
    python outreach.py --send-whatsapp           # Actually send WhatsApp messages
    python outreach.py --send-email --limit 5    # Limit to 5 leads
    python outreach.py --mark-read               # Mark all pending as 'contacted' (no send)
"""
import os
import sys
import io
# Force UTF-8 for terminal output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import smtplib
import ssl
import argparse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import psycopg2

# ─── Configuration ──────────────────────────────────────────────
load_dotenv()

DRY_RUN = True  # Will be overridden by --send flags

# Email config (set these in .env when ready)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
FROM_NAME = os.getenv("FROM_NAME", "Web Agency")

# WhatsApp / SMS config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

YOUR_AGENCY = os.getenv("AGENCY_NAME", "Your Agency")
YOUR_PHONE = os.getenv("AGENCY_PHONE", "your-phone-number")


# ─── Database ───────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT", "6543"),
    )


def get_pending_leads(limit=None):
    """Fetch leads that haven't been contacted yet."""
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT id, instagram_handle, name, phone, email, niche, city, bio
        FROM leads
        WHERE outreach_status = 'pending'
        ORDER BY niche, id
    """
    if limit:
        query += f" LIMIT {limit}"
    cur.execute(query)
    rows = cur.fetchall()
    columns = ["id", "instagram_handle", "name", "phone", "email", "niche", "city", "bio"]
    leads = [dict(zip(columns, row)) for row in rows]
    cur.close()
    conn.close()
    return leads


def mark_contacted(lead_id, method="dry_run"):
    """Update lead status after outreach attempt."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE leads
        SET outreach_status = 'contacted',
            outreach_date = %s,
            last_contacted_at = %s,
            outreach_notes = %s
        WHERE id = %s
        """,
        (datetime.utcnow(), datetime.utcnow(), f"Contacted via {method}", lead_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def mark_all_read():
    """Quick mode: mark all pending as contacted without sending."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE leads
        SET outreach_status = 'contacted',
            outreach_date = %s,
            last_contacted_at = %s,
            outreach_notes = 'Marked read (no outreach sent)'
        WHERE outreach_status = 'pending'
        """,
        (datetime.utcnow(), datetime.utcnow()),
    )
    count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return count


# ─── Templates ──────────────────────────────────────────────────
def build_outreach_message(lead):
    """Build personalized outreach message for a lead."""
    name = lead.get("name") or lead.get("instagram_handle") or "there"
    niche = lead.get("niche") or "business"
    handle = lead.get("instagram_handle") or ""
    city = lead.get("city") or "your area"

    # Clean up name — remove Instagram suffix
    clean_name = name.split("•")[0].split("(@")[0].strip()

    whatsapp = f"""Hi {clean_name}!

I came across your Instagram page (@{handle}) and really love what you're doing with your {niche} business!

We help local {niche} businesses in {city} grow with professional websites starting from just PKR XX,XXX - including a gallery, WhatsApp chat button, and contact form.

Would you be interested in a free 10-minute consultation to see how we can help you get more customers?

Looking forward to hearing from you!
{from_name}"""

    email_html = f"""<html><body style="font-family: Arial, sans-serif; max-width: 600px;">
<h2>Hi {clean_name}!</h2>
<p>I came across your Instagram page (<strong>@{handle}</strong>) and really like what you're doing with your {niche} business.</p>
<p>We help local businesses in <strong>{city}</strong> grow their online presence with professional websites. A simple landing page with a gallery, WhatsApp integration, and contact form can help you get more customers.</p>
<p>Would you be open to a <strong>free 10-minute consultation</strong> this week?</p>
<br>
<p>Best regards,<br><strong>{from_name}</strong></p>
</body></html>"""

    return {"whatsapp": whatsapp, "email_html": email_html, "email_text": f"Hi {clean_name},\n\nI came across your Instagram (@{handle}) and really like what you're doing with your {niche} business.\n\nWe help local businesses in {city} grow their online presence with professional websites.\n\nWould you be open to a free 10-minute consultation this week?\n\nBest,\n{from_name}"}


# ─── Email Sender ───────────────────────────────────────────────
def send_email(lead, dry_run=True):
    """Send personalized email to a lead."""
    if not SMTP_USER or not SMTP_PASSWORD:
        return "[SKIP] Email not configured (set SMTP_USER/SMTP_PASSWORD in .env)"

    messages = build_outreach_message(lead)
    recipient = lead.get("email")
    if not recipient:
        return "[SKIP] No email address"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Helping {lead.get('name', 'your business')} grow online"
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = recipient
    msg.attach(MIMEText(messages["email_text"], "plain"))
    msg.attach(MIMEText(messages["email_html"], "html"))

    if dry_run:
        return f"[DRY] Would send email to {recipient}"

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, recipient, msg.as_string())
        return f"[SENT] Email to {recipient}"
    except Exception as e:
        return f"[FAIL] Email to {recipient}: {e}"


# ─── WhatsApp Sender (Twilio) ───────────────────────────────────
def send_whatsapp(lead, dry_run=True):
    """Send WhatsApp message via Twilio."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return "[SKIP] WhatsApp not configured (set TWILIO_* in .env)"

    messages = build_outreach_message(lead)
    phone = lead.get("phone")
    if not phone or phone == "Not Found":
        return "[SKIP] No phone number"

    # Clean phone number
    phone = phone.replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+92" + phone.lstrip("0")  # Assume Pakistan

    if dry_run:
        return f"[DRY] Would send WhatsApp to {phone}"

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=messages["whatsapp"],
            from_=f"whatsapp:{TWILIO_FROM_NUMBER}",
            to=f"whatsapp:{phone}",
        )
        return f"[SENT] WhatsApp to {phone} (sid: {message.sid})"
    except Exception as e:
        return f"[FAIL] WhatsApp to {phone}: {e}"


# ─── SMS Sender (Twilio) ────────────────────────────────────────
def send_sms(lead, dry_run=True):
    """Send SMS via Twilio."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return "[SKIP] SMS not configured"

    messages = build_outreach_message(lead)
    phone = lead.get("phone")
    if not phone or phone == "Not Found":
        return "[SKIP] No phone number"

    phone = phone.replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+92" + phone.lstrip("0")

    if dry_run:
        return f"[DRY] Would send SMS to {phone}"

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=messages["whatsapp"][:160],  # SMS limit
            from_=TWILIO_FROM_NUMBER,
            to=phone,
        )
        return f"[SENT] SMS to {phone}"
    except Exception as e:
        return f"[FAIL] SMS to {phone}: {e}"


# ─── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OS[Outreach Suit] — Cold Outreach Automation")
    parser.add_argument("--send-email", action="store_true", help="Actually send emails")
    parser.add_argument("--send-whatsapp", action="store_true", help="Actually send WhatsApp messages")
    parser.add_argument("--send-sms", action="store_true", help="Actually send SMS")
    parser.add_argument("--limit", type=int, default=None, help="Max leads to process")
    parser.add_argument("--mark-read", action="store_true", help="Mark all pending as contacted (no send)")
    args = parser.parse_args()

    print("=" * 60)
    print("  OS[OUTREACH SUIT]")
    print("=" * 60)

    # Mark-read mode
    if args.mark_read:
        count = mark_all_read()
        print(f"[OK] Marked {count} leads as 'contacted' (no outreach sent)")
        return

    dry_run = not (args.send_email or args.send_whatsapp or args.send_sms)

    if dry_run:
        print("\n  (DRY RUN) No messages will be sent")
        print("  Use --send-email, --send-whatsapp, or --send-sms to send\n")
    else:
        methods = []
        if args.send_email: methods.append("email")
        if args.send_whatsapp: methods.append("WhatsApp")
        if args.send_sms: methods.append("SMS")
        print(f"\n  (LIVE) Sending via: {', '.join(methods)}\n")

    # Get pending leads
    leads = get_pending_leads(limit=args.limit)
    print(f"\n[*] Found {len(leads)} pending leads\n")

    if not leads:
        print("[!] No pending leads. Run pipeline.py first to scrape some.")
        return

    # Process each lead
    sent_count = 0
    failed_count = 0

    for i, lead in enumerate(leads, 1):
        name = lead.get("name") or lead.get("instagram_handle") or "?"
        niche = lead.get("niche") or "?"
        phone = lead.get("phone") or "none"
        email = lead.get("email") or "none"

        print(f"\n[{i}/{len(leads)}] {name[:30]:30} | @{lead['instagram_handle']:<15} | niche: {niche:<18}")
        print(f"       Phone: {phone:<20} Email: {email}")

        result = None
        method = "dry_run"

        if args.send_email:
            result = send_email(lead, dry_run=False)
            method = "email"

        if args.send_whatsapp:
            result = send_whatsapp(lead, dry_run=False)
            method = "whatsapp"

        if args.send_sms:
            result = send_sms(lead, dry_run=False)
            method = "sms"

        if result:
            print(f"       {result}")
            if result.startswith("[SENT]") or result.startswith("[DRY]"):
                sent_count += 1
                if not dry_run and result.startswith("[SENT]"):
                    mark_contacted(lead["id"], method)
            else:
                failed_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"  Total processed: {len(leads)}")
    print(f"  Sent/DRY:        {sent_count}")
    print(f"  Failed/Skipped:  {failed_count}")
    if dry_run:
        print(f"\n  To send for real:")
        print(f"    python outreach.py --send-email")
        print(f"    python outreach.py --send-whatsapp")
        print(f"    python outreach.py --send-email --send-whatsapp --limit 3")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
