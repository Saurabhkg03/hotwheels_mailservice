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
BANNER_URL = "https://shop.mattel.com.au/cdn/shop/files/Poster_Thumbnail.png?v=1710824118&width=1100"      # ← replace with your banner URL

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
        page.wait_for_timeout(5000)  # wait 5 seconds for JavaScript to populate products
        html = page.content()
        browser.close()
    return html

def parse_product_list(html: str) -> dict[str, str]:
    """
    Given the rendered HTML, extract each product's name and its image URL.
    Returns a dict mapping name -> image_url.
    """
    soup = BeautifulSoup(html, "html.parser")
    items: dict[str, str] = {}

    # Each product is inside a container that has both the <img> and <div class="caption">
    # We select all caption divs, then find the associated image under the same parent.
    for caption_div in soup.select("div.caption"):
        # 1) find the <a class="product-name ng-binding">…</a>
        title_anchor = caption_div.select_one("a.product-name.ng-binding")
        if not title_anchor:
            continue

        name = title_anchor.get_text(strip=True)

        # 2) navigate up to container that wraps both the image and the caption
        container = caption_div.parent
        img_tag = container.select_one("img")
        if img_tag and img_tag.has_attr("src"):
            img_url = img_tag["src"]
            # If src is relative, convert to absolute
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                img_url = "https://www.toymarche.com" + img_url
        else:
            img_url = ""  # no image found fallback

        items[name] = img_url

    return items

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
# 4) Send Email via Gmail SMTP (with banner + images)
# ─────────────────────────────────────────────────────────────────────────────

def send_email_alert(new_items: list[str], img_map: dict[str, str]) -> None:
    """
    Compose and send an HTML email listing all new_items, each with its image,
    plus a banner at the top. Uses Gmail SMTP with an App Password.
    """
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and EMAIL_TO):
        print("🚨 Missing Gmail credentials or destination address. Cannot send email.")
        return

    subject = "🏎️ [Hot Wheels] New Items in Stock!"
    # Build HTML body
    html_lines = [
        "<html>",
        "<body style='font-family: Arial, sans-serif; line-height: 1.4;'>",
        # Banner at top
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
        html_lines.append(f"  <h3 style='margin: 0 0 5px 0; font-size: 1.1em;'>{name}</h3>")
        if img_url:
            html_lines.append(
                f"  <img src='{img_url}' alt='{name}' style='max-width: 200px; display: block; margin-bottom: 5px;' />"
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

    # Build multipart message (plain-text fallback + HTML)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO

    # Plain-text fallback
    plain_body_lines = [
        "Hey Saurabh,",
        "",
        "The following new Hot Wheels cars have just appeared on ToyMarche:",
    ]
    for name in new_items:
        plain_body_lines.append(f"• {name}")
    plain_body_lines.extend([
        "",
        f"Check them out here: {URL}",
        "",
        "Good luck grabbing them first!"
    ])
    plain_body = "\n".join(plain_body_lines)

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send via Gmail SMTP SSL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print("✅ Email with banner and images sent successfully.")
    except Exception as e:
        print("🚨 Failed to send email:", e)

# ─────────────────────────────────────────────────────────────────────────────
# 5) MAIN LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print(f"[{datetime.utcnow().isoformat()}] Checking ToyMarche Hot Wheels…")

    # 1) Load previously seen names
    prev_list = load_previous_list()
    print(f"  ↳ Previously saw {len(prev_list)} items.")

    # 2) Fetch & parse current (name → image_url mapping)
    html = fetch_rendered_html()
    product_map = parse_product_list(html)
    current_list = list(product_map.keys())
    print(f"  ↳ Currently saw {len(current_list)} items.")

    # 3) Compare: identify new names
    new_items = [name for name in current_list if name not in prev_list]
    if new_items:
        print(f"  ↳ Found {len(new_items)} new item(s):")
        for itm in new_items:
            print(f"     • {itm}")

        # 4) Send email alert with banner + images
        send_email_alert(new_items, product_map)

        # 5) Save the updated list of names
        save_current_list(current_list)
        sys.exit(0)
    else:
        print("  ↳ No new items found. ✅")
        # Overwrite so next run uses the latest list
        save_current_list(current_list)
        sys.exit(0)

if __name__ == "__main__":
    main()
