# 🔍 JobLens — AI-Powered Job Search Platform for India

> Find the right job faster. Upload your resume, let AI match you to real jobs from LinkedIn, Naukri, Indeed, Government portals and more — all in one place.

---

## 🚀 What is JobLens?

JobLens is a smart job search web app built for Indian job seekers — from fresh graduates to experienced professionals, from IT engineers to hotel workers, government job aspirants to banking candidates.

You upload your resume once. Our AI reads it, understands your skills, and automatically finds and ranks the best matching jobs from across the web — every single day.

---

## ✨ Features

### For Job Seekers
- 📄 **Resume Upload** — PDF, DOCX or plain text. AI extracts your skills automatically.
- 🤖 **AI Job Matching** — Powered by Groq (Llama 3.3 70B). Every job gets a match score based on your profile.
- 🔎 **Multi-source Search** — Searches LinkedIn, Naukri, Indeed, and Internshala in real time.
- 🏛️ **Government Jobs** — Live RSS feeds from TNPSC, SSC, Railways, IBPS, Defence, KVS and more. Always up to date, no scraping needed.
- 🏨 **All Job Types** — IT, Engineering, Teaching, Banking, Hotel & Hospitality, Manufacturing, Logistics, Retail, Security and more.
- 💾 **Save Jobs** — Bookmark jobs and apply when ready.
- 📊 **Application Tracker** — Kanban board to track every application from Applied → Interview → Offer.
- ✉️ **AI Cover Letter Generator** — One click, ATS-friendly cover letter tailored to each job.
- 📱 **WhatsApp Alerts** — Get notified when high-match jobs appear (Twilio / WhatsApp Cloud API).

### For Hirers
- 📝 **Post a Job** — Simple form covering all job types including blue-collar and daily wage roles.
- 💳 **Razorpay Payment** — ₹999 per job post, secure payment gateway built in.
- 🤖 **AI Candidate Matching** — AI automatically scores and ranks applicants by skill fit.
- 👥 **Applicant Dashboard** — View all applicants, their match scores, and update their status.
- 📱 **Instant WhatsApp Alerts** — Get notified the moment someone applies.

---

## 🗂️ Job Categories Covered

| Category | Sources |
|---|---|
| 🏛️ Central Government | SSC, UPSC, Railways, DRDO, IBPS |
| 🏢 State Government | TNPSC, Tamil Nadu Govt |
| 🏦 Banking | IBPS, SBI, RBI |
| 🚂 Railways | RRB NTPC, Group D |
| 🛡️ Defence | Indian Army, Navy, Air Force |
| 🎓 Teaching | KVS, NVS, TGT, PGT |
| 💻 IT / Software | LinkedIn, Naukri, Indeed |
| 🏨 Hotel & Hospitality | Tamil Nadu hospitality jobs |
| 🏭 Manufacturing | Factory and production roles |
| 🚚 Driver & Logistics | Transport and delivery roles |
| 🛒 Retail | Shop floor and store management |
| 🔒 Security | Guard and safety roles |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5, Python 3.13 |
| AI | Groq API (Llama 3.3 70B) — Free |
| Job Data | BeautifulSoup scraping + RSS feeds |
| Payments | Razorpay |
| Notifications | WhatsApp (Twilio / Meta Cloud API) |
| Database | SQLite (dev) / PostgreSQL (production) |
| Hosting | Railway.app |
| Static Files | WhiteNoise |

---

## ⚙️ Setup (Local)

```bash
# 1. Clone the repo
git clone https://github.com/YOURNAME/joblens.git
cd joblens

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
# Create a .env file or set these in your terminal:
# GROQ_API_KEY=your_groq_key
# RAZORPAY_KEY_ID=your_key
# RAZORPAY_KEY_SECRET=your_secret
# SECRET_KEY=your_django_secret

# 5. Run migrations
python manage.py migrate

# 6. Start the server
python manage.py runserver
```

Then open `http://127.0.0.1:8000` in your browser.

---

## 🌐 Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key — generate at djecrety.ir |
| `GROQ_API_KEY` | Free at console.groq.com |
| `RAZORPAY_KEY_ID` | From Razorpay dashboard |
| `RAZORPAY_KEY_SECRET` | From Razorpay dashboard |
| `ALLOWED_HOSTS` | e.g. `yourapp.railway.app,joblens.in` |
| `DEBUG` | `True` for local, `False` for production |
| `DATABASE_URL` | Auto-set by Railway in production |
| `TWILIO_ACCOUNT_SID` | Optional — for WhatsApp alerts |
| `TWILIO_AUTH_TOKEN` | Optional — for WhatsApp alerts |

---

## 📁 Project Structure

```
joblens/
├── core/
│   ├── models.py       # UserProfile, SavedJob, JobPosting, JobApplication
│   ├── views.py        # All views including hirers + govt jobs + Razorpay
│   ├── urls.py         # URL routes
│   └── templates/
│       └── core/       # HTML templates
├── joblens/
│   ├── settings.py     # Production-ready settings
│   ├── urls.py         # Root URL config
│   └── wsgi.py
├── manage.py
├── Procfile            # For Railway deployment
└── requirements.txt
```

---

## 💰 Monetization

- **Hirers** pay ₹999 per job post (via Razorpay)
- **Pro plan** for job seekers — unlimited matches, WhatsApp alerts, AI tools (coming soon)
- **Featured listings** for employers (coming soon)

---

## 🙏 Built By

Built with ❤️ by **Ajay** from Tiruchirappalli, Tamil Nadu.  
Helping every Indian find their next opportunity — from IT to agriculture, government to hospitality.

---

## 📄 License

MIT License — free to use, modify and deploy.
