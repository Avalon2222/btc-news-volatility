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
  Karena 5% di tahun 2020 (pasar sangat bergejolak) itu biasa, tapi 5% di 2025 (pasar lebih
  tenang) itu kejadian besar. Z-score menyesuaikan ambang dengan kondisi pasar.

Semua fungsi di sini MURNI (pure): terima DataFrame, kembalikan DataFrame baru,
tidak menyentuh file/internet/Streamlit. Itulah yang membuatnya mudah diuji.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

JENDELA_DEFAULT = 30     # hari untuk menghitung volatilitas
AMBANG_Z_DEFAULT = 2.5   # |z| minimal supaya dianggap signifikan
TOLERANSI_HARI_DEFAULT = 1  # berita boleh selisih +-1 hari dari pergerakan
VOLATILITAS_MINIMUM = 1e-9  # di bawah ini (persen) pasar dianggap datar, z-score tidak dihitung


def hitung_return(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom `return_pct`: persen perubahan close dibanding hari sebelumnya.

    Contoh: close kemarin 100, hari ini 110 -> return_pct = 10.0
    Hari pertama tidak punya "kemarin", jadi nilainya NaN.
    """
    # Tanggal dobel (misalnya snapshot lama + unduhan baru digabung) membuat return palsu 0%; ambil yang terakhir.
    # Baris tanpa tanggal (NaT) dibuang: kalau ikut, ia tersortir ke paling akhir dan memberi return palsu.
    # Close kosong atau <= 0 (candle rusak) membuat return -100% lalu tak hingga di hari berikutnya.
    # Close tak hingga ("inf" di CSV) memberi return tak hingga lalu -100% keesokan harinya.
    # Close berupa teks (DataFrame yang tidak lewat muat_harga) membuat perbandingan > 0 TypeError.
    df = df.assign(close=pd.to_numeric(df["close"], errors="coerce"))
    df = df[(df["close"] > 0) & np.isfinite(df["close"])]
    hasil = (df.dropna(subset=["tanggal"]).drop_duplicates("tanggal", keep="last")
               .sort_values("tanggal").reset_index(drop=True).copy())
    hasil["return_pct"] = hasil["close"].pct_change() * 100
    return hasil


def hitung_volatilitas(df: pd.DataFrame, jendela: int = JENDELA_DEFAULT) -> pd.DataFrame:
    """Tambahkan kolom `volatilitas_pct`: std return N hari SEBELUM hari ini.

    Pakai .shift(1) supaya hari ini TIDAK ikut dihitung dalam ukuran "normal"-nya
    sendiri. Kalau tidak di-shift, hari crash besar akan membesarkan volatilitas
    dan menyembunyikan dirinya sendiri.
    """
    # 30.0 dari input angka tetap diterima, tetapi 2.5 atau NaN ditolak dengan pesan yang jelas
    # (sebelumnya lolos lalu rolling() gagal dengan pesan pandas yang membingungkan).
    if isinstance(jendela, bool) or not (isinstance(jendela, (int, float, np.integer, np.floating))
                                         and float(jendela).is_integer()):
        raise ValueError(f"jendela harus bilangan bulat hari, dapat {jendela}")
    jendela = int(jendela)
    if jendela < 2:
        raise ValueError(f"jendela minimal 2 hari supaya std bisa dihitung, dapat {jendela}")
    hasil = df.copy()
    if "return_pct" not in hasil.columns:
        hasil = hitung_return(hasil)
    elif "tanggal" in hasil.columns:
        # Return yang sudah dihitung tetapi barisnya tidak urut tanggal (hasil filter/sampling) membuat
        # rolling std memakai "30 baris acak", bukan 30 hari sebelumnya.
        hasil = hasil.sort_values("tanggal", kind="mergesort").reset_index(drop=True)
    hasil["volatilitas_pct"] = hasil["return_pct"].rolling(jendela).std().shift(1)
    return hasil


def hitung_z_score(df: pd.DataFrame, jendela: int = JENDELA_DEFAULT) -> pd.DataFrame:
    """Tambahkan kolom `z_score` = return_pct / volatilitas_pct."""
    hasil = hitung_volatilitas(df, jendela)
    # Hindari pembagian dengan nol kalau pasar benar-benar datar. Rolling std dari return yang
    # konstan tidak selalu tepat 0 (sisa pembulatan ~1e-14), dan z-score lalu meledak ke 1e13.
    vol = hasil["volatilitas_pct"].where(hasil["volatilitas_pct"] > VOLATILITAS_MINIMUM)
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
    if not ambang_z > 0:
        raise ValueError(f"ambang_z harus lebih dari 0, dapat {ambang_z}")
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
        dan perbedaan zona waktu membuat berita malam di AS sering baru tercermin
        pada candle hari berikutnya).
      - Kalau ada beberapa berita, dipilih yang selisihnya paling kecil.
      - Kalau tidak ada, kolom judul = "Penyebab belum tercatat" dan kategori
        = "belum tercatat". Kita TIDAK mengarang penyebab.

    Hasil: pergerakan + kolom judul, kategori, penjelasan, sumber_url, selisih_hari.
    """
    # Index dibuat unik dulu: pergerakan hasil pd.concat bisa punya label dobel (0, 1, 0, 1), dan
    # hasil.loc[i, ...] lalu menulis berita yang sama ke semua baris berlabel i.
    if not toleransi_hari >= 0:   # "not >=" juga menolak NaN
        raise ValueError(f"toleransi_hari tidak boleh negatif, dapat {toleransi_hari}")
    index_asli = pergerakan.index
    hasil = pergerakan.reset_index(drop=True)
    kolom_berita = ["judul", "kategori", "penjelasan", "sumber_url", "selisih_hari"]
    for kolom in kolom_berita:
        hasil[kolom] = None

    if berita.empty:
        return _isi_kosong(hasil).set_axis(index_asli)

    # Selisih dihitung per hari kalender: berita "2024-03-06 23:00" tetap 1 hari dari candle 2024-03-05,
    # bukan 1,96 hari yang lolos dari toleransi.
    # Tanggal berzona waktu (berita yang tidak lewat muat_berita) disamakan ke UTC tanpa zona dulu;
    # kalau tidak, array-nya jadi object dan pengurangan dengan datetime64 langsung error.
    tgl_berita = _tanpa_zona(pd.to_datetime(berita["tanggal"])).dt.normalize()
    # Berita tanpa judul (data yang tidak lewat muat_berita) tidak bisa dijadikan penyebab; kalau ikut
    # dipilih, baris jadi "Penyebab belum tercatat" padahal berita lain yang sah ada dalam toleransi.
    tanpa_judul = berita["judul"].map(lambda j: not isinstance(j, str) or not j.strip()).to_numpy()
    tgl_berita = tgl_berita.where(~tanpa_judul).to_numpy()
    for i, baris in hasil.iterrows():
        tgl_gerak = pd.Timestamp(baris["tanggal"])
        if tgl_gerak.tzinfo is not None:
            tgl_gerak = tgl_gerak.tz_convert("UTC").tz_localize(None)
        tgl_gerak = np.datetime64(tgl_gerak.normalize())
        selisih = np.abs((tgl_berita - tgl_gerak) / np.timedelta64(1, "D"))
        # Berita bertanggal kosong (NaT) menghasilkan NaN. argmin biasa akan memilih NaN itu,
        # jadi pakai nanargmin dan lewati kalau tidak ada satu pun tanggal yang valid.
        if np.isnan(selisih).all():
            continue
        idx_terdekat = int(np.nanargmin(selisih))
        if selisih[idx_terdekat] <= toleransi_hari:
            b = berita.iloc[idx_terdekat]
            hasil.loc[i, ["judul", "kategori", "penjelasan", "sumber_url"]] = [
                b["judul"], b["kategori"], b["penjelasan"], b["sumber_url"]
            ]
            hasil.loc[i, "selisih_hari"] = int(selisih[idx_terdekat])
    return _isi_kosong(hasil).set_axis(index_asli)


def _tanpa_zona(tanggal: pd.Series) -> pd.Series:
    """Ubah tanggal berzona waktu ke UTC lalu buang zonanya; tanggal tanpa zona dibiarkan."""
    if getattr(tanggal.dt, "tz", None) is not None:
        return tanggal.dt.tz_convert("UTC").dt.tz_localize(None)
    return tanggal


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
    if "kategori" in pergerakan:
        kategori = pergerakan["kategori"]
        terjelaskan = int((kategori.notna() & (kategori != "belum tercatat")).sum())
    else:
        terjelaskan = 0
    return {
        "total": int(len(pergerakan)),
        "naik": int((pergerakan["arah"] == "naik").sum()),
        "turun": int((pergerakan["arah"] == "turun").sum()),
        "terjelaskan": terjelaskan,
        "persen_terjelaskan": round(100 * terjelaskan / len(pergerakan), 1),
    }
