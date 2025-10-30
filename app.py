import streamlit as st
from supabase import create_client
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests

# =======================================================================
# 1️⃣ SETUP
# =======================================================================
st.set_page_config(layout="wide", page_title="Talent Match Intelligence System")
st.title("🚀 Talent Match Intelligence System")
st.caption("Menemukan talenta terbaik berdasarkan benchmark, kompetensi, dan insight AI (Gemini 2.5).")

# =======================================================================
# 2️⃣ KONEKSI SUPABASE
# =======================================================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Gagal konek ke Supabase: {e}")
    st.stop()

# =======================================================================
# 3️⃣ DATA KARYAWAN
# =======================================================================
@st.cache_data(ttl=3600)
def get_employees():
    res = supabase.table("employees").select("employee_id, fullname").execute()
    if res.data:
        return {emp["employee_id"]: emp["fullname"] for emp in sorted(res.data, key=lambda x: x["fullname"])}
    return {}

employees = get_employees()
if not employees:
    st.error("❌ Tidak ada data karyawan. Periksa tabel 'employees'.")
    st.stop()

# =======================================================================
# 4️⃣ FORM INPUT BENCHMARK
# =======================================================================
with st.form("form_benchmark"):
    st.subheader("1️⃣ Role Information")
    role_name = st.text_input("Role Name")
    job_level = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose = st.text_area("Role Purpose", placeholder="Tujuan utama role...")

    st.subheader("2️⃣ Employee Benchmarking")
    selected_names = st.multiselect(
        "Pilih Karyawan Benchmark (maksimal 3)",
        options=list(employees.values()),
        max_selections=3
    )

    submit = st.form_submit_button("✨ Find Matches")

# =======================================================================
# 5️⃣ PROSES BENCHMARK
# =======================================================================
if submit:
    if not (role_name and job_level and role_purpose and selected_names):
        st.error("Isi semua field dengan benar.")
        st.stop()

    st.info("🔄 Memproses data benchmark...")

    id_map = {v: k for k, v in employees.items()}
    selected_ids = [id_map[n] for n in selected_names]

    insert = supabase.table("talent_benchmarks").insert({
        "role_name": role_name,
        "job_level": job_level,
        "role_purpose": role_purpose,
        "selected_talent_ids": selected_ids
    }).execute()

    if not insert.data:
        st.error("❌ Gagal menyimpan benchmark.")
        st.stop()

    st.success("✅ Benchmark berhasil disimpan!")
    st.write(f"**Role:** {role_name} ({job_level})")
    st.write(f"**Purpose:** {role_purpose}")
    st.write(f"**Benchmark:** {', '.join(selected_names)}")

    # ===================================================================
    # 6️⃣ PANGGIL FUNCTION SUPABASE
    # ===================================================================
    try:
        data = supabase.rpc("get_talent_match_results").execute()
        df = pd.DataFrame(data.data)
    except Exception as e:
        st.error(f"❌ Error function SQL: {e}")
        st.stop()

    if df.empty:
        st.warning("⚠️ Tidak ada hasil match ditemukan.")
        st.stop()

    # ===================================================================
    # 7️⃣ TAMPILKAN HASIL LENGKAP (DENGAN FILTER)
    # ===================================================================
    st.subheader("🏆 Ranked Talent List (Top Matches)")

    # Pastikan nama kolom lowercase agar konsisten
    df.columns = [c.strip().lower() for c in df.columns]

    expected_columns = [
        "employee_id", "fullname", "directorate", "position_name", "grade",
        "tgv_name", "tv_name", "baseline_score", "user_score",
        "tv_match_rate", "tgv_match_rate", "final_match_rate"
    ]

    # Jika kolom tidak sesuai, tampilkan info untuk debugging
    missing_cols = [c for c in expected_columns if c not in df.columns]
    if missing_cols:
        st.warning(f"⚠️ Kolom berikut tidak ditemukan di hasil SQL: {missing_cols}")

    df_sorted = df.sort_values("final_match_rate", ascending=False)
    
    # <-- START PENAMBAHAN FITUR FILTER -->
    
    # Dapatkan daftar unik karyawan yang sudah diurutkan
    top_employees = df_sorted['employee_id'].unique()

    # Buat widget radio
    filter_option = st.radio(
        "Tampilkan Karyawan Teratas:",
        options=["Top 10", "Top 50", "Top 100", "Tampilkan Semua"],
        horizontal=True,
        index=0  # Default ke "Top 10"
    )

    # Tentukan jumlah N karyawan yang akan ditampilkan
    if filter_option == "Top 10":
        n_top = 10
    elif filter_option == "Top 50":
        n_top = 50
    elif filter_option == "Top 100":
        n_top = 100
    else: # "Tampilkan Semua"
        n_top = len(top_employees)

    # Ambil ID karyawan yang akan ditampilkan
    employees_to_show = top_employees[:n_top]
    
    # Filter DataFrame utama untuk hanya menyertakan karyawan yang dipilih
    df_filtered = df_sorted[df_sorted['employee_id'].isin(employees_to_show)]

    # <-- END PENAMBAHAN FITUR FILTER -->

    # Tampilkan DataFrame yang sudah difilter
    st.dataframe(df_filtered[expected_columns], use_container_width=True)


    # ===================================================================
    # 8️⃣ VISUALISASI
    # ===================================================================
    st.subheader("📊 Dashboard Match Overview")
    col1, col2 = st.columns(2)

    with col1:
        st.write("Distribusi Final Match Rate")
        fig, ax = plt.subplots()
        # Visualisasi ini tetap menggunakan df_sorted (data utuh) agar distribusi terlihat penuh
        sns.histplot(df_sorted["final_match_rate"], bins=10, kde=True, color="skyblue", ax=ax)
        st.pyplot(fig)

    with col2:
        st.write("Rata-rata TGV Match (Top 10 Talent)")
        if "tgv_name" in df.columns:
            # Visualisasi ini tetap hardcoded Top 10 sesuai labelnya
            top_10 = df_sorted.head(10)["employee_id"]
            df_top10 = df[df["employee_id"].isin(top_10)]
            avg_tgv = df_top10.groupby("tgv_name")["tgv_match_rate"].mean().reset_index()
            fig2, ax2 = plt.subplots()
            sns.barplot(data=avg_tgv, y="tgv_name", x="tgv_match_rate", ax=ax2)
            st.pyplot(fig2)

    # ===================================================================
    # 9️⃣ FITUR AI GOOGLE GEMINI 2.5
    # ===================================================================
    st.subheader("🤖 AI Talent Insights")

    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
    MODEL = "gemini-2.5-flash"

    def call_gemini(prompt):
        if not GOOGLE_API_KEY:
            return "[AI Error: GOOGLE_API_KEY tidak ditemukan]"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GOOGLE_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
        if res.status_code != 200:
            return f"[AI Error {res.status_code}] {res.text}"
        data = res.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except:
            return "[AI tidak mengembalikan hasil]"

    # Siapkan konteks AI
    # AI tetap menggunakan df_sorted (data utuh) untuk insight
    top_candidates = df_sorted.head(3).to_dict("records")
    tgv_summary = df.groupby("tgv_name")["tgv_match_rate"].mean().sort_values(ascending=False).to_dict()

    tgv_text = "\n".join([f"- {k}: {v:.1f}%" for k, v in tgv_summary.items()])
    candidates_text = "\n".join([f"{i+1}. {c['fullname']} ({c['final_match_rate']:.1f}%)" for i, c in enumerate(top_candidates)])

    prompt_profile = f"""
Buatkan profil pekerjaan untuk role {role_name} dengan tujuan {role_purpose}.
Gunakan data berikut:
{tgv_text}
Tuliskan dalam 3 bagian:
1. Job Requirements
2. Job Description
3. Key Competencies
"""

    prompt_formula = f"""
Dari data TGV berikut:
{tgv_text}
Buatkan rumus 'Success Formula' dengan bobot yang masuk akal seperti:
SuccessScore = 0.4*TGV_A + 0.3*TGV_B + 0.3*TGV_C
Sertakan penjelasan singkat.
"""

    prompt_candidates = f"""
Berikut 3 kandidat terbaik:
{candidates_text}
Berikan alasan singkat kenapa mereka cocok untuk role {role_name}.
"""

    with st.expander("🧠 AI-Generated Job Profile", expanded=True):
        st.write(call_gemini(prompt_profile))

    with st.expander("⚖️ AI Success Formula"):
        st.write(call_gemini(prompt_formula))

    with st.expander("🏆 AI Candidate Insights"):
        st.write(call_gemini(prompt_candidates))

    st.success("✅ Semua fitur berjalan dengan baik!")
