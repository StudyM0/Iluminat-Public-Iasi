import sqlite3
import requests
from flask import Flask, jsonify, request, render_template_string
from datetime import datetime

app = Flask(__name__)
DB_NAME = "iluminat_public.db"

# ============================================================
# BAZA DE DATE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS masuratori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            senzor TEXT NOT NULL,
            tip TEXT,
            valoare REAL,
            unitate TEXT,
            status TEXT
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM masuratori")
    if cursor.fetchone()[0] == 0:
        date_initiale = [
            ("Stalp_Bld_Independentei_01", "Consum", 145.2, "W", "Activ"),
            ("Stalp_Bld_Independentei_02", "Consum", 0.0,   "W", "Eroare"),
            ("Stalp_Pasaj_Unirii_05",      "Consum", 75.0,  "W", "Mentenanta"),
            ("Stalp_Piata_Unirii_03",      "Consum", 132.5, "W", "Activ"),
            ("Stalp_Str_Lapusneanu_07",    "Consum", 98.0,  "W", "Activ"),
        ]
        cursor.executemany(
            'INSERT INTO masuratori (senzor, tip, valoare, unitate, status) VALUES (?,?,?,?,?)',
            date_initiale
        )
    conn.commit()
    conn.close()

def db_query(query, args=(), fetchall=False, fetchone=False, lastrowid=False):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, args)
    result = None
    if fetchall:  result = [dict(row) for row in cursor.fetchall()]
    if fetchone:
        row = cursor.fetchone()
        result = dict(row) if row else None
    if lastrowid: result = cursor.lastrowid
    conn.commit()
    conn.close()
    return result

# ============================================================
# API EXTERN 1 — Sunrise-Sunset (ora apus/rasarit, Iasi)
# https://sunrise-sunset.org/api  —  GRATUIT, fara cheie API
# ============================================================

def get_sunrise_sunset():
    try:
        # Coordonate Iasi, Romania
        r = requests.get(
            "https://api.sunrise-sunset.org/json",
            params={"lat": 47.1585, "lng": 27.6014, "formatted": 0},
            timeout=5
        )
        data = r.json()["results"]
        sunrise_utc = datetime.fromisoformat(data["sunrise"].replace("Z", "+00:00"))
        sunset_utc  = datetime.fromisoformat(data["sunset"].replace("Z", "+00:00"))

        # Converitm in ora locala Romania (UTC+3 vara / UTC+2 iarna) - simplu +2
        from datetime import timezone, timedelta
        tz_ro = timezone(timedelta(hours=3))
        sunrise_local = sunrise_utc.astimezone(tz_ro).strftime("%H:%M")
        sunset_local  = sunset_utc.astimezone(tz_ro).strftime("%H:%M")

        now = datetime.now(tz=tz_ro)
        is_night = now < sunrise_utc.astimezone(tz_ro) or now > sunset_utc.astimezone(tz_ro)

        return {
            "rasarit": sunrise_local,
            "apus":    sunset_local,
            "este_noapte": is_night,
            "recomandare": "APRINS" if is_night else "STINS"
        }
    except Exception as e:
        return {"eroare": str(e)}

# ============================================================
# API EXTERN 2 — Open-Meteo (vreme curenta, Iasi)
# https://open-meteo.com/  —  GRATUIT, fara cheie API
# ============================================================

def get_weather():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":  47.1585,
                "longitude": 27.6014,
                "current":   "temperature_2m,weathercode,windspeed_10m,relativehumidity_2m",
                "timezone":  "Europe/Bucharest"
            },
            timeout=5
        )
        c = r.json()["current"]
        wcode = c["weathercode"]

        # Cod vreme simplificat
        if wcode == 0:   desc = "Cer senin ☀️"
        elif wcode <= 3: desc = "Partial noros 🌤️"
        elif wcode <= 49: desc = "Ceata / Burnita 🌫️"
        elif wcode <= 67: desc = "Ploaie 🌧️"
        elif wcode <= 77: desc = "Ninsoare ❄️"
        elif wcode <= 82: desc = "Averse 🌦️"
        else:             desc = "Furtuna ⛈️"

        # Vizibilitate redusa => intensitate luminoasa mai mare recomandata
        intensitate = "MAXIMA" if wcode >= 45 else ("NORMALA" if wcode <= 3 else "RIDICATA")

        return {
            "temperatura":    f"{c['temperature_2m']}°C",
            "umiditate":      f"{c['relativehumidity_2m']}%",
            "vant":           f"{c['windspeed_10m']} km/h",
            "descriere":      desc,
            "intensitate_rec": intensitate
        }
    except Exception as e:
        return {"eroare": str(e)}

# ============================================================
# HTML INTERFATA WEB CLIENT
# ============================================================

HTML_INTERFACE = r"""
<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sistem Iluminat Public — Iași</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #060b14;
    --surface:  #0d1b2e;
    --card:     #111f33;
    --border:   #1e3a5a;
    --accent:   #f0c040;
    --accent2:  #38bdf8;
    --danger:   #ef4444;
    --success:  #22c55e;
    --warn:     #f97316;
    --text:     #e2eaf4;
    --muted:    #6b8aaa;
    --font-h:   'Syne', sans-serif;
    --font-m:   'Space Mono', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-m);
    min-height: 100vh;
    padding: 0 0 60px;
  }

  /* ── HEADER ── */
  header {
    background: linear-gradient(135deg, #0a1628 0%, #0d1f3c 100%);
    border-bottom: 1px solid var(--border);
    padding: 22px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
  }
  header h1 {
    font-family: var(--font-h);
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: var(--accent);
  }
  header h1 span { color: var(--accent2); }
  #clock {
    font-size: 0.8rem;
    color: var(--muted);
    letter-spacing: 2px;
  }

  /* ── LAYOUT ── */
  .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

  /* ── GRID API CARDS ── */
  .api-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 32px;
  }
  @media (max-width: 700px) { .api-grid { grid-template-columns: 1fr; } }

  .api-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    position: relative;
    overflow: hidden;
  }
  .api-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
  }
  .api-card.sun::before  { background: linear-gradient(90deg, var(--accent), #fb923c); }
  .api-card.rain::before { background: linear-gradient(90deg, var(--accent2), #818cf8); }

  .api-card .label {
    font-size: 0.65rem;
    letter-spacing: 3px;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .api-card .big {
    font-family: var(--font-h);
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 12px;
  }
  .api-card .row-info {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  .api-card .pill {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.72rem;
    color: var(--text);
  }
  .rec-badge {
    display: inline-block;
    margin-top: 12px;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 1px;
  }
  .rec-APRINS  { background: #f0c04022; color: var(--accent);  border: 1px solid var(--accent); }
  .rec-STINS   { background: #38bdf822; color: var(--accent2); border: 1px solid var(--accent2); }
  .rec-MAXIMA  { background: #ef444422; color: var(--danger);  border: 1px solid var(--danger); }
  .rec-NORMALA { background: #22c55e22; color: var(--success); border: 1px solid var(--success); }
  .rec-RIDICATA{ background: #f9731622; color: var(--warn);    border: 1px solid var(--warn); }

  /* ── STATS BAR ── */
  .stats-bar {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 28px;
  }
  .stat-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 22px;
    flex: 1;
    min-width: 130px;
  }
  .stat-box .s-label { font-size: 0.6rem; letter-spacing: 2px; color: var(--muted); text-transform: uppercase; }
  .stat-box .s-val   { font-family: var(--font-h); font-size: 1.6rem; font-weight: 700; margin-top: 4px; }

  /* ── FORM ── */
  .form-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 28px;
  }
  .form-card h2 {
    font-family: var(--font-h);
    font-size: 1rem;
    font-weight: 700;
    color: var(--accent2);
    margin-bottom: 16px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .form-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: flex-end;
  }
  .form-row input, .form-row select {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    color: var(--text);
    font-family: var(--font-m);
    font-size: 0.8rem;
    outline: none;
    flex: 1;
    min-width: 150px;
  }
  .form-row input:focus, .form-row select:focus {
    border-color: var(--accent2);
  }
  .btn-add {
    background: var(--accent);
    color: #060b14;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-family: var(--font-h);
    font-weight: 700;
    font-size: 0.85rem;
    cursor: pointer;
    transition: opacity 0.2s;
    white-space: nowrap;
  }
  .btn-add:hover { opacity: 0.85; }

  /* ── TABLE ── */
  .table-wrap {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
  }
  .table-wrap h2 {
    font-family: var(--font-h);
    font-size: 1rem;
    font-weight: 700;
    color: var(--accent2);
    padding: 20px 24px 0;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
  thead th {
    background: var(--surface);
    color: var(--muted);
    font-size: 0.62rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 12px 18px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }
  tbody tr { border-bottom: 1px solid #1a2d45; transition: background 0.15s; }
  tbody tr:hover { background: #0f1e32; }
  tbody td { padding: 13px 18px; }
  .senzor-name { font-weight: 700; color: var(--text); }
  .valoare     { color: var(--accent); font-weight: 700; }

  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .badge-Activ      { background: #22c55e22; color: var(--success); border: 1px solid var(--success); }
  .badge-Eroare     { background: #ef444422; color: var(--danger);  border: 1px solid var(--danger); }
  .badge-Mentenanta { background: #f9731622; color: var(--warn);    border: 1px solid var(--warn); }

  .btn-del {
    background: transparent;
    border: 1px solid var(--danger);
    color: var(--danger);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 0.7rem;
    cursor: pointer;
    font-family: var(--font-m);
    transition: background 0.15s;
  }
  .btn-del:hover { background: #ef444422; }

  /* ── LOADING / ERROR ── */
  .spinner {
    border: 2px solid var(--border);
    border-top-color: var(--accent2);
    border-radius: 50%;
    width: 18px; height: 18px;
    animation: spin 0.7s linear infinite;
    display: inline-block;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .api-src {
    font-size: 0.6rem;
    color: var(--muted);
    margin-top: 12px;
    letter-spacing: 1px;
  }
</style>
</head>
<body>

<header>
  <h1>🏙️ Sistem <span>Iluminat Public</span> — Iași</h1>
  <div id="clock">--:--:--</div>
</header>

<div class="container">

  <!-- ── API CARDS ── -->
  <div class="api-grid">

    <div class="api-card sun" id="card-sun">
      <div class="label">📡 API 1 — Sunrise-Sunset.org</div>
      <div class="big" id="sun-apus"><span class="spinner"></span></div>
      <div class="row-info">
        <span class="pill">🌅 Răsărit: <span id="sun-rasarit">—</span></span>
        <span class="pill">🌇 Apus: <span id="sun-apus2">—</span></span>
      </div>
      <div id="sun-rec"></div>
      <div class="api-src">Sursa: api.sunrise-sunset.org · Lat 47.1585, Lng 27.6014</div>
    </div>

    <div class="api-card rain" id="card-weather">
      <div class="label">📡 API 2 — Open-Meteo.com</div>
      <div class="big" id="w-temp"><span class="spinner"></span></div>
      <div class="row-info">
        <span class="pill">💧 Umiditate: <span id="w-hum">—</span></span>
        <span class="pill">💨 Vânt: <span id="w-wind">—</span></span>
        <span class="pill" id="w-desc">—</span>
      </div>
      <div id="w-rec"></div>
      <div class="api-src">Sursa: api.open-meteo.com · Lat 47.1585, Lng 27.6014</div>
    </div>

  </div>

  <!-- ── STATISTICI ── -->
  <div class="stats-bar" id="stats-bar">
    <div class="stat-box"><div class="s-label">Total stâlpi</div><div class="s-val" id="s-total">—</div></div>
    <div class="stat-box"><div class="s-label">Activi</div><div class="s-val" style="color:var(--success)" id="s-activ">—</div></div>
    <div class="stat-box"><div class="s-label">Eroare</div><div class="s-val" style="color:var(--danger)" id="s-eroare">—</div></div>
    <div class="stat-box"><div class="s-label">Mentenanță</div><div class="s-val" style="color:var(--warn)" id="s-ment">—</div></div>
    <div class="stat-box"><div class="s-label">Consum total</div><div class="s-val" style="color:var(--accent)" id="s-consum">— W</div></div>
  </div>

  <!-- ── FORM ── -->
  <div class="form-card">
    <h2>➕ Adaugă înregistrare</h2>
    <div class="form-row">
      <input id="inp-senzor" placeholder="ID Stâlp (ex: Stalp_Str_X_01)">
      <input id="inp-valoare" type="number" placeholder="Consum (W)" min="0">
      <select id="inp-status">
        <option value="Activ">Funcționare Normală</option>
        <option value="Eroare">Eroare</option>
        <option value="Mentenanta">Mentenanță</option>
      </select>
      <button class="btn-add" onclick="addItem()">Înregistrează</button>
    </div>
  </div>

  <!-- ── TABEL ── -->
  <div class="table-wrap">
    <h2>📋 Măsurători înregistrate</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Locație / Senzor</th>
          <th>Tip</th>
          <th>Consum</th>
          <th>Unitate</th>
          <th>Status</th>
          <th>Acțiuni</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

</div>

<script>
// ── CEAS ──
function updateClock() {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('ro-RO', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── API 1: Sunrise-Sunset ──
async function loadSun() {
  const res = await fetch('/api/extern/soare');
  const d   = await res.json();
  if (d.eroare) { document.getElementById('sun-apus').textContent = 'Eroare API'; return; }
  document.getElementById('sun-apus').textContent  = d.apus;
  document.getElementById('sun-rasarit').textContent = d.rasarit;
  document.getElementById('sun-apus2').textContent   = d.apus;
  const recEl = document.getElementById('sun-rec');
  recEl.innerHTML = `<div class="rec-badge rec-${d.recomandare}">
    Recomandare sistem: ${d.recomandare}
    ${d.este_noapte ? '🌙 (este noapte)' : '☀️ (este zi)'}
  </div>`;
}

// ── API 2: Open-Meteo ──
async function loadWeather() {
  const res = await fetch('/api/extern/vreme');
  const d   = await res.json();
  if (d.eroare) { document.getElementById('w-temp').textContent = 'Eroare API'; return; }
  document.getElementById('w-temp').textContent  = d.temperatura;
  document.getElementById('w-hum').textContent   = d.umiditate;
  document.getElementById('w-wind').textContent  = d.vant;
  document.getElementById('w-desc').textContent  = d.descriere;
  const recEl = document.getElementById('w-rec');
  recEl.innerHTML = `<div class="rec-badge rec-${d.intensitate_rec}">
    Intensitate luminoasă recomandată: ${d.intensitate_rec}
  </div>`;
}

// ── TABEL + STATISTICI ──
async function loadDate() {
  const res  = await fetch('/api/masuratori');
  const data = await res.json();
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  data.forEach(m => {
    tbody.innerHTML += `
      <tr>
        <td style="color:var(--muted)">#${m.id}</td>
        <td class="senzor-name">${m.senzor}</td>
        <td style="color:var(--muted)">${m.tip || '—'}</td>
        <td class="valoare">${m.valoare} </td>
        <td style="color:var(--muted)">${m.unitate || 'W'}</td>
        <td><span class="badge badge-${m.status}">${m.status}</span></td>
        <td><button class="btn-del" onclick="deleteItem(${m.id})">Șterge</button></td>
      </tr>`;
  });
  // Statistici
  document.getElementById('s-total').textContent  = data.length;
  document.getElementById('s-activ').textContent  = data.filter(m => m.status === 'Activ').length;
  document.getElementById('s-eroare').textContent = data.filter(m => m.status === 'Eroare').length;
  document.getElementById('s-ment').textContent   = data.filter(m => m.status === 'Mentenanta').length;
  const total = data.reduce((acc, m) => acc + (m.valoare || 0), 0);
  document.getElementById('s-consum').textContent = total.toFixed(1) + ' W';
}

async function addItem() {
  const s  = document.getElementById('inp-senzor').value.trim();
  const v  = document.getElementById('inp-valoare').value;
  const st = document.getElementById('inp-status').value;
  if (!s || !v) return alert('Completează toate câmpurile!');
  await fetch('/api/masuratori', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ senzor: s, valoare: parseFloat(v), status: st })
  });
  document.getElementById('inp-senzor').value  = '';
  document.getElementById('inp-valoare').value = '';
  loadDate();
}

async function deleteItem(id) {
  if (!confirm('Ștergi înregistrarea #' + id + '?')) return;
  await fetch(`/api/masuratori/${id}`, { method: 'DELETE' });
  loadDate();
}

// ── INIT ──
loadSun();
loadWeather();
loadDate();
</script>
</body>
</html>
"""

# ============================================================
# RUTE API INTERN (REST API propriu)
# ============================================================

@app.route('/')
def index():
    return render_template_string(HTML_INTERFACE)

@app.route('/api/masuratori', methods=['GET'])
def get_all():
    rows = db_query("SELECT * FROM masuratori", fetchall=True)
    return jsonify(rows), 200

@app.route('/api/masuratori/<int:id_item>', methods=['GET'])
def get_one(id_item):
    item = db_query("SELECT * FROM masuratori WHERE id = ?", (id_item,), fetchone=True)
    if not item:
        return jsonify({"eroare": "Nu exista"}), 404
    return jsonify(item), 200

@app.route('/api/masuratori', methods=['POST'])
def add_item():
    data = request.json
    new_id = db_query(
        "INSERT INTO masuratori (senzor, tip, valoare, unitate, status) VALUES (?,?,?,?,?)",
        (data.get('senzor'), "Consum", data.get('valoare'), "W", data.get('status')),
        lastrowid=True
    )
    return jsonify({"status": "Succes", "id": new_id}), 201

@app.route('/api/masuratori/<int:id_item>', methods=['PUT'])
def update_item(id_item):
    data = request.json
    db_query(
        "UPDATE masuratori SET valoare = ?, status = ? WHERE id = ?",
        (data.get('valoare'), data.get('status'), id_item)
    )
    return jsonify({"status": "Actualizat"}), 200

@app.route('/api/masuratori/<int:id_item>', methods=['DELETE'])
def delete_item(id_item):
    db_query("DELETE FROM masuratori WHERE id = ?", (id_item,))
    return jsonify({"rezultat": "Sters din DB"}), 200

# ============================================================
# RUTE PENTRU API-URI EXTERNE (proxy catre servicii publice)
# ============================================================

@app.route('/api/extern/soare', methods=['GET'])
def extern_soare():
    """
    API EXTERN 1: Sunrise-Sunset.org
    Returneaza ora rasaritului/apusului pentru Iasi
    si recomandarea de aprindere a iluminatului public.
    """
    data = get_sunrise_sunset()
    return jsonify(data), 200

@app.route('/api/extern/vreme', methods=['GET'])
def extern_vreme():
    """
    API EXTERN 2: Open-Meteo.com
    Returneaza conditiile meteo curente pentru Iasi
    si recomandarea de intensitate a iluminatului.
    """
    data = get_weather()
    return jsonify(data), 200

@app.route('/api/extern/dashboard', methods=['GET'])
def extern_dashboard():
    """Agregat: ambele API-uri externe intr-un singur apel."""
    return jsonify({
        "soare":  get_sunrise_sunset(),
        "vreme":  get_weather(),
        "surse":  ["api.sunrise-sunset.org", "api.open-meteo.com"]
    }), 200

# ============================================================

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
