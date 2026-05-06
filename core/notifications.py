# ─────────────────────────────────────────────────────────────────────────────
# notifications.py  — Drop this file next to views.py
# pip install twilio
# ─────────────────────────────────────────────────────────────────────────────

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def _twilio_client():
    from twilio.rest import Client
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_whatsapp(to_phone: str, body: str) -> bool:
    """
    Send a WhatsApp message via Twilio.
    to_phone: Indian mobile number, e.g. "+919876543210"
    Returns True on success, False on failure.
    """
    try:
        client = _twilio_client()
        msg = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,   # "whatsapp:+14155238886"
            to=f"whatsapp:{to_phone}",
            body=body,
        )
        logger.info("WhatsApp sent. SID=%s to=%s", msg.sid, to_phone)
        return True
    except Exception as exc:
        logger.error("WhatsApp send failed to %s: %s", to_phone, exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# PRE-BUILT MESSAGE TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

def notify_job_seeker_match(user, job_title: str, company: str, score: int, phone: str):
    """
    Notify a job seeker when a new high-match job is posted.
    Call from your job-match / recommendation pipeline.
    """
    body = (
        f"🎯 *JobLens – New Job Match!*\n\n"
        f"Hi {user.get_full_name() or user.username}!\n\n"
        f"A new job matching your profile just dropped:\n"
        f"*{job_title}* at *{company}*\n"
        f"Match Score: {score}% ✨\n\n"
        f"🔗 View & Apply → https://job-lens-production-b268.up.railway.app\n\n"
        f"_Reply STOP to unsubscribe_"
    )
    return send_whatsapp(phone, body)


def notify_job_posted(posting, phone: str):
    """Confirmation to hirer after their job goes live."""
    body = (
        f"✅ *JobLens – Your Job is Live!*\n\n"
        f"Hi {posting.posted_by.get_full_name() or posting.posted_by.username},\n\n"
        f"*{posting.title}* @ *{posting.company_name}* is now live!\n\n"
        f"📍 {posting.location}\n"
        f"🗓 Active until: {posting.expires_at.strftime('%d %b %Y')}\n\n"
        f"Track applications at:\n"
        f"https://job-lens-production-b268.up.railway.app/hirer/dashboard/\n\n"
        f"— Team JobLens 🚀"
    )
    return send_whatsapp(phone, body)


def notify_application_received(posting, applicant_name: str, phone: str):
    """
    Notify the hirer when someone saves/applies to their posted job.
    Call this from your save_job or apply view.
    """
    body = (
        f"📬 *JobLens – New Application!*\n\n"
        f"*{applicant_name}* just applied for *{posting.title}*!\n\n"
        f"Login to view their profile and resume:\n"
        f"https://job-lens-production-b268.up.railway.app/hirer/dashboard/\n\n"
        f"— Team JobLens"
    )
    return send_whatsapp(phone, body)


def notify_resume_parsed(user, skills: list, phone: str):
    """Let job seeker know their resume was parsed successfully."""
    skill_str = ", ".join(skills[:5])
    body = (
        f"📄 *JobLens – Resume Analysed!*\n\n"
        f"Hi {user.get_full_name() or user.username}, your resume was successfully "
        f"analysed by our AI.\n\n"
        f"Top skills detected: *{skill_str}*{'...' if len(skills) > 5 else ''}\n\n"
        f"We're now matching you with the best jobs. Check your dashboard:\n"
        f"https://job-lens-production-b268.up.railway.app\n\n"
        f"— Team JobLens 🤖"
    )
    return send_whatsapp(phone, body)
