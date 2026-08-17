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
    
    # Using Shopify's robust products.json endpoint to avoid HTML scraping issues
    while True:
        api_url = f"{URL}/products.json?limit=250&page={page}"
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                items = data.get('products', [])
                
                if not items:
                    break # Reached the end of the pagination
                
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

    # Load previously scraped products
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r') as f:
            try:
                previous_products = json.load(f)
            except json.JSONDecodeError:
                previous_products = {}
    else:
        previous_products = {}

    # Identify new products by comparing URL handles
    new_products = {}
    for handle, data in current_products.items():
        if handle not in previous_products:
            new_products[handle] = data

    if new_products:
        print(f"Found {len(new_products)} new products!")
        send_email(new_products)
        
        # Save the updated catalog back to previous.json
        with open(JSON_FILE, 'w') as f:
            json.dump(current_products, f, indent=4)
    else:
        print("No new products found this run.")

def send_email(new_products):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
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
    main()          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          overflow: hidden;
        }}
        .banner {{
          width: 100%;
          height: auto;
          display: block;
        }}
        .content {{
          padding: 20px 30px;
        }}
        h1 {{
          color: #d32f2f;
          font-size: 24px;
          margin-bottom: 10px;
        }}
        p {{
          font-size: 16px;
          line-height: 1.5;
          margin-bottom: 20px;
        }}
        ul {{
          list-style-type: none;
          padding: 0;
        }}
        ul li {{
          background: #ffebee;
          margin-bottom: 8px;
          padding: 10px 15px;
          border-left: 6px solid #d32f2f;
          font-weight: bold;
          color: #b71c1c;
          border-radius: 4px;
        }}
        a.button {{
          display: inline-block;
          padding: 12px 25px;
          background-color: #d32f2f;
          color: white !important; /* Added !important */
          text-decoration: none;
          font-weight: bold;
          border-radius: 4px;
          margin-top: 15px;
        }}
        .footer {{
          text-align: center;
          font-size: 12px;
          color: #888;
          padding: 15px 10px;
          border-top: 1px solid #eee;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <img src="{BANNER_URL}" alt="Hot Wheels Banner" class="banner" onerror="this.style.display='none'" /> <!-- Added onerror fallback -->
        <div class="content">
          <h1>New Hot Wheels Cars Just Arrived!</h1>
          <p>Hey there,</p>
          <p>The following {len(new_items)} new Hot Wheels car(s) have just appeared on ToyMarche and are currently listed as in stock:</p>
          <ul>
    """

    # Sanitize item names before inserting into HTML to prevent potential issues
    for name in new_items:
        # Basic sanitization: escape HTML special characters
        safe_name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html_body += f"<li>{safe_name}</li>"

    html_body += f"""
          </ul>
          <p>
            <a href="{URL}" class="button" target="_blank">Check Them Out</a>
          </p>
          <p>Good luck grabbing them first!</p>
        </div>
      </div>
      <div class="footer">
        Checked at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | &copy; {datetime.utcnow().year} ToyMarche Hot Wheels Tracker
      </div>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Hot Wheels Notifier <{GMAIL_USER}>" # Improve From header
    msg["To"] = ", ".join(recipient_list) # Assign the joined list to the 'To' header
    # Simple text fallback
    text_fallback = f"Found {len(new_items)} new Hot Wheels item(s):\n\n" + "\n".join([f"- {name}" for name in new_items]) + f"\n\nCheck them out: {URL}"
    msg.set_content(text_fallback)
    # Add HTML alternative
    msg.add_alternative(html_body, subtype="html")

    try:
        # Use context manager for SMTP connection
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg) # send_message handles multiple recipients from msg["To"]
        print(f"✅ Email alert sent successfully to {', '.join(recipient_list)}.")
    except smtplib.SMTPAuthenticationError:
        print("🚨 SMTP Authentication Error: Check GMAIL_USER and GMAIL_APP_PASSWORD.")
    except Exception as e:
        print(f"🚨 Failed to send email: {e}")
        # Consider logging the full exception traceback here for debugging
        # import traceback
        # traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 5) MAIN LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def main():
    start_time = datetime.utcnow()
    print("="*60)
    print(f"[{start_time.isoformat()}] Checking ToyMarche Hot Wheels…")

    # 1) Load old list
    prev_list_set = set(load_previous_list()) # Use a set for faster lookups
    print(f"  ↳ Previously tracking {len(prev_list_set)} items.")

    # 2) Fetch & parse current available items
    html = fetch_rendered_html()
    if not html:
        print("🚨 Aborting check due to page fetch error.")
        sys.exit(1) # Exit with an error code

    current_list = parse_product_list(html)
    current_list_set = set(current_list) # Use a set
    print(f"  ↳ Currently found {len(current_list_set)} available items.")

    # 3) Compare: Find items in current that were not in previous
    new_items = sorted(list(current_list_set - prev_list_set)) # Sort for consistent email order

    if new_items:
        print(f"  ↳ Found {len(new_items)} new item(s):")
        for itm in new_items:
            print(f"      • {itm}")

        # 4) Send email alert only if there are new items
        send_email_alert(new_items)

    else:
        print("  ↳ No new items found compared to the previous list. ✅")

    # 5) Save the *current* list (available items only) for the next run,
    # regardless of whether new items were found. This keeps the state updated.
    if current_list: # Only save if the current list isn't empty (e.g., due to parse error)
        print(f"  ↳ Saving current {len(current_list)} available items to '{PREVIOUS_FILE}'.")
        save_current_list(current_list)
    else:
        print(f"⚠️ Warning: Current available list is empty. Not updating '{PREVIOUS_FILE}'.")


    end_time = datetime.utcnow()
    duration = end_time - start_time
    print(f"[{end_time.isoformat()}] Check finished in {duration.total_seconds():.2f} seconds.")
    print("="*60)
    sys.exit(0) # Ensure exit code 0 on success

if __name__ == "__main__":
    main()
