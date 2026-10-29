import os
import uuid
import hmac
import secrets
from functools import wraps

from flask import (
    Flask, request, jsonify, session, redirect, url_for, render_template, flash,
)
from flask_cors import CORS
from jinja2 import DictLoader
from supabase import create_client
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from admin_templates import TEMPLATES
from extra_routes import register_extra_routes, _limited, _line, _text, F


# =========================================================
# CONFIGURATION
# =========================================================

app = Flask(__name__)
app.jinja_env.loader = DictLoader(TEMPLATES)

app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
if app.secret_key == "dev-only-change-this-secret":
    app.logger.warning("SECRET_KEY is not set. Set it in your environment before going live.")

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
    raise RuntimeError("Set the SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if allowed_origins:
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})


# =========================================================
# SECURITY / CSRF / NAVIGATION
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


NAV = [
    {"key": "dashboard", "label": "Dashboard", "icon": "\U0001F4CA", "endpoint": "admin_dashboard"},
    {"key": "cars", "label": "Cars", "icon": "\U0001F697", "endpoint": "admin_cars"},
    {"key": "hero", "label": "Hero image", "icon": "\U0001F5BC\uFE0F", "endpoint": "admin_hero"},
    {"key": "reviews", "label": "Reviews", "icon": "\u2B50", "endpoint": "admin_reviews"},
    {"key": "blogs", "label": "Blog articles", "icon": "\U0001F4DD", "endpoint": "admin_blogs"},
    {"key": "comments", "label": "Comments", "icon": "\U0001F4AC", "endpoint": "admin_comments"},
    {"key": "faqs", "label": "FAQs", "icon": "\u2753", "endpoint": "admin_faqs"},
    {"key": "messages", "label": "Messages", "icon": "\u2709\uFE0F", "endpoint": "admin_messages"},
    {"key": "subscribers", "label": "Subscribers", "icon": "\U0001F4E7", "endpoint": "admin_subscribers"},
]


@app.context_processor
def inject_template_helpers():
    return {"csrf_token": get_csrf_token, "nav": NAV}


# =========================================================
# IMAGE HELPERS
# =========================================================

IMAGE_SIGNATURES = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),
}
CONTENT_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def upload_car_image(file, folder="cars"):
    """Upload an image to Supabase Storage (inside `folder`) and return its public URL."""
    if not file or not file.filename:
        raise ValueError("Please select an image.")

    name = secure_filename(file.filename)
    if "." not in name:
        raise ValueError("The image file has no extension.")

    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Only JPG, JPEG, PNG and WEBP images are allowed.")

    data = file.read()
    if not data:
        raise ValueError("The uploaded image is empty.")
    if len(data) > MAX_IMAGE_SIZE:
        raise ValueError("Each image must be smaller than 8 MB.")
    if not data.startswith(IMAGE_SIGNATURES[ext]):
        raise ValueError(f"{file.filename} is not a valid {ext.upper()} image.")

    path = f"{folder}/{uuid.uuid4().hex}.{ext}"
    supabase.storage.from_(STORAGE_BUCKET).upload(
        path, data, {"content-type": CONTENT_TYPES[ext], "upsert": "false"}
    )

    url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(path)
    if isinstance(url, dict):
        url = url.get("publicUrl") or url.get("publicURL") or url.get("url")
    if not url:
        raise RuntimeError("Could not get the public URL of the uploaded image.")
    return url


upload_image = upload_car_image  # shared name used by extra_routes


def delete_images(urls):
    """Best-effort removal of files from Supabase Storage."""
    marker = f"/{STORAGE_BUCKET}/"
    paths = []
    for url in urls or []:
        if url and marker in url:
            paths.append(url.split(marker, 1)[1].split("?")[0])
    if paths:
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove(paths)
        except Exception:
            app.logger.exception("Could not delete images from storage")


# =========================================================
# PUBLIC API
# =========================================================

@app.route("/")
def home():
    return redirect('/admin/login')


@app.route("/api/cars", methods=["GET"])
def get_cars():
    try:
        result = (supabase.table("cars").select("*").eq("is_available", True)
                  .order("created_at", desc=True).execute())
        cars = result.data or []
        for car in cars:
            if not car.get("main_image"):
                car["main_image"] = car.get("image_url")
            car["gallery_images"] = car.get("gallery_images") or []
            car["features"] = car.get("features") or []
        return jsonify({"cars": cars}), 200
    except Exception:
        app.logger.exception("Could not fetch cars")
        return jsonify({"error": "Could not load cars."}), 500


# =========================================================
# ADMIN LOGIN / LOGOUT
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Your session expired. Please try again.", "err")
            return redirect(url_for("admin_login"))

        if _limited(limit=8, window=300, bucket="login"):
            flash("Too many login attempts. Please wait a few minutes.", "err")
            return redirect(url_for("admin_login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            result = (supabase.table("admin").select("username, password")
                      .eq("username", username).limit(1).execute())
            admins = result.data or []

            # The password hash MUST match. (The old code skipped this check.)
            if admins and check_password_hash(admins[0]["password"], password):
                session.clear()
                session["admin_logged_in"] = True
                session["admin_username"] = admins[0]["username"]
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("admin_dashboard"))

            flash("Incorrect username or password.", "err")
        except Exception:
            app.logger.exception("Admin login failed")
            flash("Sign-in is unavailable right now. Check the server configuration.", "err")

    return render_template("login.html")


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    if not valid_csrf():
        flash("Your session expired. Please try again.", "err")
        return redirect(url_for("admin_dashboard"))
    session.clear()
    return redirect(url_for("admin_login"))


# =========================================================
# DASHBOARD
# =========================================================

def count_rows(table, **filters):
    try:
        query = supabase.table(table).select("id", count="exact")
        for column, value in filters.items():
            query = query.eq(column, value)
        return query.limit(1).execute().count or 0
    except Exception:
        return 0


@app.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
    stats = [
        {"label": "Total cars", "value": count_rows("cars"), "endpoint": "admin_cars"},
        {"label": "Available cars", "value": count_rows("cars", is_available=True), "endpoint": "admin_cars"},
        {"label": "New messages", "value": count_rows("contact_messages", is_read=False),
         "endpoint": "admin_messages", "alert": True},
        {"label": "Reviews awaiting approval", "value": count_rows("reviews", is_approved=False),
         "endpoint": "admin_reviews", "alert": True},
        {"label": "Comments awaiting approval", "value": count_rows("blog_comments", is_approved=False),
         "endpoint": "admin_comments", "alert": True},
        {"label": "Blog articles", "value": count_rows("blogs"), "endpoint": "admin_blogs"},
        {"label": "FAQs", "value": count_rows("faqs"), "endpoint": "admin_faqs"},
        {"label": "Subscribers", "value": count_rows("subscribers"), "endpoint": "admin_subscribers"},
    ]
    return render_template("dashboard.html", title="Dashboard", active_nav="dashboard", stats=stats)


# =========================================================
# CARS: LIST / ADD / EDIT / TOGGLE / DELETE (separate pages)
# =========================================================

FUELS = [(x, x) for x in ["Petrol", "Diesel", "CNG", "Electric", "Hybrid"]]
TRANSMISSIONS = [(x, x) for x in ["Manual", "Automatic", "AMT", "CVT", "DCT"]]

CAR_SECTIONS = [
    ("Basic information", [
        F("name", "Car name", required=True, max=120, placeholder="Maruti Suzuki Baleno"),
        F("brand", "Brand", required=True, max=80, placeholder="Maruti Suzuki"),
        F("category", "Category", max=60, placeholder="Hatchback"),
        F("year", "Year", "number", required=True, min=1900, max=2100),
    ]),
    ("Pricing and terms", [
        F("price", "Rental price per day (INR)", "number", required=True, min=0, step="0.01"),
        F("ex_showroom_price", "Ex-showroom price", placeholder="Rs 6.66 - 9.88 Lakh"),
        F("km_included", "Kilometres included per day", placeholder="300 km/day"),
        F("guarantee", "Guarantee / rental terms", placeholder="Vishal Car rental guarantee"),
    ]),
    ("Specifications", [
        F("fuel", "Fuel", "select", options=FUELS),
        F("transmission", "Transmission", "select", options=TRANSMISSIONS),
        F("gearbox", "Gearbox", placeholder="5-speed manual"),
        F("seats", "Seats", placeholder="5"),
        F("mileage", "Mileage", placeholder="22.35 kmpl"),
        F("engine", "Engine", placeholder="1197 cc, 4 cylinder"),
        F("max_power", "Max power", placeholder="88.50 bhp @ 6000 rpm"),
        F("max_torque", "Max torque", placeholder="113 Nm @ 4400 rpm"),
        F("fuel_tank", "Fuel tank", placeholder="37 L"),
        F("boot_space", "Boot space", placeholder="318 L"),
        F("ground_clearance", "Ground clearance", placeholder="170 mm"),
        F("dimensions", "Dimensions", placeholder="3990 x 1745 x 1500 mm"),
        F("wheelbase", "Wheelbase", placeholder="2520 mm"),
        F("competitors", "Competitors", placeholder="Hyundai i20, Tata Altroz"),
    ]),
    ("Description", [
        F("description", "Description", "textarea", full=True, rows=5, max=5000),
        F("features", "Features (one per line)", "textarea", full=True, rows=6,
          placeholder="ABS\nAirbags\nPower steering"),
    ]),
]


def build_car_payload(existing=None):
    """
    Validate the car form. Returns (data, new_uploads, files_to_delete).
    Text fields are validated BEFORE any image is uploaded.
    """
    existing = existing or {}
    data = {}

    for _, fields in CAR_SECTIONS:
        for f in fields:
            name, raw = f["name"], request.form.get(f["name"], "")
            if name == "features":
                data[name] = [ln.strip() for ln in raw.splitlines() if ln.strip()][:60]
            elif f["type"] == "textarea":
                data[name] = _text(raw, f.get("max", 2000))
            else:
                data[name] = _line(raw, f.get("max", 200))

    if not data["name"] or not data["brand"] or not data["price"] or not data["year"]:
        raise ValueError("Car name, brand, price and year are required.")
    try:
        data["price"] = float(data["price"])
        data["year"] = int(data["year"])
    except ValueError:
        raise ValueError("Price and year must be valid numbers.")
    if data["price"] < 0:
        raise ValueError("Price cannot be negative.")
    if not 1900 <= data["year"] <= 2100:
        raise ValueError("Enter a year between 1900 and 2100.")

    data["is_available"] = request.form.get("is_available") == "on"

    # ---- images ----
    current_main = existing.get("main_image") or existing.get("image_url")
    removed = set(request.form.getlist("remove_gallery"))
    kept_gallery = [u for u in (existing.get("gallery_images") or []) if u not in removed]

    main_file = request.files.get("main_image")
    new_gallery_files = [f for f in request.files.getlist("gallery_images") if f and f.filename]
    has_new_main = bool(main_file and main_file.filename)

    if not has_new_main and not current_main:
        raise ValueError("A main photo is required.")
    if len(kept_gallery) + len(new_gallery_files) > MAX_GALLERY_IMAGES:
        raise ValueError(f"A car can have at most {MAX_GALLERY_IMAGES} gallery photos.")

    uploads, to_delete = [], list(removed)
    try:
        main_url = current_main
        if has_new_main:
            main_url = upload_car_image(main_file)
            uploads.append(main_url)
            if current_main:
                to_delete.append(current_main)

        for gallery_file in new_gallery_files:
            url = upload_car_image(gallery_file)
            uploads.append(url)
            kept_gallery.append(url)
    except Exception:
        delete_images(uploads)  # roll back partial uploads
        raise

    data["image_url"] = main_url      # kept for older frontends
    data["main_image"] = main_url
    data["gallery_images"] = kept_gallery
    return data, uploads, to_delete


@app.route("/admin/cars", methods=["GET"])
@admin_required
def admin_cars():
    try:
        cars = (supabase.table("cars").select("*").order("created_at", desc=True).execute().data or [])
    except Exception:
        app.logger.exception("Load cars failed")
        flash("Could not load cars.", "err")
        cars = []
    return render_template("cars_list.html", title="Cars", active_nav="cars", cars=cars)


def _car_form_page(values, car_id, title):
    return render_template("car_form.html", title=title, active_nav="cars", sections=CAR_SECTIONS,
                           values=values, car_id=car_id, max_gallery=MAX_GALLERY_IMAGES)


@app.route("/admin/cars/new", methods=["GET", "POST"])
@admin_required
def admin_cars_new():
    if request.method == "POST":
        if not valid_csrf():
            flash("Your session expired. Please try again.", "err")
            return redirect(url_for("admin_cars_new"))
        uploads = []
        try:
            data, uploads, _ = build_car_payload()
            supabase.table("cars").insert(data).execute()
            flash("Car added.", "ok")
            return redirect(url_for("admin_cars"))
        except ValueError as error:
            flash(str(error), "err")
        except Exception:
            app.logger.exception("Add car failed")
            delete_images(uploads)
            flash("Could not add the car. Check your Supabase columns, storage permissions and server logs.", "err")
        return redirect(url_for("admin_cars_new"))

    return _car_form_page({"is_available": True}, None, "Add a car")


def _fetch_car(car_id):
    rows = supabase.table("cars").select("*").eq("id", car_id).limit(1).execute().data or []
    return rows[0] if rows else None


@app.route("/admin/cars/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_cars_edit(item_id):
    try:
        car = _fetch_car(item_id)
    except Exception:
        app.logger.exception("Load car failed")
        car = None
    if not car:
        flash("Car not found.", "err")
        return redirect(url_for("admin_cars"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Your session expired. Please try again.", "err")
            return redirect(url_for("admin_cars_edit", item_id=item_id))
        uploads = []
        try:
            data, uploads, to_delete = build_car_payload(car)
            supabase.table("cars").update(data).eq("id", item_id).execute()
            delete_images(to_delete)  # only after the database update succeeded
            flash("Car updated.", "ok")
            return redirect(url_for("admin_cars"))
        except ValueError as error:
            flash(str(error), "err")
        except Exception:
            app.logger.exception("Edit car failed")
            delete_images(uploads)
            flash("Could not update the car. Check your Supabase columns, storage permissions and server logs.", "err")
        return redirect(url_for("admin_cars_edit", item_id=item_id))

    values = dict(car)
    values["features"] = "\n".join(car.get("features") or [])
    values["main_image"] = car.get("main_image") or car.get("image_url")
    values["gallery_images"] = car.get("gallery_images") or []
    return _car_form_page(values, item_id, "Edit car")


@app.route("/admin/cars/<int:item_id>/toggle", methods=["POST"])
@admin_required
def admin_cars_toggle(item_id):
    if not valid_csrf():
        flash("Your session expired. Please try again.", "err")
        return redirect(url_for("admin_cars"))
    try:
        car = _fetch_car(item_id)
        if car:
            supabase.table("cars").update({"is_available": not car.get("is_available")}).eq("id", item_id).execute()
            flash("Availability updated.", "ok")
    except Exception:
        app.logger.exception("Toggle car failed")
        flash("Could not update availability.", "err")
    return redirect(url_for("admin_cars"))


@app.route("/admin/cars/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_cars_delete(item_id):
    if not valid_csrf():
        flash("Your session expired. Please try again.", "err")
        return redirect(url_for("admin_cars"))
    try:
        car = _fetch_car(item_id)
        supabase.table("cars").delete().eq("id", item_id).execute()
        if car:
            delete_images([car.get("main_image"), car.get("image_url")] + (car.get("gallery_images") or []))
        flash("Car and its photos deleted.", "ok")
    except Exception:
        app.logger.exception("Delete car failed")
        flash("Could not delete the car.", "err")
    return redirect(url_for("admin_cars"))


# =========================================================
# REVIEWS, BLOGS, COMMENTS, FAQS, MESSAGES, SUBSCRIBERS
# =========================================================

register_extra_routes(app, supabase, admin_required, valid_csrf, upload_image, delete_images)


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return "Upload is too large. Keep the total under 90 MB.", 413


@app.errorhandler(404)
def page_not_found(error):
    return jsonify({"error": "Page not found"}), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error"}), 500


# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)