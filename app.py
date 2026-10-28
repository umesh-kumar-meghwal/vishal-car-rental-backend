import os
import time
import uuid
import secrets
from collections import defaultdict, deque
from functools import wraps

from flask import (
    Flask, request, jsonify, session, redirect, url_for,
    render_template_string, flash
)
from flask_cors import CORS
from supabase import create_client
from werkzeug.utils import secure_filename

from extra_routes import register_extra_routes

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 90 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024
MAX_GALLERY_IMAGES = 10
STORAGE_BUCKET = "car-images"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be provided.")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if allowed_origins:
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})


# ==========================================
# AUTH & CSRF (Plain-text Password Check)
# ==========================================

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]

app.jinja_env.globals["csrf_token"] = get_csrf_token


def valid_csrf():
    submitted = request.form.get("csrf_token", "")
    saved = session.get("csrf_token", "")
    return bool(submitted and saved and submitted == saved)


def admin_required(view_function):
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view_function(*args, **kwargs)
    return wrapped


# Plain-text password verification (Without Hash)
def verify_password(stored, given):
    return str(stored or "").strip() == str(given or "").strip()


_login_fails = defaultdict(deque)

def _client_ip():
    return (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()

def login_blocked(limit=10, window=300):
    q = _login_fails[_client_ip()]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    return len(q) >= limit


# ==========================================
# IMAGE UPLOAD HELPER
# ==========================================

def upload_car_image(file):
    if not file or not file.filename:
        raise ValueError("Please choose an image file.")

    orig = secure_filename(file.filename)
    if "." not in orig:
        raise ValueError("Image extension missing.")

    ext = orig.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Only JPG, JPEG, PNG, and WEBP formats are accepted.")

    content = file.read()
    if not content:
        raise ValueError("Uploaded image file is empty.")
    if len(content) > MAX_IMAGE_SIZE:
        raise ValueError("Image size exceeds the 8MB limit.")

    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp"
    }.get(ext, "application/octet-stream")

    path = f"fleet/{uuid.uuid4().hex}.{ext}"
    supabase.storage.from_(STORAGE_BUCKET).upload(
        path, content, {"content-type": mime, "upsert": "false"}
    )

    url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(path)
    if isinstance(url, dict):
        url = url.get("publicUrl") or url.get("url")
    return url


# ==========================================
# BASE MODERN ADMIN SHELL
# ==========================================

BASE_ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title or 'Admin Portal' }} | Vishal Car Rental</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #4f46e5;
      --primary-hover: #4338ca;
      --primary-light: #eef2ff;
      --sidebar: #0f172a;
      --sidebar-hover: #1e293b;
      --sidebar-active: #312e81;
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --danger: #ef4444;
      --success: #10b981;
      --radius: 12px;
      --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px 0 rgba(0, 0, 0, 0.04);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      font-size: 14px;
    }
    a { color: inherit; text-decoration: none; }
    .layout { display: grid; grid-template-columns: 260px 1fr; min-height: 100vh; }
    
    /* Sidebar */
    aside {
      background: var(--sidebar);
      color: #94a3b8;
      padding: 24px 16px;
      position: sticky;
      top: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      border-right: 1px solid #1e293b;
      overflow-y: auto;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      color: #fff;
      padding: 0 8px 24px;
      border-bottom: 1px solid #1e293b;
      margin-bottom: 16px;
    }
    .brand-logo {
      width: 40px; height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--primary), #818cf8);
      display: grid;
      place-items: center;
      font-weight: 800;
      color: #fff;
      font-size: 18px;
    }
    .nav-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #475569;
      font-weight: 700;
      margin: 18px 8px 6px;
    }
    nav a {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 8px;
      font-weight: 500;
      color: #94a3b8;
      transition: all 0.2s;
      margin-bottom: 2px;
    }
    nav a:hover { background: var(--sidebar-hover); color: #fff; }
    nav a.active {
      background: var(--primary);
      color: #fff;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
    }
    .sidebar-footer { margin-top: auto; padding-top: 16px; border-top: 1px solid #1e293b; }
    .btn-logout {
      width: 100%;
      padding: 10px;
      background: rgba(239,68,68,0.12);
      color: #f87171;
      border: 1px solid rgba(239,68,68,0.25);
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-logout:hover { background: #ef4444; color: #fff; }

    /* Main Area */
    main { padding: 32px; max-width: 1320px; width: 100%; margin: 0 auto; }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 24px;
    }
    h1 { margin: 0; font-size: 24px; font-weight: 800; color: #0f172a; }
    .subhead { color: var(--muted); margin: 4px 0 0; }
    
    /* Common UI components */
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 16px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      background: var(--primary);
      color: #fff;
      font-size: 13px;
      transition: 0.2s;
    }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary { background: #f1f5f9; color: var(--text); border: 1px solid var(--border); }
    .btn-secondary:hover { background: #e2e8f0; }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-danger:hover { background: #dc2626; }
    .btn-sm { padding: 6px 10px; font-size: 12px; border-radius: 6px; }

    .flash {
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 20px;
      font-weight: 500;
    }
    .flash.ok { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    .flash.err { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }

    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; }
    th {
      background: #f8fafc;
      padding: 12px 14px;
      font-size: 12px;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }
    td {
      padding: 14px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: none; }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 99px;
      font-size: 12px;
      font-weight: 600;
    }
    .badge-on { background: #dcfce7; color: #15803d; }
    .badge-off { background: #f1f5f9; color: #64748b; }
    
    .form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }
    .form-full { grid-column: 1 / -1; }
    .field { display: flex; flex-direction: column; gap: 6px; }
    label { font-weight: 600; font-size: 13px; color: #334155; }
    input, select, textarea {
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font: inherit;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
    }
    textarea { min-height: 120px; }

    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
      aside { height: auto; position: static; }
      .form-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<div class="layout">
  <aside>
    <div class="brand">
      <div class="brand-logo">V</div>
      <div>
        <div style="font-weight:700; color:#fff">Vishal Rental</div>
        <div style="font-size:11px; color:#64748b">Admin Control Center</div>
      </div>
    </div>

    <div class="nav-label">Fleet Operations</div>
    <nav>
      <a href="{{ url_for('admin_dashboard') }}" class="{{ 'active' if active_nav == 'fleet' else '' }}">
        🚘 Fleet & Cars
      </a>
      <a href="{{ url_for('admin_add_car_page') }}" class="{{ 'active' if active_nav == 'add_car' else '' }}">
        ➕ Add New Car
      </a>
    </nav>

    <div class="nav-label">Content & Community</div>
    <nav>
      <a href="{{ url_for('admin_reviews_page') }}" class="{{ 'active' if active_nav == 'reviews' else '' }}">
        ⭐ Reviews
      </a>
      <a href="{{ url_for('admin_blogs_page') }}" class="{{ 'active' if active_nav == 'blogs' else '' }}">
        📰 Blog Articles
      </a>
      <a href="{{ url_for('admin_comments_page') }}" class="{{ 'active' if active_nav == 'comments' else '' }}">
        💬 Blog Comments
      </a>
      <a href="{{ url_for('admin_faqs_page') }}" class="{{ 'active' if active_nav == 'faqs' else '' }}">
        ❓ FAQs
      </a>
    </nav>

    <div class="nav-label">Lead Management</div>
    <nav>
      <a href="{{ url_for('admin_messages_page') }}" class="{{ 'active' if active_nav == 'messages' else '' }}">
        ✉️ Contact Inquiries
      </a>
      <a href="{{ url_for('admin_subscribers_page') }}" class="{{ 'active' if active_nav == 'subscribers' else '' }}">
        📫 Newsletter Subscribers
      </a>
    </nav>

    <div class="sidebar-footer">
      <form action="{{ url_for('admin_logout') }}" method="POST">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="btn-logout">Sign Out</button>
      </form>
    </div>
  </aside>

  <main>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class="flash {{ 'ok' if cat == 'ok' else 'err' }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}
  </main>
</div>
</body>
</html>
"""

# ==========================================
# AUTH VIEWS
# ==========================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Sign In | Vishal Car Rental</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body { margin:0; font-family:'Plus Jakarta Sans',sans-serif; background:#0f172a; display:grid; place-items:center; min-height:100vh; padding:20px; }
    .box { background:#fff; padding:40px; border-radius:16px; width:100%; max-width:400px; box-shadow:0 20px 25px -5px rgba(0,0,0,0.3); }
    h2 { margin:0 0 8px; font-weight:800; color:#0f172a; }
    p { margin:0 0 24px; color:#64748b; font-size:14px; }
    .field { margin-bottom:18px; }
    label { display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:#334155; }
    input { width:100%; padding:11px; border:1px solid #cbd5e1; border-radius:8px; box-sizing:border-box; font:inherit; }
    input:focus { outline:none; border-color:#4f46e5; box-shadow:0 0 0 3px rgba(79,70,229,0.2); }
    button { width:100%; padding:12px; background:#4f46e5; border:0; border-radius:8px; color:#fff; font-weight:700; cursor:pointer; font-size:15px; }
    button:hover { background:#4338ca; }
    .err { background:#fee2e2; color:#991b1b; padding:10px 12px; border-radius:8px; font-size:13px; margin-bottom:16px; }
  </style>
</head>
<body>
  <div class="box">
    <h2>Admin Sign In</h2>
    <p>Vishal Car Rental Management Panel</p>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for cat, m in messages %}<div class="err">{{ m }}</div>{% endfor %}{% endif %}
    {% endwith %}
    <form method="POST">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <div class="field">
        <label>Admin Username</label>
        <input type="text" name="username" required autofocus placeholder="admin">
      </div>
      <div class="field">
        <label>Password</label>
        <input type="password" name="password" required placeholder="••••••••">
      </div>
      <button type="submit">Sign In</button>
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
            flash("Invalid form session. Please try again.", "err")
            return render_template_string(LOGIN_HTML)

        if login_blocked():
            flash("Too many failed attempts. Try again in 5 minutes.", "err")
            return render_template_string(LOGIN_HTML)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        try:
            res = supabase.table("admin").select("*").eq("username", username).limit(1).execute()
            user = res.data[0] if res.data else None
            # Plain text check without hashing
            if user and verify_password(user.get("password"), password):
                session.clear()
                session["admin_logged_in"] = True
                session["admin_user"] = user.get("username")
                flash("Signed in successfully.", "ok")
                return redirect(url_for("admin_dashboard"))

            _login_fails[_client_ip()].append(time.time())
            flash("Invalid username or password.", "err")
        except Exception:
            app.logger.exception("Login lookup error")
            flash("Authentication service error.", "err")

    return render_template_string(LOGIN_HTML)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# ==========================================
# FLEET MANAGEMENT (CARS)
# ==========================================

CARS_LIST_HTML = BASE_ADMIN_HTML + """
{% block content %}
<div class="header">
  <div>
    <h1>Fleet Vehicles</h1>
    <p class="subhead">Manage your car fleet availability, specs, and pricing</p>
  </div>
  <a href="{{ url_for('admin_add_car_page') }}" class="btn">➕ Add New Vehicle</a>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Vehicle</th>
        <th>Category</th>
        <th>Pricing</th>
        <th>Fuel / Trans</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for car in cars %}
      <tr>
        <td>
          <div style="display:flex; align-items:center; gap:12px;">
            <img src="{{ car.main_image or car.image_url or 'https://via.placeholder.com/80x50' }}" 
                 style="width:70px; height:45px; object-fit:cover; border-radius:6px; border:1px solid #cbd5e1;">
            <div>
              <strong style="display:block;">{{ car.name }}</strong>
              <small style="color:var(--muted)">{{ car.seats }} Seats</small>
            </div>
          </div>
        </td>
        <td>{{ car.category }}</td>
        <td><strong>₹{{ car.price_per_day }}</strong> / day</td>
        <td>{{ car.fuel_type }} · {{ car.transmission }}</td>
        <td>
          <span class="badge {{ 'badge-on' if car.is_available else 'badge-off' }}">
            {{ 'Available' if car.is_available else 'Unavailable' }}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:8px;">
            <form method="POST" action="{{ url_for('admin_toggle_car', car_id=car.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-secondary btn-sm" type="submit">
                {{ 'Hide' if car.is_available else 'Show' }}
              </button>
            </form>
            <form method="POST" action="{{ url_for('admin_delete_car', car_id=car.id) }}" onsubmit="return confirm('Delete this vehicle permanently?')">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-danger btn-sm" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center; padding:30px; color:var(--muted)">No vehicles found in your fleet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""

CAR_ADD_HTML = BASE_ADMIN_HTML + """
{% block content %}
<div class="header">
  <div>
    <h1>Add New Vehicle</h1>
    <p class="subhead">Add a new car to your public fleet listing</p>
  </div>
  <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary">&larr; Back to Fleet</a>
</div>

<div class="card">
  <form method="POST" action="{{ url_for('admin_create_car') }}" enctype="multipart/form-data">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="form-grid">
      <div class="field">
        <label>Vehicle Name *</label>
        <input name="name" placeholder="e.g. Maruti Suzuki Ertiga" required>
      </div>
      <div class="field">
        <label>Category *</label>
        <input name="category" placeholder="SUV / Sedan / Hatchback / Luxury" required>
      </div>
      <div class="field">
        <label>Rental Price Per Day (₹) *</label>
        <input name="price_per_day" type="number" step="0.01" required placeholder="2500">
      </div>
      <div class="field">
        <label>Extra Km Rate (₹)</label>
        <input name="price_per_km" type="number" step="0.01" placeholder="12">
      </div>
      <div class="field">
        <label>Seating Capacity *</label>
        <input name="seats" type="number" value="5" min="2" max="20" required>
      </div>
      <div class="field">
        <label>Luggage Capacity (Bags)</label>
        <input name="luggage_capacity" type="number" value="2" min="0">
      </div>
      <div class="field">
        <label>Fuel Type *</label>
        <select name="fuel_type">
          <option>Diesel</option><option>Petrol</option><option>CNG</option><option>Electric</option>
        </select>
      </div>
      <div class="field">
        <label>Transmission *</label>
        <select name="transmission">
          <option>Manual</option><option>Automatic</option>
        </select>
      </div>
      <div class="field form-full">
        <label>Features (comma separated)</label>
        <input name="features" placeholder="Air Conditioning, Bluetooth Audio, Power Windows, GPS Navigation">
      </div>
      <div class="field form-full">
        <label>Vehicle Description</label>
        <textarea name="description" placeholder="Brief overview of the vehicle condition, ideal routes, etc."></textarea>
      </div>
      <div class="field form-full">
        <label>Main Showcase Image *</label>
        <input type="file" name="main_image" accept=".jpg,.jpeg,.png,.webp" required>
      </div>
    </div>
    <div style="margin-top:24px;">
      <button class="btn" type="submit">Save and Publish Vehicle</button>
    </div>
  </form>
</div>
{% endblock %}
"""

@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    cars = supabase.table("cars").select("*").order("created_at", desc=True).execute().data or []
    return render_template_string(CARS_LIST_HTML, title="Fleet Management", active_nav="fleet", cars=cars)


@app.route("/admin/cars/new")
@admin_required
def admin_add_car_page():
    return render_template_string(CAR_ADD_HTML, title="Add Vehicle", active_nav="add_car")


@app.route("/admin/cars", methods=["POST"])
@admin_required
def admin_create_car():
    if not valid_csrf():
        flash("Invalid form session.", "err")
        return redirect(url_for("admin_add_car_page"))

    try:
        main_img = upload_car_image(request.files.get("main_image"))
        features = [f.strip() for f in request.form.get("features", "").split(",") if f.strip()]

        supabase.table("cars").insert({
            "name": request.form.get("name", "").strip(),
            "category": request.form.get("category", "").strip(),
            "price_per_day": float(request.form.get("price_per_day") or 0),
            "price_per_km": float(request.form.get("price_per_km") or 0),
            "seats": int(request.form.get("seats") or 5),
            "luggage_capacity": int(request.form.get("luggage_capacity") or 2),
            "fuel_type": request.form.get("fuel_type", "Diesel"),
            "transmission": request.form.get("transmission", "Manual"),
            "features": features,
            "description": request.form.get("description", "").strip(),
            "main_image": main_img,
            "image_url": main_img,
            "is_available": True
        }).execute()
        flash("Vehicle published successfully.", "ok")
        return redirect(url_for("admin_dashboard"))
    except Exception as e:
        flash(f"Failed to add vehicle: {str(e)}", "err")
        return redirect(url_for("admin_add_car_page"))


@app.route("/admin/cars/<int:car_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_car(car_id):
    if not valid_csrf():
        flash("Invalid CSRF token.", "err")
        return redirect(url_for("admin_dashboard"))
    try:
        car = supabase.table("cars").select("is_available").eq("id", car_id).limit(1).execute().data
        if car:
            supabase.table("cars").update({"is_available": not car[0]["is_available"]}).eq("id", car_id).execute()
            flash("Vehicle status updated.", "ok")
    except Exception:
        flash("Could not update vehicle status.", "err")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/cars/<int:car_id>/delete", methods=["POST"])
@admin_required
def admin_delete_car(car_id):
    if not valid_csrf():
        flash("Invalid CSRF token.", "err")
        return redirect(url_for("admin_dashboard"))
    try:
        supabase.table("cars").delete().eq("id", car_id).execute()
        flash("Vehicle removed from fleet.", "ok")
    except Exception:
        flash("Could not delete vehicle.", "err")
    return redirect(url_for("admin_dashboard"))


# ==========================================
# ATTACH EXTRA DEDICATED ADMIN PAGES & APIS
# ==========================================
register_extra_routes(app, supabase, admin_required, valid_csrf, upload_car_image, BASE_ADMIN_HTML)


if __name__ == "__main__":
    app.run(debug=True, port=5000)