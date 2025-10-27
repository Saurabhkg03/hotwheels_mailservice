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
        try:
            page.goto(URL, timeout=60000) # Increased timeout
            # Wait longer and potentially for a specific element if needed
            page.wait_for_timeout(7000)  # wait 7 sec for JS to populate
            html = page.content()
        except Exception as e:
            print(f"🚨 Error fetching page: {e}")
            html = "" # Return empty string on error
        finally:
            browser.close()
    return html

def parse_product_list(html: str) -> list[str]:
    """
    Given the rendered HTML, extract product names ONLY for items NOT marked as "Out Of Stock".
    Products are in <div class="product-grid-item">.
    Product name is in <a class="product-name ng-binding">.
    Sold out items have a <div class="out-of-stock"> child within the <div class="caption">.
    Return a list of available product names (strings).
    """
    if not html: # Handle case where fetching failed
        return []
    soup = BeautifulSoup(html, "html.parser")
    # Select the main container for each product
    product_items = soup.select("div.product-grid-item")
    available_names = []
    for item in product_items:
        # Check if the 'out-of-stock' div exists within this product item's caption
        # Check within the 'caption' div specifically, as 'out-of-stock' might appear elsewhere
        caption_div = item.select_one("div.caption")
        is_sold_out = caption_div and caption_div.select_one("div.out-of-stock")

        if not is_sold_out:
            # If not sold out, find the product name anchor within this item
            name_anchor = item.select_one("a.product-name.ng-binding")
            if name_anchor:
                # Extract and add the name if found
                name = name_anchor.get_text(strip=True)
                available_names.append(name)
            else:
                print("⚠️ Warning: Found product item without a name anchor.") # Optional warning
        #else:
            # Optionally log skipped items
            #name_anchor_sold_out = item.select_one("a.product-name.ng-binding")
            #if name_anchor_sold_out:
            #    print(f"  ↳ Skipping sold out: {name_anchor_sold_out.get_text(strip=True)}")

    return available_names


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
            # Ensure loaded data is a list of strings
            if isinstance(data, list) and all(isinstance(item, str) for item in data):
                return data
            else:
                print(f"⚠️ Warning: '{PREVIOUS_FILE}' content is not a list of strings. Resetting.")
                return []
    except json.JSONDecodeError:
        print(f"🚨 Error: Could not decode JSON from '{PREVIOUS_FILE}'. Resetting.")
        return []
    except Exception as e:
        print(f"🚨 Error loading '{PREVIOUS_FILE}': {e}. Resetting.")
        return []

def save_current_list(current: list[str]) -> None:
    """
    Overwrite previous.json with the new list so next run only sees newer items.
    """
    try:
        with open(PREVIOUS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"🚨 Error saving current list to '{PREVIOUS_FILE}': {e}")


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

    subject = f"🏎️ [{len(new_items)}] New Hot Wheels Item(s) In Stock!" # Dynamic subject

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
