# ================================================================
# 🚀 Talent Match Intelligence System — FINAL VERSION
# Terintegrasi Supabase + AI Gemini
# ================================================================

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from supabase import create_client, Client
import google.generativeai as genai

# ================================================================
# 1️⃣ KONEKSI SUPABASE
# ================================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================================================================
# 2️⃣ KONFIGURASI GOOGLE GEMINI AI
# ================================================================
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    AI_ENABLED = True
except Exception as e:
    st.error(f"⚠️ Tidak dapat mengkonfigurasi Google Gemini: {e}")
    AI_ENABLED = False

# ================================================================
# 3️⃣ HEADER
# ================================================================
st.set_page_config(page_title="Talent Match Intelligence System", layout="wide")
st.title("🚀 Talent Match Intelligence System")
st.caption("Smart benchmarking & AI insights for talent evaluation")

# ================================================================
# 4️⃣ INPUT FORM
# ================================================================
st.header("📋 Step 3 - Build the AI Talent App & Dashboard")

with st.form("job_form"):
    col1, col2 = st.columns(2)
    with col1:
        role_name = st.text_input("Role Name", "Data Analyst")
        job_level = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    with col2:
        role_purpose = st.text_area("Role Purpose", "Analis penjualan dan performa bisnis perusahaan")

    benchmark_employees = st.multiselect(
        "Employee Benchmarking (Minimal 1 - Maks 3)",
        [emp["fullname"] for emp in supabase.table("employees").select("fullname").execute().data],
        default=None
    )

    submit = st.form_submit_button("✨ Find Matches")

# ================================================================
# 5️⃣ KETIKA TOMBOL DIKLIK
# ================================================================
if submit:
    if not benchmark_employees:
        st.warning("Pilih minimal satu benchmark employee terlebih dahulu.")
    else:
        st.success("✅ Benchmark berhasil disimpan!")

        # ============================================================
        # 6️⃣ AMBIL DATA HASIL DARI FUNCTION SUPABASE
        # ============================================================
        try:
            result = supabase.rpc("get_talent_match_results").execute()
            df_results = pd.DataFrame(result.data)
        except Exception as e:
            st.error(f"❌ Error menjalankan function 'get_talent_match_results': {e}")
            st.stop()

        # ============================================================
        # 7️⃣ DEBUG & RE-CALIBRATE NILAI
        # ============================================================
        if not df_results.empty:
            df_results["final_match_rate"] = df_results["final_match_rate"].fillna(0)
            df_results["tgv_match_rate"] = df_results["tgv_match_rate"].fillna(0)
            df_results["tv_match_rate"] = df_results["tv_match_rate"].fillna(0)

            # Ranking top talent berdasarkan Final Match Rate
            df_ranked = (
                df_results.groupby(["employee_id", "fullname", "position_name", "directorate", "grade"])
                .agg({"final_match_rate": "mean"})
                .reset_index()
                .sort_values("final_match_rate", ascending=False)
            )

            st.subheader("🏆 Ranked Talent List (Top Matches)")
            st.dataframe(df_ranked.head(10), use_container_width=True)

            # ========================================================
            # 8️⃣ VISUALISASI DISTRIBUSI MATCH RATE
            # ========================================================
            st.subheader("📊 Distribution of Final Match Rate")
            fig, ax = plt.subplots()
            ax.hist(df_ranked["final_match_rate"], bins=10)
            ax.set_xlabel("Final Match Rate (%)")
            ax.set_ylabel("Frequency")
            ax.set_title("Distribution of Talent Match Rate")
            st.pyplot(fig)

            # ========================================================
            # 9️⃣ VISUALISASI: TOP 10 TGV Match Rate
            # ========================================================
            st.subheader("🌟 Top 10 Average TGV Match Rate")
            tgv_avg = (
                df_results.groupby("tgv_name")["tgv_match_rate"]
                .mean()
                .reset_index()
                .sort_values("tgv_match_rate", ascending=False)
                .head(10)
            )
            fig2, ax2 = plt.subplots()
            ax2.barh(tgv_avg["tgv_name"], tgv_avg["tgv_match_rate"])
            ax2.invert_yaxis()
            ax2.set_xlabel("Average Match Rate (%)")
            ax2.set_title("Top 10 TGV Match Rate")
            st.pyplot(fig2)

            # ========================================================
            # 🔟 BAGIAN AI — GENERATE TALENT INSIGHTS
            # ========================================================
            st.subheader("🤖 AI Talent Insights")

            # --- Fungsi generate AI output ---
            def generate_ai_output(prompt_text):
                """Memanggil Google Gemini AI untuk membuat teks analisis"""
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(prompt_text)
                    return response.text
                except Exception as e:
                    return f"[AI Error] {e}"

            if AI_ENABLED:
                with st.spinner("🧠 Generating AI insights..."):
                    try:
                        # 1️⃣ Job Profile
                        prompt_profile = f"""
                        Buatkan deskripsi pekerjaan untuk role {role_name} dengan level {job_level}.
                        Sertakan job requirements, job description, dan key competencies.
                        Role purpose: {role_purpose}.
                        """
                        ai_job_profile = generate_ai_output(prompt_profile)
                        st.markdown("### 🧠 AI-Generated Job Profile")
                        st.markdown(ai_job_profile)

                        # 2️⃣ Success Formula
                        prompt_formula = f"""
                        Berdasarkan hasil match rate berikut:
                        {df_ranked.head(5).to_markdown()},
                        buatkan analisis mengapa karyawan ini unggul dan faktor sukses utama mereka.
                        """
                        ai_success_formula = generate_ai_output(prompt_formula)
                        st.markdown("### ⚖️ AI Success Formula")
                        st.markdown(ai_success_formula)

                        # 3️⃣ Candidate Insights
                        prompt_candidate = f"""
                        Dari data top 5 berikut:
                        {df_ranked.head(5).to_markdown()},
                        berikan rekomendasi siapa kandidat paling cocok dan alasan singkatnya.
                        """
                        ai_candidate = generate_ai_output(prompt_candidate)
                        st.markdown("### 🏆 AI Candidate Insights")
                        st.markdown(ai_candidate)

                    except Exception as e:
                        st.error(f"[AI Error] {e}")
            else:
                st.warning("🤖 AI belum aktif atau gagal dikonfigurasi. Periksa API Key di secrets.toml.")
        else:
            st.warning("⚠️ Tidak ada hasil data dari fungsi SQL.")
