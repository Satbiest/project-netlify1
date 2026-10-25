# CVBoost — Netlify frontend + Render backend

Paket ini disiapkan dari source CVBoost yang sudah diperbaiki di komputer lokal. Gunakan **seluruh isi folder ini** untuk satu repository GitHub baru. Frontend dan backend memakai repository yang sama, tetapi dijalankan oleh dua layanan berbeda.

```text
Browser pengguna → Frontend HTTPS di Netlify → Backend HTTPS di Render → Gemini
                                             └→ PDF parser + MiniLM di server
```

Menghubungkan GitHub ke Netlify saja tidak menjalankan proses FastAPI/Uvicorn. Dalam konfigurasi ini, pengguna tetap membuka alamat Netlify; permintaan screening dikirim JavaScript ke Render. API key Gemini hanya disimpan pada backend.

## 1. Kenali folder yang akan diupload

```text
cvboost-netlify-render/
├── netlify.toml                 ← pengaturan build Netlify
├── .gitignore
├── README.md
├── VERIFICATION.md
├── frontend/
│   ├── package.json
│   ├── build.mjs                ← membaca CVBOOST_API_URL saat build
│   ├── build.test.mjs
│   └── public/                  ← HTML yang sudah dirender, CSS, JS, data contoh
└── backend/
    ├── main.py                  ← aplikasi FastAPI
    ├── config.py
    ├── .env.example             ← contoh kosong, bukan API key asli
    ├── .dockerignore
    ├── Dockerfile
    ├── requirements*.txt
    ├── services/
    ├── templates/
    ├── static/
    ├── data/
    ├── scripts/
    └── tests/
```

Paket tidak menyertakan `.env` asli, `.venv`, cache model, riwayat Git, maupun CV pribadi. Jangan menambahkan file tersebut ke repository. Folder lokal lama tetap tersedia terpisah.

## 2. Upload ke repository GitHub baru

1. Ekstrak ZIP paket ini, atau langsung gunakan folder `cvboost-netlify-render` yang sudah tersedia.
2. Buka folder tersebut di VS Code: **File → Open Folder**.
3. Di GitHub, buat repository baru, misalnya `cvboost-deploy`. Untuk awal, pilih **Private**. Jangan centang penambahan README/.gitignore/license otomatis agar repository kosong.
4. Pada terminal PowerShell VS Code, pastikan posisi terminal adalah folder paket, lalu jalankan:

```powershell
git --version
git init
git add .gitignore netlify.toml README.md VERIFICATION.md backend frontend
git status --short
```

Periksa daftar file: tidak boleh ada `.env` berisi key, `.venv`, `.cache`, atau PDF pribadi. File `backend/.env.example` boleh karena key-nya kosong. Lalu jalankan:

```powershell
git commit -m "Prepare CVBoost for Netlify and Render"
git branch -M main
git remote add origin https://github.com/USERNAME/cvboost-deploy.git
git push -u origin main
```

**Ganti `USERNAME` dan `cvboost-deploy` dengan pemilik/nama repository baru Anda.** Jika Git meminta identitas, ikuti petunjuk untuk `user.name` dan `user.email` memakai identitas Anda. Jika `git` belum dikenali, install Git for Windows dari https://git-scm.com/downloads/win lalu tutup/buka kembali terminal.

Alternatif tanpa terminal Git: di repository kosong, pilih **uploading an existing file**, lalu tarik **isi** folder paket ke halaman upload dan commit. Pertahankan subfolder `backend` dan `frontend`. Pastikan file `netlify.toml` berada pada halaman utama repository, bukan di dalam satu lapisan folder tambahan. Sertakan `.gitignore` saat upload melalui browser.

**Tanda tahap ini selesai:** GitHub menampilkan `backend/`, `frontend/`, dan `netlify.toml` pada halaman utama repository baru.

## 3. Buat frontend di Netlify terlebih dahulu

1. Masuk ke https://app.netlify.com/.
2. Pilih **Add new project → Import an existing project → GitHub**.
3. Izinkan akses ke repository baru, kemudian pilih repository tersebut.
4. Pilih branch `main`. Gunakan pengaturan berikut:

| Pengaturan | Nilai |
|---|---|
| Base directory | `frontend` |
| Build command | `node build.mjs` |
| Publish directory | `dist` (relatif terhadap base `frontend`) |
| Framework | Tidak ada / Other |

File `netlify.toml` sudah berisi nilai tersebut. Jika UI menampilkan path publish yang sudah diperluas sebagai `frontend/dist`, jangan menambahkan `frontend` lagi. Build harus menjalankan Node dari folder `frontend`, bukan memasang dependency Python backend.

5. **Belum perlu mengisi `CVBOOST_API_URL` pada build pertama. Jangan memasukkan GEMINI_API_KEY ke Netlify.**
6. Klik deploy dan tunggu status berhasil.
7. Buka production URL Netlify dan catat alamatnya, misalnya `https://nama-anda.netlify.app`. Ini hanya contoh; gunakan alamat yang benar-benar ditampilkan akun Anda.
8. Coba **Try sample analysis**. Contoh memakai data fiktif dan tidak menghubungi Gemini.

Pesan **Connect a deployed CVBoost Python backend** masih wajar pada tahap ini: backend belum dihubungkan. Jangan menghapus pesan ini secara manual.

**Tanda tahap ini selesai:** desain tampil benar, sample analysis berfungsi, dan Anda sudah memiliki production URL Netlify.

## 4. Deploy backend di Render

1. Masuk ke https://dashboard.render.com/ dan hubungkan akun GitHub yang berisi repository baru.
2. Pilih **New → Web Service**, kemudian pilih repository yang sama.
3. Isi pengaturan berikut:

| Pengaturan | Nilai |
|---|---|
| Name | Nama unik, misalnya `cvboost-api-anda` |
| Branch | `main` |
| Root Directory | `backend` |
| Language / Runtime | **Docker** |
| Dockerfile Path | `./Dockerfile` (relatif terhadap root `backend`) |
| Docker Build Context | `.` (bila kolom tersedia) |
| Docker Command | Kosongkan; gunakan CMD dalam Dockerfile |
| Health Check Path | `/api/health` |

Tidak perlu menulis perintah `uvicorn` dengan IP laptop Anda. Dockerfile sudah menggunakan `0.0.0.0` dan port dari environment hosting. Tidak perlu menginstall Docker di laptop untuk build di Render.

**Pemilihan resource:** aplikasi memuat PyTorch, Unstructured, dan MiniLM. Kebutuhan memori perlu diukur saat berjalan. Saya menyarankan mulai menguji pada instance dengan sekitar 2 GB RAM atau lebih; ini perkiraan awal, bukan jaminan kapasitas. Periksa biaya sebelum memilih paket. Instance kecil dapat kehabisan memori meskipun halaman utama berhasil dibuka. Paket Free juga dapat tidur setelah tidak ada trafik dan tidak dianjurkan Render untuk produksi.

4. Pada **Environment**, tambahkan variabel berikut. Kolom Value di dashboard tidak memakai format `NAMA=nilai`; nama dan nilainya diisi pada dua kolom terpisah.

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | API key Gemini milik Anda yang valid |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| `MAX_UPLOAD_MB` | `5` |
| `MAX_PDF_PAGES` | `10` |
| `MAX_RESUME_CHARS` | `40000` |
| `MAX_JOB_CHARS` | `12000` |
| `AI_TIMEOUT_SECONDS` | `90` |
| `ANALYSIS_TIMEOUT_SECONDS` | `210` |
| `MAX_CONCURRENT_ANALYSES` | `1` |
| `ENABLE_DEMO` | `true` |
| `ALLOWED_ORIGINS` | `["https://nama-anda.netlify.app"]` |

**Ganti nilai ALLOWED_ORIGINS dengan production URL Netlify dari tahap 3.** Pertahankan format array JSON, tanda kurung siku, serta tanda kutip ganda. Jangan tambahkan `/` di akhir origin. Jika memakai custom domain, masukkan origin custom domain yang sebenarnya. Deploy preview dengan domain acak tidak otomatis diizinkan; gunakan production URL dahulu.

Contoh format yang benar untuk dua origin milik Anda:

```text
["https://nama-anda.netlify.app","https://cv.domain-anda.com"]
```

Model `gemini-3.5-flash-lite` adalah model yang sebelumnya berhasil diuji pada konfigurasi lokal. Ketersediaannya tetap bergantung pada akun/proyek Gemini saat deployment; jika API melaporkan model tidak ditemukan, periksa model yang tersedia untuk API key Anda, jangan menebak nama model lain.

5. Klik **Deploy Web Service**. Build pertama menginstall dependency dan mengunduh aset NLP publik, sehingga dapat memerlukan waktu lebih lama. Langkah build ini tidak menggunakan API key untuk memanggil Gemini.
6. Tunggu status **Live**. Catat URL HTTPS Render yang benar-benar muncul, misalnya `https://cvboost-api-anda.onrender.com`.

**Tanda tahap ini selesai:** backend berstatus Live dan memiliki URL HTTPS `onrender.com` sendiri.

## 5. Periksa backend sebelum menghubungkan frontend

Buka URL Render Anda ditambah `/api/health`, misalnya:

```text
https://cvboost-api-anda.onrender.com/api/health
```

Yang perlu terlihat pada JSON:

```json
{
  "status": "ok",
  "analysis_configured": true,
  "gemini_model": "gemini-3.5-flash-lite",
  "parser_installed": true,
  "encoder_installed": true
}
```

Respons sebenarnya mempunyai field tambahan. Ketiga nilai `true` di atas mengecek konfigurasi key dan keberadaan paket, **belum membuktikan key valid, kuota tersedia, model sudah berhasil dimuat, atau screening berhasil**. Itu dibuktikan dengan satu pengujian CV pada tahap 7.

Jika `analysis_configured` masih `false`, cek `GEMINI_API_KEY` di **Render**, lalu simpan dan redeploy. Jika parser/encoder `false`, periksa build log: pastikan menggunakan Dockerfile dari `backend/` dan `requirements.txt`, bukan hanya `requirements-core.txt`. Jangan lanjut ke integrasi jika pemeriksaan ini belum benar.

## 6. Hubungkan Netlify ke URL Render

1. Kembali ke project Netlify.
2. Buka **Project configuration → Environment variables**.
3. Tambahkan:

| Key | Value |
|---|---|
| `CVBOOST_API_URL` | Production URL HTTPS Render dari tahap 4 |

Contoh nilai: `https://cvboost-api-anda.onrender.com`. **Ganti dengan URL asli Anda. Jangan memakai `127.0.0.1`, IP laptop, atau menambahkan `/api/health` maupun `/api`.**

4. Pastikan variabel tersedia untuk **Builds** pada konteks **Production**. Nilai ini memang alamat publik, bukan secret.
5. Buka **Deploys → Trigger deploy → Deploy site**. Perubahan environment baru masuk frontend setelah build ulang.
6. Setelah published, buka production URL Netlify lalu tekan **Ctrl+Shift+R**.

Pemeriksaan tambahan: buka `/config.js` pada domain Netlify Anda. Isinya harus memuat `apiBaseUrl` dengan URL Render yang benar. Di file ini tidak boleh ada API key Gemini.

**Tanda tahap ini selesai:** tulisan menjadi **Ready for your next move**, pesan konfigurasi hilang, dan tombol Process dapat digunakan.

## 7. Uji satu screening dari Netlify

1. Buka production URL Netlify, bukan URL localhost atau file HTML lokal.
2. Upload PDF dengan teks yang dapat diseleksi, maksimum 5 MB dan 10 halaman.
3. Isi job description sedikitnya 80 karakter atau gunakan **Use example**.
4. Berikan persetujuan pemrosesan AI, kemudian klik **Process** sekali.
5. Tunggu hasil. Jangan klik berulang karena satu analisis dapat membuat beberapa permintaan Gemini.
6. Lihat **Render → Logs**. Permintaan screening seharusnya mencapai `POST /api/analyze` dan selesai dengan `200 OK`.
7. Pastikan skor dan rekomendasi muncul sebagai hasil live, bukan data sample. Di DevTools → Network Anda juga dapat melihat request menuju domain Render.

Keberhasilan membuka `/api/health` atau sample analysis saja belum cukup untuk menyatakan screening online berhasil. Setelah satu analisis live dari production URL Netlify sukses, integrasi frontend–backend sudah teruji untuk alur tersebut.

## Jika masih bermasalah

| Gejala | Yang diperiksa dahulu |
|---|---|
| Pesan preview tetap muncul | `CVBOOST_API_URL` belum terbawa build; buka `/config.js` dan redeploy Netlify |
| Server connection unavailable | Buka health URL Render; cek status Live dan format `ALLOWED_ORIGINS` |
| CORS error di browser | Origin Netlify harus persis sama di `ALLOWED_ORIGINS`, tanpa trailing slash; simpan/redeploy Render |
| Tampilan polos atau tulisan `{% ... %}` | Pastikan Netlify base `frontend` dan publish `dist`; jangan upload `backend/templates/index.html` sebagai website statis |
| `analysis_configured: false` | Key belum disimpan pada environment Render atau belum redeploy |
| Kuota AI habis / 429 | Periksa kuota proyek Gemini; mengganti frontend tidak menambah kuota |
| 504 / analisis terlalu lama | Periksa log Gemini serta resource Render; jangan hanya terus menambah timeout |
| Proses tiba-tiba mati / OOM / exit 137 | Lihat penggunaan memori Render dan sesuaikan kapasitas server |
| Halaman lama muncul | Pastikan Netlify sudah published commit terbaru, lalu hard refresh |

## Memperbarui kode setelah deployment

Ubah kode pada paket/repository ini, commit, lalu push ke branch yang ditautkan ke platform. Perubahan di `backend/` memicu redeploy backend; perubahan frontend dibuild Netlify.

Frontend statis yang dikirim Netlify berada di `frontend/public`. Jika mengubah UI melalui `backend/templates` atau `backend/static`, sinkronkan dahulu dengan perintah berikut menggunakan Python environment yang memiliki Jinja2:

```powershell
python backend/scripts/export_frontend.py
```

Lalu commit perubahan `frontend/public` bersama source backend. Netlify sendiri tidak perlu menginstall PyTorch/Unstructured atau menjalankan Python. Perubahan environment Netlify memerlukan build baru; perubahan environment Render memerlukan restart/redeploy server.

## Batas keamanan saat ini

Konfigurasi ini menyiapkan koneksi HTTPS, CORS untuk origin tertentu, validasi upload, dan pemisahan secret. Namun endpoint screening belum mempunyai login dan rate limit per pengguna/IP. CORS tidak mencegah akses langsung dari script lain, dan batas satu proses bersamaan bukan batas kuota harian. Gunakan untuk pengujian terkendali; tambahkan autentikasi serta pembatasan permintaan sebelum membuka layanan screening untuk publik luas.

Jika key pernah dibagikan di chat/repository, ganti dengan key baru dan cabut key lama. Simpan key pengganti hanya pada environment backend. PDF dan teks CV tidak disimpan permanen oleh aplikasi ini, tetapi teks hasil ekstraksi dikirim ke Google Gemini setelah pengguna menyetujui pemrosesan.

## Referensi resmi

- Netlify build settings: https://docs.netlify.com/build/configure-builds/overview/
- Netlify environment variables: https://docs.netlify.com/build/configure-builds/environment-variables/
- Render Docker deployment: https://render.com/docs/docker
- Render monorepo/root directory: https://render.com/docs/monorepo-support
- Render free service limitations: https://render.com/docs/free
