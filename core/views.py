from django.db.models.fields import generated
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models import UserProfile, SavedJob, ApplicationTracker, JobPosting, RazorpayOrder
import PyPDF2, docx, os, json, io, requests, feedparser
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import logging

logger = logging.getLogger("core")

MODEL = "llama-3.3-70b-versatile"

# ─────────────────────────────────────────────────────────────────────────────
# LIVE SEARCH URL BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def make_linkedin_url(query, location="India"):
    return f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}&f_TPR=r604800&sortBy=DD"

def make_naukri_url(query, location="india"):
    q = query.lower().replace(" ", "-")
    l = location.lower().replace(" ", "-")
    return f"https://www.naukri.com/{q}-jobs-in-{l}"

def make_indeed_url(query, location="India"):
    return f"https://in.indeed.com/jobs?q={urllib.parse.quote(query)}&l={urllib.parse.quote(location)}&fromage=14&sort=date"

def make_internshala_url(query):
    q = query.lower().replace(" ", "-")
    return f"https://internshala.com/jobs/{q}-jobs"

def make_shine_url(query, location="india"):
    q = query.lower().replace(" ", "-")
    l = location.lower().replace(" ", "-")
    return f"https://www.shine.com/job-search/{q}-jobs-in-{l}"

def make_foundit_url(query, location="India"):
    return f"https://www.foundit.in/srp/results?query={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}"

def make_apna_url(query):
    return f"https://apna.co/jobs?q={urllib.parse.quote(query)}"

def make_freshersworld_url(query):
    q = query.lower().replace(" ", "-")
    return f"https://www.freshersworld.com/jobs/jobsearch/{q}-jobs"

def make_timesjobs_url(query, location="India"):
    return f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote(query)}&txtLocation={urllib.parse.quote(location)}"

def make_hirist_url(query):
    return f"https://www.hirist.tech/s/{urllib.parse.quote(query)}"

def make_naukrigulf_url(query):
    q = query.lower().replace(" ", "-")
    return f"https://www.naukrigulf.com/{q}-jobs"

def make_workindia_url(query):
    return f"https://www.workindia.in/job-search?q={urllib.parse.quote(query)}"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_groq():
    from groq import Groq
    return Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(file):
    doc = docx.Document(io.BytesIO(file.read()))
    return "\n".join(para.text for para in doc.paragraphs)

def ai_call(messages_list, max_tokens=500, temp=0.1, timeout=25):
    client = get_groq()
    r = client.chat.completions.create(
        model=MODEL, messages=messages_list, max_tokens=max_tokens,
        temperature=temp, timeout=timeout)
    return r.choices[0].message.content.strip()
 

def ai_extract_skills(resume_text):
    prompt = f"""Extract from this resume. Return ONLY valid JSON, no markdown:
{{"skills":["skill1"],"job_titles":["title1"],"experience_years":0,"location":"city","summary":"2 sentence summary"}}
Resume:{resume_text[:3000]}"""
    raw = ai_call([{"role": "system", "content": "Return only valid JSON."},
                   {"role": "user", "content": prompt}])
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 — WHATSAPP HELPER
# ─────────────────────────────────────────────────────────────────────────────

def send_whatsapp(to_number: str, body: str) -> bool:
    """
    Send a WhatsApp message via Twilio Sandbox.
    Returns True on success, False on any error (never raises).

    The recipient must first join your sandbox:
      → WhatsApp "join <your-keyword>" to +1-415-523-8886

    Env vars needed (set in Railway Variables):
        TWILIO_ACCOUNT_SID
        TWILIO_AUTH_TOKEN
        TWILIO_WHATSAPP_FROM   (default: whatsapp:+14155238886)
    """
    sid   = os.environ.get("TWILIO_ACCOUNT_SID",  "")
    token = os.environ.get("TWILIO_AUTH_TOKEN",   "")
    from_ = os.environ.get("TWILIO_WHATSAPP_FROM","whatsapp:+14155238886")

    if not sid or not token:
        logger.warning("WhatsApp: TWILIO credentials not set — skipping.")
        return False
    if not to_number:
        logger.warning("WhatsApp: no recipient number — skipping.")
        return False

    # Normalise to E.164 with whatsapp: prefix
    clean = to_number.strip().replace(" ", "")
    if not clean.startswith("+"):
        clean = "+91" + clean.lstrip("0")
    to_wa = f"whatsapp:{clean}"

    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(from_=from_, to=to_wa, body=body)
        logger.info("WhatsApp sent to %s", to_wa)
        return True
    except Exception as e:
        logger.error("WhatsApp send failed to %s: %s", to_wa, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# PORTAL / CATEGORY HELPERS  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

def get_portal_cards(category, query, location="India"):
    cat_config = {
        "tech": {
            "label": "Tech & IT Jobs",
            "portals": [
                {"name": "LinkedIn",    "color": "#0077b5", "icon": "💼", "note": "Top tech roles, MNCs and startups"},
                {"name": "Naukri",      "color": "#ef4444", "icon": "🔴", "note": "India's largest IT job board"},
                {"name": "Indeed",      "color": "#003A9B", "icon": "🔍", "note": "Global & Indian tech listings"},
                {"name": "Hirist",      "color": "#0f172a", "icon": "💻", "note": "Tech-only jobs, handpicked quality"},
                {"name": "Internshala", "color": "#16a34a", "icon": "🌱", "note": "Freshers and junior developer roles"},
                {"name": "Shine",       "color": "#7c3aed", "icon": "✨", "note": "IT & software engineer vacancies"},
                {"name": "Foundit",     "color": "#9333ea", "icon": "🔮", "note": "Monster India — tech & IT listings"},
                {"name": "TimesJobs",   "color": "#dc2626", "icon": "📰", "note": "Times Group — verified tech roles"},
            ],
            "queries": {
                "LinkedIn": query or "software engineer", "Naukri": query or "software engineer",
                "Indeed": query or "software developer", "Hirist": query or "developer",
                "Internshala": query or "software developer intern", "Shine": query or "IT jobs",
                "Foundit": query or "software engineer", "TimesJobs": query or "IT engineer",
            }
        },
        "data": {
            "label": "Data & AI Jobs",
            "portals": [
                {"name": "LinkedIn",    "color": "#0077b5", "icon": "💼", "note": "Data science & ML roles"},
                {"name": "Naukri",      "color": "#ef4444", "icon": "🔴", "note": "Data analyst & BI vacancies"},
                {"name": "Indeed",      "color": "#003A9B", "icon": "🔍", "note": "AI & analytics listings"},
                {"name": "Hirist",      "color": "#0f172a", "icon": "💻", "note": "ML engineer & data roles"},
                {"name": "Internshala", "color": "#16a34a", "icon": "🌱", "note": "Data science internships"},
            ],
            "queries": {
                "LinkedIn": query or "data scientist", "Naukri": query or "data analyst",
                "Indeed": query or "data analyst", "Hirist": query or "machine learning",
                "Internshala": query or "data science intern",
            }
        },
        "marketing": {
            "label": "Marketing Jobs",
            "portals": [
                {"name": "LinkedIn",    "color": "#0077b5", "icon": "💼", "note": "Digital marketing & brand roles"},
                {"name": "Naukri",      "color": "#ef4444", "icon": "🔴", "note": "Marketing manager vacancies"},
                {"name": "Indeed",      "color": "#003A9B", "icon": "🔍", "note": "SEO, SEM & content roles"},
                {"name": "Internshala", "color": "#16a34a", "icon": "🌱", "note": "Marketing internships & freshers"},
                {"name": "Shine",       "color": "#7c3aed", "icon": "✨", "note": "Digital marketing specialists"},
            ],
            "queries": {
                "LinkedIn": query or "digital marketing", "Naukri": query or "marketing manager",
                "Indeed": query or "digital marketing", "Internshala": query or "marketing intern",
                "Shine": query or "digital marketing",
            }
        },
        "finance": {
            "label": "Finance & Accounting Jobs",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Finance, CA & investment roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Accounts, audit & tax vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Finance analyst listings"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Banking & finance specialists"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Verified finance openings"},
            ],
            "queries": {
                "LinkedIn": query or "finance manager", "Naukri": query or "chartered accountant",
                "Indeed": query or "finance analyst", "Foundit": query or "finance",
                "TimesJobs": query or "finance jobs",
            }
        },
        "sales": {
            "label": "Sales & Business Development",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "B2B sales & BD roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Sales executive vacancies"},
                {"name": "Apna",      "color": "#0891b2", "icon": "🤝", "note": "Field & inside sales — verified"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Sales listings across India"},
                {"name": "WorkIndia", "color": "#0369a1", "icon": "🏢", "note": "Ground-level sales & telecalling"},
            ],
            "queries": {
                "LinkedIn": query or "sales manager", "Naukri": query or "sales executive",
                "Apna": query or "sales", "Indeed": query or "sales executive",
                "WorkIndia": query or "sales",
            }
        },
        "design": {
            "label": "Design & Creative Jobs",
            "portals": [
                {"name": "LinkedIn",    "color": "#0077b5", "icon": "💼", "note": "UI/UX and product design"},
                {"name": "Internshala", "color": "#16a34a", "icon": "🌱", "note": "Design internships & freshers"},
                {"name": "Naukri",      "color": "#ef4444", "icon": "🔴", "note": "Graphic & UX designer roles"},
                {"name": "Hirist",      "color": "#0f172a", "icon": "💻", "note": "Product & UI design roles"},
                {"name": "Indeed",      "color": "#003A9B", "icon": "🔍", "note": "Creative & design vacancies"},
            ],
            "queries": {
                "LinkedIn": query or "UI UX designer", "Internshala": query or "graphic design intern",
                "Naukri": query or "graphic designer", "Hirist": query or "product designer",
                "Indeed": query or "UX designer",
            }
        },
        "hr": {
            "label": "HR & People Operations",
            "portals": [
                {"name": "LinkedIn", "color": "#0077b5", "icon": "💼", "note": "HR business partner & talent roles"},
                {"name": "Naukri",   "color": "#ef4444", "icon": "🔴", "note": "HR manager & recruiter vacancies"},
                {"name": "Indeed",   "color": "#003A9B", "icon": "🔍", "note": "HR generalist & payroll jobs"},
                {"name": "Shine",    "color": "#7c3aed", "icon": "✨", "note": "HR & talent acquisition roles"},
            ],
            "queries": {
                "LinkedIn": query or "HR manager", "Naukri": query or "human resources",
                "Indeed": query or "HR generalist", "Shine": query or "HR recruiter",
            }
        },
        "internship": {
            "label": "Internships & Freshers",
            "portals": [
                {"name": "Internshala",   "color": "#16a34a", "icon": "🌱", "note": "India's #1 internship platform"},
                {"name": "LinkedIn",      "color": "#0077b5", "icon": "💼", "note": "Corporate internship programmes"},
                {"name": "Freshersworld", "color": "#059669", "icon": "🎓", "note": "Entry-level & fresher jobs"},
                {"name": "Naukri",        "color": "#ef4444", "icon": "🔴", "note": "Fresher & campus placements"},
                {"name": "Indeed",        "color": "#003A9B", "icon": "🔍", "note": "Internship listings across India"},
                {"name": "Apna",          "color": "#0891b2", "icon": "🤝", "note": "Entry-level & first jobs"},
            ],
            "queries": {
                "Internshala": query or "internship", "LinkedIn": query or "internship India",
                "Freshersworld": query or "fresher jobs", "Naukri": query or "fresher",
                "Indeed": query or "internship", "Apna": query or "fresher",
            }
        },
        "remote": {
            "label": "Remote & Work From Home",
            "portals": [
                {"name": "LinkedIn",      "color": "#0077b5", "icon": "💼", "note": "Remote-first companies hiring"},
                {"name": "Internshala",   "color": "#16a34a", "icon": "🌱", "note": "WFH & remote internships"},
                {"name": "Indeed",        "color": "#003A9B", "icon": "🔍", "note": "Remote jobs across India"},
                {"name": "Naukri",        "color": "#ef4444", "icon": "🔴", "note": "Work from home listings"},
                {"name": "Freshersworld", "color": "#059669", "icon": "🎓", "note": "Remote freshers jobs"},
            ],
            "queries": {
                "LinkedIn": (query or "remote") + " remote",
                "Internshala": (query or "work from home"),
                "Indeed": (query or "remote") + " work from home",
                "Naukri": (query or "remote") + " work from home",
                "Freshersworld": query or "remote jobs",
            }
        },
        "operations": {
            "label": "Operations & Supply Chain",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Operations & supply chain roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Ops manager & SCM vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Operations listings across India"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Logistics & operations roles"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Operations & SCM jobs"},
            ],
            "queries": {
                "LinkedIn": query or "operations manager", "Naukri": query or "operations manager",
                "Indeed": query or "operations manager", "Foundit": query or "operations",
                "TimesJobs": query or "supply chain operations",
            }
        },
        "education": {
            "label": "Education & EdTech",
            "portals": [
                {"name": "LinkedIn",    "color": "#0077b5", "icon": "💼", "note": "EdTech & teaching roles"},
                {"name": "Naukri",      "color": "#ef4444", "icon": "🔴", "note": "Education sector vacancies"},
                {"name": "Indeed",      "color": "#003A9B", "icon": "🔍", "note": "Teaching & training jobs"},
                {"name": "Internshala", "color": "#16a34a", "icon": "🌱", "note": "EdTech internships & freshers"},
                {"name": "TimesJobs",   "color": "#dc2626", "icon": "📰", "note": "Education & e-learning roles"},
                {"name": "Shine",       "color": "#7c3aed", "icon": "✨", "note": "Academic & training vacancies"},
            ],
            "queries": {
                "LinkedIn": query or "edtech", "Naukri": query or "education teacher",
                "Indeed": query or "teacher trainer", "Internshala": query or "education intern",
                "TimesJobs": query or "education jobs", "Shine": query or "academic jobs",
            }
        },
        "hospitality": {
            "label": "Hotel & Hospitality",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Hotel & resort management roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Hospitality & F&B vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Hotel jobs across India"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Hospitality & tourism roles"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Hotel & catering vacancies"},
            ],
            "queries": {
                "LinkedIn": query or "hotel management", "Naukri": query or "hospitality",
                "Indeed": query or "hotel jobs", "Foundit": query or "hospitality tourism",
                "TimesJobs": query or "hotel catering jobs",
            }
        },
        "aviation": {
            "label": "Airport & Aviation",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Aviation & airline roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Airport & ground staff vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Aviation jobs across India"},
                {"name": "Shine",     "color": "#7c3aed", "icon": "✨", "note": "Cabin crew & pilot roles"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Airport operations & cargo"},
            ],
            "queries": {
                "LinkedIn": query or "aviation", "Naukri": query or "airport jobs",
                "Indeed": query or "aviation jobs", "Shine": query or "cabin crew pilot",
                "TimesJobs": query or "airport aviation jobs",
            }
        },
        "healthcare": {
            "label": "Healthcare & Pharma",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Healthcare & pharma leadership"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Doctor, nurse & pharma vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Healthcare jobs across India"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Medical & clinical roles"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Pharma & hospital vacancies"},
                {"name": "Shine",     "color": "#7c3aed", "icon": "✨", "note": "Nursing & allied health roles"},
            ],
            "queries": {
                "LinkedIn": query or "healthcare", "Naukri": query or "doctor nurse pharmacist",
                "Indeed": query or "healthcare jobs", "Foundit": query or "medical clinical",
                "TimesJobs": query or "pharma hospital jobs", "Shine": query or "nursing health",
            }
        },
        "retail": {
            "label": "Retail & E-commerce",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Retail & e-commerce leadership"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Retail store & category roles"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Retail jobs across India"},
                {"name": "Apna",      "color": "#0891b2", "icon": "🤝", "note": "Store staff & sales associates"},
                {"name": "WorkIndia", "color": "#0369a1", "icon": "🏢", "note": "Ground retail & field sales"},
            ],
            "queries": {
                "LinkedIn": query or "retail manager", "Naukri": query or "retail ecommerce",
                "Indeed": query or "retail jobs", "Apna": query or "retail store",
                "WorkIndia": query or "retail sales",
            }
        },
        "logistics": {
            "label": "Logistics & Warehouse",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Logistics & supply chain roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Warehouse & delivery vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Logistics jobs across India"},
                {"name": "Apna",      "color": "#0891b2", "icon": "🤝", "note": "Delivery & warehouse staff"},
                {"name": "WorkIndia", "color": "#0369a1", "icon": "🏢", "note": "Driver & field logistics roles"},
            ],
            "queries": {
                "LinkedIn": query or "logistics manager", "Naukri": query or "logistics warehouse",
                "Indeed": query or "logistics jobs", "Apna": query or "delivery logistics",
                "WorkIndia": query or "driver logistics",
            }
        },
        "manufacturing": {
            "label": "Manufacturing & Engineering",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Manufacturing & plant management"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Production & quality engineer roles"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Manufacturing jobs across India"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Industrial & plant engineering"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Manufacturing & production vacancies"},
                {"name": "Shine",     "color": "#7c3aed", "icon": "✨", "note": "Mechanical & electrical engineer roles"},
            ],
            "queries": {
                "LinkedIn": query or "manufacturing engineer", "Naukri": query or "production engineer",
                "Indeed": query or "manufacturing jobs", "Foundit": query or "plant engineer",
                "TimesJobs": query or "manufacturing production", "Shine": query or "mechanical engineer",
            }
        },
        "security": {
            "label": "Security & Cybersecurity",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Cybersecurity & InfoSec roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Security analyst & SOC vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Security jobs across India"},
                {"name": "Hirist",    "color": "#0f172a", "icon": "💻", "note": "Tech security & ethical hacking"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Physical & cyber security roles"},
            ],
            "queries": {
                "LinkedIn": query or "cybersecurity", "Naukri": query or "security analyst",
                "Indeed": query or "security jobs", "Hirist": query or "cybersecurity ethical hacking",
                "Foundit": query or "security engineer",
            }
        },
        "bluecollar": {
            "label": "Blue Collar & Skilled Trades",
            "portals": [
                {"name": "Apna",      "color": "#0891b2", "icon": "🤝", "note": "Blue collar & trade verified jobs"},
                {"name": "WorkIndia", "color": "#0369a1", "icon": "🏢", "note": "Skilled trade & ground-level roles"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Trade & skilled worker listings"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "ITI & diploma holder vacancies"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Technician & skilled trade roles"},
            ],
            "queries": {
                "Apna": query or "blue collar skilled", "WorkIndia": query or "skilled worker",
                "Indeed": query or "technician trade jobs", "Naukri": query or "ITI diploma jobs",
                "Foundit": query or "technician mechanic",
            }
        },
        "media": {
            "label": "Media & PR",
            "portals": [
                {"name": "LinkedIn",    "color": "#0077b5", "icon": "💼", "note": "Media, journalism & PR roles"},
                {"name": "Naukri",      "color": "#ef4444", "icon": "🔴", "note": "Content & media vacancies"},
                {"name": "Indeed",      "color": "#003A9B", "icon": "🔍", "note": "Media jobs across India"},
                {"name": "Internshala", "color": "#16a34a", "icon": "🌱", "note": "Journalism & content internships"},
                {"name": "Shine",       "color": "#7c3aed", "icon": "✨", "note": "PR & communications roles"},
            ],
            "queries": {
                "LinkedIn": query or "media journalism PR", "Naukri": query or "media content writer",
                "Indeed": query or "media jobs", "Internshala": query or "journalism content intern",
                "Shine": query or "PR communications",
            }
        },
        "legal": {
            "label": "Legal & Compliance",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Legal counsel & compliance roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Lawyer & legal advisor vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Legal jobs across India"},
                {"name": "Foundit",   "color": "#9333ea", "icon": "🔮", "note": "Corporate legal & compliance"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Legal & regulatory roles"},
            ],
            "queries": {
                "LinkedIn": query or "legal counsel", "Naukri": query or "lawyer advocate",
                "Indeed": query or "legal jobs", "Foundit": query or "compliance legal",
                "TimesJobs": query or "legal regulatory jobs",
            }
        },
        "realestate": {
            "label": "Real Estate & Construction",
            "portals": [
                {"name": "LinkedIn",  "color": "#0077b5", "icon": "💼", "note": "Real estate & property roles"},
                {"name": "Naukri",    "color": "#ef4444", "icon": "🔴", "note": "Property & construction vacancies"},
                {"name": "Indeed",    "color": "#003A9B", "icon": "🔍", "note": "Real estate jobs across India"},
                {"name": "Shine",     "color": "#7c3aed", "icon": "✨", "note": "Civil & site engineer roles"},
                {"name": "TimesJobs", "color": "#dc2626", "icon": "📰", "note": "Construction & property management"},
            ],
            "queries": {
                "LinkedIn": query or "real estate", "Naukri": query or "real estate property",
                "Indeed": query or "real estate jobs", "Shine": query or "civil site engineer",
                "TimesJobs": query or "construction property jobs",
            }
        },
    }

    URL_BUILDERS = {
        "LinkedIn":      lambda q, l: make_linkedin_url(q, l),
        "Naukri":        lambda q, l: make_naukri_url(q, l),
        "Indeed":        lambda q, l: make_indeed_url(q, l),
        "Internshala":   lambda q, l: make_internshala_url(q),
        "Shine":         lambda q, l: make_shine_url(q, l),
        "Foundit":       lambda q, l: make_foundit_url(q, l),
        "Apna":          lambda q, l: make_apna_url(q),
        "Freshersworld": lambda q, l: make_freshersworld_url(q),
        "TimesJobs":     lambda q, l: make_timesjobs_url(q, l),
        "Hirist":        lambda q, l: make_hirist_url(q),
        "NaukriGulf":    lambda q, l: make_naukrigulf_url(q),
        "WorkIndia":     lambda q, l: make_workindia_url(q),
    }

    config = cat_config.get(category)
    if not config:
        return []

    cards = []
    for portal in config["portals"]:
        name    = portal["name"]
        q       = config["queries"].get(name, query or category)
        builder = URL_BUILDERS.get(name)
        url     = builder(q, location) if builder else \
                  f"https://www.google.com/search?q={urllib.parse.quote(q + ' jobs india')}"
        cards.append({
            "portal":       name,
            "color":        portal["color"],
            "icon":         portal["icon"],
            "note":         portal["note"],
            "search_url":   url,
            "query_label":  q,
            "category":     category,
            "match_score":  0,
            "match_reason": "",
        })
    return cards


def get_general_search_cards(query, location, sources):
    URL_BUILDERS = {
        "LinkedIn":      make_linkedin_url,
        "Naukri":        make_naukri_url,
        "Indeed":        make_indeed_url,
        "Internshala":   lambda q, l: make_internshala_url(q),
        "Shine":         make_shine_url,
        "Foundit":       make_foundit_url,
        "Apna":          lambda q, l: make_apna_url(q),
        "Freshersworld": lambda q, l: make_freshersworld_url(q),
        "TimesJobs":     make_timesjobs_url,
        "Hirist":        lambda q, l: make_hirist_url(q),
        "NaukriGulf":    lambda q, l: make_naukrigulf_url(q),
        "WorkIndia":     lambda q, l: make_workindia_url(q),
    }
    PORTAL_META = {
        "LinkedIn":      {"color": "#0077b5", "icon": "💼", "note": "Professional network — MNCs & startups"},
        "Naukri":        {"color": "#ef4444", "icon": "🔴", "note": "India's largest job board"},
        "Indeed":        {"color": "#003A9B", "icon": "🔍", "note": "Global job search aggregator"},
        "Internshala":   {"color": "#16a34a", "icon": "🌱", "note": "Internships & entry-level roles"},
        "Shine":         {"color": "#7c3aed", "icon": "✨", "note": "Mid & senior level vacancies"},
        "Foundit":       {"color": "#9333ea", "icon": "🔮", "note": "Monster India — broad listings"},
        "Apna":          {"color": "#0891b2", "icon": "🤝", "note": "Blue collar & ground-level jobs"},
        "Freshersworld": {"color": "#059669", "icon": "🎓", "note": "Freshers & campus placements"},
        "TimesJobs":     {"color": "#dc2626", "icon": "📰", "note": "Times Group verified listings"},
        "Hirist":        {"color": "#0f172a", "icon": "💻", "note": "Tech-only quality roles"},
        "NaukriGulf":    {"color": "#b45309", "icon": "🌍", "note": "Gulf & Middle East openings"},
        "WorkIndia":     {"color": "#0369a1", "icon": "🏢", "note": "Blue collar & semi-skilled"},
    }
    cards = []
    for src in sources:
        meta    = PORTAL_META.get(src, {"color": "#6b7280", "icon": "🔍", "note": ""})
        builder = URL_BUILDERS.get(src)
        url     = builder(query, location) if builder else \
                  f"https://www.google.com/search?q={urllib.parse.quote(query + ' jobs ' + location)}"
        cards.append({
            "portal":       src,
            "color":        meta["color"],
            "icon":         meta["icon"],
            "note":         meta["note"],
            "search_url":   url,
            "query_label":  query,
            "category":     "general",
            "match_score":  0,
            "match_reason": "",
        })
    return cards


def ai_match_score_portal(portal_name, category_or_query, skills):
    if not skills:
        return 0, "Upload resume for match scores"
    try:
        raw = ai_call(
            [{"role": "system", "content": "Return only valid JSON."},
             {"role": "user", "content":
              f'How relevant is "{portal_name}" job portal for someone with skills: {", ".join(skills[:8])} '
              f'looking for "{category_or_query}" jobs in India? '
              f'Return: {{"score": 75, "reason": "one line reason"}}'}],
            max_tokens=60
        )
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return data.get("score", 50), data.get("reason", "")
    except Exception:
        return 50, "General match"


# ─────────────────────────────────────────────────────────────────────────────
# GOVT JOBS — Official portals only
# ─────────────────────────────────────────────────────────────────────────────

GOVT_OFFICIAL_PORTALS = [
    {"name": "NCS Portal",         "url": "https://www.ncs.gov.in/jobseeker/",                           "category": "central",  "color": "#FF6B35", "icon": "🏛️", "desc": "National Career Service — official govt job portal with lakhs of live vacancies"},
    {"name": "SSC",                 "url": "https://ssc.nic.in/",                                         "category": "central",  "color": "#FF6B35", "icon": "📋", "desc": "Staff Selection Commission — CGL, CHSL, MTS, GD Constable and more"},
    {"name": "UPSC",                "url": "https://upsc.gov.in/",                                        "category": "central",  "color": "#FF6B35", "icon": "🎓", "desc": "Civil Services, IAS, IPS, IFS, Engineering Services & Group A/B posts"},
    {"name": "Employment News",     "url": "https://employmentnews.gov.in/",                              "category": "central",  "color": "#FF6B35", "icon": "📰", "desc": "Official weekly gazette of all central & state government recruitments"},
    {"name": "Indian Railways RRB", "url": "https://indianrailways.gov.in/railwayboard/view_section.jsp?lang=0&id=0,1,304,366,533", "category": "railway", "color": "#4ECDC4", "icon": "🚂", "desc": "RRB NTPC, Group D, ALP, JE and all railway recruitment notifications"},
    {"name": "RRB Official",        "url": "https://www.rrbcdg.gov.in/",                                 "category": "railway",  "color": "#4ECDC4", "icon": "🚂", "desc": "Railway Recruitment Board — centralised recruitment for all zones"},
    {"name": "IBPS",                "url": "https://www.ibps.in/",                                        "category": "banking",  "color": "#45B7D1", "icon": "🏦", "desc": "Bank PO, Clerk, SO and RRB officer recruitment across public sector banks"},
    {"name": "SBI Careers",         "url": "https://bank.sbi/web/careers/current-openings",               "category": "banking",  "color": "#45B7D1", "icon": "🏦", "desc": "State Bank of India — PO, Clerk, Specialist Officer current openings"},
    {"name": "RBI Opportunities",   "url": "https://opportunities.rbi.org.in/Scripts/BS_ViewBulletin.aspx","category": "banking",  "color": "#45B7D1", "icon": "🏦", "desc": "Reserve Bank of India Grade B, Assistant and officer vacancies"},
    {"name": "NABARD",              "url": "https://www.nabard.org/content1.aspx?id=572&catid=23&mid=530", "category": "banking",  "color": "#45B7D1", "icon": "🏦", "desc": "National Bank — Grade A, B officer and development assistant posts"},
    {"name": "Join Indian Army",    "url": "https://joinindianarmy.nic.in/",                              "category": "defence",  "color": "#96CEB4", "icon": "🪖", "desc": "Indian Army — officer, soldier, Agniveer and technical entry recruitment"},
    {"name": "Join Indian Navy",    "url": "https://www.joinindiannavy.gov.in/",                          "category": "defence",  "color": "#96CEB4", "icon": "⚓", "desc": "Indian Navy — officer, sailor, Agniveer and MR recruitment"},
    {"name": "Indian Air Force",    "url": "https://afcat.cdac.in/AFCAT/",                                "category": "defence",  "color": "#96CEB4", "icon": "✈️", "desc": "IAF AFCAT — flying, technical and ground duty officer recruitment"},
    {"name": "DRDO",                "url": "https://www.drdo.gov.in/careers",                             "category": "defence",  "color": "#96CEB4", "icon": "🔬", "desc": "Defence Research — Scientist B, CEPTAM technician and admin posts"},
    {"name": "KVS Recruitment",     "url": "https://kvsangathan.nic.in/RecruitmentNotification",          "category": "teaching", "color": "#f59e0b", "icon": "📚", "desc": "Kendriya Vidyalaya — PRT, TGT, PGT teacher and principal vacancies"},
    {"name": "NVS Recruitment",     "url": "https://navodaya.gov.in/nvs/en/Recruitment/",                 "category": "teaching", "color": "#f59e0b", "icon": "📚", "desc": "Navodaya Vidyalaya — TGT, PGT, female staff nurse and misc posts"},
    {"name": "CTET",                "url": "https://ctet.nic.in/",                                        "category": "teaching", "color": "#f59e0b", "icon": "📝", "desc": "Central Teacher Eligibility Test — mandatory for KVS/NVS teacher posts"},
    {"name": "CRPF Recruitment",    "url": "https://crpf.gov.in/recruitment.htm",                        "category": "police",   "color": "#DDA0DD", "icon": "👮", "desc": "Central Reserve Police Force — constable, SI and assistant commandant"},
    {"name": "BSF Recruitment",     "url": "https://bsf.gov.in/recruitment.html",                        "category": "police",   "color": "#DDA0DD", "icon": "🛡️", "desc": "Border Security Force — constable, head constable and ASI vacancies"},
    {"name": "CISF Recruitment",    "url": "https://cisfrectt.cisf.gov.in/",                             "category": "police",   "color": "#DDA0DD", "icon": "🔒", "desc": "Central Industrial Security Force — constable and HC posts"},
    {"name": "TNPSC",               "url": "https://www.tnpsc.gov.in/notifications.html",                 "category": "state",    "color": "#98D8C8", "icon": "🏢", "desc": "Tamil Nadu PSC — Group 1, 2, 4, VAO, combined engineering services"},
    {"name": "UPPSC",               "url": "https://uppsc.up.nic.in/",                                   "category": "state",    "color": "#98D8C8", "icon": "🏢", "desc": "Uttar Pradesh PSC — PCS, combined state engineering and medical services"},
    {"name": "MPSC",                "url": "https://mpsc.gov.in/",                                        "category": "state",    "color": "#98D8C8", "icon": "🏢", "desc": "Maharashtra PSC — Rajyaseva, Police Sub Inspector, Clerk and other posts"},
    {"name": "KPSC",                "url": "https://kpsc.kar.nic.in/",                                    "category": "state",    "color": "#98D8C8", "icon": "🏢", "desc": "Karnataka PSC — Gazetted Probationers, FDA, SDA and Group C posts"},
]

GOVT_CATEGORY_META = {
    "all":      {"label": "All",           "icon": "🔍", "color": "#6C757D"},
    "central":  {"label": "Central Govt",  "icon": "🇮🇳", "color": "#FF6B35"},
    "railway":  {"label": "Railways",      "icon": "🚂",  "color": "#4ECDC4"},
    "banking":  {"label": "Banking / PSU", "icon": "🏦",  "color": "#45B7D1"},
    "defence":  {"label": "Defence",       "icon": "🪖",  "color": "#96CEB4"},
    "teaching": {"label": "Teaching",      "icon": "📚",  "color": "#f59e0b"},
    "police":   {"label": "Police / Para", "icon": "👮",  "color": "#DDA0DD"},
    "state":    {"label": "State Govt",    "icon": "🏢",  "color": "#98D8C8"},
}


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────────────────────

def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/landing.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        name     = request.POST.get('name', '').strip()
        if User.objects.filter(username=username).exists():
            return render(request, 'core/auth.html', {'error': 'Username already taken.', 'mode': 'register'})
        user = User.objects.create_user(username=username, email=email, password=password)
        parts = name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name  = parts[1] if len(parts) > 1 else ''
        user.save()
        UserProfile.objects.create(user=user)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'core/auth.html', {'mode': 'register'})

def login_view(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username', ''),
                            password=request.POST.get('password', ''))
        if user:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'core/auth.html', {'error': 'Invalid credentials.', 'mode': 'login'})
    return render(request, 'core/auth.html', {'mode': 'login'})

def logout_view(request):
    logout(request)
    return redirect('landing')

@login_required
def dashboard(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    skills = json.loads(profile.skills) if profile.skills else []
    return render(request, 'core/dashboard.html', {
        'profile': profile, 'skills': skills,
        'saved_count': SavedJob.objects.filter(user=request.user).count(),
        'has_resume': bool(profile.resume_text),
    })

@login_required
@csrf_exempt
def upload_resume(request):
    if request.method == 'POST':
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        resume_text = ''
        if 'resume_file' in request.FILES:
            f     = request.FILES['resume_file']
            fname = f.name.lower()
            try:
                if   fname.endswith('.pdf'):  resume_text = extract_text_from_pdf(f)
                elif fname.endswith('.docx'): resume_text = extract_text_from_docx(f)
                elif fname.endswith('.txt'):  resume_text = f.read().decode('utf-8')
                else: return JsonResponse({'error': 'Use PDF, DOCX or TXT'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)
        else:
            resume_text = request.POST.get('resume_text', '').strip()
        if not resume_text:
            return JsonResponse({'error': 'No resume content found.'}, status=400)
        try:
            extracted = ai_extract_skills(resume_text)
            profile.resume_text      = resume_text
            profile.skills           = json.dumps(extracted.get('skills', []))
            profile.experience_years = extracted.get('experience_years', 0)
            profile.location         = extracted.get('location', '')
            profile.job_title        = (extracted.get('job_titles') or [''])[0]
            profile.save()
            return JsonResponse({'success': True, 'extracted': extracted})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return render(request, 'core/upload.html')

@login_required
@csrf_exempt
def find_jobs(request):
    if request.method == 'POST':
        data     = json.loads(request.body)
        query    = data.get('query', '').strip()
        location = data.get('location', 'India').strip() or 'India'
        sources  = data.get('sources', ['LinkedIn','Naukri','Indeed','Internshala','Shine','Foundit','Apna','Freshersworld','TimesJobs','Hirist','NaukriGulf','WorkIndia'])
        category = data.get('category', 'all')

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        skills     = json.loads(profile.skills) if profile.skills else []

        if category and category != 'all':
            cards = get_portal_cards(category, query, location)
        else:
            if not query:
                return JsonResponse({'jobs': [], 'mode': 'search'})
            cards = get_general_search_cards(query, location, sources)

        for card in cards:
            score, reason = ai_match_score_portal(card['portal'], query or category, skills)
            card['match_score']  = score
            card['match_reason'] = reason

        cards.sort(key=lambda x: x['match_score'], reverse=True)
        return JsonResponse({'jobs': cards, 'mode': 'portals'})

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    skills = json.loads(profile.skills) if profile.skills else []
    return render(request, 'core/find_jobs.html', {
        'profile': profile, 'skills': skills, 'job_title': profile.job_title,
    })

@login_required
def govt_jobs(request):
    active_category = request.GET.get("category", "all")
    query           = request.GET.get("q", "").strip().lower()

    portals = list(GOVT_OFFICIAL_PORTALS)
    if active_category != "all":
        portals = [p for p in portals if p["category"] == active_category]
    if query:
        portals = [p for p in portals if query in p["name"].lower() or query in p["desc"].lower()]

    categories_list = []
    for key, meta in GOVT_CATEGORY_META.items():
        count = len(GOVT_OFFICIAL_PORTALS) if key == "all" else sum(1 for p in GOVT_OFFICIAL_PORTALS if p["category"] == key)
        categories_list.append({"key": key, "label": meta["label"], "icon": meta["icon"], "color": meta["color"], "count": count})

    return render(request, "core/govt_jobs.html", {
        "portals":         portals,
        "categories_list": categories_list,
        "active_category": active_category,
        "query":           query,
        "total":           len(portals),
    })

@login_required
@csrf_exempt
def save_job(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        SavedJob.objects.get_or_create(
            user=request.user, apply_url=data.get('apply_url', data.get('search_url', '')),
            defaults={
                'job_title':   data.get('query_label', data.get('title', '')),
                'company':     data.get('portal', data.get('company', '')),
                'location':    data.get('location', ''),
                'source':      data.get('portal', data.get('source', '')),
                'match_score': data.get('match_score', 0),
            }
        )
        return JsonResponse({'saved': True})

@login_required
def saved_jobs(request):
    return render(request, 'core/saved_jobs.html',
                  {'jobs': SavedJob.objects.filter(user=request.user).order_by('-saved_at')})

@login_required
@csrf_exempt
def generate_cover_letter(request):
    if request.method == 'POST':
        data       = json.loads(request.body)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        skills     = json.loads(profile.skills) if profile.skills else []
        name       = request.user.get_full_name() or request.user.username
        text = ai_call(
            [{"role": "user", "content":
              f"Write a 3-paragraph professional cover letter for {name} applying for "
              f"{data.get('job_title')} at {data.get('company')}. "
              f"Skills: {', '.join(skills[:10])}. Experience: {profile.experience_years} years. "
              f"ATS-friendly, confident, not over the top."}],
            max_tokens=600, temp=0.6)
        return JsonResponse({'cover_letter': text})

@login_required
def profile(request):
    prof, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name  = request.POST.get('last_name', '')
        request.user.email      = request.POST.get('email', '')
        request.user.save()
        prof.location         = request.POST.get('location', '')
        prof.job_title        = request.POST.get('job_title', '')
        prof.experience_years = int(request.POST.get('experience_years', 0) or 0)
        prof.whatsapp_number  = request.POST.get('whatsapp_number', '').strip()
        prof.save()
        messages.success(request, 'Profile updated!')
        return redirect('profile')
    skills = json.loads(prof.skills) if prof.skills else []
    return render(request, 'core/profile.html', {'prof': prof, 'skills': skills})


# ─────────────────────────────────────────────────────────────────────────────
# APPLICATION TRACKER
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tracker(request):
    if request.method == 'POST':
        ApplicationTracker.objects.create(
            user=request.user,
            job_title=request.POST.get('job_title','').strip(),
            company=request.POST.get('company','').strip(),
            location=request.POST.get('location','').strip(),
            apply_url=request.POST.get('apply_url','').strip(),
            status=request.POST.get('status','applied'),
            notes=request.POST.get('notes','').strip(),
        )
        messages.success(request, 'Application added!')
        return redirect('tracker')

    applications = ApplicationTracker.objects.filter(user=request.user).order_by('-created_at')
    columns = {
        'applied':      {'label':'Applied',     'icon':'📤','color':'#6366f1','items':[]},
        'interviewing': {'label':'Interviewing', 'icon':'🗣️','color':'#f59e0b','items':[]},
        'offered':      {'label':'Offered',      'icon':'🎉','color':'#10b981','items':[]},
        'rejected':     {'label':'Rejected',     'icon':'❌','color':'#ef4444','items':[]},
    }
    for app in applications:
        status = app.status if app.status in columns else 'applied'
        columns[status]['items'].append(app)

    return render(request, 'core/tracker.html', {
        'columns': columns, 'total': applications.count(),
        'status_choices': ApplicationTracker.STATUS_CHOICES,
    })

@login_required
@csrf_exempt
def tracker_update(request, pk):
    if request.method == 'POST':
        try:
            app  = ApplicationTracker.objects.get(pk=pk, user=request.user)
            data = json.loads(request.body)
            if 'status' in data: app.status = data['status']
            if 'notes'  in data: app.notes  = data['notes']
            app.save()
            return JsonResponse({'ok': True, 'status': app.status, 'notes': app.notes})
        except ApplicationTracker.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST only'}, status=405)

@login_required
@csrf_exempt
def tracker_delete(request, pk):
    if request.method == 'POST':
        try:
            ApplicationTracker.objects.get(pk=pk, user=request.user).delete()
            return JsonResponse({'ok': True})
        except ApplicationTracker.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'error': 'POST only'}, status=405)


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — RESUME TIPS AI
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def resume_tips(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    logger.info("resume_tips method=%s", request.method)

    # Build skills chips for the hero row
    skills_list = []
    if profile.skills:
        try:
            skills_list = json.loads(profile.skills)[:10]
        except (json.JSONDecodeError, TypeError):
            pass
 
    tips      = None
    error     = None
    generated = False
 
    if request.method == 'POST':
        if not profile.resume_text:
            error = "No resume found. Please upload your resume first."
        else:
            try:
                prompt = (
                    "You are an expert resume coach for the Indian job market. "
                    "Analyse this resume and return EXACTLY 5 actionable improvement tips "
                    "as a valid JSON array — NO markdown, NO preamble, ONLY the array.\n"
                    'Format: [{"tip_number":1,"category":"Impact","priority":"high",'
                    '"title":"Short title","detail":"2-3 sentence advice."}]\n'
                    'priority must be one of: "high", "medium", "low"\n\n'
                    f"Resume:\n{profile.resume_text[:2000]}"
                )
                raw = ai_call(
                    [
                        {"role": "system", "content": "Return only a valid JSON array, nothing else."},
                        {"role": "user",   "content": prompt},
                    ],
                    max_tokens=800,
                    temp=0.4,
                    timeout=25,
                )
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                raw = raw.strip()
 
                tips = json.loads(raw)
                if not isinstance(tips, list):
                    raise ValueError("AI returned a non-list JSON value")
 
                priority_styles = {
                    "high":   {"border": "#ef4444", "badge_bg": "#fef2f2", "badge_text": "#b91c1c"},
                    "medium": {"border": "#f59e0b", "badge_bg": "#fffbeb", "badge_text": "#92400e"},
                    "low":    {"border": "#10b981", "badge_bg": "#ecfdf5", "badge_text": "#065f46"},
                }
                for tip in tips:
                    pri = tip.get("priority", "medium").lower()
                    tip["priority"] = pri
                    tip["style"]    = priority_styles.get(pri, priority_styles["medium"])
 
                generated = True
 
            except json.JSONDecodeError as e:
                logger.error("resume_tips JSON parse error: %s | raw=%s", e, raw[:200])
                error = "AI returned unexpected format — please try again."
            except Exception as e:
                logger.error("resume_tips error: %s", e, exc_info=True)
                error = f"Error: {type(e).__name__}: {e}"
 
    logger.info("resume_tips render: generated=%s tips=%s error=%s", generated, bool(tips), error)
    return render(request, "core/resume_tips.html", {
        "profile":     profile,
        "tips":        tips,
        "error":       error,
        "generated":   generated,
        "skills_list": skills_list,
        "has_resume":  bool(profile.resume_text),
    })


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 — HIRER PLATFORM  (Razorpay field name mismatches fixed)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def post_job(request):
    """
    FIXES applied:
      • posted_by=  (was hirer=)
      • company_name        = request.POST.get("company_name", "").strip(),
      • salary_min/salary_max  (was salary_range= which doesn't exist on model)
      • how_to_apply        = request.POST.get("how_to_apply", "").strip(),
      • status="pending_payment"  (was is_active=True which doesn't exist on model)
      • razorpay_order_id=  (was order_id=)
      • razorpay_payment_id=  (was payment_id=)
      • calls rp_order.mark_paid() which also calls job.activate()
      • sends WhatsApp confirmation to hirer
    """
    import razorpay as rzp

    KEY_ID  = os.environ.get("RAZORPAY_KEY_ID",    "")
    KEY_SEC = os.environ.get("RAZORPAY_KEY_SECRET", "")
    AMOUNT  = 99900   # paise = ₹999

    if request.method == "POST":
        order_id   = request.POST.get("razorpay_order_id",   "")
        payment_id = request.POST.get("razorpay_payment_id", "")
        signature  = request.POST.get("razorpay_signature",  "")

        # 1. Verify signature
        try:
            rzp.Client(auth=(KEY_ID, KEY_SEC)).utility.verify_payment_signature({
                "razorpay_order_id":   order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature":  signature,
            })
        except Exception as e:
            logger.warning("Razorpay verify failed: %s", e)
            messages.error(request, "Payment verification failed. Please contact support.")
            return redirect("post_job")

        # 2. Parse optional salary range ("50000-80000" or "60000")
        ssalary_min = salary_max = None
        try:
            salary_min = int(request.POST.get("salary_min", "") or 0) or None
            salary_max = int(request.POST.get("salary_max", "") or 0) or None
        except (ValueError, TypeError):
            pass

        # 3. Create JobPosting with correct field names
        job = JobPosting.objects.create(
            posted_by           = request.user,
            title               = request.POST.get("title", "").strip(),
            company_name        = request.POST.get("company", "").strip(),
            location            = request.POST.get("location", "").strip(),
            job_type            = request.POST.get("job_type", "full_time"),
            experience_required = request.POST.get("experience_required", "any"),
            salary_min          = salary_min,
            salary_max          = salary_max,
            skills_required     = request.POST.get("skills_required", "").strip(),
            description         = request.POST.get("description", "").strip(),
            how_to_apply        = request.POST.get("apply_url", "").strip(),
            status              = "pending_payment",
        )

        # 4. Record payment + activate listing (30 days)
        rp_order = RazorpayOrder.objects.create(
            user                = request.user,
            job_posting         = job,
            razorpay_order_id   = order_id,
            razorpay_payment_id = payment_id,
            razorpay_signature  = signature,
            amount              = AMOUNT,
            currency            = "INR",
            status              = "created",
        )
        rp_order.mark_paid(payment_id, signature)

        # 5. WhatsApp confirmation to hirer
        try:
            prof = UserProfile.objects.get(user=request.user)
            if prof.whatsapp_number:
                send_whatsapp(
                    prof.whatsapp_number,
                    f"✅ JobLens: Your job *{job.title}* at *{job.company_name}* "
                    f"is now LIVE for 30 days!\nOrder: {order_id}\nAmount paid: ₹999"
                )
        except UserProfile.DoesNotExist:
            pass

        logger.info("Job posted id=%s by %s order=%s", job.id, request.user, order_id)
        messages.success(request, f"✅ '{job.title}' is now live! Valid for 30 days.")
        return redirect("hirer_dashboard")

    # GET — create Razorpay order
    razorpay_order_id = ""
    razorpay_error    = ""
    try:
        order = rzp.Client(auth=(KEY_ID, KEY_SEC)).order.create({
            "amount": AMOUNT, "currency": "INR", "payment_capture": 1,
            "notes": {"source": "JobLens hirer platform"},
        })
        razorpay_order_id = order["id"]
    except Exception as e:
        logger.error("Razorpay order creation failed: %s", e)
        razorpay_error = "Payment gateway unavailable — please try again later."

    return render(request, "core/post_job.html", {
        "razorpay_key_id":   KEY_ID,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_error":    razorpay_error,
        "price":             "999",
        "amount_paise":      AMOUNT,
    })


@login_required
def hirer_dashboard(request):
    jobs = JobPosting.objects.filter(posted_by=request.user).order_by("-created_at")
    return render(request, "core/hirer_dashboard.html", {"jobs": jobs})
