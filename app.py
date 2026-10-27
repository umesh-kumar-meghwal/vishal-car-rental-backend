
import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# 1. Pehle Flask app banao
app = Flask(__name__)

# 2. Uske baad CORS configure karo
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": allowed_origins
        }
    }
)

# 3. Supabase connection
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise RuntimeError(
        "SUPABASE_URL ya SUPABASE_SERVICE_ROLE_KEY missing hai. .env check karo."
    )

supabase = create_client(supabase_url, supabase_key)


@app.route("/")
def home():
    return jsonify({"message": "Car website API is running"})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/cars")
def get_cars():
    try:
        result = (
            supabase.table("cars")
            .select("*")
            .eq("is_available", True)
            .order("created_at", desc=True)
            .execute()
        )

        return jsonify({"cars": result.data})

    except Exception:
        app.logger.exception("Cars fetch failed")
        return jsonify({"error": "Unable to load cars"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
