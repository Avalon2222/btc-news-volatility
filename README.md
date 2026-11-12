# ₿ Bitcoin vs Berita Dunia

[![tests](https://github.com/Avalon2222/btc-news-volatility/actions/workflows/tests.yml/badge.svg)](https://github.com/Avalon2222/btc-news-volatility/actions/workflows/tests.yml) [![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://btc-news-volatility.streamlit.app)

> Chart interaktif harga Bitcoin yang **otomatis menandai hari-hari bergejolak**, lalu memasangkannya dengan
> berita besar dunia: pernyataan Trump, keputusan The Fed, perang, regulasi, sampai bursa kripto yang bangkrut.
> Arahkan kursor ke titik untuk lihat penyebabnya, klik untuk detail dan sumber.
> Dibangun dengan Python, pandas, Plotly, dan Streamlit.

## 🇬🇧 In English

**Did the news move Bitcoin, or did Twitter just say so?** An interactive Bitcoin price chart that flags statistically unusual days with a rolling z-score and pairs each one with a curated dataset of 102 major world events (2020–2026): Fed decisions, Trump statements, wars, regulation, exchange collapses.

- **Hover** a flagged point to see the likely cause, click it for the full story and source link.
- **Measure** which news categories move the price most often, and by how much.
- **Count** the big moves that have no clear news behind them at all.
- **Tune** the detection threshold, volatility window, and date tolerance live.

**Built with:** Python, pandas, NumPy, Plotly, Streamlit  
**Data:** Daily BTC-USD prices from Yahoo Finance and a hand-curated event list with a source for every event  
**Engineering:** Tested anomaly-detection module, CI on GitHub Actions, and a learning mode with formulas and code

*The rest of this README is in Indonesian.*

**🚀 Coba langsung di browser:** [btc-news-volatility.streamlit.app](https://btc-news-volatility.streamlit.app)

![Chart utama](docs/screenshots/02_hover.png)

## Kenapa project ini ada?

Setiap kali harga Bitcoin melonjak atau anjlok, lini masa penuh orang yang "tahu" penyebabnya: Trump membuat pernyataan,
The Fed naikkan bunga, ada perang. Tapi klaim itu jarang dicek balik ke data. Project ini mencoba menjawabnya
secara sistematis:

1. **Hari mana saja** harga Bitcoin bergerak jauh di luar kebiasaannya?
2. **Ada berita besar apa** di hari-hari itu?
3. **Kategori berita mana** yang paling sering, dan paling besar, menggoyang harga?
4. Berapa banyak gerakan besar yang **tidak** punya penjelasan berita yang jelas?

Hasilnya bukan ramalan harga, tapi alat untuk membaca hubungan antara berita dan pasar dengan lebih jujur.

## Fitur

| Tab | Isi |
|---|---|
| 📈 Chart | Garis harga + titik berwarna per kategori penyebab. Hover = ringkasan berita, klik = kartu detail + link sumber. Ukuran titik mengikuti seberapa ekstrem gerakannya |
| 📋 Flagged days | Tabel semua pergerakan signifikan di rentang yang dipilih, bisa diurutkan dan di-download sebagai CSV |
| 📊 Stats | Jumlah titik per kategori, rata-rata besar gerakan per kategori, 15 berita dengan reaksi terbesar, jumlah hari ekstrem per tahun |
| 📰 All news | 102 peristiwa 2020–2026 beserta reaksi harga di hari itu, walau kecil |
| 🧭 How it works | Diagram alur data, sumber, dan daftar keterbatasan |
| 🎓 Learning mode | Toggle di sidebar: tiap grafik dapat penjelasan rumus + potongan kode |

Semua parameter deteksi (ambang z-score, jendela volatilitas, toleransi tanggal) bisa digeser lewat slider dan
seluruh dashboard langsung dihitung ulang.

![Detail titik](docs/screenshots/03_klik_detail.png)
![Statistik](docs/screenshots/05_statistik.png)

## Cara menjalankan

```bash
git clone https://github.com/Avalon2222/btc-news-volatility.git
cd btc-news-volatility
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Buka `http://localhost:8501`. Jalankan tes dengan `python -m pytest tests/ -v`.
Perbarui data harga dengan `python -m src.ambil_harga` (atau tombol di sidebar). Snapshot di `data/` juga diperbarui otomatis setiap Senin lewat GitHub Actions (`.github/workflows/perbarui-data.yml`).

## Cara kerja (ringkas)

```mermaid
flowchart LR
    Y[Yahoo Finance BTC-USD] -->|src/ambil_harga.py| H[data/btc_harga_harian.csv]
    H --> D[src/deteksi.py<br/>return → volatilitas → z-score]
    D --> C[cocokkan_berita<br/>±1 hari]
    B[data/berita_besar.csv<br/>102 peristiwa, dikurasi manual] --> C
    C --> A[app.py<br/>Streamlit + Plotly]
```

Inti deteksinya tiga baris pandas:

```python
df["return_pct"]      = df["close"].pct_change() * 100                      # % perubahan dari kemarin
df["volatilitas_pct"] = df["return_pct"].rolling(30).std().shift(1)         # gejolak "normal" 30 hari sebelumnya
df["z_score"]         = df["return_pct"] / df["volatilitas_pct"]            # berapa kali lipat dari normal?
titik = df[df["z_score"].abs() >= 2.5]
```

Kenapa z-score dan bukan sekadar "turun 5%"? Karena 5% di 2020 itu hari biasa, sedangkan 5% di 2025 itu
berita utama. Z-score menyesuaikan ambang dengan kondisi pasar saat itu. Penjelasan lengkap ada di
[docs/BELAJAR.md](docs/BELAJAR.md).

## Temuan menarik (ambang |z| ≥ 2,5, 2020–Okt 2026)

- Ada **104 hari** dengan pergerakan ekstrem dari 2.496 hari data; **sekitar 77%** di antaranya bisa
  dipasangkan dengan berita besar di dataset.
- Kategori **The Fed & makroekonomi** paling sering muncul: Bitcoin bergerak searah dengan saham teknologi
  AS jauh lebih sering daripada yang diduga narasi "emas digital".
- Gerakan harian terbesar sejak 2020 tetap **crash COVID 12 Maret 2020 (−37%)**. Di era ETF (2024+)
  gerakan ekstrem jarang lebih dari ±10%, tapi **likuidasi** jadi penguat utama: 10 Oktober 2025
  (ancaman tarif 100% ke China) dan 5 Februari 2026 (crash saham tech) keduanya diperbesar oleh posisi
  leverage yang dipaksa tutup.
- Banyak berita "besar" ternyata **tidak** menggerakkan harga, misalnya halving 2024 dan pemangkasan bunga
  September 2025: pasar sudah menghitungnya duluan (*priced in*).

Angka di atas berubah kalau slider digeser, dan itu memang tujuannya.

## Struktur folder

```
btc-news-volatility/
├── app.py                  # dashboard Streamlit (tampilan)
├── src/
│   ├── ambil_harga.py      # unduh harga dari Yahoo Finance
│   ├── muat_data.py        # baca + validasi CSV
│   └── deteksi.py          # return, volatilitas, z-score, pencocokan berita
├── data/
│   ├── btc_harga_harian.csv
│   ├── berita_besar.csv    # dataset berita, mudah ditambah
│   └── SUMBER_DATA.md
├── tests/test_deteksi.py
└── docs/
    ├── BELAJAR.md          # panduan belajar langkah demi langkah
    ├── LATIHAN.md          # 9 latihan bertingkat
    └── screenshots/
```

## Keterbatasan

- **Korelasi bukan sebab-akibat.** Berita yang berdekatan tanggalnya adalah penjelasan yang paling masuk akal,
  bukan bukti. Sering ada beberapa faktor sekaligus.
- Dataset berita dikurasi manual dan bisa bias ke berita berbahasa Inggris yang terkenal. Titik abu-abu
  menandai gerakan besar yang belum ada catatannya.
- Harga harian menyembunyikan flash crash yang pulih di hari yang sama.
- Bukan saran investasi.

## Lisensi

MIT. Data harga milik Yahoo Finance; dataset berita boleh dipakai ulang dengan menyebut repo ini.
