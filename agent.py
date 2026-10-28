import os
import re
import json

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
from urllib.parse import urlparse

import requests

# Load resume-based job preferences
with open("job_preferences.json", "r", encoding="utf-8") as file:
    PREFERENCES = json.load(file)

TARGET_ROLES = [
    role.lower()
    for role in PREFERENCES["target_roles"]
]

RESUME_SKILLS = [
    skill.lower()
    for skill in PREFERENCES["skills"]
]

PREFERRED_LOCATIONS = [
    location.lower()
    for location in PREFERENCES["preferred_locations"]
]

MAX_DAILY_JOBS = PREFERENCES["max_daily_jobs"]

TIMEOUT = 20
KEYWORDS = ('software', 'developer', 'engineer', 'python', 'frontend', 'front-end', 'backend', 'back-end', 'full stack', 'fullstack', 'machine learning', 'ai/ml', 'intern')
EXCLUDE = ('senior', 'staff', 'principal', 'lead ', 'manager', 'director', 'architect')
SKILLS = ('python', 'react', 'javascript', 'typescript', 'node', 'sql', 'mongodb', 'machine learning', 'ai', 'aws')


def fetch_remotive():
    response = requests.get('https://remotive.com/api/remote-jobs', timeout=TIMEOUT, headers={'User-Agent': 'StudentJobAgent/1.0'})
    response.raise_for_status()
    for item in response.json().get('jobs', []):
        yield {'title': item.get('title', ''), 'company': item.get('company_name', ''), 'url': item.get('url', ''), 'location': item.get('candidate_required_location', 'Remote'), 'description': re.sub('<[^>]*>', ' ', item.get('description', '')), 'source': 'Remotive'}


def fetch_arbeitnow():
    response = requests.get('https://www.arbeitnow.com/api/job-board-api', timeout=TIMEOUT, headers={'User-Agent': 'StudentJobAgent/1.0'})
    response.raise_for_status()
    for item in response.json().get('data', []):
        yield {'title': item.get('title', ''), 'company': item.get('company_name', ''), 'url': item.get('url', ''), 'location': item.get('location', ''), 'description': re.sub('<[^>]*>', ' ', item.get('description', '')), 'source': 'Arbeitnow'}


def score(job):
    title = job['title'].lower()
    text = (job['title'] + ' ' + job['description']).lower()
    location = job['location'].lower()
    if not any(word in title for word in KEYWORDS) or any(word in title for word in EXCLUDE):
        return -1
    if re.search(r'\b(?:[3-9]|1[0-9])\+?\s*(?:years|yrs)\b', text[:1200]):
        return -1
    if any(term in location for term in ('us only', 'usa only', 'united states only', 'europe only', 'eu only')):
        return -1
    points = sum(2 for skill in SKILLS if skill in text)
    points += 7 if 'intern' in title else 0
    points += 5 if any(term in text for term in ('entry level', 'entry-level', 'graduate', 'fresher', 'junior', 'new grad')) else 0
    points += 2 if any(term in location for term in ('india', 'worldwide', 'anywhere', 'remote', 'global')) else 0
    return points


def collect():
    found = []
    for source in (fetch_remotive, fetch_arbeitnow):
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
            unique[url.split('?')[0].rstrip('/')] = job
    return sorted(unique.values(), key=lambda job: job['score'], reverse=True)[:50]


def format_report(jobs):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    lines = [f'Job Agent Report — {today} (UTC)', f'{len(jobs)} possible matches', '', 'Check eligibility, location restrictions, and whether each role is still open before applying.', 'Listings are not guaranteed to accept 2027 graduates.', '']
    for index, job in enumerate(jobs, 1):
        lines.extend([f"{index}. {job['title']} — {job['company']}", f"Location: {job['location']} | Score: {job['score']} | Source: {job['source']}", job['url'], ''])
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
    message['Subject'] = 'Daily Job Agent — Fresher & Internship Leads'
    message.set_content(report)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=TIMEOUT) as server:
        server.login(sender, password)
        server.send_message(message)


def send_telegram(report):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    # Telegram limits messages to 4096 characters; send complete lines in batches.
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
        response = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat_id, 'text': chunk, 'disable_web_page_preview': True}, timeout=TIMEOUT)
        response.raise_for_status()


def main():
    jobs = collect()
    report = format_report(jobs)
    print(report)
    if all(os.getenv(key) for key in ('EMAIL_USER', 'EMAIL_APP_PASSWORD', 'EMAIL_TO')):
        send_email(report)
    else:
        print('Email skipped: missing configuration.')
    if all(os.getenv(key) for key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')):
        send_telegram(report)
    else:
        print('Telegram skipped: missing configuration.')


if __name__ == '__main__':
    main()
