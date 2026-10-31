# Sumber data

## 1. `btc_harga_harian.csv` — harga Bitcoin harian

| Kolom | Arti |
|---|---|
| `tanggal` | Tanggal candle harian (UTC) |
| `open`, `high`, `low`, `close` | Harga buka, tertinggi, terendah, tutup dalam USD |
| `volume` | Volume perdagangan (USD) menurut Yahoo |

- **Sumber:** Yahoo Finance, simbol `BTC-USD` (agregat dari CoinMarketCap). Endpoint publik
  `https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD`, gratis, tanpa API key.
- **Rentang snapshot:** 1 Januari 2020 sampai tanggal terakhir di file. Perbarui dengan
  `python -m src.ambil_harga` atau tombol di sidebar app.
- **Kenapa bukan CoinGecko / Binance / CryptoCompare?** CoinGecko gratis hanya memberi 365 hari harian,
  Binance memblokir beberapa negara, CryptoCompare sekarang mewajibkan API key.
- **Catatan:** harga penutupan harian UTC. Berita sore hari waktu AS (misalnya pengumuman The Fed pukul
  14.00 ET = 19.00 UTC) sering baru terlihat penuh di candle hari berikutnya.

## 2. `berita_besar.csv` — peristiwa besar dunia

| Kolom | Arti |
|---|---|
| `tanggal` | Tanggal peristiwa (UTC). Untuk peristiwa akhir pekan, tanggal reaksi pasar kripto |
| `judul` | Satu baris ringkas |
| `kategori` | Salah satu dari: `trump_politik_as`, `the_fed_makro`, `geopolitik`, `regulasi`, `kripto_internal` |
| `penjelasan` | 1–3 kalimat: apa yang terjadi dan kenapa pasar bereaksi |
| `sumber_url` | Link yang bisa dibuka: rilis resmi (The Fed, SEC, BLS, OCC), media arus utama, atau Wikipedia |

### Cara dataset ini disusun

1. Jalankan deteksi (`src/deteksi.py`) untuk mendapatkan daftar hari dengan |z-score| ≥ 2,5.
2. Untuk tiap hari itu, cari berita besar ±1 hari di media arus utama (Reuters, CNBC, Bloomberg, CoinDesk,
   The Block) dan rilis resmi.
3. Tulis penjelasan singkat, pilih kategori, simpan link.
4. Tambahkan juga peristiwa penting yang reaksinya *tidak* besar (misalnya halving, pemangkasan bunga yang
   sudah diperkirakan) supaya pembaca melihat bahwa tidak semua berita besar menggerakkan harga.

### Arti kategori

| Kategori | Contoh |
|---|---|
| `trump_politik_as` | Pernyataan/kebijakan Trump, tarif, pemilu AS, Crypto Strategic Reserve |
| `the_fed_makro` | Keputusan FOMC, pidato Powell, data CPI/PPI/PDB, crash saham, krisis bank |
| `geopolitik` | Perang, serangan militer, sanksi |
| `regulasi` | SEC, persetujuan ETF, larangan China, UU stablecoin, kebijakan negara lain |
| `kripto_internal` | Kebangkrutan bursa, peretasan, halving, arus ETF, pembelian korporasi |

### Keterbatasan

- Dikurasi manual oleh satu orang; bisa bias ke berita berbahasa Inggris yang "terkenal".
- Banyak hari bergejolak punya lebih dari satu penyebab; yang ditulis adalah penjelasan dominan.
- Hari dengan pergerakan besar yang belum punya baris di file ini ditampilkan sebagai titik abu-abu.
  Itu undangan untuk menambahkan, bukan kesimpulan bahwa tidak ada penyebabnya.
- Angka di kolom `penjelasan` (misalnya "likuidasi $19 miliar") diambil dari pemberitaan saat itu dan
  bisa berbeda antar sumber.
