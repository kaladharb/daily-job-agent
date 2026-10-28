import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.parse import urlparse

import requests

TIMEOUT = 20
EXCLUDE = ('senior', 'staff', 'principal', 'lead ', 'manager', 'director', 'architect', 'head of', 'vp ')

with open('job_preferences.json', 'r', encoding='utf-8') as file:
    PREFERENCES = json.load(file)

TARGET_ROLES = [role.lower() for role in PREFERENCES.get('target_roles', [])]
RESUME_SKILLS = [skill.lower() for skill in PREFERENCES.get('skills', [])]
PREFERRED_LOCATIONS = [loc.lower() for loc in PREFERENCES.get('preferred_locations', [])]
MAX_DAILY_JOBS = max(1, min(int(PREFERENCES.get('max_daily_jobs', 50)), 100))

ROLE_GROUPS = {
    'Full Stack / MERN / Web': (20, ('full stack', 'fullstack', 'mern', 'web developer', 'web engineer')),
    'Software Development': (18, ('software developer', 'software engineer', 'software development', 'sde', 'graduate engineer trainee', 'associate software')),
    'Frontend / Backend': (17, ('frontend', 'front-end', 'backend', 'back-end', 'react developer', 'react engineer', 'node.js', 'nodejs', 'javascript developer')),
    'Python / Java': (15, ('python developer', 'python engineer', 'java developer', 'java engineer', 'python intern', 'java intern')),
    'AI / Automation': (15, ('ai engineer', 'ai developer', 'genai', 'generative ai', 'machine learning', 'ml engineer', 'ai agent', 'n8n', 'automation developer', 'workflow automation', 'ai intern', 'ml intern')),
    'Database / SQL': (12, ('sql developer', 'mysql developer', 'database developer', 'database engineer', 'sql intern', 'database intern')),
    'Testing / QA': (12, ('software tester', 'qa engineer', 'quality assurance', 'manual tester', 'test engineer', 'testing intern', 'automation testing', 'qa intern', 'qa tester', 'software testing')),
}


def fetch_remotive():
    response = requests.get(
        'https://remotive.com/api/remote-jobs', timeout=TIMEOUT,
        headers={'User-Agent': 'StudentJobAgent/1.0'},
    )
    response.raise_for_status()
    for item in response.json().get('jobs', []):
        yield {
            'title': item.get('title') or '',
            'company': item.get('company_name') or '',
            'url': item.get('url') or '',
            'location': item.get('candidate_required_location') or 'Unspecified',
            'description': re.sub(r'<[^>]*>', ' ', item.get('description') or ''),
            'source': 'Remotive',
        }


def fetch_arbeitnow():
    response = requests.get(
        'https://www.arbeitnow.com/api/job-board-api', timeout=TIMEOUT,
        headers={'User-Agent': 'StudentJobAgent/1.0'},
    )
    response.raise_for_status()
    for item in response.json().get('data', []):
        yield {
            'title': item.get('title') or '',
            'company': item.get('company_name') or '',
            'url': item.get('url') or '',
            'location': item.get('location') or 'Unspecified',
            'description': re.sub(r'<[^>]*>', ' ', item.get('description') or ''),
            'source': 'Arbeitnow',
        }

def fetch_greenhouse():
    with open("company_sources.json", "r", encoding="utf-8") as file:
        sources = json.load(file)

    for company in sources.get("greenhouse", []):
        try:
            url = (
                "https://boards-api.greenhouse.io"
                f"/v1/boards/{company}/jobs"
            )

            response = requests.get(
                url,
                params={"content": "true"},
                timeout=TIMEOUT
            )
            response.raise_for_status()

            for item in response.json().get("jobs", []):
                location = item.get("location") or {}

                yield {
                    "title": item.get("title", ""),
                    "company": company.title(),
                    "url": item.get("absolute_url", ""),
                    "location": location.get("name", ""),
                    "description": re.sub(
                        r"<[^>]*>",
                        " ",
                        item.get("content") or ""
                    ),
                    "source": "Greenhouse"
                }

        except (requests.RequestException, ValueError) as exc:
            print(f"Greenhouse {company} unavailable: {exc}")


def fetch_lever():
    with open("company_sources.json", "r", encoding="utf-8") as file:
        sources = json.load(file)

    for company in sources.get("lever", []):
        try:
            url = f"https://api.lever.co/v0/postings/{company}"
            response = requests.get(
                url,
                params={"mode": "json"},
                timeout=TIMEOUT
            )
            response.raise_for_status()

            for item in response.json():
                categories = item.get("categories") or {}

                yield {
                    "title": item.get("text", ""),
                    "company": company.title(),
                    "url": item.get("applyUrl") or item.get("hostedUrl", ""),
                    "location": categories.get("location", ""),
                    "description": item.get("descriptionPlain", ""),
                    "source": "Lever"
                }

        except (requests.RequestException, ValueError) as exc:
            print(f"Lever {company} unavailable: {exc}")

def score(job):
    title = job['title'].lower()
    description = job['description'].lower()
    location = job['location'].lower()
    text = title + ' ' + description

    if any(term in title for term in EXCLUDE):
        return -1

    matched_groups = [
        (name, weight)
        for name, (weight, terms) in ROLE_GROUPS.items()
        if any(term in title for term in terms)
    ]
    if not matched_groups:
        return -1

    # Avoid obvious experienced-only openings. This does not prove eligibility.
    if re.search(r'\b(?:[3-9]|1[0-9])\+?\s*(?:years|yrs)\b', text[:1500]):
        return -1



    points = max(weight for _, weight in matched_groups)
    # Cap skill points so a long description does not dominate rankings.
    matched_skills = [skill for skill in RESUME_SKILLS if skill in text]
    points += min(len(matched_skills), 10) * 3

    if any(role in title for role in TARGET_ROLES):
        points += 8
    if 'intern' in title:
        points += 12
    if any(term in title for term in ('junior', 'graduate', 'trainee', 'entry level', 'entry-level', 'fresher')):
        points += 8
    elif any(term in text for term in ('entry level', 'entry-level', 'fresher', 'new grad', '0-1 years')):
        points += 4
    if '2027' in text:
        points += 5  # Mention alone is NOT confirmation of 2027 eligibility.
    if any(loc in location for loc in ('india', 'hyderabad', 'bengaluru', 'bangalore', 'pune', 'chennai', 'mumbai', 'delhi')):
        points += 8
    elif any(loc in location for loc in ('worldwide', 'anywhere', 'global')):
        points += 4

    job['category'] = max(matched_groups, key=lambda item: item[1])[0]
    job['matched_skills'] = matched_skills[:8]
    return points


def collect():
    found = []
    for source in (fetch_remotive, fetch_arbeitnow, fetch_greenhouse, fetch_lever):
        try:
            found.extend(source())
        except (requests.RequestException, ValueError) as exc:
            print(f'{source.__name__} unavailable: {exc}')

    unique = {}
    for job in found:
        url = job['url']
        if not url or urlparse(url).scheme not in ('http', 'https'):
            continue
        job['score'] = score(job)
        if job['score'] >= 3:
            key = url.split('?')[0].rstrip('/')
            if key not in unique or job['score'] > unique[key]['score']:
                unique[key] = job
    return sorted(unique.values(), key=lambda job: job['score'], reverse=True)[:MAX_DAILY_JOBS]


def format_report(jobs):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    lines = [
        f'Job Agent Report — {today} (UTC)',
        f'{len(jobs)} possible resume-based matches', '',
        'These are job listing links from public feeds, not necessarily direct employer application forms.',
        'Verify that each opening is active, accepts applicants in India, and is eligible for 2027 graduates.',
        'Scores are ranking points, not percentages or eligibility guarantees.', '',
    ]
    for index, job in enumerate(jobs, 1):
        lines.extend([
            f"{index}. {job['title']} — {job['company']}",
            f"Category: {job.get('category', 'Software')} | Location: {job['location']}",
            f"Ranking points: {job['score']} | Source: {job['source']}",
            f"Matching skills: {', '.join(job.get('matched_skills', [])) or 'Role-title match'}",
            f"View job / Apply: {job['url']}", '',
        ])
    if not jobs:
        lines.append('No matching listings were found in the available feeds today.')
    return '\n'.join(lines)


def send_email(report):
    sender = os.environ['EMAIL_USER']
    password = os.environ['EMAIL_APP_PASSWORD']
    recipient = os.environ['EMAIL_TO']
    message = EmailMessage()
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = 'Daily Job Agent — Resume-Matched Jobs & Internships'
    message.set_content(report)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=TIMEOUT) as server:
        server.login(sender, password)
        server.send_message(message)


def send_telegram(report):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    chunks, current = [], ''
    for line in report.splitlines(keepends=True):
        if len(current) + len(line) > 3500 and current:
            chunks.append(current)
            current = ''
        while len(line) > 3500:
            chunks.append(line[:3500])
            line = line[3500:]
        current += line
    if current:
        chunks.append(current)
    for chunk in chunks:
        response = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': chunk, 'disable_web_page_preview': True},
            timeout=TIMEOUT,
        )
        response.raise_for_status()


def main():
    jobs = collect()
    report = format_report(jobs)
    print(report)
    if all(os.getenv(key) for key in ('EMAIL_USER', 'EMAIL_APP_PASSWORD', 'EMAIL_TO')):
        send_email(report)
        print('Email sent successfully.')
    else:
        print('Email skipped: missing configuration.')
    if all(os.getenv(key) for key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')):
        send_telegram(report)
        print('Telegram sent successfully.')
    else:
        print('Telegram skipped: missing configuration.')


if __name__ == '__main__':
    main()
