import json
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────────────────────
# 1) CONFIGURATION / CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

URL = "https://www.toymarche.com/brand/hot-wheels"
PREVIOUS_FILE = "previous.json"

# Gmail SMTP (from GitHub Secrets)
GMAIL_USER         = os.getenv("GMAIL_USER", "")           # e.g. "your.email@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")   # the 16-char App Password
EMAIL_TO           = os.getenv("EMAIL_TO", "")             # where you want the notification

# Banner image URL to display at the top of the email
BANNER_URL = "https://i.imgur.com/YourBannerImage.jpg"  # ← replace with real banner URL

# ─────────────────────────────────────────────────────────────────────────────
# 2) HELPERS: Fetch + Parse
# ─────────────────────────────────────────────────────────────────────────────

def fetch_rendered_html() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()
    return html

def parse_product_list(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    items: dict[str, str] = {}
    for caption_div in soup.select("div.caption"):
        title_anchor = caption_div.select_one("a.product-name.ng-binding")
        if not title_anchor:
            continue
        name = title_anchor.get_text(strip=True)
        container = caption_div.parent
        img_tag = container.select_one("img")
        if img_tag and img_tag.has_attr("src"):
            img_url = img_tag["src"]
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                img_url = "https://www.toymarche.com" + img_url
        else:
            img_url = ""
        items[name] = img_url
    return items

# ─────────────────────────────────────────────────────────────────────────────
# 3) Compare + Save
# ─────────────────────────────────────────────────────────────────────────────

def load_previous_map() -> dict[str, str]:
    if not os.path.exists(PREVIOUS_FILE):
        return {}
    try:
        with open(PREVIOUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_current_map(current_map: dict[str, str]) -> None:
    with open(PREVIOUS_FILE, "w", encoding="utf-8") as f:
        json.dump(current_map, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# 4) Email Sender
# ─────────────────────────────────────────────────────────────────────────────

def send_email_alert(new_items: list[str], img_map: dict[str, str]) -> None:
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and EMAIL_TO):
        print("🚨 Missing Gmail credentials or destination address. Cannot send email.")
        return

    subject = "🏎️ [Hot Wheels] New Items in Stock!"
    html_lines = [
        "<html>",
        "<body style='font-family: Arial, sans-serif; line-height: 1.4;'>",
        f"<div style='text-align: center; margin-bottom: 20px;'>"
        f"<img src='{BANNER_URL}' alt='Hot Wheels Banner' style='max-width: 100%; height: auto;'/>"
        f"</div>",
        "<h2 style='color: #E03E2D;'>Hey Saurabh,</h2>",
        "<p>The following new <strong>Hot Wheels</strong> cars have just appeared on ToyMarche:</p>",
        "<ul style='list-style: none; padding: 0;'>"
    ]

    for name in new_items:
        img_url = img_map.get(name, "")
        html_lines.append("<li style='margin-bottom: 30px;'>")
        html_lines.append(f"<h3 style='margin: 0 0 5px 0; font-size: 1.1em;'>{name}</h3>")
        if img_url:
            html_lines.append(
                f"<img src='{img_url}' alt='{name}' style='max-width: 200px; display: block; margin-bottom: 5px;' />"
            )
        html_lines.append("</li>")

    html_lines.extend([
        "</ul>",
        f"<p>Check them out here: <a href='{URL}' style='color: #1E90FF;'>{URL}</a></p>",
        "<p style='margin-top: 40px;'>Good luck grabbing them first! 🏁</p>",
        "</body>",
        "</html>"
    ])
    html_body = "\n".join(html_lines)

    plain_lines = [
        "Hey Saurabh,",
        "",
        "The following new Hot Wheels cars have just appeared on ToyMarche:",
    ] + [f"• {name}" for name in new_items] + [
        "",
        f"Check them out: {URL}",
        "Good luck grabbing them first!"
    ]
    plain_body = "\n".join(plain_lines)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print("✅ Email with banner and images sent successfully.")
    except Exception as e:
        print("🚨 Failed to send email:", e)

# ─────────────────────────────────────────────────────────────────────────────
# 5) Main Execution
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"[{datetime.utcnow().isoformat()}] Checking ToyMarche Hot Wheels…")

    prev_map = load_previous_map()
    print(f"  ↳ Previously saw {len(prev_map)} items.")

    html = fetch_rendered_html()
    product_map = parse_product_list(html)
    print(f"  ↳ Currently saw {len(product_map)} items.")

    # Detect new or updated items
    new_items = [name for name, img in product_map.items()
                 if name not in prev_map or prev_map[name] != img]

    if new_items:
        print(f"  ↳ Found {len(new_items)} new item(s):")
        for item in new_items:
            print(f"     • {item}")
        send_email_alert(new_items, product_map)
        save_current_map(product_map)
    else:
        print("  ↳ No new items found. ✅")
        save_current_map(product_map)

if __name__ == "__main__":
    main()
