# Pemeriksaan lokal — 25 Oktober 2026

## Hasil

- Backend: **28 tests passed** (`pytest -q`). Respons Gemini dipalsukan dalam tes; tidak ada CV dikirim ke Gemini.
- Frontend: **4 tests passed** (`node --test build.test.mjs`).
- Build frontend: berhasil menghasilkan tepat **7 file publik**.
- HTML statis sudah dirender: tidak ada sintaks Jinja mentah pada HTML publik.
- CORS: origin yang diizinkan memperoleh header akses pada health dan preflight POST; origin lain ditolak pada preflight.
- Route `/.env`, `/.git/config`, dan `/config.py`: 404 pada aplikasi uji.
- Regresi pemotongan dokumen MiniLM tetap ada dan lolos; source embedding memakai perbaikan terbaru dari folder kerja pengguna.
- URL backend HTTP jaringan privat, URL dengan credential/query, dan alamat berakhiran `/api` ditolak oleh build frontend.
- Build frontend hanya membaca `CVBOOST_API_URL`, tidak mengimpor konfigurasi Python dan tidak membaca `.env`.

## Perubahan deployment

- Satu repository berisi `backend/` untuk Render Docker dan `frontend/` untuk Netlify.
- `netlify.toml` membatasi build Netlify ke folder frontend, sehingga Netlify tidak menginstall dependency ML backend.
- Backend memiliki CORS melalui environment `ALLOWED_ORIGINS`.
- Default konfigurasi mempertahankan model dan timeout yang sebelumnya berhasil dipakai lokal: `gemini-3.5-flash-lite`, AI 90 detik, keseluruhan 210 detik, satu analisis bersamaan.
- Docker menjalankan Uvicorn pada `0.0.0.0` dan mengikuti variabel `PORT` hosting.
- Dockerfile menyiapkan aset tokenizer dan MiniLM publik saat build. Build tidak memanggil Gemini dan tidak mengacu pada API key.
- UI Netlify tetap jujur menampilkan preview jika URL backend belum diatur. Banner disembunyikan ketika pemeriksaan health backend terhubung menunjukkan konfigurasi siap.

## Yang belum dibuktikan oleh pemeriksaan ini

- Docker image belum dibuild di Render maupun Docker Engine lokal.
- Repository baru belum dibuat atau dipush.
- Netlify dan Render belum diprovisikan/ditautkan oleh pemeriksaan ini.
- Belum ada production URL backend baru yang diketahui.
- Belum diuji satu screening live dari Netlify ke Render dan Gemini.
- Kapasitas memori, kuota Gemini, serta latensi cloud perlu diperiksa setelah deploy.
- Belum ada autentikasi dan rate limit per pengguna/IP. CORS bukan pengganti keduanya.

Tes lokal mendukung persiapan deployment, bukan jaminan produksi atau audit keamanan menyeluruh. Ikuti README dan lakukan uji screening live pada tahap terakhir.
