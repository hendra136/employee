# app_with_ai.py
import streamlit as st
from supabase import create_client, Client as SupabaseClient
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import json
import time

st.set_page_config(layout="wide", page_title="Talent Match Intelligence System (AI)")

# ------------------------
# 1. LOAD SECRETS & SUPABASE
# ------------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Failed to connect to Supabase: {e}")
    st.stop()

# AI config (Google Generative)
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
GOOGLE_AI_MODEL = st.secrets.get("GOOGLE_AI_MODEL", "models/text-bison-001")  # adjust if needed

# small util: call Google Generative REST (Text generation)
def call_google_generate(prompt: str, temperature: float = 0.2, max_tokens: int = 512):
    """Call Google Generative API (REST). Returns text or raises."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set in secrets.")
    url = f"https://generativeai.googleapis.com/v1beta2/{GOOGLE_AI_MODEL}:generate?key={GOOGLE_API_KEY}"
    payload = {
        "prompt": {
            "text": prompt
        },
        "temperature": temperature,
        "maxOutputTokens": max_tokens
    }
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Google API error {r.status_code}: {r.text}")
    data = r.json()
    # Google returns text at data['candidates'][0]['content'] or similar depending on model version
    # try to extract smartly:
    if "candidates" in data and len(data["candidates"]) > 0:
        return data["candidates"][0].get("content", "")
    # fallback
    return data.get("output", {}).get("text", "") or json.dumps(data)

# ------------------------
# 2. Helper functions (fetch employees, RPC)
# ------------------------
@st.cache_data(ttl=600)
def fetch_employees_map():
    resp = supabase.table('employees').select('employee_id, fullname').execute()
    if not resp.data:
        return {}
    df = pd.DataFrame(resp.data)
    df = df.drop_duplicates(subset=['employee_id']).sort_values('fullname')
    return {r['employee_id']: r['fullname'] for _, r in df.iterrows()}

def call_rpc_get_results():
    resp = supabase.rpc('get_talent_match_results').execute()
    if not resp or not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)

# ------------------------
# 3. UI: form + select benchmark (we assume prior logic enforces rating==5)
# ------------------------
st.title("🚀 Talent Match Intelligence System (AI-enabled)")
st.write("Pilih benchmark employee (sebaiknya rating=5 tahun terakhir).")

employees_map = fetch_employees_map()
emp_names = list(employees_map.values())

with st.form("bench_form"):
    role_name = st.text_input("Role Name")
    job_level = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose = st.text_area("Role Purpose")
    selected_names = st.multiselect("Employee Benchmarking (1-3)", options=emp_names, max_selections=3)
    enable_ai = st.checkbox("Enable AI insights (Google Generative)", value=True)
    submit = st.form_submit_button("Find Matches")

if submit:
    if not role_name or not job_level or not role_purpose or not selected_names:
        st.error("All fields required")
        st.stop()

    # map back to ids
    name_to_id = {v:k for k,v in employees_map.items()}
    selected_ids = [name_to_id[n] for n in selected_names if n in name_to_id]

    # insert benchmark
    ins = supabase.table('talent_benchmarks').insert({
        "role_name": role_name,
        "job_level": job_level,
        "role_purpose": role_purpose,
        "selected_talent_ids": selected_ids
    }).execute()
    if hasattr(ins, "error") and ins.error:
        st.error(f"Failed to save benchmark: {ins.error.message if ins.error else ins}")
        st.stop()
    st.info("Benchmark saved — running analysis...")

    # call rpc
    df_results = call_rpc_get_results()
    if df_results.empty:
        st.warning("No results returned by RPC.")
        st.stop()

    # show ranked list
    if 'final_match_rate' not in df_results.columns:
        st.error("RPC result missing final_match_rate")
        st.stop()
    df_ranked = df_results.drop_duplicates(subset=['employee_id']).sort_values(by='final_match_rate', ascending=False)

    # present table
    display_cols = ['fullname','position_name','directorate','grade','final_match_rate']
    for c in display_cols:
        if c not in df_ranked.columns:
            df_ranked[c] = None
    st.subheader("🏆 Ranked Talent List (Top Matches)")
    st.dataframe(
        df_ranked[display_cols].head(20),
        use_container_width=True,
        hide_index=True,
        column_config={"final_match_rate": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)}
    )

    # small visual
    st.subheader("📈 Distribution of Final Match Rate")
    fig, ax = plt.subplots(figsize=(8,4))
    sns.histplot(df_ranked['final_match_rate'].dropna(), kde=True, bins=15, ax=ax)
    st.pyplot(fig)

    # ------------------------
    # 4. AI: Generate Role Summary, Success Formula, Top-5 Insights
    # ------------------------
    if enable_ai:
        if not GOOGLE_API_KEY:
            st.warning("AI enabled but GOOGLE_API_KEY missing in secrets.")
        else:
            st.subheader("🤖 AI Insights")
            with st.spinner("Generating AI insights..."):
                # prepare context
                # 1) top TGV averages
                try:
                    tgv_avg = (df_results.drop_duplicates(subset=['employee_id','tgv_name'])
                               .groupby('tgv_name')['tgv_match_rate'].mean()
                               .sort_values(ascending=False))
                    top_tgvs = tgv_avg.head(5).to_dict()
                except Exception:
                    top_tgvs = {}

                # 2) top 5 employees basic
                top5 = df_ranked.head(5)[['employee_id','fullname','final_match_rate']].to_dict(orient='records')

                # build prompt
                prompt = f"""
You are an HR analytics assistant.
Role: {role_name} ({job_level})
Role purpose: {role_purpose}

Selected benchmark employees (ids): {selected_ids}
Top TGV averages: {json.dumps(top_tgvs)}

Top 5 candidates (employee_id, fullname, score):
{json.dumps(top5, indent=2)}

Tasks:
1) Provide a concise Role Profile Summary (3 bullets).
2) Propose a short Success Formula (explainable weighting across TGVs) based on Top TGVs.
3) For each of the Top 5 candidates, provide one short explanation why they scored high (use TGV names or likely drivers).
4) Give 3 actionable recommendations for hiring/coaching/promotion.

Answer in clear bullet points and short sentences.
"""
                # call Google generative API
                try:
                    ai_text = call_google_generate(prompt, temperature=0.2, max_tokens=400)
                except Exception as e:
                    st.error(f"AI generation failed: {e}")
                    ai_text = None

                if ai_text:
                    st.markdown("**AI Narrative**")
                    st.write(ai_text)
                else:
                    st.info("No AI output available.")

    st.success("Analysis complete")
