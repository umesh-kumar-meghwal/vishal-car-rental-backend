
import os
import uuid
import secrets
import hmac
import json

from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    render_template_string,
    flash,
)

from flask_cors import CORS
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
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024
MAX_GALLERY_IMAGES = 10
STORAGE_BUCKET = "car-images"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL aur SUPABASE_SERVICE_ROLE_KEY environment variables set karo."
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

if allowed_origins:
    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}}
    )


# =========================================================
# SECURITY / CSRF
# =========================================================

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


@app.context_processor
def inject_template_helpers():
    return {"csrf_token": get_csrf_token}


def valid_csrf():
    submitted = request.form.get("csrf_token", "")
    saved = session.get("csrf_token", "")

    return bool(
        submitted
        and saved
        and hmac.compare_digest(submitted, saved)
    )


def admin_required(view_function):
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))

        return view_function(*args, **kwargs)

    return wrapped


# =========================================================
# IMAGE UPLOAD
# =========================================================

def upload_car_image(file):
    """
    Supabase Storage mein image upload karke public URL return karta hai.
    """

    if not file or not file.filename:
        raise ValueError("Image select karo.")

    original_name = secure_filename(file.filename)

    if "." not in original_name:
        raise ValueError("Image file ka extension missing hai.")

    extension = original_name.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            "Sirf JPG, JPEG, PNG aur WEBP images allowed hain."
        )

    file_bytes = file.read()

    if not file_bytes:
        raise ValueError("Uploaded image empty hai.")

    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise ValueError("Har image 8 MB se chhoti honi chahiye.")

    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }

    storage_path = f"cars/{uuid.uuid4().hex}.{extension}"

    supabase.storage.from_(STORAGE_BUCKET).upload(
        storage_path,
        file_bytes,
        {
            "content-type": content_types[extension],
            "upsert": "false",
        },
    )

    public_url = supabase.storage.from_(
        STORAGE_BUCKET
    ).get_public_url(storage_path)

    # Supabase SDK versions may return a URL string or a dictionary.
    if isinstance(public_url, dict):
        public_url = (
            public_url.get("publicUrl")
            or public_url.get("publicURL")
            or public_url.get("url")
        )

    if not public_url:
        raise RuntimeError("Uploaded image ka public URL nahi mila.")

    return public_url


# =========================================================
# PUBLIC API - AVAILABLE CARS
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
        result = (
            supabase.table("cars")
            .select("*")
            .eq("is_available", True)
            .order("created_at", desc=True)
            .execute()
        )

        cars = result.data or []

        # Keep image_url for compatibility with an existing frontend.
        for car in cars:
            if not car.get("main_image"):
                car["main_image"] = car.get("image_url")

            if not car.get("gallery_images"):
                car["gallery_images"] = []

            if not car.get("features"):
                car["features"] = []

        return jsonify({"cars": cars}), 200

    except Exception as error:
        app.logger.exception("Could not fetch cars")
        return jsonify({
            "error": "Cars fetch nahi ho paayi."
        }), 500


# =========================================================
# ADMIN LOGIN
# =========================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Login | Kota Carz</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f1f5f9;
        }
        .card {
            width: 100%;
            max-width: 400px;
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 8px 30px #00000012;
        }
        h1 { margin-top: 0; font-size: 25px; }
        label { display: block; margin: 16px 0 7px; }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #cbd5e1;
            border-radius: 7px;
        }
        button {
            width: 100%;
            margin-top: 20px;
            padding: 13px;
            background: #111827;
            color: white;
            border: 0;
            border-radius: 7px;
            cursor: pointer;
        }
        .message { padding: 10px; background: #fee2e2; border-radius: 6px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Kota Carz Admin</h1>
        <p>Login to manage your cars.</p>

        {% with messages = get_flashed_messages() %}
            {% for message in messages %}
                <p class="message">{{ message }}</p>
            {% endfor %}
        {% endwith %}

        <form method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

            <label>Username</label>
            <input type="text" name="username" required
                   autocomplete="username">

            <label>Password</label>
            <input type="password" name="password" required
                   autocomplete="current-password">

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
            flash("Session expire hua hai. Dobara try karo.")
            return redirect(url_for("admin_login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            result = (
                supabase.table("admin")
                .select("username, password_hash")
                .eq("username", username)
                .limit(1)
                .execute()
            )

            admins = result.data or []

            if admins:
                session.clear()
                session["admin_logged_in"] = True
                session["admin_username"] = admins[0]["username"]
                session["csrf_token"] = secrets.token_urlsafe(32)

                return redirect(url_for("admin_dashboard"))

            flash("Username ya password galat hai.")

        except Exception:
            app.logger.exception("Admin login failed")
            flash("Login abhi nahi ho paaya. Configuration check karo.")

    return render_template_string(LOGIN_HTML)


# =========================================================
# ADMIN DASHBOARD
# =========================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Car Management | Kota Carz</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f8fafc;
            color: #111827;
        }
        .container { max-width: 1200px; margin: auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 24px;
        }
        .panel {
            background: white;
            padding: 22px;
            margin-bottom: 24px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
        }
        .form-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 15px;
        }
        .field { min-width: 0; }
        .full { grid-column: 1 / -1; }
        label {
            display: block;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 7px;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font: inherit;
        }
        textarea { min-height: 90px; resize: vertical; }
        input[type="checkbox"] { width: auto; }
        input[type="file"] { background: #f8fafc; }
        button, .button {
            display: inline-block;
            padding: 11px 15px;
            background: #111827;
            color: white;
            border: 0;
            border-radius: 6px;
            text-decoration: none;
            cursor: pointer;
        }
        .danger { background: #dc2626; }
        .success { background: #dcfce7; padding: 12px; }
        .error { background: #fee2e2; padding: 12px; }
        .table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; min-width: 650px; }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
            vertical-align: top;
        }
        .car-image {
            width: 90px;
            height: 65px;
            object-fit: cover;
            border-radius: 6px;
        }
        .muted { color: #64748b; font-size: 13px; }
        @media (max-width: 650px) {
            body { padding: 12px; }
            .form-grid { grid-template-columns: 1fr; }
            .full { grid-column: auto; }
            .panel { padding: 15px; }
        }
    </style>
</head>
<body>
<div class="container">
    <header>
        <div>
            <h1>Car Management</h1>
            <p class="muted">
                Logged in as {{ session.get("admin_username", "Admin") }}
            </p>
        </div>
        <form method="POST" action="{{ url_for('admin_logout') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button type="submit">Logout</button>
        </form>
    </header>

    {% with messages = get_flashed_messages() %}
        {% for message in messages %}
            <p class="success">{{ message }}</p>
        {% endfor %}
    {% endwith %}

    <section class="panel">
        <h2>Add New Car</h2>
        <p class="muted">
            Main image required hai. Gallery mein maximum 10 images select kar sakte ho.
            Har image 8 MB se chhoti honi chahiye.
        </p>

        <form method="POST"
              action="{{ url_for('admin_add_car') }}"
              enctype="multipart/form-data">

            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

            <div class="form-grid">

                <div class="field">
                    <label>Car Name *</label>
                    <input name="name" required placeholder="Maruti Suzuki Baleno">
                </div>

                <div class="field">
                    <label>Brand *</label>
                    <input name="brand" required placeholder="Maruti Suzuki">
                </div>

                <div class="field">
                    <label>Category</label>
                    <input name="category" placeholder="Hatchback">
                </div>

                <div class="field">
                    <label>Rental Price Per Day (₹) *</label>
                    <input name="price" type="number" min="0" step="0.01" required>
                </div>

                <div class="field">
                    <label>Ex-showroom Price</label>
                    <input name="ex_showroom_price" placeholder="₹6.66 - 9.88 Lakh">
                </div>

                <div class="field">
                    <label>Year *</label>
                    <input name="year" type="number" min="1900" max="2100" required>
                </div>

                <div class="field">
                    <label>Fuel</label>
                    <select name="fuel">
                        <option value="">Select fuel</option>
                        <option>Petrol</option>
                        <option>Diesel</option>
                        <option>CNG</option>
                        <option>Electric</option>
                        <option>Hybrid</option>
                    </select>
                </div>

                <div class="field">
                    <label>Transmission</label>
                    <select name="transmission">
                        <option value="">Select transmission</option>
                        <option>Manual</option>
                        <option>Automatic</option>
                        <option>AMT</option>
                        <option>CVT</option>
                        <option>DCT</option>
                    </select>
                </div>

                <div class="field">
                    <label>Gearbox</label>
                    <input name="gearbox" placeholder="5-Speed Manual">
                </div>

                <div class="field">
                    <label>Seats</label>
                    <input name="seats" placeholder="5">
                </div>

                <div class="field">
                    <label>KM Included Per Day</label>
                    <input name="km_included" placeholder="300 km/day">
                </div>

                <div class="field">
                    <label>Mileage</label>
                    <input name="mileage" placeholder="22.35 Kmpl">
                </div>

                <div class="field">
                    <label>Engine</label>
                    <input name="engine" placeholder="1197 cc, 4 Cylinder">
                </div>

                <div class="field">
                    <label>Max Power</label>
                    <input name="max_power" placeholder="88.50 bhp @ 6000 rpm">
                </div>

                <div class="field">
                    <label>Max Torque</label>
                    <input name="max_torque" placeholder="113 Nm @ 4400 rpm">
                </div>

                <div class="field">
                    <label>Fuel Tank</label>
                    <input name="fuel_tank" placeholder="37 L">
                </div>

                <div class="field">
                    <label>Boot Space</label>
                    <input name="boot_space" placeholder="318 L">
                </div>

                <div class="field">
                    <label>Ground Clearance</label>
                    <input name="ground_clearance" placeholder="170 mm">
                </div>

                <div class="field">
                    <label>Dimensions</label>
                    <input name="dimensions" placeholder="3990 x 1745 x 1500 mm">
                </div>

                <div class="field">
                    <label>Wheelbase</label>
                    <input name="wheelbase" placeholder="2520 mm">
                </div>

                <div class="field">
                    <label>Competitors</label>
                    <input name="competitors" placeholder="Hyundai i20, Tata Altroz">
                </div>

                <div class="field">
                    <label>Guarantee / Rental Terms</label>
                    <input name="guarantee" placeholder="Kota Carz rental guarantee">
                </div>

                <div class="field full">
                    <label>Car Description</label>
                    <textarea name="description"
                              placeholder="Car ki details likho..."></textarea>
                </div>

                <div class="field full">
                    <label>Features (har feature alag line mein)</label>
                    <textarea name="features"
                              placeholder="ABS&#10;Airbags&#10;Power Steering"></textarea>
                </div>

                <div class="field full">
                    <label>Main Car Image *</label>
                    <input type="file" name="main_image"
                           accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                           required>
                </div>

                <div class="field full">
                    <label>Gallery Images (multiple select kar sakte ho)</label>
                    <input type="file" name="gallery_images" multiple
                           accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp">
                </div>

                <div class="field full">
                    <label>
                        <input type="checkbox" name="is_available" value="true" checked>
                        Car available for rent
                    </label>
                </div>

                <div class="field full">
                    <button type="submit">Upload Images & Add Car</button>
                </div>

            </div>
        </form>
    </section>

    <section class="panel">
        <h2>All Cars ({{ cars|length }})</h2>

        {% if cars %}
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Image</th>
                        <th>Car</th>
                        <th>Price/Day</th>
                        <th>Status</th>
                        <th>Gallery</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                {% for car in cars %}
                    <tr>
                        <td>
                            {% set img = car.get("main_image") or car.get("image_url") %}
                            {% if img %}
                                <img class="car-image" src="{{ img }}" alt="Car image">
                            {% else %}
                                No image
                            {% endif %}
                        </td>
                        <td>
                            <strong>{{ car.get("name", "Unnamed car") }}</strong><br>
                            <span class="muted">
                                {{ car.get("brand", "") }} · {{ car.get("year", "") }}
                            </span>
                        </td>
                        <td>₹{{ car.get("price", "") }}</td>
                        <td>
                            {{ "Available" if car.get("is_available") else "Unavailable" }}
                        </td>
                        <td>
                            {% set gallery = car.get("gallery_images") or [] %}
                            {{ gallery|length if gallery is iterable and gallery is not string else 0 }}
                        </td>
                        <td>
                            <form method="POST"
                                  action="{{ url_for('admin_delete_car', car_id=car.get('id')) }}"
                                  onsubmit="return confirm('Kya aap ye car record delete karna chahte ho?')">
                                <input type="hidden" name="csrf_token"
                                       value="{{ csrf_token() }}">
                                <button class="danger" type="submit">Delete</button>
                            </form>
                            <form method="GET"
                                action="{{ url_for('admin_edit_car', car_id=car.get('id')) }}"
                                style="display:inline-block; margin-bottom:6px;">
                                <button type="submit">Edit</button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
            <p>Abhi koi car add nahi hui hai.</p>
        {% endif %}
    </section>
</div>
</body>
</html>
"""


@app.route("/admin", methods=["GET"])
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

        return render_template_string(
            DASHBOARD_HTML,
            cars=cars
        )

    except Exception:
        app.logger.exception("Dashboard load failed")
        return "Dashboard load nahi ho paaya. Server logs check karo.", 500


# =========================================================
# ADD CAR + MAIN IMAGE + GALLERY
# =========================================================

@app.route("/admin/cars/add", methods=["POST"])
@admin_required
def admin_add_car():
    if not valid_csrf():
        flash("Invalid form session. Dobara submit karo.")
        return redirect(url_for("admin_dashboard"))

    uploaded_urls = []

    try:
        name = request.form.get("name", "").strip()
        brand = request.form.get("brand", "").strip()
        price_text = request.form.get("price", "").strip()
        year_text = request.form.get("year", "").strip()

        if not name or not brand or not price_text or not year_text:
            raise ValueError("Name, brand, price aur year required hain.")

        try:
            price = float(price_text)
            year = int(year_text)
        except ValueError:
            raise ValueError("Price aur year valid numbers hone chahiye.")

        if price < 0:
            raise ValueError("Price negative nahi ho sakti.")

        if year < 1900 or year > 2100:
            raise ValueError("Year valid range mein enter karo.")

        main_file = request.files.get("main_image")

        if not main_file or not main_file.filename:
            raise ValueError("Main car image select karna required hai.")

        gallery_files = [
            file for file in request.files.getlist("gallery_images")
            if file and file.filename
        ]

        if len(gallery_files) > MAX_GALLERY_IMAGES:
            raise ValueError(
                f"Maximum {MAX_GALLERY_IMAGES} gallery images allowed hain."
            )

        # Upload the main image first.
        main_image_url = upload_car_image(main_file)
        uploaded_urls.append(main_image_url)

        # Upload gallery images.
        gallery_urls = []

        for gallery_file in gallery_files:
            image_url = upload_car_image(gallery_file)
            uploaded_urls.append(image_url)
            gallery_urls.append(image_url)

        # Features are stored as a JSONB array.
        features_text = request.form.get("features", "")
        features = [
            line.strip()
            for line in features_text.splitlines()
            if line.strip()
        ]

        car_data = {
            "name": name,
            "brand": brand,
            "price": price,
            "year": year,
            "fuel": request.form.get("fuel", "").strip(),
            "transmission": request.form.get("transmission", "").strip(),
            "description": request.form.get("description", "").strip(),
            "is_available": request.form.get("is_available") == "true",

            # Main image also goes into image_url for old frontend compatibility.
            "image_url": main_image_url,
            "main_image": main_image_url,
            "gallery_images": gallery_urls,

            "category": request.form.get("category", "").strip(),
            "ex_showroom_price": request.form.get("ex_showroom_price", "").strip(),
            "km_included": request.form.get("km_included", "").strip(),
            "seats": request.form.get("seats", "").strip(),
            "mileage": request.form.get("mileage", "").strip(),
            "gearbox": request.form.get("gearbox", "").strip(),
            "engine": request.form.get("engine", "").strip(),
            "max_power": request.form.get("max_power", "").strip(),
            "max_torque": request.form.get("max_torque", "").strip(),
            "fuel_tank": request.form.get("fuel_tank", "").strip(),
            "boot_space": request.form.get("boot_space", "").strip(),
            "ground_clearance": request.form.get("ground_clearance", "").strip(),
            "dimensions": request.form.get("dimensions", "").strip(),
            "wheelbase": request.form.get("wheelbase", "").strip(),
            "features": features,
            "competitors": request.form.get("competitors", "").strip(),
            "guarantee": request.form.get("guarantee", "").strip(),
        }

        supabase.table("cars").insert(car_data).execute()

        flash("Car aur images successfully add ho gayi!")
        return redirect(url_for("admin_dashboard"))

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("admin_dashboard"))

    except Exception:
        app.logger.exception("Add car failed")

        # Storage uploads may remain if the database insert fails.
        flash(
            "Car add nahi ho paayi. Supabase columns, Storage permissions "
            "aur server logs check karo."
        )
        return redirect(url_for("admin_dashboard"))


# =========================================================
# DELETE CAR RECORD
# =========================================================

@app.route("/admin/cars/<int:car_id>/delete", methods=["POST"])
@admin_required
def admin_delete_car(car_id):
    if not valid_csrf():
        flash("Invalid form session. Dobara try karo.")
        return redirect(url_for("admin_dashboard"))

    try:
        (
            supabase.table("cars")
            .delete()
            .eq("id", car_id)
            .execute()
        )

        flash(
            "Car database se delete ho gayi. "
            "Storage mein uski images automatically delete nahi hui hain."
        )

    except Exception:
        app.logger.exception("Delete car failed")
        flash("Car delete nahi ho paayi.")

    return redirect(url_for("admin_dashboard"))


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    if not valid_csrf():
        flash("Invalid form session.")
        return redirect(url_for("admin_dashboard"))

    session.clear()
    return redirect(url_for("admin_login"))


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return (
        "Upload size limit exceed ho gayi. Total upload 90 MB se kam rakho.",
        413,
    )


@app.errorhandler(404)
def page_not_found(error):
    return jsonify({"error": "Page not found"}), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error"}), 500

# =========================================================
# EDIT CAR
# =========================================================

EDIT_CAR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Car | Kota Carz</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f8fafc;
            color: #111827;
        }
        .container { max-width: 1000px; margin: auto; }
        .panel {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 22px;
            margin-bottom: 20px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 15px;
        }
        .field { min-width: 0; }
        .full { grid-column: 1 / -1; }
        label {
            display: block;
            margin-bottom: 7px;
            font-weight: bold;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font: inherit;
        }
        input[type="checkbox"] { width: auto; }
        input[type="file"] { background: #f8fafc; }
        textarea { min-height: 90px; }
        button, .btn {
            display: inline-block;
            padding: 11px 15px;
            border: 0;
            border-radius: 6px;
            background: #111827;
            color: white;
            text-decoration: none;
            cursor: pointer;
        }
        .image {
            width: 150px;
            height: 105px;
            object-fit: cover;
            border-radius: 7px;
        }
        .muted { color: #64748b; font-size: 13px; }
        .message { background: #fee2e2; padding: 10px; }
        @media (max-width: 600px) {
            .grid { grid-template-columns: 1fr; }
            .full { grid-column: auto; }
            body { padding: 10px; }
            .panel { padding: 14px; }
        }
    </style>
</head>
<body>
<div class="container">
    <p><a class="btn" href="{{ url_for('admin_dashboard') }}">Back to Dashboard</a></p>

    <section class="panel">
        <h1>Edit Car: {{ car.get('name', '') }}</h1>

        {% with messages = get_flashed_messages() %}
            {% for message in messages %}
                <p class="message">{{ message }}</p>
            {% endfor %}
        {% endwith %}

        <form method="POST"
              enctype="multipart/form-data"
              action="{{ url_for('admin_edit_car', car_id=car.get('id')) }}">

            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

            <div class="grid">
                <div class="field">
                    <label>Car Name *</label>
                    <input name="name" value="{{ car.get('name') or '' }}" required>
                </div>

                <div class="field">
                    <label>Brand *</label>
                    <input name="brand" value="{{ car.get('brand') or '' }}" required>
                </div>

                <div class="field">
                    <label>Category</label>
                    <input name="category" value="{{ car.get('category') or '' }}">
                </div>

                <div class="field">
                    <label>Rental Price Per Day (₹) *</label>
                    <input type="number" name="price" min="0" step="0.01"
                           value="{{ car.get('price', '') }}" required>
                </div>

                <div class="field">
                    <label>Ex-showroom Price</label>
                    <input name="ex_showroom_price"
                           value="{{ car.get('ex_showroom_price') or '' }}">
                </div>

                <div class="field">
                    <label>Year *</label>
                    <input type="number" name="year" min="1900" max="2100"
                           value="{{ car.get('year', '') }}" required>
                </div>

                <div class="field">
                    <label>Fuel</label>
                    <select name="fuel">
                        {% for option in ['Petrol', 'Diesel', 'CNG', 'Electric', 'Hybrid'] %}
                            <option value="{{ option }}"
                                {% if car.get('fuel') == option %}selected{% endif %}>
                                {{ option }}
                            </option>
                        {% endfor %}
                    </select>
                </div>

                <div class="field">
                    <label>Transmission</label>
                    <select name="transmission">
                        {% for option in ['Manual', 'Automatic', 'AMT', 'CVT', 'DCT'] %}
                            <option value="{{ option }}"
                                {% if car.get('transmission') == option %}selected{% endif %}>
                                {{ option }}
                            </option>
                        {% endfor %}
                    </select>
                </div>

                <div class="field">
                    <label>Gearbox</label>
                    <input name="gearbox" value="{{ car.get('gearbox') or '' }}">
                </div>

                <div class="field">
                    <label>Seats</label>
                    <input name="seats" value="{{ car.get('seats') or '' }}">
                </div>

                <div class="field">
                    <label>KM Included Per Day</label>
                    <input name="km_included" value="{{ car.get('km_included') or '' }}">
                </div>

                <div class="field">
                    <label>Mileage</label>
                    <input name="mileage" value="{{ car.get('mileage') or '' }}">
                </div>

                <div class="field">
                    <label>Engine</label>
                    <input name="engine" value="{{ car.get('engine') or '' }}">
                </div>

                <div class="field">
                    <label>Max Power</label>
                    <input name="max_power" value="{{ car.get('max_power') or '' }}">
                </div>

                <div class="field">
                    <label>Max Torque</label>
                    <input name="max_torque" value="{{ car.get('max_torque') or '' }}">
                </div>

                <div class="field">
                    <label>Fuel Tank</label>
                    <input name="fuel_tank" value="{{ car.get('fuel_tank') or '' }}">
                </div>

                <div class="field">
                    <label>Boot Space</label>
                    <input name="boot_space" value="{{ car.get('boot_space') or '' }}">
                </div>

                <div class="field">
                    <label>Ground Clearance</label>
                    <input name="ground_clearance"
                           value="{{ car.get('ground_clearance') or '' }}">
                </div>

                <div class="field">
                    <label>Dimensions</label>
                    <input name="dimensions" value="{{ car.get('dimensions') or '' }}">
                </div>

                <div class="field">
                    <label>Wheelbase</label>
                    <input name="wheelbase" value="{{ car.get('wheelbase') or '' }}">
                </div>

                <div class="field">
                    <label>Competitors</label>
                    <input name="competitors" value="{{ car.get('competitors') or '' }}">
                </div>

                <div class="field">
                    <label>Guarantee / Rental Terms</label>
                    <input name="guarantee" value="{{ car.get('guarantee') or '' }}">
                </div>

                <div class="field full">
                    <label>Description</label>
                    <textarea name="description">{{ car.get('description') or '' }}</textarea>
                </div>

                <div class="field full">
                    <label>Features (har line par ek feature)</label>
                    <textarea name="features">{% for feature in car.get('features') or [] %}{{ feature }}
{% endfor %}</textarea>
                </div>

                <div class="field full">
                    <label>Current Main Image</label>
                    {% set main_img = car.get('main_image') or car.get('image_url') %}
                    {% if main_img %}
                        <p><img class="image" src="{{ main_img }}" alt="Current main image"></p>
                    {% else %}
                        <p class="muted">No main image uploaded.</p>
                    {% endif %}
                    <label>Upload a new main image (optional)</label>
                    <input type="file" name="main_image"
                           accept=".jpg,.jpeg,.png,.webp">
                    <p class="muted">Koi nayi image select nahi karoge to current image rahegi.</p>
                </div>

                <div class="field full">
                    <label>Current Gallery Images</label>
                    {% for image_url in car.get('gallery_images') or [] %}
                        <img class="image" src="{{ image_url }}" alt="Gallery image">
                    {% else %}
                        <p class="muted">No gallery images uploaded.</p>
                    {% endfor %}

                    <label>Upload gallery images (optional)</label>
                    <input type="file" name="gallery_images" multiple
                           accept=".jpg,.jpeg,.png,.webp">
                    <p class="muted">
                        Nayi gallery files select karne par gallery replace hogi.
                        Purani gallery rakhne ke liye files select mat karo.
                    </p>

                    <label>
                        <input type="checkbox" name="clear_gallery" value="true">
                        Purani gallery clear karo
                    </label>
                </div>

                <div class="field full">
                    <label>
                        <input type="checkbox" name="is_available" value="true"
                            {% if car.get('is_available') %}checked{% endif %}>
                        Car available for rent
                    </label>
                </div>

                <div class="field full">
                    <button type="submit">Save Car Changes</button>
                </div>
            </div>
        </form>
    </section>
</div>
</body>
</html>
"""


@app.route("/admin/cars/<int:car_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_car(car_id):
    try:
        result = (
            supabase.table("cars")
            .select("*")
            .eq("id", car_id)
            .limit(1)
            .execute()
        )

        rows = result.data or []

        if not rows:
            flash("Car nahi mili.")
            return redirect(url_for("admin_dashboard"))

        car = rows[0]

        if request.method == "GET":
            return render_template_string(EDIT_CAR_HTML, car=car)

        if not valid_csrf():
            flash("Invalid form session. Dobara try karo.")
            return redirect(url_for("admin_edit_car", car_id=car_id))

        name = request.form.get("name", "").strip()
        brand = request.form.get("brand", "").strip()
        price_text = request.form.get("price", "").strip()
        year_text = request.form.get("year", "").strip()

        if not name or not brand or not price_text or not year_text:
            raise ValueError("Name, brand, price aur year required hain.")

        try:
            price = float(price_text)
            year = int(year_text)
        except ValueError:
            raise ValueError("Price aur year valid numbers hone chahiye.")

        if price < 0:
            raise ValueError("Price negative nahi ho sakti.")

        if year < 1900 or year > 2100:
            raise ValueError("Year valid range mein enter karo.")

        main_image_url = car.get("main_image") or car.get("image_url")

        new_main_file = request.files.get("main_image")

        # No new main image selected means keep the current one.
        if new_main_file and new_main_file.filename:
            main_image_url = upload_car_image(new_main_file)

        gallery_urls = car.get("gallery_images") or []

        new_gallery_files = [
            file for file in request.files.getlist("gallery_images")
            if file and file.filename
        ]

        if len(new_gallery_files) > MAX_GALLERY_IMAGES:
            raise ValueError(
                f"Maximum {MAX_GALLERY_IMAGES} gallery images allowed hain."
            )

        if request.form.get("clear_gallery") == "true":
            gallery_urls = []

        # Selecting new gallery files replaces the existing gallery.
        if new_gallery_files:
            gallery_urls = []

            for gallery_file in new_gallery_files:
                gallery_urls.append(upload_car_image(gallery_file))

        features_text = request.form.get("features", "")
        features = [
            line.strip()
            for line in features_text.splitlines()
            if line.strip()
        ]

        updated_data = {
            "name": name,
            "brand": brand,
            "price": price,
            "year": year,
            "fuel": request.form.get("fuel", "").strip(),
            "transmission": request.form.get("transmission", "").strip(),
            "description": request.form.get("description", "").strip(),
            "is_available": request.form.get("is_available") == "true",

            "image_url": main_image_url,
            "main_image": main_image_url,
            "gallery_images": gallery_urls,

            "category": request.form.get("category", "").strip(),
            "ex_showroom_price": request.form.get("ex_showroom_price", "").strip(),
            "km_included": request.form.get("km_included", "").strip(),
            "seats": request.form.get("seats", "").strip(),
            "mileage": request.form.get("mileage", "").strip(),
            "gearbox": request.form.get("gearbox", "").strip(),
            "engine": request.form.get("engine", "").strip(),
            "max_power": request.form.get("max_power", "").strip(),
            "max_torque": request.form.get("max_torque", "").strip(),
            "fuel_tank": request.form.get("fuel_tank", "").strip(),
            "boot_space": request.form.get("boot_space", "").strip(),
            "ground_clearance": request.form.get("ground_clearance", "").strip(),
            "dimensions": request.form.get("dimensions", "").strip(),
            "wheelbase": request.form.get("wheelbase", "").strip(),
            "features": features,
            "competitors": request.form.get("competitors", "").strip(),
            "guarantee": request.form.get("guarantee", "").strip(),
        }

        # UPDATE existing row; does not create a duplicate.
        (
            supabase.table("cars")
            .update(updated_data)
            .eq("id", car_id)
            .execute()
        )

        flash("Car details successfully update ho gayi!")
        return redirect(url_for("admin_dashboard"))

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("admin_edit_car", car_id=car_id))

    except Exception:
        app.logger.exception("Edit car failed")
        return (
            "Car update nahi ho paayi. Supabase columns, Storage aur server logs check karo.",
            500,
        )








# =========================================================
# EXTRA ROUTES (reviews, blogs, faqs, contact, admin content)
# =========================================================
from extra_routes import register_extra_routes
register_extra_routes(app, supabase, admin_required, valid_csrf, upload_image)




# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
