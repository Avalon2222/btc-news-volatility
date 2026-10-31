"""
deteksi.py - Mendeteksi hari-hari ketika harga Bitcoin bergerak "signifikan".

Ide intinya sederhana:
  1. Hitung RETURN harian = persen perubahan harga penutupan dibanding kemarin.
  2. Hitung VOLATILITAS = standar deviasi return selama N hari sebelumnya
     (default 30 hari). Ini "ukuran normal" gejolak pasar saat itu.
  3. Z-SCORE = return hari ini / volatilitas. Artinya: "hari ini gerak berapa
     kali lipat dari gejolak normal?"
  4. Kalau |z-score| >= ambang (default 2.5), hari itu kita tandai sebagai
     pergerakan signifikan dan tampilkan sebagai TITIK di chart.

Kenapa pakai z-score, bukan sekadar "turun 5%"?
  Karena 5% di tahun 2020 (pasar liar) itu biasa, tapi 5% di 2025 (pasar lebih
  tenang) itu kejadian besar. Z-score menyesuaikan ambang dengan kondisi pasar.

Semua fungsi di sini MURNI (pure): terima DataFrame, kembalikan DataFrame baru,
tidak menyentuh file/internet/Streamlit. Itu yang bikin gampang dites.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

JENDELA_DEFAULT = 30     # hari untuk menghitung volatilitas
AMBANG_Z_DEFAULT = 2.5   # |z| minimal supaya dianggap signifikan
TOLERANSI_HARI_DEFAULT = 1  # berita boleh selisih +-1 hari dari pergerakan


def hitung_return(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom `return_pct`: persen perubahan close dibanding hari sebelumnya.

    Contoh: close kemarin 100, hari ini 110 -> return_pct = 10.0
    Hari pertama tidak punya "kemarin", jadi nilainya NaN.
    """
    hasil = df.sort_values("tanggal").reset_index(drop=True).copy()
    hasil["return_pct"] = hasil["close"].pct_change() * 100
    return hasil


def hitung_volatilitas(df: pd.DataFrame, jendela: int = JENDELA_DEFAULT) -> pd.DataFrame:
    """Tambahkan kolom `volatilitas_pct`: std return N hari SEBELUM hari ini.

    Pakai .shift(1) supaya hari ini TIDAK ikut dihitung dalam ukuran "normal"-nya
    sendiri. Kalau tidak di-shift, hari crash besar akan membesarkan volatilitas
    dan menyembunyikan dirinya sendiri.
    """
    hasil = df.copy()
    if "return_pct" not in hasil.columns:
        hasil = hitung_return(hasil)
    hasil["volatilitas_pct"] = hasil["return_pct"].rolling(jendela).std().shift(1)
    return hasil


def hitung_z_score(df: pd.DataFrame, jendela: int = JENDELA_DEFAULT) -> pd.DataFrame:
    """Tambahkan kolom `z_score` = return_pct / volatilitas_pct."""
    hasil = hitung_volatilitas(df, jendela)
    # Hindari pembagian dengan nol kalau pasar benar-benar datar.
    vol = hasil["volatilitas_pct"].replace(0, np.nan)
    hasil["z_score"] = hasil["return_pct"] / vol
    return hasil


def deteksi_pergerakan(
    df: pd.DataFrame,
    ambang_z: float = AMBANG_Z_DEFAULT,
    jendela: int = JENDELA_DEFAULT,
) -> pd.DataFrame:
    """Kembalikan HANYA hari-hari dengan |z_score| >= ambang_z.

    Kolom tambahan `arah`: "naik" kalau return positif, "turun" kalau negatif.
    """
    lengkap = hitung_z_score(df, jendela)
    signifikan = lengkap[lengkap["z_score"].abs() >= ambang_z].copy()
    signifikan["arah"] = np.where(signifikan["return_pct"] > 0, "naik", "turun")
    return signifikan.reset_index(drop=True)


def cocokkan_berita(
    pergerakan: pd.DataFrame,
    berita: pd.DataFrame,
    toleransi_hari: int = TOLERANSI_HARI_DEFAULT,
) -> pd.DataFrame:
    """Pasangkan tiap pergerakan signifikan dengan berita terdekat.

    Aturan:
      - Berita dianggap "penyebab" kalau tanggalnya selisih <= toleransi_hari
        dari tanggal pergerakan (default +-1 hari, karena pasar kripto 24 jam
        dan perbedaan zona waktu sering bikin berita AS malam = candle besok).
      - Kalau ada beberapa berita, dipilih yang selisihnya paling kecil.
      - Kalau tidak ada, kolom judul = "Penyebab belum tercatat" dan kategori
        = "belum tercatat". Kita TIDAK mengarang penyebab.

    Hasil: pergerakan + kolom judul, kategori, penjelasan, sumber_url, selisih_hari.
    """
    hasil = pergerakan.copy()
    kolom_berita = ["judul", "kategori", "penjelasan", "sumber_url", "selisih_hari"]
    for kolom in kolom_berita:
        hasil[kolom] = None

    if berita.empty:
        return _isi_kosong(hasil)

    tgl_berita = pd.to_datetime(berita["tanggal"]).to_numpy()
    for i, baris in hasil.iterrows():
        selisih = np.abs((tgl_berita - np.datetime64(baris["tanggal"])) / np.timedelta64(1, "D"))
        idx_terdekat = int(selisih.argmin())
        if selisih[idx_terdekat] <= toleransi_hari:
            b = berita.iloc[idx_terdekat]
            hasil.loc[i, ["judul", "kategori", "penjelasan", "sumber_url"]] = [
                b["judul"], b["kategori"], b["penjelasan"], b["sumber_url"]
            ]
            hasil.loc[i, "selisih_hari"] = int(selisih[idx_terdekat])
    return _isi_kosong(hasil)


def _isi_kosong(df: pd.DataFrame) -> pd.DataFrame:
    """Isi baris tanpa berita dengan label jujur."""
    tanpa = df["judul"].isna()
    df.loc[tanpa, "judul"] = "Penyebab belum tercatat"
    df.loc[tanpa, "kategori"] = "belum tercatat"
    df.loc[tanpa, "penjelasan"] = (
        "Belum ada berita di data/berita_besar.csv untuk tanggal ini. "
        "Coba cari sendiri lalu tambahkan (lihat docs/LATIHAN.md, Latihan 1)."
    )
    df.loc[tanpa, "sumber_url"] = ""
    return df


def ringkasan(pergerakan: pd.DataFrame) -> dict:
    """Angka-angka kecil untuk kartu ringkasan di dashboard."""
    if pergerakan.empty:
        return {"total": 0, "naik": 0, "turun": 0, "terjelaskan": 0, "persen_terjelaskan": 0.0}
    terjelaskan = int((pergerakan["kategori"] != "belum tercatat").sum()) if "kategori" in pergerakan else 0
    return {
        "total": int(len(pergerakan)),
        "naik": int((pergerakan["arah"] == "naik").sum()),
        "turun": int((pergerakan["arah"] == "turun").sum()),
        "terjelaskan": terjelaskan,
        "persen_terjelaskan": round(100 * terjelaskan / len(pergerakan), 1),
    }
