# ─────────────────────────────────────────────────────────────────────────────
# Migration for JobPosting and RazorpayOrder
#
# INSTRUCTIONS:
#   1. Add the model code from models_additions.py into your models.py first.
#   2. Then run:
#        python manage.py makemigrations
#        python manage.py migrate
#
#   OR manually place this file at:
#        jobs/migrations/0002_jobposting_razorpayorder.py
#   (adjust the number so it's one higher than your latest migration)
#   Then run only:  python manage.py migrate
# ─────────────────────────────────────────────────────────────────────────────

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    # ── Change "0001_initial" to match your actual latest migration name ──────
    dependencies = [
        ("jobs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── JobPosting ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="JobPosting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title",               models.CharField(max_length=200)),
                ("company_name",        models.CharField(max_length=200)),
                ("company_logo",        models.ImageField(blank=True, null=True, upload_to="company_logos/")),
                ("location",            models.CharField(max_length=200)),
                ("job_type",            models.CharField(
                    choices=[
                        ("full_time",  "Full Time"),
                        ("part_time",  "Part Time"),
                        ("internship", "Internship"),
                        ("contract",   "Contract / Freelance"),
                        ("remote",     "Remote"),
                    ],
                    default="full_time", max_length=20,
                )),
                ("experience_required", models.CharField(
                    choices=[
                        ("fresher", "Fresher (0–1 yr)"),
                        ("junior",  "Junior (1–3 yrs)"),
                        ("mid",     "Mid-level (3–6 yrs)"),
                        ("senior",  "Senior (6+ yrs)"),
                        ("any",     "Any"),
                    ],
                    default="any", max_length=20,
                )),
                ("salary_min",          models.PositiveIntegerField(blank=True, null=True)),
                ("salary_max",          models.PositiveIntegerField(blank=True, null=True)),
                ("skills_required",     models.TextField()),
                ("description",         models.TextField()),
                ("how_to_apply",        models.TextField()),
                ("status",              models.CharField(
                    choices=[
                        ("pending_payment", "Pending Payment"),
                        ("active",          "Active"),
                        ("expired",         "Expired"),
                        ("paused",          "Paused"),
                    ],
                    default="pending_payment", max_length=20,
                )),
                ("created_at",    models.DateTimeField(auto_now_add=True)),
                ("activated_at",  models.DateTimeField(blank=True, null=True)),
                ("expires_at",    models.DateTimeField(blank=True, null=True)),
                ("views",         models.PositiveIntegerField(default=0)),
                ("applications",  models.PositiveIntegerField(default=0)),
                ("posted_by",     models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="job_postings",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Job Posting", "verbose_name_plural": "Job Postings"},
        ),

        # ── RazorpayOrder ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="RazorpayOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("razorpay_order_id",   models.CharField(max_length=100, unique=True)),
                ("razorpay_payment_id", models.CharField(blank=True, max_length=100, null=True)),
                ("razorpay_signature",  models.CharField(blank=True, max_length=256, null=True)),
                ("amount",    models.PositiveIntegerField(default=99900)),
                ("currency",  models.CharField(default="INR", max_length=10)),
                ("status",    models.CharField(
                    choices=[
                        ("created",  "Created"),
                        ("paid",     "Paid"),
                        ("failed",   "Failed"),
                        ("refunded", "Refunded"),
                    ],
                    default="created", max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at",    models.DateTimeField(blank=True, null=True)),
                ("job_posting", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="payment_orders",
                    to="jobs.jobposting",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="razorpay_orders",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Razorpay Order", "verbose_name_plural": "Razorpay Orders"},
        ),
    ]
