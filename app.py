
import os
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, jsonify, request, redirect,
    url_for, session, render_template_string, flash
)
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable missing hai.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
)

allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise RuntimeError("Supabase environment variables missing hain.")

supabase = create_client(supabase_url, supabase_key)


# ---------------- SECURITY HELPERS ----------------

def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


def valid_csrf():
    supplied = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(supplied, expected))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------- PUBLIC API ----------------

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
        return jsonify({"cars": result.data or []})
    except Exception:
        app.logger.exception("Cars fetch failed")
        return jsonify({"error": "Unable to load cars"}), 500


# ---------------- LOGIN PAGE ----------------

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Login | Vishal Car Rental</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;
padding:20px;background:#0f172a;color:#f8fafc;font-family:Arial}
.card{width:100%;max-width:390px;background:#1e293b;padding:30px;
border-radius:16px}
input,button{width:100%;padding:13px;margin-top:12px;border-radius:8px;
font-size:16px}
input{background:#0f172a;color:white;border:1px solid #475569}
button{background:#22c55e;border:0;font-weight:bold;cursor:pointer}
.error{color:#fca5a5}
</style>
</head>
<body>
<div class="card">
<h1>Admin Login</h1>
<p>Vishal Car Rental & Tour and Travels</p>
{% for message in get_flashed_messages() %}
<p class="error">{{ message }}</p>
{% endfor %}
<form method="post">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<input name="username" placeholder="Username" required
autocomplete="username">
<input type="password" name="password" placeholder="Password"
required autocomplete="current-password">
<button type="submit">Login</button>
</form>
</div>
</body>
</html>
"""


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Page expire ho gaya. Dobara try karo.")
            return redirect(url_for("admin_login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            result = (
                supabase.table("admin")
                .select("id, username, password_hash")
                .eq("username", username)
                .limit(1)
                .execute()
            )

            admins = result.data or []

            if admins:
                session.clear()
                session["admin_logged_in"] = True
                session["admin_id"] = admins[0]["id"]
                session.permanent = True
                csrf_token()
                return redirect(url_for("admin_dashboard"))

            flash("Username ya password galat hai.")

        except Exception:
            app.logger.exception("Admin login failed")
            flash("Login abhi nahi ho paya. Server logs check karo.")

    return render_template_string(LOGIN_HTML)


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    if not valid_csrf():
        return "Invalid CSRF token", 400

    session.clear()
    return redirect(url_for("admin_login"))


# ---------------- ADMIN DASHBOARD ----------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Car Admin Dashboard</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f1f5f9;color:#0f172a;font-family:Arial}
header{background:#0f172a;color:white;padding:18px 5%;
display:flex;justify-content:space-between;align-items:center;gap:12px}
header h2{margin:0;font-size:20px}
main{max-width:1200px;margin:25px auto;padding:0 16px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.stat,.panel{background:white;border-radius:12px;padding:20px;
box-shadow:0 3px 15px #0f172a0c}
.stat strong{display:block;font-size:27px;margin-top:8px}
.layout{display:grid;grid-template-columns:minmax(260px,350px) minmax(0,1fr);
gap:20px;margin-top:22px;align-items:start}
input,select,textarea,button{width:100%;padding:11px;margin-top:7px;
margin-bottom:12px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}
label{font-size:14px;font-weight:bold}
textarea{min-height:85px;resize:vertical}
button{background:#16a34a;color:white;border:0;font-weight:bold;cursor:pointer}
.logout{background:#dc2626;width:auto;margin:0}
.delete{background:#dc2626;width:auto;margin:0}
.notice{background:#dcfce7;color:#166534;padding:12px;
border-radius:8px;margin-bottom:15px}
.error{background:#fee2e2;color:#991b1b}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:590px}
th,td{text-align:left;padding:12px;border-bottom:1px solid #e2e8f0}
th{background:#f8fafc}
.car-image{width:75px;height:50px;object-fit:cover;border-radius:5px}
.status{font-size:12px;padding:5px 7px;border-radius:5px;
background:#dcfce7;color:#166534}
.off{background:#fee2e2;color:#991b1b}
@media(max-width:800px){.layout{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<h2>Vishal Car Rental — Admin</h2>
<form method="post" action="{{ url_for('admin_logout') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<button class="logout" type="submit">Logout</button>
</form>
</header>
<main>
{% for message in get_flashed_messages() %}
<div class="notice">{{ message }}</div>
{% endfor %}

<div class="stats">
<div class="stat">Total Cars<strong>{{ cars|length }}</strong></div>
<div class="stat">Available<strong>{{ available }}</strong></div>
<div class="stat">Unavailable<strong>{{ cars|length - available }}</strong></div>
</div>

<div class="layout">
<section class="panel">
<h2>Add New Car</h2>
<form method="post" action="{{ url_for('admin_add_car') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

<label>Car Name *</label>
<input name="name" placeholder="Swift VXI" required maxlength="100">

<label>Brand *</label>
<input name="brand" placeholder="Maruti Suzuki" required maxlength="100">

<label>Price per day (₹) *</label>
<input type="number" name="price" min="0" step="0.01" required>

<label>Year *</label>
<input type="number" name="year" min="1900" max="2100" required>

<label>Fuel *</label>
<select name="fuel" required>
<option value="">Select fuel</option>
<option>Petrol</option><option>Diesel</option>
<option>CNG</option><option>Electric</option><option>Hybrid</option>
</select>

<label>Transmission *</label>
<select name="transmission" required>
<option value="">Select transmission</option>
<option>Manual</option><option>Automatic</option>
</select>

<label>Image URL</label>
<input type="url" name="image_url" placeholder="https://example.com/car.jpg">

<label>Description</label>
<textarea name="description" maxlength="2000"
placeholder="Car details and features"></textarea>

<label>
<input type="checkbox" name="is_available" value="true"
checked style="width:auto;margin:0 5px 12px 0">
Available for booking
</label>
<button type="submit">+ Add Car</button>
</form>
</section>

<section class="panel">
<h2>Car List</h2>
<div class="table-wrap">
<table>
<thead><tr><th>Image</th><th>Car Details</th>
<th>Price/day</th><th>Status</th><th>Action</th></tr></thead>
<tbody>
{% for car in cars %}
<tr>
<td>
{% if car.get('image_url') %}
<img class="car-image" src="{{ car.get('image_url') }}"
alt="{{ car.get('name', 'Car') }}" loading="lazy">
{% else %}No image{% endif %}
</td>
<td><strong>{{ car.get('name', 'Unnamed') }}</strong><br>
{{ car.get('brand', '') }} · {{ car.get('year', '') }}<br>
<small>{{ car.get('fuel', '') }} · {{ car.get('transmission', '') }}</small>
</td>
<td>₹{{ car.get('price', 0) }}</td>
<td>
{% if car.get('is_available') %}
<span class="status">Available</span>
{% else %}
<span class="status off">Unavailable</span>
{% endif %}
</td>
<td>
<form method="post"
action="{{ url_for('admin_delete_car', car_id=car.get('id')) }}"
onsubmit="return confirm('Kya is car ko permanently delete karna hai?')">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<button class="delete" type="submit">Delete</button>
</form>
</td>
</tr>
{% else %}
<tr><td colspan="5">Abhi koi car add nahi hai.</td></tr>
{% endfor %}
</tbody>
</table>
</div>
</section>
</div>
</main>
</body>
</html>
"""


@app.route("/admin")
@admin_required
def admin_dashboard():
    try:
        result = (
            supabase.table("cars")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        cars = result.data or []
        available = sum(
            1 for car in cars if car.get("is_available") is True
        )

        return render_template_string(
            DASHBOARD_HTML,
            cars=cars,
            available=available,
        )

    except Exception:
        app.logger.exception("Dashboard load failed")
        return "Dashboard load nahi hua. Server logs check karo.", 500


# ---------------- ADD CAR ----------------

@app.route("/admin/cars/add", methods=["POST"])
@admin_required
def admin_add_car():
    if not valid_csrf():
        return "Invalid CSRF token. Dashboard reload karo.", 400

    name = request.form.get("name", "").strip()
    brand = request.form.get("brand", "").strip()
    fuel = request.form.get("fuel", "").strip()
    transmission = request.form.get("transmission", "").strip()
    image_url = request.form.get("image_url", "").strip()
    description = request.form.get("description", "").strip()

    if not name or not brand or not fuel or not transmission:
        flash("Saare required fields fill karo.")
        return redirect(url_for("admin_dashboard"))

    if len(name) > 100 or len(brand) > 100 or len(description) > 2000:
        flash("Name, brand ya description bahut lamba hai.")
        return redirect(url_for("admin_dashboard"))

    if image_url:
        parsed_url = urlparse(image_url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            flash("Valid HTTP/HTTPS image URL enter karo.")
            return redirect(url_for("admin_dashboard"))

    try:
        price = float(request.form.get("price", ""))
        year = int(request.form.get("year", ""))
    except (ValueError, TypeError):
        flash("Price aur year valid enter karo.")
        return redirect(url_for("admin_dashboard"))

    if price < 0 or not 1900 <= year <= 2100:
        flash("Price ya year valid nahi hai.")
        return redirect(url_for("admin_dashboard"))

    car_data = {
        "name": name,
        "brand": brand,
        "price": price,
        "year": year,
        "fuel": fuel,
        "transmission": transmission,
        "image_url": image_url or None,
        "description": description or None,
        "is_available": request.form.get("is_available") == "true",
    }

    try:
        supabase.table("cars").insert(car_data).execute()
        flash("Car successfully add ho gayi!")
    except Exception:
        app.logger.exception("Car insert failed")
        flash("Car add nahi hui. Database columns aur logs check karo.")

    return redirect(url_for("admin_dashboard"))


# ---------------- DELETE CAR ----------------

@app.route("/admin/cars/<car_id>/delete", methods=["POST"])
@admin_required
def admin_delete_car(car_id):
    if not valid_csrf():
        return "Invalid CSRF token. Dashboard reload karo.", 400

    try:
        result = (
            supabase.table("cars")
            .delete()
            .eq("id", car_id)
            .execute()
        )

        if result.data:
            flash("Car successfully delete ho gayi.")
        else:
            flash("Car nahi mili ya delete nahi hui.")

    except Exception:
        app.logger.exception("Car deletion failed")
        flash("Delete fail hua. Database ID aur logs check karo.")

    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
