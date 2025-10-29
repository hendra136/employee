import streamlit as st
from supabase import create_client, Client as SupabaseClient
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import google.genai as genai # ====> Tambahan untuk AI Gemini

# =======================================================================
# 1️⃣ KONEKSI SUPABASE
# =======================================================================
st.set_page_config(layout="wide", page_title="Talent Match Intelligence System")
st.title("🚀 Talent Match Intelligence System")
st.write("Aplikasi ini membantu menemukan talenta internal yang cocok dengan profil benchmark.")

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Gagal menghubungkan ke Supabase: {e}")
    st.stop()

# =======================================================================
# 2️⃣ FUNGSI AMBIL DATA EMPLOYEE
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
    st.error("Gagal memuat daftar karyawan dari database.")
    st.stop()

# =======================================================================
# 3️⃣ FORM INPUT BENCHMARK
# =======================================================================
with st.form(key="benchmark_form"):
    st.header("1️⃣ Role Information")
    role_name_input = st.text_input("Role Name", placeholder="Contoh: Data Analyst")
    job_level_input = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose_input = st.text_area("Role Purpose", placeholder="Tuliskan tujuan peran ini...")

    st.header("2️⃣ Employee Benchmarking")
    employee_names_options = list(employee_dict.values())
    selected_benchmark_names = st.multiselect(
        "Pilih Karyawan Benchmark (minimal 1, maksimal 3)",
        options=employee_names_options,
        max_selections=3
    )
    submit_button = st.form_submit_button("✨ Find Matches")

# =======================================================================
# 4️⃣ LOGIKA SAAT SUBMIT
# =======================================================================
if submit_button:
    if not role_name_input or not job_level_input or not role_purpose_input or not selected_benchmark_names:
        st.error("❌ Semua field wajib diisi!")
        st.stop()

    st.info("🔄 Menyimpan benchmark dan menjalankan analisis...")

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

    st.success("✅ Benchmark berhasil disimpan!")
    st.subheader("📄 Role Profile Summary")
    st.write(f"**Role Name:** {role_name_input}")
    st.write(f"**Job Level:** {job_level_input}")
    st.write(f"**Role Purpose:** {role_purpose_input}")
    st.write(f"**Benchmark Employees:** {', '.join(selected_benchmark_names)}")

    # =======================================================================
    # 5️⃣ AMBIL DATA HASIL SQL
    # =======================================================================
    try:
        data_response = supabase.rpc("get_talent_match_results").execute()

        if not data_response or not data_response.data:
            st.warning("⚠️ Tidak ada hasil dari function 'get_talent_match_results'.")
            st.stop()

        df_results = pd.DataFrame(data_response.data)
    except Exception as e:
        st.error(f"❌ Error menjalankan function 'get_talent_match_results': {e}")
        st.stop()

    # =======================================================================
    # 6️⃣ TAMPILKAN HASIL & DASHBOARD
    # =======================================================================
    if not df_results.empty:
        st.subheader("🏆 Ranked Talent List (Top Matches)")

        df_ranked = df_results.drop_duplicates(subset=['employee_id']).sort_values(
            by="final_match_rate", ascending=False
        )

        expected_cols = ['fullname', 'position_name', 'directorate', 'grade', 'final_match_rate']
        for col in expected_cols:
            if col not in df_ranked.columns:
                st.warning(f"Kolom '{col}' tidak ada di hasil SQL.")

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

        # Chart 1: Distribusi Final Match Rate
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Distribusi Final Match Rate**")
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            sns.histplot(df_ranked['final_match_rate'].dropna(), kde=True, bins=15, color='skyblue', ax=ax1)
            ax1.set_xlabel("Final Match Rate (%)")
            ax1.set_ylabel("Jumlah Karyawan")
            st.pyplot(fig1)

        # Chart 2: Rata-rata TGV Match
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

    # =======================================================================
    # 7️⃣ FITUR AI — GOOGLE GEMINI
    # =======================================================================
    st.header("🤖 AI Talent Insights")

    # Konfigurasi koneksi AI
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except Exception as e:
        st.warning(f"⚠️ Tidak dapat mengkonfigurasi Google Gemini: {e}")


    def generate_ai_output(prompt_text):
        """Fungsi panggil AI Gemini"""
        try:
            client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
            model_name = "gemini-1.5-flash"  # ✅ Model terbaru
    
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
    
            ai_text = response.output_text.strip() if hasattr(response, "output_text") else str(response)
            return ai_text
        except Exception as e:
            return f"[AI Error] {e}"

    # AI Output 1 — Job Profile
    st.subheader("🧠 AI-Generated Job Profile")
    job_prompt = f"""
    Buatkan profil pekerjaan singkat untuk role '{role_name_input}' level '{job_level_input}'.
    Sertakan: deskripsi pekerjaan, kompetensi utama, dan kebutuhan keahlian.
    Bahasa: Indonesia.
    """
    st.write(generate_ai_output(job_prompt))

    # AI Output 2 — Success Formula
    st.subheader("⚖️ AI Success Formula")
    success_prompt = f"""
    Berdasarkan karakteristik top performer di role '{role_name_input}', 
    jelaskan formula sukses (skill, mindset, dan perilaku utama) dalam Bahasa Indonesia.
    """
    st.write(generate_ai_output(success_prompt))

    # AI Output 3 — Candidate Insights
    st.subheader("🏆 AI Candidate Insights")
    candidate_prompt = f"""
    Analisis bagaimana 3 kandidat teratas cocok dengan role '{role_name_input}' 
    dan berikan area pengembangan yang perlu diperbaiki.
    Bahasa: Indonesia.
    """
    st.write(generate_ai_output(candidate_prompt))
