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

MODEL = "llama-3.3-70b-versatile"

# ── Government RSS Feeds ───────────────────────────────────────────────────────
GOVT_RSS_FEEDS_LIST = [
    {"url": "https://www.sarkariresult.com/feed/",                "source": "SarkariResult",   "category": "government"},
    {"url": "https://www.govtjobsblog.in/feed/",                  "source": "GovtJobsBlog",    "category": "government"},
    {"url": "https://www.freejobalert.com/feed/",                 "source": "FreeJobAlert",    "category": "government"},
    {"url": "https://ibps.in/feed/",                              "source": "IBPS",            "category": "banking"},
    {"url": "https://www.sbi.co.in/web/careers/rss",              "source": "SBI Careers",     "category": "banking"},
    {"url": "https://indianrailways.gov.in/railwayboard/rss.jsp", "source": "Indian Railways", "category": "railways"},
    {"url": "https://www.ncs.gov.in/jobseeker/rss",               "source": "NCS Portal",      "category": "government"},
]

# ── Category-specific searches ─────────────────────────────────────────────────
CATEGORY_SEARCHES = {
    "hotel": [
        {"query": "hotel jobs india",              "source_color": "#f59e0b"},
        {"query": "hospitality jobs india",        "source_color": "#f59e0b"},
        {"query": "front desk hotel india",        "source_color": "#f59e0b"},
        {"query": "housekeeping supervisor india", "source_color": "#f59e0b"},
        {"query": "chef jobs india",               "source_color": "#f59e0b"},
    ],
    "airport": [
        {"query": "airport jobs india",            "source_color": "#0ea5e9"},
        {"query": "ground staff airport india",    "source_color": "#0ea5e9"},
        {"query": "cabin crew jobs india",         "source_color": "#0ea5e9"},
        {"query": "aviation jobs india",           "source_color": "#0ea5e9"},
        {"query": "air hostess jobs india",        "source_color": "#0ea5e9"},
    ],
    "healthcare": [
        {"query": "doctor jobs india",             "source_color": "#ef4444"},
        {"query": "nurse jobs india",              "source_color": "#ef4444"},
        {"query": "hospital jobs india",           "source_color": "#ef4444"},
        {"query": "pharmacist jobs india",         "source_color": "#ef4444"},
        {"query": "lab technician jobs india",     "source_color": "#ef4444"},
    ],
    "education": [
        {"query": "teacher jobs india",            "source_color": "#8b5cf6"},
        {"query": "professor jobs india",          "source_color": "#8b5cf6"},
        {"query": "school teacher india",          "source_color": "#8b5cf6"},
        {"query": "edtech jobs india",             "source_color": "#8b5cf6"},
        {"query": "tutor jobs india",              "source_color": "#8b5cf6"},
    ],
    "retail": [
        {"query": "retail jobs india",             "source_color": "#10b981"},
        {"query": "store manager india",           "source_color": "#10b981"},
        {"query": "sales associate india",         "source_color": "#10b981"},
        {"query": "showroom jobs india",           "source_color": "#10b981"},
    ],
    "logistics": [
        {"query": "logistics jobs india",          "source_color": "#6366f1"},
        {"query": "driver jobs india",             "source_color": "#6366f1"},
        {"query": "delivery jobs india",           "source_color": "#6366f1"},
        {"query": "warehouse jobs india",          "source_color": "#6366f1"},
        {"query": "supply chain jobs india",       "source_color": "#6366f1"},
    ],
    "manufacturing": [
        {"query": "manufacturing jobs india",      "source_color": "#78716c"},
        {"query": "production engineer india",     "source_color": "#78716c"},
        {"query": "quality control india",         "source_color": "#78716c"},
        {"query": "plant manager india",           "source_color": "#78716c"},
    ],
    "security": [
        {"query": "security guard jobs india",     "source_color": "#475569"},
        {"query": "security supervisor india",     "source_color": "#475569"},
        {"query": "security officer india",        "source_color": "#475569"},
    ],
    "bluecollar": [
        {"query": "electrician jobs india",        "source_color": "#d97706"},
        {"query": "plumber jobs india",            "source_color": "#d97706"},
        {"query": "carpenter jobs india",          "source_color": "#d97706"},
        {"query": "welder jobs india",             "source_color": "#d97706"},
        {"query": "mechanic jobs india",           "source_color": "#d97706"},
    ],
    "media": [
        {"query": "journalist jobs india",         "source_color": "#ec4899"},
        {"query": "content writer jobs india",     "source_color": "#ec4899"},
        {"query": "video editor jobs india",       "source_color": "#ec4899"},
        {"query": "media jobs india",              "source_color": "#ec4899"},
    ],
    "legal": [
        {"query": "lawyer jobs india",             "source_color": "#1e3a5f"},
        {"query": "legal advisor india",           "source_color": "#1e3a5f"},
        {"query": "company secretary india",       "source_color": "#1e3a5f"},
        {"query": "compliance officer india",      "source_color": "#1e3a5f"},
    ],
    "realestate": [
        {"query": "real estate jobs india",        "source_color": "#059669"},
        {"query": "property consultant india",     "source_color": "#059669"},
        {"query": "site engineer india",           "source_color": "#059669"},
        {"query": "civil engineer jobs india",     "source_color": "#059669"},
    ],
}

GOVT_RSS_FEEDS_PAGE = {
    "sarkari_result":  {"url": "https://www.sarkariresult.com/feed/",                                    "label": "Sarkari Result",  "icon": "🏛️"},
    "employment_news": {"url": "https://www.employmentnews.gov.in/rss/rss.xml",                          "label": "Employment News", "icon": "📰"},
    "upsc":            {"url": "https://www.upsc.gov.in/rss.xml",                                        "label": "UPSC",            "icon": "🎓"},
    "ssc":             {"url": "https://ssc.nic.in/SSCFileServer/PortalManagement/UploadedFiles/rss.xml","label": "SSC",             "icon": "📋"},
    "railway_rrb":     {"url": "https://rrbcdg.gov.in/rss/recruitment.xml",                              "label": "Railway (RRB)",   "icon": "🚂"},
    "banking_ibps":    {"url": "https://www.ibps.in/rss.xml",                                            "label": "IBPS / Banking",  "icon": "🏦"},
    "naukri_govt":     {"url": "https://www.naukri.com/rss/jobs/government-jobs",                        "label": "Naukri Govt",     "icon": "💼"},
}

CATEGORY_META = {
    "central":  {"label": "Central Govt",  "icon": "🇮🇳", "color": "#FF6B35"},
    "railway":  {"label": "Railways",      "icon": "🚂",  "color": "#4ECDC4"},
    "banking":  {"label": "Banking / PSU", "icon": "🏦",  "color": "#45B7D1"},
    "defence":  {"label": "Defence",       "icon": "🪖",  "color": "#96CEB4"},
    "teaching": {"label": "Teaching",      "icon": "📚",  "color": "#FFEAA7"},
    "police":   {"label": "Police / Para", "icon": "👮",  "color": "#DDA0DD"},
    "state":    {"label": "State Govt",    "icon": "🏢",  "color": "#98D8C8"},
    "all":      {"label": "All",           "icon": "🔍",  "color": "#6C757D"},
}

CATEGORY_KEYWORDS = {
    "railway":  ["railway", "rrb", "rrb-ntpc", "loco pilot", "station master"],
    "banking":  ["bank", "ibps", "sbi", "rbi", "nabard", "psu"],
    "defence":  ["army", "navy", "air force", "defence", "crpf", "bsf", "cisf", "nda", "cds"],
    "teaching": ["teacher", "tgt", "pgt", "lecturer", "professor", "tet", "ctet"],
    "police":   ["police", "constable", "si", "sub-inspector", "paramilitary"],
    "state":    ["state", "state psc", "state board", "municipal", "panchayat"],
    "central":  ["upsc", "ssc", "ias", "ips", "central", "ministry", "government of india"],
}


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

def ai_call(messages_list, max_tokens=500, temp=0.1):
    client = get_groq()
    r = client.chat.completions.create(
        model=MODEL, messages=messages_list, max_tokens=max_tokens, temperature=temp)
    return r.choices[0].message.content.strip()

def ai_extract_skills(resume_text):
    prompt = f"""Extract from this resume. Return ONLY valid JSON, no markdown:
{{"skills":["skill1"],"job_titles":["title1"],"experience_years":0,"location":"city","summary":"2 sentence summary"}}
Resume:{resume_text[:3000]}"""
    raw = ai_call([{"role": "system", "content": "Return only valid JSON."},
                   {"role": "user", "content": prompt}])
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def _categorise_govt_job(title, summary):
    text = (title + " " + summary).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "central"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ─────────────────────────────────────────────────────────────────────────────
# JOB SCRAPERS
# ─────────────────────────────────────────────────────────────────────────────

def search_linkedin_jobs(query, location="India", num=10):
    jobs = []
    try:
        url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}&f_TPR=r86400"
        r = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="base-card")[:num]:
            t = card.find("h3", class_="base-search-card__title")
            c = card.find("h4", class_="base-search-card__subtitle")
            l = card.find("span", class_="job-search-card__location")
            a = card.find("a", class_="base-card__full-link")
            if t and a:
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else location,
                             "apply_url": a.get("href", "#"),
                             "source": "LinkedIn", "source_color": "#0077b5"})
    except: pass
    return jobs

def search_naukri_jobs(query, location="India", num=10):
    jobs = []
    try:
        slug = query.lower().replace(" ", "-")
        loc  = location.lower().replace(" ", "-")
        r = requests.get(f"https://www.naukri.com/{slug}-jobs-in-{loc}",
                         headers={**HEADERS, "Accept-Language": "en-US"}, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("article", class_="jobTuple")[:num]:
            t = card.find("a", class_="title")
            c = card.find("a", class_="subTitle")
            l = card.find("li", class_="location")
            if t:
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else location,
                             "apply_url": t.get("href", f"https://www.naukri.com/{slug}-jobs"),
                             "source": "Naukri", "source_color": "#ef4444"})
    except: pass
    return jobs

def search_indeed_jobs(query, location="India", num=10):
    jobs = []
    try:
        url = f"https://in.indeed.com/jobs?q={urllib.parse.quote(query)}&l={urllib.parse.quote(location)}&fromage=7"
        r = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="job_seen_beacon")[:num]:
            t = card.find("h2", class_="jobTitle")
            c = card.find("span", {"data-testid": "company-name"})
            l = card.find("div", {"data-testid": "text-location"})
            a = card.find("a", class_="jcs-JobTitle")
            if t:
                href = a.get("href", "") if a else ""
                url2 = f"https://in.indeed.com{href}" if href.startswith("/") else href or f"https://in.indeed.com/jobs?q={urllib.parse.quote(query)}"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else location,
                             "apply_url": url2,
                             "source": "Indeed", "source_color": "#003A9B"})
    except: pass
    return jobs

def search_internshala_jobs(query, num=10):
    jobs = []
    try:
        slug = urllib.parse.quote(query.lower().replace(" ", "-"))
        r = requests.get(f"https://internshala.com/jobs/{slug}-jobs",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="individual_internship")[:num]:
            t = card.find("h3", class_="job-internship-name")
            c = card.find("p", class_="company-name")
            l = card.find("p", class_="locations")
            a = card.find("a", class_="view_detail_button")
            if t:
                href = a.get("href", "") if a else ""
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else "India",
                             "apply_url": f"https://internshala.com{href}" if href else "https://internshala.com/jobs",
                             "source": "Internshala", "source_color": "#16a34a"})
    except: pass
    return jobs

def search_shine_jobs(query, location="India", num=10):
    jobs = []
    try:
        q = urllib.parse.quote(query)
        l = urllib.parse.quote(location)
        r = requests.get(f"https://www.shine.com/job-search/{q.lower().replace('%20','-')}-jobs-in-{l.lower().replace('%20','-')}",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="jobCard")[:num]:
            t = card.find("h3") or card.find("a", class_="jobTitle")
            c = card.find("span", class_="companyName") or card.find("p", class_="company")
            a = card.find("a", href=True)
            if t:
                href = a["href"] if a else ""
                url2 = f"https://www.shine.com{href}" if href.startswith("/") else href or "https://www.shine.com"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": location, "apply_url": url2,
                             "source": "Shine", "source_color": "#7c3aed"})
    except: pass
    return jobs

def search_foundit_jobs(query, location="India", num=10):
    """Foundit (formerly Monster India)"""
    jobs = []
    try:
        q = urllib.parse.quote(query)
        r = requests.get(f"https://www.foundit.in/srp/results?query={q}&location={urllib.parse.quote(location)}",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="cardContainer")[:num]:
            t = card.find("h3", class_="jobTitle") or card.find("a", class_="jobTitle")
            c = card.find("span", class_="companyName")
            l = card.find("span", class_="location")
            a = card.find("a", href=True)
            if t:
                href = a["href"] if a else ""
                url2 = f"https://www.foundit.in{href}" if href.startswith("/") else href or "https://www.foundit.in"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else location,
                             "apply_url": url2,
                             "source": "Foundit", "source_color": "#9333ea"})
    except: pass
    return jobs

def search_apna_jobs(query, num=10):
    """Apna.co — best for blue collar and field sales"""
    jobs = []
    try:
        q = urllib.parse.quote(query)
        r = requests.get(f"https://apna.co/jobs?q={q}",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", {"class": lambda c: c and "JobCard" in c})[:num]:
            t = card.find("h2") or card.find("h3")
            c = card.find("p")
            a = card.find("a", href=True)
            if t:
                href = a["href"] if a else ""
                url2 = f"https://apna.co{href}" if href.startswith("/") else href or f"https://apna.co/jobs?q={q}"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": "India", "apply_url": url2,
                             "source": "Apna", "source_color": "#0891b2"})
    except: pass
    return jobs

def search_freshersworld_jobs(query, num=10):
    """Freshersworld — freshers and entry-level"""
    jobs = []
    try:
        q = query.lower().replace(" ", "-")
        r = requests.get(f"https://www.freshersworld.com/jobs/jobsearch/{q}-jobs",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="joblist-comp-box")[:num]:
            t = card.find("h3") or card.find("a", class_="job-title")
            c = card.find("span", class_="company-name")
            l = card.find("span", class_="location")
            a = card.find("a", href=True)
            if t:
                href = a["href"] if a else ""
                url2 = f"https://www.freshersworld.com{href}" if href.startswith("/") else href or "https://www.freshersworld.com"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else "India",
                             "apply_url": url2,
                             "source": "Freshersworld", "source_color": "#059669"})
    except: pass
    return jobs

def search_timesjobs(query, location="India", num=10):
    jobs = []
    try:
        q = urllib.parse.quote(query)
        l = urllib.parse.quote(location)
        r = requests.get(f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={q}&txtLocation={l}",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("li", class_="clearfix job-bx wht-shd-bx")[:num]:
            t = card.find("h2")
            c = card.find("h3", class_="joblist-comp-name")
            l_tag = card.find("span", class_="srp-skills")
            a = card.find("a", href=True)
            if t:
                href = a["href"] if a else ""
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": location, "apply_url": href or "https://www.timesjobs.com",
                             "source": "TimesJobs", "source_color": "#dc2626"})
    except: pass
    return jobs

def search_hirist_jobs(query, num=10):
    """Hirist — tech-only jobs"""
    jobs = []
    try:
        q = urllib.parse.quote(query)
        r = requests.get(f"https://www.hirist.tech/s/{q}",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="job-card")[:num]:
            t = card.find("h2") or card.find("h3")
            c = card.find("p", class_="company")
            l = card.find("span", class_="location")
            a = card.find("a", href=True)
            if t:
                href = a["href"] if a else ""
                url2 = f"https://www.hirist.tech{href}" if href.startswith("/") else href or "https://www.hirist.tech"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else "India",
                             "apply_url": url2,
                             "source": "Hirist", "source_color": "#0f172a"})
    except: pass
    return jobs

def search_naukrigulf_jobs(query, num=10):
    """NaukriGulf — Gulf/Middle East jobs"""
    jobs = []
    try:
        q = urllib.parse.quote(query)
        r = requests.get(f"https://www.naukrigulf.com/{query.lower().replace(' ','-')}-jobs",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="ng-star-inserted")[:num]:
            t = card.find("a", class_="desig")
            c = card.find("label", class_="company-name")
            l = card.find("span", class_="loc-time-wrap")
            if t:
                href = t.get("href", "")
                url2 = f"https://www.naukrigulf.com{href}" if href.startswith("/") else href or "https://www.naukrigulf.com"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else "Gulf",
                             "apply_url": url2,
                             "source": "NaukriGulf", "source_color": "#b45309"})
    except: pass
    return jobs

def search_workindia_jobs(query, num=10):
    """WorkIndia — blue collar & semi-skilled"""
    jobs = []
    try:
        q = urllib.parse.quote(query)
        r = requests.get(f"https://www.workindia.in/job-search?q={q}",
                         headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", {"class": lambda c: c and "job" in c.lower()})[:num]:
            t = card.find("h2") or card.find("h3") or card.find("p", class_="title")
            c = card.find("span", class_="company") or card.find("p", class_="company")
            a = card.find("a", href=True)
            if t and t.text.strip():
                href = a["href"] if a else ""
                url2 = f"https://www.workindia.in{href}" if href.startswith("/") else href or f"https://www.workindia.in/job-search?q={q}"
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": "India", "apply_url": url2,
                             "source": "WorkIndia", "source_color": "#0369a1"})
    except: pass
    return jobs


def fetch_govt_rss_jobs(category_filter=None, max_per_feed=25):
    all_jobs = []
    for feed_info in GOVT_RSS_FEEDS_LIST:
        if category_filter and feed_info["category"] != category_filter:
            continue
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:max_per_feed]:
                all_jobs.append({
                    "title":        entry.get("title", "Government Job"),
                    "company":      feed_info["source"],
                    "location":     "India",
                    "apply_url":    entry.get("link", "#"),
                    "source":       feed_info["source"],
                    "source_color": "#1d4ed8",
                    "category":     feed_info["category"],
                    "published":    entry.get("published", ""),
                })
        except: pass
    return all_jobs

def fetch_category_jobs(category, location="India", num_per_query=6):
    all_jobs = []
    searches = CATEGORY_SEARCHES.get(category, [])
    for s in searches[:4]:
        q     = s["query"]
        color = s.get("source_color", "#6b7280")
        for job in search_indeed_jobs(q, location, num=num_per_query):
            job["category"] = category; job["source_color"] = color; all_jobs.append(job)
        for job in search_naukri_jobs(q, location, num=num_per_query):
            job["category"] = category; job["source_color"] = color; all_jobs.append(job)
        for job in search_shine_jobs(q, location, num=num_per_query):
            job["category"] = category; job["source_color"] = color; all_jobs.append(job)
    return all_jobs

def ai_match_score(job_title, company, skills):
    if not skills:
        return {"score": 0, "reason": "Upload resume for match scores"}
    try:
        raw = ai_call([{"role": "system", "content": "Return only valid JSON."},
                       {"role": "user", "content": f'Rate match 0-100. Skills:{",".join(skills[:10])} Job:{job_title} at {company}. Return:{{"score":75,"reason":"one line"}}'}],
                      max_tokens=80)
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except:
        return {"score": 50, "reason": "General match"}

def ai_fallback_jobs(query, location):
    try:
        raw = ai_call([{"role": "system", "content": "Return only valid JSON array."},
                       {"role": "user", "content": f'Generate 10 realistic job listings for "{query}" in {location} India. JSON array:[{{"title":"","company":"","location":"City, India","apply_url":"https://linkedin.com/jobs","source":"LinkedIn","source_color":"#0077b5","category":"whitecollar"}}]'}],
                      max_tokens=1000, temp=0.5)
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except:
        return []


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
            f = request.FILES['resume_file']
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
        query    = data.get('query', '')
        location = data.get('location', 'India')
        sources  = data.get('sources', ['LinkedIn','Naukri','Indeed','Internshala','Shine','Foundit','Apna','Freshersworld','TimesJobs','Hirist','NaukriGulf','WorkIndia'])
        category = data.get('category', 'all')

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        skills     = json.loads(profile.skills) if profile.skills else []
        all_jobs   = []

        if category == 'government':
            all_jobs += fetch_govt_rss_jobs(category_filter='government')
        elif category == 'banking':
            all_jobs += fetch_govt_rss_jobs(category_filter='banking')
        elif category == 'railways':
            all_jobs += fetch_govt_rss_jobs(category_filter='railways')
        elif category in CATEGORY_SEARCHES:
            all_jobs += fetch_category_jobs(category, location)
        else:
            if 'LinkedIn'      in sources: all_jobs += search_linkedin_jobs(query, location)
            if 'Naukri'        in sources: all_jobs += search_naukri_jobs(query, location)
            if 'Indeed'        in sources: all_jobs += search_indeed_jobs(query, location)
            if 'Internshala'   in sources: all_jobs += search_internshala_jobs(query)
            if 'Shine'         in sources: all_jobs += search_shine_jobs(query, location)
            if 'Foundit'       in sources: all_jobs += search_foundit_jobs(query, location)
            if 'Apna'          in sources: all_jobs += search_apna_jobs(query)
            if 'Freshersworld' in sources: all_jobs += search_freshersworld_jobs(query)
            if 'TimesJobs'     in sources: all_jobs += search_timesjobs(query, location)
            if 'Hirist'        in sources: all_jobs += search_hirist_jobs(query)
            if 'NaukriGulf'    in sources: all_jobs += search_naukrigulf_jobs(query)
            if 'WorkIndia'     in sources: all_jobs += search_workindia_jobs(query)
            all_jobs += fetch_govt_rss_jobs(max_per_feed=3)

        if not all_jobs:
            all_jobs = ai_fallback_jobs(query, location)

        for job in all_jobs:
            m = ai_match_score(job['title'], job.get('company', ''), skills)
            job['match_score']  = m.get('score', 0)
            job['match_reason'] = m.get('reason', '')

        all_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        return JsonResponse({'jobs': all_jobs})

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    skills = json.loads(profile.skills) if profile.skills else []
    return render(request, 'core/find_jobs.html', {
        'profile': profile, 'skills': skills, 'job_title': profile.job_title,
    })

@login_required
def govt_jobs(request):
    active_category = request.GET.get("category", "all")
    query           = request.GET.get("q", "").strip().lower()

    FALLBACK_JOBS = [
        {"title": "SSC CGL 2025 — Combined Graduate Level Recruitment",         "summary": "Staff Selection Commission invites applications for Group B and C posts across central government departments.",          "link": "https://ssc.nic.in",                "pub_date": "2025", "source": "SSC",             "source_icon": "📋", "category": "central"},
        {"title": "UPSC Civil Services 2025 — IAS IPS IFS Recruitment",         "summary": "Union Public Service Commission annual civil services examination for IAS, IPS, IFS and allied services.",               "link": "https://upsc.gov.in",               "pub_date": "2025", "source": "UPSC",            "source_icon": "🎓", "category": "central"},
        {"title": "IBPS PO 2025 — Probationary Officer Recruitment",            "summary": "Institute of Banking Personnel Selection recruitment for Probationary Officers in public sector banks.",                   "link": "https://ibps.in",                   "pub_date": "2025", "source": "IBPS / Banking",  "source_icon": "🏦", "category": "banking"},
        {"title": "SBI PO 2025 — State Bank Probationary Officers",             "summary": "State Bank of India recruitment for Probationary Officers in Junior Management Grade Scale I.",                           "link": "https://sbi.co.in/careers",         "pub_date": "2025", "source": "SBI Careers",     "source_icon": "🏦", "category": "banking"},
        {"title": "RRB NTPC 2025 — Railway Non-Technical Popular Categories",   "summary": "Indian Railways RRB recruitment for NTPC posts including Junior Clerk, Accounts Clerk and more.",                        "link": "https://indianrailways.gov.in",     "pub_date": "2025", "source": "Railway (RRB)",   "source_icon": "🚂", "category": "railway"},
        {"title": "RRB Group D 2025 — Railway Track Maintainer & Helper Posts", "summary": "Railway Recruitment Board Group D recruitment for Track Maintainer, Helper and Level 1 posts.",                          "link": "https://rrbcdg.gov.in",             "pub_date": "2025", "source": "Railway (RRB)",   "source_icon": "🚂", "category": "railway"},
        {"title": "Indian Army Agniveer 2025 — Soldier Recruitment",            "summary": "Indian Army recruitment under Agnipath scheme for Agniveer General Duty, Technical and Clerk posts.",                     "link": "https://joinindianarmy.nic.in",     "pub_date": "2025", "source": "Defence",         "source_icon": "🪖", "category": "defence"},
        {"title": "Indian Navy Agniveer MR 2025 — Matric Recruit",              "summary": "Indian Navy recruitment for Agniveer Matric Recruit posts in Chef, Steward and Hydrographic Survey branches.",           "link": "https://joinindiannavy.gov.in",     "pub_date": "2025", "source": "Defence",         "source_icon": "🪖", "category": "defence"},
        {"title": "CRPF Constable 2025 — Central Reserve Police Force",         "summary": "CRPF recruitment for Constable Technical and Tradesman posts across various specialisations.",                            "link": "https://crpf.gov.in",               "pub_date": "2025", "source": "Police / Para",   "source_icon": "👮", "category": "police"},
        {"title": "BSF Head Constable 2025 — Border Security Force",            "summary": "Border Security Force recruitment for Head Constable Radio Operator and Radio Mechanic posts.",                          "link": "https://bsf.gov.in",                "pub_date": "2025", "source": "Police / Para",   "source_icon": "👮", "category": "police"},
        {"title": "KVS TGT PGT 2025 — Kendriya Vidyalaya Teachers",            "summary": "Kendriya Vidyalaya Sangathan recruitment for Trained Graduate Teachers and Post Graduate Teachers.",                      "link": "https://kvsangathan.nic.in",        "pub_date": "2025", "source": "Teaching",        "source_icon": "📚", "category": "teaching"},
        {"title": "NVS TGT 2025 — Navodaya Vidyalaya Teachers",                "summary": "Navodaya Vidyalaya Samiti recruitment for Trained Graduate Teachers in various subjects.",                               "link": "https://navodaya.gov.in",           "pub_date": "2025", "source": "Teaching",        "source_icon": "📚", "category": "teaching"},
        {"title": "TNPSC Group 2 2025 — Tamil Nadu Public Service Commission",  "summary": "TNPSC recruitment for Group 2 posts including Deputy Commercial Tax Officer, Revenue Divisional Officer.",              "link": "https://tnpsc.gov.in",              "pub_date": "2025", "source": "State Govt",      "source_icon": "🏢", "category": "state"},
        {"title": "TNPSC Group 4 2025 — VAO and Junior Assistant Posts",        "summary": "TNPSC Village Administrative Officer and Junior Assistant recruitment across Tamil Nadu.",                                "link": "https://tnpsc.gov.in",              "pub_date": "2025", "source": "State Govt",      "source_icon": "🏢", "category": "state"},
        {"title": "NCS Portal — National Career Service — Latest Govt Jobs",    "summary": "Browse thousands of verified government and public sector jobs across India on the official NCS portal.",                "link": "https://www.ncs.gov.in",            "pub_date": "2025", "source": "NCS Portal",      "source_icon": "🏛️", "category": "central"},
        {"title": "Employment News — Latest Recruitment Notifications 2025",    "summary": "Official Employment News listing all central and state government recruitment notifications.",                           "link": "https://employmentnews.gov.in",     "pub_date": "2025", "source": "Employment News", "source_icon": "📰", "category": "central"},
        {"title": "RBI Grade B 2025 — Reserve Bank of India Officers",          "summary": "Reserve Bank of India recruitment for Grade B officers in General, DEPR and DSIM departments.",                         "link": "https://rbi.org.in/careers",        "pub_date": "2025", "source": "IBPS / Banking",  "source_icon": "🏦", "category": "banking"},
        {"title": "NABARD Grade A 2025 — Agriculture Development Bank",         "summary": "National Bank for Agriculture and Rural Development recruitment for Assistant Manager Grade A.",                         "link": "https://nabard.org",                "pub_date": "2025", "source": "IBPS / Banking",  "source_icon": "🏦", "category": "banking"},
        {"title": "SSC CHSL 2025 — Combined Higher Secondary Level",            "summary": "SSC recruitment for LDC, JSA, PA, SA and DEO posts for Class 12 pass candidates.",                                      "link": "https://ssc.nic.in",                "pub_date": "2025", "source": "SSC",             "source_icon": "📋", "category": "central"},
        {"title": "DRDO Scientist B 2025 — Defence Research Recruitment",       "summary": "Defence Research and Development Organisation recruitment for Scientist B posts in technical disciplines.",               "link": "https://drdo.gov.in",               "pub_date": "2025", "source": "Defence",         "source_icon": "🪖", "category": "defence"},
    ]

    all_jobs = list(FALLBACK_JOBS)
    import socket; socket.setdefaulttimeout(3)
    for feed_meta in GOVT_RSS_FEEDS_PAGE.values():
        try:
            feed = feedparser.parse(feed_meta["url"])
            for entry in feed.entries[:25]:
                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                if title and title != "Untitled":
                    all_jobs.append({
                        "title":       title,
                        "summary":     summary[:200] + "…" if len(summary) > 200 else summary,
                        "link":        getattr(entry, "link", "#"),
                        "pub_date":    getattr(entry, "published", ""),
                        "source":      feed_meta["label"],
                        "source_icon": feed_meta["icon"],
                        "category":    _categorise_govt_job(title, summary),
                    })
        except: pass

    if active_category != "all":
        all_jobs = [j for j in all_jobs if j["category"] == active_category]
    if query:
        all_jobs = [j for j in all_jobs if query in j["title"].lower() or query in j["summary"].lower()]

    # Build a flat list of (key, meta, count) so the template never needs dict[variable_key]
    all_count = len(all_jobs)
    categories_list = []
    for cat_key, meta in CATEGORY_META.items():
        if cat_key == "all":
            count = all_count
        else:
            count = sum(1 for j in all_jobs if j["category"] == cat_key)
        categories_list.append({
            "key":    cat_key,
            "label":  meta["label"],
            "icon":   meta["icon"],
            "color":  meta["color"],
            "count":  count,
        })

    return render(request, "core/govt_jobs.html", {
        "jobs":            all_jobs,
        "categories_list": categories_list,
        "active_category": active_category,
        "query":           query,
        "total":           all_count,
    })

@login_required
@csrf_exempt
def save_job(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        SavedJob.objects.get_or_create(
            user=request.user, apply_url=data.get('apply_url'),
            defaults={'job_title': data.get('title',''), 'company': data.get('company',''),
                      'location': data.get('location',''), 'source': data.get('source',''),
                      'match_score': data.get('match_score', 0)}
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
              f"ATS-friendly, confident but not over the top."}],
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
        prof.save()
        messages.success(request, 'Profile updated!')
        return redirect('profile')
    skills = json.loads(prof.skills) if prof.skills else []
    return render(request, 'core/profile.html', {'prof': prof, 'skills': skills})


# =============================================================================
# APPLICATION TRACKER
# =============================================================================

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


# =============================================================================
# RESUME TIPS AI
# =============================================================================

@login_required
def resume_tips(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    tips = None; error = None

    if request.method == 'POST':
        if not profile.resume_text:
            error = "No resume found. Please upload your resume first."
        else:
            try:
                prompt = f"""You are an expert resume coach. Analyse this resume and return EXACTLY 5 actionable improvement tips as valid JSON — no markdown.
Format:[{{"tip_number":1,"category":"Impact","priority":"high","title":"Short title","detail":"2-3 sentence advice."}}]
Priority: "high","medium","low". Resume:\n{profile.resume_text[:4000]}"""
                raw  = ai_call([{"role":"system","content":"Return only a valid JSON array."},
                                {"role":"user","content":prompt}], max_tokens=1000, temp=0.4)
                raw  = raw.replace("```json","").replace("```","").strip()
                tips = json.loads(raw)
                if not isinstance(tips, list): raise ValueError("Expected array")
                ps = {'high':{'border':'#ef4444','badge_bg':'#fef2f2','badge_text':'#b91c1c'},
                      'medium':{'border':'#f59e0b','badge_bg':'#fffbeb','badge_text':'#92400e'},
                      'low':{'border':'#10b981','badge_bg':'#ecfdf5','badge_text':'#065f46'}}
                for tip in tips:
                    tip['style'] = ps.get(tip.get('priority','medium').lower(), ps['medium'])
            except json.JSONDecodeError:
                error = "AI returned unexpected format — please try again."
            except Exception as e:
                error = f"Something went wrong: {str(e)}"

    return render(request, 'core/resume_tips.html', {
        'profile': profile, 'tips': tips, 'error': error,
        'has_resume': bool(profile.resume_text),
    })


# =============================================================================
# HIRER
# =============================================================================

@login_required
def post_job(request):
    import razorpay
    KEY_ID  = os.environ.get("RAZORPAY_KEY_ID", "")
    KEY_SEC = os.environ.get("RAZORPAY_KEY_SECRET", "")
    PRICE   = 99900

    if request.method == 'POST':
        try:
            razorpay.Client(auth=(KEY_ID,KEY_SEC)).utility.verify_payment_signature({
                'razorpay_order_id':   request.POST.get('razorpay_order_id',''),
                'razorpay_payment_id': request.POST.get('razorpay_payment_id',''),
                'razorpay_signature':  request.POST.get('razorpay_signature',''),
            })
        except:
            messages.error(request, 'Payment verification failed.')
            return redirect('post_job')

        job = JobPosting.objects.create(
            hirer=request.user,
            title=request.POST.get('title','').strip(),
            company=request.POST.get('company','').strip(),
            location=request.POST.get('location','').strip(),
            job_type=request.POST.get('job_type','full-time'),
            salary_range=request.POST.get('salary_range','').strip(),
            description=request.POST.get('description','').strip(),
            skills_required=request.POST.get('skills_required','').strip(),
            apply_url=request.POST.get('apply_url','').strip(),
            is_active=True,
        )
        RazorpayOrder.objects.create(
            user=request.user, order_id=request.POST.get('razorpay_order_id',''),
            payment_id=request.POST.get('razorpay_payment_id',''),
            amount=PRICE, status='paid', job_posting=job,
        )
        messages.success(request, 'Job posted successfully!')
        return redirect('hirer_dashboard')

    try:
        order = razorpay.Client(auth=(KEY_ID,KEY_SEC)).order.create({'amount':PRICE,'currency':'INR','payment_capture':1})
        razorpay_order_id = order['id']
    except:
        razorpay_order_id = ''

    return render(request, 'core/post_job.html', {
        'razorpay_key_id': KEY_ID, 'razorpay_order_id': razorpay_order_id, 'price': '999',
    })

@login_required
def hirer_dashboard(request):
    jobs = JobPosting.objects.filter(hirer=request.user).order_by('-created_at')
    return render(request, 'core/hirer_dashboard.html', {'jobs': jobs})
