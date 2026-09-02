# app.py
# ORDIDSOLARCALC - Application Streamlit pour gestion de projets de solarisation (Maroua)
# Usage: streamlit run app.py
import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import io
import time
import random
from datetime import datetime

# ---------------------------
# Configuration & Constants
# ---------------------------
DB_PATH = "ordidsolar.db"
UPLOAD_DIR = "uploads"
MAX_UPLOAD_MB = 10
SOLAR_GREEN = "#00D26A"
ORANGE_ACCENT = "#FF8A00"
QUARTIERS = ["Djarengol", "Domayo", "Kakataré", "Dougoï", "Pitoaré", "Palar"]
STATUSES = ["Nouveau", "En cours", "Validé", "Rejeté"]

# Demo users: emails and plaintext passwords (only for demo). Passwords hashed with sha256.
DEMO_USERS = {
    "admin@ordidsolarcalc.cm": {"password": "Admin2026!", "role": "admin"},
    "gestionnaire@ordidsolarcalc.cm": {"password": "Gest2026!", "role": "gestionnaire"},
    "agent@ordidsolarcalc.cm": {"password": "Agent2026!", "role": "agent"},
}

# ---------------------------
# Utilities
# ---------------------------
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            quartier TEXT NOT NULL,
            puissance_kwc REAL NOT NULL,
            statut TEXT NOT NULL,
            battery_autonomy_hours REAL,
            lan_available INTEGER,
            filename TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def insert_demo_data(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM dossiers")
    if c.fetchone()[0] == 0:
        now = datetime.utcnow().isoformat()
        sample = [
            ("Centre Solaire A", "Djarengol", 3.5, "Nouveau", 24, 1, None, now),
            ("Ecole B", "Domayo", 5.0, "En cours", 36, 1, None, now),
            ("Infirmerie C", "Kakataré", 2.2, "Validé", 12, 0, None, now),
        ]
        c.executemany("""
            INSERT INTO dossiers (client_name, quartier, puissance_kwc, statut, battery_autonomy_hours, lan_available, filename, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sample)
        conn.commit()

# ---------------------------
# Authentication
# ---------------------------
def make_user_store():
    store = {}
    for email, info in DEMO_USERS.items():
        store[email] = {"pw_hash": hash_password(info["password"]), "role": info["role"]}
    return store

USER_STORE = make_user_store()

def authenticate(username: str, password: str):
    user = USER_STORE.get(username)
    if not user:
        return False, None
    if hash_password(password) == user["pw_hash"]:
        return True, user["role"]
    return False, None

# ---------------------------
# App UI Helpers & CSS
# ---------------------------
st.set_page_config(page_title="ORDIDSOLARCALC", layout="wide", initial_sidebar_state="auto")

def inject_css():
    st.markdown(f"""
    <style>
    /* Dark background and text */
    .stApp {{
        background-color: #0e1117;
        color: #E6EDF3;
    }}
    /* Headings */
    h1, h2, h3, .streamlit-expanderHeader {{
        color: #E6EDF3;
    }}
    /* Metrics styling */
    .stMetricValue {{
        font-size: 24px !important;
        color: {SOLAR_GREEN} !important;
    }}
    .stMetricLabel {{
        font-size: 14px !important;
        color: #CFEFE0 !important;
    }}
    /* Card like container for content */
    .card {{
        background-color: #0b0f14;
        padding: 18px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.6);
        border: 1px solid rgba(255,255,255,0.03);
    }}
    /* Buttons accent */
    .stButton>button {{
        background: linear-gradient(90deg, {SOLAR_GREEN}, {ORANGE_ACCENT}) !important;
        color: #0b0f14;
        font-weight: 600;
    }}
    /* File uploader */
    .stFileUploader>div {{
        background-color: #0b0f14;
        border: 1px dashed rgba(255,255,255,0.06);
        padding: 8px;
    }}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------
# Database operations
# ---------------------------
def get_dossiers_df(conn, filters=None):
    q = "SELECT id, client_name, quartier, puissance_kwc, statut, battery_autonomy_hours, lan_available, filename, created_at FROM dossiers"
    params = []
    if filters:
        clauses = []
        if filters.get("quartier"):
            clauses.append("quartier = ?")
            params.append(filters["quartier"])
        if filters.get("statut"):
            clauses.append("statut = ?")
            params.append(filters["statut"])
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
    df = pd.read_sql_query(q, conn, params=params)
    return df

def create_dossier(conn, client_name, quartier, puissance_kwc, statut, battery_autonomy_hours, lan_available, filename):
    c = conn.cursor()
    c.execute("""
        INSERT INTO dossiers (client_name, quartier, puissance_kwc, statut, battery_autonomy_hours, lan_available, filename, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (client_name, quartier, puissance_kwc, statut, battery_autonomy_hours, int(lan_available), filename, datetime.utcnow().isoformat()))
    conn.commit()

def update_dossier(conn, dossier_id, **kwargs):
    keys = []
    params = []
    for k, v in kwargs.items():
        keys.append(f"{k} = ?")
        params.append(v)
    params.append(dossier_id)
    q = f"UPDATE dossiers SET {', '.join(keys)} WHERE id = ?"
    c = conn.cursor()
    c.execute(q, params)
    conn.commit()

def delete_dossier(conn, dossier_id):
    c = conn.cursor()
    c.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
    conn.commit()

# ---------------------------
# Monitoring Simulation
# ---------------------------
def get_monitoring_sample():
    # Simulate realistic values for Sahel / Extrême-Nord
    temp = round(random.uniform(28.0, 45.0), 1)  # degrees C
    mains_v = round(random.uniform(200.0, 240.0), 1)  # Volts
    solar_v = round(random.uniform(40.0, 70.0), 1)  # Volts (panel string)
    statuses = {
        "ENEO": random.choice(["OK", "Panne", "Faible"]),
        "Solaire": random.choice(["Chargé", "Faible", "Optimal"]),
        "Onduleur": random.choice(["Online", "Bypass", "Fault"]),
        "Groupe": random.choice(["Arrêté", "En marche", "Maintenance"])
    }
    return {"temp": temp, "mains_v": mains_v, "solar_v": solar_v, "statuses": statuses}

def status_color(val):
    if val in ["OK", "Chargé", "Optimal", "Online", "En marche"]:
        return SOLAR_GREEN
    if val in ["Faible", "Bypass", "Arrêté"]:
        return ORANGE_ACCENT
    return "#FF3B30"  # red-ish for faults

# ---------------------------
# Main App Layout & Logic
# ---------------------------
def main():
    ensure_dirs()
    inject_css()
    conn = init_db()
    insert_demo_data(conn)

    # Sidebar: Login / User info
    if "auth" not in st.session_state:
        st.session_state.auth = {"logged_in": False, "username": None, "role": None}

    with st.sidebar:
        st.markdown(f"<h2 style='color:{SOLAR_GREEN}'>ORDIDSOLARCALC</h2>", unsafe_allow_html=True)
        if not st.session_state.auth["logged_in"]:
            st.markdown("### 🔐 Connexion")
            username = st.text_input("Email", value="admin@ordidsolarcalc.cm")
            password = st.text_input("Mot de passe", type="password", value="Admin2026!")
            if st.button("Se connecter"):
                ok, role = authenticate(username.strip(), password.strip())
                if ok:
                    st.session_state.auth["logged_in"] = True
                    st.session_state.auth["username"] = username.strip()
                    st.session_state.auth["role"] = role
                    st.success(f"Connecté en tant que {username} ({role})")
                    st.experimental_rerun()
                else:
                    st.error("Identifiants invalides.")
            st.markdown("---")
            st.markdown("Comptes de démo :")
            st.markdown("- admin@ordidsolarcalc.cm / Admin2026! (admin)")
            st.markdown("- gestionnaire@ordidsolarcalc.cm / Gest2026! (gestionnaire)")
            st.markdown("- agent@ordidsolarcalc.cm / Agent2026! (agent)")
        else:
            st.markdown(f"**Utilisateur:** {st.session_state.auth['username']}")
            st.markdown(f"**Rôle:** {st.session_state.auth['role']}")
            if st.button("Se déconnecter"):
                st.session_state.auth = {"logged_in": False, "username": None, "role": None}
                st.experimental_rerun()
            st.markdown("---")
            st.markdown("Navigation rapide")
            st.markdown("- Tableau de bord")
            st.markdown("- Gestion dossiers")
            st.markdown("- Monitoring")

    # Require login for app use
    if not st.session_state.auth["logged_in"]:
        st.markdown("<div class='card'><h3 style='color:#E6EDF3'>Bienvenue — ORDIDSOLARCALC</h3><p>Veuillez vous connecter depuis la barre latérale.</p></div>", unsafe_allow_html=True)
        return

    # Top header
    st.markdown(f"<h1 style='color:{SOLAR_GREEN};margin-bottom:4px'>ORDIDSOLARCALC — Gestion Solarisation (Maroua)</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#BFDCC9'>Tableau de bord métier & monitoring pour l'Extrême-Nord (Sahelien)</p>", unsafe_allow_html=True)

    tabs = st.tabs([f"📊 Dashboard", f"🗂️ Gestion Dossiers", f"🖥️ Monitoring Serveur"])
    # ---------------------------
    # Dashboard Tab
    # ---------------------------
    with tabs[0]:
        st.markdown("## Vue analytique")
        df_all = get_dossiers_df(conn)
        # Computed metrics
        total_power = float(df_all["puissance_kwc"].sum()) if not df_all.empty else 0.0
        dossier_count = int(len(df_all))
        avg_autonomy = float(df_all["battery_autonomy_hours"].dropna().mean()) if not df_all.empty else 0.0
        lan_avail_pct = (df_all["lan_available"].sum() / max(1, dossier_count) * 100) if "lan_available" in df_all.columns and dossier_count>0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Puissance totale (kWc)", value=f"{total_power:.2f}", delta=None)
        with col2:
            st.metric(label="Nombre de dossiers", value=f"{dossier_count}", delta=None)
        with col3:
            st.metric(label="Autonomie moyenne (h)", value=f"{avg_autonomy:.1f}", delta=None)
        with col4:
            st.metric(label="Disponibilité LAN (%)", value=f"{lan_avail_pct:.0f}%", delta=None)

        st.markdown("---")
        # Charts
        st.markdown("### Répartition & évolution")
        if df_all.empty:
            st.info("Pas de dossiers pour afficher des graphiques.")
        else:
            # Bar chart: dossiers par quartier
            bar_df = df_all.groupby("quartier").agg({"id":"count"}).rename(columns={"id":"count"}).reset_index().set_index("quartier")
            st.subheader("Dossiers par quartier")
            st.bar_chart(bar_df)

            # Line chart: puissance cumulée par date (created_at)
            df_all["created_dt"] = pd.to_datetime(df_all["created_at"])
            ts = df_all.groupby(df_all["created_dt"].dt.to_period("M")).agg({"puissance_kwc":"sum"})
            ts.index = ts.index.to_timestamp()
            ts = ts.rename_axis("month").reset_index().set_index("month")
            st.subheader("Puissance cumulée (kWc) par mois")
            st.line_chart(ts)

        st.markdown("---")
        st.markdown("Export / Rapports")
        colA, colB = st.columns([1,1])
        with colA:
            if st.session_state.auth["role"] == "admin":
                if st.button("Exporter base CSV"):
                    df_all.to_csv("export_dossiers.csv", index=False)
                    with open("export_dossiers.csv", "rb") as f:
                        st.download_button("Télécharger export_dossiers.csv", data=f, file_name="export_dossiers.csv", mime="text/csv")
            else:
                st.info("Export CSV réservé aux administrateurs.")

        with colB:
            st.markdown("Filtrer aperçu rapide")
            q = st.selectbox("Quartier (filtre rapide)", options=["Tous"] + QUARTIERS)
            s = st.selectbox("Statut (filtre rapide)", options=["Tous"] + STATUSES)
            filt = {}
            if q != "Tous":
                filt["quartier"] = q
            if s != "Tous":
                filt["statut"] = s
            df_filtered = get_dossiers_df(conn, filters=filt) if (q!="Tous" or s!="Tous") else df_all
            st.dataframe(df_filtered.sort_values(by="created_at", ascending=False).reset_index(drop=True), use_container_width=True)

    # ---------------------------
    # Gestion Dossiers Tab
    # ---------------------------
    with tabs[1]:
        st.markdown("## Gestion des dossiers")
        # Two columns: left form create, right list & search
        left, right = st.columns([1,2])

        with left:
            st.markdown("### ➕ Création de dossier")
            with st.form("create_form", clear_on_submit=True):
                client_name = st.text_input("Nom du client", max_chars=120)
                quartier = st.selectbox("Quartier", QUARTIERS)
                puissance_kwc = st.number_input("Puissance (kWc)", min_value=0.1, step=0.1, format="%.2f")
                statut = st.selectbox("Statut", STATUSES, index=0)
                battery_autonomy_hours = st.number_input("Autonomie batterie (heures) — optionnel", min_value=0.0, step=0.5, value=24.0)
                lan_available = st.checkbox("Disponibilité LAN local", value=True)
                uploaded = st.file_uploader("Upload document / image (<= 10 MB)", type=["png","jpg","jpeg","pdf","doc","docx","xlsx"])
                submit = st.form_submit_button("Créer le dossier")
                if submit:
                    if not client_name.strip():
                        st.error("Le nom du client est requis.")
                    else:
                        filename = None
                        if uploaded is not None:
                            size = len(uploaded.getbuffer())
                            if size > MAX_UPLOAD_MB * 1024 * 1024:
                                st.error(f"Fichier trop volumineux (> {MAX_UPLOAD_MB} MB).")
                                st.stop()
                            # save file
                            basename = f"{int(time.time())}_{uploaded.name}"
                            path = os.path.join(UPLOAD_DIR, basename)
                            with open(path, "wb") as f:
                                f.write(uploaded.getbuffer())
                            filename = basename
                        create_dossier(conn, client_name.strip(), quartier, float(puissance_kwc), statut, float(battery_autonomy_hours) if battery_autonomy_hours>0 else None, bool(lan_available), filename)
                        st.success("Dossier créé.")
                        st.experimental_rerun()

        with right:
            st.markdown("### 🔎 Rechercher & Modifier")
            col_f1, col_f2, col_f3 = st.columns([1,1,1])
            with col_f1:
                filter_quartier = st.selectbox("Filtrer par quartier", options=["Tous"] + QUARTIERS, key="filter_quartier")
            with col_f2:
                filter_statut = st.selectbox("Filtrer par statut", options=["Tous"] + STATUSES, key="filter_statut")
            with col_f3:
                search_text = st.text_input("Recherche texte (client)", value="", key="search_text")

            filters = {}
            if filter_quartier != "Tous":
                filters["quartier"] = filter_quartier
            if filter_statut != "Tous":
                filters["statut"] = filter_statut

            df_view = get_dossiers_df(conn, filters=filters)
            if search_text.strip():
                df_view = df_view[df_view["client_name"].str.contains(search_text.strip(), case=False, na=False)]

            st.dataframe(df_view.sort_values(by="created_at", ascending=False).reset_index(drop=True), use_container_width=True)

            # Edit / Delete inline: select dossier by id
            st.markdown("#### Modifier un dossier")
            ids = df_view["id"].tolist()
            if ids:
                sel = st.selectbox("Choisir un dossier (ID)", options=ids)
                if sel:
                    row = df_view[df_view["id"] == sel].iloc[0]
                    with st.form(f"edit_form_{sel}"):
                        e_client = st.text_input("Nom client", value=row["client_name"])
                        e_quartier = st.selectbox("Quartier", options=QUARTIERS, index=QUARTIERS.index(row["quartier"]) if row["quartier"] in QUARTIERS else 0)
                        e_puissance = st.number_input("Puissance (kWc)", value=float(row["puissance_kwc"]), step=0.1, format="%.2f")
                        e_statut = st.selectbox("Statut", options=STATUSES, index=STATUSES.index(row["statut"]) if row["statut"] in STATUSES else 0)
                        e_batt = st.number_input("Autonomie batterie (h)", value=float(row["battery_autonomy_hours"]) if row["battery_autonomy_hours"] is not None else 0.0, step=0.5)
                        e_lan = st.checkbox("LAN disponible", value=bool(row["lan_available"]))
                        e_file = st.file_uploader("Remplacer le fichier (laisser vide pour conserver)", type=["png","jpg","jpeg","pdf","doc","docx","xlsx"])
                        saved = st.form_submit_button("Enregistrer les modifications")
                        if saved:
                            filename = row["filename"]
                            if e_file is not None:
                                size = len(e_file.getbuffer())
                                if size > MAX_UPLOAD_MB * 1024 * 1024:
                                    st.error(f"Fichier trop volumineux (> {MAX_UPLOAD_MB} MB).")
                                    st.stop()
                                basename = f"{int(time.time())}_{e_file.name}"
                                path = os.path.join(UPLOAD_DIR, basename)
                                with open(path, "wb") as f:
                                    f.write(e_file.getbuffer())
                                filename = basename
                            update_dossier(conn, sel,
                                           client_name=e_client.strip(),
                                           quartier=e_quartier,
                                           puissance_kwc=float(e_puissance),
                                           statut=e_statut,
                                           battery_autonomy_hours=float(e_batt) if e_batt>0 else None,
                                           lan_available=int(bool(e_lan)),
                                           filename=filename)
                            st.success("Dossier mis à jour.")
                            st.experimental_rerun()
                    # Delete (admin only)
                    if st.session_state.auth["role"] == "admin":
                        if st.button("Supprimer ce dossier (ADMIN)"):
                            delete_dossier(conn, sel)
                            st.success("Dossier supprimé.")
                            st.experimental_rerun()
                    else:
                        st.info("Suppression réservée aux administrateurs.")
            else:
                st.info("Aucun dossier correspondant aux filtres.")

    # ---------------------------
    # Monitoring Tab
    # ---------------------------
    with tabs[2]:
        st.markdown("## Console de Monitoring Serveur — Extrême-Nord (Sahelien)")
        st.markdown("Indicateurs de température, tensions, et état des 4 paliers d'énergie.")

        monitor_col1, monitor_col2 = st.columns([2,1])
        with monitor_col1:
            # Show metrics in cards
            mon = get_monitoring_sample()
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color:{ORANGE_ACCENT}'>🏜️ Conditions ambiantes</h3>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Température baie (°C)", f"{mon['temp']} °C")
            c2.metric("Tension secteur (V)", f"{mon['mains_v']} V")
            c3.metric("Tension solaire (V)", f"{mon['solar_v']} V")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### États des paliers d'énergie")
            st_table = []
            for name, stt in mon["statuses"].items():
                col = status_color(stt)
                st.markdown(f"<div style='display:flex;align-items:center;gap:12px;padding:8px;border-radius:8px;background:#071014;margin-bottom:6px'>"
                            f"<div style='width:12px;height:12px;border-radius:6px;background:{col}'></div>"
                            f"<div style='color:#E6EDF3;font-weight:600'>{name}</div>"
                            f"<div style='color:#BFDCC9;margin-left:8px'>{stt}</div>"
                            f"</div>", unsafe_allow_html=True)

            st.markdown("---")
            if st.button("Rafraîchir"):
                st.experimental_rerun()

        with monitor_col2:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='color:{SOLAR_GREEN}'>Contrôles rapides</h4>", unsafe_allow_html=True)
            st.markdown("Simulation des seuils et alarmes")
            temp_threshold = st.slider("Seuil température (°C) alarme", 30, 60, 42)
            mains_low = st.slider("Tension secteur basse (V)", 150, 220, 200)
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("Journal des évènements (simulé)")
            for i in range(3):
                t = datetime.utcnow().isoformat(timespec="seconds")
                msg = random.choice([
                    "Commutation vers solaire (panne ENEO)",
                    "Battery charging optimal",
                    "Onduleur: fonctionnement nominal",
                    "Groupe: Test automatique programmé"
                ])
                st.markdown(f"- {t} — {msg}")
            st.markdown("</div>", unsafe_allow_html=True)

    # Footer / credits
    st.markdown("---")
    st.markdown(f"<small style='color:#9FBF9A'>ORDIDSOLARCALC • Démonstration — Ne pas utiliser en production sans audit. Theme: sombre, accents {SOLAR_GREEN} & {ORANGE_ACCENT}.</small>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
