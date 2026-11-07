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
