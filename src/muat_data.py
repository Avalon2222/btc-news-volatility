"""
muat_data.py - Membaca dua file data proyek ini.

  data/btc_harga_harian.csv : harga BTC-USD harian (snapshot dari Yahoo Finance)
  data/berita_besar.csv     : daftar peristiwa besar dunia yang disusun manual

Dipisah dari app.py supaya bisa dipakai juga oleh tes dan notebook.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"
KATEGORI_VALID = {"trump_politik_as", "the_fed_makro", "geopolitik", "regulasi", "kripto_internal"}


def muat_harga(path: Path | None = None) -> pd.DataFrame:
    """Baca CSV harga. Kolom: tanggal (datetime), open, high, low, close, volume."""
    path = path or FOLDER_DATA / "btc_harga_harian.csv"
    df = pd.read_csv(path)
    kurang = {"tanggal", "close"} - set(df.columns)
    if kurang:
        raise ValueError(f"Kolom hilang di {Path(path).name}: {sorted(kurang)}")
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    return df.sort_values("tanggal").reset_index(drop=True)


def muat_berita(path: Path | None = None) -> pd.DataFrame:
    """Baca CSV berita dan validasi isinya biar salah ketik ketahuan cepat.

    Kolom wajib: tanggal, judul, kategori, penjelasan, sumber_url
    """
    path = Path(path or FOLDER_DATA / "berita_besar.csv")   # path boleh berupa string
    # Tanggal diubah setelah cek kolom: parse_dates di read_csv langsung error dengan pesan pandas
    # yang membingungkan kalau kolom tanggal tidak ada.
    df = pd.read_csv(path)
    wajib = {"tanggal", "judul", "kategori", "penjelasan", "sumber_url"}
    kurang = wajib - set(df.columns)
    if kurang:
        raise ValueError(f"Kolom hilang di {path.name}: {sorted(kurang)}")
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    # " Geopolitik" hasil edit manual di spreadsheet tetap kategori yang sama.
    df["kategori"] = df["kategori"].map(lambda k: k.strip().lower() or None if isinstance(k, str) else None)
    kosong = df["kategori"].isna()
    if kosong.any():
        baris = [int(i) + 2 for i in df.index[kosong]]  # +2: header dan nomor baris mulai dari 1
        raise ValueError(f"Kategori kosong di {path.name}, baris: {baris}")
    asing = set(df["kategori"].unique()) - KATEGORI_VALID
    if asing:
        raise ValueError(
            f"Kategori tidak dikenal di {path.name}: {sorted(asing)}. "
            f"Pilihan: {sorted(KATEGORI_VALID)}"
        )
    df["sumber_url"] = df["sumber_url"].fillna("")
    return df.sort_values("tanggal").reset_index(drop=True)
