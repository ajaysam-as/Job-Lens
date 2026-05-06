# ─────────────────────────────────────────────────────────────────────────────
# HIRER VIEWS  — add to (or import into) your main views.py
# pip install razorpay
# ─────────────────────────────────────────────────────────────────────────────

import hmac
import hashlib
import json
import logging

import razorpay
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import JobPosting, RazorpayOrder

logger = logging.getLogger(__name__)

# ── Razorpay client (lazy singleton) ──────────────────────────────────────────

def _rzp_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. POST A JOB (form + preview)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def post_job(request):
    """
    GET  → render the job-posting form
    POST → save a JobPosting (status=pending_payment) then redirect to payment
    """
    if request.method == "POST":
        data = request.POST

        # Basic server-side validation
        required = ["title", "company_name", "location", "description",
                    "skills_required", "how_to_apply"]
        for field in required:
            if not data.get(field, "").strip():
                messages.error(request, f"'{field}' is required.")
                return render(request, "post_job.html", {"post": data})

        posting = JobPosting.objects.create(
            posted_by=request.user,
            title=data["title"].strip(),
            company_name=data["company_name"].strip(),
            location=data["location"].strip(),
            job_type=data.get("job_type", "full_time"),
            experience_required=data.get("experience_required", "any"),
            salary_min=int(data["salary_min"]) if data.get("salary_min") else None,
            salary_max=int(data["salary_max"]) if data.get("salary_max") else None,
            skills_required=data["skills_required"].strip(),
            description=data["description"].strip(),
            how_to_apply=data["how_to_apply"].strip(),
            status="pending_payment",
        )
        return redirect("initiate_payment", posting_id=posting.id)

    return render(request, "post_job.html")


# ─────────────────────────────────────────────────────────────────────────────
# 2. INITIATE PAYMENT  — creates Razorpay order, renders checkout page
# ─────────────────────────────────────────────────────────────────────────────

POSTING_PRICE_PAISE = 99900  # ₹999

@login_required
def initiate_payment(request, posting_id):
    posting = get_object_or_404(
        JobPosting, id=posting_id, posted_by=request.user
    )

    if posting.status == "active":
        messages.info(request, "This job is already live!")
        return redirect("hirer_dashboard")

    # Create a fresh Razorpay order each time user lands here
    client = _rzp_client()
    rzp_order = client.order.create({
        "amount": POSTING_PRICE_PAISE,
        "currency": "INR",
        "receipt": f"joblens_posting_{posting.id}",
        "notes": {
            "posting_id": str(posting.id),
            "user_id": str(request.user.id),
        },
    })

    db_order = RazorpayOrder.objects.create(
        user=request.user,
        job_posting=posting,
        razorpay_order_id=rzp_order["id"],
        amount=POSTING_PRICE_PAISE,
    )

    context = {
        "posting": posting,
        "rzp_order_id": rzp_order["id"],
        "rzp_key": settings.RAZORPAY_KEY_ID,
        "amount": POSTING_PRICE_PAISE,
        "amount_display": "₹999",
        "user_name": request.user.get_full_name() or request.user.username,
        "user_email": request.user.email,
    }
    return render(request, "payment_checkout.html", context)


# ─────────────────────────────────────────────────────────────────────────────
# 3. PAYMENT CALLBACK  — called by Razorpay JS after user pays
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def payment_callback(request):
    """
    Razorpay JS posts razorpay_order_id, razorpay_payment_id, razorpay_signature
    here after successful payment. We verify the signature then activate posting.
    """
    order_id   = request.POST.get("razorpay_order_id", "")
    payment_id = request.POST.get("razorpay_payment_id", "")
    signature  = request.POST.get("razorpay_signature", "")

    db_order = get_object_or_404(
        RazorpayOrder, razorpay_order_id=order_id, user=request.user
    )

    # ── Signature verification ─────────────────────────────────────────────
    generated = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(generated, signature):
        logger.warning("Razorpay signature mismatch for order %s", order_id)
        db_order.status = "failed"
        db_order.save(update_fields=["status"])
        messages.error(request, "Payment verification failed. Contact support.")
        return redirect("initiate_payment", posting_id=db_order.job_posting.id)

    # ── All good — activate ────────────────────────────────────────────────
    db_order.mark_paid(payment_id, signature)

    # WhatsApp notification to hirer
    _notify_hirer_whatsapp(db_order.job_posting)

    messages.success(
        request,
        f"🎉 Payment successful! Your job '{db_order.job_posting.title}' "
        "is now live for 30 days.",
    )
    return redirect("hirer_dashboard")


# ─────────────────────────────────────────────────────────────────────────────
# 4. RAZORPAY WEBHOOK  (optional but recommended for reliability)
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """
    Set Webhook URL in Razorpay dashboard → https://yourdomain/payments/webhook/
    Event: payment.captured
    """
    webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    payload = request.body

    # Verify webhook signature
    received_sig = request.headers.get("X-Razorpay-Signature", "")
    expected_sig = hmac.new(
        webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, received_sig):
        logger.warning("Invalid Razorpay webhook signature")
        return HttpResponseBadRequest("Invalid signature")

    event = json.loads(payload)
    if event.get("event") == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        order_id = payment.get("order_id")
        payment_id = payment.get("id")
        try:
            db_order = RazorpayOrder.objects.get(
                razorpay_order_id=order_id, status="created"
            )
            db_order.mark_paid(payment_id, received_sig)
        except RazorpayOrder.DoesNotExist:
            pass  # already handled by callback or duplicate event

    return JsonResponse({"status": "ok"})


# ─────────────────────────────────────────────────────────────────────────────
# 5. HIRER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def hirer_dashboard(request):
    postings = JobPosting.objects.filter(posted_by=request.user).order_by("-created_at")
    context = {
        "postings": postings,
        "active_count": postings.filter(status="active").count(),
        "total_views": sum(p.views for p in postings),
        "total_applications": sum(p.applications for p in postings),
    }
    return render(request, "hirer_dashboard.html", context)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPER — WhatsApp via Twilio
# ─────────────────────────────────────────────────────────────────────────────

def _notify_hirer_whatsapp(posting: JobPosting):
    """Send WhatsApp confirmation to the hirer after job goes live."""
    try:
        from twilio.rest import Client as TwilioClient

        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token  = settings.TWILIO_AUTH_TOKEN
        from_number = settings.TWILIO_WHATSAPP_FROM   # e.g. "whatsapp:+14155238886"
        to_number   = getattr(posting.posted_by, "profile", None)

        if not to_number:
            return

        phone = getattr(to_number, "whatsapp_number", None)
        if not phone:
            return

        client = TwilioClient(account_sid, auth_token)
        body = (
            f"✅ *JobLens – Job Live!*\n\n"
            f"Hi {posting.posted_by.get_full_name() or posting.posted_by.username},\n\n"
            f"Your job posting *{posting.title}* at *{posting.company_name}* "
            f"is now live on JobLens!\n\n"
            f"🗓 Active until: {posting.expires_at.strftime('%d %b %Y')}\n"
            f"📍 Location: {posting.location}\n\n"
            f"We'll notify you when candidates apply. Good luck! 🚀\n"
            f"— Team JobLens"
        )
        client.messages.create(
            from_=from_number,
            to=f"whatsapp:{phone}",
            body=body,
        )
    except Exception as exc:
        logger.error("WhatsApp notification failed: %s", exc)
