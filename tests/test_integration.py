import unittest

from config import DATABASE, create_driver
from main import (
    KesalahanAplikasi,
    PenggunaTanpaFavorit,
    PenggunaTidakDitemukan,
    ValidasiError,
    ambil_daftar_film,
    ambil_daftar_pengguna,
    ambil_film_favorit,
    ambil_rekomendasi,
    ambil_statistik,
    hapus_film_favorit_data,
    normalisasi_teks,
    simpan_film_favorit,
    simpan_pengguna,
)

PREFIX = "TESTSISTEMREKOMENDASI_"


class TesIntegrasiNeo4j(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.driver = create_driver()
            cls.driver.verify_connectivity()
        except Exception as error:
            raise unittest.SkipTest(
                "Neo4j tidak tersedia untuk pengujian integrasi: "
                f"{type(error).__name__}"
            )

        cls.session = cls.driver.session(database=DATABASE)
        cls._bersihkan_data_uji()

    @classmethod
    def tearDownClass(cls):
        session = getattr(cls, "session", None)
        driver = getattr(cls, "driver", None)

        try:
            if session is not None:
                cls._bersihkan_data_uji()
        finally:
            if session is not None:
                session.close()
            if driver is not None:
                driver.close()

    @classmethod
    def _bersihkan_data_uji(cls):
        cls.session.run(
            """
            MATCH (u:User)
            WHERE u.name STARTS WITH $prefix
            DETACH DELETE u
            """,
            prefix=PREFIX,
        ).consume()

        cls.session.run(
            """
            MATCH (m:Movie)
            WHERE m.title_normal STARTS WITH $prefix
            DETACH DELETE m
            """,
            prefix=PREFIX.lower(),
        ).consume()

    def _nama(self, suffix):
        return f"{PREFIX}{suffix}"

    def _film(self, suffix):
        return f"{PREFIX}{suffix}"

    def _tambah_pengguna(self, suffix):
        return simpan_pengguna(self.session, self._nama(suffix))

    def _tambah_film(self, pengguna, suffix, genres):
        return simpan_film_favorit(
            self.session,
            pengguna,
            self._film(suffix),
            genres,
        )

    def _cari_rekomendasi(self, hasil, judul):
        return next(
            (
                rekomendasi
                for rekomendasi in hasil["rekomendasi"]
                if rekomendasi["rekomendasi"] == judul
            ),
            None,
        )

    def test_01_tambah_pengguna_baru(self):
        hasil = self._tambah_pengguna("Pengguna Baru")

        self.assertTrue(hasil["dibuat"])
        self.assertEqual(hasil["nama"], self._nama("Pengguna Baru"))

        jumlah = self.session.run(
            """
            MATCH (u:User)
            WHERE toLower(trim(u.name)) = $nama
            RETURN count(u) AS jumlah
            """,
            nama=normalisasi_teks(self._nama("Pengguna Baru")),
        ).single()["jumlah"]

        self.assertEqual(jumlah, 1)

    def test_02_cegah_pengguna_duplikat(self):
        pertama = self._tambah_pengguna("Pengguna Duplikat")
        kedua = simpan_pengguna(
            self.session,
            self._nama("pengguna duplikat"),
        )

        self.assertTrue(pertama["dibuat"])
        self.assertFalse(kedua["dibuat"])

        jumlah = self.session.run(
            """
            MATCH (u:User)
            WHERE toLower(trim(u.name)) = $nama
            RETURN count(u) AS jumlah
            """,
            nama=normalisasi_teks(self._nama("Pengguna Duplikat")),
        ).single()["jumlah"]

        self.assertEqual(jumlah, 1)

    def test_03_tambah_film_favorit(self):
        pengguna = self._nama("Pengguna Film")
        self._tambah_pengguna("Pengguna Film")

        hasil = self._tambah_film(
            pengguna,
            "Film Favorit",
            "Sci-FI, sci-fi",
        )

        self.assertEqual(hasil["genres"], ["Sci-Fi"])
        self.assertFalse(hasil["sudah_ada"])

        favorit = ambil_film_favorit(self.session, pengguna)
        self.assertEqual(len(favorit["films"]), 1)
        self.assertEqual(
            favorit["films"][0]["judul"],
            self._film("Film Favorit"),
        )

    def test_04_cegah_film_duplikat_kapitalisasi(self):
        pengguna_satu = self._nama("Pengguna Kapitalisasi Satu")
        pengguna_dua = self._nama("Pengguna Kapitalisasi Dua")
        self._tambah_pengguna("Pengguna Kapitalisasi Satu")
        self._tambah_pengguna("Pengguna Kapitalisasi Dua")

        self._tambah_film(
            pengguna_satu,
            "Film Kapitalisasi",
            "Sci-Fi",
        )
        self._tambah_film(
            pengguna_dua,
            "film kapitalisasi",
            "Action",
        )

        judul_normal = normalisasi_teks(self._film("Film Kapitalisasi"))

        jumlah_film = self.session.run(
            """
            MATCH (m:Movie)
            WHERE m.title_normal = $judul_normal
            RETURN count(m) AS jumlah
            """,
            judul_normal=judul_normal,
        ).single()["jumlah"]

        jumlah_relasi = self.session.run(
            """
            MATCH (:User)-[relasi:LIKES]->(m:Movie)
            WHERE m.title_normal = $judul_normal
            RETURN count(relasi) AS jumlah
            """,
            judul_normal=judul_normal,
        ).single()["jumlah"]

        genres = self.session.run(
            """
            MATCH (m:Movie)
            WHERE m.title_normal = $judul_normal
            RETURN m.genres AS genres
            """,
            judul_normal=judul_normal,
        ).single()["genres"]

        self.assertEqual(jumlah_film, 1)
        self.assertEqual(jumlah_relasi, 2)
        self.assertEqual(set(genres), {"Sci-Fi", "Action"})

    def test_05_lihat_film_favorit(self):
        pengguna = self._nama("Pengguna Lihat Favorit")
        self._tambah_pengguna("Pengguna Lihat Favorit")
        self._tambah_film(pengguna, "Film Favorit Satu", "Drama")
        self._tambah_film(pengguna, "Film Favorit Dua", "Romance")

        favorit = ambil_film_favorit(self.session, pengguna)
        judul = {film["judul"] for film in favorit["films"]}

        self.assertEqual(len(favorit["films"]), 2)
        self.assertIn(self._film("Film Favorit Satu"), judul)
        self.assertIn(self._film("Film Favorit Dua"), judul)

    def test_06_collaborative_filtering(self):
        target = self._nama("Target CF")
        tetangga = self._nama("Tetangga CF")
        self._tambah_pengguna("Target CF")
        self._tambah_pengguna("Tetangga CF")

        self._tambah_film(target, "Film Dasar CF", "Drama")
        self._tambah_film(tetangga, "Film Dasar CF", "Drama")
        self._tambah_film(tetangga, "Film Kandidat CF", "Horror")

        hasil = ambil_rekomendasi(self.session, target)
        rekomendasi = self._cari_rekomendasi(
            hasil,
            self._film("Film Kandidat CF"),
        )

        self.assertIsNotNone(rekomendasi)
        self.assertEqual(rekomendasi["skor_pengguna"], 1)
        self.assertEqual(rekomendasi["skor_genre"], 0)
        self.assertEqual(rekomendasi["skor_akhir"], 2)

    def test_07_content_based_filtering(self):
        target = self._nama("Target CB")
        pengguna_lain = self._nama("Pengguna CB")
        self._tambah_pengguna("Target CB")
        self._tambah_pengguna("Pengguna CB")

        self._tambah_film(target, "Film Dasar CB", "Sci-Fi")
        self._tambah_film(pengguna_lain, "Film Kandidat CB", "Sci-Fi")

        hasil = ambil_rekomendasi(self.session, target)
        rekomendasi = self._cari_rekomendasi(
            hasil,
            self._film("Film Kandidat CB"),
        )

        self.assertIsNotNone(rekomendasi)
        self.assertEqual(rekomendasi["skor_pengguna"], 0)
        self.assertEqual(rekomendasi["skor_genre"], 1)
        self.assertEqual(rekomendasi["genre_cocok"], ["Sci-Fi"])
        self.assertEqual(rekomendasi["skor_akhir"], 1)

    def test_08_hybrid_recommendation(self):
        target = self._nama("Target Hybrid")
        tetangga = self._nama("Tetangga Hybrid")
        self._tambah_pengguna("Target Hybrid")
        self._tambah_pengguna("Tetangga Hybrid")

        self._tambah_film(target, "Film Dasar Hybrid", "Action, Sci-Fi")
        self._tambah_film(tetangga, "Film Dasar Hybrid", "Action, Sci-Fi")
        self._tambah_film(tetangga, "Film Kandidat Hybrid", "Action, Drama")

        hasil = ambil_rekomendasi(self.session, target)
        rekomendasi = self._cari_rekomendasi(
            hasil,
            self._film("Film Kandidat Hybrid"),
        )

        self.assertIsNotNone(rekomendasi)
        self.assertEqual(rekomendasi["skor_pengguna"], 1)
        self.assertEqual(rekomendasi["skor_genre"], 1)
        self.assertEqual(
            rekomendasi["skor_akhir"],
            rekomendasi["skor_pengguna"] * 2
            + rekomendasi["skor_genre"],
        )
        self.assertEqual(rekomendasi["skor_akhir"], 3)

    def test_09_input_kosong(self):
        with self.assertRaises(ValidasiError):
            simpan_pengguna(self.session, "   ")

        pengguna = self._nama("Pengguna Input Kosong")
        self._tambah_pengguna("Pengguna Input Kosong")

        with self.assertRaises(ValidasiError):
            simpan_film_favorit(
                self.session,
                pengguna,
                "   ",
                "Action",
            )

        with self.assertRaises(ValidasiError):
            simpan_film_favorit(
                self.session,
                pengguna,
                self._film("Film Input Kosong"),
                "   ",
            )

        with self.assertRaises(ValidasiError):
            simpan_film_favorit(
                self.session,
                pengguna,
                self._film("Film Input Kosong"),
                " , , ",
            )

    def test_10_genre_tidak_valid(self):
        pengguna = self._nama("Pengguna Genre Salah")
        self._tambah_pengguna("Pengguna Genre Salah")

        with self.assertRaises(ValidasiError):
            simpan_film_favorit(
                self.session,
                pengguna,
                self._film("Film Genre Salah"),
                "Genre Ngawur",
            )

        jumlah = self.session.run(
            """
            MATCH (m:Movie)
            WHERE m.title_normal = $judul_normal
            RETURN count(m) AS jumlah
            """,
            judul_normal=normalisasi_teks(self._film("Film Genre Salah")),
        ).single()["jumlah"]

        self.assertEqual(jumlah, 0)

    def test_11_pengguna_belum_terdaftar(self):
        nama = self._nama("Pengguna Hantu")

        with self.assertRaises(PenggunaTidakDitemukan):
            ambil_rekomendasi(self.session, nama)

        with self.assertRaises(PenggunaTidakDitemukan):
            ambil_film_favorit(self.session, nama)

    def test_12_pengguna_tanpa_film_favorit(self):
        pengguna = self._nama("Pengguna Tanpa Favorit")
        self._tambah_pengguna("Pengguna Tanpa Favorit")

        with self.assertRaises(PenggunaTanpaFavorit):
            ambil_rekomendasi(self.session, pengguna)

    def test_13_hapus_relasi_favorit(self):
        pengguna = self._nama("Pengguna Hapus Favorit")
        self._tambah_pengguna("Pengguna Hapus Favorit")
        self._tambah_film(pengguna, "Film Hapus Favorit", "Horror")

        hasil = hapus_film_favorit_data(
            self.session,
            pengguna,
            self._film("Film Hapus Favorit"),
        )

        self.assertEqual(hasil["jumlah_dihapus"], 1)

        favorit = ambil_film_favorit(self.session, pengguna)
        self.assertEqual(favorit["films"], [])

        jumlah_film = self.session.run(
            """
            MATCH (m:Movie)
            WHERE m.title_normal = $judul_normal
            RETURN count(m) AS jumlah
            """,
            judul_normal=normalisasi_teks(
                self._film("Film Hapus Favorit")
            ),
        ).single()["jumlah"]

        self.assertEqual(jumlah_film, 1)

        with self.assertRaises(KesalahanAplikasi):
            hapus_film_favorit_data(
                self.session,
                pengguna,
                self._film("Film Hapus Favorit"),
            )

    def test_14_tidak_ada_rekomendasi(self):
        jumlah_dokumenter = self.session.run(
            """
            MATCH (m:Movie)
            WHERE 'Documentary' IN coalesce(m.genres, [])
            RETURN count(m) AS jumlah
            """
        ).single()["jumlah"]

        if jumlah_dokumenter > 0:
            self.skipTest(
                "Sudah ada film bergenre Documentary pada database."
            )

        pengguna = self._nama("Pengguna Tanpa Rekomendasi")
        self._tambah_pengguna("Pengguna Tanpa Rekomendasi")
        self._tambah_film(
            pengguna,
            "Film Dokumenter Unik",
            "Documentary",
        )

        hasil = ambil_rekomendasi(self.session, pengguna)
        self.assertEqual(hasil["rekomendasi"], [])

    def test_15_statistik_sistem(self):
        statistik = ambil_statistik(self.session)

        self.assertIn("total_pengguna", statistik)
        self.assertIn("total_film", statistik)
        self.assertIn("total_relasi", statistik)
        self.assertGreaterEqual(statistik["total_pengguna"], 1)
        self.assertGreaterEqual(statistik["total_film"], 1)
        self.assertGreaterEqual(statistik["total_relasi"], 1)

    def test_16_daftar_pengguna(self):
        nama_zeta = self._nama("Zeta Daftar")
        nama_alpha = self._nama("Alpha Daftar")
        self._tambah_pengguna("Zeta Daftar")
        self._tambah_pengguna("Alpha Daftar")

        daftar = ambil_daftar_pengguna(self.session)

        self.assertIn(nama_zeta, daftar)
        self.assertIn(nama_alpha, daftar)
        self.assertEqual(len(daftar), len(set(daftar)))
        self.assertEqual(
            daftar,
            sorted(daftar, key=normalisasi_teks),
        )
        self.assertLess(
            daftar.index(nama_alpha),
            daftar.index(nama_zeta),
        )

    def test_17_daftar_film_katalog(self):
        pengguna = self._nama("Pengguna Katalog")
        self._tambah_pengguna("Pengguna Katalog")
        self._tambah_film(pengguna, "Film Katalog", "Comedy")

        films = ambil_daftar_film(self.session)
        judul = {film["judul"] for film in films}

        self.assertIn(self._film("Film Katalog"), judul)
        self.assertEqual(
            films,
            sorted(films, key=lambda film: film["judul"].lower()),
        )

        film_katalog = next(
            film
            for film in films
            if film["judul"] == self._film("Film Katalog")
        )
        self.assertEqual(film_katalog["genres"], ["Comedy"])


if __name__ == "__main__":
    unittest.main()
