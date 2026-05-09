from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime 

# ─────────────────────────────────────────────────────────────────────────────
# EXISTING MODELS (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    resume_text = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    experience_years = models.IntegerField(default=0)
    location = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True,
                                       help_text="+91XXXXXXXXXX format")  # ← NEW for WhatsApp alerts
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class SavedJob(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    job_title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    apply_url = models.URLField(max_length=500)
    source = models.CharField(max_length=50)
    match_score = models.IntegerField(default=0)
    saved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job_title} at {self.company}"


# ─────────────────────────────────────────────────────────────────────────────
# NEW: HIRER PLATFORM MODELS
# ─────────────────────────────────────────────────────────────────────────────

class JobPosting(models.Model):
    """Posted by hirers after paying ₹999. Shown alongside scraped listings."""

    STATUS_CHOICES = [
        ("pending_payment", "Pending Payment"),
        ("active",          "Active"),
        ("expired",         "Expired"),
        ("paused",          "Paused"),
    ]
    JOB_TYPE_CHOICES = [
        ("full_time",  "Full Time"),
        ("part_time",  "Part Time"),
        ("internship", "Internship"),
        ("contract",   "Contract / Freelance"),
        ("remote",     "Remote"),
    ]
    EXPERIENCE_CHOICES = [
        ("fresher", "Fresher (0–1 yr)"),
        ("junior",  "Junior (1–3 yrs)"),
        ("mid",     "Mid-level (3–6 yrs)"),
        ("senior",  "Senior (6+ yrs)"),
        ("any",     "Any"),
    ]

    posted_by           = models.ForeignKey(User, on_delete=models.CASCADE, related_name="job_postings")
    title               = models.CharField(max_length=200)
    company_name        = models.CharField(max_length=200)
    company_logo        = models.ImageField(upload_to="company_logos/", null=True, blank=True)
    location            = models.CharField(max_length=200)
    job_type            = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default="full_time")
    experience_required = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, default="any")
    salary_min          = models.PositiveIntegerField(null=True, blank=True, help_text="Monthly salary in INR")
    salary_max          = models.PositiveIntegerField(null=True, blank=True, help_text="Monthly salary in INR")
    skills_required     = models.TextField(help_text="Comma-separated, e.g. Python, Django, SQL")
    description         = models.TextField()
    how_to_apply        = models.TextField()
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_payment")
    created_at          = models.DateTimeField(auto_now_add=True)
    activated_at        = models.DateTimeField(null=True, blank=True)
    expires_at          = models.DateTimeField(null=True, blank=True)
    views               = models.PositiveIntegerField(default=0)
    applications        = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job Posting"
        verbose_name_plural = "Job Postings"

    def __str__(self):
        return f"{self.title} @ {self.company_name} [{self.get_status_display()}]"

    @property
    def is_active(self):
        if self.status != "active":
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @property
    def salary_display(self):
        if self.salary_min and self.salary_max:
            return f"₹{self.salary_min:,} – ₹{self.salary_max:,}/mo"
        if self.salary_min:
            return f"From ₹{self.salary_min:,}/mo"
        return "Salary not disclosed"

    def activate(self):
        """Call after successful Razorpay payment — activates listing for 30 days."""
        self.status = "active"
        self.activated_at = timezone.now()
        self.expires_at = timezone.now() + timezone.timedelta(days=30)
        self.save(update_fields=["status", "activated_at", "expires_at"])

    def skills_list(self):
        return [s.strip() for s in self.skills_required.split(",") if s.strip()]


class RazorpayOrder(models.Model):
    """Tracks every Razorpay payment attempt for a JobPosting."""

    STATUS_CHOICES = [
        ("created",  "Created"),
        ("paid",     "Paid"),
        ("failed",   "Failed"),
        ("refunded", "Refunded"),
    ]

    user                 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="razorpay_orders")
    job_posting          = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="payment_orders")
    razorpay_order_id    = models.CharField(max_length=100, unique=True)
    razorpay_payment_id  = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature   = models.CharField(max_length=256, null=True, blank=True)
    amount               = models.PositiveIntegerField(default=99900, help_text="In paise — 99900 = ₹999")
    currency             = models.CharField(max_length=10, default="INR")
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    created_at           = models.DateTimeField(auto_now_add=True)
    paid_at              = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Razorpay Order"
        verbose_name_plural = "Razorpay Orders"

    def __str__(self):
        return f"{self.razorpay_order_id} — {self.get_status_display()} — ₹{self.amount // 100}"

    def mark_paid(self, payment_id: str, signature: str):
        """Verify + activate. Call this from payment_callback and razorpay_webhook."""
        self.status = "paid"
        self.razorpay_payment_id = payment_id
        self.razorpay_signature = signature
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "razorpay_payment_id", "razorpay_signature", "paid_at"])
        self.job_posting.activate()
class ApplicationTracker(models.Model):
    """Tracks a seeker's job applications across a Kanban pipeline."""
 
    STATUS_CHOICES = [
        ("applied",       "Applied"),
        ("interviewing",  "Interviewing"),
        ("offered",       "Offered"),
        ("rejected",      "Rejected"),
    ]
 
    user         = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="tracked_applications"
    )
    job_title    = models.CharField(max_length=200)
    company      = models.CharField(max_length=200)
    location     = models.CharField(max_length=200, blank=True)
    apply_url    = models.URLField(max_length=500, blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="applied")
    notes        = models.TextField(blank=True, help_text="Interview rounds, contact, salary discussed…")
    applied_date = models.DateField(default=datetime.date.today)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering           = ["-updated_at"]
        verbose_name       = "Application Tracker"
        verbose_name_plural = "Application Tracker"
 
    def __str__(self):
        return f"{self.job_title} @ {self.company} [{self.get_status_display()}]"