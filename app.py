import streamlit as st
from supabase import create_client, Client as SupabaseClient
import pandas as pd
# HAPUS: from openrouter import OpenRouter 
import matplotlib.pyplot as plt
import seaborn as sns
# Ini adalah komentar untuk trigger rebuild
# =======================================================================
# 1. KONEKSI & SETUP (Menggunakan Streamlit Secrets)
# =======================================================================

# Ambil kunci dari file secrets.toml
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    # HAPUS: OPENROUTER_KEY = st.secrets["OPENROUTER_KEY"] 
except KeyError as e:
    st.error(f"Error: Kunci '{e}' tidak ditemukan di file .streamlit/secrets.toml. Pastikan file ada dan nama kunci benar (huruf besar).")
    st.stop()
except FileNotFoundError:
    st.error("Error: File .streamlit/secrets.toml tidak ditemukan. Pastikan file ada di folder .streamlit di dalam folder proyek Anda.")
    st.stop()

# Buat koneksi ke Supabase
try:
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Gagal terhubung ke Supabase: {e}")
    st.stop()

# HAPUS BAGIAN KONEKSI AI
# client_ai = None 
# try:
#     client_ai = OpenRouter(api_key=OPENROUTER_KEY)
# except NameError:
#      st.warning("Library 'OpenRouter' tidak bisa diimpor. Fitur AI tidak akan aktif.")
# except Exception as e:
#     st.warning(f"Gagal terhubung ke OpenRouter: {e}. Fitur AI tidak aktif.")


# =======================================================================
# 2. JUDUL APLIKASI
# =======================================================================
st.set_page_config(layout="wide")
st.title("🚀 Talent Match Intelligence System")
st.write("Aplikasi ini membantu menemukan talenta internal yang cocok dengan profil benchmark.")

# =======================================================================
# 3. FUNGSI AMBIL DAFTAR KARYAWAN
# =======================================================================
@st.cache_data(ttl=3600) # Cache selama 1 jam
def get_employee_list():
    try:
        response = supabase.table('employees').select('employee_id, fullname').execute()
        if response.data:
             # Sort dictionary by employee name (value)
            sorted_employees = sorted(response.data, key=lambda x: x['fullname'])
            return {emp['employee_id']: emp['fullname'] for emp in sorted_employees}
        return {}
    except Exception as e:
        st.error(f"Error mengambil daftar karyawan: {e}")
        return {}

employee_dict = get_employee_list()
if not employee_dict:
    st.error("Gagal memuat daftar karyawan dari database. Periksa koneksi/nama tabel.")
    st.stop()

# =======================================================================
# 4. FORM INPUT
# =======================================================================
with st.form(key="benchmark_form"):
    st.header("1. Role Information")
    role_name_input = st.text_input("Role Name", placeholder="Ex. Data Analyst")
    job_level_input = st.selectbox("Job Level", ["Staff", "Supervisor", "Manager", "Senior Manager"])
    role_purpose_input = st.text_area("Role Purpose", placeholder="1-2 sentences describe role outcome...")

    st.header("2. Employee Benchmarking")
    employee_names_options = list(employee_dict.values())
    selected_benchmark_names = st.multiselect(
        "Select Employee Benchmarking (min 1, max 3)",
        options=employee_names_options,
        max_selections=3
    )

    submit_button = st.form_submit_button("✨ Find Matches") # Ubah teks tombol

# =======================================================================
# 5. LOGIKA SETELAH SUBMIT
# =======================================================================
if submit_button:
    # --- VALIDASI INPUT ---
    if not role_name_input or not job_level_input or not role_purpose_input or not selected_benchmark_names:
        st.error("❌ Semua field wajib diisi!")
    elif len(selected_benchmark_names) < 1:
        st.error("❌ Pilih minimal 1 karyawan benchmark!")
    else:
        st.info("🔄 Memproses permintaan Anda...")
        with st.spinner("Menyimpan benchmark dan menghitung skor..."): # Hapus bagian AI

            # --- LANGKAH 5.1: SIMPAN BENCHMARK ---
            name_to_id_dict = {v: k for k, v in employee_dict.items()}
            selected_benchmark_ids = [name_to_id_dict[name] for name in selected_benchmark_names]
            insert_success = False
            try:
                insert_response = supabase.table('talent_benchmarks').insert({
                    "role_name": role_name_input,
                    "job_level": job_level_input,
                    "role_purpose": role_purpose_input,
                    "selected_talent_ids": selected_benchmark_ids
                }).execute()
                if hasattr(insert_response, 'data') and insert_response.data:
                    insert_success = True
                else:
                    error_detail = insert_response.error.message if hasattr(insert_response, 'error') and insert_response.error else "No data returned after insert"
                    st.error(f"Gagal menyimpan data benchmark: {error_detail}")
                    st.stop()
            except Exception as e:
                st.error(f"Error menyimpan benchmark ke Supabase: {e}")
                st.stop()

            # --- LANGKAH 5.2: TAMPILKAN INFO PROFIL (PENGGANTI AI) ---
            st.subheader("📝 Role Profile Summary")
            st.write(f"**Role Name:** {role_name_input}")
            st.write(f"**Job Level:** {job_level_input}")
            st.write(f"**Role Purpose:** {role_purpose_input}")
            st.write(f"**Benchmark Employees:** {', '.join(selected_benchmark_names)}")
            st.markdown("---") 

            # HAPUS BAGIAN PANGGIL AI 
            # ai_output = None
            # ... (kode AI dihapus) ...

            # --- LANGKAH 5.3: JALANKAN KUERI SQL ---
            st.header("📊 Ranked Talent List & Dashboard")
            df_results = None
            try:
                data_response = supabase.rpc('get_talent_match_results').execute()

                if not data_response.data:
                    error_detail = data_response.error.message if hasattr(data_response, 'error') and data_response.error else "No data returned from function"
                    st.error(f"Gagal menjalankan kueri SQL 'get_talent_match_results': {error_detail}")
                    st.write("Pastikan function ada di Supabase & benchmark sudah dipilih.")
                    st.stop()

                df_results = pd.DataFrame(data_response.data)

            except Exception as e:
                st.error(f"Error saat menjalankan/memproses kueri SQL: {e}")
                st.write("Pastikan function 'get_talent_match_results' ada dan tidak error di Supabase.")
                st.stop()

            # --- LANGKAH 5.4: TAMPILKAN OUTPUT ---
            if df_results is not None and not df_results.empty:
                st.subheader("🏆 Ranked Talent List (Top Matches)")
                df_ranked_list = df_results.drop_duplicates(subset=['employee_id']).sort_values(
                    by="final_match_rate", ascending=False, na_position='last'
                )

                # --- TAMBAHKAN DEBUG INI ---
                st.write("DEBUG: Kolom di df_ranked_list:", df_ranked_list.columns.tolist())
                # --- BATAS DEBUG ---
    
                # Periksa nama kolom 'position_name' 
                if 'position_name' not in df_ranked_list.columns:
                    st.error("Kolom 'position_name' tidak ditemukan dalam hasil kueri. Periksa function SQL.")
                    st.write("Kolom yang tersedia:", df_ranked_list.columns.tolist())
                    st.stop()

                st.dataframe(
                    df_ranked_list[['fullname', 'position_name', 'directorate', 'grade', 'final_match_rate']].head(20),
                    use_container_width=True, hide_index=True,
                    column_config={"final_match_rate": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)}
                )

                st.subheader("💡 Dashboard Visualizations")
                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Distribusi Final Match Rate**")
                    fig1, ax1 = plt.subplots(figsize=(6, 4)) 
                    sns.histplot(df_ranked_list['final_match_rate'].dropna(), kde=True, ax=ax1, bins=15, color='skyblue')
                    ax1.set_xlabel('Final Match Rate (%)', fontsize=10)
                    ax1.set_ylabel('Jumlah Karyawan', fontsize=10)
                    ax1.tick_params(axis='both', which='major', labelsize=8)
                    st.pyplot(fig1)

                with col2:
                    st.write("**Kekuatan TGV (Rata-rata Top 10)**")
                    top_10_ids = df_ranked_list.head(10)['employee_id']
                    df_top_10 = df_results[df_results['employee_id'].isin(top_10_ids)]
                    
                    if not df_top_10.empty:
                        tgv_avg = df_top_10.drop_duplicates(
                            subset=['employee_id', 'tgv_name']
                        ).groupby('tgv_name')['tgv_match_rate'].mean().reset_index().sort_values(
                            by='tgv_match_rate', ascending=False
                        )
                        fig2, ax2 = plt.subplots(figsize=(6, 4)) 
                        sns.barplot(data=tgv_avg, x='tgv_match_rate', y='tgv_name', ax=ax2, palette='coolwarm', hue='tgv_name', dodge=False, legend=False) 
                        ax2.set_xlabel('Rata-rata Match Rate (%)', fontsize=10)
                        ax2.set_ylabel('TGV', fontsize=10)
                        ax2.tick_params(axis='both', which='major', labelsize=8)
                        ax2.set_xlim(0, 100)
                        st.pyplot(fig2)
                    else:
                        st.write("Tidak cukup data untuk menampilkan chart TGV.")

                st.success("✅ Analisis Selesai!")
            else:
                st.warning("Tidak ada hasil yang bisa ditampilkan.")
