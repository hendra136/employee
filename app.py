import streamlit as st
from supabase import create_client, Client as SupabaseClient
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests

# =======================================================================
# 1️⃣ SETUP APLIKASI
# =======================================================================
st.set_page_config(layout="wide", page_title="Talent Match Intelligence System")
st.title("🚀 Talent Match Intelligence System")
st.write("Aplikasi ini membantu menemukan talenta internal yang cocok dengan profil benchmark berdasarkan data karyawan dan AI insight.")

# =======================================================================
# 2️⃣ KONEKSI SUPABASE
# =======================================================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Gagal menghubungkan ke Supabase: {e}")
    st.stop()

# =======================================================================
# 3️⃣ AMBIL DAFTAR KARYAWAN
# =======================================================================
@st.cache_data(ttl=3600)
def get_employee_list():
    try:
        response = supabase.table('employees').select('employee_id, fullname').execute()
        if response.data:
            sorted_employees = sorted(response.data, key=lambda x: x['fullname'])
            return {emp['employee_id']: emp['fullname'] for emp in sorted_employees}
        else:
            st.warning("⚠️ Tidak ada data di tabel 'employees'. Pastikan tabel berisi data dan policy SELECT sudah benar.")
            return {}
    except Exception as e:
        st.error(f"❌ Error mengambil daftar karyawan: {e}")
        return {}

employee_dict = get_employee_list()
if not employee_dict:
    st.error("Gagal memuat daftar karyawan dari database. Periksa koneksi/nama tabel.")
    st.stop()

# =======================================================================
# 4️⃣ FORM INPUT BENCHMARK
# =======================================================================
with st.form(key="benchmark_form"):
    st.header("1️⃣ Role Information")
    role_name_input = st.text_input("Role Name", placeholder="Contoh: Data Analyst")
    job_level_input = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose_input = st.text_area("Role Purpose", placeholder="1-2 kalimat tujuan utama peran...")

    st.header("2️⃣ Employee Benchmarking")
    employee_names_options = list(employee_dict.values())
    selected_benchmark_names = st.multiselect(
        "Pilih Karyawan Benchmark (minimal 1, maksimal 3)",
        options=employee_names_options,
        max_selections=3
    )

    submit_button = st.form_submit_button("✨ Find Matches")

# =======================================================================
# 5️⃣ LOGIKA KETIKA FORM DIKIRIM
# =======================================================================
if submit_button:
    if not role_name_input or not job_level_input or not role_purpose_input or not selected_benchmark_names:
        st.error("❌ Semua field wajib diisi!")
        st.stop()

    st.info("🔄 Memproses benchmark dan menjalankan analisis...")

    # Simpan benchmark ke Supabase
    try:
        name_to_id_dict = {v: k for k, v in employee_dict.items()}
        selected_benchmark_ids = [name_to_id_dict[name] for name in selected_benchmark_names]

        insert_response = supabase.table('talent_benchmarks').insert({
            "role_name": role_name_input,
            "job_level": job_level_input,
            "role_purpose": role_purpose_input,
            "selected_talent_ids": selected_benchmark_ids
        }).execute()

        if not insert_response.data:
            st.error("❌ Gagal menyimpan benchmark. Periksa policy INSERT di tabel 'talent_benchmarks'.")
            st.stop()
    except Exception as e:
        st.error(f"❌ Error menyimpan benchmark: {e}")
        st.stop()

    # Tampilkan informasi benchmark
    st.success("✅ Benchmark berhasil disimpan!")
    st.subheader("📄 Role Profile Summary")
    st.write(f"**Role Name:** {role_name_input}")
    st.write(f"**Job Level:** {job_level_input}")
    st.write(f"**Role Purpose:** {role_purpose_input}")
    st.write(f"**Benchmark Employees:** {', '.join(selected_benchmark_names)}")

    # =======================================================================
    # 6️⃣ JALANKAN FUNCTION SQL DI SUPABASE
    # =======================================================================
    try:
        data_response = supabase.rpc("get_talent_match_results").execute()

        if not data_response or not data_response.data:
            st.warning("⚠️ Tidak ada hasil dari function 'get_talent_match_results'. Pastikan function-nya berjalan normal.")
            st.stop()

        df_results = pd.DataFrame(data_response.data)

    except Exception as e:
        st.error(f"❌ Error menjalankan function 'get_talent_match_results': {e}")
        st.stop()

    # =======================================================================
    # 7️⃣ TAMPILKAN HASIL RANKING
    # =======================================================================
    if not df_results.empty:
        st.subheader("🏆 Ranked Talent List (Top Matches)")

        if 'final_match_rate' in df_results.columns:
            df_ranked = df_results.drop_duplicates(subset=['employee_id']).sort_values(
                by="final_match_rate", ascending=False
            )
        else:
            st.error("Kolom 'final_match_rate' tidak ditemukan di hasil SQL.")
            st.stop()

        expected_cols = ['fullname', 'position_name', 'directorate', 'grade', 'final_match_rate']
        for col in expected_cols:
            if col not in df_ranked.columns:
                st.warning(f"Kolom '{col}' tidak ada di hasil. Periksa function SQL kamu.")

        st.dataframe(
            df_ranked[expected_cols].head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "final_match_rate": st.column_config.ProgressColumn(
                    "Match Rate", format="%.1f%%", min_value=0, max_value=100
                )
            }
        )

        # =======================================================================
        # 8️⃣ VISUALISASI DASHBOARD
        # =======================================================================
        st.subheader("📈 Talent Match Dashboard")
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Distribusi Final Match Rate**")
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            sns.histplot(df_ranked['final_match_rate'].dropna(), kde=True, bins=15, color='skyblue', ax=ax1)
            ax1.set_xlabel("Final Match Rate (%)")
            ax1.set_ylabel("Jumlah Karyawan")
            st.pyplot(fig1)

        with col2:
            st.write("**Rata-rata TGV Match (Top 10 Talent)**")
            if 'tgv_name' in df_results.columns:
                top_10 = df_ranked.head(10)['employee_id']
                df_top10 = df_results[df_results['employee_id'].isin(top_10)]
                tgv_avg = df_top10.groupby('tgv_name')['tgv_match_rate'].mean().reset_index().sort_values(
                    by='tgv_match_rate', ascending=False
                )
                fig2, ax2 = plt.subplots(figsize=(6, 4))
                sns.barplot(data=tgv_avg, y='tgv_name', x='tgv_match_rate', palette='coolwarm', ax=ax2)
                ax2.set_xlabel("Rata-rata Match Rate (%)")
                ax2.set_ylabel("TGV")
                ax2.set_xlim(0, 100)
                st.pyplot(fig2)
            else:
                st.info("Kolom 'tgv_name' belum ada di hasil SQL. Tambahkan di function jika ingin grafik ini muncul.")

        # =======================================================================
        # 9️⃣ FITUR AI (GOOGLE GENERATIVE LANGUAGE)
        # =======================================================================
        GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
        GOOGLE_AI_MODEL = st.secrets.get("GOOGLE_AI_MODEL", "gemini-2.5-flash")

        def panggil_ai(prompt: str):
            if not GOOGLE_API_KEY:
                return "[AI Error: GOOGLE_API_KEY tidak ditemukan di secrets]"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GOOGLE_AI_MODEL}:generateContent?key={GOOGLE_API_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
            if response.status_code != 200:
                return f"[AI Error {response.status_code}: {response.text}]"
            hasil = response.json()
            if "candidates" in hasil and len(hasil["candidates"]) > 0:
                return hasil["candidates"][0].get("output", "[AI: Tidak ada teks dihasilkan]")
            return "[AI: Tidak ada respons dari model]"

        st.markdown("---")
        st.header("🤖 AI Talent Insights")

        # Data untuk AI prompt
        if 'tgv_name' in df_results.columns and 'tgv_match_rate' in df_results.columns:
            tgv_avg = df_results.groupby('tgv_name')['tgv_match_rate'].mean().sort_values(ascending=False).to_dict()
        else:
            tgv_avg = {}

        df_sorted = df_results.sort_values(by='final_match_rate', ascending=False)
        top_candidates = df_sorted.head(3).to_dict('records')

        # Prompt AI
        tgv_text = "\n".join([f"- {k}: {v:.1f}%" for k, v in tgv_avg.items()])
        candidates_text = "\n".join([f"{i+1}. {c['fullname']} ({c['final_match_rate']:.1f}%)" for i, c in enumerate(top_candidates)])

        prompt_profile = f"""
Buatkan profil pekerjaan untuk jabatan {role_name_input} dengan tujuan: {role_purpose_input}.
Gunakan data berikut sebagai konteks:
{tgv_text}
Tuliskan dalam 3 bagian:
1. Job Requirements
2. Job Description
3. Key Competencies
"""

        prompt_formula = f"""
Dari data TGV berikut:
{tgv_text}
Buatkan rumus "Success Formula" berbobot seperti:
SuccessScore = 0.4*TGV_A + 0.3*TGV_B + 0.3*TGV_C
dan beri penjelasan singkat.
"""

        prompt_candidates = f"""
Berikut 3 kandidat terbaik:
{candidates_text}
Berikan alasan kenapa mereka cocok dengan posisi ini dalam 1 kalimat per orang.
"""

        # Tampilkan hasil AI
        with st.expander("🧠 AI-Generated Job Profile", expanded=True):
            st.write(panggil_ai(prompt_profile))

        with st.expander("⚖️ AI Success Formula", expanded=False):
            st.write(panggil_ai(prompt_formula))

        with st.expander("🏆 AI Candidate Insights", expanded=False):
            st.write(panggil_ai(prompt_candidates))

        st.success("✅ Semua sistem & fitur AI berjalan normal!")

    else:
        st.warning("⚠️ Tidak ada hasil untuk ditampilkan.")
