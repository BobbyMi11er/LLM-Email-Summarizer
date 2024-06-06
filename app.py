import os
import email
import re
import datetime as datetime
import json
import sys
import markdown
import subprocess
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from imap_tools import MailBox, AND, NOT
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP_SSL, SMTP_SSL_PORT
from datetime import timedelta, date

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASS = os.getenv("PASS")
LMS_PATH = os.getenv("LMS_PATH")

TODAY = date.today()
LLM_MODEL = "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF"
# anything w/ these in the sender will be ignored, usful for 
# companies with complex HTML and unnecessary links
blacklist = ["walmart", "lenovo", "uber", "panera"]

def fetch_emails():
    date_cons = AND(date_lt=TODAY+timedelta(days=1), date_gte=TODAY-timedelta(days = 1))
    subj_cons = NOT(subject="Spam")

    from_cons = NOT(from_=blacklist[0])
    for item in blacklist[1:]:
        from_cons = AND(from_cons, NOT(from_=item))

    query = AND(date_cons, subj_cons, from_cons)

    with MailBox('imap.1and1.com').login(EMAIL, PASS) as mailbox:
        messages = mailbox.fetch(query, mark_seen=False)

        return list(messages)

def clean_text(text):
    # Replace unwanted characters with space or remove them
    text = re.sub(r'\s+', ' ', text)  # Replace multiple whitespace with a single space
    text = re.sub(r'[\r\n\t]', ' ', text)  # Replace newlines, carriage returns, and tabs with space
    text = text.replace('\u200c', '')  # Remove zero-width non-joiner characters
    return text.strip()

def extract_text_and_links(html_content):
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract text
    for script in soup(["script", "style", "img", "span", "a", "href"]):
        script.extract()  # Remove these tags from the soup

    raw_text = soup.get_text(separator=' ', strip=True)
    cleaned_text = clean_text(raw_text)
    
    return cleaned_text

# Extract and preprocess email content
def extract_email_content(emails):
    email_contents = []
    for msg in emails:
        subject = msg.subject
        from_ = msg.from_
        body = msg.text or msg.html
        body = extract_text_and_links(body)
        
        email_contents.append("subject: " + subject + "|from:"+ from_ + "|body:"+ body)
    
    return email_contents

class Email(BaseModel):
    subject: str = Field(description="Subject line of email")
    sender: str = Field(description="Sender of email")
    date: str = Field(description="Date in form MM/DD/YYYY")
    body: str = Field(description="Summarized version of email with relevant links included")
    category: str = Field(description="Whether the email is a reminder, promotion, social, action, or informational")

def create_summary_chain(model):
    parser = JsonOutputParser(pydantic_object=Email)
    prompt = PromptTemplate(
        template="Answer the user query. {sys_prompt}\n{format_instructions}\n{query}\n",
        input_variables=["sys_prompt", "query"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    summary_chain = prompt | model | parser
    return summary_chain

def create_email_summary(email, chain):
    summary_prompt = """You are a helpful assistant who is an expert at parsing and summarizing emails.
                        If it is a marketing email, only include deals with large, meaningful discounts. 
                        I do not care about the format of the email.
                        Include any relevant or urgent information as well as meaningful deals, with relevant links.
                        The summary should be consise.
                        Your response must follow the JSON format that was outlined with subject, sender, date, body, and category fields.
                        """
    user_query = "Summarize the following email: " + email
    try:
        return chain.invoke({"sys_prompt": summary_prompt, "query": user_query})
    except:
        return ""

def create_digest(emails, model):
    example = """Here is a concise digest of important emails from the past day:
Best Deals:

Get 15% off at Meridian Grooming with code SUMMER15 when you spend $100+ (ends on 05/27/2024)
Shop Shady Rays for exclusive deals and follow them on social media
Get 20% off tickets to Luke Combs, Morgan Wallen, 21 Savage, and more with code MEMORIAL24* through Tuesday
Reminders:

None
Action:

Join Kenny Chesney's Sun Goes Down Tour at Commanders Field (access tickets on SeatGeek)
Shop for Father's Day gifts at Shinesty.com before it's too late
Get a show on the books and use code MEMORIAL24* to get 20% off
Informational:

None
I hope this digest helps you stay informed about the important emails from the past day!"""

    summary_prompt = """You are a helpful assistant who is an expert at creating a weekly digest of important emails. 
                        Given the following emails from the past day, create a concise digest similar to this example: """ + example
    emails_str = ""
    for email in emails:
        emails_str += json.dumps(email)

    template = """Given these instructions: {sys_prompt}, answer {query}"""
    digest_prompt = PromptTemplate.from_template(template)

    
    user_query = "Create a digest of the following email summaries: " + emails_str

    digest_chain = digest_prompt | model
    return digest_chain.invoke({"sys_prompt":summary_prompt, "query": user_query})

def email_digest(digest):
    from_email=EMAIL
    to_email=EMAIL

    # Connect, authenticate, and send mail
    smtp_server = SMTP_SSL('smtp.1and1.com', port=SMTP_SSL_PORT)
    smtp_server.set_debuglevel(1)  # Show SMTP server interactions
    smtp_server.login(EMAIL, PASS)

    multipart_msg = multipart_msg = MIMEMultipart("alternative")
    multipart_msg["Subject"] = 'Daily Digest: ' + TODAY.strftime("%m/%d/%Y")
    multipart_msg["From"] = from_email
    multipart_msg["To"] = to_email

    text = digest.content
    html = markdown.markdown(digest.content)

    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    multipart_msg.attach(part1)
    multipart_msg.attach(part2)

    smtp_server.sendmail(from_email, to_email, multipart_msg.as_string())

    # Disconnect
    smtp_server.quit()
    
def start_llm():
    subprocess.run([LMS_PATH, "server", "start"])
    subprocess.run([LMS_PATH, "load", LLM_MODEL, "--gpu=max"])
    model = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio", model="QuantFactory/Meta-Llama-3-8B-Instruct-GGUF", temperature=0.2, max_tokens=500)
    return model


def end_llm():
    subprocess.run([LMS_PATH, "unload", "--all"])
    subprocess.run([LMS_PATH, "server", "stop"])

print("STARTING LLM...", end="")
model = start_llm()
print("DONE")

print("FECTHING & EXTRACTING EMAILS...", end="")
emails = extract_email_content(fetch_emails())
print("DONE")
dict_emails = []

n = len(emails)
interval = max(1, round(n/20))

print("CREATING EMAIL SUMMARIES", end="")
sys.stdout.flush()
chain = create_summary_chain(model)
for i, email in enumerate(emails):
    if i % interval == 0:
        print(".", end="")
        sys.stdout.flush()
    dict_emails.append(create_email_summary(email, chain))
print("DONE")

print("GENERATING DIGEST...", end="")
digest = create_digest(dict_emails, model)
print("DONE")

print("EMAILING DIGEST...", end="")
email_digest(digest)
print("DONE")

print("CLOSING LLM...", end="")
end_llm()
print("DONE")
subprocess.call("cls", shell=True)
print("WORK COMPLETE")