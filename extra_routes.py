"""
extra_routes.py
Public APIs (reviews, blogs, comments, FAQs, contact, newsletter) and
separate admin pages (list / add / edit / delete) for each of them.
"""
import re
import time
import secrets
from collections import defaultdict, deque

from flask import request, jsonify, redirect, url_for, flash, render_template

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+ ()-]{8,18}$")
_hits = defaultdict(deque)


def _limited(limit=6, window=60, bucket="public"):
    """Simple in-memory rate limiter (per IP and bucket)."""
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()
    now = time.time()
    q = _hits[(bucket, ip)]
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


def F(name, label, type="text", **kw):
    return dict(name=name, label=label, type=type, **kw)


# =========================================================
# ADMIN RESOURCE DEFINITIONS (one entry = list + add + edit + delete pages)
# =========================================================

RESOURCES = {
    "reviews": dict(
        table="reviews", title="Reviews", singular="Review",
        subtitle="Customer testimonials shown on your website.",
        empty="No reviews yet.", can_create=True, order=("created_at", True),
        toggle=dict(field="is_approved", on="Approved", off="Pending", on_action="Approve", off_action="Hide"),
        columns=[("Customer", "name", "strong"), ("Trip", "trip", "text"), ("Rating", "rating", "rating"),
                 ("Review", "message", "clamp"), ("Status", "is_approved", "badge")],
        fields=[
            F("name", "Customer name", required=True, max=60, placeholder="Rahul Sharma"),
            F("trip", "Trip route / city", max=60, placeholder="Kota to Jaipur"),
            F("rating", "Rating", "select", required=True, cast=int,
              options=[("5", "5 stars"), ("4", "4 stars"), ("3", "3 stars"), ("2", "2 stars"), ("1", "1 star")],
              default=5),
            F("message", "Review", "textarea", required=True, full=True, max=600, rows=5),
            F("is_approved", "Show on website", "bool", default=True),
        ],
    ),
    "blogs": dict(
        table="blogs", title="Blog articles", singular="Article",
        subtitle="Travel guides, news and rental tips.",
        empty="No articles yet. Write your first one.", can_create=True, order=("created_at", True),
        toggle=dict(field="is_published", on="Published", off="Draft", on_action="Publish", off_action="Unpublish"),
        columns=[("Article", "slug", "slug"), ("Category", "category", "text"), ("Author", "author", "text"),
                 ("Read time", "read_minutes", "text"), ("Status", "is_published", "badge")],
        fields=[
            F("title", "Title", required=True, full=True, max=160, placeholder="Top 5 weekend getaways from Kota"),
            F("category", "Category", max=60, placeholder="Travel guides"),
            F("author", "Author", max=60, default="Vishal Car Rental"),
            F("read_minutes", "Read time (minutes)", "number", min=1, max=120, default=4),
            F("image", "Cover image", "image", column="image_url"),
            F("excerpt", "Short excerpt (SEO description)", "textarea", required=True, full=True, max=400, rows=3),
            F("content", "Content (separate paragraphs with a blank line)", "textarea",
              required=True, full=True, max=25000, rows=14),
            F("is_published", "Published", "bool", default=True),
        ],
    ),
    "comments": dict(
        table="blog_comments", title="Comments", singular="Comment",
        subtitle="Moderate comments left on your articles.",
        empty="No comments yet.", can_create=False, order=("created_at", True),
        toggle=dict(field="is_approved", on="Approved", off="Pending", on_action="Approve", off_action="Hide"),
        columns=[("Name", "name", "strong"), ("Email", "email", "text"), ("Article ID", "blog_id", "text"),
                 ("Comment", "message", "clamp"), ("Status", "is_approved", "badge")],
        fields=[
            F("name", "Name", required=True, max=60),
            F("email", "Email", "email", required=True, max=120),
            F("message", "Comment", "textarea", required=True, full=True, max=800, rows=5),
            F("is_approved", "Approved", "bool", default=False),
        ],
    ),
    "faqs": dict(
        table="faqs", title="FAQs", singular="FAQ",
        subtitle="Questions and answers shown in your help section.",
        empty="No FAQs yet.", can_create=True, order=("sort_order", False),
        toggle=dict(field="is_published", on="Visible", off="Hidden", on_action="Show", off_action="Hide"),
        columns=[("Category", "category", "strong"), ("Question", "question", "clamp"),
                 ("Answer", "answer", "clamp"), ("Order", "sort_order", "text"), ("Status", "is_published", "badge")],
        fields=[
            F("category", "Category", "select", required=True,
              options=[(c, c) for c in ["Booking", "Fleet & Specs", "Pricing & Security",
                                        "Documents Required", "Cancellation"]]),
            F("sort_order", "Display order", "number", default=0, help="Smaller numbers appear first."),
            F("question", "Question", required=True, full=True, max=250),
            F("answer", "Answer", "textarea", required=True, full=True, max=1500, rows=5),
            F("is_published", "Visible on website", "bool", default=True),
        ],
    ),
    "messages": dict(
        table="contact_messages", title="Messages", singular="Message",
        subtitle="Enquiries sent through your contact form.",
        empty="No messages yet.", can_create=False, order=("created_at", True),
        toggle=dict(field="is_read", on="Read", off="New", on_action="Mark as read", off_action="Mark as unread"),
        columns=[("Date", "created_at", "date"), ("Name", "name", "strong"), ("Phone", "phone", "text"),
                 ("Email", "email", "text"), ("Message", "message", "clamp"), ("Status", "is_read", "badge")],
        fields=[
            F("name", "Name", required=True, max=90),
            F("email", "Email", "email", required=True, max=120),
            F("phone", "Phone", "tel", required=True, max=20),
            F("message", "Message", "textarea", required=True, full=True, max=1000, rows=6),
            F("is_read", "Marked as read", "bool", default=False),
        ],
    ),
    "subscribers": dict(
        table="subscribers", title="Subscribers", singular="Subscriber",
        subtitle="Emails collected from your newsletter form.",
        empty="No subscribers yet.", can_create=True, order=("created_at", True), toggle=None,
        columns=[("Email", "email", "strong"), ("Subscribed on", "created_at", "date")],
        fields=[F("email", "Email address", "email", required=True, full=True, max=120)],
    ),
}


def _blog_before_create(data, supabase):
    slug = _slug(data["title"])
    if supabase.table("blogs").select("id").eq("slug", slug).limit(1).execute().data:
        slug = f"{slug}-{secrets.token_hex(2)}"
    data["slug"] = slug
    data.setdefault("image_url", None)


HOOKS = {"blogs": _blog_before_create}


# =========================================================
# REGISTRATION
# =========================================================

def register_extra_routes(app, supabase, admin_required, valid_csrf, upload_image):

    def fail(message, code=400):
        return jsonify({"error": message}), code

    def guard(data):
        if data.get("website"):  # honeypot field
            return jsonify({"ok": True}), 200
        if _limited():
            return fail("Too many requests. Please wait a minute and try again.", 429)
        return None

    # ------------------------------------------------------------
    # PUBLIC APIS
    # ------------------------------------------------------------
    @app.route("/api/reviews", methods=["GET"])
    def api_reviews():
        try:
            res = (supabase.table("reviews").select("*").eq("is_approved", True)
                   .order("created_at", desc=True).limit(100).execute())
            return jsonify({"reviews": res.data or []})
        except Exception:
            app.logger.exception("Load reviews failed")
            return fail("Failed to load reviews.", 500)

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
            return fail("Please provide a valid name, rating (1-5) and review text (min 10 characters).")
        try:
            supabase.table("reviews").insert({
                "name": name, "trip": trip, "rating": rating,
                "message": message, "is_approved": False,
            }).execute()
            return jsonify({"ok": True, "message": "Review submitted for approval."}), 201
        except Exception:
            app.logger.exception("Add review failed")
            return fail("Failed to record review.", 500)

    @app.route("/api/blogs", methods=["GET"])
    def api_blogs():
        try:
            res = (supabase.table("blogs")
                   .select("id,slug,title,category,excerpt,image_url,author,read_minutes,created_at")
                   .eq("is_published", True).order("created_at", desc=True).execute())
            return jsonify({"blogs": res.data or []})
        except Exception:
            app.logger.exception("Load blogs failed")
            return fail("Could not load blog posts.", 500)

    @app.route("/api/blogs/<slug>", methods=["GET"])
    def api_blog_detail(slug):
        try:
            res = (supabase.table("blogs").select("*").eq("slug", slug)
                   .eq("is_published", True).limit(1).execute())
            if not res.data:
                return fail("Article not found", 404)
            blog = res.data[0]
            comments = (supabase.table("blog_comments").select("id,name,message,created_at")
                        .eq("blog_id", blog["id"]).eq("is_approved", True)
                        .order("created_at").execute()).data or []
            recent = (supabase.table("blogs").select("slug,title,category,created_at")
                      .eq("is_published", True).neq("slug", slug)
                      .order("created_at", desc=True).limit(3).execute()).data or []
            return jsonify({"blog": blog, "comments": comments, "recent": recent})
        except Exception:
            app.logger.exception("Load blog failed")
            return fail("Failed to load article details.", 500)

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
            return fail("Please provide a valid name, email address and comment.")
        try:
            blog = (supabase.table("blogs").select("id").eq("slug", slug)
                    .eq("is_published", True).limit(1).execute()).data
            if not blog:
                return fail("Article not found", 404)
            supabase.table("blog_comments").insert({
                "blog_id": blog[0]["id"], "name": name, "email": email,
                "message": message, "is_approved": False,
            }).execute()
            return jsonify({"ok": True, "message": "Comment submitted for moderation."}), 201
        except Exception:
            app.logger.exception("Add comment failed")
            return fail("Failed to post comment.", 500)

    @app.route("/api/faqs", methods=["GET"])
    def api_faqs():
        try:
            res = (supabase.table("faqs").select("id,category,question,answer,sort_order")
                   .eq("is_published", True).order("sort_order").order("id").execute())
            return jsonify({"faqs": res.data or []})
        except Exception:
            app.logger.exception("Load FAQs failed")
            return fail("Could not load FAQs.", 500)

    @app.route("/api/contact", methods=["POST"])
    def api_contact():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop:
            return stop
        name = _line(data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}", 90)
        email = _line(data.get("email"), 120)
        phone = _line(data.get("phone"), 20)
        message = _text(data.get("message"), 1000)
        if len(name) < 2 or not EMAIL_RE.match(email) or not PHONE_RE.match(phone) or len(message) < 10:
            return fail("Please fill all required fields with a valid email and phone number.")
        try:
            supabase.table("contact_messages").insert({
                "name": name, "email": email, "phone": phone, "message": message,
            }).execute()
            return jsonify({"ok": True, "message": "Your message has been received."}), 201
        except Exception:
            app.logger.exception("Contact failed")
            return fail("Failed to send your enquiry. Please try again later.", 500)

    @app.route("/api/subscribe", methods=["POST"])
    def api_subscribe():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop:
            return stop
        email = _line(data.get("email"), 120).lower()
        if not EMAIL_RE.match(email):
            return fail("Please enter a valid email address.")
        try:
            supabase.table("subscribers").upsert({"email": email}, on_conflict="email").execute()
            return jsonify({"ok": True, "message": "Subscribed successfully."}), 201
        except Exception:
            app.logger.exception("Subscribe failed")
            return fail("Could not complete subscription.", 500)

    # ------------------------------------------------------------
    # ADMIN CRUD PAGES (generated for every resource above)
    # ------------------------------------------------------------
    def clean(res, form, files):
        """Validate form input and return a dict ready for Supabase."""
        data = {}
        for f in res["fields"]:
            name, kind = f["name"], f["type"]

            if kind == "bool":
                data[name] = form.get(name) == "on"
                continue

            if kind == "image":
                upload = files.get(name)
                if upload and upload.filename:
                    data[f["column"]] = upload_image(upload)
                continue

            raw = form.get(name, "")
            value = _text(raw, f.get("max", 2000)) if kind == "textarea" else _line(raw, f.get("max", 200))

            if f.get("required") and value == "":
                raise ValueError(f"{f['label']} is required.")

            if kind == "number":
                try:
                    value = int(value) if value else f.get("default", 0)
                except ValueError:
                    raise ValueError(f"{f['label']} must be a number.")
                if "min" in f:
                    value = max(f["min"], value)
                if "max" in f:
                    value = min(f["max"], value)
            elif kind == "email":
                value = value.lower()
                if not EMAIL_RE.match(value):
                    raise ValueError("Please enter a valid email address.")
            elif kind == "tel":
                if not PHONE_RE.match(value):
                    raise ValueError("Please enter a valid phone number.")
            elif kind == "select":
                if value not in [str(o[0]) for o in f["options"]] and (f.get("required") or value):
                    raise ValueError(f"Please choose a valid {f['label'].lower()}.")
                if f.get("cast") and value != "":
                    value = f["cast"](value)

            data[name] = value
        return data

    def get_row(res, item_id):
        rows = supabase.table(res["table"]).select("*").eq("id", item_id).limit(1).execute().data or []
        return rows[0] if rows else None

    def build(key, res):
        list_ep = f"admin_{key}"

        def list_view():
            col, desc = res["order"]
            try:
                q = supabase.table(res["table"]).select("*").order(col, desc=desc)
                if col == "sort_order":
                    q = q.order("id")
                rows = q.limit(500).execute().data or []
            except Exception:
                app.logger.exception("Load %s failed", key)
                flash(f"Could not load {res['title'].lower()}.", "err")
                rows = []
            return render_template("list.html", title=res["title"], active_nav=key, key=key, res=res, rows=rows)

        def new_view():
            values = {f["name"]: f.get("default") for f in res["fields"]}
            if request.method == "POST":
                if not valid_csrf():
                    flash("Your session expired. Please try again.", "err")
                    return redirect(url_for(f"admin_{key}_new"))
                try:
                    data = clean(res, request.form, request.files)
                    if key in HOOKS:
                        HOOKS[key](data, supabase)
                    supabase.table(res["table"]).insert(data).execute()
                    flash(f"{res['singular']} added.", "ok")
                    return redirect(url_for(list_ep))
                except ValueError as e:
                    flash(str(e), "err")
                except Exception:
                    app.logger.exception("Add %s failed", key)
                    flash(f"Could not add {res['singular'].lower()}. Check the server logs.", "err")
                return redirect(url_for(f"admin_{key}_new"))
            return render_template("form.html", title=f"Add {res['singular'].lower()}", active_nav=key,
                                   key=key, res=res, values=values, item_id=None)

        def edit_view(item_id):
            try:
                row = get_row(res, item_id)
            except Exception:
                app.logger.exception("Load %s failed", key)
                row = None
            if not row:
                flash(f"{res['singular']} not found.", "err")
                return redirect(url_for(list_ep))

            if request.method == "POST":
                if not valid_csrf():
                    flash("Your session expired. Please try again.", "err")
                    return redirect(url_for(f"admin_{key}_edit", item_id=item_id))
                try:
                    data = clean(res, request.form, request.files)
                    supabase.table(res["table"]).update(data).eq("id", item_id).execute()
                    flash(f"{res['singular']} updated.", "ok")
                    return redirect(url_for(list_ep))
                except ValueError as e:
                    flash(str(e), "err")
                except Exception:
                    app.logger.exception("Edit %s failed", key)
                    flash(f"Could not update {res['singular'].lower()}. Check the server logs.", "err")
                return redirect(url_for(f"admin_{key}_edit", item_id=item_id))

            return render_template("form.html", title=f"Edit {res['singular'].lower()}", active_nav=key,
                                   key=key, res=res, values=row, item_id=item_id)

        def toggle_view(item_id):
            if not valid_csrf():
                flash("Your session expired. Please try again.", "err")
                return redirect(url_for(list_ep))
            field = res["toggle"]["field"]
            try:
                row = get_row(res, item_id)
                if row:
                    supabase.table(res["table"]).update({field: not row.get(field)}).eq("id", item_id).execute()
                    flash("Status updated.", "ok")
            except Exception:
                app.logger.exception("Toggle %s failed", key)
                flash("Could not update status.", "err")
            return redirect(url_for(list_ep))

        def delete_view(item_id):
            if not valid_csrf():
                flash("Your session expired. Please try again.", "err")
                return redirect(url_for(list_ep))
            try:
                supabase.table(res["table"]).delete().eq("id", item_id).execute()
                flash(f"{res['singular']} deleted.", "ok")
            except Exception:
                app.logger.exception("Delete %s failed", key)
                flash(f"Could not delete {res['singular'].lower()}.", "err")
            return redirect(url_for(list_ep))

        rule = f"/admin/{key}"
        app.add_url_rule(rule, list_ep, admin_required(list_view), methods=["GET"])
        if res["can_create"]:
            app.add_url_rule(f"{rule}/new", f"admin_{key}_new", admin_required(new_view), methods=["GET", "POST"])
        app.add_url_rule(f"{rule}/<int:item_id>/edit", f"admin_{key}_edit", admin_required(edit_view),
                         methods=["GET", "POST"])
        if res["toggle"]:
            app.add_url_rule(f"{rule}/<int:item_id>/toggle", f"admin_{key}_toggle", admin_required(toggle_view),
                             methods=["POST"])
        app.add_url_rule(f"{rule}/<int:item_id>/delete", f"admin_{key}_delete", admin_required(delete_view),
                         methods=["POST"])

    for key, res in RESOURCES.items():
        build(key, res)