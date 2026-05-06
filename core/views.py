from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models import UserProfile, SavedJob
import PyPDF2, docx, os, json, io, requests, feedparser
from bs4 import BeautifulSoup
import urllib.parse

MODEL = "llama-3.3-70b-versatile"

# ── Government & Specialised RSS Feeds (list — used by find_jobs scraper) ─────
GOVT_RSS_FEEDS_LIST = [
    {"url": "https://www.sarkariresult.com/feed/",                "source": "SarkariResult",   "category": "government"},
    {"url": "https://www.govtjobsblog.in/feed/",                  "source": "GovtJobsBlog",    "category": "government"},
    {"url": "https://www.freejobalert.com/feed/",                 "source": "FreeJobAlert",    "category": "government"},
    {"url": "https://ibps.in/feed/",                              "source": "IBPS",            "category": "banking"},
    {"url": "https://www.sbi.co.in/web/careers/rss",              "source": "SBI Careers",     "category": "banking"},
    {"url": "https://indianrailways.gov.in/railwayboard/rss.jsp", "source": "Indian Railways", "category": "railways"},
    {"url": "https://www.ncs.gov.in/jobseeker/rss",               "source": "NCS Portal",      "category": "government"},
]

BLUECOLLAR_SEARCHES = [
    {"query": "hotel jobs chennai",        "category": "hotel"},
    {"query": "housekeeping jobs india",   "category": "hotel"},
    {"query": "manufacturing jobs india",  "category": "manufacturing"},
    {"query": "driver jobs india",         "category": "logistics"},
    {"query": "security guard jobs india", "category": "security"},
    {"query": "retail jobs india",         "category": "retail"},
    {"query": "electrician jobs india",    "category": "bluecollar"},
    {"query": "plumber jobs india",        "category": "bluecollar"},
]

# ── Govt Jobs page — RSS feed dict (used by the /govt-jobs/ page view) ────────
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


def _categorise_govt_job(title: str, summary: str) -> str:
    """Classify a govt RSS entry into one of the CATEGORY_META keys."""
    text = (title + " " + summary).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "central"


# ── Job scrapers ──────────────────────────────────────────────────────────────

def search_linkedin_jobs(query, location="India", num=15):
    jobs = []
    try:
        url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}&f_TPR=r86400"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="base-card")[:num]:
            t = card.find("h3", class_="base-search-card__title")
            c = card.find("h4", class_="base-search-card__subtitle")
            l = card.find("span", class_="job-search-card__location")
            a = card.find("a", class_="base-card__full-link")
            if t and a:
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else location,
                             "apply_url": a.get("href", "#"), "source": "LinkedIn",
                             "source_color": "#0077b5", "category": "whitecollar"})
    except:
        pass
    return jobs


def search_indeed_jobs(query, location="India", num=15):
    jobs = []
    try:
        url = f"https://in.indeed.com/jobs?q={urllib.parse.quote(query)}&l={urllib.parse.quote(location)}&fromage=7"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
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
                             "apply_url": url2, "source": "Indeed",
                             "source_color": "#003A9B", "category": "whitecollar"})
    except:
        pass
    return jobs


def search_internshala_jobs(query, num=15):
    jobs = []
    try:
        slug = urllib.parse.quote(query.lower().replace(" ", "-"))
        r = requests.get(f"https://internshala.com/jobs/{slug}-jobs",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
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
                             "apply_url": f"https://internshala.com{href}" if href else f"https://internshala.com/jobs/{slug}-jobs",
                             "source": "Internshala", "source_color": "#16a34a", "category": "whitecollar"})
    except:
        pass
    return jobs


def search_naukri_jobs(query, location="India", num=15):
    jobs = []
    try:
        slug = query.lower().replace(" ", "-")
        loc  = location.lower().replace(" ", "-")
        r = requests.get(f"https://www.naukri.com/{slug}-jobs-in-{loc}",
                         headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("article", class_="jobTuple")[:num]:
            t = card.find("a", class_="title")
            c = card.find("a", class_="subTitle")
            l = card.find("li", class_="location")
            if t:
                jobs.append({"title": t.text.strip(), "company": c.text.strip() if c else "N/A",
                             "location": l.text.strip() if l else location,
                             "apply_url": t.get("href", f"https://www.naukri.com/{slug}-jobs"),
                             "source": "Naukri", "source_color": "#ef4444", "category": "whitecollar"})
    except:
        pass
    return jobs


def fetch_govt_rss_jobs(category_filter=None, max_per_feed=15):
    """Used by find_jobs() to mix a few govt jobs into the main results."""
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
        except:
            pass
    return all_jobs


def fetch_bluecollar_jobs(query="", num=15):
    all_jobs = []
    searches = [s for s in BLUECOLLAR_SEARCHES if not query or query.lower() in s["query"]] or BLUECOLLAR_SEARCHES[:3]
    for s in searches[:3]:
        for j in search_naukri_jobs(s["query"], "India", num=5):
            j["category"] = s["category"]; all_jobs.append(j)
        for j in search_indeed_jobs(s["query"], "India", num=5):
            j["category"] = s["category"]; all_jobs.append(j)
    return all_jobs[:num]


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
        'profile':     profile,
        'skills':      skills,
        'saved_count': SavedJob.objects.filter(user=request.user).count(),
        'has_resume':  bool(profile.resume_text),
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
                else:
                    return JsonResponse({'error': 'Use PDF, DOCX or TXT'}, status=400)
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
        sources  = data.get('sources', ['LinkedIn', 'Indeed', 'Internshala', 'Naukri'])
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
        elif category == 'bluecollar':
            all_jobs += fetch_bluecollar_jobs(query)
        else:
            if 'LinkedIn'    in sources: all_jobs += search_linkedin_jobs(query, location, num=15)
            if 'Indeed'      in sources: all_jobs += search_indeed_jobs(query, location, num=15)
            if 'Internshala' in sources: all_jobs += search_internshala_jobs(query, num=15)
            if 'Naukri'      in sources: all_jobs += search_naukri_jobs(query, location, num=15)
            all_jobs += fetch_govt_rss_jobs(max_per_feed=5)

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
        'profile':   profile,
        'skills':    skills,
        'job_title': profile.job_title,
    })


@login_required
def govt_jobs(request):
    """
    Dedicated /govt-jobs/ page — aggregates RSS feeds with category filter + search.
    Replaces the old simple govt_jobs view.
    """
    active_category = request.GET.get("category", "all")
    query           = request.GET.get("q", "").strip().lower()
    all_jobs        = []

    for feed_meta in GOVT_RSS_FEEDS_PAGE.values():
        try:
            feed = feedparser.parse(feed_meta["url"])
            for entry in feed.entries[:20]:
                title    = getattr(entry, "title", "Untitled")
                summary  = getattr(entry, "summary", "")
                all_jobs.append({
                    "title":       title,
                    "summary":     summary[:200] + "…" if len(summary) > 200 else summary,
                    "link":        getattr(entry, "link", "#"),
                    "pub_date":    getattr(entry, "published", ""),
                    "source":      feed_meta["label"],
                    "source_icon": feed_meta["icon"],
                    "category":    _categorise_govt_job(title, summary),
                })
        except:
            pass

    if active_category != "all":
        all_jobs = [j for j in all_jobs if j["category"] == active_category]
    if query:
        all_jobs = [j for j in all_jobs if query in j["title"].lower() or query in j["summary"].lower()]

    category_counts = {"all": len(all_jobs)}
    for cat in CATEGORY_META:
        if cat != "all":
            category_counts[cat] = sum(1 for j in all_jobs if j["category"] == cat)

    return render(request, "core/govt_jobs.html", {
        "jobs":            all_jobs,
        "categories":      CATEGORY_META,
        "active_category": active_category,
        "category_counts": category_counts,
        "query":           query,
        "total":           len(all_jobs),
    })


@login_required
@csrf_exempt
def save_job(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        SavedJob.objects.get_or_create(
            user=request.user,
            apply_url=data.get('apply_url'),
            defaults={
                'job_title':   data.get('title', ''),
                'company':     data.get('company', ''),
                'location':    data.get('location', ''),
                'source':      data.get('source', ''),
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
              f"Write a 3-paragraph professional cover letter for {name} "
              f"applying for {data.get('job_title')} at {data.get('company')}. "
              f"Skills: {', '.join(skills[:10])}. Experience: {profile.experience_years} years. "
              f"ATS-friendly, confident but not over the top."}],
            max_tokens=600, temp=0.6
        )
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
