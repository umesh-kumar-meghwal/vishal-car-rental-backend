"""
extra_routes.py
Dedicated pages for:
- Reviews (/admin/reviews)
- Blog Articles (/admin/blogs & /admin/blogs/new)
- Blog Comments (/admin/comments)
- FAQs (/admin/faqs)
- Contact Messages (/admin/messages)
- Newsletter Subscribers (/admin/subscribers)
"""
import re
import time
import secrets
from collections import defaultdict, deque

from flask import request, jsonify, redirect, url_for, flash, render_template_string

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+ ()-]{8,18}$")
_hits = defaultdict(deque)


def _limited(limit=6, window=60):
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()
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


# =========================================================
# DEDICATED SEPARATE HTML TEMPLATES
# =========================================================

REVIEWS_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Customer Reviews</h1>
    <p class="subhead">Manage and moderate customer testimonials</p>
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0;">Add a Review</h3>
  <form method="POST" action="{{ url_for('admin_add_review') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="form-grid">
      <div class="field">
        <label>Customer Name *</label>
        <input name="name" required placeholder="John Doe">
      </div>
      <div class="field">
        <label>Trip Route / City</label>
        <input name="trip" placeholder="Kota to Jaipur">
      </div>
      <div class="field">
        <label>Rating *</label>
        <select name="rating">
          <option value="5">⭐⭐⭐⭐⭐ (5 Stars)</option>
          <option value="4">⭐⭐⭐⭐ (4 Stars)</option>
          <option value="3">⭐⭐⭐ (3 Stars)</option>
          <option value="2">⭐⭐ (2 Stars)</option>
          <option value="1">⭐ (1 Star)</option>
        </select>
      </div>
      <div class="field form-full">
        <label>Review Content *</label>
        <textarea name="message" required placeholder="Write the review content here..."></textarea>
      </div>
    </div>
    <div style="margin-top:16px;">
      <button class="btn" type="submit">Submit & Publish Review</button>
    </div>
  </form>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Customer</th>
        <th>Trip</th>
        <th>Rating</th>
        <th>Review</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for r in reviews %}
      <tr>
        <td><strong>{{ r.name }}</strong></td>
        <td>{{ r.trip or '—' }}</td>
        <td>{{ r.rating }} / 5</td>
        <td style="max-width:300px;">{{ r.message }}</td>
        <td>
          <span class="badge {{ 'badge-on' if r.is_approved else 'badge-off' }}">
            {{ 'Approved' if r.is_approved else 'Pending' }}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:8px;">
            <form method="POST" action="{{ url_for('admin_toggle_review', item_id=r.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-secondary btn-sm" type="submit">{{ 'Hide' if r.is_approved else 'Approve' }}</button>
            </form>
            <form method="POST" action="{{ url_for('admin_delete_review', item_id=r.id) }}" onsubmit="return confirm('Permanently delete review?')">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-danger btn-sm" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center; padding:30px; color:var(--muted)">No reviews found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""

BLOGS_LIST_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Blog Articles</h1>
    <p class="subhead">Manage travel guides, news, and rental advice articles</p>
  </div>
  <a href="{{ url_for('admin_add_blog_page') }}" class="btn">✍️ Write New Article</a>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Article</th>
        <th>Category</th>
        <th>Author</th>
        <th>Read Time</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for b in blogs %}
      <tr>
        <td>
          <strong>{{ b.title }}</strong><br>
          <small style="color:var(--muted)">Slug: /blogs/{{ b.slug }}</small>
        </td>
        <td>{{ b.category or 'General' }}</td>
        <td>{{ b.author }}</td>
        <td>{{ b.read_minutes }} min</td>
        <td>
          <span class="badge {{ 'badge-on' if b.is_published else 'badge-off' }}">
            {{ 'Published' if b.is_published else 'Draft' }}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:8px;">
            <form method="POST" action="{{ url_for('admin_toggle_blog', item_id=b.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-secondary btn-sm" type="submit">{{ 'Unpublish' if b.is_published else 'Publish' }}</button>
            </form>
            <form method="POST" action="{{ url_for('admin_delete_blog', item_id=b.id) }}" onsubmit="return confirm('Delete article permanently?')">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-danger btn-sm" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center; padding:30px; color:var(--muted)">No articles published yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""

BLOG_ADD_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Write Blog Article</h1>
    <p class="subhead">Create and publish insightful content for your visitors</p>
  </div>
  <a href="{{ url_for('admin_blogs_page') }}" class="btn btn-secondary">&larr; Back to Articles</a>
</div>

<div class="card">
  <form method="POST" action="{{ url_for('admin_create_blog') }}" enctype="multipart/form-data">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="form-grid">
      <div class="field form-full">
        <label>Article Title *</label>
        <input name="title" required placeholder="Top 5 Weekend Getaways from Kota">
      </div>
      <div class="field">
        <label>Category</label>
        <input name="category" placeholder="Travel Guides / Road Trips / Tips">
      </div>
      <div class="field">
        <label>Author</label>
        <input name="author" value="Vishal Car Rental">
      </div>
      <div class="field">
        <label>Read Time (minutes)</label>
        <input name="read_minutes" type="number" value="4" min="1">
      </div>
      <div class="field">
        <label>Cover Banner Image</label>
        <input type="file" name="image" accept=".jpg,.jpeg,.png,.webp">
      </div>
      <div class="field form-full">
        <label>Short Excerpt (SEO Description) *</label>
        <textarea name="excerpt" style="min-height:70px;" required placeholder="A brief one or two sentence summary shown on search results and lists..."></textarea>
      </div>
      <div class="field form-full">
        <label>Article Content * (Paragraphs separated by blank line)</label>
        <textarea name="content" style="min-height:250px;" required placeholder="Write your full article content here..."></textarea>
      </div>
    </div>
    <div style="margin-top:20px;">
      <button class="btn" type="submit">Publish Article</button>
    </div>
  </form>
</div>
{% endblock %}
"""

COMMENTS_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Blog Comments</h1>
    <p class="subhead">Moderate user responses submitted on your articles</p>
  </div>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Commenter</th>
        <th>Email</th>
        <th>Article ID</th>
        <th>Comment</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for c in comments %}
      <tr>
        <td><strong>{{ c.name }}</strong></td>
        <td>{{ c.email }}</td>
        <td>#{{ c.blog_id }}</td>
        <td style="max-width:320px;">{{ c.message }}</td>
        <td>
          <span class="badge {{ 'badge-on' if c.is_approved else 'badge-off' }}">
            {{ 'Approved' if c.is_approved else 'Pending' }}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:8px;">
            <form method="POST" action="{{ url_for('admin_toggle_comment', item_id=c.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-secondary btn-sm" type="submit">{{ 'Hide' if c.is_approved else 'Approve' }}</button>
            </form>
            <form method="POST" action="{{ url_for('admin_delete_comment', item_id=c.id) }}" onsubmit="return confirm('Delete comment?')">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-danger btn-sm" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center; padding:30px; color:var(--muted)">No comments submitted yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""

FAQS_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Frequently Asked Questions</h1>
    <p class="subhead">Manage questions and answers displayed in customer help sections</p>
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0;">Add New FAQ</h3>
  <form method="POST" action="{{ url_for('admin_add_faq') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="form-grid">
      <div class="field">
        <label>Category</label>
        <select name="category">
          <option>Booking</option><option>Fleet & Specs</option><option>Pricing & Security</option><option>Documents Required</option><option>Cancellation</option>
        </select>
      </div>
      <div class="field">
        <label>Display Order Priority</label>
        <input name="sort_order" type="number" value="0">
      </div>
      <div class="field form-full">
        <label>Question *</label>
        <input name="question" required placeholder="What documents are needed to rent a self-drive car?">
      </div>
      <div class="field form-full">
        <label>Answer *</label>
        <textarea name="answer" required placeholder="A valid driving license, Aadhaar card or Passport, and refundable security deposit..."></textarea>
      </div>
    </div>
    <div style="margin-top:16px;">
      <button class="btn" type="submit">Save and Publish FAQ</button>
    </div>
  </form>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Category</th>
        <th>Question</th>
        <th>Answer</th>
        <th>Priority</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for f in faqs %}
      <tr>
        <td><strong>{{ f.category }}</strong></td>
        <td>{{ f.question }}</td>
        <td style="max-width:300px;">{{ f.answer }}</td>
        <td>{{ f.sort_order }}</td>
        <td>
          <span class="badge {{ 'badge-on' if f.is_published else 'badge-off' }}">
            {{ 'Visible' if f.is_published else 'Hidden' }}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:8px;">
            <form method="POST" action="{{ url_for('admin_toggle_faq', item_id=f.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-secondary btn-sm" type="submit">{{ 'Hide' if f.is_published else 'Show' }}</button>
            </form>
            <form method="POST" action="{{ url_for('admin_delete_faq', item_id=f.id) }}" onsubmit="return confirm('Delete this FAQ?')">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-danger btn-sm" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center; padding:30px; color:var(--muted)">No FAQs available.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""

MESSAGES_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Contact Inquiries</h1>
    <p class="subhead">Review customer contact form messages and inquiries</p>
  </div>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Contact Person</th>
        <th>Phone & Email</th>
        <th>Message Details</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for m in messages %}
      <tr>
        <td>{{ (m.created_at or '')[:10] }}</td>
        <td><strong>{{ m.name }}</strong></td>
        <td>
          <div>📞 {{ m.phone }}</div>
          <div>✉️ {{ m.email }}</div>
        </td>
        <td style="max-width:350px;">{{ m.message }}</td>
        <td>
          <span class="badge {{ 'badge-on' if m.is_read else 'badge-off' }}">
            {{ 'Read' if m.is_read else 'New' }}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:8px;">
            <form method="POST" action="{{ url_for('admin_toggle_message', item_id=m.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-secondary btn-sm" type="submit">
                {{ 'Mark as Unread' if m.is_read else 'Mark as Read' }}
              </button>
            </form>
            <form method="POST" action="{{ url_for('admin_delete_message', item_id=m.id) }}" onsubmit="return confirm('Delete message permanently?')">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="btn btn-danger btn-sm" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center; padding:30px; color:var(--muted)">No customer inquiries received yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""

SUBSCRIBERS_HTML = """
{% block content %}
<div class="header">
  <div>
    <h1>Newsletter Subscribers</h1>
    <p class="subhead">Email addresses collected from website subscription forms</p>
  </div>
</div>

<div class="card table-wrap">
  <table>
    <thead>
      <tr>
        <th>Subscriber ID</th>
        <th>Email Address</th>
        <th>Subscribed Date</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for s in subscribers %}
      <tr>
        <td>#{{ s.id }}</td>
        <td><strong>{{ s.email }}</strong></td>
        <td>{{ (s.created_at or '')[:10] }}</td>
        <td>
          <form method="POST" action="{{ url_for('admin_delete_subscriber', item_id=s.id) }}" onsubmit="return confirm('Remove subscriber?')">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="btn btn-danger btn-sm" type="submit">Remove</button>
          </form>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="4" style="text-align:center; padding:30px; color:var(--muted)">No subscribers signed up yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
"""


# =========================================================
# ROUTE REGISTRATION FUNCTION
# =========================================================

def register_extra_routes(app, supabase, admin_required, valid_csrf, upload_image, base_template):

    def fail(message, code=400):
        return jsonify({"error": message}), code

    def guard(data):
        if data.get("website"):
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
            res = (supabase.table("reviews")
                   .select("id,name,trip,rating,message,avatar_url,created_at")
                   .eq("is_approved", True)
                   .order("created_at", desc=True).limit(100).execute())
            return jsonify({"reviews": res.data or []})
        except Exception:
            return fail("Failed to load reviews.", 500)

    @app.route("/api/reviews", methods=["POST"])
    def api_add_review():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop: return stop

        name = _line(data.get("name"), 60)
        trip = _line(data.get("trip"), 60)
        message = _text(data.get("message"), 600)
        try:
            rating = int(data.get("rating", 5))
        except (TypeError, ValueError):
            rating = 0

        if len(name) < 2 or len(message) < 10 or not 1 <= rating <= 5:
            return fail("Please provide a valid name, rating (1-5), and review text (min 10 characters).")
        try:
            supabase.table("reviews").insert({
                "name": name, "trip": trip, "rating": rating,
                "message": message, "is_approved": False,
            }).execute()
            return jsonify({"ok": True, "message": "Review submitted successfully for approval."}), 201
        except Exception:
            return fail("Failed to record review.", 500)

    @app.route("/api/blogs", methods=["GET"])
    def api_blogs():
        try:
            res = (supabase.table("blogs")
                   .select("id,slug,title,category,excerpt,image_url,author,read_minutes,created_at")
                   .eq("is_published", True)
                   .order("created_at", desc=True).execute())
            return jsonify({"blogs": res.data or []})
        except Exception:
            return fail("Could not load blog posts.", 500)

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
            return fail("Failed to load article details.", 500)

    @app.route("/api/blogs/<slug>/comments", methods=["POST"])
    def api_add_comment(slug):
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop: return stop

        name = _line(data.get("name"), 60)
        email = _line(data.get("email"), 120)
        message = _text(data.get("message"), 800)
        if len(name) < 2 or not EMAIL_RE.match(email) or len(message) < 5:
            return fail("Please provide a valid name, email address, and comment.")
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
            return fail("Failed to post comment.", 500)

    @app.route("/api/faqs", methods=["GET"])
    def api_faqs():
        try:
            res = (supabase.table("faqs")
                   .select("id,category,question,answer,sort_order")
                   .eq("is_published", True)
                   .order("sort_order").order("id").execute())
            return jsonify({"faqs": res.data or []})
        except Exception:
            return fail("Could not load FAQs.", 500)

    @app.route("/api/contact", methods=["POST"])
    def api_contact():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop: return stop

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
            return fail("Failed to send your inquiry. Please try again later.", 500)

    @app.route("/api/subscribe", methods=["POST"])
    def api_subscribe():
        data = request.get_json(silent=True) or {}
        stop = guard(data)
        if stop: return stop

        email = _line(data.get("email"), 120).lower()
        if not EMAIL_RE.match(email):
            return fail("Please enter a valid email address.")
        try:
            supabase.table("subscribers").upsert({"email": email}, on_conflict="email").execute()
            return jsonify({"ok": True, "message": "Subscribed to newsletter successfully."}), 201
        except Exception:
            return fail("Could not complete subscription.", 500)

    # ------------------------------------------------------------
    # 1. DEDICATED REVIEWS PAGE
    # ------------------------------------------------------------
    @app.route("/admin/reviews", methods=["GET"])
    @admin_required
    def admin_reviews_page():
        rows = supabase.table("reviews").select("*").order("created_at", desc=True).limit(200).execute().data or []
        html = base_template + REVIEWS_HTML
        return render_template_string(html, title="Customer Reviews", active_nav="reviews", reviews=rows)

    @app.route("/admin/reviews/add", methods=["POST"])
    @admin_required
    def admin_add_review():
        if not valid_csrf():
            flash("Invalid session token.", "err")
            return redirect(url_for("admin_reviews_page"))
        try:
            supabase.table("reviews").insert({
                "name": _line(request.form.get("name"), 60),
                "trip": _line(request.form.get("trip"), 60),
                "rating": max(1, min(5, int(request.form.get("rating", 5)))),
                "message": _text(request.form.get("message"), 600),
                "is_approved": True,
            }).execute()
            flash("Customer review published successfully.", "ok")
        except Exception:
            flash("Failed to add review.", "err")
        return redirect(url_for("admin_reviews_page"))

    @app.route("/admin/reviews/<int:item_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_review(item_id):
        if not valid_csrf():
            flash("Invalid session.", "err")
            return redirect(url_for("admin_reviews_page"))
        try:
            row = supabase.table("reviews").select("is_approved").eq("id", item_id).limit(1).execute().data
            if row:
                supabase.table("reviews").update({"is_approved": not row[0]["is_approved"]}).eq("id", item_id).execute()
                flash("Review status updated.", "ok")
        except Exception:
            flash("Unable to update review.", "err")
        return redirect(url_for("admin_reviews_page"))

    @app.route("/admin/reviews/<int:item_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_review(item_id):
        if not valid_csrf():
            flash("Invalid session.", "err")
            return redirect(url_for("admin_reviews_page"))
        try:
            supabase.table("reviews").delete().eq("id", item_id).execute()
            flash("Review removed permanently.", "ok")
        except Exception:
            flash("Unable to delete review.", "err")
        return redirect(url_for("admin_reviews_page"))

    # ------------------------------------------------------------
    # 2. DEDICATED BLOG ARTICLES PAGE
    # ------------------------------------------------------------
    @app.route("/admin/blogs", methods=["GET"])
    @admin_required
    def admin_blogs_page():
        blogs = supabase.table("blogs").select("*").order("created_at", desc=True).limit(200).execute().data or []
        html = base_template + BLOGS_LIST_HTML
        return render_template_string(html, title="Blog Articles", active_nav="blogs", blogs=blogs)

    @app.route("/admin/blogs/new", methods=["GET"])
    @admin_required
    def admin_add_blog_page():
        html = base_template + BLOG_ADD_HTML
        return render_template_string(html, title="Write Article", active_nav="blogs")

    @app.route("/admin/blogs/create", methods=["POST"])
    @admin_required
    def admin_create_blog():
        if not valid_csrf():
            flash("Invalid session token.", "err")
            return redirect(url_for("admin_add_blog_page"))
        try:
            title = _line(request.form.get("title"), 160)
            excerpt = _text(request.form.get("excerpt"), 400)
            content = _text(request.form.get("content"), 25000)

            if not title or not excerpt or not content:
                flash("Title, excerpt, and content are mandatory.", "err")
                return redirect(url_for("admin_add_blog_page"))

            slug = _slug(title)
            if supabase.table("blogs").select("id").eq("slug", slug).limit(1).execute().data:
                slug = f"{slug}-{secrets.token_hex(2)}"

            img_url = None
            f = request.files.get("image")
            if f and f.filename:
                img_url = upload_image(f)

            supabase.table("blogs").insert({
                "slug": slug, "title": title, "excerpt": excerpt, "content": content,
                "category": _line(request.form.get("category"), 60) or "General",
                "author": _line(request.form.get("author"), 60) or "Vishal Car Rental",
                "read_minutes": max(1, int(request.form.get("read_minutes") or 4)),
                "image_url": img_url, "is_published": True,
            }).execute()
            flash("Article published successfully.", "ok")
            return redirect(url_for("admin_blogs_page"))
        except Exception as e:
            flash(f"Failed to publish article: {str(e)}", "err")
            return redirect(url_for("admin_add_blog_page"))

    @app.route("/admin/blogs/<int:item_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_blog(item_id):
        if not valid_csrf(): return redirect(url_for("admin_blogs_page"))
        try:
            row = supabase.table("blogs").select("is_published").eq("id", item_id).limit(1).execute().data
            if row:
                supabase.table("blogs").update({"is_published": not row[0]["is_published"]}).eq("id", item_id).execute()
                flash("Article visibility updated.", "ok")
        except Exception:
            flash("Could not update visibility.", "err")
        return redirect(url_for("admin_blogs_page"))

    @app.route("/admin/blogs/<int:item_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_blog(item_id):
        if not valid_csrf(): return redirect(url_for("admin_blogs_page"))
        try:
            supabase.table("blogs").delete().eq("id", item_id).execute()
            flash("Article deleted.", "ok")
        except Exception:
            flash("Could not delete article.", "err")
        return redirect(url_for("admin_blogs_page"))

    # ------------------------------------------------------------
    # 3. DEDICATED BLOG COMMENTS PAGE
    # ------------------------------------------------------------
    @app.route("/admin/comments", methods=["GET"])
    @admin_required
    def admin_comments_page():
        rows = supabase.table("blog_comments").select("*").order("created_at", desc=True).limit(200).execute().data or []
        html = base_template + COMMENTS_HTML
        return render_template_string(html, title="Blog Comments", active_nav="comments", comments=rows)

    @app.route("/admin/comments/<int:item_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_comment(item_id):
        if not valid_csrf(): return redirect(url_for("admin_comments_page"))
        try:
            row = supabase.table("blog_comments").select("is_approved").eq("id", item_id).limit(1).execute().data
            if row:
                supabase.table("blog_comments").update({"is_approved": not row[0]["is_approved"]}).eq("id", item_id).execute()
                flash("Comment status changed.", "ok")
        except Exception:
            flash("Failed to update comment.", "err")
        return redirect(url_for("admin_comments_page"))

    @app.route("/admin/comments/<int:item_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_comment(item_id):
        if not valid_csrf(): return redirect(url_for("admin_comments_page"))
        try:
            supabase.table("blog_comments").delete().eq("id", item_id).execute()
            flash("Comment deleted.", "ok")
        except Exception:
            flash("Failed to delete comment.", "err")
        return redirect(url_for("admin_comments_page"))

    # ------------------------------------------------------------
    # 4. DEDICATED FAQS PAGE
    # ------------------------------------------------------------
    @app.route("/admin/faqs", methods=["GET"])
    @admin_required
    def admin_faqs_page():
        faqs = supabase.table("faqs").select("*").order("sort_order").order("id").execute().data or []
        html = base_template + FAQS_HTML
        return render_template_string(html, title="FAQs", active_nav="faqs", faqs=faqs)

    @app.route("/admin/faqs/add", methods=["POST"])
    @admin_required
    def admin_add_faq():
        if not valid_csrf(): return redirect(url_for("admin_faqs_page"))
        try:
            supabase.table("faqs").insert({
                "category": _line(request.form.get("category"), 40),
                "question": _line(request.form.get("question"), 250),
                "answer": _text(request.form.get("answer"), 1500),
                "sort_order": int(request.form.get("sort_order") or 0),
                "is_published": True,
            }).execute()
            flash("New FAQ added.", "ok")
        except Exception:
            flash("Failed to add FAQ.", "err")
        return redirect(url_for("admin_faqs_page"))

    @app.route("/admin/faqs/<int:item_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_faq(item_id):
        if not valid_csrf(): return redirect(url_for("admin_faqs_page"))
        try:
            row = supabase.table("faqs").select("is_published").eq("id", item_id).limit(1).execute().data
            if row:
                supabase.table("faqs").update({"is_published": not row[0]["is_published"]}).eq("id", item_id).execute()
                flash("FAQ visibility toggled.", "ok")
        except Exception:
            flash("Could not update FAQ.", "err")
        return redirect(url_for("admin_faqs_page"))

    @app.route("/admin/faqs/<int:item_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_faq(item_id):
        if not valid_csrf(): return redirect(url_for("admin_faqs_page"))
        try:
            supabase.table("faqs").delete().eq("id", item_id).execute()
            flash("FAQ removed.", "ok")
        except Exception:
            flash("Could not delete FAQ.", "err")
        return redirect(url_for("admin_faqs_page"))

    # ------------------------------------------------------------
    # 5. DEDICATED CONTACT INQUIRIES PAGE
    # ------------------------------------------------------------
    @app.route("/admin/messages", methods=["GET"])
    @admin_required
    def admin_messages_page():
        messages = supabase.table("contact_messages").select("*").order("created_at", desc=True).limit(200).execute().data or []
        html = base_template + MESSAGES_HTML
        return render_template_string(html, title="Contact Inquiries", active_nav="messages", messages=messages)

    @app.route("/admin/messages/<int:item_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_message(item_id):
        if not valid_csrf(): return redirect(url_for("admin_messages_page"))
        try:
            row = supabase.table("contact_messages").select("is_read").eq("id", item_id).limit(1).execute().data
            if row:
                supabase.table("contact_messages").update({"is_read": not row[0]["is_read"]}).eq("id", item_id).execute()
                flash("Message marked as read/unread.", "ok")
        except Exception:
            flash("Unable to update inquiry status.", "err")
        return redirect(url_for("admin_messages_page"))

    @app.route("/admin/messages/<int:item_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_message(item_id):
        if not valid_csrf(): return redirect(url_for("admin_messages_page"))
        try:
            supabase.table("contact_messages").delete().eq("id", item_id).execute()
            flash("Message inquiry deleted.", "ok")
        except Exception:
            flash("Could not delete message.", "err")
        return redirect(url_for("admin_messages_page"))

    # ------------------------------------------------------------
    # 6. DEDICATED SUBSCRIBERS PAGE
    # ------------------------------------------------------------
    @app.route("/admin/subscribers", methods=["GET"])
    @admin_required
    def admin_subscribers_page():
        subs = supabase.table("subscribers").select("*").order("created_at", desc=True).limit(300).execute().data or []
        html = base_template + SUBSCRIBERS_HTML
        return render_template_string(html, title="Subscribers", active_nav="subscribers", subscribers=subs)

    @app.route("/admin/subscribers/<int:item_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_subscriber(item_id):
        if not valid_csrf(): return redirect(url_for("admin_subscribers_page"))
        try:
            supabase.table("subscribers").delete().eq("id", item_id).execute()
            flash("Subscriber removed.", "ok")
        except Exception:
            flash("Could not remove subscriber.", "err")
        return redirect(url_for("admin_subscribers_page"))