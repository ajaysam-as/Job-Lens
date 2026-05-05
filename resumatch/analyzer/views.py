from groq import Groq
import PyPDF2
import docx
import os
import json
import io

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Configure Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


# ── helpers ───────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file):
    doc = docx.Document(io.BytesIO(file.read()))
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_txt(file):
    return file.read().decode("utf-8")


# ── views ─────────────────────────────────────────────────────────────────────

def index(request):
    return render(request, "index.html")


@csrf_exempt
@require_http_methods(["POST"])
def analyze(request):
    resume_text = ""
    job_description = request.POST.get("job_description", "").strip()

    if not job_description:
        return JsonResponse({"error": "Job description is required."}, status=400)

    if "resume_file" in request.FILES:
        file = request.FILES["resume_file"]
        fname = file.name.lower()
        try:
            if fname.endswith(".pdf"):
                resume_text = extract_text_from_pdf(file)
            elif fname.endswith(".docx"):
                resume_text = extract_text_from_docx(file)
            elif fname.endswith(".txt"):
                resume_text = extract_text_from_txt(file)
            else:
                return JsonResponse({"error": "Unsupported file type. Use PDF, DOCX, or TXT."}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Could not read file: {str(e)}"}, status=400)
    else:
        resume_text = request.POST.get("resume_text", "").strip()

    if not resume_text:
        return JsonResponse({"error": "Please provide a resume."}, status=400)

    prompt = f"""You are an expert ATS (Applicant Tracking System) and career coach. Analyze the following resume against the job description.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Provide a detailed analysis in the following JSON format (return ONLY valid JSON, no markdown, no code blocks, no extra text):
{{
  "match_score": <integer 0-100>,
  "match_level": "<Excellent|Good|Fair|Poor>",
  "summary": "<2-3 sentence overall assessment>",
  "matched_skills": ["<skill1>", "<skill2>"],
  "missing_skills": ["<skill1>", "<skill2>"],
  "strengths": ["<strength1>", "<strength2>"],
  "gaps": ["<gap1>", "<gap2>"],
  "keyword_analysis": {{
    "found": ["<keyword1>", "<keyword2>"],
    "missing": ["<keyword1>", "<keyword2>"]
  }},
  "improvements": [
    {{
      "section": "<section name>",
      "current": "<what the resume currently says or lacks>",
      "suggested": "<specific rewritten text or addition>",
      "reason": "<why this improves the match>"
    }}
  ],
  "ats_tips": ["<tip1>", "<tip2>"],
  "overall_recommendation": "<detailed recommendation paragraph>"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an expert ATS resume analyzer. Always respond with valid JSON only, no markdown, no code blocks."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({"error": "AI returned invalid response. Please try again."}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rewrite_section(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    section         = data.get("section", "")
    current_text    = data.get("current_text", "")
    job_description = data.get("job_description", "")
    suggestion      = data.get("suggestion", "")

    prompt = f"""You are an expert resume writer. Rewrite the following resume section to better match the job description.

Section: {section}
Current content: {current_text}
Job Description: {job_description}
Suggested improvement: {suggestion}

Provide an improved version of this section that:
1. Incorporates relevant keywords from the job description
2. Uses strong action verbs
3. Quantifies achievements where possible
4. Is ATS-friendly
5. Sounds natural and professional

Return ONLY the rewritten section text, no explanations, no markdown."""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an expert resume writer. Return only the rewritten text, no explanations."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.4,
        )
        return JsonResponse({"rewritten": response.choices[0].message.content.strip()})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
