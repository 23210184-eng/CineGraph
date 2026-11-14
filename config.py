import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE")


def create_driver():
    konfigurasi = {
        "NEO4J_URI": URI,
        "NEO4J_USERNAME": USERNAME,
        "NEO4J_PASSWORD": PASSWORD,
        "NEO4J_DATABASE": DATABASE,
    }
    belum_diisi = [nama for nama, nilai in konfigurasi.items() if not nilai]

    if belum_diisi:
        raise ValueError(
            "Konfigurasi Neo4j belum lengkap. "
            "Variabel yang belum diisi: " + ", ".join(belum_diisi) + ". "
            "Periksa file .env."
        )

    return GraphDatabase.driver(
        URI,
        auth=(USERNAME, PASSWORD),
    )
