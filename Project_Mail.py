# Importing necessary libraries.
import imaplib
import email
import yaml
from datetime import datetime

def fetch_emails():
    # Load credentials from YAML file.
    with open("password.yaml") as f:
        content = f.read()

    # Load the username and password from YAML file.
    my_passwords = yaml.safe_load(content)
    username, password = my_passwords["username"], my_passwords["password"]

    # URL for IMAP connection.
    imap_url = 'imap.gmail.com'

    # Connection with Gmail using SSL.
    my_mail = imaplib.IMAP4_SSL(imap_url)

    # Log in using your credentials.
    my_mail.login(username, password)

    # Select the inbox to fetch messages.
    my_mail.select('inbox')

    # Calculate today's date.
    today_date = datetime.now().strftime("%d-%b-%Y")

    # Search for emails from today
    status, data = my_mail.search(None, f'ON {today_date}')  # Use ON to filter emails by today's date.

    if status != 'OK':
        print("No messages found!")
        return []

    mail_id_list = data[0].split()  # IDs of all emails that we want to fetch.

    msgs = []  # Empty list to capture all messages.

    # Iterate through messages and extract data into the msgs list.
    for num in mail_id_list:
        try:
            typ, data = my_mail.fetch(num, '(RFC822)')  # RFC822 returns the whole message (BODY fetches just body.)
            msgs.append(data)
        except imaplib.IMAP4.abort as e:
            print(f"Failed to fetch email {num}: {str(e)}")
            continue

    # Extract Email content extracting the date, subject, sender, and body text. Handles possible decoding issues with different character sets.
    email_texts = []
    for msg in msgs[::-1]:
        for response_part in msg:
            if type(response_part) is tuple:
                my_msg = email.message_from_bytes(response_part[1])
                email_date = my_msg['date']
                email_text = f"Date: {email_date}\n"
                email_text += f"Subject: {my_msg['subject']}\n"
                email_text += f"From: {my_msg['from']}\n"
                email_text += "Body:\n"
                for part in my_msg.walk():
                    if part.get_content_type() == 'text/plain':
                        try:
                            email_text += part.get_payload(decode=True).decode()
                        except UnicodeDecodeError:
                            email_text += part.get_payload(decode=True).decode('latin-1')
                email_texts.append(email_text)

    return email_texts

# Example usage.
emails = fetch_emails()

# Importing necessary libraries. 
import concurrent.futures
import requests
import email.utils

# Extracts the sender's information from the email text.
def extract_sender(email_text):
    lines = email_text.split('\n')
    for line in lines:
        if line.lower().startswith('from:'):
            return line
    return "Sender: Unknown"

# Extracts and formats the email date.
def extract_email_date(email_text):
    for line in email_text.split('\n'):
        if line.lower().startswith('date:'):
            try:
                date_str = line.split(':', 1)[1].strip()
                email_date = email.utils.parsedate_to_datetime(date_str)
                return email_date.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, IndexError):
                pass
    return "Unknown Date"

# Handles API response and possible errors, extracting the summary.
def summarize_email(email_text, api_url, api_token):
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    data = {
        'inputs': email_text,
        'parameters': {'max_length': 150, 'min_length': 40, 'length_penalty': 2.0, 'num_beams': 4, 'early_stopping': True}
    }
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        summary = response.json()[0]['summary_text']
    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        summary = "Error: Unable to summarize this email."
    sender = extract_sender(email_text)
    email_date = extract_email_date(email_text)
    return f"Date: {email_date}\n{sender}\nSummary: {summary}"

#  process emails concurrently, improving performance Collects summarized emails, checking for any errors related to API summarization.
def process_emails(emails, api_url, api_token):
    summarized_emails = []
    error_occurred = False
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(summarize_email, email, api_url, api_token) for email in emails if email.strip()]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if "Error: Unable to summarize this email." in result:
                error_occurred = True
            elif not error_occurred:
                summarized_emails.append(result)
    if error_occurred:
        summarized_emails.append("Error: Unable to summarize emails due to invalid API.")
    return summarized_emails

# Taking url and token from Hugging face (--note-- if the code prints error try to use with another url or token.)
api_url = "https://api-inference.huggingface.co/models/sshleifer/distilbart-cnn-12-6"
api_token = "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"

#Fetches emails, processes them, and prints the summarized information.
emails = fetch_emails()
summarized_emails = process_emails(emails, api_url, api_token)
for summary in summarized_emails:
    print(summary)
