"""
Tes untuk src/muat_data.py dan bagian parsing src/ambil_harga.py.

Semua tes di sini OFFLINE: CSV dibuat di folder sementara (tmp_path) dan
respons Yahoo dipalsukan, jadi tes tetap jalan walau internet mati.
"""

import pandas as pd
import pytest

from src import ambil_harga
from src.muat_data import muat_berita, muat_harga

KOLOM_BERITA = "tanggal,judul,kategori,penjelasan,sumber_url\n"


def test_muat_harga_diurutkan_dan_tanggal_jadi_datetime(tmp_path):
    csv = tmp_path / "harga.csv"
    csv.write_text(
        "tanggal,open,high,low,close,volume\n"
        "2024-01-03,3,3,3,3,1\n"
        "2024-01-01,1,1,1,1,1\n"
        "2024-01-02,2,2,2,2,1\n"
    )
    df = muat_harga(csv)
    assert pd.api.types.is_datetime64_any_dtype(df["tanggal"])
    assert df["close"].tolist() == [1, 2, 3]
    assert df.index.tolist() == [0, 1, 2]


def test_muat_berita_kolom_hilang_langsung_error(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text("tanggal,judul,kategori\n2024-01-01,Tes,geopolitik\n")
    with pytest.raises(ValueError, match="Kolom hilang"):
        muat_berita(csv)


def test_muat_berita_kategori_salah_ketik_ketahuan(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text(KOLOM_BERITA + "2024-01-01,Tes,geopolitk,Salah ketik,\n")
    with pytest.raises(ValueError, match="geopolitk"):
        muat_berita(csv)


def test_muat_berita_url_kosong_jadi_string_kosong(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text(
        KOLOM_BERITA
        + "2024-02-01,B,regulasi,Penjelasan B,\n"
        + "2024-01-01,A,geopolitik,Penjelasan A,https://contoh.id\n"
    )
    df = muat_berita(csv)
    assert df["judul"].tolist() == ["A", "B"]          # urut tanggal
    assert df.loc[1, "sumber_url"] == ""                # bukan NaN


def test_ke_unix_pakai_utc():
    assert ambil_harga._ke_unix("1970-01-02") == 86400


class _ResponsPalsu:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_ambil_harga_yahoo_merapikan_respons(monkeypatch):
    hari = 86400
    data = {
        "chart": {
            "result": [
                {
                    # hari ke-2 dobel, hari ke-3 close kosong (belum ditutup)
                    "timestamp": [0, hari, hari + 60, 2 * hari],
                    "indicators": {
                        "quote": [
                            {
                                "open": [1.111, 2.0, 2.0, 3.0],
                                "high": [1.5, 2.5, 2.5, 3.5],
                                "low": [0.9, 1.9, 1.9, 2.9],
                                "close": [1.234, 2.346, 2.346, None],
                                "volume": [10, None, None, 30],
                            }
                        ]
                    },
                }
            ]
        }
    }
    monkeypatch.setattr(ambil_harga.requests, "get", lambda *a, **k: _ResponsPalsu(data))

    df = ambil_harga.ambil_harga_yahoo("1970-01-01", "1970-01-05")

    assert len(df) == 2                                  # dobel dibuang, close kosong dibuang
    assert df["close"].tolist() == [1.23, 2.35]          # dibulatkan 2 desimal
    assert df["volume"].tolist() == [10, 0]              # volume kosong jadi 0
    assert str(df["volume"].dtype) == "int64"
    assert df["tanggal"].dt.hour.eq(0).all()             # jam dinolkan


def test_perbarui_csv_buang_candle_hari_ini(monkeypatch, tmp_path):
    palsu = pd.DataFrame({"tanggal": pd.to_datetime(["2026-11-07", "2026-11-08", "2026-11-09"]),
                          "open": [1.0, 2.0, 3.0], "high": [1.0, 2.0, 3.0], "low": [1.0, 2.0, 3.0],
                          "close": [1.0, 2.0, 3.0], "volume": [1, 2, 3]})
    monkeypatch.setattr(ambil_harga, "ambil_harga_yahoo", lambda: palsu)
    path = tmp_path / "btc.csv"
    df = ambil_harga.perbarui_csv(path, hari_ini=pd.Timestamp("2026-11-09"))
    assert df["tanggal"].dt.strftime("%Y-%m-%d").tolist() == ["2026-11-07", "2026-11-08"]
    assert pd.read_csv(path)["tanggal"].tolist() == ["2026-11-07", "2026-11-08"]


def test_muat_berita_kategori_kosong_sebut_nomor_baris(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text(
        KOLOM_BERITA
        + "2024-01-01,A,geopolitik,Penjelasan A,\n"
        + "2024-01-02,B,,Lupa isi kategori,\n"
    )
    with pytest.raises(ValueError, match=r"Kategori kosong.*\[3\]"):
        muat_berita(csv)


def test_ambil_harga_yahoo_tolak_rentang_terbalik(monkeypatch):
    def jangan_dipanggil(*a, **k):
        raise AssertionError("request tidak boleh dikirim kalau rentang tanggal salah")

    monkeypatch.setattr(ambil_harga.requests, "get", jangan_dipanggil)
    with pytest.raises(ValueError, match="setelah 'mulai'"):
        ambil_harga.ambil_harga_yahoo("2024-05-01", "2024-01-01")


def test_muat_harga_kolom_close_hilang_langsung_error(tmp_path):
    csv = tmp_path / "harga.csv"
    csv.write_text("tanggal,open,high,low,volume\n2024-01-01,1,1,1,1\n")
    with pytest.raises(ValueError, match="close"):
        muat_harga(csv)


def test_muat_berita_terima_path_string(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text(KOLOM_BERITA + "2024-01-01,Tes,geopolitk,Salah ketik,\n")
    # Pesan error memakai nama file; dulu path string membuat AttributeError, bukan ValueError.
    with pytest.raises(ValueError, match="berita.csv"):
        muat_berita(str(csv))


def test_muat_berita_tanpa_kolom_tanggal_pesan_jelas(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text("judul,kategori,penjelasan,sumber_url\nTes,geopolitik,Tanpa tanggal,\n")
    with pytest.raises(ValueError, match=r"Kolom hilang.*tanggal"):
        muat_berita(csv)


def test_ambil_harga_yahoo_respons_error_dan_kosong(monkeypatch):
    galat = {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}
    monkeypatch.setattr(ambil_harga.requests, "get", lambda *a, **k: _ResponsPalsu(galat))
    with pytest.raises(ValueError, match="Not Found"):
        ambil_harga.ambil_harga_yahoo("2024-01-01", "2024-01-05")

    tanpa_candle = {"chart": {"result": [{"meta": {}, "indicators": {"quote": [{}]}}], "error": None}}
    monkeypatch.setattr(ambil_harga.requests, "get", lambda *a, **k: _ResponsPalsu(tanpa_candle))
    df = ambil_harga.ambil_harga_yahoo("2024-01-01", "2024-01-05")
    assert df.empty and list(df.columns) == ["tanggal", "open", "high", "low", "close", "volume"]


def test_perbarui_csv_tidak_menimpa_dengan_data_kosong(monkeypatch, tmp_path):
    path = tmp_path / "btc.csv"
    path.write_text("tanggal,close\n2026-11-07,1.0\n")
    kosong = pd.DataFrame(columns=["tanggal", "open", "high", "low", "close", "volume"])
    kosong["tanggal"] = pd.to_datetime(kosong["tanggal"])
    monkeypatch.setattr(ambil_harga, "ambil_harga_yahoo", lambda: kosong)
    with pytest.raises(ValueError, match="tidak ditimpa"):
        ambil_harga.perbarui_csv(path, hari_ini=pd.Timestamp("2026-11-09"))
    assert path.read_text() == "tanggal,close\n2026-11-07,1.0\n"


def test_muat_berita_kategori_dirapikan_spasi_dan_huruf(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text(KOLOM_BERITA + '2024-01-01,A," Geopolitik ",Spasi,\n2024-01-02,B,REGULASI,Kapital,\n')
    df = muat_berita(csv)
    assert df["kategori"].tolist() == ["geopolitik", "regulasi"]


def test_muat_berita_kategori_spasi_saja_dianggap_kosong(tmp_path):
    csv = tmp_path / "berita.csv"
    csv.write_text(KOLOM_BERITA + '2024-01-01,A,"  ",Kosong,\n')
    with pytest.raises(ValueError, match="Kategori kosong"):
        muat_berita(csv)


def test_muat_berita_semua_url_kosong_tanpa_warning(tmp_path):
    import warnings

    csv = tmp_path / "berita.csv"
    csv.write_text(KOLOM_BERITA + "2024-01-01,A,geopolitik,Tanpa sumber,\n")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        df = muat_berita(csv)
    assert df["sumber_url"].tolist() == [""]
