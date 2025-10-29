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

    # =========================
    # DEBUG: Mulai blok debugging (tidak mengubah logic lain)
    # =========================
    st.markdown("### 🐞 Debugging Info (AUTOMATIS)")
    try:
        # 1. Tampilkan semua employees (konfirmasi)
        st.write("🔎 [DEBUG] Employees (sample 10)", list(employees.items())[:10])

        # 2. Cek isi tabel talent_benchmarks (terbaru 5)
        try:
            res_bench_all = supabase.table("talent_benchmarks").select("*").order("job_vacancy_id", desc=True).limit(10).execute()
            st.write("🔎 [DEBUG] talent_benchmarks (latest 10)", res_bench_all.data)
        except Exception as e:
            st.error(f"🔎 [DEBUG] Gagal fetch talent_benchmarks: {e}")

        # 3. Ambil latest vacancy (mirip CTE Latest_Vacancy)
        try:
            latest_vac = supabase.table("talent_benchmarks").select("*").order("job_vacancy_id", desc=True).limit(1).execute()
            latest_vacancy = latest_vac.data[0] if latest_vac.data else None
            st.write("🔎 [DEBUG] Latest Vacancy (CTE emulation):", latest_vacancy)
            if latest_vacancy:
                st.write("🔎 [DEBUG] selected_talent_ids from latest vacancy:", latest_vacancy.get("selected_talent_ids"))
        except Exception as e:
            st.error(f"🔎 [DEBUG] Error getting latest vacancy: {e}")

        # 4. Cek competencies_yearly untuk year=2025 (sample)
        try:
            res_comp_2025 = supabase.table("competencies_yearly").select("employee_id, pillar_code, score, year").eq("year", 2025).limit(50).execute()
            st.write("🔎 [DEBUG] competencies_yearly (2025 sample 50 rows):", res_comp_2025.data)
            # juga cek count
            cnt_comp = supabase.table("competencies_yearly").select("employee_id", count="exact").eq("year", 2025).execute()
            st.write("🔎 [DEBUG] Count competencies_yearly for 2025:", cnt_comp.count if hasattr(cnt_comp, 'count') else "N/A")
        except Exception as e:
            st.error(f"🔎 [DEBUG] Error fetching competencies_yearly: {e}")

        # 5. Cek strengths (sample)
        try:
            res_strengths = supabase.table("strengths").select("employee_id, theme, rank").limit(100).execute()
            st.write("🔎 [DEBUG] strengths (sample 100):", res_strengths.data)
        except Exception as e:
            st.error(f"🔎 [DEBUG] Error fetching strengths: {e}")

        # 6. Cek dim tables apakah ada mapping id yang invalid (sample counts)
        try:
            dim_pos = supabase.table("dim_positions").select("position_id", count="exact").execute()
            dim_grade = supabase.table("dim_grades").select("grade_id", count="exact").execute()
            dim_dir = supabase.table("dim_directorate").select("directorate_id", count="exact").execute()
            st.write("🔎 [DEBUG] dim_positions count:", dim_pos.count if hasattr(dim_pos, 'count') else "N/A")
            st.write("🔎 [DEBUG] dim_grades count:", dim_grade.count if hasattr(dim_grade, 'count') else "N/A")
            st.write("🔎 [DEBUG] dim_directorate count:", dim_dir.count if hasattr(dim_dir, 'count') else "N/A")
        except Exception as e:
            st.error(f"🔎 [DEBUG] Error fetching dim tables: {e}")

    except Exception as e:
        st.error(f"🔎 [DEBUG] Error in debug block: {e}")

    # =========================
    # 6️⃣ FUNGSI SQL SUPABASE (ASLINYA)
    # =========================
    try:
        data = supabase.rpc("get_talent_match_results").execute()

        # DEBUG: tunjukkan hasil raw RPC sebelum menjadi DataFrame
        st.write("🔎 [DEBUG] RPC raw result (first 5 elements)", data.data[:5] if getattr(data, "data", None) else data.data)

        df = pd.DataFrame(data.data)

        # DEBUG: informasikan shape, columns, dtypes
        st.write("🔎 [DEBUG] DataFrame shape:", df.shape)
        st.write("🔎 [DEBUG] DataFrame columns (raw):", df.columns.tolist())
        try:
            st.write("🔎 [DEBUG] DataFrame dtypes:", df.dtypes.to_dict())
        except:
            pass
    except Exception as e:
        st.error(f"❌ Error function SQL: {e}")
        st.stop()

    if df.empty:
        st.warning("⚠️ Tidak ada hasil match ditemukan.")
        # Tambahkan debug tambahan mengapa kosong: periksa apakah selected_ids exist & apakah competencies/strength kosong
        try:
            # Periksa kembali last benchmark dan selected_ids
            last_bench = supabase.table("talent_benchmarks").select("*").order("job_vacancy_id", desc=True).limit(1).execute()
            st.write("🔎 [DEBUG] Re-check latest benchmark:", last_bench.data)
        except Exception as e:
            st.error(f"🔎 [DEBUG] Error re-checking benchmark: {e}")

        try:
            # Cek sample competencies dan strengths counts
            comp_cnt = supabase.table("competencies_yearly").select("employee_id", count="exact").eq("year", 2025).execute()
            str_cnt = supabase.table("strengths").select("employee_id", count="exact").execute()
            st.write("🔎 [DEBUG] competencies_yearly count (2025):", comp_cnt.count if hasattr(comp_cnt, 'count') else "N/A")
            st.write("🔎 [DEBUG] strengths count:", str_cnt.count if hasattr(str_cnt, 'count') else "N/A")
        except Exception as e:
            st.error(f"🔎 [DEBUG] Error counting competencies/strengths: {e}")

        st.stop()

    #DEBUG
    #st.write(df.head())
    #st.write(df.columns.tolist())

    # ===================================================================
    # ✅ NORMALISASI DATA AGAR NONE TIDAK MUNCUL
    # ===================================================================
    # Pastikan kolom tidak sensitif terhadap huruf besar
    df.columns = [c.strip().lower() for c in df.columns]

    # Kadang Supabase mengembalikan null walau ada data
    for col in ["position_name", "directorate", "grade"]:
        if col in df.columns:
            df[col] = df[col].fillna("").replace("None", "").replace("null", "")
            df[col] = df[col].apply(lambda x: str(x).strip() if x else "Data Tidak Ditemukan")

    # ===================================================================
    # 7️⃣ HASIL RANK
    # ===================================================================
    st.subheader("🏆 Ranked Talent List (Top Matches)")

    df_sorted = df.drop_duplicates(subset=["employee_id"]).sort_values("final_match_rate", ascending=False)
    df_display = df_sorted[["fullname", "position_name", "directorate", "grade", "final_match_rate"]]

    st.dataframe(df_display.head(20), use_container_width=True)

    # ===================================================================
    # 8️⃣ VISUALISASI
    # ===================================================================
    st.subheader("📊 Dashboard Match Overview")
    col1, col2 = st.columns(2)

    with col1:
        st.write("Distribusi Final Match Rate")
        fig, ax = plt.subplots()
        sns.histplot(df_sorted["final_match_rate"], bins=10, kde=True, color="skyblue", ax=ax)
        st.pyplot(fig)

    with col2:
        st.write("Rata-rata TGV Match (Top 10 Talent)")
        if "tgv_name" in df.columns:
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
