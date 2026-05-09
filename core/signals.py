# ─────────────────────────────────────────────────────────────────────────────
# core/signals.py  (new file — create it next to models.py)
# Sends email alerts to seekers whose skills match a newly-activated JobPosting ≥ 70%
# ─────────────────────────────────────────────────────────────────────────────

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail

from .models import JobPosting, UserProfile


# ── Skill matching ────────────────────────────────────────────────────────────

def _skill_match_score(user_skills_csv: str, job_skills_csv: str) -> int:
    """
    Returns the percentage of job-required skills covered by the user's skills.
    Simple keyword intersection — same logic as the existing AI scorer's fallback.

    E.g. user="Python, Django, SQL", job="Python, SQL, AWS"  → 2/3 = 66%
    """
    if not user_skills_csv or not job_skills_csv:
        return 0

    user_set = {s.strip().lower() for s in user_skills_csv.split(",") if s.strip()}
    job_set  = {s.strip().lower() for s in job_skills_csv.split(",")  if s.strip()}

    if not job_set:
        return 0

    matched = user_set & job_set
    return int(len(matched) / len(job_set) * 100)


# ── Signal handler ────────────────────────────────────────────────────────────

@receiver(post_save, sender=JobPosting)
def alert_matching_seekers(sender, instance, created, update_fields, **kwargs):
    """
    Fires whenever a JobPosting is saved.

    We only send emails when the posting has just become active:
      • It was brand-new and already active (edge case), OR
      • The 'status' field was just written (i.e. JobPosting.activate() was called,
        which does save(update_fields=["status", "activated_at", "expires_at"]))

    Never crashes — all mail sending is wrapped in try/except with fail_silently.
    """
    if instance.status != "active":
        return

    status_just_changed = update_fields is not None and "status" in update_fields
    if not created and not status_just_changed:
        return   # routine field update, not an activation event

    # Fetch all seekers who have skills + a valid email
    profiles = (
        UserProfile.objects
        .select_related("user")
        .exclude(skills="")
        .exclude(user__email="")
    )

    for profile in profiles:
        score = _skill_match_score(profile.skills, instance.skills_required)
        if score < 70:
            continue

        name    = profile.user.get_full_name() or profile.user.username
        subject = (
            f"🎯 {score}% Match — {instance.title} at {instance.company_name} | JobLens"
        )
        body = f"""Hi {name},

A new job on JobLens matches {score}% of your skills — check it out before it fills!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌  Role     : {instance.title}
🏢  Company  : {instance.company_name}
📍  Location : {instance.location}
💼  Type     : {instance.get_job_type_display()}  ·  {instance.get_experience_required_display()}
💰  Salary   : {instance.salary_display}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛠  Skills required:
{instance.skills_required}

📋  How to apply:
{instance.how_to_apply}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find more matching jobs →
https://job-lens-production-b268.up.railway.app/find-jobs/

— The JobLens Team

(You're receiving this because your profile skills matched this listing.
To stop alerts, clear your skills in Profile → Settings.)
"""
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email="alerts@joblens.in",
                recipient_list=[profile.user.email],
                fail_silently=True,   # never interrupt a payment callback
            )
        except Exception:
            pass
