"""
admin_templates.py
All admin HTML lives here. app.py loads these into Jinja via a DictLoader,
so every page can use {% extends "base.html" %} properly.
"""

STYLES = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f4f6f8; --surface:#ffffff; --text:#12202f; --muted:#64748b; --line:#e3e8ee;
  --side:#0f1b2d; --side-text:#b8c4d6; --brand:#0e9f8e; --brand-dark:#0a7c6f;
  --ok:#15803d; --ok-bg:#dcfce7; --err:#b91c1c; --err-bg:#fee2e2; --warn:#b45309; --warn-bg:#fef3c7;
  --shadow:0 1px 2px rgba(18,32,47,.06),0 6px 20px rgba(18,32,47,.05);
}
@media (prefers-color-scheme: dark){
  :root{--bg:#0b1320;--surface:#121e30;--text:#e6edf6;--muted:#93a3b8;--line:#22314a;--side:#08101c;
        --ok-bg:#12351f;--err-bg:#3a1a1d;--warn-bg:#3a2e10;--ok:#4ade80;--err:#f87171;--warn:#fbbf24}
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:"Plus Jakarta Sans",system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:15px;line-height:1.5}
a{color:var(--brand-dark);text-decoration:none}
h1{font-size:26px;margin:0;letter-spacing:-.02em}
h2{font-size:17px;margin:0 0 4px}
:focus-visible{outline:2px solid var(--brand);outline-offset:2px}

/* layout */
.sidebar{position:fixed;inset:0 auto 0 0;width:250px;background:var(--side);color:var(--side-text);display:flex;flex-direction:column;padding:20px 14px;z-index:30;transition:transform .2s}
.brand{display:flex;align-items:center;gap:12px;padding:4px 10px 22px}
.logo{width:38px;height:38px;border-radius:10px;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:700;font-size:18px}
.brand b{display:block;color:#fff;font-size:16px;line-height:1.1}
.brand small{color:var(--side-text);font-size:12px}
.sidebar nav{display:flex;flex-direction:column;gap:2px;flex:1;overflow-y:auto}
.sidebar nav a{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:10px;color:var(--side-text);font-weight:500}
.sidebar nav a:hover{background:rgba(255,255,255,.06);color:#fff}
.sidebar nav a.active{background:var(--brand);color:#fff}
.sidebar nav .ico{width:22px;text-align:center}
.side-foot{border-top:1px solid rgba(255,255,255,.1);padding-top:14px}
.side-foot button{width:100%;background:rgba(255,255,255,.08);color:#fff}
main{margin-left:250px;min-height:100vh}
.topbar{display:flex;align-items:center;gap:12px;padding:14px 28px;border-bottom:1px solid var(--line);background:var(--surface);position:sticky;top:0;z-index:10}
.topbar .grow{flex:1;font-weight:600}
.topbar .user{color:var(--muted);font-size:13px}
.burger{display:none;cursor:pointer;font-size:22px;line-height:1}
.scrim{display:none}
.content{padding:28px;max-width:1240px;margin:0 auto}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:22px}
.page-head p{margin:4px 0 0;color:var(--muted)}

/* components */
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:22px;box-shadow:var(--shadow);margin-bottom:22px}
.card.flush{padding:0;overflow:hidden}
.btn,button{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:10px 16px;border:0;border-radius:9px;background:var(--brand);color:#fff;font:inherit;font-weight:600;cursor:pointer;transition:background .15s}
.btn:hover,button:hover{background:var(--brand-dark)}
.btn.ghost{background:transparent;color:var(--text);border:1px solid var(--line)}
.btn.ghost:hover{background:var(--bg)}
.btn.soft{background:var(--bg);color:var(--text);border:1px solid var(--line)}
.btn.danger,button.danger{background:var(--err-bg);color:var(--err)}
.btn.danger:hover,button.danger:hover{background:var(--err);color:#fff}
.btn.sm,button.sm{padding:6px 11px;font-size:13px}
.actions{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.actions form{margin:0}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600}
.badge.on{background:var(--ok-bg);color:var(--ok)}
.badge.off{background:var(--warn-bg);color:var(--warn)}
.muted{color:var(--muted);font-size:13px}
.toasts{display:grid;gap:10px;margin-bottom:20px}
.toast{padding:12px 16px;border-radius:10px;font-weight:500}
.toast.ok{background:var(--ok-bg);color:var(--ok)}
.toast.err{background:var(--err-bg);color:var(--err)}

/* tables */
.toolbar{display:flex;gap:12px;align-items:center;padding:16px 20px;border-bottom:1px solid var(--line)}
.search{flex:1;max-width:340px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;background:var(--bg);color:var(--text);font:inherit}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:720px}
th{font-size:12.5px;text-align:left;color:var(--muted);font-weight:600;padding:12px 20px;background:var(--bg);border-bottom:1px solid var(--line)}
td{padding:14px 20px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:0}
tbody tr:hover{background:color-mix(in srgb,var(--brand) 4%,transparent)}
.thumb{width:76px;height:52px;object-fit:cover;border-radius:8px;border:1px solid var(--line);display:block}
.empty{text-align:center;padding:48px 20px;color:var(--muted)}
.clamp{max-width:340px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

/* forms */
.form-section{margin-bottom:26px}
.form-section>h2{padding-bottom:12px;margin-bottom:16px;border-bottom:1px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.field{min-width:0}
.field.full{grid-column:1/-1}
label{display:block;font-size:13.5px;font-weight:600;margin-bottom:6px}
label em{color:var(--err);font-style:normal}
input,select,textarea{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--text);font:inherit}
input:focus,select:focus,textarea:focus{border-color:var(--brand);outline:0;box-shadow:0 0 0 3px color-mix(in srgb,var(--brand) 22%,transparent)}
input[type=file]{padding:8px;background:var(--bg)}
textarea{resize:vertical}
.help{font-size:12.5px;color:var(--muted);margin:6px 0 0}
.switch{display:flex;align-items:center;gap:12px;cursor:pointer;margin:0}
.switch input{position:absolute;opacity:0;width:0;height:0}
.slider{width:42px;height:24px;border-radius:99px;background:var(--line);position:relative;transition:background .15s;flex:none}
.slider:after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;transition:transform .15s}
.switch input:checked+.slider{background:var(--brand)}
.switch input:checked+.slider:after{transform:translateX(18px)}
.switch input:focus-visible+.slider{outline:2px solid var(--brand);outline-offset:2px}
.form-bar{display:flex;gap:10px;justify-content:flex-end;position:sticky;bottom:0;background:var(--surface);padding:16px 0 0;border-top:1px solid var(--line);margin-top:8px}
.thumb-lg{width:180px;height:120px;object-fit:cover;border-radius:10px;border:1px solid var(--line);margin-bottom:10px;display:block}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;margin-bottom:12px}
.gallery label{margin:0;font-weight:500;font-size:12.5px;cursor:pointer}
.gallery img{width:100%;height:90px;object-fit:cover;border-radius:8px;border:1px solid var(--line);display:block;margin-bottom:6px}
.gallery input{width:auto;margin-right:6px}

/* dashboard */
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px;margin-bottom:26px}
.stat{display:block;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px 20px;box-shadow:var(--shadow);color:var(--text)}
.stat:hover{border-color:var(--brand)}
.stat .n{font-size:32px;font-weight:700;letter-spacing:-.03em;line-height:1.1}
.stat .l{color:var(--muted);font-size:13.5px;margin-top:4px}
.stat.alert{border-color:var(--warn)}
.stat.alert .n{color:var(--warn)}

/* login */
.login-wrap{min-height:100vh;display:grid;place-items:center;padding:20px}
.login-card{width:100%;max-width:400px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:32px;box-shadow:var(--shadow)}
.login-card .logo{margin-bottom:18px}
.login-card button{width:100%;margin-top:20px;padding:12px}
.login-card label{margin-top:16px}

@media (max-width: 900px){
  .sidebar{transform:translateX(-100%)}
  #nav-toggle:checked ~ .sidebar{transform:none}
  #nav-toggle:checked ~ .scrim{display:block;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:20}
  main{margin-left:0}
  .burger{display:block}
  .topbar,.content{padding-left:16px;padding-right:16px}
  .grid,.grid.three{grid-template-columns:1fr}
  .field.full{grid-column:auto}
}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>
"""

BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - Vishal Car Rental Admin</title>
{% include "styles.html" %}
</head>
<body>
<input type="checkbox" id="nav-toggle" hidden>
<aside class="sidebar">
  <div class="brand"><span class="logo">K</span><div><b>Vishal Car Rental</b><small>Admin panel</small></div></div>
  <nav>
    {% for n in nav %}
      <a href="{{ url_for(n.endpoint) }}" class="{{ 'active' if active_nav == n.key }}">
        <span class="ico">{{ n.icon }}</span>{{ n.label }}
      </a>
    {% endfor %}
  </nav>
  <div class="side-foot">
    <form method="POST" action="{{ url_for('admin_logout') }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit">Log out</button>
    </form>
  </div>
</aside>
<label for="nav-toggle" class="scrim" aria-label="Close menu"></label>
<main>
  <div class="topbar">
    <label for="nav-toggle" class="burger" aria-label="Open menu">&#9776;</label>
    <span class="grow">{{ title }}</span>
    <span class="user">Signed in as {{ session.get('admin_username', 'Admin') }}</span>
  </div>
  <div class="content">
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% if msgs %}<div class="toasts">
        {% for cat, m in msgs %}<div class="toast {{ 'err' if cat == 'err' else 'ok' }}" role="status">{{ m }}</div>{% endfor %}
      </div>{% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
</main>
<script>
function filterRows(q){
  q = q.toLowerCase();
  document.querySelectorAll('#tbl tbody tr[data-row]').forEach(function(tr){
    tr.style.display = tr.textContent.toLowerCase().indexOf(q) > -1 ? '' : 'none';
  });
}
</script>
</body>
</html>
"""

LOGIN = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in - Vishal Car Rental Kota  Admin</title>
{% include "styles.html" %}
</head>
<body>
<div class="login-wrap">
  <div class="login-card">
    <span class="logo">K</span>
    <h1>Welcome back</h1>
    <p class="muted">Sign in to manage cars, content and enquiries.</p>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat, m in msgs %}<div class="toast err" role="alert" style="margin-top:14px">{{ m }}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label for="username">Username</label>
      <input id="username" type="text" name="username" required autocomplete="username" autofocus>
      <label for="password">Password</label>
      <input id="password" type="password" name="password" required autocomplete="current-password">
      <button type="submit">Sign in</button>
    </form>
  </div>
</div>
</body>
</html>
"""

MACROS = """
{% macro field(f, v) %}
{% set val = v.get(f.name) %}
{% if f.type == 'bool' %}
  <div class="field full">
    <label class="switch">
      <input type="checkbox" name="{{ f.name }}" {{ 'checked' if val }}>
      <span class="slider"></span><span>{{ f.label }}</span>
    </label>
    {% if f.help %}<p class="help">{{ f.help }}</p>{% endif %}
  </div>
{% else %}
  <div class="field {{ 'full' if f.full }}">
    <label for="f_{{ f.name }}">{{ f.label }}{% if f.required %} <em>*</em>{% endif %}</label>
    {% if f.type == 'textarea' %}
      <textarea id="f_{{ f.name }}" name="{{ f.name }}" rows="{{ f.rows or 4 }}" placeholder="{{ f.placeholder or '' }}" {{ 'required' if f.required }}>{{ val if val is not none else '' }}</textarea>
    {% elif f.type == 'select' %}
      <select id="f_{{ f.name }}" name="{{ f.name }}" {{ 'required' if f.required }}>
        {% if not f.required %}<option value="">Select</option>{% endif %}
        {% for o in f.options %}
          <option value="{{ o[0] }}" {{ 'selected' if (val|string) == (o[0]|string) }}>{{ o[1] }}</option>
        {% endfor %}
      </select>
    {% elif f.type == 'image' %}
      {% set img = v.get(f.column or f.name) %}
      {% if img %}<img class="thumb-lg" src="{{ img }}" alt="Current image">{% endif %}
      <input id="f_{{ f.name }}" type="file" name="{{ f.name }}" accept=".jpg,.jpeg,.png,.webp">
    {% else %}
      <input id="f_{{ f.name }}" type="{{ f.type }}" name="{{ f.name }}"
             value="{{ val if val is not none else '' }}" placeholder="{{ f.placeholder or '' }}"
             {% if f.min is defined %}min="{{ f.min }}"{% endif %}
             {% if f.max is defined and f.type == 'number' %}max="{{ f.max }}"{% endif %}
             {% if f.step %}step="{{ f.step }}"{% endif %}
             {{ 'required' if f.required }}>
    {% endif %}
    {% if f.help %}<p class="help">{{ f.help }}</p>{% endif %}
  </div>
{% endif %}
{% endmacro %}
"""

DASHBOARD = """{% extends "base.html" %}
{% block content %}
<div class="page-head">
  <div><h1>Dashboard</h1><p>A quick look at your business today.</p></div>
  <a class="btn" href="{{ url_for('admin_cars_new') }}">Add a car</a>
</div>
<div class="stats">
  {% for s in stats %}
    <a class="stat {{ 'alert' if s.alert and s.value }}" href="{{ url_for(s.endpoint) }}">
      <div class="n">{{ s.value }}</div>
      <div class="l">{{ s.label }}</div>
    </a>
  {% endfor %}
</div>
{% endblock %}
"""

CARS_LIST = """{% extends "base.html" %}
{% block content %}
<div class="page-head">
  <div><h1>Cars</h1><p>Your rental fleet. Edit details, change availability or remove cars.</p></div>
  <a class="btn" href="{{ url_for('admin_cars_new') }}">Add a car</a>
</div>
<div class="card flush">
  <div class="toolbar">
    <input class="search" placeholder="Search cars" oninput="filterRows(this.value)" aria-label="Search cars">
    <span class="muted">{{ cars|length }} total</span>
  </div>
  <div class="table-wrap">
  <table id="tbl">
    <thead><tr><th>Photo</th><th>Car</th><th>Price / day</th><th>Status</th><th>Gallery</th><th>Actions</th></tr></thead>
    <tbody>
    {% for car in cars %}
      {% set img = car.get('main_image') or car.get('image_url') %}
      <tr data-row>
        <td>{% if img %}<img class="thumb" src="{{ img }}" alt="">{% else %}<span class="muted">No photo</span>{% endif %}</td>
        <td><strong>{{ car.get('name') or 'Unnamed car' }}</strong><br>
            <span class="muted">{{ car.get('brand') or '' }} {{ car.get('year') or '' }}</span></td>
        <td>&#8377;{{ car.get('price') }}</td>
        <td><span class="badge {{ 'on' if car.get('is_available') else 'off' }}">{{ 'Available' if car.get('is_available') else 'Unavailable' }}</span></td>
        <td>{{ (car.get('gallery_images') or [])|length }} photos</td>
        <td><div class="actions">
          <a class="btn soft sm" href="{{ url_for('admin_cars_edit', item_id=car.id) }}">Edit</a>
          <form method="POST" action="{{ url_for('admin_cars_toggle', item_id=car.id) }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="btn ghost sm" type="submit">{{ 'Mark unavailable' if car.get('is_available') else 'Mark available' }}</button>
          </form>
          <form method="POST" action="{{ url_for('admin_cars_delete', item_id=car.id) }}" onsubmit="return confirm('Delete this car and its photos? This cannot be undone.')">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="danger sm" type="submit">Delete</button>
          </form>
        </div></td>
      </tr>
    {% else %}
      <tr><td colspan="6" class="empty">No cars yet. Add your first car to get started.</td></tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
{% endblock %}
"""

CAR_FORM = """{% extends "base.html" %}
{% from "macros.html" import field %}
{% block content %}
<div class="page-head">
  <div><h1>{{ 'Edit car' if car_id else 'Add a car' }}</h1>
       <p>{{ 'Update details and photos for this car.' if car_id else 'Fill in the details and upload photos.' }}</p></div>
  <a class="btn ghost" href="{{ url_for('admin_cars') }}">Back to cars</a>
</div>
<form method="POST" enctype="multipart/form-data" class="card">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

  {% for section_title, fields in sections %}
  <div class="form-section">
    <h2>{{ section_title }}</h2>
    <div class="grid">
      {% for f in fields %}{{ field(f, values) }}{% endfor %}
    </div>
  </div>
  {% endfor %}

  <div class="form-section">
    <h2>Photos</h2>
    <div class="grid">
      <div class="field full">
        <label for="main_image">Main photo {% if not values.get('main_image') %}<em>*</em>{% endif %}</label>
        {% if values.get('main_image') %}<img class="thumb-lg" src="{{ values.get('main_image') }}" alt="Current main photo">{% endif %}
        <input id="main_image" type="file" name="main_image" accept=".jpg,.jpeg,.png,.webp" {{ 'required' if not values.get('main_image') }}>
        <p class="help">JPG, PNG or WEBP, up to 8 MB. {% if car_id %}Leave empty to keep the current photo.{% endif %}</p>
      </div>
      <div class="field full">
        <label>Gallery photos</label>
        {% if values.get('gallery_images') %}
          <div class="gallery">
            {% for url in values.get('gallery_images') %}
              <label><img src="{{ url }}" alt=""><input type="checkbox" name="remove_gallery" value="{{ url }}">Remove</label>
            {% endfor %}
          </div>
        {% endif %}
        <input type="file" name="gallery_images" multiple accept=".jpg,.jpeg,.png,.webp">
        <p class="help">Up to {{ max_gallery }} photos in total. New uploads are added to the existing gallery.</p>
      </div>
      <div class="field full">
        <label class="switch">
          <input type="checkbox" name="is_available" {{ 'checked' if values.get('is_available') }}>
          <span class="slider"></span><span>Available for rent</span>
        </label>
      </div>
    </div>
  </div>

  <div class="form-bar">
    <a class="btn ghost" href="{{ url_for('admin_cars') }}">Cancel</a>
    <button type="submit">{{ 'Save changes' if car_id else 'Add car' }}</button>
  </div>
</form>
{% endblock %}
"""

LIST = """{% extends "base.html" %}
{% block content %}
<div class="page-head">
  <div><h1>{{ res.title }}</h1><p>{{ res.subtitle }}</p></div>
  {% if res.can_create %}
    <a class="btn" href="{{ url_for('admin_' ~ key ~ '_new') }}">Add {{ res.singular }}</a>
  {% endif %}
</div>
<div class="card flush">
  <div class="toolbar">
    <input class="search" placeholder="Search {{ res.title|lower }}" oninput="filterRows(this.value)" aria-label="Search">
    <span class="muted">{{ rows|length }} total</span>
  </div>
  <div class="table-wrap">
  <table id="tbl">
    <thead><tr>
      {% for c in res.columns %}<th>{{ c[0] }}</th>{% endfor %}
      <th>Actions</th>
    </tr></thead>
    <tbody>
    {% for r in rows %}
      <tr data-row>
        {% for label, k, kind in res.columns %}
          <td>
          {% if kind == 'strong' %}<strong>{{ r.get(k) or '-' }}</strong>
          {% elif kind == 'clamp' %}<div class="clamp">{{ r.get(k) or '-' }}</div>
          {% elif kind == 'image' %}{% if r.get(k) %}<img class="thumb" src="{{ r.get(k) }}" alt="">{% else %}-{% endif %}
          {% elif kind == 'date' %}{{ (r.get(k) or '')[:10] or '-' }}
          {% elif kind == 'rating' %}{{ r.get(k) }} / 5
          {% elif kind == 'slug' %}<strong>{{ r.get('title') }}</strong><br><span class="muted">/blogs/{{ r.get(k) }}</span>
          {% elif kind == 'badge' %}
            <span class="badge {{ 'on' if r.get(res.toggle.field) else 'off' }}">{{ res.toggle.on if r.get(res.toggle.field) else res.toggle.off }}</span>
          {% else %}{{ r.get(k) if r.get(k) is not none and r.get(k) != '' else '-' }}
          {% endif %}
          </td>
        {% endfor %}
        <td><div class="actions">
          <a class="btn soft sm" href="{{ url_for('admin_' ~ key ~ '_edit', item_id=r.id) }}">Edit</a>
          {% if res.toggle %}
          <form method="POST" action="{{ url_for('admin_' ~ key ~ '_toggle', item_id=r.id) }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="btn ghost sm" type="submit">{{ res.toggle.off_action if r.get(res.toggle.field) else res.toggle.on_action }}</button>
          </form>
          {% endif %}
          <form method="POST" action="{{ url_for('admin_' ~ key ~ '_delete', item_id=r.id) }}" onsubmit="return confirm('Delete this {{ res.singular|lower }}? This cannot be undone.')">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="danger sm" type="submit">Delete</button>
          </form>
        </div></td>
      </tr>
    {% else %}
      <tr><td colspan="{{ res.columns|length + 1 }}" class="empty">{{ res.empty }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
{% endblock %}
"""

FORM = """{% extends "base.html" %}
{% from "macros.html" import field %}
{% block content %}
<div class="page-head">
  <div><h1>{{ ('Edit ' if item_id else 'Add ') ~ res.singular|lower }}</h1><p>{{ res.subtitle }}</p></div>
  <a class="btn ghost" href="{{ url_for('admin_' ~ key) }}">Back to {{ res.title|lower }}</a>
</div>
<form method="POST" enctype="multipart/form-data" class="card">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <div class="grid">
    {% for f in res.fields %}{{ field(f, values) }}{% endfor %}
  </div>
  <div class="form-bar">
    <a class="btn ghost" href="{{ url_for('admin_' ~ key) }}">Cancel</a>
    <button type="submit">{{ 'Save changes' if item_id else 'Add ' ~ res.singular|lower }}</button>
  </div>
</form>
{% endblock %}
"""

TEMPLATES = {
    "styles.html": STYLES,
    "base.html": BASE,
    "login.html": LOGIN,
    "macros.html": MACROS,
    "dashboard.html": DASHBOARD,
    "cars_list.html": CARS_LIST,
    "car_form.html": CAR_FORM,
    "list.html": LIST,
    "form.html": FORM,
}