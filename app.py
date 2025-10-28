# app.py (versi: enforce benchmark rating 5 di tahun terakhir)
import streamlit as st
from supabase import create_client, Client as SupabaseClient
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(layout="wide", page_title="Talent Match Intelligence System")

# -----------------------
# 1) CONNECT TO SUPABASE
# -----------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Gagal terhubung ke Supabase: {e}")
    st.stop()

# -----------------------
# 2) Helper: ambil high-performers (rating==5 di tahun terbaru)
# -----------------------
@st.cache_data(ttl=600)
def fetch_high_performers(latest_only=True):
    """Return dict employee_id -> fullname for employees who have rating==5 in the latest year.
       If none found and latest_only True, returns empty dict.
    """
    try:
        resp = supabase.table('performance_yearly').select('employee_id, rating, year').execute()
        if not resp.data:
            return {}  # no performance data
        df = pd.DataFrame(resp.data)
        # ensure proper dtypes
        if 'year' in df.columns:
            df['year'] = pd.to_numeric(df['year'], errors='coerce')
        # get latest year available
        latest_year = int(df['year'].max())
        df_latest = df[df['year'] == latest_year]
        # keep only rating == 5
        df_high = df_latest[df_latest['rating'] == 5]
        high_ids = df_high['employee_id'].unique().tolist()
        if not high_ids:
            return {}  # nothing found for latest year
        # fetch names for these ids
        emp_resp = supabase.table('employees').select('employee_id, fullname').in_('employee_id', high_ids).execute()
        if not emp_resp.data:
            return {}
        emp_df = pd.DataFrame(emp_resp.data)
        emp_df = emp_df.drop_duplicates(subset=['employee_id'])
        emp_df = emp_df.sort_values('fullname')
        return {row['employee_id']: row['fullname'] for _, row in emp_df.iterrows()}
    except Exception as e:
        # silent fail to UI: return {}
        return {}

# fallback: full employees list (used only if no high-performers found)
@st.cache_data(ttl=600)
def fetch_all_employees():
    try:
        resp = supabase.table('employees').select('employee_id, fullname').execute()
        if not resp.data:
            return {}
        df = pd.DataFrame(resp.data).drop_duplicates(subset=['employee_id']).sort_values('fullname')
        return {row['employee_id']: row['fullname'] for _, row in df.iterrows()}
    except Exception:
        return {}

# -----------------------
# 3) BUILD UI FORM
# -----------------------
st.title("🚀 Talent Match Intelligence System")
st.write("Pilih benchmark (karyawan *rating=5* di tahun terbaru).")

# try to get high performers
high_emp = fetch_high_performers()
use_fallback = False
if not high_emp:
    st.warning("Tidak ditemukan top-performer (rating=5) di tahun terakhir. Menyediakan seluruh daftar karyawan sebagai fallback.")
    high_emp = fetch_all_employees()
    use_fallback = True

with st.form(key="benchmark_form"):
    st.header("1️⃣ Role Information")
    role_name_input = st.text_input("Role Name", placeholder="Contoh: Data Analyst")
    job_level_input = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose_input = st.text_area("Role Purpose", placeholder="1-2 kalimat tujuan utama peran...")

    st.header("2️⃣ Employee Benchmarking")
    st.write("Hanya karyawan dengan rating=5 (tahun terakhir) yang ditampilkan. Jika kosong, tampilkan semua (fallback).")
    employee_names_options = list(high_emp.values())
    selected_benchmark_names = st.multiselect(
        "Pilih Karyawan Benchmark (minimal 1, maksimal 3)",
        options=employee_names_options,
        max_selections=3
    )

    submit_button = st.form_submit_button("✨ Find Matches")

# -----------------------
# 4) ON SUBMIT: VALIDATION + SAVE
# -----------------------
if submit_button:
    if not role_name_input or not job_level_input or not role_purpose_input or not selected_benchmark_names:
        st.error("❌ Semua field wajib diisi dan pilih minimal 1 benchmark.")
        st.stop()

    # map names back to ids
    name_to_id = {v: k for k, v in high_emp.items()}
    selected_ids = []
    for name in selected_benchmark_names:
        if name in name_to_id:
            selected_ids.append(name_to_id[name])
        else:
            # fallback: if user selected name from fallback list, try fetch_all_employees map
            all_map = fetch_all_employees()
            if name in all_map.values():
                # find id by name
                for k, v in all_map.items():
                    if v == name:
                        selected_ids.append(k)
                        break

    # Validate again that selected employees have rating==5 in latest year (if high-performer mode)
    if not use_fallback:
        # recheck via performance_yearly
        try:
            perf_resp = supabase.table('performance_yearly').select('employee_id, rating, year').in_('employee_id', selected_ids).execute()
            perf_df = pd.DataFrame(perf_resp.data) if perf_resp.data else pd.DataFrame()
            latest_year = int(perf_df['year'].max()) if not perf_df.empty else None
            invalid = []
            if latest_year is not None:
                for emp in selected_ids:
                    r = perf_df[(perf_df['employee_id'] == emp) & (perf_df['year'] == latest_year)]
                    if r.empty or int(r.iloc[0]['rating']) != 5:
                        invalid.append(emp)
            if invalid:
                st.error("❌ Salah satu benchmark tidak memiliki rating=5 di tahun terakhir. Pilih benchmark lain.")
                st.stop()
        except Exception:
            st.error("❌ Gagal memverifikasi rating benchmark. Periksa data performance_yearly.")
            st.stop()

    # Save benchmark to table
    try:
        insert_response = supabase.table('talent_benchmarks').insert({
            "role_name": role_name_input,
            "job_level": job_level_input,
            "role_purpose": role_purpose_input,
            "selected_talent_ids": selected_ids
        }).execute()

        # debug minimal: only show if error
        if hasattr(insert_response, 'error') and insert_response.error:
            st.error(f"Error menyimpan benchmark: {insert_response.error.message if insert_response.error else insert_response}")
            st.stop()
    except Exception as e:
        st.error(f"Exception saat menyimpan benchmark: {e}")
        st.stop()

    st.success("✅ Benchmark tersimpan. Menjalankan analisis (get_talent_match_results)...")

    # -----------------------
    # 5) CALL RPC (function)
    # -----------------------
    try:
        data_response = supabase.rpc('get_talent_match_results').execute()
        if not data_response or not data_response.data:
            st.warning("⚠️ Function tidak mengembalikan data. Pastikan function sudah di-deploy dan owner/execute permission sudah diset.")
            st.stop()
        df_results = pd.DataFrame(data_response.data)
    except Exception as e:
        st.error(f"Error memanggil get_talent_match_results: {e}")
        st.stop()

    # -----------------------
    # 6) SHOW RANKING + VISUALS (sederhana)
    # -----------------------
    st.header("🏆 Ranked Talent List (Top Matches)")
    if 'final_match_rate' not in df_results.columns:
        st.error("Kolom final_match_rate tidak ditemukan di hasil function.")
        st.stop()

    df_ranked = df_results.drop_duplicates(subset=['employee_id']).sort_values(by='final_match_rate', ascending=False)
    # show top 20
    display_cols = ['fullname', 'position_name', 'directorate', 'grade', 'final_match_rate']
    for c in display_cols:
        if c not in df_ranked.columns:
            df_ranked[c] = None

    st.dataframe(
        df_ranked[display_cols].head(20),
        use_container_width=True,
        hide_index=True,
        column_config={"final_match_rate": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)}
    )

    # small charts
    st.subheader("📈 Distribusi Final Match Rate")
    fig, ax = plt.subplots(figsize=(8,4))
    sns.histplot(df_ranked['final_match_rate'].dropna(), kde=True, ax=ax, bins=15)
    ax.set_xlabel("Final Match Rate (%)")
    st.pyplot(fig)

    st.success("Analisis selesai ✅")
