from flask import Flask, render_template, request, jsonify
from register_daraja_live import register_urls
import logging

app = Flask(__name__)

# Basic route to access both forms
@app.route("/")
def index():
    return """
    <h2>Daraja Registration Portal</h2>
    <ul>
      <li><a href='/register_sandbox'>Register Sandbox</a></li>
      <li><a href='/register_live'>Register Live</a></li>
    </ul>
    """

@app.route("/register_sandbox")
def sandbox_page():
    return render_template("register_sandbox.html")

@app.route("/register_live")
def live_page():
    return render_template("register_live.html")

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    env = data.get("env", "sandbox").lower()
    key = data.get("consumer_key")
    secret = data.get("consumer_secret")
    shortcode = data.get("shortcode")
    callback = data.get("callback_url")

    if not all([key, secret, shortcode, callback]):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    live = env == "live"
    base_url = "https://api.safaricom.co.ke" if live else "https://sandbox.safaricom.co.ke"

    try:
        result = register_urls(
            env_name=env.upper(),
            base_url=base_url,
            key=key,
            secret=secret,
            shortcode=shortcode,
            callback_base=callback,
            live=live
        )
        return jsonify(result)
    except Exception as e:
        logging.exception("Daraja registration failed")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5005)
