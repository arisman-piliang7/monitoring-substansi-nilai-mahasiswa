import pandas as pd
import plotly.express as px
import streamlit as st

from auth import (
    authenticate,
    get_conn,
    reset_user_password,
    set_user_password,
    generate_random_password,
    get_user,
    create_reset_request,
    get_pending_requests,
    resolve_reset_request,
)

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Hasil Ujian - Rekayasa Perangkat Lunak",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

GRADE_ORDER = ["A", "A-", "B+", "B", "B-", "C+", "C", "D", "E"]
GRADE_COLORS = {
    "A": "#22C55E",
    "A-": "#4ADE80",
    "B+": "#84CC16",
    "B": "#EAB308",
    "B-": "#F59E0B",
    "C+": "#F97316",
    "C": "#FB923C",
    "D": "#EF4444",
    "E": "#B91C1C",
}
CLASS_COLORS = {"A": "#6366F1", "C": "#EC4899"}

# ----------------------------------------------------------------------------
# STYLE
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1200px; }

    .hero {
        background: linear-gradient(135deg, #4338CA 0%, #7C3AED 55%, #DB2777 100%);
        border-radius: 20px; padding: 28px 32px; color: white; margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.25);
    }
    .hero h1 { font-size: 1.65rem; font-weight: 800; margin: 0 0 4px 0; color: white; }
    .hero p { margin: 0; opacity: 0.9; font-size: 0.95rem; }

    .metric-card {
        background: white; border-radius: 16px; padding: 18px 20px;
        border: 1px solid #EEF0F4; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        text-align: center; height: 100%;
    }
    .metric-card .label {
        font-size: 0.78rem; color: #6B7280; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px;
    }
    .metric-card .value { font-size: 1.7rem; font-weight: 800; color: #111827; }
    .metric-card .sub { font-size: 0.78rem; color: #9CA3AF; margin-top: 2px; }

    .section-title {
        font-size: 1.05rem; font-weight: 700; color: #111827;
        margin: 22px 0 10px 0; display: flex; align-items: center; gap: 8px;
    }

    .password-box {
        background: #FEF9C3; border: 2px dashed #CA8A04; border-radius: 14px;
        padding: 18px 22px; text-align: center; margin: 14px 0;
    }
    .password-box .pwd {
        font-family: 'Courier New', monospace; font-size: 1.6rem; font-weight: 800;
        letter-spacing: 0.15em; color: #78350F; margin: 8px 0;
    }

    div[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid #EEF0F4; }

    .stTabs [data-baseweb="tab-list"] { gap: 6px; background: #F3F4F6; padding: 5px; border-radius: 12px; }
    .stTabs [data-baseweb="tab"] { border-radius: 9px; padding: 8px 18px; font-weight: 600; color: #4B5563; }
    .stTabs [aria-selected="true"] { background: white !important; color: #111827 !important; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }

    .badge {
        display: inline-block; padding: 3px 12px; border-radius: 999px;
        font-size: 0.75rem; font-weight: 700; background: #EEF2FF; color: #4338CA;
    }

    .app-footer {
        text-align: center; padding: 28px 0 10px 0; margin-top: 12px;
        color: #9CA3AF; font-size: 0.78rem; border-top: 1px solid #EEF0F4;
    }
    .app-footer b { color: #6B7280; }

    @media (max-width: 640px) {
        .hero { padding: 20px 18px; border-radius: 16px; }
        .hero h1 { font-size: 1.25rem; }
        .metric-card { padding: 14px; }
        .metric-card .value { font-size: 1.35rem; }
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        .password-box .pwd { font-size: 1.2rem; }
    }
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# DATA HELPERS
# ----------------------------------------------------------------------------
def load_all_students() -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM students ORDER BY kelas, nama", conn)
    finally:
        conn.close()
    return df


NUMERIC_STUDENT_COLS = [
    "tugas", "uts", "formatif", "tugas2", "uas",
    "bintang", "diskusi_mteam", "nilai_aktual", "absensi",
]


def load_student(nim: str):
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM students WHERE nim = ?", conn, params=(nim,)
        )
    finally:
        conn.close()
    if df.empty:
        return None
    for col in NUMERIC_STUDENT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.iloc[0]


def fmt_num(value, fmt="{:.0f}", default="-"):
    """Format angka dengan aman; kembalikan '-' jika nilainya kosong/None/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return fmt.format(value)
    except (ValueError, TypeError):
        return default


def load_meetings_for_student(nim: str) -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            """SELECT meeting_code, urutan, duration_seconds, duration_display,
                      target_seconds, target_display
               FROM meeting_durations WHERE nim = ? ORDER BY urutan""",
            conn,
            params=(nim,),
        )
    finally:
        conn.close()
    return df


def load_meetings_for_class(kelas: str) -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            """SELECT nim, meeting_code, urutan, duration_seconds, target_seconds, target_display
               FROM meeting_durations WHERE kelas = ? ORDER BY urutan""",
            conn,
            params=(kelas,),
        )
    finally:
        conn.close()
    return df


def format_seconds(total_seconds) -> str:
    """Ubah total detik menjadi tampilan 'Xj Ym Zd' yang ringkas."""
    if total_seconds is None or pd.isna(total_seconds):
        return "-"
    total_seconds = int(total_seconds)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}j")
    if m:
        parts.append(f"{m}m")
    if not h and not m:
        parts.append(f"{s}d")
    elif s:
        parts.append(f"{s}d")
    return " ".join(parts)


COMP_COLS = ["tugas", "uts", "formatif", "tugas2", "uas", "diskusi_mteam"]
COMP_LABELS = {
    "tugas": "TUGAS",
    "uts": "UTS",
    "formatif": "Formatif",
    "tugas2": "Tugas-2",
    "uas": "UAS",
    "diskusi_mteam": "Diskusi Mteam",
}


# ----------------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------------
def init_session():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("role", None)
    st.session_state.setdefault("username", None)
    st.session_state.setdefault(
        "login_stage", "credentials"
    )  # or 'reveal_password' / 'forgot_password'
    st.session_state.setdefault("revealed_password", None)


def do_logout():
    for key in ["logged_in", "role", "username", "login_stage", "revealed_password"]:
        st.session_state.pop(key, None)
    init_session()


init_session()


# ----------------------------------------------------------------------------
# LOGIN PAGE
# ----------------------------------------------------------------------------
def render_login():
    st.markdown(
        """
    <div class="hero">
        <h1>🎓 Dashboard Hasil Ujian</h1>
        <p>Rekayasa Perangkat Lunak · Semester Genap 2025/2026 · Teknik Informatika (Sore)</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown("### 🔐 Masuk ke Dashboard")
        mode = st.radio(
            "Masuk sebagai",
            ["Mahasiswa", "Admin"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if mode == "Admin":
            render_admin_login()
        else:
            render_student_login()


def render_admin_login():
    with st.form("admin_login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Masuk", use_container_width=True)

    if submitted:
        user = get_user(username)
        if user is None or user["role"] != "admin":
            st.error("Akun admin tidak ditemukan.")
            return
        ok, msg = authenticate(username, password)
        if ok:
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.session_state.username = username
            st.rerun()
        else:
            st.error(
                "Password salah."
                if msg != "FIRST_LOGIN"
                else "Akun belum memiliki password."
            )


def render_student_login():
    # Stage 1: enter NIM
    if st.session_state.login_stage == "credentials":
        with st.form("student_nim_form"):
            nim = st.text_input("NIM", placeholder="Masukkan NIM Anda")
            password = st.text_input(
                "Password",
                type="password",
                help="Kosongkan jika ini login pertama Anda",
            )
            submitted = st.form_submit_button("Lanjutkan", use_container_width=True)

        if submitted:
            nim = nim.strip()
            user = get_user(nim)
            if user is None or user["role"] != "student":
                st.error("NIM tidak ditemukan pada data mahasiswa terdaftar.")
                return

            if user["password_hash"] is None:
                # First login -> generate password now
                new_password = generate_random_password()
                set_user_password(nim, new_password)
                st.session_state.login_stage = "reveal_password"
                st.session_state.revealed_password = new_password
                st.session_state.pending_nim = nim
                st.rerun()
            else:
                ok, msg = authenticate(nim, password)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.role = "student"
                    st.session_state.username = nim
                    st.rerun()
                else:
                    st.error(msg if msg != "FIRST_LOGIN" else "Password salah.")

        st.markdown(
            "<div style='text-align:center; margin-top:6px;'>", unsafe_allow_html=True
        )
        if st.button("🔒 Lupa password?", use_container_width=True):
            st.session_state.login_stage = "forgot_password"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Stage 1b: forgot password -> submit a request to admin
    elif st.session_state.login_stage == "forgot_password":
        st.info(
            "Masukkan NIM Anda. Permintaan reset akan dikirim ke admin untuk disetujui."
        )
        with st.form("forgot_password_form"):
            nim_forgot = st.text_input("NIM", placeholder="Masukkan NIM Anda")
            submitted = st.form_submit_button(
                "Kirim Permintaan Reset", use_container_width=True
            )

        if submitted:
            ok, msg = create_reset_request(nim_forgot.strip())
            if ok:
                st.success(
                    msg + " Silakan hubungi dosen/admin jika perlu tindak lanjut, "
                    "lalu login kembali setelah password direset."
                )
            else:
                st.error(msg)

        if st.button("⬅️ Kembali ke Login", use_container_width=True):
            st.session_state.login_stage = "credentials"
            st.rerun()

    # Stage 2: reveal generated password once, require confirmation
    elif st.session_state.login_stage == "reveal_password":
        nim = st.session_state.pending_nim
        student = load_student(nim)
        st.success(
            f"Login pertama berhasil terverifikasi untuk **{student['nama']}** (NIM {nim})."
        )
        st.markdown(
            f"""
        <div class="password-box">
            <div style="font-weight:700; color:#78350F;">🔑 Password Anda (hanya ditampilkan sekali)</div>
            <div class="pwd">{st.session_state.revealed_password}</div>
            <div style="font-size:0.85rem; color:#92400E;">
                Simpan password ini baik-baik. Password ini <b>tidak dapat ditampilkan ulang</b>
                — Anda akan membutuhkannya untuk login berikutnya.
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        confirm = st.text_input(
            "Ketik ulang password di atas untuk konfirmasi bahwa Anda sudah menyimpannya"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "✅ Konfirmasi & Masuk", use_container_width=True, type="primary"
            ):
                if confirm == st.session_state.revealed_password:
                    st.session_state.logged_in = True
                    st.session_state.role = "student"
                    st.session_state.username = nim
                    st.session_state.login_stage = "credentials"
                    st.session_state.revealed_password = None
                    st.rerun()
                else:
                    st.error(
                        "Password yang diketik tidak cocok. Silakan cek kembali dan coba lagi."
                    )
        with col2:
            if st.button("⬅️ Batal", use_container_width=True):
                st.session_state.login_stage = "credentials"
                st.session_state.revealed_password = None
                st.rerun()


# ----------------------------------------------------------------------------
# STUDENT VIEW
# ----------------------------------------------------------------------------
def render_student_view():
    nim = st.session_state.username
    row = load_student(nim)
    if row is None:
        st.error("Data mahasiswa tidak ditemukan.")
        return

    all_students = load_all_students()
    class_df = all_students[all_students["kelas"] == row["kelas"]]

    st.markdown(
        f"""
    <div class="hero">
        <h1>👋 Halo, {row['nama']}</h1>
        <p>NIM {row['nim']} · Kelas {row['kelas']} · Rekayasa Perangkat Lunak</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    bintang_val = row["bintang"] if pd.notna(row["bintang"]) else 0

    if pd.notna(row["nilai_aktual"]):
        peringkat_display = f"#{int((class_df['nilai_aktual'] > row['nilai_aktual']).sum() + 1)}"
    else:
        peringkat_display = "-"

    cols = st.columns(5)
    metrics = [
        (
            "Nilai Akhir",
            fmt_num(row["nilai_aktual"]),
            f"Nilai huruf: {row['nilai_huruf'] or '-'}",
        ),
        ("Kehadiran", fmt_num(row["absensi"], "{:.0f}%"), "tingkat kehadiran"),
        (
            "Rata-rata Kelas",
            fmt_num(class_df["nilai_aktual"].mean(), "{:.1f}"),
            f"Kelas {row['kelas']}",
        ),
        (
            "Peringkat",
            peringkat_display,
            f"dari {len(class_df)} mahasiswa",
        ),
        ("⭐ Bintang", f"{bintang_val:.0f}", "reward keaktifan"),
    ]
    for c, (label, value, sub) in zip(cols, metrics):
        with c:
            st.markdown(
                f"""
            <div class="metric-card">
                <div class="label">{label}</div>
                <div class="value">{value}</div>
                <div class="sub">{sub}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-title">🧩 Rincian Nilai Komponen</div>',
        unsafe_allow_html=True,
    )
    comp_data = pd.DataFrame(
        {
            "Komponen": [COMP_LABELS[c] for c in COMP_COLS],
            "Nilai Anda": [row[c] if pd.notna(row[c]) else 0 for c in COMP_COLS],
            "Rata-rata Kelas": [class_df[c].mean() for c in COMP_COLS],
        }
    )
    comp_melt = comp_data.melt(
        id_vars="Komponen", var_name="Kategori", value_name="Nilai"
    )
    fig = px.bar(
        comp_melt,
        x="Komponen",
        y="Nilai",
        color="Kategori",
        barmode="group",
        color_discrete_map={"Nilai Anda": "#7C3AED", "Rata-rata Kelas": "#D1D5DB"},
        title="Nilai Anda vs Rata-rata Kelas",
    )
    fig.update_layout(
        height=380, plot_bgcolor="white", paper_bgcolor="white", legend_title_text=""
    )
    st.plotly_chart(fig, use_container_width=True)

    meetings = load_meetings_for_student(nim)
    if not meetings.empty:
        st.markdown(
            '<div class="section-title">🎥 Durasi Pertemuan Online</div>',
            unsafe_allow_html=True,
        )
        m = meetings.copy()
        m["Durasi Anda (menit)"] = (m["duration_seconds"].fillna(0) / 60).round(1)
        m["Target (menit)"] = (m["target_seconds"].fillna(0) / 60).round(1)
        m_melt = m.melt(
            id_vars="meeting_code",
            value_vars=["Durasi Anda (menit)", "Target (menit)"],
            var_name="Kategori",
            value_name="Menit",
        )
        fig_m = px.bar(
            m_melt,
            x="meeting_code",
            y="Menit",
            color="Kategori",
            barmode="group",
            color_discrete_map={
                "Durasi Anda (menit)": "#7C3AED",
                "Target (menit)": "#D1D5DB",
            },
            title="Durasi Kehadiran Online per Pertemuan",
        )
        fig_m.update_layout(
            height=340,
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend_title_text="",
            xaxis_title="Pertemuan",
        )
        st.plotly_chart(fig_m, use_container_width=True)

        m_table = m[["meeting_code", "duration_display", "target_display"]].rename(
            columns={
                "meeting_code": "Pertemuan",
                "duration_display": "Durasi Anda",
                "target_display": "Target Durasi",
            }
        )
        m_table["Durasi Anda"] = m_table["Durasi Anda"].fillna("Tidak hadir")
        st.dataframe(m_table, hide_index=True, use_container_width=True)

    st.markdown(
        '<div class="section-title">📄 Detail Lengkap (Nilai Huruf yang tertera hanya Estimasi, untuk aktual cek pada MIKA)</div>',
        unsafe_allow_html=True,
    )
    detail = pd.DataFrame(
        {
            "Komponen": [
                "TUGAS",
                "UTS",
                "Formatif",
                "Tugas-2",
                "UAS",
                "Diskusi Mteam",
                "Bintang",
                "Kehadiran (%)",
                "Nilai Akhir",
                "Nilai Huruf",
            ],
            "Nilai": [
                fmt_num(row["tugas"]),
                fmt_num(row["uts"]),
                fmt_num(row["formatif"]),
                fmt_num(row["tugas2"]),
                fmt_num(row["uas"]),
                fmt_num(row["diskusi_mteam"]),
                fmt_num(bintang_val),
                fmt_num(row["absensi"]),
                fmt_num(row["nilai_aktual"]),
                row["nilai_huruf"] or "-",
            ],
        }
    )
    st.dataframe(detail, hide_index=True, use_container_width=True)

    st.caption("🔒 Anda hanya dapat melihat data milik Anda sendiri.")


# ----------------------------------------------------------------------------
# ADMIN VIEW
# ----------------------------------------------------------------------------
def render_metrics(df: pd.DataFrame):
    n = len(df)
    avg = df["nilai_aktual"].mean()
    lulus = (df["nilai_huruf"] != "E").sum()
    tertinggi = df["nilai_aktual"].max()

    cols = st.columns(4)
    metrics = [
        ("Jumlah Mahasiswa", f"{n}", "orang terdaftar"),
        ("Rata-rata Nilai", f"{avg:.1f}", "skala 0-100"),
        ("Nilai Tertinggi", f"{tertinggi:.0f}", "pencapaian terbaik"),
        ("Lulus (bukan E)", f"{lulus}/{n}", f"{lulus/n*100:.0f}% tingkat kelulusan"),
    ]
    for c, (label, value, sub) in zip(cols, metrics):
        with c:
            st.markdown(
                f"""
            <div class="metric-card">
                <div class="label">{label}</div>
                <div class="value">{value}</div>
                <div class="sub">{sub}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def render_class_admin(df_kelas: pd.DataFrame, kelas_label: str, color: str):
    render_metrics(df_kelas)

    st.markdown(
        '<div class="section-title">🔍 Cari & Filter Mahasiswa</div>',
        unsafe_allow_html=True,
    )
    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        search = st.text_input(
            "Cari nama atau NIM",
            key=f"search_{kelas_label}",
            placeholder="Ketik nama atau NIM...",
            label_visibility="collapsed",
        )
    with fcol2:
        grade_options = ["Semua Nilai"] + [
            g for g in GRADE_ORDER if g in df_kelas["nilai_huruf"].unique()
        ]
        grade_filter = st.selectbox(
            "Filter nilai huruf",
            grade_options,
            key=f"grade_{kelas_label}",
            label_visibility="collapsed",
        )

    filtered = df_kelas.copy()
    if search:
        mask = filtered["nama"].str.contains(search, case=False, na=False) | filtered[
            "nim"
        ].astype(str).str.contains(search, case=False, na=False)
        filtered = filtered[mask]
    if grade_filter != "Semua Nilai":
        filtered = filtered[filtered["nilai_huruf"] == grade_filter]

    st.markdown(
        f'<div class="section-title">📋 Tabel Nilai ({len(filtered)} mahasiswa)</div>',
        unsafe_allow_html=True,
    )

    display_df = filtered[
        [
            "nim",
            "nama",
            "tugas",
            "uts",
            "formatif",
            "tugas2",
            "uas",
            "diskusi_mteam",
            "bintang",
            "nilai_aktual",
            "nilai_huruf",
            "absensi",
        ]
    ].rename(
        columns={
            "nim": "NIM",
            "nama": "Nama",
            "tugas": "TUGAS",
            "uts": "UTS",
            "formatif": "Formatif",
            "tugas2": "Tugas-2",
            "uas": "UAS",
            "diskusi_mteam": "Diskusi Mteam",
            "bintang": "Bintang",
            "nilai_aktual": "Nilai Akhir",
            "nilai_huruf": "Nilai Huruf",
            "absensi": "Kehadiran (%)",
        }
    )
    display_df["Bintang"] = display_df["Bintang"].fillna(0)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(460, 42 * (len(display_df) + 1)),
        column_config={
            "Nilai Akhir": st.column_config.ProgressColumn(
                "Nilai Akhir", min_value=0, max_value=100, format="%.0f"
            ),
            "Kehadiran (%)": st.column_config.ProgressColumn(
                "Kehadiran (%)", min_value=0, max_value=100, format="%.0f%%"
            ),
        },
    )

    csv_bytes = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Unduh data (CSV)",
        data=csv_bytes,
        file_name=f"hasil_ujian_kelas_{kelas_label}.csv",
        mime="text/csv",
        key=f"dl_{kelas_label}",
    )

    st.markdown(
        '<div class="section-title">📊 Distribusi & Analisis</div>',
        unsafe_allow_html=True,
    )
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        grade_counts = (
            df_kelas["nilai_huruf"]
            .value_counts()
            .reindex(GRADE_ORDER)
            .dropna()
            .reset_index()
        )
        grade_counts.columns = ["Nilai", "Jumlah"]
        fig = px.bar(
            grade_counts,
            x="Nilai",
            y="Jumlah",
            text="Jumlah",
            color="Nilai",
            color_discrete_map=GRADE_COLORS,
            title="Distribusi Nilai Huruf",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False,
            height=340,
            margin=dict(t=45, b=10, l=10, r=10),
            plot_bgcolor="white",
            paper_bgcolor="white",
            title_font_size=14,
        )
        st.plotly_chart(fig, use_container_width=True)
    with gcol2:
        fig2 = px.histogram(
            df_kelas,
            x="nilai_aktual",
            nbins=15,
            title="Sebaran Nilai Akhir",
            color_discrete_sequence=[color],
        )
        fig2.update_layout(
            height=340,
            margin=dict(t=45, b=10, l=10, r=10),
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis_title="Nilai Akhir",
            yaxis_title="Jumlah Mahasiswa",
            title_font_size=14,
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown(
        '<div class="section-title">🧩 Rata-rata per Komponen</div>',
        unsafe_allow_html=True,
    )
    comp_avg = df_kelas[COMP_COLS].mean().reset_index()
    comp_avg.columns = ["Komponen", "Rata-rata"]
    comp_avg["Komponen"] = comp_avg["Komponen"].map(COMP_LABELS)
    fig3 = px.bar(
        comp_avg,
        x="Komponen",
        y="Rata-rata",
        text_auto=".1f",
        color="Komponen",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig3.update_layout(
        showlegend=False,
        height=320,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig3, use_container_width=True)

    meetings_kelas = load_meetings_for_class(kelas_label)
    if not meetings_kelas.empty:
        st.markdown(
            '<div class="section-title">🎥 Rata-rata Durasi Pertemuan Online (Kelas)</div>',
            unsafe_allow_html=True,
        )
        agg = (
            meetings_kelas.groupby(["urutan", "meeting_code"], as_index=False)
            .agg(
                avg_seconds=("duration_seconds", "mean"),
                target_seconds=("target_seconds", "first"),
            )
            .sort_values("urutan")
        )
        agg["Rata-rata Kelas (menit)"] = (agg["avg_seconds"] / 60).round(1)
        agg["Target (menit)"] = (agg["target_seconds"] / 60).round(1)
        agg_melt = agg.melt(
            id_vars="meeting_code",
            value_vars=["Rata-rata Kelas (menit)", "Target (menit)"],
            var_name="Kategori",
            value_name="Menit",
        )
        fig_agg = px.bar(
            agg_melt,
            x="meeting_code",
            y="Menit",
            color="Kategori",
            barmode="group",
            color_discrete_map={
                "Rata-rata Kelas (menit)": color,
                "Target (menit)": "#D1D5DB",
            },
            title=f"Rata-rata Durasi vs Target per Pertemuan — Kelas {kelas_label}",
        )
        fig_agg.update_layout(
            height=340,
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend_title_text="",
            xaxis_title="Pertemuan",
        )
        st.plotly_chart(fig_agg, use_container_width=True)

    st.markdown(
        '<div class="section-title">⭐ Leaderboard Bintang</div>',
        unsafe_allow_html=True,
    )
    top_bintang = (
        df_kelas[df_kelas["bintang"].fillna(0) > 0][["nim", "nama", "bintang"]]
        .sort_values("bintang", ascending=False)
        .head(10)
        .rename(columns={"nim": "NIM", "nama": "Nama", "bintang": "Bintang"})
    )
    if top_bintang.empty:
        st.caption("Belum ada mahasiswa dengan Bintang di kelas ini.")
    else:
        st.dataframe(top_bintang, hide_index=True, use_container_width=True)

    st.markdown(
        '<div class="section-title">🔑 Manajemen Password Mahasiswa</div>',
        unsafe_allow_html=True,
    )
    reset_nim = st.selectbox(
        "Pilih mahasiswa untuk reset password",
        options=df_kelas["nim"].tolist(),
        format_func=lambda n: f"{n} - {df_kelas.set_index('nim').loc[n, 'nama']}",
        key=f"reset_{kelas_label}",
    )
    if st.button("🔄 Reset Password Mahasiswa Ini", key=f"reset_btn_{kelas_label}"):
        reset_user_password(reset_nim)
        st.success(
            f"Password untuk NIM {reset_nim} telah direset. "
            f"Mahasiswa akan membuat password baru saat login berikutnya."
        )


def render_pending_requests_panel():
    requests = get_pending_requests()
    if not requests:
        return

    st.markdown(
        f"""
    <div class="section-title">🔔 Permintaan Reset Password ({len(requests)} menunggu)</div>
    """,
        unsafe_allow_html=True,
    )

    for r in requests:
        rcol1, rcol2, rcol3 = st.columns([3, 1, 1])
        with rcol1:
            st.markdown(
                f"**{r['nama']}** · NIM {r['nim']} · Kelas {r['kelas']}  \n"
                f"<span style='color:#9CA3AF; font-size:0.8rem;'>Diminta: {r['requested_at']}</span>",
                unsafe_allow_html=True,
            )
        with rcol2:
            if st.button(
                "✅ Setujui & Reset", key=f"approve_{r['id']}", use_container_width=True
            ):
                resolve_reset_request(r["id"], approve=True)
                st.success(f"Password NIM {r['nim']} telah direset.")
                st.rerun()
        with rcol3:
            if st.button("✖️ Tolak", key=f"reject_{r['id']}", use_container_width=True):
                resolve_reset_request(r["id"], approve=False)
                st.rerun()
    st.markdown("---")


def render_admin_view():
    st.markdown(
        """
    <div class="hero">
        <h1>🎓 Dashboard Hasil Ujian Rekayasa Perangkat Lunak <span class="badge">ADMIN</span></h1>
        <p>Rekayasa Perangkat Lunak · Semester Genap 2025/2026 · Teknik Informatika (Sore)</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    render_pending_requests_panel()

    all_students = load_all_students()
    df_a = all_students[all_students["kelas"] == "A"]
    df_c = all_students[all_students["kelas"] == "C"]

    tab_a, tab_c, tab_compare = st.tabs(["🅰️ Kelas A", "🅲 Kelas C", "⚖️ Perbandingan"])

    with tab_a:
        render_class_admin(df_a, "A", CLASS_COLORS["A"])
    with tab_c:
        render_class_admin(df_c, "C", CLASS_COLORS["C"])
    with tab_compare:
        st.markdown(
            '<div class="section-title">⚖️ Perbandingan Kelas A vs Kelas C</div>',
            unsafe_allow_html=True,
        )
        ccol1, ccol2, ccol3 = st.columns(3)
        with ccol1:
            st.markdown(
                f"""<div class="metric-card"><div class="label">Rata-rata Kelas A</div>
                <div class="value">{df_a['nilai_aktual'].mean():.1f}</div>
                <div class="sub">{len(df_a)} mahasiswa</div></div>""",
                unsafe_allow_html=True,
            )
        with ccol2:
            st.markdown(
                f"""<div class="metric-card"><div class="label">Rata-rata Kelas C</div>
                <div class="value">{df_c['nilai_aktual'].mean():.1f}</div>
                <div class="sub">{len(df_c)} mahasiswa</div></div>""",
                unsafe_allow_html=True,
            )
        with ccol3:
            selisih = df_a["nilai_aktual"].mean() - df_c["nilai_aktual"].mean()
            st.markdown(
                f"""<div class="metric-card"><div class="label">Selisih Rata-rata</div>
                <div class="value">{selisih:+.1f}</div>
                <div class="sub">A dibanding C</div></div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        comp = pd.concat([df_a.assign(Kelas="Kelas A"), df_c.assign(Kelas="Kelas C")])
        fig = px.box(
            comp,
            x="Kelas",
            y="nilai_aktual",
            color="Kelas",
            color_discrete_map={
                "Kelas A": CLASS_COLORS["A"],
                "Kelas C": CLASS_COLORS["C"],
            },
            points="all",
            title="Sebaran Nilai Akhir: Kelas A vs Kelas C",
        )
        fig.update_layout(
            height=420,
            plot_bgcolor="white",
            paper_bgcolor="white",
            showlegend=False,
            yaxis_title="Nilai Akhir",
        )
        st.plotly_chart(fig, use_container_width=True)

        grade_comp = (
            pd.concat(
                [
                    df_a["nilai_huruf"].value_counts().rename("Kelas A"),
                    df_c["nilai_huruf"].value_counts().rename("Kelas C"),
                ],
                axis=1,
            )
            .reindex(GRADE_ORDER)
            .fillna(0)
            .reset_index()
        )
        grade_comp.columns = ["Nilai", "Kelas A", "Kelas C"]
        grade_comp_melt = grade_comp.melt(
            id_vars="Nilai", var_name="Kelas", value_name="Jumlah"
        )
        fig2 = px.bar(
            grade_comp_melt,
            x="Nilai",
            y="Jumlah",
            color="Kelas",
            barmode="group",
            color_discrete_map={
                "Kelas A": CLASS_COLORS["A"],
                "Kelas C": CLASS_COLORS["C"],
            },
            title="Distribusi Nilai Huruf: Kelas A vs Kelas C",
        )
        fig2.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig2, use_container_width=True)


# ----------------------------------------------------------------------------
# ADMIN CHANGE PASSWORD (sidebar)
# ----------------------------------------------------------------------------
def render_change_password_sidebar():
    with st.expander("🔑 Ganti Password"):
        with st.form("change_pwd_form"):
            old_pwd = st.text_input("Password saat ini", type="password")
            new_pwd = st.text_input("Password baru", type="password")
            new_pwd2 = st.text_input("Ulangi password baru", type="password")
            submitted = st.form_submit_button("Simpan")
        if submitted:
            ok, msg = authenticate(st.session_state.username, old_pwd)
            if not ok:
                st.error("Password saat ini salah.")
            elif len(new_pwd) < 6:
                st.error("Password baru minimal 6 karakter.")
            elif new_pwd != new_pwd2:
                st.error("Konfirmasi password baru tidak cocok.")
            else:
                set_user_password(st.session_state.username, new_pwd)
                st.success("Password berhasil diubah.")


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
if not st.session_state.logged_in:
    render_login()
else:
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.username}")
        st.markdown(
            f"Peran: **{'Admin' if st.session_state.role == 'admin' else 'Mahasiswa'}**"
        )
        st.markdown("---")
        render_change_password_sidebar()
        st.markdown("---")
        if st.button("🚪 Keluar", use_container_width=True):
            do_logout()
            st.rerun()

    if st.session_state.role == "admin":
        render_admin_view()
    else:
        render_student_view()

# ----------------------------------------------------------------------------
# FOOTER (tampil di semua halaman: login, mahasiswa, admin)
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-footer">
        Designed by <b>Arisman</b> · Dashboard Hasil Ujian Rekayasa Perangkat Lunak · Teknik Informatika Universitas Mikroskil
    </div>
    """,
    unsafe_allow_html=True,
)
