from datetime import datetime, timezone

from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

from config import DATABASE, create_driver

GENRE_ALIASES = {
    "action": "Action",
    "adventure": "Adventure",
    "animation": "Animation",
    "comedy": "Comedy",
    "crime": "Crime",
    "documentary": "Documentary",
    "drama": "Drama",
    "family": "Family",
    "fantasy": "Fantasy",
    "film noir": "Film-Noir",
    "history": "History",
    "horror": "Horror",
    "music": "Music",
    "mystery": "Mystery",
    "romance": "Romance",
    "sci fi": "Sci-Fi",
    "scifi": "Sci-Fi",
    "science fiction": "Sci-Fi",
    "sport": "Sport",
    "thriller": "Thriller",
    "war": "War",
    "western": "Western",
}

GENRE_LIST = [
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "Film-Noir",
    "History",
    "Horror",
    "Music",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Sport",
    "Thriller",
    "War",
    "Western",
]


class KesalahanAplikasi(Exception):
    pass


class ValidasiError(KesalahanAplikasi):
    pass


class PenggunaTidakDitemukan(KesalahanAplikasi):
    pass


class PenggunaTanpaFavorit(KesalahanAplikasi):
    pass


class FilmTidakDitemukan(KesalahanAplikasi):
    pass


def rapikan_teks(nilai):
    return " ".join(nilai.strip().split())


def normalisasi_teks(nilai):
    return rapikan_teks(nilai).lower()


def normalisasi_genre(nilai):
    kunci = normalisasi_teks(nilai).replace("-", " ").replace("_", " ")
    kunci = " ".join(kunci.split())
    return GENRE_ALIASES.get(kunci)


def parse_genres(teks):
    if not isinstance(teks, str) or not teks.strip():
        raise ValidasiError("Genre tidak boleh kosong.")

    genres = []

    for bagian in teks.split(","):
        bagian = bagian.strip()

        if not bagian:
            continue

        genre = normalisasi_genre(bagian)

        if genre is None:
            raise ValidasiError(
                f"Genre '{bagian}' tidak dikenal. "
                f"Genre yang tersedia: {', '.join(GENRE_LIST)}."
            )

        if genre not in genres:
            genres.append(genre)

    if not genres:
        raise ValidasiError("Genre tidak boleh kosong.")

    return genres


def gabungkan_genre(*daftar_genre):
    hasil = []

    for daftar in daftar_genre:
        if not daftar:
            continue

        if not isinstance(daftar, list):
            daftar = [daftar]

        for genre in daftar:
            if genre is not None and genre not in hasil:
                hasil.append(genre)

    return hasil


def validasi_nama(nama):
    if not isinstance(nama, str) or not nama.strip():
        raise ValidasiError("Nama pengguna tidak boleh kosong.")

    return rapikan_teks(nama), normalisasi_teks(nama)


def validasi_judul(judul):
    if not isinstance(judul, str) or not judul.strip():
        raise ValidasiError("Judul film tidak boleh kosong.")

    return rapikan_teks(judul), normalisasi_teks(judul)


def buat_alasan(skor_pengguna, skor_genre, genre_cocok):
    alasan = []

    if skor_pengguna > 0:
        alasan.append(
            f"{skor_pengguna} pengguna lain memiliki film favorit yang sama "
            "dan juga menyukai film ini"
        )

    if skor_genre > 0:
        genre = ", ".join(genre_cocok) if genre_cocok else "genre yang sesuai"
        alasan.append(
            f"memiliki genre yang sesuai dengan film favorit Anda ({genre})"
        )

    if not alasan:
        return "Tidak ada kesamaan pengguna maupun genre."

    if skor_pengguna > 0 and skor_genre > 0:
        return "Mendapat nilai dari kedua metode: " + "; ".join(alasan) + "."

    return "Karena " + "; ".join(alasan) + "."


def _ambil_pengguna(tx, nama_normal):
    return tx.run(
        """
        MATCH (u:User)
        WHERE toLower(trim(u.name)) = $nama_normal
        RETURN
            elementId(u) AS id,
            u.name AS nama
        ORDER BY u.name
        LIMIT 1
        """,
        nama_normal=nama_normal,
    ).single()


def _ambil_film(tx, judul_normal):
    return tx.run(
        """
        MATCH (m:Movie)
        WHERE m.title_normal = $judul_normal
           OR toLower(trim(m.title)) = $judul_normal
        RETURN
            elementId(m) AS id,
            m.title AS judul,
            m.title_normal AS judul_normal,
            coalesce(
                m.genres,
                CASE WHEN m.genre IS NULL THEN [] ELSE [m.genre] END
            ) AS genres
        ORDER BY
            CASE WHEN m.title_normal = $judul_normal THEN 0 ELSE 1 END,
            m.title
        LIMIT 1
        """,
        judul_normal=judul_normal,
    ).single()


def simpan_pengguna(session, nama):
    nama_tampil, nama_normal = validasi_nama(nama)

    def pekerjaan(tx):
        pengguna = _ambil_pengguna(tx, nama_normal)

        if pengguna:
            return {"nama": pengguna["nama"], "dibuat": False}

        tx.run(
            """
            CREATE (u:User {
                name: $nama,
                dibuat: $dibuat
            })
            """,
            nama=nama_tampil,
            dibuat=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

        return {"nama": nama_tampil, "dibuat": True}

    return session.execute_write(pekerjaan)


def simpan_film_favorit(session, nama, judul, genre_input):
    nama_tampil, nama_normal = validasi_nama(nama)
    judul_tampil, judul_normal = validasi_judul(judul)
    genres = parse_genres(genre_input)
    waktu = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def pekerjaan(tx):
        pengguna = _ambil_pengguna(tx, nama_normal)

        if not pengguna:
            raise PenggunaTidakDitemukan(
                f"Pengguna '{nama_tampil}' belum terdaftar."
            )

        film = _ambil_film(tx, judul_normal)

        if film:
            genres_final = gabungkan_genre(film["genres"], genres)

            tx.run(
                """
                MATCH (m:Movie)
                WHERE elementId(m) = $id
                SET m.genres = $genres,
                    m.title_normal = coalesce(m.title_normal, $judul_normal)
                """,
                id=film["id"],
                genres=genres_final,
                judul_normal=judul_normal,
            )

            film_id = film["id"]
            judul_final = film["judul"]
        else:
            genres_final = genres

            hasil_film = tx.run(
                """
                MERGE (m:Movie {title_normal: $judul_normal})
                ON CREATE SET
                    m.title = $judul,
                    m.genres = $genres,
                    m.dibuat = $dibuat
                RETURN elementId(m) AS id, m.title AS judul
                """,
                judul=judul_tampil,
                judul_normal=judul_normal,
                genres=genres_final,
                dibuat=waktu,
            ).single()

            film_id = hasil_film["id"]
            judul_final = hasil_film["judul"]

        hasil_relasi = tx.run(
            """
            MATCH (u:User)
            WHERE elementId(u) = $user_id
            MATCH (m:Movie)
            WHERE elementId(m) = $film_id
            OPTIONAL MATCH (u)-[relasi_lama:LIKES]->(m)
            WITH u, m, relasi_lama IS NOT NULL AS sudah_ada
            MERGE (u)-[relasi:LIKES]->(m)
            ON CREATE SET relasi.dibuat = $dibuat
            RETURN sudah_ada
            """,
            user_id=pengguna["id"],
            film_id=film_id,
            dibuat=waktu,
        ).single()

        return {
            "nama": pengguna["nama"],
            "judul": judul_final,
            "genres": genres_final,
            "sudah_ada": hasil_relasi["sudah_ada"],
        }

    return session.execute_write(pekerjaan)


def ambil_film_favorit(session, nama):
    nama_tampil, nama_normal = validasi_nama(nama)

    def pekerjaan(tx):
        pengguna = _ambil_pengguna(tx, nama_normal)

        if not pengguna:
            raise PenggunaTidakDitemukan(
                f"Pengguna '{nama_tampil}' belum terdaftar."
            )

        films = tx.run(
            """
            MATCH (u:User)-[:LIKES]->(m:Movie)
            WHERE elementId(u) = $id
            RETURN DISTINCT
                m.title AS judul,
                coalesce(
                    m.genres,
                    CASE WHEN m.genre IS NULL THEN [] ELSE [m.genre] END
                ) AS genres
            ORDER BY toLower(m.title), m.title
            """,
            id=pengguna["id"],
        ).data()

        return {"nama": pengguna["nama"], "films": films}

    return session.execute_read(pekerjaan)


def ambil_daftar_film(session):
    def pekerjaan(tx):
        return [
            {
                "judul": record["judul"],
                "genres": record["genres"],
            }
            for record in tx.run(
                """
                MATCH (m:Movie)
                RETURN
                    m.title AS judul,
                    coalesce(
                        m.genres,
                        CASE WHEN m.genre IS NULL THEN [] ELSE [m.genre] END
                    ) AS genres
                ORDER BY toLower(m.title), m.title
                """
            ).data()
        ]

    return session.execute_read(pekerjaan)


def ambil_daftar_pengguna(session):
    def pekerjaan(tx):
        return [
            record["nama"]
            for record in tx.run(
                """
                MATCH (u:User)
                RETURN u.name AS nama
                ORDER BY toLower(u.name), u.name
                """
            ).data()
        ]

    return session.execute_read(pekerjaan)


def ambil_rekomendasi(session, nama):
    nama_tampil, nama_normal = validasi_nama(nama)

    def pekerjaan(tx):
        pengguna = _ambil_pengguna(tx, nama_normal)

        if not pengguna:
            raise PenggunaTidakDitemukan(
                f"Pengguna '{nama_tampil}' belum terdaftar."
            )

        total_favorit = tx.run(
            """
            MATCH (u:User)
            WHERE elementId(u) = $id
            OPTIONAL MATCH (u)-[:LIKES]->(m:Movie)
            RETURN count(m) AS total
            """,
            id=pengguna["id"],
        ).single()["total"]

        if total_favorit == 0:
            raise PenggunaTanpaFavorit(
                f"Pengguna '{pengguna['nama']}' belum memiliki film favorit. "
                "Tambahkan film favorit terlebih dahulu."
            )

        rekomendasi = tx.run(
            """
            MATCH (target:User)
            WHERE elementId(target) = $id
            MATCH (target)-[:LIKES]->(film_favorit:Movie)

            WITH target, collect(DISTINCT film_favorit) AS daftar_favorit

            WITH target,
                reduce(
                    acc = [],
                    film IN daftar_favorit |
                    acc + coalesce(
                        film.genres,
                        CASE
                            WHEN film.genre IS NULL THEN []
                            ELSE [film.genre]
                        END
                    )
                ) AS genre_mentah

            WITH target,
                [genre IN genre_mentah WHERE genre IS NOT NULL]
                AS genre_favorit

            MATCH (kandidat:Movie)
            WHERE NOT (target)-[:LIKES]->(kandidat)

            OPTIONAL MATCH
                (target)-[:LIKES]->(film_sama:Movie)
                <-[:LIKES]-(pengguna_lain:User)
                -[:LIKES]->(kandidat)

            WITH kandidat, genre_favorit,
                count(DISTINCT pengguna_lain) AS skor_pengguna

            WITH kandidat, genre_favorit, skor_pengguna,
                [
                    genre IN coalesce(
                        kandidat.genres,
                        CASE
                            WHEN kandidat.genre IS NULL THEN []
                            ELSE [kandidat.genre]
                        END
                    )
                    WHERE genre IS NOT NULL
                      AND genre IN genre_favorit
                ] AS genre_cocok

            WITH kandidat,
                skor_pengguna,
                genre_cocok,
                size(genre_cocok) AS skor_genre,
                (skor_pengguna * 2 + size(genre_cocok)) AS skor_akhir

            WHERE skor_pengguna > 0 OR skor_genre > 0

            RETURN
                kandidat.title AS rekomendasi,
                coalesce(
                    kandidat.genres,
                    CASE
                        WHEN kandidat.genre IS NULL THEN []
                        ELSE [kandidat.genre]
                    END
                ) AS genres,
                genre_cocok,
                skor_pengguna,
                skor_genre,
                skor_akhir

            ORDER BY skor_akhir DESC, toLower(kandidat.title), kandidat.title
            """,
            id=pengguna["id"],
        ).data()

        return {"nama": pengguna["nama"], "rekomendasi": rekomendasi}

    return session.execute_read(pekerjaan)


def hapus_film_favorit_data(session, nama, judul):
    nama_tampil, nama_normal = validasi_nama(nama)
    judul_tampil, judul_normal = validasi_judul(judul)

    def pekerjaan(tx):
        pengguna = _ambil_pengguna(tx, nama_normal)

        if not pengguna:
            raise PenggunaTidakDitemukan(
                f"Pengguna '{nama_tampil}' belum terdaftar."
            )

        film = _ambil_film(tx, judul_normal)

        if not film:
            raise FilmTidakDitemukan(
                f"Film '{judul_tampil}' tidak ditemukan."
            )

        jumlah = tx.run(
            """
            MATCH (u:User), (m:Movie)
            WHERE elementId(u) = $user_id
            AND elementId(m) = $film_id
            OPTIONAL MATCH (u)-[relasi:LIKES]->(m)
            RETURN count(relasi) AS jumlah
            """,
            user_id=pengguna["id"],
            film_id=film["id"],
        ).single()["jumlah"]

        if jumlah == 0:
            raise KesalahanAplikasi(
                f"Film '{film['judul']}' tidak ada dalam daftar favorit "
                f"pengguna '{pengguna['nama']}'."
            )

        tx.run(
            """
            MATCH (u:User)-[relasi:LIKES]->(m:Movie)
            WHERE elementId(u) = $user_id
            AND elementId(m) = $film_id
            DELETE relasi
            """,
            user_id=pengguna["id"],
            film_id=film["id"],
        )

        return {
            "nama": pengguna["nama"],
            "judul": film["judul"],
            "jumlah_dihapus": jumlah,
        }

    return session.execute_write(pekerjaan)


def ambil_statistik(session):
    def pekerjaan(tx):
        hasil = tx.run(
            """
            MATCH (u:User)
            WITH count(u) AS total_pengguna
            MATCH (m:Movie)
            WITH total_pengguna, count(m) AS total_film
            OPTIONAL MATCH ()-[relasi:LIKES]->()
            RETURN
                total_pengguna,
                total_film,
                count(relasi) AS total_relasi
            """
        ).single()

        return {
            "total_pengguna": hasil["total_pengguna"],
            "total_film": hasil["total_film"],
            "total_relasi": hasil["total_relasi"],
        }

    return session.execute_read(pekerjaan)


def minta_input_wajib(prompt, label):
    nilai = input(prompt)

    if not nilai.strip():
        raise ValidasiError(f"{label} tidak boleh kosong.")

    return nilai


def tampilkan_menu():
    print("\n" + "=" * 42)
    print("        SISTEM REKOMENDASI FILM")
    print("=" * 42)
    print("1. Tambah pengguna")
    print("2. Tambah film favorit pengguna")
    print("3. Lihat rekomendasi film")
    print("4. Lihat film favorit pengguna")
    print("5. Keluar")
    print("6. Hapus film favorit pengguna")
    print("7. Statistik sistem")
    print("-" * 42)


def tambah_pengguna(session):
    nama = minta_input_wajib(
        "Masukkan nama pengguna baru: ",
        "Nama pengguna",
    )

    hasil = simpan_pengguna(session, nama)

    if hasil["dibuat"]:
        print(f"Pengguna '{hasil['nama']}' berhasil ditambahkan.")
    else:
        print(
            f"Pengguna '{hasil['nama']}' sudah terdaftar. "
            "Data tidak diduplikasi."
        )


def tambah_film_favorit(session):
    nama = minta_input_wajib("Masukkan nama pengguna: ", "Nama pengguna")
    judul = minta_input_wajib("Masukkan judul film: ", "Judul film")
    genre_input = input(
        "Masukkan genre film (pisahkan dengan koma): "
    )

    hasil = simpan_film_favorit(session, nama, judul, genre_input)

    if hasil["sudah_ada"]:
        print(
            f"Film '{hasil['judul']}' sudah ada di daftar favorit "
            f"pengguna '{hasil['nama']}'. Data genre tetap diperbarui."
        )
    else:
        print(
            f"Film '{hasil['judul']}' berhasil ditambahkan ke daftar "
            f"favorit pengguna '{hasil['nama']}'."
        )

    print("Genre:", ", ".join(hasil["genres"]))


def lihat_film_favorit(session):
    nama = minta_input_wajib("Masukkan nama pengguna: ", "Nama pengguna")
    hasil = ambil_film_favorit(session, nama)

    print(f"\nDaftar film favorit {hasil['nama']}:")

    if not hasil["films"]:
        print("Belum ada film favorit yang tersimpan.")
        return

    for nomor, film in enumerate(hasil["films"], start=1):
        genres = gabungkan_genre(film["genres"]) or ["Tidak diketahui"]
        print(f"{nomor}. {film['judul']}")
        print(f"   Genre: {', '.join(genres)}")


def tampilkan_rekomendasi(session):
    nama = minta_input_wajib("Masukkan nama pengguna: ", "Nama pengguna")
    hasil = ambil_rekomendasi(session, nama)

    print(f"\nRekomendasi film untuk {hasil['nama']}:")

    if not hasil["rekomendasi"]:
        print(
            "Tidak ada rekomendasi yang dapat diberikan saat ini. "
            "Tambahkan lebih banyak pengguna dan film favorit."
        )
        return

    for nomor, rekomendasi in enumerate(hasil["rekomendasi"], start=1):
        genres = gabungkan_genre(rekomendasi["genres"])
        genre_cocok = gabungkan_genre(rekomendasi["genre_cocok"])
        alasan = buat_alasan(
            rekomendasi["skor_pengguna"],
            rekomendasi["skor_genre"],
            genre_cocok,
        )

        print(f"\n{nomor}. {rekomendasi['rekomendasi']}")
        print(
            "   Genre          : "
            + (", ".join(genres) if genres else "Tidak diketahui")
        )
        print(
            f"   Skor pengguna  : {rekomendasi['skor_pengguna']} "
            f"(dikalikan 2 = {rekomendasi['skor_pengguna'] * 2})"
        )
        print(f"   Skor genre     : {rekomendasi['skor_genre']}")
        print(f"   Skor akhir     : {rekomendasi['skor_akhir']}")
        print(f"   Alasan         : {alasan}")


def hapus_film_favorit(session):
    nama = minta_input_wajib("Masukkan nama pengguna: ", "Nama pengguna")
    judul = minta_input_wajib("Masukkan judul film: ", "Judul film")

    hasil = hapus_film_favorit_data(session, nama, judul)

    print(
        f"Film '{hasil['judul']}' berhasil dihapus dari daftar favorit "
        f"pengguna '{hasil['nama']}'."
    )


def tampilkan_statistik(session):
    statistik = ambil_statistik(session)

    print("\nStatistik sistem:")
    print(f"Total pengguna       : {statistik['total_pengguna']}")
    print(f"Total film           : {statistik['total_film']}")
    print(f"Total relasi favorit : {statistik['total_relasi']}")


def main():
    driver = None

    try:
        driver = create_driver()
        driver.verify_connectivity()
        print("Koneksi Neo4j berhasil.")

        with driver.session(database=DATABASE) as session:
            while True:
                tampilkan_menu()
                pilihan = input("Pilih menu (1-7): ").strip()

                try:
                    if pilihan == "1":
                        tambah_pengguna(session)
                    elif pilihan == "2":
                        tambah_film_favorit(session)
                    elif pilihan == "3":
                        tampilkan_rekomendasi(session)
                    elif pilihan == "4":
                        lihat_film_favorit(session)
                    elif pilihan == "5":
                        print("Program selesai.")
                        break
                    elif pilihan == "6":
                        hapus_film_favorit(session)
                    elif pilihan == "7":
                        tampilkan_statistik(session)
                    else:
                        print(
                            "Pilihan tidak valid. Silakan pilih 1 sampai 7."
                        )
                except KesalahanAplikasi as error:
                    print(f"Gagal: {error}")
                except ServiceUnavailable:
                    print(
                        "Koneksi ke Neo4j terputus. Program dihentikan. "
                        "Periksa server Neo4j lalu jalankan kembali program."
                    )
                    break
                except AuthError:
                    print(
                        "Autentikasi Neo4j gagal. Periksa NEO4J_USERNAME "
                        "dan NEO4J_PASSWORD pada file .env."
                    )
                    break
                except Neo4jError:
                    print(
                        "Terjadi kesalahan pada database Neo4j. "
                        "Operasi dibatalkan. Silakan coba lagi."
                    )
                except Exception:
                    print(
                        "Terjadi kesalahan tak terduga. "
                        "Operasi dibatalkan. Silakan coba lagi."
                    )

    except ServiceUnavailable:
        print(
            "Tidak dapat terhubung ke Neo4j. Pastikan server Neo4j "
            "sudah berjalan dan konfigurasi koneksi pada file .env benar."
        )
    except AuthError:
        print(
            "Autentikasi Neo4j gagal. Periksa NEO4J_USERNAME dan "
            "NEO4J_PASSWORD pada file .env."
        )
    except ValueError as error:
        print("Kesalahan konfigurasi:", error)
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")
    except EOFError:
        print("\nProgram selesai.")
    except Neo4jError:
        print(
            "Terjadi kesalahan pada database Neo4j. "
            "Periksa konfigurasi koneksi dan pastikan server berjalan."
        )
    except Exception:
        print(
            "Terjadi kesalahan tak terduga saat menjalankan program. "
            "Silakan periksa kembali data dan konfigurasi Anda."
        )
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    main()
