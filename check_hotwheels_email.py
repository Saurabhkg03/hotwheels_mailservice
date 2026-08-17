import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

URL = "https://www.toymarche.com/collections/hot-wheels"
JSON_FILE = "previous.json"

def get_current_products():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    products = {}
    page = 1
    
    while True:
        api_url = f"{URL}/products.json?limit=250&page={page}"
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                items = data.get('products', [])
                
                if not items:
                    break 
                
                for item in items:
                    handle = item.get('handle')
                    title = item.get('title')
                    link = f"https://www.toymarche.com/products/{handle}"
                    products[handle] = {"title": title, "link": link}
                
                page += 1
            else:
                print(f"Failed to fetch page {page}. Status code: {response.status_code}")
                break
        except Exception as e:
            print(f"Error fetching JSON endpoint: {e}")
            break
            
    return products

def main():
    current_products = get_current_products()
    
    if not current_products:
        print("No products found. The website might be blocking the request.")
        return

    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r') as f:
            try:
                previous_products = json.load(f)
            except json.JSONDecodeError:
                previous_products = {}
    else:
        previous_products = {}

    new_products = {}
    for handle, data in current_products.items():
        if handle not in previous_products:
            new_products[handle] = data

    if new_products:
        print(f"Found {len(new_products)} new products!")
        send_email(new_products)
        
        with open(JSON_FILE, 'w') as f:
            json.dump(current_products, f, indent=4)
    else:
        print("No new products found this run.")

def send_email(new_products):
    # Updated variable names here!
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")
    receiver_email = os.environ.get("EMAIL_TO")
    
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 465))

    if not all([sender_email, sender_password, receiver_email]):
        print("Error: Email credentials are not fully set in environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🚨 New Hot Wheels on ToyMarche!"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    text_body = "New Hot Wheels available:\n\n"
    html_body = "<h2>New Hot Wheels Available!</h2><ul>"
    
    for handle, data in new_products.items():
        text_body += f"- {data['title']}: {data['link']}\n"
        html_body += f"<li><a href='{data['link']}'>{data['title']}</a></li>"
    
    html_body += "</ul>"

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Notification email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    main()
