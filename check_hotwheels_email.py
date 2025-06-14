import json
import os
import sys
import smtplib
from email.message import EmailMessage
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────────────────────
# 1) CONFIGURATION / CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

URL = "https://www.toymarche.com/brand/hot-wheels"
PREVIOUS_FILE = "previous.json"

# Gmail SMTP (from GitHub Secrets)
GMAIL_USER         = os.getenv("GMAIL_USER", "")         # e.g. "your.email@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "") # the 16-char App Password
EMAIL_TO           = os.getenv("EMAIL_TO", "")           # where you want the notification (comma-separated for multiple)

# Banner image URL (hosted online somewhere, or you can replace with your own)
BANNER_URL = "https://shop.mattel.com.au/cdn/shop/files/Poster_Thumbnail.png?v=1710824118&width=1100"  # example Hot Wheels banner (replace if you want)

# ─────────────────────────────────────────────────────────────────────────────
# 2) HELPERS: Fetch + Parse
# ─────────────────────────────────────────────────────────────────────────────

def fetch_rendered_html() -> str:
    """
    Launch headless Chromium (Playwright), navigate to URL, wait for JS to load,
    and return the fully-rendered HTML as a string.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(5000)  # wait 5 sec for JS to populate
        html = page.content()
        browser.close()
    return html

def parse_product_list(html: str) -> list[str]:
    """
    Given the rendered HTML, extract all "product name" strings.
    Each product name lives in <a class="product-name ng-binding">…</a>.
    Return a list of names (strings).
    """
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("a.product-name.ng-binding")
    names = [a.get_text(strip=True) for a in anchors]
    return names

# ─────────────────────────────────────────────────────────────────────────────
# 3) Compare to previous.json
# ─────────────────────────────────────────────────────────────────────────────

def load_previous_list() -> list[str]:
    """
    Load the JSON file that holds the previously-seen product names.
    If missing or invalid, return an empty list.
    """
    if not os.path.exists(PREVIOUS_FILE):
        return []
    try:
        with open(PREVIOUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_current_list(current: list[str]) -> None:
    """
    Overwrite previous.json with the new list so next run only sees newer items.
    """
    with open(PREVIOUS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# 4) Send Email via Gmail SMTP (HTML version with banner)
# ─────────────────────────────────────────────────────────────────────────────

def send_email_alert(new_items: list[str]) -> None:
    """
    Compose and send an HTML email listing all new_items with a banner.
    Uses Gmail SMTP with an App Password.
    """
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and EMAIL_TO):
        print("🚨 Missing Gmail credentials or destination address. Cannot send email.")
        return

    # Split the comma-separated string from EMAIL_TO into a list of recipients
    recipient_list = [email.strip() for email in EMAIL_TO.split(',') if email.strip()]

    if not recipient_list:
        print("🚨 No valid recipient email addresses found in EMAIL_TO. Cannot send email.")
        return

    subject = "🏎️ [Hot Wheels] New Items in Stock!"

    # Build the HTML content
    html_body = f"""
    <html>
    <head>
      <style>
        body {{
          font-family: Arial, sans-serif;
          background-color: #f9f9f9;
          color: #333;
          margin: 0; padding: 0;
        }}
        .container {{
          max-width: 600px;
          margin: 20px auto;
          background-color: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
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
          color: white !important;
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
        <img src="{BANNER_URL}" alt="Hot Wheels Banner" class="banner" />
        <div class="content">
          <h1>New Hot Wheels Cars Just Arrived!</h1>
          <p>Hey there,</p>
          <p>The following new Hot Wheels cars have just appeared on ToyMarche:</p>
          <ul>
    """

    for name in new_items:
        html_body += f"<li>{name}</li>"

    html_body += f"""
          </ul>
          <p>
            <a href="{URL}" class="button" target="_blank">Check Them Out</a>
          </p>
          <p>Good luck grabbing them first!</p>
        </div>
      </div>
      <div class="footer">
        &copy; {datetime.utcnow().year} ToyMarche Hot Wheels Tracker
      </div>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(recipient_list) # Assign the joined list to the 'To' header
    msg.set_content("You need an HTML-compatible email client to view this message.")
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg) # send_message handles multiple recipients from msg["To"]
        print("✅ Email sent successfully.")
    except Exception as e:
        print("🚨 Failed to send email:", e)

# ─────────────────────────────────────────────────────────────────────────────
# 5) MAIN LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print(f"[{datetime.utcnow().isoformat()}] Checking ToyMarche Hot Wheels…")

    # 1) Load old list
    prev_list = load_previous_list()
    print(f"  ↳ Previously saw {len(prev_list)} items.")

    # 2) Fetch & parse current
    html = fetch_rendered_html()
    current_list = parse_product_list(html)
    print(f"  ↳ Currently saw {len(current_list)} items.")

    # 3) Compare
    new_items = [item for item in current_list if item not in prev_list]
    if new_items:
        print(f"  ↳ Found {len(new_items)} new item(s):")
        for itm in new_items:
            print(f"      • {itm}")

        # 4) Send email alert
        send_email_alert(new_items)

        # 5) Save the updated list
        save_current_list(current_list)
        sys.exit(0)
    else:
        print("  ↳ No new items found. ✅")
        # Even if no new items, overwrite so next run uses the latest list
        save_current_list(current_list)
        sys.exit(0)

if __name__ == "__main__":
    main()
