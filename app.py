import streamlit as st
import pandas as pd
from supabase import create_client, Client
import google.generativeai as genai

# ==============================
# 1️⃣ KONFIGURASI DASAR
# ==============================
st.set_page_config(page_title="🚀 Talent Match Intelligence System", layout="wide")

url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

genai.configure(api_key=st.secrets["gemini"]["api_key"])
MODEL = "gemini-2.5-flash"

# ==============================
# 2️⃣ FUNGSI BANTUAN
# ==============================

def get_talent_match_results():
    """Ambil data hasil kecocokan dari Supabase function"""
    try:
        response = supabase.rpc("get_talent_match_results").execute()
        if not response.data:
            st.warning("⚠️ Tidak ada data hasil kecocokan ditemukan.")
            return pd.DataFrame()
        df = pd.DataFrame(response.data)

        # --- Normalisasi kolom agar sesuai ---
        df.columns = [c.strip().lower() for c in df.columns]

        rename_map = {
            "fullname": "fullname",
            "position": "position_name",
            "positionname": "position_name",
            "position_name": "position_name",
            "grade": "grade",
            "grade_name": "grade",
            "directorate": "directorate",
            "directorate_name": "directorate",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

        # Pastikan kolom wajib selalu ada
        for col in ["fullname", "position_name", "grade", "directorate", "final_match_rate"]:
            if col not in df.columns:
                df[col] = None

        # Bersihkan nilai kosong
        df["position_name"] = df["position_name"].fillna("Tidak Ditemukan")
        df["grade"] = df["grade"].fillna("Tidak Ditemukan")
        df["directorate"] = df["directorate"].fillna("Tidak Ditemukan")

        return df
    except Exception as e:
        st.error(f"❌ Error mengambil data match results: {e}")
        return pd.DataFrame()


def generate_ai_summary(prompt_text: str) -> str:
    """Gunakan Google Gemini untuk membuat ringkasan AI"""
    try:
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(prompt_text)
        return response.text
    except Exception as e:
        return f"[AI Error] {e}"


# ==============================
# 3️⃣ UI: INPUT DATA
# ==============================
st.title("🚀 Talent Match Intelligence System")
st.write("Gunakan sistem ini untuk menganalisis kecocokan talent berdasarkan benchmark & insight AI.")

with st.form("role_form"):
    st.subheader("📋 Role Information")
    role_name = st.text_input("Role Name", placeholder="Contoh: Data Analyst")
    job_level = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose = st.text_area("Role Purpose", placeholder="Tuliskan tujuan dari role ini...")

    st.subheader("👥 Employee Benchmarking")
    benchmark_employees = st.multiselect(
        "Pilih Benchmark Employee (1–3 orang)",
        [r["fullname"] for r in supabase.table("employees").select("fullname").execute().data],
    )

    submitted = st.form_submit_button("✨ Find Matches")

# ==============================
# 4️⃣ LOGIKA UTAMA
# ==============================
if submitted:
    if not role_name or not benchmark_employees:
        st.warning("⚠️ Mohon lengkapi seluruh form terlebih dahulu.")
    else:
        st.success("✅ Benchmark berhasil disimpan!")

        st.markdown(f"""
        ### 📄 Role Profile Summary
        **Role Name:** {role_name}  
        **Job Level:** {job_level}  
        **Role Purpose:** {role_purpose}  
        **Benchmark Employees:** {", ".join(benchmark_employees)}
        """)

        # Ambil hasil match dari Supabase
        df_ranked = get_talent_match_results()
        if not df_ranked.empty:
            st.markdown("### 🏆 Ranked Talent List (Top Matches)")
            df_ranked["final_match_rate"] = df_ranked["final_match_rate"].fillna(0).astype(float)
            df_ranked = df_ranked.sort_values("final_match_rate", ascending=False)

            def progress_bar(rate):
                bar = "█" * int(rate / 10)
                return f"{bar} {rate:.1f}%"

            df_display = df_ranked[
                ["fullname", "position_name", "grade", "directorate", "final_match_rate"]
            ].copy()
            df_display["Match Rate"] = df_display["final_match_rate"].apply(progress_bar)
            st.dataframe(df_display, use_container_width=True)

            # ==============================
            # 5️⃣ AI INSIGHT (Gemini)
            # ==============================
            st.subheader("🤖 AI Talent Insights")

            with st.spinner("🔍 Menganalisis dengan Google Gemini..."):
                prompt_summary = f"""
                Buat ringkasan analisis AI tentang role {role_name} level {job_level}
                dengan tujuan: {role_purpose}.
                Berdasarkan hasil match rate berikut:
                {df_ranked.head(5).to_string(index=False)}
                """
                ai_summary = generate_ai_summary(prompt_summary)
                st.markdown(f"### 🧠 AI-Generated Summary\n{ai_summary}")

        else:
            st.warning("Tidak ada hasil match ditemukan.")
