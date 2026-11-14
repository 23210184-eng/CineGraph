import sys
import tkinter as tk
from functools import lru_cache
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from config import DATABASE, create_driver
from main import (
    GENRE_LIST,
    KesalahanAplikasi,
    PenggunaTanpaFavorit,
    PenggunaTidakDitemukan,
    ambil_daftar_film,
    ambil_daftar_pengguna,
    ambil_film_favorit,
    ambil_rekomendasi,
    ambil_statistik,
    buat_alasan,
    gabungkan_genre,
    hapus_film_favorit_data,
    simpan_film_favorit,
    simpan_pengguna,
)

WARNA_LATAR = "#07101E"
WARNA_SIDEBAR = "#0A1526"
WARNA_KARTU = "#0F1D33"
WARNA_KARTU_ALT = "#14243E"
WARNA_BORDER = "#1D3353"
WARNA_AKSEN = "#3B82F6"
WARNA_AKSEN_HOVER = "#2563EB"
WARNA_TEKS = "#EAF2FF"
WARNA_MUTED = "#8FA6C4"
WARNA_SUKSES = "#22C55E"
WARNA_GAGAL = "#EF4444"
WARNA_PERINGATAN = "#F59E0B"

FONT_UI = "Segoe UI"

NAVIGASI = [
    ("dashboard", "▦", "Dashboard"),
    ("katalog", "▧", "Katalog Film"),
    ("tambah_pengguna", "＋", "Tambah Pengguna"),
    ("tambah_film", "★", "Tambah Film"),
    ("rekomendasi", "✦", "Rekomendasi"),
    ("favorit", "▤", "Film Favorit"),
    ("hapus_favorit", "−", "Hapus Favorit"),
    ("statistik", "▥", "Statistik"),
]

INFO_HALAMAN = {
    "dashboard": (
        "Dashboard",
        "Ringkasan sistem, rekomendasi, dan film favorit pengguna.",
    ),
    "katalog": (
        "Katalog Film",
        "Seluruh film yang tersimpan di Neo4j beserta poster dan genre.",
    ),
    "tambah_pengguna": (
        "Tambah Pengguna",
        "Daftarkan pengguna baru dengan pengecekan duplikasi.",
    ),
    "tambah_film": (
        "Tambah Film Favorit",
        "Simpan film favorit beserta genre yang sesuai.",
    ),
    "rekomendasi": (
        "Rekomendasi Film",
        "Hasil Hybrid Recommendation dari Collaborative dan Content-Based Filtering.",
    ),
    "favorit": (
        "Film Favorit",
        "Daftar film favorit yang tersimpan untuk setiap pengguna.",
    ),
    "hapus_favorit": (
        "Hapus Film Favorit",
        "Hapus relasi favorit tanpa menghapus data film dari database.",
    ),
    "statistik": (
        "Statistik Sistem",
        "Jumlah pengguna, film, dan relasi LIKES di database Neo4j.",
    ),
}

FOLDER_POSTER = Path(__file__).resolve().parent / "assets" / "posters"
PRIORITAS_EKSTENSI = {
    ".png": 0,
    ".webp": 1,
    ".jpg": 2,
    ".jpeg": 3,
    ".bmp": 4,
    ".gif": 5,
}
UKURAN_POSTER = {
    "ringkas": (66, 99),
    "penuh": (108, 162),
    "favorit": (44, 66),
    "katalog": (156, 234),
}
RASIO_SUDUT_POSTER = 12


def normalisasi_judul_poster(judul):
    return "".join(
        karakter
        for karakter in str(judul).lower()
        if karakter.isalnum()
    )


def pindai_poster(folder=FOLDER_POSTER):
    index = {}

    try:
        berkas = [path for path in folder.iterdir() if path.is_file()]
    except OSError:
        return index

    for path in berkas:
        ekstensi = path.suffix.lower()

        if ekstensi not in PRIORITAS_EKSTENSI:
            continue

        kunci = normalisasi_judul_poster(path.stem)

        if not kunci:
            continue

        lama = index.get(kunci)

        if lama is None or (
            PRIORITAS_EKSTENSI[ekstensi]
            < PRIORITAS_EKSTENSI[lama.suffix.lower()]
        ):
            index[kunci] = path

    return index


def _potong_sudut(gambar, radius):
    if radius <= 0:
        return gambar

    lebar, tinggi = gambar.size
    mask = Image.new("L", (lebar, tinggi), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, lebar - 1, tinggi - 1),
        radius=radius,
        fill=255,
    )
    hasil = gambar.convert("RGBA")
    hasil.putalpha(mask)
    return hasil


@lru_cache(maxsize=160)
def _muat_gambar_poster(path_teks, waktu_modifikasi, ukuran):
    try:
        with Image.open(path_teks) as gambar:
            gambar = ImageOps.exif_transpose(gambar)
            gambar = gambar.convert("RGBA")
            gambar = ImageOps.fit(
                gambar,
                ukuran,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.35),
            )
            gambar = gambar.copy()
    except (OSError, UnidentifiedImageError, ValueError):
        return None

    radius = max(4, round(min(ukuran) * RASIO_SUDUT_POSTER / 100))
    return _potong_sudut(gambar, radius)


@lru_cache(maxsize=16)
def _buat_placeholder_poster(ukuran):
    lebar, tinggi = ukuran
    gambar = Image.new("RGBA", (lebar, tinggi), (10, 21, 38, 255))
    gambar_draw = ImageDraw.Draw(gambar)

    warna_atas = (24, 48, 82)
    warna_bawah = (8, 17, 32)

    for baris in range(tinggi):
        rasio = baris / max(1, tinggi - 1)
        warna = tuple(
            round(warna_atas[i] + (warna_bawah[i] - warna_atas[i]) * rasio)
            for i in range(3)
        )
        gambar_draw.line(
            [(0, baris), (lebar, baris)],
            fill=warna + (255,),
        )

    margin = max(3, lebar // 14)
    lebar_lubang = max(2, lebar // 14)
    tinggi_lubang = max(2, tinggi // 22)
    jarak_lubang = max(5, tinggi // 12)

    for posisi_x in (margin, lebar - margin - lebar_lubang):
        posisi_y = margin

        while posisi_y < tinggi - margin - tinggi_lubang:
            gambar_draw.rounded_rectangle(
                [
                    posisi_x,
                    posisi_y,
                    posisi_x + lebar_lubang,
                    posisi_y + tinggi_lubang,
                ],
                radius=max(1, lebar_lubang // 3),
                fill=(70, 110, 170, 210),
            )
            posisi_y += tinggi_lubang + jarak_lubang

    pusat_x = lebar // 2
    pusat_y = tinggi // 2
    jari = max(6, min(lebar, tinggi) // 7)

    gambar_draw.polygon(
        [
            (pusat_x - jari // 2, pusat_y - jari),
            (pusat_x - jari // 2, pusat_y + jari),
            (pusat_x + jari, pusat_y),
        ],
        fill=(59, 130, 246, 235),
    )

    if tinggi >= 90:
        try:
            font = ImageFont.truetype(
                "segoeui.ttf",
                max(7, lebar // 12),
            )
        except OSError:
            font = ImageFont.load_default()

        teks = "POSTER"
        kotak = gambar_draw.textbbox((0, 0), teks, font=font)
        lebar_teks = kotak[2] - kotak[0]
        tinggi_teks = kotak[3] - kotak[1]
        gambar_draw.text(
            (
                (lebar - lebar_teks) / 2,
                tinggi - tinggi_teks - margin * 2,
            ),
            teks,
            font=font,
            fill=(143, 166, 196, 235),
        )

    radius = max(4, round(min(ukuran) * RASIO_SUDUT_POSTER / 100))
    return _potong_sudut(gambar, radius)


class AplikasiRekomendasiFilm(ctk.CTk):
    def __init__(self, mode_uji=False):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.mode_uji = mode_uji
        self.driver = None
        self.session = None
        self.daftar_pengguna = []
        self.combo_pengguna_refs = []
        self.halaman = {}
        self.tombol_nav = {}
        self.halaman_aktif = None
        self.status_koneksi = "memeriksa"
        self._toast_after = None
        self.index_poster = {}
        self._poster_mtime = None
        self._cache_poster = {}
        self.daftar_film_katalog = []
        self.filter_katalog = ""
        self._katalog_kolom_terakhir = 0
        self._katalog_after = None

        self._muat_index_poster(paksa=True)

        self.title("CineGraph - Sistem Rekomendasi Film")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(fg_color=WARNA_LATAR)

        self._siapkan_font()
        self._buat_layout()
        self._buat_semua_halaman()
        self._buat_toast()

        self.protocol("WM_DELETE_WINDOW", self._tutup_aplikasi)
        self._hubungkan(tampilkan_dialog=not self.mode_uji)
        self._tampilkan_halaman("dashboard")

    def _siapkan_font(self):
        self.font_brand = ctk.CTkFont(FONT_UI, 22, "bold")
        self.font_brand_kecil = ctk.CTkFont(FONT_UI, 10, "bold")
        self.font_halaman = ctk.CTkFont(FONT_UI, 28, "bold")
        self.font_judul = ctk.CTkFont(FONT_UI, 20, "bold")
        self.font_subjudul = ctk.CTkFont(FONT_UI, 14, "bold")
        self.font_body = ctk.CTkFont(FONT_UI, 13)
        self.font_body_bold = ctk.CTkFont(FONT_UI, 13, "bold")
        self.font_kecil = ctk.CTkFont(FONT_UI, 11)
        self.font_nav = ctk.CTkFont(FONT_UI, 13, "bold")
        self.font_stat = ctk.CTkFont(FONT_UI, 34, "bold")
        self.font_ikon = ctk.CTkFont(FONT_UI, 16, "bold")

    def _buat_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._buat_sidebar()
        self._buat_area_konten()

    def _buat_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self,
            width=252,
            corner_radius=0,
            fg_color=WARNA_SIDEBAR,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(9, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 28))
        brand.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(
            brand,
            text="CG",
            width=42,
            height=42,
            corner_radius=12,
            fg_color=WARNA_AKSEN,
            text_color="#FFFFFF",
            font=self.font_body_bold,
        )
        logo.grid(row=0, column=0, rowspan=2, sticky="w")

        ctk.CTkLabel(
            brand,
            text="CINEGRAPH",
            font=self.font_brand,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=1, sticky="sw", padx=(12, 0))

        ctk.CTkLabel(
            brand,
            text="SISTEM REKOMENDASI FILM",
            font=self.font_brand_kecil,
            text_color=WARNA_MUTED,
            anchor="w",
        ).grid(row=1, column=1, sticky="nw", padx=(12, 0))

        for index, (kunci, ikon, label) in enumerate(NAVIGASI, start=1):
            tombol = ctk.CTkButton(
                self.sidebar,
                text=f"{ikon}   {label}",
                anchor="w",
                height=44,
                corner_radius=11,
                fg_color="transparent",
                hover_color=WARNA_KARTU_ALT,
                text_color=WARNA_MUTED,
                font=self.font_nav,
                command=lambda key=kunci: self._tampilkan_halaman(key),
            )
            tombol.grid(row=index, column=0, sticky="ew", padx=14, pady=3)
            self.tombol_nav[kunci] = tombol

        kartu_status = ctk.CTkFrame(
            self.sidebar,
            fg_color=WARNA_KARTU,
            corner_radius=14,
            border_width=1,
            border_color=WARNA_BORDER,
        )
        kartu_status.grid(row=10, column=0, sticky="ew", padx=16, pady=(12, 8))
        kartu_status.grid_columnconfigure(1, weight=1)

        self.indikator_koneksi = ctk.CTkLabel(
            kartu_status,
            text="●",
            font=self.font_ikon,
            text_color=WARNA_PERINGATAN,
            width=18,
        )
        self.indikator_koneksi.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(14, 4),
            pady=(14, 2),
        )

        self.label_koneksi = ctk.CTkLabel(
            kartu_status,
            text="Memeriksa koneksi",
            font=self.font_kecil,
            text_color=WARNA_MUTED,
            anchor="w",
        )
        self.label_koneksi.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 12),
            pady=(14, 2),
        )

        self.tombol_koneksi = ctk.CTkButton(
            kartu_status,
            text="Hubungkan Ulang",
            height=30,
            corner_radius=8,
            fg_color=WARNA_KARTU_ALT,
            hover_color="#1C3354",
            border_width=1,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            font=self.font_kecil,
            command=self._hubungkan_dari_ui,
        )
        self.tombol_koneksi.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=12,
            pady=(6, 12),
        )

        ctk.CTkLabel(
            self.sidebar,
            text="CLI tetap tersedia:\npython main.py",
            justify="left",
            font=self.font_kecil,
            text_color="#5E7698",
            anchor="w",
        ).grid(
            row=11,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 18),
        )

    def _buat_area_konten(self):
        self.area_konten = ctk.CTkFrame(self, fg_color="transparent")
        self.area_konten.grid(row=0, column=1, sticky="nsew")
        self.area_konten.grid_columnconfigure(0, weight=1)
        self.area_konten.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(self.area_konten, fg_color="transparent")
        topbar.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 0))
        topbar.grid_columnconfigure(0, weight=1)

        self.label_judul_halaman = ctk.CTkLabel(
            topbar,
            text="Dashboard",
            font=self.font_halaman,
            text_color=WARNA_TEKS,
            anchor="w",
        )
        self.label_judul_halaman.grid(row=0, column=0, sticky="w")

        self.label_deskripsi_halaman = ctk.CTkLabel(
            topbar,
            text="",
            font=self.font_body,
            text_color=WARNA_MUTED,
            anchor="w",
        )
        self.label_deskripsi_halaman.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(2, 0),
        )

        self.tombol_muat_ulang = ctk.CTkButton(
            topbar,
            text="↻   Muat Ulang",
            width=132,
            height=38,
            corner_radius=10,
            fg_color=WARNA_KARTU,
            hover_color=WARNA_KARTU_ALT,
            border_width=1,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            font=self.font_body_bold,
            command=self._muat_halaman_aktif,
        )
        self.tombol_muat_ulang.grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
            padx=(16, 0),
        )

        self.wadah_halaman = ctk.CTkFrame(
            self.area_konten,
            fg_color="transparent",
        )
        self.wadah_halaman.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=28,
            pady=(14, 22),
        )
        self.wadah_halaman.grid_columnconfigure(0, weight=1)
        self.wadah_halaman.grid_rowconfigure(0, weight=1)

    def _buat_halaman(self, kunci):
        halaman = ctk.CTkScrollableFrame(
            self.wadah_halaman,
            fg_color="transparent",
            scrollbar_fg_color="transparent",
            scrollbar_button_color=WARNA_AKSEN,
            scrollbar_button_hover_color=WARNA_AKSEN_HOVER,
        )
        halaman.grid(row=0, column=0, sticky="nsew")
        halaman.grid_remove()
        halaman.grid_columnconfigure(0, weight=1)
        self.halaman[kunci] = halaman
        return halaman

    def _buat_semua_halaman(self):
        self._buat_halaman_dashboard()
        self._buat_halaman_katalog()
        self._buat_halaman_tambah_pengguna()
        self._buat_halaman_tambah_film()
        self._buat_halaman_rekomendasi()
        self._buat_halaman_favorit()
        self._buat_halaman_hapus_favorit()
        self._buat_halaman_statistik()

    def _buat_toast(self):
        self.toast = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color=WARNA_KARTU_ALT,
            border_width=1,
            border_color=WARNA_BORDER,
        )
        self.toast_label = ctk.CTkLabel(
            self.toast,
            text="",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            wraplength=430,
            justify="left",
        )
        self.toast_label.pack(padx=18, pady=12)
        self.toast.place_forget()

    def _buat_kartu(self, induk, **kwargs):
        return ctk.CTkFrame(
            induk,
            fg_color=kwargs.get("fg_color", WARNA_KARTU),
            corner_radius=kwargs.get("corner_radius", 16),
            border_width=kwargs.get("border_width", 1),
            border_color=kwargs.get("border_color", WARNA_BORDER),
        )

    def _buat_judul_kartu(self, induk, teks, deskripsi=None):
        wadah = ctk.CTkFrame(induk, fg_color="transparent")

        judul = ctk.CTkLabel(
            wadah,
            text=teks,
            font=self.font_judul,
            text_color=WARNA_TEKS,
            anchor="w",
        )
        judul.pack(fill="x", anchor="w")

        if deskripsi:
            ctk.CTkLabel(
                wadah,
                text=deskripsi,
                font=self.font_body,
                text_color=WARNA_MUTED,
                anchor="w",
                justify="left",
            ).pack(fill="x", pady=(4, 0))

        return wadah

    def _buat_entry(self, induk, placeholder):
        return ctk.CTkEntry(
            induk,
            height=42,
            corner_radius=10,
            fg_color=WARNA_LATAR,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            placeholder_text=placeholder,
            placeholder_text_color=WARNA_MUTED,
            font=self.font_body,
        )

    def _buat_combo(self, induk, values=None, command=None, read_only=False):
        return ctk.CTkComboBox(
            induk,
            values=values or [],
            state="readonly" if read_only else "normal",
            height=42,
            corner_radius=10,
            fg_color=WARNA_LATAR,
            border_color=WARNA_BORDER,
            button_color=WARNA_AKSEN,
            button_hover_color=WARNA_AKSEN_HOVER,
            dropdown_fg_color=WARNA_KARTU_ALT,
            dropdown_hover_color=WARNA_AKSEN,
            dropdown_text_color=WARNA_TEKS,
            text_color=WARNA_TEKS,
            font=self.font_body,
            command=command,
        )

    def _buat_tombol_utama(self, induk, teks, command):
        return ctk.CTkButton(
            induk,
            text=teks,
            height=42,
            corner_radius=10,
            fg_color=WARNA_AKSEN,
            hover_color=WARNA_AKSEN_HOVER,
            text_color="#FFFFFF",
            font=self.font_body_bold,
            command=command,
        )

    def _buat_tombol_sekunder(self, induk, teks, command):
        return ctk.CTkButton(
            induk,
            text=teks,
            height=36,
            corner_radius=9,
            fg_color=WARNA_KARTU_ALT,
            hover_color="#1C3354",
            border_width=1,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            font=self.font_kecil,
            command=command,
        )

    def _buat_label_kosong(self, induk, teks, warna=None):
        return ctk.CTkLabel(
            induk,
            text=teks,
            font=self.font_body,
            text_color=warna or WARNA_MUTED,
            anchor="w",
            justify="left",
            wraplength=760,
        )

    def _bersihkan_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def _muat_index_poster(self, paksa=False):
        try:
            waktu_modifikasi = FOLDER_POSTER.stat().st_mtime
        except OSError:
            waktu_modifikasi = None

        if not paksa and waktu_modifikasi == self._poster_mtime:
            return

        self.index_poster = pindai_poster(FOLDER_POSTER)
        self._poster_mtime = waktu_modifikasi

    def _ambil_gambar_poster(self, judul, jenis="penuh"):
        ukuran = UKURAN_POSTER.get(jenis, UKURAN_POSTER["penuh"])
        path = self.index_poster.get(normalisasi_judul_poster(judul))
        gambar = None
        kunci = None

        if path is not None:
            try:
                waktu_modifikasi = path.stat().st_mtime
                gambar = _muat_gambar_poster(
                    str(path),
                    waktu_modifikasi,
                    ukuran,
                )
            except OSError:
                gambar = None

            if gambar is not None:
                kunci = ("poster", str(path), waktu_modifikasi, ukuran)

        if gambar is None:
            gambar = _buat_placeholder_poster(ukuran)
            kunci = ("placeholder", ukuran)

        gambar_ctk = self._cache_poster.get(kunci)

        if gambar_ctk is None:
            gambar_ctk = ctk.CTkImage(
                light_image=gambar,
                dark_image=gambar,
                size=ukuran,
            )
            self._cache_poster[kunci] = gambar_ctk

        return gambar_ctk

    def _buat_label_poster(self, induk, judul, jenis="penuh"):
        lebar, tinggi = UKURAN_POSTER.get(jenis, UKURAN_POSTER["penuh"])
        return ctk.CTkLabel(
            induk,
            text="",
            image=self._ambil_gambar_poster(judul, jenis),
            width=lebar,
            height=tinggi,
        )

    def _buat_kartu_statistik(self, induk, kolom, judul, variabel, ikon, aksen):
        kartu = self._buat_kartu(induk)
        kartu.grid(
            row=0,
            column=kolom,
            sticky="nsew",
            padx=(0 if kolom == 0 else 8, 0 if kolom == 2 else 8),
        )
        kartu.grid_columnconfigure(1, weight=1)

        ikon_label = ctk.CTkLabel(
            kartu,
            text=ikon,
            width=40,
            height=40,
            corner_radius=11,
            fg_color=WARNA_KARTU_ALT,
            text_color=aksen,
            font=self.font_ikon,
        )
        ikon_label.grid(
            row=0,
            column=0,
            rowspan=2,
            sticky="w",
            padx=(18, 12),
            pady=18,
        )

        ctk.CTkLabel(
            kartu,
            text=judul.upper(),
            font=self.font_brand_kecil,
            text_color=WARNA_MUTED,
            anchor="w",
        ).grid(row=0, column=1, sticky="sw", pady=(18, 0))

        ctk.CTkLabel(
            kartu,
            textvariable=variabel,
            font=self.font_stat,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=1, column=1, sticky="nw", pady=(0, 16))

        return kartu

    def _buat_halaman_dashboard(self):
        halaman = self._buat_halaman("dashboard")

        sambutan = self._buat_kartu(halaman)
        sambutan.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        sambutan.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sambutan,
            text="Selamat datang di CineGraph",
            font=self.font_judul,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=22,
            pady=(20, 2),
        )

        ctk.CTkLabel(
            sambutan,
            text=(
                "Pantau data, lihat rekomendasi hybrid, dan kelola film "
                "favorit langsung dari satu dashboard."
            ),
            font=self.font_body,
            text_color=WARNA_MUTED,
            anchor="w",
            justify="left",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=22,
            pady=(0, 20),
        )

        pilihan = ctk.CTkFrame(sambutan, fg_color="transparent")
        pilihan.grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
            padx=22,
            pady=18,
        )

        ctk.CTkLabel(
            pilihan,
            text="Pengguna aktif",
            font=self.font_kecil,
            text_color=WARNA_MUTED,
            anchor="w",
        ).pack(fill="x")

        self.combo_dashboard = self._buat_combo(
            pilihan,
            command=lambda _: self._muat_dashboard_pengguna(),
        )
        self.combo_dashboard.configure(width=230)
        self.combo_dashboard.pack(fill="x", pady=(5, 0))
        self.combo_pengguna_refs.append(self.combo_dashboard)

        statistik = ctk.CTkFrame(halaman, fg_color="transparent")
        statistik.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for kolom in range(3):
            statistik.grid_columnconfigure(kolom, weight=1, uniform="stat")

        self.var_dash_pengguna = tk.StringVar(value="0")
        self.var_dash_film = tk.StringVar(value="0")
        self.var_dash_relasi = tk.StringVar(value="0")

        self._buat_kartu_statistik(
            statistik,
            0,
            "Total Pengguna",
            self.var_dash_pengguna,
            "◉",
            WARNA_AKSEN,
        )
        self._buat_kartu_statistik(
            statistik,
            1,
            "Total Film",
            self.var_dash_film,
            "▤",
            "#38BDF8",
        )
        self._buat_kartu_statistik(
            statistik,
            2,
            "Relasi Favorit",
            self.var_dash_relasi,
            "★",
            WARNA_SUKSES,
        )

        status = self._buat_kartu(halaman)
        status.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        status.grid_columnconfigure(1, weight=1)

        self.indikator_dashboard = ctk.CTkLabel(
            status,
            text="●",
            font=self.font_ikon,
            text_color=WARNA_PERINGATAN,
            width=20,
        )
        self.indikator_dashboard.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(18, 6),
            pady=16,
        )

        self.label_status_dashboard = ctk.CTkLabel(
            status,
            text="Memeriksa koneksi Neo4j...",
            font=self.font_body_bold,
            text_color=WARNA_MUTED,
            anchor="w",
        )
        self.label_status_dashboard.grid(
            row=0,
            column=1,
            sticky="ew",
            pady=16,
        )

        ctk.CTkButton(
            status,
            text="Periksa Koneksi",
            width=140,
            height=32,
            corner_radius=8,
            fg_color=WARNA_KARTU_ALT,
            hover_color="#1C3354",
            border_width=1,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            font=self.font_kecil,
            command=self._hubungkan_dari_ui,
        ).grid(row=0, column=2, sticky="e", padx=16, pady=12)

        kolom = ctk.CTkFrame(halaman, fg_color="transparent")
        kolom.grid(row=3, column=0, sticky="nsew")
        kolom.grid_columnconfigure(0, weight=1, uniform="dash")
        kolom.grid_columnconfigure(1, weight=1, uniform="dash")

        kartu_rekomendasi = self._buat_kartu(kolom)
        kartu_rekomendasi.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 8),
        )
        self._buat_judul_kartu(
            kartu_rekomendasi,
            "Rekomendasi Film",
            "Tiga rekomendasi teratas untuk pengguna aktif.",
        ).pack(fill="x", padx=18, pady=(18, 0))
        self.frame_dash_rekomendasi = ctk.CTkFrame(
            kartu_rekomendasi,
            fg_color="transparent",
        )
        self.frame_dash_rekomendasi.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(14, 18),
        )

        kartu_favorit = self._buat_kartu(kolom)
        kartu_favorit.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 0),
        )
        self._buat_judul_kartu(
            kartu_favorit,
            "Film Favorit Pengguna",
            "Film favorit yang tersimpan untuk pengguna aktif.",
        ).pack(fill="x", padx=18, pady=(18, 0))
        self.frame_dash_favorit = ctk.CTkFrame(
            kartu_favorit,
            fg_color="transparent",
        )
        self.frame_dash_favorit.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(14, 18),
        )

    def _buat_halaman_katalog(self):
        halaman = self._buat_halaman("katalog")

        kontrol = self._buat_kartu(halaman)
        kontrol.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        kontrol.grid_columnconfigure(0, weight=1)

        self.entry_cari_katalog = self._buat_entry(
            kontrol,
            "Cari judul film...",
        )
        self.entry_cari_katalog.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(20, 10),
            pady=18,
        )
        self.entry_cari_katalog.bind(
            "<KeyRelease>",
            lambda _: self._terapkan_filter_katalog(),
        )

        self._buat_tombol_sekunder(
            kontrol,
            "Muat Ulang",
            self._muat_katalog,
        ).grid(row=0, column=1, sticky="e", padx=(0, 20), pady=18)

        self.label_info_katalog = ctk.CTkLabel(
            halaman,
            text="",
            font=self.font_body_bold,
            text_color=WARNA_MUTED,
            anchor="w",
        )
        self.label_info_katalog.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0, 10),
        )

        self.frame_grid_katalog = ctk.CTkFrame(
            halaman,
            fg_color="transparent",
        )
        self.frame_grid_katalog.grid(row=2, column=0, sticky="nsew")
        self.frame_grid_katalog.grid_columnconfigure(0, weight=1)
        self.frame_grid_katalog.bind(
            "<Configure>",
            self._jadwalkan_render_katalog,
        )

    def _jadwalkan_render_katalog(self, _event=None):
        if self._katalog_after is not None:
            try:
                self.after_cancel(self._katalog_after)
            except Exception:
                pass

        self._katalog_after = self.after(120, self._render_katalog)

    def _muat_katalog(self):
        self._bersihkan_frame(self.frame_grid_katalog)
        self.label_info_katalog.configure(
            text="Memuat data film...",
            text_color=WARNA_MUTED,
        )

        try:
            films = self._panggil(ambil_daftar_film)
        except Exception as error:
            self.daftar_film_katalog = []
            self._tampilkan_error(error)
            self.label_info_katalog.configure(
                text=self._pesan_error(error),
                text_color=WARNA_GAGAL,
            )
            self._buat_label_kosong(
                self.frame_grid_katalog,
                self._pesan_error(error),
                WARNA_GAGAL,
            ).grid(row=0, column=0, sticky="w", pady=8)
            return

        self.daftar_film_katalog = films
        self._render_katalog(paksa=True)

    def _terapkan_filter_katalog(self):
        self.filter_katalog = self.entry_cari_katalog.get().strip().lower()
        self._render_katalog(paksa=True)

    def _render_katalog(self, paksa=False):
        if self._katalog_after is not None:
            try:
                self.after_cancel(self._katalog_after)
            except Exception:
                pass
            self._katalog_after = None

        if not hasattr(self, "frame_grid_katalog"):
            return

        lebar = self.frame_grid_katalog.winfo_width()

        if lebar <= 1:
            lebar = 900

        kolom = max(1, min(6, (lebar + 14) // 198))

        if not paksa and kolom == self._katalog_kolom_terakhir:
            return

        self._katalog_kolom_terakhir = kolom
        self._bersihkan_frame(self.frame_grid_katalog)

        for index in range(kolom):
            self.frame_grid_katalog.grid_columnconfigure(
                index,
                weight=1,
                uniform="katalog",
            )

        if not self.daftar_film_katalog:
            self.label_info_katalog.configure(
                text=(
                    "Katalog masih kosong. Data film akan muncul otomatis "
                    "setelah film ditambahkan ke Neo4j."
                ),
                text_color=WARNA_MUTED,
            )
            self._buat_label_kosong(
                self.frame_grid_katalog,
                "Belum ada film yang tersimpan di database. Tambahkan film "
                "favorit melalui menu Tambah Film untuk melihatnya di sini.",
            ).grid(
                row=0,
                column=0,
                columnspan=kolom,
                sticky="w",
                pady=8,
            )
            return

        kueri = self.filter_katalog
        film_tampil = [
            film
            for film in self.daftar_film_katalog
            if kueri in str(film["judul"]).lower()
        ]

        if not film_tampil:
            self.label_info_katalog.configure(
                text=(
                    f'Tidak ada film yang cocok dengan "{self.filter_katalog}".'
                ),
                text_color=WARNA_MUTED,
            )
            self._buat_label_kosong(
                self.frame_grid_katalog,
                "Coba kata kunci lain atau kosongkan kolom pencarian.",
            ).grid(
                row=0,
                column=0,
                columnspan=kolom,
                sticky="w",
                pady=8,
            )
            return

        self.label_info_katalog.configure(
            text=(
                f"Menampilkan {len(film_tampil)} dari "
                f"{len(self.daftar_film_katalog)} film"
            ),
            text_color=WARNA_MUTED,
        )

        for index, film in enumerate(film_tampil):
            baris, kolom_kartu = divmod(index, kolom)
            kartu = self._buat_kartu_katalog(
                self.frame_grid_katalog,
                film,
            )
            kartu.grid(
                row=baris,
                column=kolom_kartu,
                sticky="nsew",
                padx=(
                    0 if kolom_kartu == 0 else 7,
                    0 if kolom_kartu == kolom - 1 else 7,
                ),
                pady=(0, 14),
            )

    def _buat_kartu_katalog(self, induk, film):
        kartu = ctk.CTkFrame(
            induk,
            fg_color=WARNA_KARTU,
            corner_radius=14,
            border_width=1,
            border_color=WARNA_BORDER,
        )
        kartu.grid_columnconfigure(0, weight=1)

        self._buat_label_poster(
            kartu,
            film["judul"],
            "katalog",
        ).grid(
            row=0,
            column=0,
            padx=12,
            pady=(14, 10),
        )

        ctk.CTkLabel(
            kartu,
            text=film["judul"],
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
            justify="left",
            wraplength=156,
        ).grid(row=1, column=0, sticky="ew", padx=14)

        genres = gabungkan_genre(film["genres"])
        ctk.CTkLabel(
            kartu,
            text=", ".join(genres) or "Genre tidak diketahui",
            font=self.font_kecil,
            text_color="#7DD3FC",
            anchor="w",
            justify="left",
            wraplength=156,
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 14))

        return kartu

    def _buat_halaman_tambah_pengguna(self):
        halaman = self._buat_halaman("tambah_pengguna")

        kartu = self._buat_kartu(halaman)
        kartu.grid(row=0, column=0, sticky="ew")
        kartu.grid_columnconfigure(0, weight=1)

        isi = ctk.CTkFrame(kartu, fg_color="transparent")
        isi.grid(row=0, column=0, sticky="ew", padx=24, pady=24)
        isi.grid_columnconfigure(0, weight=1)

        self._buat_judul_kartu(
            isi,
            "Daftarkan Pengguna Baru",
            "Nama pengguna akan dinormalisasi dan dicek agar tidak duplikat.",
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            isi,
            text="Nama pengguna",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(22, 6))

        self.entry_nama_pengguna = self._buat_entry(
            isi,
            "Contoh: Budi Santoso",
        )
        self.entry_nama_pengguna.grid(row=2, column=0, sticky="ew")
        self.entry_nama_pengguna.bind(
            "<Return>",
            lambda _: self._aksi_tambah_pengguna(),
        )

        self.tombol_tambah_pengguna = self._buat_tombol_utama(
            isi,
            "Tambah Pengguna",
            self._aksi_tambah_pengguna,
        )
        self.tombol_tambah_pengguna.grid(
            row=3,
            column=0,
            sticky="w",
            pady=(18, 0),
        )

        self.label_hasil_tambah_pengguna = ctk.CTkLabel(
            isi,
            text="",
            font=self.font_body,
            text_color=WARNA_MUTED,
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.label_hasil_tambah_pengguna.grid(
            row=4,
            column=0,
            sticky="w",
            pady=(14, 0),
        )

    def _buat_halaman_tambah_film(self):
        halaman = self._buat_halaman("tambah_film")

        kartu = self._buat_kartu(halaman)
        kartu.grid(row=0, column=0, sticky="ew")
        kartu.grid_columnconfigure(0, weight=1)

        isi = ctk.CTkFrame(kartu, fg_color="transparent")
        isi.grid(row=0, column=0, sticky="ew", padx=24, pady=24)
        isi.grid_columnconfigure(0, weight=1)

        self._buat_judul_kartu(
            isi,
            "Tambah Film Favorit",
            "Pilih pengguna, masukkan judul, lalu tentukan satu atau lebih genre.",
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            isi,
            text="Nama pengguna",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(22, 6))

        self.combo_film_pengguna = self._buat_combo(isi)
        self.combo_film_pengguna.grid(row=2, column=0, sticky="ew")
        self.combo_pengguna_refs.append(self.combo_film_pengguna)

        ctk.CTkLabel(
            isi,
            text="Judul film",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=3, column=0, sticky="w", pady=(16, 6))

        self.entry_judul_film = self._buat_entry(
            isi,
            "Contoh: Interstellar",
        )
        self.entry_judul_film.grid(row=4, column=0, sticky="ew")
        self.entry_judul_film.bind(
            "<Return>",
            lambda _: self._aksi_tambah_film(),
        )

        header_genre = ctk.CTkFrame(isi, fg_color="transparent")
        header_genre.grid(row=5, column=0, sticky="ew", pady=(20, 8))
        header_genre.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_genre,
            text="Genre film",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header_genre,
            text="Pilih Semua",
            width=92,
            height=28,
            corner_radius=8,
            fg_color=WARNA_KARTU_ALT,
            hover_color="#1C3354",
            border_width=1,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            font=self.font_kecil,
            command=self._pilih_semua_genre,
        ).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkButton(
            header_genre,
            text="Bersihkan",
            width=84,
            height=28,
            corner_radius=8,
            fg_color=WARNA_KARTU_ALT,
            hover_color="#1C3354",
            border_width=1,
            border_color=WARNA_BORDER,
            text_color=WARNA_TEKS,
            font=self.font_kecil,
            command=self._bersihkan_pilihan_genre,
        ).grid(row=0, column=2, padx=(8, 0))

        genre_frame = ctk.CTkFrame(
            isi,
            fg_color=WARNA_LATAR,
            corner_radius=12,
            border_width=1,
            border_color=WARNA_BORDER,
        )
        genre_frame.grid(row=6, column=0, sticky="ew")
        for kolom in range(3):
            genre_frame.grid_columnconfigure(kolom, weight=1)

        self.genre_vars = {}

        for index, genre in enumerate(GENRE_LIST):
            variabel = tk.IntVar(value=0)
            self.genre_vars[genre] = variabel
            ctk.CTkCheckBox(
                genre_frame,
                text=genre,
                variable=variabel,
                font=self.font_body,
                text_color=WARNA_TEKS,
                fg_color=WARNA_AKSEN,
                hover_color=WARNA_AKSEN_HOVER,
                border_color=WARNA_BORDER,
                checkmark_color="#FFFFFF",
                checkbox_width=20,
                checkbox_height=20,
            ).grid(
                row=index // 3,
                column=index % 3,
                sticky="w",
                padx=16,
                pady=8,
            )

        self.tombol_simpan_film = self._buat_tombol_utama(
            isi,
            "Simpan Film Favorit",
            self._aksi_tambah_film,
        )
        self.tombol_simpan_film.grid(
            row=7,
            column=0,
            sticky="w",
            pady=(20, 0),
        )

        self.label_hasil_tambah_film = ctk.CTkLabel(
            isi,
            text="",
            font=self.font_body,
            text_color=WARNA_MUTED,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.label_hasil_tambah_film.grid(
            row=8,
            column=0,
            sticky="w",
            pady=(14, 0),
        )

    def _buat_halaman_rekomendasi(self):
        halaman = self._buat_halaman("rekomendasi")

        kontrol = self._buat_kartu(halaman)
        kontrol.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        kontrol.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            kontrol,
            text="Pengguna",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(20, 12), pady=(18, 6))

        self.combo_rekomendasi = self._buat_combo(
            kontrol,
            command=lambda _: self._muat_rekomendasi_halaman(),
        )
        self.combo_rekomendasi.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=20,
            pady=(0, 6),
        )
        self.combo_pengguna_refs.append(self.combo_rekomendasi)

        ctk.CTkButton(
            kontrol,
            text="Tampilkan Rekomendasi",
            height=40,
            corner_radius=10,
            fg_color=WARNA_AKSEN,
            hover_color=WARNA_AKSEN_HOVER,
            text_color="#FFFFFF",
            font=self.font_body_bold,
            command=self._muat_rekomendasi_halaman,
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
            pady=(8, 18),
        )

        self.frame_hasil_rekomendasi = ctk.CTkFrame(
            halaman,
            fg_color="transparent",
        )
        self.frame_hasil_rekomendasi.grid(row=1, column=0, sticky="nsew")
        self.frame_hasil_rekomendasi.grid_columnconfigure(0, weight=1)

    def _buat_halaman_favorit(self):
        halaman = self._buat_halaman("favorit")

        kontrol = self._buat_kartu(halaman)
        kontrol.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        kontrol.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            kontrol,
            text="Pilih pengguna",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 6))

        self.combo_favorit = self._buat_combo(
            kontrol,
            command=lambda _: self._muat_favorit_halaman(),
        )
        self.combo_favorit.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 6),
        )
        self.combo_pengguna_refs.append(self.combo_favorit)

        self.tombol_tampilkan_favorit = self._buat_tombol_utama(
            kontrol,
            "Tampilkan Film Favorit",
            self._muat_favorit_halaman,
        )
        self.tombol_tampilkan_favorit.grid(
            row=2,
            column=0,
            sticky="w",
            padx=20,
            pady=(8, 18),
        )

        self.frame_hasil_favorit = ctk.CTkFrame(
            halaman,
            fg_color="transparent",
        )
        self.frame_hasil_favorit.grid(row=1, column=0, sticky="nsew")
        self.frame_hasil_favorit.grid_columnconfigure(0, weight=1)

    def _buat_halaman_hapus_favorit(self):
        halaman = self._buat_halaman("hapus_favorit")

        kartu = self._buat_kartu(halaman)
        kartu.grid(row=0, column=0, sticky="ew")
        kartu.grid_columnconfigure(0, weight=1)

        isi = ctk.CTkFrame(kartu, fg_color="transparent")
        isi.grid(row=0, column=0, sticky="ew", padx=24, pady=24)
        isi.grid_columnconfigure(0, weight=1)

        self._buat_judul_kartu(
            isi,
            "Hapus Film dari Favorit",
            "Hanya relasi LIKES yang dihapus. Node film tetap tersimpan.",
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            isi,
            text="Nama pengguna",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(22, 6))

        self.combo_hapus_pengguna = self._buat_combo(
            isi,
            command=lambda _: self._muat_film_untuk_dihapus(),
            read_only=True,
        )
        self.combo_hapus_pengguna.grid(row=2, column=0, sticky="ew")
        self.combo_pengguna_refs.append(self.combo_hapus_pengguna)

        ctk.CTkLabel(
            isi,
            text="Film favorit",
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=3, column=0, sticky="w", pady=(16, 6))

        self.combo_film_hapus = self._buat_combo(
            isi,
            read_only=True,
        )
        self.combo_film_hapus.grid(row=4, column=0, sticky="ew")

        baris_tombol = ctk.CTkFrame(isi, fg_color="transparent")
        baris_tombol.grid(row=5, column=0, sticky="w", pady=(18, 0))

        self.tombol_hapus_favorit = ctk.CTkButton(
            baris_tombol,
            text="Hapus Film Favorit",
            height=42,
            corner_radius=10,
            fg_color=WARNA_GAGAL,
            hover_color="#DC2626",
            text_color="#FFFFFF",
            font=self.font_body_bold,
            command=self._aksi_hapus_favorit,
        )
        self.tombol_hapus_favorit.pack(side="left")

        self._buat_tombol_sekunder(
            baris_tombol,
            "Muat Daftar Film",
            self._muat_film_untuk_dihapus,
        ).pack(side="left", padx=(10, 0))

        self.label_status_hapus = ctk.CTkLabel(
            isi,
            text="",
            font=self.font_body,
            text_color=WARNA_MUTED,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.label_status_hapus.grid(
            row=6,
            column=0,
            sticky="w",
            pady=(14, 0),
        )

    def _buat_halaman_statistik(self):
        halaman = self._buat_halaman("statistik")

        atas = ctk.CTkFrame(halaman, fg_color="transparent")
        atas.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        atas.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            atas,
            text="Ringkasan data Neo4j",
            font=self.font_judul,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._buat_tombol_sekunder(
            atas,
            "Muat Ulang Statistik",
            self._muat_statistik,
        ).grid(row=0, column=1, sticky="e")

        statistik = ctk.CTkFrame(halaman, fg_color="transparent")
        statistik.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for kolom in range(3):
            statistik.grid_columnconfigure(kolom, weight=1, uniform="stat")

        self.var_stat_pengguna = tk.StringVar(value="0")
        self.var_stat_film = tk.StringVar(value="0")
        self.var_stat_relasi = tk.StringVar(value="0")

        self._buat_kartu_statistik(
            statistik,
            0,
            "Total Pengguna",
            self.var_stat_pengguna,
            "◉",
            WARNA_AKSEN,
        )
        self._buat_kartu_statistik(
            statistik,
            1,
            "Total Film",
            self.var_stat_film,
            "▤",
            "#38BDF8",
        )
        self._buat_kartu_statistik(
            statistik,
            2,
            "Relasi LIKES",
            self.var_stat_relasi,
            "★",
            WARNA_SUKSES,
        )

        catatan = self._buat_kartu(halaman)
        catatan.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(
            catatan,
            text="Statistik dihitung langsung dari database Neo4j.",
            font=self.font_body,
            text_color=WARNA_MUTED,
            anchor="w",
        ).pack(fill="x", padx=20, pady=18)

    def _tampilkan_halaman(self, kunci):
        if kunci not in self.halaman:
            return

        self._muat_index_poster()

        for halaman in self.halaman.values():
            halaman.grid_remove()

        self.halaman[kunci].grid(row=0, column=0, sticky="nsew")
        self.halaman_aktif = kunci

        judul, deskripsi = INFO_HALAMAN[kunci]
        self.label_judul_halaman.configure(text=judul)
        self.label_deskripsi_halaman.configure(text=deskripsi)

        for nama, tombol in self.tombol_nav.items():
            if nama == kunci:
                tombol.configure(
                    fg_color=WARNA_AKSEN,
                    hover_color=WARNA_AKSEN_HOVER,
                    text_color="#FFFFFF",
                )
            else:
                tombol.configure(
                    fg_color="transparent",
                    hover_color=WARNA_KARTU_ALT,
                    text_color=WARNA_MUTED,
                )

        pemuat = {
            "dashboard": self._muat_dashboard,
            "katalog": self._muat_katalog,
            "tambah_pengguna": self._muat_pilihan_pengguna,
            "tambah_film": self._muat_pilihan_pengguna,
            "rekomendasi": self._muat_halaman_rekomendasi,
            "favorit": self._muat_halaman_favorit,
            "hapus_favorit": self._muat_halaman_hapus,
            "statistik": self._muat_statistik,
        }.get(kunci)

        if pemuat:
            pemuat()

    def _muat_halaman_aktif(self):
        if self.halaman_aktif:
            self._tampilkan_halaman(self.halaman_aktif)

    def _hubungkan(self, tampilkan_dialog=False):
        self._tutup_koneksi()
        self._perbarui_status_koneksi("memeriksa")

        try:
            driver = create_driver()
            driver.verify_connectivity()
            self.driver = driver
            self.session = driver.session(database=DATABASE)
            self._perbarui_status_koneksi("terhubung")
            return True
        except Exception as error:
            self._tutup_koneksi()
            self._perbarui_status_koneksi("gagal")
            pesan = self._pesan_error(error)
            if tampilkan_dialog:
                messagebox.showerror("Koneksi Neo4j", pesan, parent=self)
            else:
                self.tampilkan_notifikasi(pesan, "error")
            return False

    def _hubungkan_dari_ui(self):
        if self._hubungkan(tampilkan_dialog=True):
            self.tampilkan_notifikasi("Koneksi Neo4j berhasil.", "sukses")
            self._muat_daftar_pengguna(tampilkan_error=False)
            self._muat_halaman_aktif()

    def _tutup_koneksi(self):
        if self.session is not None:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None

        if self.driver is not None:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None

    def _tutup_aplikasi(self):
        self._tutup_koneksi()
        self.destroy()

    def _perbarui_status_koneksi(self, status):
        self.status_koneksi = status

        if status == "terhubung":
            warna = WARNA_SUKSES
            teks = "Terhubung ke Neo4j"
            teks_dashboard = "Neo4j terhubung. Data siap digunakan."
        elif status == "gagal":
            warna = WARNA_GAGAL
            teks = "Koneksi gagal"
            teks_dashboard = (
                "Neo4j tidak terhubung. Periksa server dan konfigurasi, "
                "lalu klik Hubungkan Ulang."
            )
        else:
            warna = WARNA_PERINGATAN
            teks = "Memeriksa koneksi"
            teks_dashboard = "Memeriksa koneksi Neo4j..."

        self.indikator_koneksi.configure(text_color=warna)
        self.label_koneksi.configure(text=teks)

        if hasattr(self, "indikator_dashboard"):
            self.indikator_dashboard.configure(text_color=warna)
            self.label_status_dashboard.configure(
                text=teks_dashboard,
                text_color=warna if status != "memeriksa" else WARNA_MUTED,
            )

    def _pastikan_session(self):
        if self.session is not None:
            return self.session

        raise KesalahanAplikasi(
            "Koneksi Neo4j belum tersedia. Klik tombol Hubungkan Ulang "
            "pada sidebar."
        )

    def _panggil(self, fungsi, *args):
        return fungsi(self._pastikan_session(), *args)

    def _pesan_error(self, error):
        if isinstance(error, KesalahanAplikasi):
            return str(error)
        if isinstance(error, ServiceUnavailable):
            return (
                "Tidak dapat terhubung ke Neo4j. Pastikan server Neo4j "
                "berjalan dan konfigurasi .env sudah benar."
            )
        if isinstance(error, AuthError):
            return (
                "Autentikasi Neo4j gagal. Periksa NEO4J_USERNAME dan "
                "NEO4J_PASSWORD pada file .env."
            )
        if isinstance(error, ValueError):
            return "Konfigurasi Neo4j belum lengkap. Periksa file .env."
        if isinstance(error, Neo4jError):
            return (
                "Terjadi kesalahan pada database Neo4j. "
                "Operasi dibatalkan. Silakan coba lagi."
            )
        return (
            "Terjadi kesalahan tak terduga. "
            "Operasi dibatalkan. Silakan coba lagi."
        )

    def _tampilkan_error(self, error):
        if isinstance(error, (ServiceUnavailable, AuthError)):
            self._tutup_koneksi()
            self._perbarui_status_koneksi("gagal")
        self.tampilkan_notifikasi(self._pesan_error(error), "error")

    def tampilkan_notifikasi(self, pesan, jenis="info"):
        warna = {
            "info": (WARNA_KARTU_ALT, WARNA_BORDER, WARNA_TEKS),
            "sukses": ("#0D2A1B", "#1E7A46", "#B8F5CF"),
            "error": ("#2B1218", "#8F2C3A", "#FFC2CC"),
            "peringatan": ("#2B2110", "#8A651E", "#FFE0A3"),
        }.get(jenis, (WARNA_KARTU_ALT, WARNA_BORDER, WARNA_TEKS))

        self.toast.configure(fg_color=warna[0], border_color=warna[1])
        self.toast_label.configure(text=pesan, text_color=warna[2])
        self.toast.place(relx=0.985, rely=0.975, anchor="se")
        self.toast.lift()

        if self._toast_after is not None:
            try:
                self.after_cancel(self._toast_after)
            except Exception:
                pass

        self._toast_after = self.after(
            4200,
            lambda: self.toast.place_forget(),
        )

    def _muat_daftar_pengguna(self, tampilkan_error=True):
        try:
            self.daftar_pengguna = self._panggil(ambil_daftar_pengguna)
        except Exception as error:
            self.daftar_pengguna = []
            if tampilkan_error:
                self._tampilkan_error(error)

        self._perbarui_combo_pengguna()
        return self.daftar_pengguna

    def _perbarui_combo_pengguna(self):
        values = self.daftar_pengguna

        for combo in self.combo_pengguna_refs:
            try:
                current = combo.get().strip()
                combo.configure(values=values)
                if values:
                    if current not in values:
                        combo.set(values[0])
                else:
                    combo.set("")
            except Exception:
                pass

    def _muat_pilihan_pengguna(self):
        self._muat_daftar_pengguna(tampilkan_error=False)

    def _muat_dashboard(self):
        self._muat_daftar_pengguna(tampilkan_error=False)

        try:
            statistik = self._panggil(ambil_statistik)
            self.var_dash_pengguna.set(str(statistik["total_pengguna"]))
            self.var_dash_film.set(str(statistik["total_film"]))
            self.var_dash_relasi.set(str(statistik["total_relasi"]))
            if self.session is not None:
                self._perbarui_status_koneksi("terhubung")
        except Exception as error:
            self.var_dash_pengguna.set("-")
            self.var_dash_film.set("-")
            self.var_dash_relasi.set("-")
            self._tampilkan_error(error)

        self._muat_dashboard_pengguna()

    def _muat_dashboard_pengguna(self):
        self._bersihkan_frame(self.frame_dash_rekomendasi)
        self._bersihkan_frame(self.frame_dash_favorit)

        nama = self.combo_dashboard.get().strip()

        if not nama:
            self._buat_label_kosong(
                self.frame_dash_rekomendasi,
                "Belum ada pengguna. Tambahkan pengguna terlebih dahulu.",
            ).pack(fill="x")
            self._buat_label_kosong(
                self.frame_dash_favorit,
                "Belum ada pengguna. Tambahkan pengguna terlebih dahulu.",
            ).pack(fill="x")
            return

        try:
            hasil = self._panggil(ambil_rekomendasi, nama)
            rekomendasi = hasil["rekomendasi"][:3]

            if not rekomendasi:
                self._buat_label_kosong(
                    self.frame_dash_rekomendasi,
                    "Tidak ada rekomendasi yang dapat diberikan saat ini.",
                ).pack(fill="x")
            else:
                for item in rekomendasi:
                    self._buat_kartu_rekomendasi(
                        self.frame_dash_rekomendasi,
                        item,
                        ringkas=True,
                    )
        except PenggunaTanpaFavorit:
            self._buat_label_kosong(
                self.frame_dash_rekomendasi,
                f"{nama} belum memiliki film favorit.",
            ).pack(fill="x")
        except PenggunaTidakDitemukan:
            self._buat_label_kosong(
                self.frame_dash_rekomendasi,
                f"Pengguna '{nama}' tidak ditemukan.",
            ).pack(fill="x")
        except Exception as error:
            self._tampilkan_error(error)
            self._buat_label_kosong(
                self.frame_dash_rekomendasi,
                self._pesan_error(error),
                WARNA_GAGAL,
            ).pack(fill="x")

        try:
            hasil = self._panggil(ambil_film_favorit, nama)
            films = hasil["films"]

            if not films:
                self._buat_label_kosong(
                    self.frame_dash_favorit,
                    f"{nama} belum memiliki film favorit.",
                ).pack(fill="x")
            else:
                for film in films[:5]:
                    self._buat_baris_favorit(
                        self.frame_dash_favorit,
                        film["judul"],
                        film["genres"],
                    )
                if len(films) > 5:
                    self._buat_label_kosong(
                        self.frame_dash_favorit,
                        f"+{len(films) - 5} film lainnya.",
                    ).pack(fill="x", pady=(8, 0))
        except Exception as error:
            self._tampilkan_error(error)
            self._buat_label_kosong(
                self.frame_dash_favorit,
                self._pesan_error(error),
                WARNA_GAGAL,
            ).pack(fill="x")

    def _buat_baris_favorit(self, induk, judul, genres):
        baris = ctk.CTkFrame(
            induk,
            fg_color=WARNA_KARTU_ALT,
            corner_radius=10,
        )
        baris.pack(fill="x", pady=(0, 8))
        baris.grid_columnconfigure(1, weight=1)

        self._buat_label_poster(baris, judul, "favorit").grid(
            row=0,
            column=0,
            rowspan=2,
            sticky="ns",
            padx=(10, 12),
            pady=8,
        )

        ctk.CTkLabel(
            baris,
            text=judul,
            font=self.font_body_bold,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(10, 2))

        daftar_genre = gabungkan_genre(genres)
        ctk.CTkLabel(
            baris,
            text="Genre: " + (", ".join(daftar_genre) or "Tidak diketahui"),
            font=self.font_kecil,
            text_color=WARNA_MUTED,
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=(0, 10))

    def _buat_kartu_rekomendasi(self, induk, item, ringkas=False):
        kartu = ctk.CTkFrame(
            induk,
            fg_color=WARNA_KARTU_ALT,
            corner_radius=12,
            border_width=1,
            border_color=WARNA_BORDER,
        )
        kartu.pack(fill="x", pady=(0, 10))
        kartu.grid_columnconfigure(1, weight=1)

        self._buat_label_poster(
            kartu,
            item["rekomendasi"],
            "ringkas" if ringkas else "penuh",
        ).grid(
            row=0,
            column=0,
            rowspan=3,
            sticky="n",
            padx=(16, 14),
            pady=16,
        )

        isi = ctk.CTkFrame(kartu, fg_color="transparent")
        isi.grid(
            row=0,
            column=1,
            rowspan=3,
            sticky="nsew",
            padx=(0, 16),
            pady=14,
        )
        isi.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(isi, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=item["rekomendasi"],
            font=self.font_subjudul,
            text_color=WARNA_TEKS,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        genres = gabungkan_genre(item["genres"])
        ctk.CTkLabel(
            header,
            text=", ".join(genres) or "Genre tidak diketahui",
            font=self.font_kecil,
            text_color="#7DD3FC",
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        skor = ctk.CTkFrame(isi, fg_color="transparent")
        skor.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        for kolom in range(3):
            skor.grid_columnconfigure(kolom, weight=1)

        data_skor = [
            ("Skor Pengguna", str(item["skor_pengguna"]), WARNA_TEKS),
            ("Skor Genre", str(item["skor_genre"]), WARNA_TEKS),
            ("Skor Akhir", str(item["skor_akhir"]), "#7DD3FC"),
        ]

        for kolom, (label, nilai, warna) in enumerate(data_skor):
            mini = ctk.CTkFrame(
                skor,
                fg_color=WARNA_LATAR,
                corner_radius=8,
            )
            mini.grid(
                row=0,
                column=kolom,
                sticky="ew",
                padx=(0 if kolom == 0 else 4, 0 if kolom == 2 else 4),
            )
            ctk.CTkLabel(
                mini,
                text=label.upper(),
                font=self.font_brand_kecil,
                text_color=WARNA_MUTED,
                anchor="w",
            ).pack(fill="x", padx=12, pady=(8, 0))
            ctk.CTkLabel(
                mini,
                text=nilai,
                font=self.font_subjudul,
                text_color=warna,
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 8))

        if not ringkas:
            alasan = buat_alasan(
                item["skor_pengguna"],
                item["skor_genre"],
                gabungkan_genre(item["genre_cocok"]),
            )
            ctk.CTkLabel(
                isi,
                text="Alasan: " + alasan,
                font=self.font_kecil,
                text_color=WARNA_MUTED,
                anchor="w",
                justify="left",
                wraplength=720,
            ).grid(
                row=2,
                column=0,
                sticky="ew",
                pady=(4, 0),
            )
        else:
            ctk.CTkFrame(isi, fg_color="transparent", height=4).grid(
                row=2,
                column=0,
                sticky="ew",
            )

        return kartu

    def _muat_halaman_rekomendasi(self):
        self._muat_daftar_pengguna(tampilkan_error=False)
        self._muat_rekomendasi_halaman()

    def _muat_rekomendasi_halaman(self):
        self._bersihkan_frame(self.frame_hasil_rekomendasi)

        nama = self.combo_rekomendasi.get().strip()

        if not nama:
            self._buat_label_kosong(
                self.frame_hasil_rekomendasi,
                "Pilih atau masukkan nama pengguna terlebih dahulu.",
            ).pack(fill="x")
            return

        try:
            hasil = self._panggil(ambil_rekomendasi, nama)
            rekomendasi = hasil["rekomendasi"]

            if not rekomendasi:
                self._buat_label_kosong(
                    self.frame_hasil_rekomendasi,
                    "Tidak ada rekomendasi yang dapat diberikan saat ini. "
                    "Tambahkan lebih banyak pengguna dan film favorit.",
                ).pack(fill="x")
                return

            ctk.CTkLabel(
                self.frame_hasil_rekomendasi,
                text=f"Hasil untuk {hasil['nama']} - {len(rekomendasi)} film",
                font=self.font_body_bold,
                text_color=WARNA_MUTED,
                anchor="w",
            ).pack(fill="x", pady=(0, 10))

            for item in rekomendasi:
                self._buat_kartu_rekomendasi(
                    self.frame_hasil_rekomendasi,
                    item,
                )
        except PenggunaTanpaFavorit as error:
            self._buat_label_kosong(
                self.frame_hasil_rekomendasi,
                str(error),
                WARNA_PERINGATAN,
            ).pack(fill="x")
        except PenggunaTidakDitemukan as error:
            self._buat_label_kosong(
                self.frame_hasil_rekomendasi,
                str(error),
                WARNA_GAGAL,
            ).pack(fill="x")
        except Exception as error:
            self._tampilkan_error(error)
            self._buat_label_kosong(
                self.frame_hasil_rekomendasi,
                self._pesan_error(error),
                WARNA_GAGAL,
            ).pack(fill="x")

    def _muat_halaman_favorit(self):
        self._muat_daftar_pengguna(tampilkan_error=False)
        self._muat_favorit_halaman()

    def _muat_favorit_halaman(self):
        self._bersihkan_frame(self.frame_hasil_favorit)

        nama = self.combo_favorit.get().strip()

        if not nama:
            self._buat_label_kosong(
                self.frame_hasil_favorit,
                "Pilih nama pengguna terlebih dahulu.",
            ).pack(fill="x")
            return

        try:
            hasil = self._panggil(ambil_film_favorit, nama)
            films = hasil["films"]

            ctk.CTkLabel(
                self.frame_hasil_favorit,
                text=f"Film favorit {hasil['nama']} ({len(films)})",
                font=self.font_body_bold,
                text_color=WARNA_MUTED,
                anchor="w",
            ).pack(fill="x", pady=(0, 10))

            if not films:
                self._buat_label_kosong(
                    self.frame_hasil_favorit,
                    "Belum ada film favorit yang tersimpan.",
                ).pack(fill="x")
                return

            for film in films:
                self._buat_baris_favorit(
                    self.frame_hasil_favorit,
                    film["judul"],
                    film["genres"],
                )
        except PenggunaTidakDitemukan as error:
            self._buat_label_kosong(
                self.frame_hasil_favorit,
                str(error),
                WARNA_GAGAL,
            ).pack(fill="x")
        except Exception as error:
            self._tampilkan_error(error)
            self._buat_label_kosong(
                self.frame_hasil_favorit,
                self._pesan_error(error),
                WARNA_GAGAL,
            ).pack(fill="x")

    def _muat_halaman_hapus(self):
        self._muat_daftar_pengguna(tampilkan_error=False)
        self._muat_film_untuk_dihapus()

    def _muat_film_untuk_dihapus(self):
        nama = self.combo_hapus_pengguna.get().strip()
        self.combo_film_hapus.configure(values=[])
        self.combo_film_hapus.set("")
        self.tombol_hapus_favorit.configure(state="disabled")
        self.label_status_hapus.configure(
            text="",
            text_color=WARNA_MUTED,
        )

        if not nama:
            self.label_status_hapus.configure(
                text="Pilih pengguna terlebih dahulu.",
                text_color=WARNA_MUTED,
            )
            return

        try:
            hasil = self._panggil(ambil_film_favorit, nama)
            films = hasil["films"]

            if not films:
                self.label_status_hapus.configure(
                    text=f"{hasil['nama']} belum memiliki film favorit.",
                    text_color=WARNA_PERINGATAN,
                )
                return

            judul_films = [film["judul"] for film in films]
            self.combo_film_hapus.configure(values=judul_films)
            self.combo_film_hapus.set(judul_films[0])
            self.tombol_hapus_favorit.configure(state="normal")
            self.label_status_hapus.configure(
                text=f"{len(judul_films)} film favorit ditemukan.",
                text_color=WARNA_MUTED,
            )
        except PenggunaTidakDitemukan as error:
            self.label_status_hapus.configure(
                text=str(error),
                text_color=WARNA_GAGAL,
            )
        except Exception as error:
            self._tampilkan_error(error)
            self.label_status_hapus.configure(
                text=self._pesan_error(error),
                text_color=WARNA_GAGAL,
            )

    def _aksi_hapus_favorit(self):
        nama = self.combo_hapus_pengguna.get().strip()
        judul = self.combo_film_hapus.get().strip()

        if not nama:
            self.tampilkan_notifikasi(
                "Pilih pengguna terlebih dahulu.",
                "peringatan",
            )
            return

        if not judul:
            self.tampilkan_notifikasi(
                "Pilih film favorit yang akan dihapus.",
                "peringatan",
            )
            return

        konfirmasi = messagebox.askyesno(
            "Konfirmasi Hapus Favorit",
            f"Hapus film '{judul}' dari daftar favorit '{nama}'?\n\n"
            "Node film tetap tersimpan di database.",
            parent=self,
        )

        if not konfirmasi:
            return

        try:
            hapus_film_favorit_data(
                self._pastikan_session(),
                nama,
                judul,
            )
            self.tampilkan_notifikasi(
                f"Film '{judul}' berhasil dihapus dari favorit '{nama}'.",
                "sukses",
            )
            self._muat_daftar_pengguna(tampilkan_error=False)
            self._muat_film_untuk_dihapus()
        except Exception as error:
            self._tampilkan_error(error)
            self._muat_film_untuk_dihapus()

    def _muat_statistik(self):
        try:
            statistik = self._panggil(ambil_statistik)
            self.var_stat_pengguna.set(str(statistik["total_pengguna"]))
            self.var_stat_film.set(str(statistik["total_film"]))
            self.var_stat_relasi.set(str(statistik["total_relasi"]))
            if self.session is not None:
                self._perbarui_status_koneksi("terhubung")
        except Exception as error:
            self.var_stat_pengguna.set("-")
            self.var_stat_film.set("-")
            self.var_stat_relasi.set("-")
            self._tampilkan_error(error)

    def _aksi_tambah_pengguna(self):
        nama = self.entry_nama_pengguna.get().strip()

        if not nama:
            self.label_hasil_tambah_pengguna.configure(
                text="Nama pengguna tidak boleh kosong.",
                text_color=WARNA_GAGAL,
            )
            self.tampilkan_notifikasi(
                "Nama pengguna tidak boleh kosong.",
                "peringatan",
            )
            return

        try:
            hasil = simpan_pengguna(
                self._pastikan_session(),
                nama,
            )

            if hasil["dibuat"]:
                pesan = f"Pengguna '{hasil['nama']}' berhasil ditambahkan."
                jenis = "sukses"
                self.entry_nama_pengguna.delete(0, "end")
            else:
                pesan = (
                    f"Pengguna '{hasil['nama']}' sudah terdaftar. "
                    "Data tidak diduplikasi."
                )
                jenis = "peringatan"

            self.label_hasil_tambah_pengguna.configure(
                text=pesan,
                text_color=WARNA_SUKSES if hasil["dibuat"] else WARNA_PERINGATAN,
            )
            self.tampilkan_notifikasi(pesan, jenis)
            self._muat_daftar_pengguna(tampilkan_error=False)
        except Exception as error:
            pesan = self._pesan_error(error)
            self.label_hasil_tambah_pengguna.configure(
                text=pesan,
                text_color=WARNA_GAGAL,
            )
            self._tampilkan_error(error)

    def _pilih_semua_genre(self):
        for variabel in self.genre_vars.values():
            variabel.set(1)

    def _bersihkan_pilihan_genre(self):
        for variabel in self.genre_vars.values():
            variabel.set(0)

    def _aksi_tambah_film(self):
        nama = self.combo_film_pengguna.get().strip()
        judul = self.entry_judul_film.get().strip()
        genres = [
            genre
            for genre, variabel in self.genre_vars.items()
            if variabel.get()
        ]

        if not nama:
            self.label_hasil_tambah_film.configure(
                text="Nama pengguna tidak boleh kosong.",
                text_color=WARNA_GAGAL,
            )
            self.tampilkan_notifikasi(
                "Nama pengguna tidak boleh kosong.",
                "peringatan",
            )
            return

        if not judul:
            self.label_hasil_tambah_film.configure(
                text="Judul film tidak boleh kosong.",
                text_color=WARNA_GAGAL,
            )
            self.tampilkan_notifikasi(
                "Judul film tidak boleh kosong.",
                "peringatan",
            )
            return

        if not genres:
            self.label_hasil_tambah_film.configure(
                text="Pilih minimal satu genre film.",
                text_color=WARNA_GAGAL,
            )
            self.tampilkan_notifikasi(
                "Pilih minimal satu genre film.",
                "peringatan",
            )
            return

        try:
            hasil = simpan_film_favorit(
                self._pastikan_session(),
                nama,
                judul,
                ", ".join(genres),
            )

            if hasil["sudah_ada"]:
                pesan = (
                    f"Film '{hasil['judul']}' sudah ada di daftar favorit "
                    f"'{hasil['nama']}'. Genre diperbarui."
                )
                jenis = "peringatan"
                warna = WARNA_PERINGATAN
            else:
                pesan = (
                    f"Film '{hasil['judul']}' berhasil ditambahkan ke "
                    f"favorit '{hasil['nama']}'."
                )
                jenis = "sukses"
                warna = WARNA_SUKSES

            self.label_hasil_tambah_film.configure(
                text=pesan + " Genre: " + ", ".join(hasil["genres"]),
                text_color=warna,
            )
            self.tampilkan_notifikasi(pesan, jenis)
            self.entry_judul_film.delete(0, "end")
            self._bersihkan_pilihan_genre()
            self._muat_daftar_pengguna(tampilkan_error=False)
        except Exception as error:
            pesan = self._pesan_error(error)
            self.label_hasil_tambah_film.configure(
                text=pesan,
                text_color=WARNA_GAGAL,
            )
            self._tampilkan_error(error)

    def jalankan_uji_asap(self):
        urutan = [
            "dashboard",
            "katalog",
            "tambah_pengguna",
            "tambah_film",
            "rekomendasi",
            "favorit",
            "hapus_favorit",
            "statistik",
        ]

        for index, kunci in enumerate(urutan, start=1):
            self.after(
                180 * index,
                lambda key=kunci: self._tampilkan_halaman(key),
            )

        self.after(180 * (len(urutan) + 2), self._tutup_aplikasi)


def main():
    mode_uji = "--smoke-test" in sys.argv
    aplikasi = AplikasiRekomendasiFilm(mode_uji=mode_uji)

    if mode_uji:
        aplikasi.update()
        aplikasi.jalankan_uji_asap()

    aplikasi.mainloop()

    if mode_uji:
        print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
