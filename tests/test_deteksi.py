"""
Tes untuk src/deteksi.py. Jalankan:  python -m pytest tests/ -v

Pola tiap tes: SIAPKAN data kecil yang bisa dihitung di kepala -> PANGGIL fungsi
-> PERIKSA hasilnya. Kalau nanti kamu mengubah rumus, tes ini yang memberi tahu
apakah ada yang rusak.
"""

import pandas as pd
import pytest

from src import deteksi
from src.muat_data import muat_berita, muat_harga


def buat_harga(closes, mulai="2024-01-01"):
    """Membuat DataFrame harga mini dari daftar angka close."""
    tanggal = pd.date_range(mulai, periods=len(closes), freq="D")
    return pd.DataFrame({"tanggal": tanggal, "close": closes})


def test_return_harian_sederhana():
    df = deteksi.hitung_return(buat_harga([100, 110, 99]))
    assert pd.isna(df["return_pct"].iloc[0])          # hari pertama tidak punya "kemarin"
    assert df["return_pct"].iloc[1] == pytest.approx(10.0)
    assert df["return_pct"].iloc[2] == pytest.approx(-10.0)


def test_volatilitas_tidak_memasukkan_hari_ini():
    # 10 hari datar (return 0) lalu satu hari lompat 50%.
    harga = [100] * 11 + [150]
    df = deteksi.hitung_volatilitas(buat_harga(harga), jendela=5)
    # Volatilitas di hari lompatan dihitung dari 5 hari SEBELUMNYA (semua 0),
    # jadi harus 0, bukan terpengaruh lompatan itu sendiri.
    assert df["volatilitas_pct"].iloc[-1] == pytest.approx(0.0)


def test_deteksi_menangkap_hari_lompatan():
    # Pasar "tenang": naik turun 1%, lalu tiba-tiba +15%.
    closes = [100]
    for i in range(40):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 0.99))
    closes.append(closes[-1] * 1.15)
    hasil = deteksi.deteksi_pergerakan(buat_harga(closes), ambang_z=2.5, jendela=30)
    assert len(hasil) == 1
    assert hasil["arah"].iloc[0] == "naik"
    assert hasil["tanggal"].iloc[0] == pd.Timestamp("2024-01-01") + pd.Timedelta(days=41)


def test_ambang_lebih_tinggi_lebih_sedikit_titik():
    harga = muat_harga()
    sedikit = deteksi.deteksi_pergerakan(harga, ambang_z=3.5)
    banyak = deteksi.deteksi_pergerakan(harga, ambang_z=2.0)
    assert len(sedikit) < len(banyak)


def test_cocokkan_berita_dalam_toleransi():
    pergerakan = pd.DataFrame({
        "tanggal": pd.to_datetime(["2024-01-10", "2024-06-01"]),
        "return_pct": [5.0, -6.0],
        "arah": ["naik", "turun"],
    })
    berita = pd.DataFrame({
        "tanggal": pd.to_datetime(["2024-01-11"]),   # selisih 1 hari dari pergerakan pertama
        "judul": ["ETF disetujui"],
        "kategori": ["regulasi"],
        "penjelasan": ["SEC setuju"],
        "sumber_url": ["https://contoh.org"],
    })
    hasil = deteksi.cocokkan_berita(pergerakan, berita, toleransi_hari=1)
    assert hasil["judul"].iloc[0] == "ETF disetujui"
    assert hasil["selisih_hari"].iloc[0] == 1
    assert hasil["judul"].iloc[1] == "Penyebab belum tercatat"   # jujur kalau tidak ada
    assert hasil["kategori"].iloc[1] == "belum tercatat"


def test_dataset_berita_valid():
    berita = muat_berita()      # muat_berita() melempar error kalau kategori salah ketik
    assert len(berita) >= 50
    assert berita["tanggal"].is_monotonic_increasing
    assert berita["judul"].str.len().min() > 5


def test_ringkasan_data_asli():
    harga = muat_harga()
    berita = muat_berita()
    pergerakan = deteksi.cocokkan_berita(deteksi.deteksi_pergerakan(harga), berita)
    r = deteksi.ringkasan(pergerakan)
    assert r["total"] == r["naik"] + r["turun"]
    assert 0 <= r["persen_terjelaskan"] <= 100
    assert r["terjelaskan"] > r["total"] / 2       # mayoritas titik punya penjelasan


def test_pasar_datar_tidak_menghasilkan_titik():
    # Harga sama terus: return 0, volatilitas 0 -> z-score tidak terdefinisi,
    # jadi tidak boleh ada hari yang dianggap signifikan (dan tidak boleh error).
    hasil = deteksi.deteksi_pergerakan(buat_harga([100] * 50), ambang_z=2.5, jendela=30)
    assert hasil.empty


def test_deteksi_arah_turun():
    closes = [100]
    for i in range(40):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 0.99))
    closes.append(closes[-1] * 0.85)   # crash 15%
    hasil = deteksi.deteksi_pergerakan(buat_harga(closes), ambang_z=2.5, jendela=30)
    assert len(hasil) == 1
    assert hasil["arah"].iloc[0] == "turun"
    assert hasil["z_score"].iloc[0] < 0


def test_cocokkan_berita_tanpa_dataset():
    pergerakan = pd.DataFrame({
        "tanggal": pd.to_datetime(["2024-01-10"]),
        "return_pct": [5.0],
        "arah": ["naik"],
    })
    berita = pd.DataFrame(columns=["tanggal", "judul", "kategori", "penjelasan", "sumber_url"])
    hasil = deteksi.cocokkan_berita(pergerakan, berita)
    assert hasil["judul"].iloc[0] == "Penyebab belum tercatat"
    assert hasil["sumber_url"].iloc[0] == ""


def test_cocokkan_berita_memilih_yang_terdekat():
    pergerakan = pd.DataFrame({
        "tanggal": pd.to_datetime(["2024-03-05"]),
        "return_pct": [-7.0],
        "arah": ["turun"],
    })
    berita = pd.DataFrame({
        "tanggal": pd.to_datetime(["2024-03-04", "2024-03-05"]),
        "judul": ["Berita kemarin", "Berita hari ini"],
        "kategori": ["makro", "regulasi"],
        "penjelasan": ["a", "b"],
        "sumber_url": ["https://a.org", "https://b.org"],
    })
    hasil = deteksi.cocokkan_berita(pergerakan, berita, toleransi_hari=1)
    assert hasil["judul"].iloc[0] == "Berita hari ini"
    assert hasil["selisih_hari"].iloc[0] == 0


def test_ringkasan_kosong():
    r = deteksi.ringkasan(pd.DataFrame())
    assert r == {"total": 0, "naik": 0, "turun": 0, "terjelaskan": 0, "persen_terjelaskan": 0.0}


def test_z_score_pasar_datar_jadi_nan_bukan_inf():
    # Harga tidak bergerak sama sekali -> volatilitas 0. Z-score harus NaN,
    # bukan inf, supaya hari itu tidak ikut terdeteksi sebagai lonjakan.
    df = deteksi.hitung_z_score(buat_harga([100] * 8), jendela=3)
    assert not df["z_score"].isin([float("inf"), float("-inf")]).any()
    assert df["z_score"].iloc[4:].isna().all()


def test_z_score_sama_dengan_return_dibagi_volatilitas():
    df = deteksi.hitung_z_score(buat_harga([100, 102, 99, 101, 120]), jendela=3)
    baris = df.iloc[-1]
    assert baris["z_score"] == pytest.approx(baris["return_pct"] / baris["volatilitas_pct"])
    assert baris["z_score"] > 2.5  # lompatan ~19% jauh di atas gejolak normal


def test_z_score_mengurutkan_tanggal_dulu():
    acak = buat_harga([100, 102, 99, 101, 120]).sample(frac=1, random_state=0)
    df = deteksi.hitung_z_score(acak, jendela=3)
    assert df["tanggal"].is_monotonic_increasing
    assert df["close"].iloc[-1] == 120


def test_isi_kosong_hanya_baris_tanpa_berita():
    df = pd.DataFrame({"tanggal": pd.to_datetime(["2024-03-05", "2024-03-06"]),
                       "judul": ["ETF disetujui", None], "kategori": ["regulasi", None],
                       "penjelasan": ["Ada beritanya.", None], "sumber_url": ["https://contoh", None]})
    hasil = deteksi._isi_kosong(df)
    assert hasil.loc[0, "judul"] == "ETF disetujui" and hasil.loc[0, "sumber_url"] == "https://contoh"
    assert hasil.loc[1, "judul"] == "Penyebab belum tercatat"
    assert hasil.loc[1, "kategori"] == "belum tercatat"
    assert "LATIHAN.md" in hasil.loc[1, "penjelasan"]
    assert hasil.loc[1, "sumber_url"] == ""


def test_cocokkan_berita_abaikan_tanggal_berita_rusak():
    """Satu berita bertanggal kosong tidak boleh membuat berita lain ikut tidak cocok."""
    pergerakan = pd.DataFrame({"tanggal": pd.to_datetime(["2024-03-05"]), "return_pct": [8.0], "arah": ["naik"]})
    berita = pd.DataFrame({
        "tanggal": pd.to_datetime([None, "2024-03-05"]),
        "judul": ["Tanpa tanggal", "ETF disetujui"],
        "kategori": ["makro", "regulasi"],
        "penjelasan": ["a", "b"],
        "sumber_url": ["", "https://b.org"],
    })
    hasil = deteksi.cocokkan_berita(pergerakan, berita)
    assert hasil["judul"].iloc[0] == "ETF disetujui"


def test_cocokkan_berita_semua_tanggal_rusak():
    pergerakan = pd.DataFrame({"tanggal": pd.to_datetime(["2024-03-05"]), "return_pct": [8.0], "arah": ["naik"]})
    berita = pd.DataFrame({"tanggal": pd.to_datetime([None]), "judul": ["x"], "kategori": ["makro"],
                           "penjelasan": ["a"], "sumber_url": [""]})
    hasil = deteksi.cocokkan_berita(pergerakan, berita)
    assert hasil["kategori"].iloc[0] == "belum tercatat"


def test_ringkasan_tanpa_kolom_kategori():
    """Pergerakan yang belum dicocokkan dengan berita tetap bisa diringkas."""
    pergerakan = pd.DataFrame({"arah": ["naik", "turun", "turun"]})
    r = deteksi.ringkasan(pergerakan)
    assert r == {"total": 3, "naik": 1, "turun": 2, "terjelaskan": 0, "persen_terjelaskan": 0.0}


def test_jendela_pendek_mulai_mendeteksi_lebih_awal():
    closes = [100 + (i % 2) for i in range(12)] + [130]
    harga = buat_harga(closes)
    # Dengan jendela 30 hari, 13 hari data belum cukup untuk punya volatilitas sama sekali.
    assert deteksi.deteksi_pergerakan(harga, jendela=30).empty
    pendek = deteksi.deteksi_pergerakan(harga, jendela=5)
    assert pendek["tanggal"].tolist() == [harga["tanggal"].iloc[-1]]
    assert pendek["arah"].iloc[0] == "naik"
