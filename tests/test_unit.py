import unittest

from main import (
    ValidasiError,
    buat_alasan,
    normalisasi_genre,
    normalisasi_teks,
    parse_genres,
    rapikan_teks,
    validasi_judul,
    validasi_nama,
)


class TesNormalisasi(unittest.TestCase):
    def test_rapikan_teks(self):
        self.assertEqual(rapikan_teks("  Budi   Santoso  "), "Budi Santoso")

    def test_normalisasi_teks(self):
        self.assertEqual(normalisasi_teks("  Budi   Santoso  "), "budi santoso")

    def test_normalisasi_genre_sci_fi(self):
        self.assertEqual(normalisasi_genre("Sci-FI"), "Sci-Fi")
        self.assertEqual(normalisasi_genre("science fiction"), "Sci-Fi")
        self.assertEqual(normalisasi_genre("scifi"), "Sci-Fi")

    def test_normalisasi_genre_kapitalisasi(self):
        self.assertEqual(normalisasi_genre("  ACTION "), "Action")
        self.assertEqual(normalisasi_genre("Horror"), "Horror")

    def test_normalisasi_genre_tidak_dikenal(self):
        self.assertIsNone(normalisasi_genre("Genre Ngawur"))


class TesValidasiInput(unittest.TestCase):
    def test_nama_kosong(self):
        with self.assertRaises(ValidasiError):
            validasi_nama("   ")

    def test_judul_kosong(self):
        with self.assertRaises(ValidasiError):
            validasi_judul("\t")

    def test_genre_kosong(self):
        with self.assertRaises(ValidasiError):
            parse_genres("")
        with self.assertRaises(ValidasiError):
            parse_genres(" , , ")

    def test_genre_tidak_valid(self):
        with self.assertRaises(ValidasiError):
            parse_genres("Action, Genre Ngawur")

    def test_genre_duplikat_dan_variasi(self):
        self.assertEqual(
            parse_genres("Sci-FI, sci-fi, science fiction"),
            ["Sci-Fi"],
        )
        self.assertEqual(
            parse_genres("Action, action, ACTION"),
            ["Action"],
        )


class TesAlasanRekomendasi(unittest.TestCase):
    def test_kedua_metode(self):
        alasan = buat_alasan(2, 1, ["Action"])
        self.assertIn("kedua metode", alasan)
        self.assertIn("pengguna lain", alasan)
        self.assertIn("genre yang sesuai", alasan)

    def test_collaborative_saja(self):
        alasan = buat_alasan(1, 0, [])
        self.assertIn("pengguna lain", alasan)
        self.assertNotIn("kedua metode", alasan)

    def test_content_saja(self):
        alasan = buat_alasan(0, 2, ["Sci-Fi"])
        self.assertIn("genre yang sesuai", alasan)
        self.assertIn("Sci-Fi", alasan)

    def test_tanpa_alasan(self):
        self.assertEqual(
            buat_alasan(0, 0, []),
            "Tidak ada kesamaan pengguna maupun genre.",
        )


if __name__ == "__main__":
    unittest.main()
