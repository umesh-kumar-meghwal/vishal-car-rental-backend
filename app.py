import os
import time
import uuid
import secrets
import hmac
from collections import defaultdict, deque
from functools import wraps

from flask import (
    Flask, request, jsonify, session, redirect, url_for,
    render_template, flash,
)
from flask_cors import CORS
from jinja2 import DictLoader, ChoiceLoader
from supabase import create_client
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename


# =========================================================
# CONFIGURATION
# =========================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
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
    raise RuntimeError("SUPABASE_URL aur SUPABASE_SERVICE_ROLE_KEY environment variables set karo.")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if allowed_origins:
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})


# =========================================================
# SECURITY HELPERS
# =========================================================

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def valid_csrf():
    submitted = request.form.get("csrf_token", "")
    saved = session.get("csrf_token", "")
    return bool(submitted and saved and hmac.compare_digest(submitted, saved))


def admin_required(view_function):
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view_function(*args, **kwargs)
    return wrapped


def notify(message, ok=True):
    flash(message, "ok" if ok else "err")


# Plain password compare (hash bhi support karta hai, agar kabhi hash use karo).
def verify_password(stored, given):
    stored = str(stored or "")
    if not stored or not given:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored, given)
    return hmac.compare_digest(stored.encode("utf-8"), given.encode("utf-8"))


_login_fails = defaultdict(deque)


def _client_ip():
    return (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()


def login_blocked(limit=6, window=300):
    q = _login_fails[_client_ip()]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    return len(q) >= limit


# =========================================================
# IMAGE UPLOAD
# =========================================================

def upload_car_image(file):
    """Supabase Storage me image upload karke public URL return karta hai."""
    if not file or not file.filename:
        raise ValueError("Image select karo.")

    original_name = secure_filename(file.filename)
    if "." not in original_name:
        raise ValueError("Image file ka extension missing hai.")

    extension = original_name.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Sirf JPG, JPEG, PNG aur WEBP images allowed hain.")

    file_bytes = file.read()
    if not file_bytes:
        raise ValueError("Uploaded image empty hai.")
    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise ValueError("Har image 8 MB se chhoti honi chahiye.")

    content_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "png": "image/png", "webp": "image/webp"}
    storage_path = f"cars/{uuid.uuid4().hex}.{extension}"

    supabase.storage.from_(STORAGE_BUCKET).upload(
        storage_path, file_bytes,
        {"content-type": content_types[extension], "upsert": "false"},
    )

    public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
    if isinstance(public_url, dict):
        public_url = public_url.get("publicUrl") or public_url.get("publicURL") or public_url.get("url")
    if not public_url:
        raise RuntimeError("Uploaded image ka public URL nahi mila.")
    return public_url


# =========================================================
# PUBLIC API
# =========================================================

@app.route("/")
def home():
    return jsonify({
        "message": "Car Rental API is running",
        "cars_endpoint": "/api/cars",
        "admin_login": "/admin/login",
    })


@app.route("/api/cars", methods=["GET"])
def get_cars():
    try:
        result = (supabase.table("cars").select("*")
                  .eq("is_available", True).order("created_at", desc=True).execute())
        cars = result.data or []
        for car in cars:
            if not car.get("main_image"):
                car["main_image"] = car.get("image_url")
            car["gallery_images"] = car.get("gallery_images") or []
            car["features"] = car.get("features") or []
        return jsonify({"cars": cars}), 200
    except Exception:
        app.logger.exception("Could not fetch cars")
        return jsonify({"error": "Cars fetch nahi ho paayi."}), 500


# =========================================================
# ADMIN DESIGN (shared CSS + templates)
# =========================================================

CSS = """
:root{--bg:#f3f5fa;--card:#fff;--ink:#0f172a;--mut:#64748b;--line:#e6eaf3;--pri:#4f46e5;--bad:#dc2626;--side:#0b1020}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,Arial,sans-serif;background:var(--bg);color:var(--ink);font-size:14px}
a{color:inherit;text-decoration:none}
.app{display:grid;grid-template-columns:250px minmax(0,1fr);min-height:100vh}
aside{background:var(--side);color:#94a3b8;padding:20px 14px;position:sticky;top:0;height:100vh;overflow:auto;display:flex;flex-direction:column;gap:6px}
aside form{margin:0;margin-top:auto}
.brand{display:flex;gap:10px;align-items:center;color:#fff;padding:4px 8px 16px}
.brand span{font-size:26px}.brand small{display:block;color:#64748b;font-size:12px}
aside nav a{display:flex;gap:10px;align-items:center;padding:10px 12px;border-radius:10px;font-weight:500}
aside nav a:hover{background:#ffffff12;color:#fff}
aside nav a.on{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.grp{margin:14px 12px 4px;font-size:11px;letter-spacing:.1em;color:#475569;font-weight:700}
.logout{width:100%;background:#ffffff12;color:#e2e8f0;justify-content:center}
main{padding:28px;max-width:1280px;width:100%}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:22px}
h1{margin:0;font-size:26px;letter-spacing:-.02em}.top p{margin:4px 0 0;color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;margin-bottom:20px;box-shadow:0 1px 2px #0f172a08}
h3{margin:0 0 14px;font-size:16px}
.btn,button{display:inline-flex;align-items:center;gap:6px;padding:10px 16px;border:0;border-radius:10px;background:var(--pri);color:#fff;font:inherit;font-weight:600;cursor:pointer}
.btn:hover,button:hover{filter:brightness(1.1)}
.ghost{background:#eef0f8;color:var(--ink)}.danger{background:#fee2e2;color:var(--bad)}.good{background:#dcfce7;color:#15803d}.sm{padding:6px 11px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.full{grid-column:1/-1}
label{display:block;font-weight:600;margin-bottom:6px;font-size:13px}
input,select,textarea{width:100%;padding:11px 13px;border:1px solid #d5dbe8;border-radius:10px;font:inherit;background:#fff}
input:focus,select:focus,textarea:focus{outline:2px solid #c7d2fe;border-color:var(--pri)}
input[type=checkbox]{width:auto}textarea{min-height:100px;resize:vertical}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-bottom:20px}
.stat{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;display:flex;gap:14px;align-items:center;transition:.2s}
.stat:hover{transform:translateY(-2px);box-shadow:0 10px 24px -12px #0f172a40}
.stat i{font-style:normal;font-size:24px;width:48px;height:48px;border-radius:14px;display:grid;place-items:center;background:#eef2ff}
.stat b{font-size:26px;display:block}.stat span{color:var(--mut)}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:640px}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);text-align:left;padding:10px;border-bottom:1px solid var(--line)}
td{padding:12px 10px;border-bottom:1px solid #f0f2f8;vertical-align:middle}
.tag{padding:4px 10px;border-radius:99px;font-size:12px;font-weight:600;background:#f1f5f9;color:#475569}.tag.on{background:#dcfce7;color:#15803d}
.thumb{width:84px;height:60px;object-fit:cover;border-radius:10px}
.muted{color:var(--mut)}.row{display:flex;gap:6px;flex-wrap:wrap}.row form{margin:0}
.flash{padding:12px 16px;border-radius:12px;margin-bottom:16px;font-weight:500}
.flash.ok{background:#dcfce7;color:#166534}.flash.err{background:#fee2e2;color:#991b1b}
.search{max-width:320px;margin-bottom:14px}.gal{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.auth{display:grid;place-items:center;min-height:100vh;padding:20px;background:radial-gradient(circle at 20% 10%,#c7d2fe,transparent 45%),radial-gradient(circle at 85% 90%,#ddd6fe,transparent 45%),#eef2ff}
.login{width:100%;max-width:400px;padding:32px}.login h1{font-size:24px}.login .field{margin-top:16px}.login button{width:100%;justify-content:center;margin-top:22px;padding:13px}
@media(max-width:860px){.app{grid-template-columns:1fr}aside{position:static;height:auto;flex-direction:row;flex-wrap:wrap;align-items:center}aside nav{display:flex;gap:4px;overflow-x:auto;width:100%}aside nav a{white-space:nowrap}.grp{display:none}aside form{margin:0}.logout{width:auto}main{padding:16px}.grid{grid-template-columns:1fr}}
"""

HEAD = """<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{{ css|safe }}</style>"""

TEMPLATES = {
"admin_base.html": """<!DOCTYPE html><html lang="en"><head>""" + HEAD + """
<title>{{ heading }} · Vishal Car Rental</title></head><body>
<div class="app"><aside>
<div class="brand"><span>🚗</span><div><b>Vishal Car Rental</b><small>Admin Panel</small></div></div>
<nav>
{% set items = [
 ('', '', 'OVERVIEW', ''),
 ('dashboard', '📊', 'Dashboard', url_for('admin_dashboard')),
 ('', '', 'CARS', ''),
 ('cars', '🚗', 'All Cars', url_for('admin_cars')),
 ('add_car', '➕', 'Add New Car', url_for('admin_add_car')),
 ('', '', 'CONTENT', ''),
 ('reviews', '⭐', 'Reviews', url_for('admin_manage', table='reviews')),
 ('blogs', '📰', 'Blogs', url_for('admin_manage', table='blogs')),
 ('blog_comments', '💬', 'Blog Comments', url_for('admin_manage', table='blog_comments')),
 ('faqs', '❓', 'FAQs', url_for('admin_manage', table='faqs')),
 ('', '', 'INBOX', ''),
 ('contact_messages', '✉️', 'Messages', url_for('admin_manage', table='contact_messages')),
 ('subscribers', '📬', 'Subscribers', url_for('admin_manage', table='subscribers')),
] %}
{% for k, icon, title, link in items %}
{% if not k %}<p class="grp">{{ title }}</p>
{% else %}<a href="{{ link }}" class="{{ 'on' if active == k else '' }}"><i style="font-style:normal">{{ icon }}</i>{{ title }}</a>{% endif %}
{% endfor %}
</nav>
<form method="POST" action="{{ url_for('admin_logout') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="logout" type="submit">Logout</button></form>
</aside>
<main>
<div class="top"><div><h1>{{ heading }}</h1>{% if sub %}<p>{{ sub }}</p>{% endif %}</div><div>{% block actions %}{% endblock %}</div></div>
{% for category, m in get_flashed_messages(with_categories=true) %}<div class="flash {{ 'err' if category == 'err' else 'ok' }}">{{ m }}</div>{% endfor %}
{% block content %}{% endblock %}
</main></div></body></html>""",

"login.html": """<!DOCTYPE html><html lang="en"><head>""" + HEAD + """<title>Admin Login · Vishal Car Rental</title></head>
<body class="auth"><form class="card login" method="POST">
<div style="font-size:34px">🚗</div><h1>Vishal Car Rental</h1><p class="muted">Admin panel me login karo.</p>
{% for category, m in get_flashed_messages(with_categories=true) %}<div class="flash err">{{ m }}</div>{% endfor %}
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<div class="field"><label>Username</label><input type="text" name="username" required autocomplete="username"></div>
<div class="field"><label>Password</label><input type="password" name="password" required autocomplete="current-password"></div>
<button type="submit">Login</button></form></body></html>""",

"dashboard.html": """{% extends "admin_base.html" %}
{% block actions %}<a class="btn" href="{{ url_for('admin_add_car') }}">➕ Add New Car</a>{% endblock %}
{% block content %}
<div class="stats">{% for s in stats %}
<a class="stat" href="{{ s.url }}"><i>{{ s.icon }}</i><div><b>{{ s.value }}</b><span>{{ s.label }}</span></div></a>{% endfor %}</div>
<div class="card"><h3>Latest contact messages</h3>
{% if messages %}<div class="wrap"><table><thead><tr><th>Name</th><th>Phone</th><th>Message</th><th>Status</th></tr></thead><tbody>
{% for m in messages %}<tr><td><b>{{ m.name }}</b><br><span class="muted">{{ m.email }}</span></td><td>{{ m.phone }}</td>
<td>{{ (m.message or '')|truncate(90) }}</td><td><span class="tag {{ 'on' if m.is_read else '' }}">{{ 'Read' if m.is_read else 'New' }}</span></td></tr>{% endfor %}
</tbody></table></div>{% else %}<p class="muted">Abhi koi message nahi hai.</p>{% endif %}</div>
{% endblock %}""",

"cars.html": """{% extends "admin_base.html" %}
{% block actions %}<a class="btn" href="{{ url_for('admin_add_car') }}">➕ Add New Car</a>{% endblock %}
{% block content %}<div class="card">
<input class="search" placeholder="Search cars..." oninput="var v=this.value.toLowerCase();document.querySelectorAll('#t tbody tr').forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(v)>-1?'':'none'})">
{% if cars %}<div class="wrap"><table id="t"><thead><tr><th>Image</th><th>Car</th><th>Price/Day</th><th>Status</th><th>Gallery</th><th>Action</th></tr></thead><tbody>
{% for car in cars %}{% set img = car.get('main_image') or car.get('image_url') %}<tr>
<td>{% if img %}<img class="thumb" src="{{ img }}" alt="">{% else %}<span class="muted">No image</span>{% endif %}</td>
<td><b>{{ car.get('name', 'Unnamed car') }}</b><br><span class="muted">{{ car.get('brand', '') }} · {{ car.get('year', '') }}</span></td>
<td><b>₹{{ car.get('price', '') }}</b></td>
<td><span class="tag {{ 'on' if car.get('is_available') else '' }}">{{ 'Available' if car.get('is_available') else 'Unavailable' }}</span></td>
<td>{{ (car.get('gallery_images') or [])|length }}</td>
<td><div class="row"><a class="btn sm ghost" href="{{ url_for('admin_edit_car', car_id=car.get('id')) }}">Edit</a>
<form method="POST" action="{{ url_for('admin_delete_car', car_id=car.get('id')) }}" onsubmit="return confirm('Ye car delete karni hai?')">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="sm danger" type="submit">Delete</button></form></div></td></tr>{% endfor %}
</tbody></table></div>{% else %}<p class="muted">Abhi koi car add nahi hui hai.</p>{% endif %}</div>{% endblock %}""",

"car_form.html": """{% extends "admin_base.html" %}
{% block actions %}<a class="btn ghost" href="{{ url_for('admin_cars') }}">← All cars</a>{% endblock %}
{% block content %}
<form method="POST" enctype="multipart/form-data">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<div class="card"><h3>Car details</h3><div class="grid">
{% for n, l, p, o, t in fields %}<div class="field"><label>{{ l }}{% if n in required %} *{% endif %}</label>
{% if o %}<select name="{{ n }}"><option value="">Select</option>{% for x in o %}<option {{ 'selected' if car.get(n) == x else '' }}>{{ x }}</option>{% endfor %}</select>
{% else %}<input name="{{ n }}" type="{{ t }}" {% if t == 'number' %}step="any"{% endif %} value="{{ car.get(n) if car.get(n) is not none else '' }}" placeholder="{{ p }}" {{ 'required' if n in required else '' }}>{% endif %}</div>{% endfor %}
<div class="field full"><label>Description</label><textarea name="description" placeholder="Car ki details likho...">{{ car.get('description') or '' }}</textarea></div>
<div class="field full"><label>Features (har feature alag line me)</label><textarea name="features" placeholder="ABS&#10;Airbags&#10;Power Steering">{{ (car.get('features') or [])|join('\\n') }}</textarea></div>
</div></div>
<div class="card"><h3>Images</h3><div class="grid">
<div class="field"><label>Main image{% if mode == 'add' %} *{% else %} (nayi select karo to replace hogi){% endif %}</label>
{% set mi = car.get('main_image') or car.get('image_url') %}{% if mi %}<div class="gal"><img class="thumb" src="{{ mi }}" alt=""></div>{% endif %}
<input type="file" name="main_image" accept=".jpg,.jpeg,.png,.webp" {{ 'required' if mode == 'add' else '' }}></div>
<div class="field"><label>Gallery images (max 10){% if mode == 'edit' %} - nayi select karo to purani replace hongi{% endif %}</label>
{% if car.get('gallery_images') %}<div class="gal">{% for g in car.get('gallery_images') %}<img class="thumb" src="{{ g }}" alt="">{% endfor %}</div>{% endif %}
<input type="file" name="gallery_images" multiple accept=".jpg,.jpeg,.png,.webp">
{% if mode == 'edit' %}<p><label style="font-weight:500"><input type="checkbox" name="clear_gallery" value="true"> Purani gallery clear karo</label></p>{% endif %}</div>
<div class="field full"><label style="font-weight:500"><input type="checkbox" name="is_available" value="true" {{ 'checked' if mode == 'add' or car.get('is_available') else '' }}> Car rent ke liye available hai</label></div>
</div></div>
<button type="submit">{{ 'Add Car' if mode == 'add' else 'Save Changes' }}</button>
</form>{% endblock %}""",
}

app.jinja_env.loader = ChoiceLoader([DictLoader(TEMPLATES), app.jinja_env.loader])


@app.context_processor
def inject_template_helpers():
    return {"csrf_token": get_csrf_token, "css": CSS, "sub": None}


# =========================================================
# ADMIN LOGIN / LOGOUT
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            notify("Session expire hua hai. Dobara try karo.", False)
            return redirect(url_for("admin_login"))
        if login_blocked():
            notify("Bahut zyada galat attempts. 5 minute baad try karo.", False)
            return redirect(url_for("admin_login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            result = (supabase.table("admin").select("*")
                      .eq("username", username).limit(1).execute())
            admins = result.data or []

            # Column "password" ya "password_hash" - jo bhi table me ho, plain text chalega.
            stored = ""
            if admins:
                stored = admins[0].get("password") or admins[0].get("password_hash") or ""

            if admins and verify_password(stored, password):
                session.clear()
                session["admin_logged_in"] = True
                session["admin_username"] = admins[0]["username"]
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("admin_dashboard"))

            _login_fails[_client_ip()].append(time.time())
            notify("Username ya password galat hai.", False)

        except Exception:
            app.logger.exception("Admin login failed")
            notify("Login abhi nahi ho paaya. Configuration check karo.", False)

    return render_template("login.html")


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    if not valid_csrf():
        notify("Invalid form session.", False)
        return redirect(url_for("admin_dashboard"))
    session.clear()
    return redirect(url_for("admin_login"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

def count_rows(table, column=None, value=None):
    try:
        query = supabase.table(table).select("id", count="exact")
        if column:
            query = query.eq(column, value)
        return query.limit(1).execute().count or 0
    except Exception:
        return 0


@app.route("/admin")
@admin_required
def admin_dashboard():
    def manage(table):
        return url_for("admin_manage", table=table)

    stats = [
        {"icon": "🚗", "value": count_rows("cars"), "label": "Total cars", "url": url_for("admin_cars")},
        {"icon": "✅", "value": count_rows("cars", "is_available", True), "label": "Available cars", "url": url_for("admin_cars")},
        {"icon": "⭐", "value": count_rows("reviews", "is_approved", False), "label": "Reviews pending", "url": manage("reviews")},
        {"icon": "💬", "value": count_rows("blog_comments", "is_approved", False), "label": "Comments pending", "url": manage("blog_comments")},
        {"icon": "✉️", "value": count_rows("contact_messages", "is_read", False), "label": "New messages", "url": manage("contact_messages")},
        {"icon": "📬", "value": count_rows("subscribers"), "label": "Subscribers", "url": manage("subscribers")},
    ]
    try:
        messages = (supabase.table("contact_messages").select("*")
                    .order("created_at", desc=True).limit(5).execute()).data or []
    except Exception:
        messages = []

    return render_template(
        "dashboard.html", stats=stats, messages=messages, active="dashboard",
        heading="Dashboard", sub=f"Welcome back, {session.get('admin_username', 'Admin')}",
    )


# =========================================================
# CARS (list / add / edit / delete)
# =========================================================

# (name, label, placeholder, select options, input type)
CAR_FIELDS = [
    ("name", "Car Name", "Maruti Suzuki Baleno", None, "text"),
    ("brand", "Brand", "Maruti Suzuki", None, "text"),
    ("category", "Category", "Hatchback", None, "text"),
    ("price", "Rental Price Per Day (₹)", "2500", None, "number"),
    ("ex_showroom_price", "Ex-showroom Price", "₹6.66 - 9.88 Lakh", None, "text"),
    ("year", "Year", "2024", None, "number"),
    ("fuel", "Fuel", "", ["Petrol", "Diesel", "CNG", "Electric", "Hybrid"], "text"),
    ("transmission", "Transmission", "", ["Manual", "Automatic", "AMT", "CVT", "DCT"], "text"),
    ("gearbox", "Gearbox", "5-Speed Manual", None, "text"),
    ("seats", "Seats", "5", None, "text"),
    ("km_included", "KM Included Per Day", "300 km/day", None, "text"),
    ("mileage", "Mileage", "22.35 Kmpl", None, "text"),
    ("engine", "Engine", "1197 cc, 4 Cylinder", None, "text"),
    ("max_power", "Max Power", "88.50 bhp @ 6000 rpm", None, "text"),
    ("max_torque", "Max Torque", "113 Nm @ 4400 rpm", None, "text"),
    ("fuel_tank", "Fuel Tank", "37 L", None, "text"),
    ("boot_space", "Boot Space", "318 L", None, "text"),
    ("ground_clearance", "Ground Clearance", "170 mm", None, "text"),
    ("dimensions", "Dimensions", "3990 x 1745 x 1500 mm", None, "text"),
    ("wheelbase", "Wheelbase", "2520 mm", None, "text"),
    ("competitors", "Competitors", "Hyundai i20, Tata Altroz", None, "text"),
    ("guarantee", "Guarantee / Rental Terms", "Vishal Car Rental guarantee", None, "text"),
]
CAR_REQUIRED = ["name", "brand", "price", "year"]
CAR_TEXT_KEYS = [f[0] for f in CAR_FIELDS if f[0] not in ("name", "brand", "price", "year")]


def read_car_form():
    """Form se car data nikalta hai aur validate karta hai."""
    form = request.form
    name = form.get("name", "").strip()
    brand = form.get("brand", "").strip()

    if not name or not brand or not form.get("price", "").strip() or not form.get("year", "").strip():
        raise ValueError("Name, brand, price aur year required hain.")
    try:
        price = float(form.get("price", "").strip())
        year = int(form.get("year", "").strip())
    except ValueError:
        raise ValueError("Price aur year valid numbers hone chahiye.")
    if price < 0:
        raise ValueError("Price negative nahi ho sakti.")
    if year < 1900 or year > 2100:
        raise ValueError("Year valid range me enter karo.")

    data = {key: form.get(key, "").strip() for key in CAR_TEXT_KEYS}
    data.update({
        "name": name, "brand": brand, "price": price, "year": year,
        "description": form.get("description", "").strip(),
        "features": [l.strip() for l in form.get("features", "").splitlines() if l.strip()],
        "is_available": form.get("is_available") == "true",
    })
    return data


def read_gallery_files():
    files = [f for f in request.files.getlist("gallery_images") if f and f.filename]
    if len(files) > MAX_GALLERY_IMAGES:
        raise ValueError(f"Maximum {MAX_GALLERY_IMAGES} gallery images allowed hain.")
    return files


def car_page(car, mode):
    return render_template(
        "car_form.html", car=car, mode=mode, fields=CAR_FIELDS, required=CAR_REQUIRED,
        active="add_car" if mode == "add" else "cars",
        heading="Add New Car" if mode == "add" else f"Edit: {car.get('name', '')}",
        sub="Main image required hai. Har image 8 MB se chhoti honi chahiye." if mode == "add" else None,
    )


@app.route("/admin/cars")
@admin_required
def admin_cars():
    try:
        cars = supabase.table("cars").select("*").order("created_at", desc=True).execute().data or []
    except Exception:
        app.logger.exception("Cars list failed")
        return "Cars load nahi ho payi. Server logs check karo.", 500
    return render_template("cars.html", cars=cars, active="cars", heading="All Cars",
                           sub=f"{len(cars)} cars total")


@app.route("/admin/cars/add", methods=["GET", "POST"])
@admin_required
def admin_add_car():
    if request.method == "GET":
        return car_page({}, "add")

    if not valid_csrf():
        notify("Invalid form session. Dobara submit karo.", False)
        return redirect(url_for("admin_add_car"))
    try:
        data = read_car_form()
        main_file = request.files.get("main_image")
        if not main_file or not main_file.filename:
            raise ValueError("Main car image select karna required hai.")
        gallery_files = read_gallery_files()

        main_url = upload_car_image(main_file)
        data["image_url"] = main_url  # purane frontend ke liye
        data["main_image"] = main_url
        data["gallery_images"] = [upload_car_image(f) for f in gallery_files]

        supabase.table("cars").insert(data).execute()
        notify("Car aur images successfully add ho gayi!")
        return redirect(url_for("admin_cars"))

    except ValueError as error:
        notify(str(error), False)
    except Exception:
        app.logger.exception("Add car failed")
        notify("Car add nahi ho payi. Supabase columns, Storage permissions aur logs check karo.", False)
    return redirect(url_for("admin_add_car"))


@app.route("/admin/cars/<int:car_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_car(car_id):
    try:
        rows = supabase.table("cars").select("*").eq("id", car_id).limit(1).execute().data or []
        if not rows:
            notify("Car nahi mili.", False)
            return redirect(url_for("admin_cars"))
        car = rows[0]

        if request.method == "GET":
            return car_page(car, "edit")

        if not valid_csrf():
            notify("Invalid form session. Dobara try karo.", False)
            return redirect(url_for("admin_edit_car", car_id=car_id))

        data = read_car_form()
        main_url = car.get("main_image") or car.get("image_url")
        new_main = request.files.get("main_image")
        if new_main and new_main.filename:
            main_url = upload_car_image(new_main)

        gallery = car.get("gallery_images") or []
        new_gallery = read_gallery_files()
        if request.form.get("clear_gallery") == "true":
            gallery = []
        if new_gallery:
            gallery = [upload_car_image(f) for f in new_gallery]

        data.update({"image_url": main_url, "main_image": main_url, "gallery_images": gallery})
        supabase.table("cars").update(data).eq("id", car_id).execute()
        notify("Car details successfully update ho gayi!")
        return redirect(url_for("admin_cars"))

    except ValueError as error:
        notify(str(error), False)
        return redirect(url_for("admin_edit_car", car_id=car_id))
    except Exception:
        app.logger.exception("Edit car failed")
        return "Car update nahi ho payi. Supabase columns, Storage aur server logs check karo.", 500


@app.route("/admin/cars/<int:car_id>/delete", methods=["POST"])
@admin_required
def admin_delete_car(car_id):
    if not valid_csrf():
        notify("Invalid form session. Dobara try karo.", False)
        return redirect(url_for("admin_cars"))
    try:
        supabase.table("cars").delete().eq("id", car_id).execute()
        notify("Car database se delete ho gayi. Storage ki images automatically delete nahi hoti.")
    except Exception:
        app.logger.exception("Delete car failed")
        notify("Car delete nahi ho payi.", False)
    return redirect(url_for("admin_cars"))


# =========================================================
# EXTRA ROUTES (reviews, blogs, faqs, contact, comments, subscribers)
# =========================================================
# IMPORTANT: extra_routes.py isi folder me honi chahiye.

from extra_routes import register_extra_routes

register_extra_routes(app, supabase, admin_required, valid_csrf, upload_car_image)


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return "Upload size limit exceed ho gayi. Total upload 90 MB se kam rakho.", 413


@app.errorhandler(404)
def page_not_found(error):
    return jsonify({"error": "Page not found"}), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)