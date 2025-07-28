import streamlit as st
import pandas as pd
import sqlite3
import random
from datetime import datetime
import time

# ===========================
# Database Setup
# ===========================
def init_db():
    conn = sqlite3.connect("badminton_cup.db", check_same_thread=False)
    cursor = conn.cursor()

    # Table for Teams
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grup TEXT NOT NULL,
        nama_tim TEXT NOT NULL UNIQUE
    )
    """)

    # Table for Matches (dengan kolom tambahan)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grup TEXT NOT NULL,
        team1 TEXT NOT NULL,
        team2 TEXT NOT NULL,
        score1 INTEGER,
        score2 INTEGER,
        team1_pf INTEGER,
        team1_pa INTEGER,
        team2_pf INTEGER,
        team2_pa INTEGER,
        court TEXT,
        waktu TEXT,
        status TEXT DEFAULT 'scheduled',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(grup, team1, team2)
    )
    """)

    # Alter Table - Tambahkan kolom jika belum ada
    def add_column_if_not_exists(col_name, col_type):
        try:
            cursor.execute(f"ALTER TABLE matches ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if f"duplicate column name: {col_name}" not in str(e).lower():
                raise e  # hanya abaikan jika kolom sudah ada

    for col, tipe in [
        ("team1_pf", "INTEGER"),
        ("team1_pa", "INTEGER"),
        ("team2_pf", "INTEGER"),
        ("team2_pa", "INTEGER"),
        ("court", "TEXT"),
        ("waktu", "TEXT"),
        ("status", "TEXT")
    ]:
        add_column_if_not_exists(col, tipe)

    conn.commit()
    return conn, cursor


conn, cursor = init_db()

# ===========================
# Authentication
# ===========================
USERS = {
    "admin": "admin123",
    "viewer": "viewonly"
}

def delete_match(match_id):
    cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()

def login_form():
    """Display login form in sidebar"""
    with st.sidebar:
        st.markdown("## 🔐 Admin Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login", use_container_width=True):
                if username in USERS and USERS[username] == password:
                    st.session_state["authenticated"] = True
                    st.session_state["role"] = "admin" if username == "admin" else "viewer"
                    st.success(f"Welcome, {username}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        with col2:
            if st.button("Continue as Guest", use_container_width=True):
                st.session_state["authenticated"] = False
                st.session_state["role"] = "guest"
                st.success("Viewing as guest")
                time.sleep(1)
                st.rerun()

# ===========================
# Helper Functions
# ===========================
def get_grup_teams(grup):
    """Get all teams in a group"""
    return [row[0] for row in cursor.execute("SELECT nama_tim FROM teams WHERE grup=?", (grup,)).fetchall()]

def get_all_grups():
    """Get all available groups"""
    return sorted(set([row[0] for row in cursor.execute("SELECT grup FROM teams").fetchall()]))

def calculate_klasemen(grup):
    """Hitung klasemen berdasarkan pertandingan selesai"""

    teams = get_grup_teams(grup)
    if not teams:
        return pd.DataFrame()

    # Inisialisasi statistik
    stats = {team: {"Main": 0, "Menang": 0, "Kalah": 0, "PF": 0, "PA": 0} for team in teams}

    # Ambil pertandingan selesai
    for row in cursor.execute("""
        SELECT team1, team2, score1, score2 
        FROM matches 
        WHERE grup = ? AND status = 'done'
    """, (grup,)):
        t1, t2, s1, s2 = row
        if s1 is None or s2 is None:
            continue

        stats[t1]["Main"] += 1
        stats[t2]["Main"] += 1

        stats[t1]["PF"] += s1
        stats[t1]["PA"] += s2
        stats[t2]["PF"] += s2
        stats[t2]["PA"] += s1

        if s1 > s2:
            stats[t1]["Menang"] += 1
            stats[t2]["Kalah"] += 1
        elif s2 > s1:
            stats[t2]["Menang"] += 1
            stats[t1]["Kalah"] += 1

    # Susun DataFrame klasemen
    tabel = []
    for team, val in stats.items():
        selisih = val["PF"] - val["PA"]
        poin = val["Menang"] * 3
        tabel.append({
            "Tim": team,
            **val,
            "Selisih": selisih,
            "Poin": poin
        })

    return pd.DataFrame(tabel).sort_values(by=["Poin", "Selisih"], ascending=[False, False]).reset_index(drop=True)


def style_klasemen(df):
    """Styling simple without background_gradient (no matplotlib needed)"""
    if df.empty:
        return df

    return df.style \
        .format({"Selisih": "{:+}"}) \
        .set_properties(**{'text-align': 'center'}) \
        .set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#4a7d8c'), ('color', 'white'), ('text-align', 'center')]},
            {'selector': 'td', 'props': [('border', '1px solid #dee2e6')]}
        ])


# ===========================
# UI Components
# ===========================
def show_klasemen():
    """Display group standings"""
    st.subheader("📊 Klasemen Grup", divider="rainbow")
    
    if not get_all_grups():
        st.warning("Belum ada tim yang terdaftar")
        return
    
    tabs = st.tabs([f"Grup {grup}" for grup in get_all_grups()])
    
    for i, grup in enumerate(get_all_grups()):
        with tabs[i]:
            df = calculate_klasemen(grup)
            
            if df.empty:
                st.warning(f"Belum ada tim di Grup {grup}")
                continue
                
            st.dataframe(
                style_klasemen(df),
                use_container_width=True,
                hide_index=True
            )
            
            if len(df) >= 4 and df["Main"].min() >= 3:
                cols = st.columns(2)
                with cols[0]:
                    st.success(f"🏆 **Juara Grup:** {df.iloc[0]['Tim']}")
                with cols[1]:
                    st.info(f"🥈 **Runner-up:** {df.iloc[1]['Tim']}")

def show_input_score():
    """Score input interface"""
    st.subheader("✍️ Input Skor Pertandingan", divider="rainbow")
    
    if not get_all_grups():
        st.warning("Belum ada tim yang terdaftar")
        return
    
    selected_grup = st.selectbox("Pilih Grup", get_all_grups())
    teams = get_grup_teams(selected_grup)
    
    if not teams:
        st.warning(f"Belum ada tim di Grup {selected_grup}")
        return
        
    st.markdown(f"### Grup {selected_grup}")
    
    # Generate all possible matchups
    matchups = [(a, b) for i, a in enumerate(teams) for j, b in enumerate(teams) if i < j]
    
    for t1, t2 in matchups:
        # Check if match already exists
        existing = cursor.execute(
            "SELECT score1, score2 FROM matches WHERE grup=? AND team1=? AND team2=?",
            (selected_grup, t1, t2)
        ).fetchone()
        
        with st.expander(f"{t1} vs {t2}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                score1 = st.number_input(
                    f"Score {t1}",
                    min_value=0,
                    max_value=30,
                    value=existing[0] if existing else 0,
                    key=f"score1_{selected_grup}_{t1}_{t2}"
                )
            with col2:
                score2 = st.number_input(
                    f"Score {t2}",
                    min_value=0,
                    max_value=30,
                    value=existing[1] if existing else 0,
                    key=f"score2_{selected_grup}_{t1}_{t2}"
                )
            
            if st.button("Simpan", key=f"save_{selected_grup}_{t1}_{t2}"):
                cursor.execute("""
                    INSERT OR REPLACE INTO matches (grup, team1, team2, score1, score2)
                    VALUES (?, ?, ?, ?, ?)
                """, (selected_grup, t1, t2, score1, score2))
                conn.commit()
                st.success("Skor berhasil disimpan!")
                time.sleep(1)
                st.rerun()

def show_team_management():
    """Team management interface"""
    st.subheader("🧑‍🤝‍🧑 Manajemen Tim", divider="rainbow")
    
    with st.form("team_form"):
        cols = st.columns(2)
        with cols[0]:
            grup = st.selectbox("Grup", ["A", "B", "C", "D"])
        with cols[1]:
            nama_tim = st.text_input("Nama Tim")
        
        submitted = st.form_submit_button("Tambah Tim")
        
        if submitted and nama_tim:
            try:
                cursor.execute(
                    "INSERT INTO teams (grup, nama_tim) VALUES (?, ?)", 
                    (grup, nama_tim)
                )
                conn.commit()
                st.success("Tim berhasil ditambahkan!")
                time.sleep(1)
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Tim dengan nama tersebut sudah ada")

    st.markdown("### Daftar Tim")
    df = pd.read_sql("SELECT grup, nama_tim FROM teams ORDER BY grup, nama_tim", conn)
    
    if df.empty:
        st.warning("Belum ada tim yang terdaftar")
    else:
        st.dataframe(
            df.style.set_properties(**{'text-align': 'center'}) \
                  .set_table_styles([{
                      'selector': 'th',
                      'props': [('background-color', '#4a7d8c'), ('color', 'white')]
                  }]),
            use_container_width=True,
            hide_index=True
        )
        
        if st.button("Hapus Semua Tim", type="primary"):
            cursor.execute("DELETE FROM teams")
            cursor.execute("DELETE FROM matches")
            conn.commit()
            st.success("Semua tim dan pertandingan telah dihapus")
            time.sleep(1)
            st.rerun()

def show_final_bracket():
    """Final bracket interface"""
    st.subheader("🏆 Bagan Final", divider="rainbow")
    
    # Cek apakah semua tim sudah bermain minimal 3 kali
    all_groups_ready = True
    group_status = []
    
    for grup in get_all_grups():
        df = calculate_klasemen(grup)
        if len(df) < 4:  # Minimal 4 tim per grup
            all_groups_ready = False
            group_status.append(f"Grup {grup}: ❌ (minimal 4 tim)")
            continue
            
        if df["Main"].min() < 3:  # Minimal 3 pertandingan per tim
            all_groups_ready = False
            group_status.append(f"Grup {grup}: ❌ (beberapa tim belum bermain 3x)")
        else:
            group_status.append(f"Grup {grup}: ✅ (siap untuk final)")
    
    # Tampilkan status grup
    st.markdown("### Status Kesiapan Grup")
    for status in group_status:
        st.write(status)
    
    if not all_groups_ready:
        st.warning("Final belum dapat digenerate. Syarat:")
        st.markdown("""
        - Setiap grup harus memiliki minimal 4 tim
        - Setiap tim harus sudah bermain minimal 3 kali
        """)
        
        # Tampilkan calon finalis jika ada
        all_finalists = []
        for grup in get_all_grups():
            df = calculate_klasemen(grup)
            if len(df) >= 2:
                all_finalists.append((grup, df.iloc[0]["Tim"]))
                all_finalists.append((grup, df.iloc[1]["Tim"]))
        
        if all_finalists:
            st.markdown("#### Calon Finalis (Sementara)")
            cols = st.columns(4)
            for i, (grup, team) in enumerate(all_finalists):
                with cols[i % 4]:
                    st.info(f"Grup {grup}: {team}")
        return
    
    # Jika semua grup siap, buat bagan final
    st.success("Semua grup telah memenuhi syarat! Siap untuk menentukan bagan final.")
    
    # Ambil 2 tim teratas dari setiap grup
    all_finalists = []
    for grup in get_all_grups():
        df = calculate_klasemen(grup)
        all_finalists.append((grup, df.iloc[0]["Tim"]))  # Juara grup
        all_finalists.append((grup, df.iloc[1]["Tim"]))  # Runner-up
    
    if "final_draw" not in st.session_state:
        # Buat bagan final yang seimbang
        juara_grup = {grup: team for grup, team in all_finalists if all_finalists.index((grup, team)) % 2 == 0}
        runner_up = {grup: team for grup, team in all_finalists if all_finalists.index((grup, team)) % 2 == 1}
        
        st.session_state["final_draw"] = [
            juara_grup["A"], runner_up["B"],  # A1 vs B2
            juara_grup["C"], runner_up["D"],  # C1 vs D2
            juara_grup["B"], runner_up["A"],  # B1 vs A2
            juara_grup["D"], runner_up["C"]   # D1 vs C2
        ]
    
    if st.button("Acak Ulang Bagan"):
        # Acak tetapi tetap pertahankan juara grup vs runner-up
        groups = ["A", "B", "C", "D"]
        random.shuffle(groups)
        
        juara_grup = {grup: team for grup, team in all_finalists if all_finalists.index((grup, team)) % 2 == 0}
        runner_up = {grup: team for grup, team in all_finalists if all_finalists.index((grup, team)) % 2 == 1}
        
        st.session_state["final_draw"] = [
            juara_grup[groups[0]], runner_up[groups[1]],
            juara_grup[groups[2]], runner_up[groups[3]],
            juara_grup[groups[1]], runner_up[groups[0]],
            juara_grup[groups[3]], runner_up[groups[2]]
        ]
        st.rerun()
    
    # Tampilkan bagan final
    st.markdown("### Bagan 8 Besar")
    draw = st.session_state["final_draw"]
    
    # Tampilkan dengan layout yang bagus
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Bagian Atas")
        st.markdown(f"""
        <div style='background-color:#d9edf7; padding:20px; border-radius:12px; margin:15px 0;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); color:#00394d;'>
            <h4 style='margin-bottom:5px;'>🏸 Pertandingan 1</h4>
            <p style='font-size:18px;'>{draw[0]} <strong>🆚</strong> {draw[1]}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background-color:#d9edf7; padding:20px; border-radius:12px; margin:15px 0;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); color:#00394d;'>
            <h4 style='margin-bottom:5px;'>🏸 Pertandingan 2</h4>
            <p style='font-size:18px;'>{draw[2]} <strong>🆚</strong> {draw[3]}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style='text-align:center; margin:30px 0; font-size:16px; color:#005c87;'>
            <strong>➡️ Semifinal:</strong> Pemenang 1 🆚 Pemenang 2
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("#### Bagian Bawah")
        st.markdown(f"""
        <div style='background-color:#fbeec1; padding:20px; border-radius:12px; margin:15px 0;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); color:#5a4500;'>
            <h4 style='margin-bottom:5px;'>🏸 Pertandingan 3</h4>
            <p style='font-size:18px;'>{draw[4]} <strong>🆚</strong> {draw[5]}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background-color:#fbeec1; padding:20px; border-radius:12px; margin:15px 0;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); color:#5a4500;'>
            <h4 style='margin-bottom:5px;'>🏸 Pertandingan 4</h4>
            <p style='font-size:18px;'>{draw[6]} <strong>🆚</strong> {draw[7]}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style='text-align:center; margin:30px 0; font-size:16px; color:#8a6d00;'>
            <strong>➡️ Semifinal:</strong> Pemenang 3 🆚 Pemenang 4
        </div>
        """, unsafe_allow_html=True)

    
    st.markdown("""
    <div style='text-align:center; margin:30px 0; padding:15px; background-color:#e6f7ff; border-radius:10px;'>
        <strong>Final:</strong> Pemenang Semifinal Atas vs Pemenang Semifinal Bawah
    </div>
    """, unsafe_allow_html=True)

# [Previous imports and database setup remain the same...]

# ===========================
# New Helper Functions
# ===========================
def get_all_matches():
    """Get all matches with formatted datetime"""
    return pd.read_sql("""
        SELECT id, grup, team1, team2, score1, score2,
               strftime('%d/%m/%Y %H:%M', updated_at) as waktu,
               CASE 
                    WHEN status IS NULL THEN 'Belum dimulai'
                    ELSE status
                END AS status
        FROM matches
        ORDER BY updated_at DESC
    """, conn)

def generate_match_schedule(grup, match_dates):
    """Generate match schedule for a group"""
    teams = get_grup_teams(grup)
    matchups = [(a, b) for i, a in enumerate(teams) for j, b in enumerate(teams) if i < j]
    
    for i, (t1, t2) in enumerate(matchups):
        match_date = match_dates[i % len(match_dates)]
        cursor.execute("""
            INSERT OR IGNORE INTO matches (grup, team1, team2, updated_at)
            VALUES (?, ?, ?, ?)
        """, (grup, t1, t2, match_date))
    conn.commit()

def calculate_final_standings():
    """Calculate final tournament standings"""
    winners = {}
    for grup in get_all_grups():
        df = calculate_klasemen(grup)
        if len(df) >= 2:
            winners[grup] = {
                'juara': df.iloc[0]['Tim'],
                'runner_up': df.iloc[1]['Tim']
            }
    return winners

# ===========================
# New UI Components
# ===========================
def show_live_match():
    """Live match input with timer"""
    st.subheader("🕒 Live Match Input", divider="rainbow")
    
    # Select ongoing match
    live_matches = pd.read_sql("""
        SELECT id, grup, team1, team2 
        FROM matches 
        ORDER BY grup
    """, conn)
    
    # Buat mapping dari display label ke match_id
    match_map = {
        f"{x['team1']} vs {x['team2']} (Grup {x['grup']}) - {x['waktu']}": x['id']
        for _, x in live_matches.iterrows()
    }

    # Jika belum ada yang dipilih, set default ke match pertama
    if 'selected_match_id' not in st.session_state:
        st.session_state.selected_match_id = live_matches.iloc[0]['id']

    # Ambil label dari match_map berdasarkan match_id tersimpan
    default_label = next((k for k, v in match_map.items() if v == st.session_state.selected_match_id), None)

    selected_label = st.sidebar.selectbox(
        "Pilih Pertandingan Aktif",
        options=list(match_map.keys()),
        index=list(match_map.keys()).index(default_label) if default_label in match_map else 0
    )

    # Simpan pilihan baru ke session_state
    st.session_state.selected_match_id = match_map[selected_label]

    # Gunakan match_id dari session_state
    match_id = st.session_state.selected_match_id
    
    # Timer section
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Timer Pertandingan**")
        timer_placeholder = st.empty()
        if st.button("Mulai Timer"):
            st.session_state['start_time'] = time.time()
        
        if 'start_time' in st.session_state:
            elapsed = time.time() - st.session_state['start_time']
            mins, secs = divmod(int(elapsed), 60)
            timer_placeholder.markdown(f"⏱️ **{mins:02d}:{secs:02d}**")
    
    # Score input
    with col2:
        st.markdown("**Input Skor**")
        score1 = st.number_input(f"Skor {live_matches.iloc[0]['team1']}", min_value=0, max_value=30)
        score2 = st.number_input(f"Skor {live_matches.iloc[0]['team2']}", min_value=0, max_value=30)
        
        if st.button("Simpan Skor"):
            cursor.execute("""
                UPDATE matches SET 
                    score1 = ?, score2 = ?, 
                    team1_pf = ?, team1_pa = ?, 
                    team2_pf = ?, team2_pa = ?, 
                    status = 'done', 
                WHERE id = ?
            """, (score1, score2, score1, score2, score2, score1, match_id))

            conn.commit()
            st.success("Skor berhasil disimpan!")
            time.sleep(1)
            st.rerun()
def update_match(id, team1, team2, waktu, grup):
    conn = sqlite3.connect("badminton_cup.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        UPDATE matches 
        SET team1 = ?, team2 = ?, updated_at = ?, grup = ?
        WHERE id = ?
    """, (team1, team2, waktu, grup, id))
    conn.commit()
    conn.close()

def show_match_schedule():
    """Match scheduling interface for individual teams"""
    st.subheader("🗓️ Jadwal Pertandingan Antar Tim", divider="rainbow")

    with st.expander("Buat Jadwal Baru", expanded=False):
        with st.form("schedule_form"):
            # Get all teams
            all_teams = pd.read_sql("SELECT nama_tim FROM teams ORDER BY nama_tim", conn)

            if all_teams.empty:
                st.warning("Belum ada tim yang terdaftar")
                st.stop()

            team_list = all_teams["nama_tim"].tolist()

            # Input team1 and team2 manually
            team1 = st.selectbox("Pilih Tim 1", team_list, key="team1")
            team2 = st.selectbox("Pilih Tim 2", team_list, key="team2")

            # Optional group label
            group_label = st.text_input("Label Grup (Opsional)", value="Non-Grup")

            # Date and time selection
            st.markdown("**Pilih Tanggal dan Waktu Pertandingan**")
            match_date = st.date_input("Tanggal", datetime.now().date(), key="match_date")
            match_time = st.time_input("Waktu", datetime.strptime("19:00", "%H:%M").time(), key="match_time")

            if st.form_submit_button("Simpan Jadwal"):
                match_datetime = datetime.combine(match_date, match_time).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute("""
                    INSERT OR IGNORE INTO matches (grup, team1, team2, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (group_label, team1, team2, match_datetime))
                conn.commit()
                st.success(f"Jadwal pertandingan {team1} vs {team2} berhasil disimpan!")
                time.sleep(1)
                st.rerun()

    st.markdown("### 📋 Daftar Jadwal Pertandingan")

    is_admin = st.session_state.role == "admin"

    matches = get_all_matches()

    if not matches.empty:
        matches["No"] = range(1, len(matches)+1)
        matches["Waktu"] = pd.to_datetime(matches["waktu"], format='%d/%m/%Y %H:%M')

        
        # Header
        col_header = st.columns([0.5, 2.5, 2.5, 2, 1.2, 1.2, 1])
        col_header[0].markdown("**No**")
        col_header[1].markdown("**Tim 1**")
        col_header[2].markdown("**Tim 2**")
        col_header[3].markdown("**Waktu**")
        col_header[4].markdown("**Grup**")
        col_header[5].markdown("**Status**")
        if is_admin:
            col_header[6].markdown("**Aksi**")

        # Baris data
        for _, row in matches.iterrows():
            c = st.columns([0.5, 2.5, 2.5, 2, 1.2, 1.2, 1])

            c[0].markdown(f"{row['No']}")

            # Editable field
            team1 = c[1].text_input(" ", value=row['team1'], key=f"team1_{row['id']}")
            team2 = c[2].text_input(" ", value=row['team2'], key=f"team2_{row['id']}")
            waktu_str = c[3].text_input(" ", value=row['Waktu'].strftime('%d/%m/%Y %H:%M'), key=f"waktu_{row['id']}")
            grup = c[4].text_input(" ", value=row['grup'], key=f"grup_{row['id']}")
            status = c[5].selectbox(" ", ["Belum", "Selesai"], index=0 if row["status"] == "Belum" else 1, key=f"status_{row['id']}")

            # Aksi admin
            if is_admin:
                with c[6]:
                    col_btn1, col_btn2 = st.columns([1, 1])
                    if col_btn1.button("💾", key=f"save_{row['id']}"):
                        try:
                            waktu_parsed = datetime.strptime(waktu_str, "%d/%m/%Y %H:%M")
                            update_match(row['id'], team1, team2, waktu_parsed, grup)
                            st.success(f"Pertandingan {team1} vs {team2} diperbarui.")
                            time.sleep(1)
                            st.rerun()
                        except ValueError:
                            st.error("Format waktu salah. Gunakan dd/mm/yyyy HH:MM.")
                    
                    if col_btn2.button("🗑️", key=f"del_{row['id']}"):
                        delete_match(row['id'])
                        st.warning(f"Pertandingan {team1} vs {team2} dihapus.")
                        time.sleep(1)
                        st.rerun()

    

       
    else:
        st.warning("Belum ada jadwal pertandingan")

def show_live_score_tv():
    """Live Score Display for TV with auto-refresh and team selection"""
    
    st.sidebar.title("📅 Pilih Pertandingan")

    # Ambil semua pertandingan
    matches = pd.read_sql("""
        SELECT id, grup, team1, team2, score1, score2, status,
               strftime('%d/%m/%Y %H:%M', updated_at) as waktu
        FROM matches
        ORDER BY updated_at DESC
    """, conn)

    if matches.empty:
        st.warning("Tidak ada pertandingan yang sedang berlangsung")
        return

    match_map = {
        f"{x['team1']} vs {x['team2']} (Grup {x['grup']}) - {x['waktu']}": x['id']
        for _, x in matches.iterrows()
    }

    if 'selected_match_id' not in st.session_state:
        st.session_state.selected_match_id = matches.iloc[0]['id']

    default_label = next((label for label, mid in match_map.items()
                         if mid == st.session_state.selected_match_id), None)

    selected_label = st.sidebar.selectbox(
        "Pilih Pertandingan Aktif",
        options=list(match_map.keys()),
        index=list(match_map.keys()).index(default_label) if default_label else 0
    )

    st.session_state.selected_match_id = match_map[selected_label]
    match_id = st.session_state.selected_match_id

    st.title("⚡ LIVE SCORE")
    st.markdown(f"### {selected_label}")

    refresh_placeholder = st.empty()

    st.markdown("""
    <style>
        #MainMenu, header, footer {visibility: hidden;}
        .scoreboard {
            background-color: #001f3f;
            color: white;
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            font-family: Arial, sans-serif;
            box-shadow: 0 0 25px rgba(0,0,0,0.3);
            margin-top: 30px;
        }
        .scoreboard .teams {
            display: flex;
            justify-content: space-around;
            align-items: center;
            font-size: 4rem;
            margin-bottom: 30px;
        }
        .scoreboard .team-name {
            font-weight: bold;
            font-size: 2rem;
            margin-bottom: 10px;
        }
        .scoreboard .score {
            font-size: 5rem;
            font-weight: bold;
            color: #FFD700;
        }
        .scoreboard .vs {
            font-size: 3rem;
            font-weight: bold;
            margin: 0 30px;
            color: #ccc;
        }
        .scoreboard .match-info {
            margin-top: 20px;
            font-size: 1.5rem;
            color: #aaa;
        }
    </style>
    """, unsafe_allow_html=True)

    current_match = pd.read_sql(f"""
        SELECT team1, team2, score1, score2, status,
               strftime('%d/%m/%Y %H:%M', updated_at) as waktu
        FROM matches 
        WHERE id = {match_id}
    """, conn).iloc[0]

    with refresh_placeholder.container():
        st.markdown(f"""
        <div class="scoreboard">
            <div class="teams">
                <div>
                    <div class="team-name">{current_match['team1']}</div>
                    <div class="score">{current_match['score1'] or 0}</div>
                </div>
                <div class="vs">VS</div>
                <div>
                    <div class="team-name">{current_match['team2']}</div>
                    <div class="score">{current_match['score2'] or 0}</div>
                </div>
            </div>
            <div class="match-info">
                Status: <strong>{current_match['status']}</strong> 
            </div>
        </div>
        """, unsafe_allow_html=True)

    # === ADMIN CONTROLS ===
    if st.session_state.get("role") == "admin":
        st.markdown("---") 
        st.subheader("Admin Controls")

        status = current_match["status"]

        if not status  or status.lower() == "pending":
            if st.button("🚀 Mulai Pertandingan"):
                cursor.execute("UPDATE matches SET status = 'ongoing', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (match_id,))
                conn.commit()
                st.success("Pertandingan dimulai!")
                time.sleep(1)
                st.rerun()

        elif status == "ongoing":
            col1, col2 = st.columns(2)
            with col1:
                new_score1 = st.number_input(
                    f"Score {current_match['team1']}",
                    min_value=0,
                    max_value=30,
                    value=int(current_match['score1']) if current_match['score1'] is not None else 0
                )
            with col2:
                new_score2 = st.number_input(
                    f"Score {current_match['team2']}",
                    min_value=0,
                    max_value=30,
                    value=int(current_match['score2']) if current_match['score2'] is not None else 0
                )

            if st.button("✅ Update Score"):
                cursor.execute("""
                    UPDATE matches SET 
                        score1 = ?, score2 = ?, 
                        team1_pf = ?, team1_pa = ?, 
                        team2_pf = ?, team2_pa = ?, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (new_score1, new_score2, new_score1, new_score2, new_score2, new_score1, match_id))
                conn.commit()
                st.success("Score diperbarui!")
                time.sleep(1)
                st.rerun()

            if st.button("⛔ Selesaikan Pertandingan"):
                cursor.execute("UPDATE matches SET status = 'done', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (match_id,))
                conn.commit()
                st.success("Pertandingan diselesaikan.")
                time.sleep(1)
                st.rerun()

        elif status == "done":
            st.info("✅ Pertandingan sudah selesai.")

    st.sidebar.markdown("""
    ### Petunjuk Tampilan TV:
    1. Pilih pertandingan dari dropdown
    2. Tekan **F11** untuk mode fullscreen
    3. Sistem auto-refresh setiap 1 detik
    """)

    time.sleep(1)
    st.rerun()



def show_match_schedule_public():
    """Readonly schedule view for participants or guests"""
    st.subheader("📅 Jadwal Pertandingan", divider="rainbow")
    
    matches = get_all_matches()

    if not matches.empty:
        # Convert and sort by time
        matches["Waktu"] = pd.to_datetime(matches["waktu"], format='%d/%m/%Y %H:%M')
        matches = matches.sort_values("Waktu")
        
        # Format display columns
        matches["Pertandingan"] = matches["team1"] + " vs " + matches["team2"]
        matches["Waktu"] = matches["Waktu"].dt.strftime('%d/%m/%Y %H:%M')
        matches["Status"] = matches["status"].replace({
            "Selesai": "✅ Selesai",
            "Belum dimulai": "⏳ Belum Mulai"
        })
        
        # Reorder columns
        display_cols = ["Pertandingan", "Waktu", "grup", "Status"]
        display_df = matches[display_cols].rename(columns={"grup": "Grup"})
        
        # Custom CSS for the table
        st.markdown("""
        <style>
            .schedule-table {
                max-height: 500px;
                overflow-y: auto;
                margin-top: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .schedule-table table {
                width: 100%;
            }
            .schedule-table th {
                position: sticky;
                top: 0;
                background-color: #4a7d8c;
                color: white;
                z-index: 100;
            }

        </style>
        """, unsafe_allow_html=True)
        
        
            
        # Add filters
        st.markdown("---")
        st.markdown("**Filter Jadwal**")
        col1, col2 = st.columns(2)
        
        with col1:
            grup_filter = st.selectbox(
                "Filter Grup",
                ["Semua Grup"] + sorted(matches["grup"].unique().tolist())
            )
        
        with col2:
            status_filter = st.selectbox(
                "Filter Status",
                ["Semua Status", "✅ Selesai", "⏳ Belum Mulai"]
            )
        
        # Apply filters
        if grup_filter != "Semua Grup":
            display_df = display_df[display_df["Grup"] == grup_filter]
        if status_filter != "Semua Status":
            display_df = display_df[display_df["Status"] == status_filter]
        
        # Show filtered count
        st.caption(f"Menampilkan {len(display_df)} dari {len(matches)} pertandingan")
        # Display the table in a scrollable container
        with st.container():
            st.markdown(
                f"""
                <div class="schedule-table">
                    {display_df.to_html(index=False, escape=False)}
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("Belum ada jadwal yang tersedia.", icon="ℹ️")
def show_match_history():
    """Match history viewer"""
    st.subheader("📜 Riwayat Pertandingan", divider="rainbow")
    
    matches = get_all_matches()
    if matches.empty:
        st.warning("Belum ada riwayat pertandingan")
        return
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        grup_filter = st.selectbox(
            "Filter Grup",
            ["Semua"] + get_all_grups()
        )
    with col2:
        status_filter = st.selectbox(
            "Filter Status",
            ["Semua", "Selesai", "Belum dimulai"]
        )
    
    # Apply filters
    if grup_filter != "Semua":
        matches = matches[matches["grup"] == grup_filter]
    if status_filter != "Semua":
        matches = matches[matches["status"] == status_filter]
    
    # Display results
    for _, match in matches.iterrows():
        with st.expander(f"{match['team1']} vs {match['team2']} (Grup {match['grup']})"):
            cols = st.columns(3)
            with cols[0]:
                st.markdown(f"**Waktu:** {match['waktu']}")
            with cols[1]:
                st.markdown(f"**Status:** {match['status']}")
            with cols[2]:
                if match['status'] == "Selesai":
                    st.markdown(f"**Hasil:** {match['score1']} - {match['score2']}")

def show_final_standings():
    """Final tournament standings"""
    st.subheader("🎖️ Peringkat Final", divider="rainbow")
    
    winners = calculate_final_standings()
    if not winners:
        st.warning("Belum ada data final")
        return
    
    # Display champions
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏆 Juara 1", "TBD")
    with col2:
        st.metric("🥈 Juara 2", "TBD")
    with col3:
        st.metric("🥉 Juara 3", "TBD")
    with col4:
        st.metric("🥉 Juara 4", "TBD")
    
    # Display group winners
    st.markdown("### Juara Grup")
    cols = st.columns(len(winners))
    for i, (grup, data) in enumerate(winners.items()):
        with cols[i]:
            st.info(f"**Grup {grup}**")
            st.markdown(f"🥇 {data['juara']}")
            st.markdown(f"🥈 {data['runner_up']}")

def export_data():
    """Data export functionality"""
    st.subheader("🧾 Export Data", divider="rainbow")
    
    export_type = st.selectbox(
        "Pilih Jenis Data",
        ["Klasemen Grup", "Jadwal Pertandingan", "Hasil Final"]
    )
    
    if export_type == "Klasemen Grup":
        data = []
        for grup in get_all_grups():
            df = calculate_klasemen(grup)
            df["Grup"] = grup
            data.append(df)
        result = pd.concat(data)
    elif export_type == "Jadwal Pertandingan":
        result = get_all_matches()
    else:
        result = pd.DataFrame(calculate_final_standings()).T
    
    # Display preview
    st.dataframe(result, use_container_width=True)
    
    # Export buttons
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download CSV",
            data=result.to_csv(index=False).encode('utf-8'),
            file_name=f"{export_type.lower().replace(' ', '_')}.csv",
            mime="text/csv"
        )
    with col2:
        st.download_button(
            "Download Excel",
            data=result.to_excel(excel_writer=pd.ExcelWriter('temp.xlsx', engine='xlsxwriter')),
            file_name=f"{export_type.lower().replace(' ', '_')}.xlsx",
            mime="application/vnd.ms-excel"
        )

# ===========================
# Updated Main App
# ===========================
def main():
    st.set_page_config(
        page_title="PBGS Badminton Cup",
        page_icon="🏸",
        layout="wide"
    )
    
    # Enhanced CSS
    st.markdown("""
    <style>
    .stButton>button {
        border-radius: 8px !important;
    }
    .stTextInput>div>div>input, 
    .stSelectbox>div>div>select,
    .stNumberInput>div>div>input {
        border-radius: 8px !important;
        border: 1px solid #ced4da !important;
    }
    .stDataFrame {
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    @media (max-width: 768px) {
        .stDataFrame {
            font-size: 14px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["role"] = "guest"
    
    # Show login form if not authenticated as admin
    if not st.session_state.get("authenticated", False):
        login_form()
    
    # Main content
    st.title("🏸 PBGS Badminton Cup")
    
    # Enhanced Navigation
    if st.session_state.get("role") == "admin":
        menu_options = {
            "🏠 Klasemen": show_klasemen,
            "🕒 Live Match": show_live_match,
            "🗓️ Jadwal": show_match_schedule,
            "✍️ Input Skor": show_input_score,
            "📜 Riwayat": show_match_history,
            "🔧 Manajemen Tim": show_team_management,
            "🏆 Final": show_final_bracket,
            "🎖️ Peringkat": show_final_standings,
            "🧾 Export": export_data,
            "📺 Live Score TV": show_live_score_tv
        }
    else:
        menu_options = {
            "🏠 Klasemen": show_klasemen,
            "🗓️ Jadwal": show_match_schedule_public,
            "📜 Riwayat": show_match_history,
            "🏆 Final": show_final_bracket,
            "🎖️ Peringkat": show_final_standings,
            "📺 Live Score TV": show_live_score_tv
        }
    
    selected = st.sidebar.radio("Menu", list(menu_options.keys()))
    
    # Enhanced logout button
    if st.session_state.get("authenticated", False):
        if st.sidebar.button("👋 Logout", type="primary"):
            st.session_state["authenticated"] = False
            st.session_state["role"] = "guest"
            st.session_state.pop('start_time', None)
            st.rerun()
    
    # Display selected page
    menu_options[selected]()

if __name__ == "__main__":
    main()
