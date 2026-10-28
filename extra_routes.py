"""
extra_routes.py
Reviews, Blogs, Blog comments, FAQs, Contact messages, Newsletter subscribers
+ Admin panel (/admin/content) for managing all of them.

app.py me sirf 2 lines add karni hain (neeche instructions dekho).
"""
import re
import time
import secrets
from collections import defaultdict, deque

from flask import (
    request, jsonify, redirect, url_for, flash, render_template_string
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+ ()-]{8,18}$")
_hits = defaultdict(deque)


def _limited(limit=6, window=60):
    """Simple per-IP rate limit (best effort on serverless)."""
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "?")
    ip = ip.split(",")[0].strip()
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def _line(value, limit):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _text(value, limit):
    return str(value or "").replace("\r\n", "\n").strip()[:limit]


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "post"


# Admin table config: which column is the on/off flag, and what to show.
TABLES = {
    "reviews": {
        "title": "Customer Reviews", "flag": "is_approved",
        "on": "Approved", "off": "Pending",
        "cols": ["name", "trip", "rating", "message"],
        "order": "created_at", "desc": True,
    },
    "blogs": {
        "title": "Blog Articles", "flag": "is_published",
        "on": "Published", "off": "Hidden",
        "cols": ["title", "category", "slug"],
        "order": "created_at", "desc": True,
    },
    "blog_comments": {
        "title": "Blog Comments", "flag": "is_approved",
        "on": "Approved", "off": "Pending",
        "cols": ["name", "email", "message", "blog_id"],
        "order": "created_at", "desc": True,
    },
    "faqs": {
        "title": "FAQs", "flag": "is_published",
        "on": "Published", "off": "Hidden",
        "cols": ["category", "question", "sort_order"],
        "order": "sort_order", "desc": False,
    },
    "contact_messages": {
        "title": "Contact Messages", "flag": "is_read",
        "on": "Read", "off": "New",
        "cols": ["name", "phone", "email", "message"],
        "order": "created_at", "desc": True,
    },
    "subscribers": {
        "title": "Subscribers", "flag": None, "on": "", "off": "",
        "cols": ["email"], "order": "created_at", "desc": True,
    },
}

CONTENT_HTML = """
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content Management | Vishal Car Rental</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:20px;font-family:Arial,sans-serif;background:#f8fafc;color:#111827}
.container{max-width:1200px;margin:auto}.panel{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin-bottom:22px}
header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:20px}
input,select,textarea{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:6px;font:inherit}
textarea{min-height:90px}label{display:block;font-size:14px;font-weight:bold;margin:12px 0 6px}
button,.button{display:inline-block;padding:9px 13px;background:#111827;color:#fff;border:0;border-radius:6px;text-decoration:none;cursor:pointer;font-size:14px}
.danger{background:#dc2626}.ok{background:#16a34a}.msg{background:#dcfce7;padding:12px;border-radius:6px}
table{width:100%;border-collapse:collapse;min-width:700px}th,td{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top;font-size:14px}
.wrap{overflow-x:auto}.tag{padding:3px 8px;border-radius:99px;font-size:12px;background:#e2e8f0}.tag.on{background:#dcfce7}
details{margin:10px 0}summary{cursor:pointer;font-weight:bold;padding:8px 0}.row{display:flex;gap:6px}.row form{margin:0}
.nav a{margin-right:6px}
</style></head><body><div class="container">
<header><div><h1 style="margin:0">Content Management</h1>
<div class="nav" style="margin-top:8px"><a class="button" href="{{ url_for('admin_dashboard') }}">&larr; Cars Dashboard</a>
{% for s in sections %}<a class="button" href="#{{ s.key }}">{{ s.title }} ({{ s.rows|length }})</a>{% endfor %}</div></div></header>
{% with messages = get_flashed_messages() %}{% for m in messages %}<p class="msg">{{ m }}</p>{% endfor %}{% endwith %}

<section class="panel"><h2>Add Content</h2>
<details><summary>+ Add Review</summary>
<form method="POST" action="{{ url_for('admin_add_review') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name *</label><input name="name" required>
<label>Trip (e.g. Kota to Bundi)</label><input name="trip">
<label>Rating (1-5) *</label><select name="rating"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select>
<label>Review *</label><textarea name="message" required></textarea>
<p><button type="submit">Add & Publish Review</button></p></form></details>

<details><summary>+ Add Blog Article</summary>
<form method="POST" action="{{ url_for('admin_add_blog') }}" enctype="multipart/form-data">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Title *</label><input name="title" required>
<label>Category</label><input name="category" placeholder="Travel Guide / Tips & Advice / Fleet Highlights">
<label>Author</label><input name="author" value="Vishal Car Rental">
<label>Read time (minutes)</label><input name="read_minutes" type="number" value="4" min="1">
<label>Short excerpt (shown on list & Google) *</label><textarea name="excerpt" required></textarea>
<label>Article content * (blank line = new paragraph, "## Heading" for heading, "- item" for bullets)</label>
<textarea name="content" style="min-height:260px" required></textarea>
<label>Cover image (optional)</label><input type="file" name="image" accept=".jpg,.jpeg,.png,.webp">
<p><button type="submit">Add & Publish Article</button></p></form></details>

<details><summary>+ Add FAQ</summary>
<form method="POST" action="{{ url_for('admin_add_faq') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Category</label><select name="category"><option>Booking</option><option>Fleet</option><option>Pricing</option><option>Requirements</option><option>Returns</option><option>Support</option></select>
<label>Question *</label><input name="question" required>
<label>Answer *</label><textarea name="answer" required></textarea>
<label>Sort order</label><input name="sort_order" type="number" value="0">
<p><button type="submit">Add FAQ</button></p></form></details></section>

{% for s in sections %}
<section class="panel" id="{{ s.key }}"><h2>{{ s.title }} ({{ s.rows|length }})</h2>
{% if s.rows %}<div class="wrap"><table><thead><tr><th>ID</th>
{% for c in s.cols %}<th>{{ c }}</th>{% endfor %}{% if s.flag %}<th>Status</th>{% endif %}<th>Date</th><th>Action</th></tr></thead><tbody>
{% for r in s.rows %}<tr><td>{{ r.get('id') }}</td>
{% for c in s.cols %}<td>{{ (r.get(c) or '')|string|truncate(110) }}</td>{% endfor %}
{% if s.flag %}<td><span class="tag {{ 'on' if r.get(s.flag) else '' }}">{{ s.on if r.get(s.flag) else s.off }}</span></td>{% endif %}
<td>{{ (r.get('created_at') or '')[:10] }}</td>
<td><div class="row">
{% if s.flag %}<form method="POST" action="{{ url_for('admin_toggle_row', table=s.key, row_id=r.get('id')) }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<button class="{{ '' if r.get(s.flag) else 'ok' }}" type="submit">{{ 'Hide / Unmark' if r.get(s.flag) else ('Mark read' if s.key == 'contact_messages' else 'Approve / Publish') }}</button></form>{% endif %}
<form method="POST" action="{{ url_for('admin_delete_row', table=s.key, row_id=r.get('id')) }}" onsubmit="return confirm('Delete permanently?')">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="danger" type="submit">Delete</button></form></div></td></tr>
{% endfor %}</tbody></table></div>{% else %}<p>Abhi kuch nahi hai.</p>{% endif %}</section>
{% endfor %}
</div></body></html>
"""


def register_extra_routes(app, supabase, admin_required, valid_csrf, upload_image):

    def fail(message, code=400):
        return jsonify({"error": message}), code

    def guard(data):
        """Honeypot + rate limit. Returns a response if request must stop."""
        if data.get("website"):                       # bots fill hidden field
            return jsonify({"ok": True}), 200
        if _limited():
            return fail("Too many requests. Please wait a minute and try again.", 429)
        return None

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------
    @app.route("/api/reviews", methods=["GET"])
    def api_reviews():
        try:
            res = (supabase.table("reviews")
                   .select("id,name,trip,rating,message,avatar_url,created_at")
                   .eq("is_approved", True)
                   .order("created_at", desc=True).limit(100).execute())
            return jsonify({"reviews": res.data or []})
        except Exception:
            app.logger.exception("reviews fetch")
            return fail("Reviews load nahi hue.", 500)

    @app.route("/api/reviews", methods=["POST"])
    def api_add_review():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop:
            return stop
        name = _line(data.get("name"), 60)
        trip = _line(data.get("trip"), 60)
        message = _text(data.get("message"), 600)
        try:
            rating = int(data.get("rating", 5))
        except (TypeError, ValueError):
            rating = 0
        if len(name) < 2 or len(message) < 10 or not 1 <= rating <= 5:
            return fail("Please enter your name, a 1-5 rating and a review (min 10 characters).")
        try:
            supabase.table("reviews").insert({
                "name": name, "trip": trip, "rating": rating,
                "message": message, "is_approved": False,
            }).execute()
            return jsonify({"ok": True}), 201
        except Exception:
            app.logger.exception("review insert")
            return fail("Review save nahi hui. Please try again.", 500)

    @app.route("/api/blogs", methods=["GET"])
    def api_blogs():
        try:
            res = (supabase.table("blogs")
                   .select("id,slug,title,category,excerpt,image_url,author,read_minutes,created_at")
                   .eq("is_published", True)
                   .order("created_at", desc=True).execute())
            return jsonify({"blogs": res.data or []})
        except Exception:
            app.logger.exception("blogs fetch")
            return fail("Articles load nahi hue.", 500)

    @app.route("/api/blogs/<slug>", methods=["GET"])
    def api_blog_detail(slug):
        try:
            res = (supabase.table("blogs").select("*").eq("slug", slug)
                   .eq("is_published", True).limit(1).execute())
            if not res.data:
                return fail("Article not found", 404)
            blog = res.data[0]
            comments = (supabase.table("blog_comments")
                        .select("id,name,message,created_at")
                        .eq("blog_id", blog["id"]).eq("is_approved", True)
                        .order("created_at").execute()).data or []
            recent = (supabase.table("blogs")
                      .select("slug,title,category,created_at")
                      .eq("is_published", True).neq("slug", slug)
                      .order("created_at", desc=True).limit(3).execute()).data or []
            return jsonify({"blog": blog, "comments": comments, "recent": recent})
        except Exception:
            app.logger.exception("blog detail")
            return fail("Article load nahi hua.", 500)

    @app.route("/api/blogs/<slug>/comments", methods=["POST"])
    def api_add_comment(slug):
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop:
            return stop
        name = _line(data.get("name"), 60)
        email = _line(data.get("email"), 120)
        message = _text(data.get("message"), 800)
        if len(name) < 2 or not EMAIL_RE.match(email) or len(message) < 5:
            return fail("Please enter a valid name, email and comment.")
        try:
            blog = (supabase.table("blogs").select("id").eq("slug", slug)
                    .eq("is_published", True).limit(1).execute()).data
            if not blog:
                return fail("Article not found", 404)
            supabase.table("blog_comments").insert({
                "blog_id": blog[0]["id"], "name": name, "email": email,
                "message": message, "is_approved": False,
            }).execute()
            return jsonify({"ok": True}), 201
        except Exception:
            app.logger.exception("comment insert")
            return fail("Comment save nahi hua.", 500)

    @app.route("/api/faqs", methods=["GET"])
    def api_faqs():
        try:
            res = (supabase.table("faqs")
                   .select("id,category,question,answer,sort_order")
                   .eq("is_published", True)
                   .order("sort_order").order("id").execute())
            return jsonify({"faqs": res.data or []})
        except Exception:
            app.logger.exception("faqs fetch")
            return fail("FAQs load nahi hue.", 500)

    @app.route("/api/contact", methods=["POST"])
    def api_contact():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop:
            return stop
        name = _line(data.get("name") or
                     f"{data.get('first_name', '')} {data.get('last_name', '')}", 90)
        email = _line(data.get("email"), 120)
        phone = _line(data.get("phone"), 20)
        message = _text(data.get("message"), 1000)
        if (len(name) < 2 or not EMAIL_RE.match(email)
                or not PHONE_RE.match(phone) or len(message) < 10):
            return fail("Please fill name, valid email, phone and message.")
        try:
            supabase.table("contact_messages").insert({
                "name": name, "email": email, "phone": phone, "message": message,
            }).execute()
            return jsonify({"ok": True}), 201
        except Exception:
            app.logger.exception("contact insert")
            return fail("Message save nahi hua.", 500)

    @app.route("/api/subscribe", methods=["POST"])
    def api_subscribe():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop:
            return stop
        email = _line(data.get("email"), 120).lower()
        if not EMAIL_RE.match(email):
            return fail("Please enter a valid email.")
        try:
            supabase.table("subscribers").upsert(
                {"email": email}, on_conflict="email").execute()
            return jsonify({"ok": True}), 201
        except Exception:
            app.logger.exception("subscribe")
            return fail("Subscribe nahi ho paaya.", 500)

    # ------------------------------------------------------------
    # ADMIN
    # ------------------------------------------------------------
    @app.route("/admin/content", methods=["GET"])
    @admin_required
    def admin_content():
        sections = []
        try:
            for key, cfg in TABLES.items():
                rows = (supabase.table(key).select("*")
                        .order(cfg["order"], desc=cfg["desc"])
                        .limit(200).execute()).data or []
                sections.append({"key": key, "rows": rows, **cfg})
            return render_template_string(CONTENT_HTML, sections=sections)
        except Exception:
            app.logger.exception("content page")
            return "Content page load nahi hua. Supabase tables (schema.sql) check karo.", 500

    def _back(message):
        flash(message)
        return redirect(url_for("admin_content"))

    @app.route("/admin/content/reviews/add", methods=["POST"])
    @admin_required
    def admin_add_review():
        if not valid_csrf():
            return _back("Invalid form session.")
        try:
            supabase.table("reviews").insert({
                "name": _line(request.form.get("name"), 60),
                "trip": _line(request.form.get("trip"), 60),
                "rating": max(1, min(5, int(request.form.get("rating", 5)))),
                "message": _text(request.form.get("message"), 600),
                "is_approved": True,
            }).execute()
            return _back("Review add ho gaya.")
        except Exception:
            app.logger.exception("admin add review")
            return _back("Review add nahi ho paaya.")

    @app.route("/admin/content/blogs/add", methods=["POST"])
    @admin_required
    def admin_add_blog():
        if not valid_csrf():
            return _back("Invalid form session.")
        try:
            title = _line(request.form.get("title"), 160)
            excerpt = _text(request.form.get("excerpt"), 400)
            content = _text(request.form.get("content"), 20000)
            if not title or not excerpt or not content:
                return _back("Title, excerpt aur content required hain.")

            slug = _slug(title)
            exists = supabase.table("blogs").select("id").eq("slug", slug).limit(1).execute().data
            if exists:
                slug = f"{slug}-{secrets.token_hex(2)}"

            image_url = None
            image = request.files.get("image")
            if image and image.filename:
                image_url = upload_image(image)

            supabase.table("blogs").insert({
                "slug": slug, "title": title, "excerpt": excerpt, "content": content,
                "category": _line(request.form.get("category"), 60),
                "author": _line(request.form.get("author"), 60) or "Vishal Car Rental",
                "read_minutes": max(1, int(request.form.get("read_minutes") or 4)),
                "image_url": image_url, "is_published": True,
            }).execute()
            return _back("Blog article publish ho gaya.")
        except ValueError as error:
            return _back(str(error))
        except Exception:
            app.logger.exception("admin add blog")
            return _back("Article add nahi ho paaya. Logs check karo.")

    @app.route("/admin/content/faqs/add", methods=["POST"])
    @admin_required
    def admin_add_faq():
        if not valid_csrf():
            return _back("Invalid form session.")
        try:
            supabase.table("faqs").insert({
                "category": _line(request.form.get("category"), 40),
                "question": _line(request.form.get("question"), 250),
                "answer": _text(request.form.get("answer"), 1500),
                "sort_order": int(request.form.get("sort_order") or 0),
                "is_published": True,
            }).execute()
            return _back("FAQ add ho gaya.")
        except Exception:
            app.logger.exception("admin add faq")
            return _back("FAQ add nahi ho paaya.")

    @app.route("/admin/content/<table>/<int:row_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_row(table, row_id):
        cfg = TABLES.get(table)
        if not cfg or not cfg["flag"] or not valid_csrf():
            return _back("Invalid request.")
        try:
            flag = cfg["flag"]
            row = (supabase.table(table).select(flag).eq("id", row_id)
                   .limit(1).execute()).data
            if not row:
                return _back("Row nahi mili.")
            supabase.table(table).update({flag: not row[0][flag]}).eq("id", row_id).execute()
            return _back("Status update ho gaya.")
        except Exception:
            app.logger.exception("toggle row")
            return _back("Update nahi ho paaya.")

    @app.route("/admin/content/<table>/<int:row_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_row(table, row_id):
        if table not in TABLES or not valid_csrf():
            return _back("Invalid request.")
        try:
            supabase.table(table).delete().eq("id", row_id).execute()
            return _back("Delete ho gaya.")
        except Exception:
            app.logger.exception("delete row")
            return _back("Delete nahi ho paaya.")