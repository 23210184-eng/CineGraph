# Poster Film

Folder ini menyimpan gambar poster untuk Desktop GUI. Poster akan tampil pada
kartu rekomendasi di Dashboard dan halaman Rekomendasi, daftar film favorit,
serta grid Katalog Film.

## Cara Menambahkan Poster

1. Siapkan gambar poster berformat `.png`, `.webp`, `.jpg`, `.jpeg`, `.bmp`,
   atau `.gif`.
2. Beri nama file sama dengan judul film di database Neo4j.
3. Simpan file ke folder `assets/posters/`.
4. Buka kembali halaman GUI atau klik **Muat Ulang**. Aplikasi memindai folder
   secara otomatis, jadi tidak perlu mengubah kode.

Pencocokan judul tidak membedakan huruf besar/kecil dan mengabaikan spasi
serta tanda baca.

## Contoh

| Judul film di database | Nama file yang cocok |
| --- | --- |
| `Interstellar` | `Interstellar.jpg` |
| `The Dark Knight` | `the-dark-knight.png` |
| `Spider-Man: No Way Home` | `SpiderManNoWayHome.webp` |
| `Sci-Fi Story` | `sci fi story.png` |

Semua contoh di atas cocok karena perbandingan hanya memakai huruf dan angka.

## Prioritas Format

Jika ada beberapa file dengan judul yang sama, urutan prioritasnya:

1. `.png`
2. `.webp`
3. `.jpg`
4. `.jpeg`
5. `.bmp`
6. `.gif`

## Placeholder

Jika poster belum tersedia, aplikasi menampilkan placeholder bergambar film
secara otomatis. Aplikasi tidak akan error karena poster yang hilang.

## Rasio Gambar

Poster ditampilkan dengan rasio tetap sehingga tidak gepeng. Gambar akan
dipotong perlahan (crop) agar memenuhi kartu. Gunakan gambar dengan orientasi
potret dan rasio sekitar 2:3 untuk hasil terbaik.

## Performa

Gambar dibaca sekali lalu disimpan di cache. Folder dipindai ulang hanya saat
halaman dibuka atau dimuat ulang, sehingga GUI tetap ringan meskipun berisi
banyak poster.
