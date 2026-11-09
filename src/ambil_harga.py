"""
ambil_harga.py - Mengunduh harga Bitcoin harian dari Yahoo Finance.

Kenapa Yahoo Finance?
  - Gratis dan TIDAK butuh API key (CoinGecko gratis hanya memberi 365 hari,
    Binance diblokir di beberapa negara, CryptoCompare sekarang minta key).
  - Datanya harian (open/high/low/close/volume) sejak 2014.

Cara pakai dari terminal (memperbarui data/btc_harga_harian.csv):
    python -m src.ambil_harga

Cara pakai dari kode:
    from src.ambil_harga import ambil_harga_yahoo
    df = ambil_harga_yahoo("2020-01-01")
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

URL_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD"
# Yahoo menolak request tanpa User-Agent "mirip browser".
HEADER = {"User-Agent": "Mozilla/5.0 (btc-news-volatility; belajar Python)"}
PATH_CSV = Path(__file__).resolve().parent.parent / "data" / "btc_harga_harian.csv"


def _ke_unix(tanggal: str) -> int:
    """'2020-01-01' -> detik sejak 1970 (format yang diminta Yahoo)."""
    dt = datetime.strptime(tanggal, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def ambil_harga_yahoo(mulai: str = "2020-01-01", sampai: str | None = None) -> pd.DataFrame:
    """Unduh harga harian BTC-USD dan kembalikan DataFrame rapi.

    Kolom hasil: tanggal, open, high, low, close, volume.
    Melempar exception kalau internet mati / Yahoo berubah, jadi pemanggil
    (app.py) bisa fallback ke CSV lokal.
    """
    akhir = _ke_unix(sampai) if sampai else int(datetime.now(tz=timezone.utc).timestamp())
    params = {"interval": "1d", "period1": _ke_unix(mulai), "period2": akhir}
    r = requests.get(URL_YAHOO, params=params, headers=HEADER, timeout=20)
    r.raise_for_status()

    hasil = r.json()["chart"]["result"][0]
    kutipan = hasil["indicators"]["quote"][0]
    df = pd.DataFrame(
        {
            "tanggal": pd.to_datetime(hasil["timestamp"], unit="s").normalize(),
            "open": kutipan["open"],
            "high": kutipan["high"],
            "low": kutipan["low"],
            "close": kutipan["close"],
            "volume": kutipan["volume"],
        }
    )
    df = df.dropna(subset=["close"]).drop_duplicates("tanggal").sort_values("tanggal")
    for kolom in ["open", "high", "low", "close"]:
        df[kolom] = df[kolom].astype(float).round(2)
    df["volume"] = df["volume"].fillna(0).astype("int64")
    return df.reset_index(drop=True)


def perbarui_csv(path: Path = PATH_CSV, hari_ini: pd.Timestamp | None = None) -> pd.DataFrame:
    """Unduh ulang lalu timpa CSV snapshot di folder data/.

    Candle hari ini (UTC) belum ditutup, jadi angkanya masih berubah. Baris itu tidak ikut disimpan
    supaya snapshot hanya berisi hari yang sudah final.
    """
    hari_ini = hari_ini if hari_ini is not None else pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    df = ambil_harga_yahoo()
    df = df[df["tanggal"] < hari_ini].reset_index(drop=True)
    df.to_csv(path, index=False)
    return df


if __name__ == "__main__":
    data = perbarui_csv()
    print(f"OK: {len(data)} baris disimpan ke {PATH_CSV}")
    print(data.tail(3).to_string(index=False))
