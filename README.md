# Sistem Rekomendasi Film

## Deskripsi

Sistem Rekomendasi Film adalah aplikasi berbasis Python yang menggunakan Neo4j sebagai database graph. Sistem menyimpan data pengguna, film, dan relasi film favorit, kemudian menghasilkan rekomendasi film dengan pendekatan hybrid.

Aplikasi menyediakan dua antarmuka yang memakai backend dan algoritma yang sama:

- **Desktop GUI** (CustomTkinter) dengan tampilan modern bertema gelap melalui `python desktop.py`.
- **CLI** (Command Line Interface) melalui `python main.py`.

Aplikasi ini **bukan aplikasi web**. Seluruh data tetap disimpan di Neo4j.

## Tujuan

1. Menyimpan pengguna dan film favoritnya dalam database graph.
2. Menghasilkan rekomendasi film yang relevan untuk setiap pengguna.
3. Menggabungkan Collaborative Filtering dan Content-Based Filtering dalam satu skor hybrid.
4. Menjaga konsistensi data, terutama pada nama pengguna, judul film, dan genre.
5. Memberikan hasil rekomendasi yang dapat dijelaskan alasan pemilihannya.

## Teknologi

- Python
- Neo4j
- Neo4j Python Driver
- Cypher Query Language
- Graph Database
- python-dotenv
- CustomTkinter
- Pillow

## Fitur

### Desktop GUI

- Dashboard ringkasan statistik, rekomendasi, dan film favorit pengguna aktif.
- Katalog Film berisi seluruh film dari Neo4j dalam grid kartu dengan poster, judul, genre, pencarian judul, dan tombol muat ulang.
- Tambah pengguna baru dengan pengecekan duplikasi.
- Tambah film favorit dengan pemilihan genre berbentuk checkbox.
- Halaman rekomendasi lengkap dengan skor pengguna, skor genre, skor akhir, dan alasan.
- Halaman film favorit per pengguna.
- Hapus film favorit dengan konfirmasi, tanpa menghapus node film.
- Halaman statistik Neo4j.
- Poster film otomatis pada Dashboard, Rekomendasi, dan daftar favorit, dengan placeholder jika poster belum tersedia.
- Indikator status koneksi dan tombol hubungkan ulang.
- Notifikasi singkat (toast) untuk setiap hasil operasi.

### CLI

- Menu 1: Tambah pengguna.
- Menu 2: Tambah film favorit pengguna.
- Menu 3: Lihat rekomendasi film.
- Menu 4: Lihat daftar film favorit pengguna.
- Menu 5: Keluar dari program.
- Menu 6: Hapus film dari daftar favorit pengguna.
- Menu 7: Statistik sistem (jumlah pengguna, film, dan relasi favorit).

## Struktur Database Graph

### Node User

| Properti | Keterangan |
| --- | --- |
| `name` | Nama tampilan pengguna |
| `dibuat` | Waktu pembuatan data pengguna |

### Node Movie

| Properti | Keterangan |
| --- | --- |
| `title` | Judul film untuk ditampilkan |
| `title_normal` | Judul yang sudah dinormalisasi untuk mencegah duplikasi |
| `genres` | Daftar genre film |

### Relasi

```text
(:User)-[:LIKES]->(:Movie)
```

Satu pengguna dapat menyukai banyak film. Satu film juga dapat disukai banyak pengguna.

## Normalisasi Data

### Nama Pengguna

Nama pengguna dibersihkan dari spasi berlebih di awal, akhir, dan antar kata. Pencarian serta pengecekan duplikasi menggunakan bentuk huruf kecil, sehingga:

- `Budi`
- `budi`
- `BUDI`

dianggap sebagai pengguna yang sama.

### Judul Film

Judul film memiliki properti `title_normal`. Pengecekan duplikasi menggunakan judul yang sudah dinormalisasi, sehingga perbedaan kapitalisasi tidak membuat film tercatat dua kali.

### Genre

Genre diubah ke bentuk standar. Contoh:

| Input | Hasil |
| --- | --- |
| `Sci-FI` | `Sci-Fi` |
| `scifi` | `Sci-Fi` |
| `science fiction` | `Sci-Fi` |
| `ACTION` | `Action` |

Genre ganda dalam satu input akan dihapus. Genre yang tidak dikenal akan ditolak beserta daftar genre yang tersedia.

## Algoritma Rekomendasi

### 1. Collaborative Filtering

Sistem mencari pengguna lain yang memiliki minimal satu film favorit yang sama dengan pengguna target. Film yang disukai pengguna lain tersebut menjadi kandidat rekomendasi.

Skor pengguna dihitung dari jumlah pengguna lain yang berbeda dan menyukai kandidat film tersebut.

```text
Skor Pengguna = jumlah pengguna lain yang memiliki film favorit sama
                dan juga menyukai kandidat film
```

### 2. Content-Based Filtering

Sistem membandingkan genre kandidat film dengan genre film favorit pengguna target. Setiap genre yang sama menambah skor.

```text
Skor Genre = jumlah genre kandidat yang sama dengan genre film favorit pengguna
```

### 3. Hybrid Filtering

Skor akhir menggabungkan kedua metode menggunakan rumus:

```text
Skor Akhir = (Skor Pengguna x 2) + Skor Genre
```

Bobot 2 pada skor pengguna menunjukkan bahwa kesamaan selera antar pengguna diberi prioritas lebih tinggi dibandingkan kesamaan genre.

### Aturan Hasil Rekomendasi

- Film yang sudah disukai pengguna tidak direkomendasikan kembali.
- Kandidat dengan skor akhir 0 tidak ditampilkan.
- Hasil diurutkan dari skor akhir tertinggi.
- Jika skor sama, hasil diurutkan berdasarkan judul film.
- Setiap film hanya muncul satu kali.
- Setiap rekomendasi menampilkan skor pengguna, skor genre, skor akhir, dan alasan rekomendasi.

## Instalasi

### 1. Prasyarat

- Python 3.10 atau lebih baru.
- Neo4j 5.x atau lebih baru yang sudah berjalan dan dapat diakses.
- Database Neo4j yang akan digunakan.

### 2. Membuat Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Memasang Dependensi

```powershell
pip install -r requirements.txt
```

### 4. Konfigurasi Koneksi Neo4j

Buat file `.env` di folder proyek. Contoh struktur variabel tersedia pada `.env.example`. Salin contoh tersebut menjadi `.env`, lalu sesuaikan nilainya dengan konfigurasi Neo4j Anda.

File `.env` **tidak boleh dibagikan** dan tidak boleh dimasukkan ke repository.

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=isi_password_anda
NEO4J_DATABASE=neo4j
```

Jangan menyalin password asli ke dokumentasi atau laporan.

### 5. Menjalankan Program

Menjalankan desktop GUI:

```powershell
python desktop.py
```

Menjalankan CLI:

```powershell
python main.py
```

Jika koneksi berhasil, GUI akan menampilkan dashboard, sedangkan CLI akan menampilkan menu utama.

## Antarmuka Desktop (GUI)

File `desktop.py` menyediakan antarmuka grafis berbasis CustomTkinter. GUI memanggil fungsi backend yang sama dari `main.py`, sehingga aturan validasi, normalisasi, dan rumus rekomendasi hybrid tetap identik dengan CLI.

Halaman yang tersedia:

| Halaman | Fungsi |
| --- | --- |
| Dashboard | Ringkasan statistik, tiga rekomendasi teratas, dan film favorit pengguna aktif. |
| Katalog Film | Seluruh film dari Neo4j dalam grid kartu berisi poster, judul, dan genre, lengkap dengan pencarian dan muat ulang. |
| Tambah Pengguna | Mendaftarkan pengguna baru dengan pengecekan duplikasi. |
| Tambah Film | Menyimpan film favorit beserta genre yang dipilih. |
| Rekomendasi | Menampilkan seluruh rekomendasi beserta skor dan alasan. |
| Film Favorit | Menampilkan daftar film favorit pengguna. |
| Hapus Favorit | Menghapus relasi favorit setelah konfirmasi. |
| Statistik | Menampilkan jumlah pengguna, film, dan relasi `LIKES`. |

Catatan GUI:

- Sidebar menampilkan status koneksi Neo4j dan tombol **Hubungkan Ulang**.
- Tombol **Muat Ulang** memuat ulang halaman yang sedang aktif.
- Operasi yang gagal menampilkan pesan dalam bahasa Indonesia tanpa traceback teknis.
- Untuk memeriksa GUI tanpa interaksi manual, gunakan mode uji asap:

```powershell
python desktop.py --smoke-test
```

Mode ini membuka jendela, berpindah melalui seluruh halaman, menutup jendela, lalu mencetak `SMOKE_TEST_OK`.

### Menambahkan Poster Film

Poster film ditampilkan pada kartu rekomendasi di Dashboard dan halaman Rekomendasi, serta pada daftar film favorit. Gambar disimpan di folder lokal:

```text
assets/posters/
```

Langkah menambahkan poster baru:

1. Siapkan gambar poster berformat `.png`, `.webp`, `.jpg`, `.jpeg`, `.bmp`, atau `.gif`.
2. Beri nama file sesuai judul film di database Neo4j.
3. Simpan file ke `assets/posters/`.
4. Buka kembali halaman GUI atau klik **Muat Ulang**. Tidak perlu mengubah kode.

Pencocokan judul tidak membedakan huruf besar/kecil dan mengabaikan spasi serta tanda baca. Contoh:

| Judul film di database | Nama file yang cocok |
| --- | --- |
| `Interstellar` | `Interstellar.jpg` |
| `The Dark Knight` | `the-dark-knight.png` |
| `Spider-Man: No Way Home` | `SpiderManNoWayHome.webp` |
| `Sci-Fi Story` | `sci fi story.png` |

Jika tersedia beberapa file untuk judul yang sama, urutan prioritas format adalah `.png`, `.webp`, `.jpg`, `.jpeg`, `.bmp`, lalu `.gif`.

Poster ditampilkan dengan rasio tetap sehingga tidak gepeng. Jika poster belum tersedia atau gambar gagal dibaca, GUI menampilkan placeholder bergambar film secara otomatis tanpa error. Gambar dibaca sekali dan disimpan di cache agar GUI tetap ringan, dan folder dipindai ulang hanya saat halaman dibuka atau dimuat ulang.

Petunjuk lengkap juga tersedia di `assets/posters/README.md`.

## Cara Python Terhubung ke Neo4j

File `config.py` melakukan hal berikut:

1. Memuat variabel dari file `.env` menggunakan `python-dotenv`.
2. Membaca `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, dan `NEO4J_DATABASE`.
3. Membuat driver Neo4j dengan `GraphDatabase.driver(...)`.
4. Memeriksa koneksi menggunakan `driver.verify_connectivity()` saat program dijalankan.

Seluruh query Cypher menggunakan parameter, bukan penggabungan langsung input pengguna ke dalam query.

## Penjelasan Menu

| Menu | Fungsi |
| --- | --- |
| 1 | Menambahkan pengguna baru. Nama kosong dan pengguna duplikat akan ditolak. |
| 2 | Menambahkan film favorit ke pengguna. Nama, judul, dan genre wajib diisi. Genre tidak dikenal akan ditolak. |
| 3 | Menampilkan rekomendasi film beserta skor dan alasan rekomendasi. |
| 4 | Menampilkan daftar film favorit pengguna. |
| 5 | Keluar dari program. |
| 6 | Menghapus relasi film favorit pengguna tanpa menghapus node film dari database. |
| 7 | Menampilkan statistik jumlah pengguna, film, dan relasi favorit. |

## Contoh Penggunaan

Contoh tampilan menu:

```text

        SISTEM REKOMENDASI FILM

1. Tambah pengguna
2. Tambah film favorit pengguna
3. Lihat rekomendasi film
4. Lihat film favorit pengguna
5. Keluar
6. Hapus film favorit pengguna
7. Statistik sistem
------------------------------------------
Pilih menu (1-7):
```

Contoh hasil rekomendasi:

```text
Rekomendasi film untuk Andi:

1. Avatar
   Genre          : Sci-Fi
   Skor pengguna  : 2 (dikalikan 2 = 4)
   Skor genre     : 1
   Skor akhir     : 5
   Alasan         : Mendapat nilai dari kedua metode: 2 pengguna lain
                    memiliki film favorit yang sama dan juga menyukai
                    film ini; memiliki genre yang sesuai dengan film
                    favorit Anda (Sci-Fi).
```

Angka dan film pada contoh dapat berbeda sesuai data yang tersimpan di database.

## Pengujian

Pengujian menggunakan `unittest` dari Python sehingga tidak memerlukan paket tambahan.

```powershell
python -m unittest discover -s tests -v
```

Jenis pengujian:

- Pengujian unit untuk normalisasi nama, judul, genre, validasi input, dan alasan rekomendasi.
- Pengujian integrasi Neo4j untuk tambah pengguna, pencegahan duplikasi, tambah film favorit, daftar favorit, daftar pengguna, Collaborative Filtering, Content-Based Filtering, Hybrid Recommendation, input kosong, genre tidak valid, pengguna belum terdaftar, pengguna tanpa favorit, penghapusan favorit, kondisi tanpa rekomendasi, dan statistik.
- Uji asap GUI dengan `python desktop.py --smoke-test` untuk memastikan seluruh halaman dapat dibuka dan ditutup tanpa kesalahan.

Pengujian integrasi menggunakan data khusus dengan awalan `TESTSISTEMREKOMENDASI_`. Data uji dibersihkan sebelum dan sesudah pengujian. Data asli tidak dihapus atau diubah oleh pengujian.

Jika Neo4j tidak tersedia, pengujian integrasi akan dilewati, sedangkan pengujian unit tetap dapat dijalankan.

## Troubleshooting

Program menampilkan pesan kesalahan umum dalam bahasa Indonesia tanpa menampilkan traceback teknis. Jika operasi gagal, periksa pesan yang muncul dan konfigurasi yang terkait.

### Tidak dapat terhubung ke Neo4j

- Pastikan server Neo4j sudah berjalan.
- Periksa `NEO4J_URI` pada `.env`.
- Pastikan database yang dituju tersedia.

### Autentikasi gagal

- Periksa `NEO4J_USERNAME` dan `NEO4J_PASSWORD` pada `.env`.
- Jangan menampilkan atau membagikan isi `.env`.

### Genre ditolak

Gunakan genre yang tersedia:

`Action`, `Adventure`, `Animation`, `Comedy`, `Crime`, `Documentary`, `Drama`, `Family`, `Fantasy`, `Film-Noir`, `History`, `Horror`, `Music`, `Mystery`, `Romance`, `Sci-Fi`, `Sport`, `Thriller`, `War`, `Western`.

### Rekomendasi kosong

Rekomendasi dapat kosong jika belum ada pengguna lain dengan film favorit yang sama dan tidak ada film lain dengan genre yang sesuai. Tambahkan data pengguna dan film favorit untuk memperkaya hasil.

### GUI tidak terbuka atau tampil kosong

- Pastikan dependensi GUI sudah terpasang dengan `pip install -r requirements.txt`.
- Pastikan CustomTkinter dan Pillow berhasil diimpor pada virtual environment yang sama.
- Jika jendela terbuka tetapi data kosong, periksa indikator koneksi di sidebar dan klik **Hubungkan Ulang**.
- Jalankan `python desktop.py --smoke-test` untuk memastikan GUI dapat dimuat tanpa interaksi manual.

## Catatan Data

- Program tidak melakukan penghapusan data secara massal.
- Menghapus film favorit hanya menghapus relasi `LIKES`, bukan node `Movie`.
- Program tidak mereset database.
- Data pengujian menggunakan awalan khusus dan dibersihkan secara terpisah.
# CineGraph
Aplikasi Sistem Rekomendasi Film menggunakan Python, Neo4j, dan TMDB API.
