# app.py
import streamlit as st
from supabase import create_client, Client as SupabaseClient
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import json
from typing import Optional

# -------------------------
# Page config
# -------------------------
st.set_page_config(layout="wide", page_title="Talent Match Intelligence System")

# -------------------------
# Helper / Config
# -------------------------
SHOW_DEBUG_DEFAULT = False  # default debug collapsed

# -------------------------
# Load secrets and connect to Supabase
# -------------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    # optional google ai config
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
    GOOGLE_AI_MODEL = st.secrets.get("GOOGLE_AI_MODEL", "models/text-bison-001")
    DEBUG_MODE = bool(st.secrets.get("DEBUG", SHOW_DEBUG_DEFAULT))
except Exception as e:
    st.error("❌ Missing keys in .streamlit/secrets.toml or Streamlit Secrets. "
             "Required: SUPABASE_URL and SUPABASE_KEY. If you want AI: GOOGLE_API_KEY.")
    st.stop()

# Connect to Supabase
try:
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Gagal menghubungkan ke Supabase: {e}")
    st.stop()

# -------------------------
# Utility functions
# -------------------------
def call_google_text_api(prompt: str, model: str = "models/text-bison-001", api_key: Optional[str] = None, max_tokens=512):
    """Simple wrapper to call Google Vertex/Generative text endpoint via REST.
       NOTE: endpoint & payload may differ per Google product. Adjust if needed.
    """
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not provided")
    url = f"https://generativelanguage.googleapis.com/v1beta2/{model}:generateText"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    data = {
        "prompt": {"text": prompt},
        "maxOutputTokens": max_tokens
    }
    resp = requests.post(url, headers=headers, json=data, timeout=25)
    if resp.status_code != 200:
        raise RuntimeError(f"Google API error: {resp.status_code} {resp.text}")
    return resp.json()

@st.cache_data(ttl=3600)
def get_employee_list():
    """Return dict {employee_id: fullname} sorted by fullname"""
    try:
        response = supabase.table('employees').select('employee_id, fullname').execute()
        # debug: response object
        if hasattr(response, 'data') and response.data:
            sorted_employees = sorted(response.data, key=lambda x: x.get('fullname', ''))
            return {emp['employee_id']: emp['fullname'] for emp in sorted_employees}
        return {}
    except Exception as e:
        # don't stop app completely here; return empty
        st.error(f"Error mengambil daftar karyawan: {e}")
        return {}

def insert_benchmark(role_name, job_level, role_purpose, selected_ids):
    """Insert benchmark row into talent_benchmarks; returns response object"""
    try:
        resp = supabase.table('talent_benchmarks').insert({
            "role_name": role_name,
            "job_level": job_level,
            "role_purpose": role_purpose,
            "selected_talent_ids": selected_ids
        }).execute()
        return resp
    except Exception as e:
        return {"error": str(e)}

def run_rpc_talent_match():
    """Call RPC get_talent_match_results and return DataFrame or None"""
    try:
        resp = supabase.rpc("get_talent_match_results").execute()
        if hasattr(resp, 'data') and resp.data:
            df = pd.DataFrame(resp.data)
            return df, resp
        return pd.DataFrame(), resp
    except Exception as e:
        raise

# -------------------------
# UI: Title + Form
# -------------------------
st.title("🚀 Talent Match Intelligence System")
st.write("Aplikasi membantu menemukan talenta internal yang cocok dengan profil benchmark.")

with st.form(key="benchmark_form"):
    st.header("1️⃣ Role Information")
    role_name_input = st.text_input("Role Name", placeholder="Contoh: Data Analyst / Leadership")
    job_level_input = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose_input = st.text_area("Role Purpose", placeholder="1-2 kalimat tujuan utama peran...")

    # Employee selections
    st.header("2️⃣ Employee Benchmarking")
    employee_dict = get_employee_list()
    employee_names_options = list(employee_dict.values())
    selected_benchmark_names = st.multiselect(
        "Pilih Karyawan Benchmark (min 1, maks 3). Pilih karyawan dengan RATING = 5 untuk benchmark ideal.",
        options=employee_names_options,
        max_selections=3
    )
    submit_button = st.form_submit_button("✨ Find Matches")

# -------------------------
# After submit: process
# -------------------------
if submit_button:
    # validate
    if not role_name_input or not job_level_input or not role_purpose_input or not selected_benchmark_names:
        st.error("❌ Semua field wajib diisi!")
        st.stop()

    st.info("🔄 Memproses benchmark dan menjalankan analisis...")

    # Map selected names to employee_id
    name_to_id = {v: k for k, v in employee_dict.items()}
    selected_ids = [name_to_id[n] for n in selected_benchmark_names]

    # Insert benchmark (and handle RLS / errors)
    insert_resp = insert_benchmark(role_name_input, job_level_input, role_purpose_input, selected_ids)

    # Debug section (hidden by default)
    with st.expander("🔎 Debug (raw responses)"):
        st.write("DEBUG insert_response:", insert_resp)

    # check insert result
    if hasattr(insert_resp, 'error') and insert_resp.error:
        st.error(f"Error menyimpan benchmark: {insert_resp.error.message if hasattr(insert_resp.error,'message') else insert_resp.error}")
        st.stop()
    elif isinstance(insert_resp, dict) and insert_resp.get("error"):
        st.error(f"Error menyimpan benchmark: {insert_resp.get('error')}")
        st.stop()
    else:
        st.success("✅ Benchmark berhasil disimpan!")

    # Optional: generate small role summary via AI (if key available)
    if GOOGLE_API_KEY:
        try:
            prompt = f"Ringkas role berikut jadi 2-3 bullet singkat untuk internal HR:\nRole: {role_name_input}\nLevel: {job_level_input}\nPurpose: {role_purpose_input}\nBenchmark examples: {', '.join(selected_benchmark_names)}"
            ai_json = call_google_text_api(prompt, model=GOOGLE_AI_MODEL, api_key=GOOGLE_API_KEY)
            # parsing may vary by Google API version; attempt best-effort
            ai_text = ""
            if isinstance(ai_json, dict):
                # try common path
                content = ai_json.get('candidates') or ai_json.get('outputs') or ai_json.get('result')
                if content and isinstance(content, list):
                    # try to get text
                    ai_text = content[0].get('content') if isinstance(content[0], dict) else str(content[0])
                elif 'output' in ai_json and isinstance(ai_json['output'], dict):
                    ai_text = ai_json['output'].get('text','')
                else:
                    # fallback stringify
                    ai_text = json.dumps(ai_json)[:1000]
            else:
                ai_text = str(ai_json)[:1000]
            st.subheader("📝 Role Profile Summary (AI)")
            st.write(ai_text)
        except Exception as e:
            st.warning(f"AI disabled or failed: {e}")
    else:
        st.info("AI disabled: `GOOGLE_API_KEY` tidak ditemukan di secrets. Tambahkan jika ingin ringkasan otomatis.")

    # -------------------------
    # Call RPC to get talent match results
    # -------------------------
    try:
        df_results, raw_resp = run_rpc_talent_match()
    except Exception as e:
        st.error(f"Error saat menjalankan function 'get_talent_match_results': {e}")
        st.stop()

    # Debug raw RPC
    with st.expander("🔎 Debug: hasil RPC mentah"):
        st.write("RAW response object:", raw_resp)

    if df_results.empty:
        st.warning("⚠️ Tidak ada hasil dari function RPC 'get_talent_match_results'. Pastikan function ada dan menerima benchmark yang baru saja disimpan.")
        st.stop()

    # show small preview (hidden by default)
    with st.expander("🔎 Debug: preview df_results (first 10 rows)", expanded=False):
        st.write(df_results.head(10))

    # -------------------------
    # Recalibration (client-side) untuk memperbaiki skala match rate
    # -------------------------
    df = df_results.copy()

    # ensure numeric columns
    for col in ['user_score', 'baseline_score', 'tv_match_rate', 'tgv_match_rate', 'final_match_rate']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # helper to set max possible per tv_name
    def max_possible(tv_name):
        if not isinstance(tv_name, str):
            return 5.0
        t = tv_name.lower()
        if t.startswith('competency'):
            return 5.0
        if t.startswith('papi') or t.startswith('iq'):
            # PAPI scales may be 1..7 etc — we fallback to 6-7; however we'll prefer baseline if present
            return max(6.0, float( df.loc[df['tv_name']==tv_name, 'baseline_score'].median() if 'baseline_score' in df.columns else 5.0 ))
        if t.startswith('strength'):
            return 1.0
        return 5.0

    # compute absolute match and combined
    if 'tv_name' in df.columns:
        df['max_possible'] = df['tv_name'].apply(max_possible)
    else:
        df['max_possible'] = 5.0

    df['tv_match_absolute'] = ((df['user_score'] / df['max_possible']).clip(0,1) * 100.0).fillna(0)
    # If tv_match_rate exists, use it; otherwise derive simple relative measure
    if 'tv_match_rate' not in df.columns:
        # fallback: if baseline_score > 0: relative = user/baseline *100 else 0
        df['tv_match_rate'] = df.apply(lambda r: min(100.0, (r['user_score'] / r['baseline_score'] * 100.0)) if r.get('baseline_score',0) > 0 else 0.0, axis=1)

    df['tv_match_combined'] = 0.5 * df['tv_match_rate'] + 0.5 * df['tv_match_absolute']

    # compute new TGV avg and final avg
    tgv_new = df.groupby(['employee_id','tgv_name'])['tv_match_combined'].mean().reset_index().rename(columns={'tv_match_combined':'tgv_match_rate_new'})
    final_new = tgv_new.groupby('employee_id')['tgv_match_rate_new'].mean().reset_index().rename(columns={'tgv_match_rate_new':'final_match_rate_new'})

    # Merge names into final
    if 'employee_id' in df.columns and 'fullname' in df.columns:
        final_new = final_new.merge(df[['employee_id','fullname']].drop_duplicates(), on='employee_id', how='left')

    # -------------------------
    # Prepare ranked dataframe for display
    # -------------------------
    df_ranked = final_new.copy()
    # if position/grade/directorate info available in RPC (if not, try to left join from dim tables via new RPC in DB)
    # Try to get position/grade/directorate from original df_results
    if 'employee_id' in df.columns:
        info_cols = ['employee_id','fullname']
        # grab a single row per employee from original results (to extract grade/position if present)
        info = df[['employee_id','fullname']].drop_duplicates()
        # some RPC returned additional columns: 'position_name', 'grade', 'directorate'
        for c in ['position_name','grade','directorate']:
            if c in df.columns:
                info[c] = df.groupby('employee_id')[c].first().values
        df_ranked = df_ranked.merge(info.drop_duplicates(subset=['employee_id']), on='employee_id', how='left')

    # sort by new final match
    df_ranked = df_ranked.sort_values(by='final_match_rate_new', ascending=False).reset_index(drop=True)

    # -------------------------
    # UI: Show Ranked list & Charts
    # -------------------------
    st.subheader("🏆 Ranked Talent List (Top Matches)")
    # columns for display
    display_cols = ['fullname', 'position_name', 'directorate', 'grade', 'final_match_rate_new']
    # ensure columns exist
    for c in display_cols:
        if c not in df_ranked.columns:
            df_ranked[c] = None

    # show table with progress bar
    st.dataframe(
        df_ranked[display_cols].head(20).rename(columns={'final_match_rate_new':'Match Rate (%)'}),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Match Rate (%)': st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
        }
    )

    # -------------------------
    # Dashboard visualizations
    # -------------------------
    st.subheader("📈 Talent Match Dashboard")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Distribusi Final Match Rate (Recalibrated)**")
        fig1, ax1 = plt.subplots(figsize=(6,4))
        sns.histplot(df_ranked['final_match_rate_new'].dropna(), kde=True, ax=ax1, bins=15)
        ax1.set_xlabel("Final Match Rate (%)")
        ax1.set_ylabel("Jumlah Karyawan")
        st.pyplot(fig1)

    with col2:
        st.write("**Kekuatan TGV (Rata-rata Top 10)**")
        # need the df with tgv rows (tgv_new contains tgv per employee)
        if not tgv_new.empty:
            # restrict to top 10 employees
            top10_ids = df_ranked.head(10)['employee_id'].tolist()
            tgv_top10 = tgv_new[tgv_new['employee_id'].isin(top10_ids)].copy()
            if tgv_top10.empty:
                st.info("Tidak cukup data TGV untuk top 10 (cek RPC).")
            else:
                # Chart A: bar mean per TGV
                tgv_avg = tgv_top10.groupby('tgv_name')['tgv_match_rate_new'].mean().reset_index().sort_values('tgv_match_rate_new', ascending=False)
                fig2, ax2 = plt.subplots(figsize=(6,4))
                sns.barplot(data=tgv_avg, x='tgv_match_rate_new', y='tgv_name', ax=ax2)
                ax2.set_xlabel('Rata-rata Match Rate (%)')
                ax2.set_ylabel('TGV')
                ax2.set_xlim(0,100)
                st.pyplot(fig2)

                # Chart B: stacked per employee
                pivot = tgv_top10.pivot_table(index='employee_id', columns='tgv_name', values='tgv_match_rate_new', aggfunc='mean').fillna(0)
                # map employee_id -> name in order of ranking
                name_map = dict(df_ranked[['employee_id','fullname']].drop_duplicates().values)
                pivot.index = pivot.index.map(lambda eid: name_map.get(eid, eid))
                # reorder rows by df_ranked order
                ordered_names = df_ranked.head(10)['fullname'].tolist()
                pivot = pivot.reindex(ordered_names).fillna(0)
                fig3, ax3 = plt.subplots(figsize=(8,4))
                pivot.plot(kind='bar', stacked=True, ax=ax3)
                ax3.set_ylabel('Match Rate Contribution (%)')
                ax3.set_xlabel('Employee (Top 10)')
                ax3.legend(title='TGV', bbox_to_anchor=(1.05,1), loc='upper left')
                st.pyplot(fig3)
        else:
            st.info("Kolom TGV tidak tersedia. Pastikan RPC mengembalikan fields tgv_name & tv info.")

    st.success("✅ Analisis selesai!")

    # small hidden debug panel (collapsed by default)
    if DEBUG_MODE:
        with st.expander("🔧 DEBUG (detailed)", expanded=False):
            st.write("df (sample):")
            st.dataframe(df.head(20))
            st.write("tgv_new (sample):")
            st.dataframe(tgv_new.head(50))
            st.write("final_new (sample):")
            st.dataframe(final_new.head(50))
            st.write("df_ranked (top):")
            st.dataframe(df_ranked.head(50))

# End of app.py
