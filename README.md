# Prototipe AI-Powered Talent Matching 

Ini adalah prototipe aplikasi web yang dibangun dengan Streamlit dan Supabase untuk *case study* analitik. Aplikasi ini mengimplementasikan algoritma pencocokan talenta berdasarkan *benchmark* yang dipilih pengguna.

## 🛠️ Stack Teknologi

* **Aplikasi/Dashboard:** Streamlit
* **Database:** Supabase (PostgreSQL)
* **Analisis & Perhitungan:** Python (Pandas)
* **(Opsional) AI Insights:** Google Gemini API

## 🚀 Fitur

* Form input dinamis untuk mendefinisikan kriteria peran.
* Pemilihan *benchmark* karyawan secara interaktif.
* Menjalankan *function* SQL kompleks di Supabase untuk menghitung skor kecocokan.
* Menampilkan daftar peringkat talenta internal.
* Visualisasi *dashboard* untuk distribusi skor dan kekuatan TGV.

---

## 🏁 Instruksi Pengaturan & Menjalankan (Setup)

Berikut adalah cara untuk menjalankan aplikasi ini di lingkungan lokal Anda.

### 1. Prasyarat

* Python 3.9+
* Git
* Akun [Supabase](https://supabase.com/) (gratis)
* (Opsional) Kunci API [Google AI Studio (Gemini)](https://aistudio.google.com/app/apikey)

### 2. Clone Repositori

```bash
git clone [https://github.com/](https://github.com/)[NAMA_PENGGUNA_ANDA]/[NAMA_REPOSITORI_ANDA].git
cd [NAMA_REPOSITORI_ANDA]
````

### 3\. Pengaturan Database Supabase

1.  **Buat Proyek:** Buat proyek baru di Supabase.
2.  **Buat Tabel:** Buka **SQL Editor**. Salin dan jalankan skrip SQL dari file `setup_database.sql` (atau nama file SQL Anda) untuk membuat semua tabel yang diperlukan (`employees`, `dim_positions`, `talent_benchmarks`, dll.).
3.  **Upload Data:** Buka **Table Editor**. Upload file-file CSV Anda ke tabel yang sesuai.
      * **Urutan Penting:** Upload tabel `dim_` terlebih dahulu, lalu `employees`, baru kemudian tabel dependen (seperti `papi_scores`, `strengths`, `performance_yearly`).
4.  **Buat Function SQL:** Buka **SQL Editor** lagi. Salin dan jalankan skrip SQL untuk membuat *function* `get_talent_match_results()`.

### 4\. Pengaturan Lingkungan Python

1.  (Opsional tapi disarankan) Buat *virtual environment*:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
2.  Install semua *library* yang dibutuhkan dari `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

### 5\. Pengaturan Kunci Rahasia (Secrets)

1.  Di folder proyek, buat folder baru bernama `.streamlit`.

2.  Di dalam folder `.streamlit`, buat file baru bernama `secrets.toml`.

3.  Isi `secrets.toml` dengan kunci API Anda:

    ```toml
    # .streamlit/secrets.toml
    SUPABASE_URL = "httpsU_URL_SUPABASE_ANDA.supabase.co"
    SUPABASE_KEY = "KUNCI_ANON_PUBLIK_SUPABASE_ANDA"
    GOOGLE_API_KEY = "KUNCI_API_GOOGLE_AI_ANDA" 
    ```

      * Ambil kunci Supabase dari **Settings -\> API** di Supabase.
      * Ambil kunci Google dari Google AI Studio.

### 6\. Jalankan Aplikasi

```bash
streamlit run app.py
```
* **README.md with setup instructions:** Anda baru saja membuatnya.
* **Analysis:** Aman tersimpan **HANYA** di dalam Laporan PDF yang Anda kumpulkan.
```
