from django.contrib import admin
from django.utils.html import format_html
from .models import JobPosting, RazorpayOrder


# ─────────────────────────────────────────────────────────────────────────────
# JOB POSTING ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display  = (
        "title", "company_name", "location", "job_type",
        "status_colored", "views", "applications",
        "activated_at", "expires_at", "posted_by",
    )
    list_filter   = ("status", "job_type", "experience_required", "created_at")
    search_fields = ("title", "company_name", "location", "posted_by__username")
    readonly_fields = ("created_at", "activated_at", "expires_at", "views", "applications")
    ordering      = ("-created_at",)

    fieldsets = (
        ("Job Details", {
            "fields": (
                "posted_by", "title", "company_name", "company_logo",
                "location", "job_type", "experience_required",
                "salary_min", "salary_max",
            )
        }),
        ("Content", {
            "fields": ("skills_required", "description", "how_to_apply"),
        }),
        ("Status & Lifecycle", {
            "fields": ("status", "created_at", "activated_at", "expires_at"),
        }),
        ("Analytics", {
            "fields": ("views", "applications"),
        }),
    )

    actions = ["activate_postings", "expire_postings", "pause_postings"]

    @admin.display(description="Status")
    def status_colored(self, obj):
        color_map = {
            "active":          ("#27ae60", "✅ Active"),
            "pending_payment": ("#f39c12", "⏳ Pending"),
            "expired":         ("#e74c3c", "❌ Expired"),
            "paused":          ("#95a5a6", "⏸ Paused"),
        }
        color, label = color_map.get(obj.status, ("#999", obj.status))
        return format_html('<span style="color:{}; font-weight:600;">{}</span>', color, label)

    @admin.action(description="✅ Activate selected postings (30 days)")
    def activate_postings(self, request, queryset):
        for posting in queryset:
            posting.activate()
        self.message_user(request, f"{queryset.count()} posting(s) activated.")

    @admin.action(description="❌ Mark selected postings as Expired")
    def expire_postings(self, request, queryset):
        queryset.update(status="expired")
        self.message_user(request, f"{queryset.count()} posting(s) expired.")

    @admin.action(description="⏸ Pause selected postings")
    def pause_postings(self, request, queryset):
        queryset.update(status="paused")
        self.message_user(request, f"{queryset.count()} posting(s) paused.")


# ─────────────────────────────────────────────────────────────────────────────
# RAZORPAY ORDER ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(RazorpayOrder)
class RazorpayOrderAdmin(admin.ModelAdmin):
    list_display  = (
        "razorpay_order_id", "user", "job_posting_title",
        "amount_display", "status_colored", "created_at", "paid_at",
    )
    list_filter   = ("status", "currency", "created_at")
    search_fields = (
        "razorpay_order_id", "razorpay_payment_id",
        "user__username", "job_posting__title",
    )
    readonly_fields = (
        "razorpay_order_id", "razorpay_payment_id", "razorpay_signature",
        "created_at", "paid_at", "user", "job_posting",
    )
    ordering = ("-created_at",)

    @admin.display(description="Job")
    def job_posting_title(self, obj):
        return obj.job_posting.title

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return f"₹{obj.amount // 100}"

    @admin.display(description="Status")
    def status_colored(self, obj):
        color_map = {
            "paid":     ("#27ae60", "💚 Paid"),
            "created":  ("#f39c12", "🟡 Created"),
            "failed":   ("#e74c3c", "🔴 Failed"),
            "refunded": ("#3498db", "🔵 Refunded"),
        }
        color, label = color_map.get(obj.status, ("#999", obj.status))
        return format_html('<span style="color:{}; font-weight:600;">{}</span>', color, label)