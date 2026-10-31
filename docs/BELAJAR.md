# 🎓 Panduan Belajar: Bedah Project dari Nol

Panduan ini buat kamu yang baru bisa Python dasar dan pengin ngerti *kenapa* kodenya ditulis begitu,
bukan cuma *apa* yang ditulis. Baca sambil buka file yang dibahas. Santai aja, satu langkah sehari juga oke.

Yang bakal kamu pelajari:
- cara membaca data deret waktu (time series) dengan pandas,
- satu konsep statistik yang dipakai di mana-mana: **z-score**,
- cara menyambungkan dua tabel berdasarkan tanggal yang "kira-kira sama",
- cara bikin chart interaktif yang bisa diklik di Streamlit,
- dan kebiasaan paling penting: menulis tes dan jujur soal keterbatasan.

---

## Peta besar: 4 lapisan

```
┌──────────────────────────────────────────────────────────────────┐
│  LAPISAN 4: TAMPILAN          app.py                              │
│  sidebar → hitung → chart Plotly → kartu detail saat titik diklik │
├──────────────────────────────────────────────────────────────────┤
│  LAPISAN 3: LOGIKA            src/deteksi.py                      │
│  return → volatilitas → z-score → titik → cocokkan dengan berita  │
├──────────────────────────────────────────────────────────────────┤
│  LAPISAN 2: PEMUAT DATA       src/muat_data.py, src/ambil_harga.py│
│  baca CSV, validasi kategori, unduh dari Yahoo Finance            │
├──────────────────────────────────────────────────────────────────┤
│  LAPISAN 1: DATA              data/*.csv                          │
│  harga harian BTC-USD  +  102 berita besar yang dikurasi manual   │
└──────────────────────────────────────────────────────────────────┘
```

Kenapa dipisah-pisah? Supaya tiap lapisan bisa diganti tanpa merusak yang lain. Mau ganti Bitcoin jadi
Ethereum? Cuma lapisan 1-2 yang berubah. Mau ganti Streamlit jadi website biasa? Cuma lapisan 4.
Lapisan 3 (logika) tidak tahu-menahu soal file atau tampilan, makanya gampang dites.

---

## Langkah 1 — Kenalan sama data harga (pandas)

Buka `data/btc_harga_harian.csv`. Tiap baris = satu hari.

```python
import pandas as pd
df = pd.read_csv("data/btc_harga_harian.csv", parse_dates=["tanggal"])
df.head()
```

| tanggal | open | high | low | close | volume |
|---|---|---|---|---|---|
| 2020-01-01 | 7194.89 | 7254.33 | 7174.94 | 7200.17 | 18565664997 |

`parse_dates=["tanggal"]` penting: tanpa itu kolom tanggal cuma dianggap teks, dan kamu tidak bisa
menghitung selisih hari atau mengelompokkan per tahun.

Coba beberapa hal ini di terminal Python:

```python
df["close"].describe()                 # ringkasan statistik
df.set_index("tanggal")["close"].plot()  # grafik cepat (butuh matplotlib)
df.loc[df["close"].idxmax()]           # hari dengan harga tertinggi sepanjang data
```

### Dari mana datanya? (`src/ambil_harga.py`)

Yahoo Finance punya endpoint publik yang mengembalikan JSON. File ini cuma melakukan tiga hal:
(1) `requests.get(...)` ke URL itu, (2) ambil daftar `timestamp` dan `close` dari JSON-nya,
(3) rapikan ke DataFrame dan simpan CSV. Kalau internet mati, app tetap jalan dari CSV yang sudah ada.
Pola "ambil dari API → simpan snapshot lokal → app baca snapshot" ini sangat umum dan layak dihafal.

---

## Langkah 2 — Konsep inti: return, volatilitas, z-score (`src/deteksi.py`)

### 2a. Return harian

> *"Hari ini harga berubah berapa persen dari kemarin?"*

```python
df["return_pct"] = df["close"].pct_change() * 100
```

`pct_change()` = (nilai sekarang − nilai sebelumnya) / nilai sebelumnya. Hari pertama hasilnya `NaN`
karena tidak ada "kemarin". Itu normal, bukan bug.

### 2b. Volatilitas = "gejolak normal"

> *"Seberapa liar pasar akhir-akhir ini?"*

```python
df["volatilitas_pct"] = df["return_pct"].rolling(30).std().shift(1)
```

Bedah satu per satu:
- `.rolling(30)` → ambil jendela 30 hari yang bergeser maju tiap hari.
- `.std()` → standar deviasi return di jendela itu. Kalau returnnya ±1% tiap hari, std kecil. Kalau ±8%, std besar.
- `.shift(1)` → geser hasilnya satu hari ke depan, supaya volatilitas yang dipakai untuk hari ini
  dihitung dari **30 hari sebelum** hari ini. Kalau tidak di-shift, hari crash besar ikut masuk ke
  "ukuran normal"-nya sendiri dan jadi kelihatan kurang ekstrem. Ini kesalahan klasik yang namanya
  *look-ahead bias*: memakai informasi yang di dunia nyata belum tersedia saat itu.

```
   hari:    1  2  3 ... 30 | 31 | 32
   rolling std dihitung dari hari 1-30 ───┐
   .shift(1) → dipakai untuk hari 31 ─────┘  (hari 31 sendiri TIDAK ikut)
```

### 2c. Z-score

> *"Hari ini gerak berapa kali lipat dari gejolak normal?"*

```python
df["z_score"] = df["return_pct"] / df["volatilitas_pct"]
```

Contoh: volatilitas 30 hari = 2%. Hari ini return −7%. Maka z = −3,5. Artinya "hari ini turun 3,5 kali
lebih besar dari gejolak harian biasa". Kalau return datanya kira-kira berbentuk lonceng (distribusi normal),
|z| ≥ 2,5 itu terjadi sekitar 1% waktu. Return Bitcoin sebenarnya punya "ekor" lebih gemuk dari lonceng
(kejadian ekstrem lebih sering), jadi di data kita hari |z| ≥ 2,5 muncul sekitar 4% hari. Tetap jarang,
tetap layak ditandai.

Kenapa tidak pakai aturan "turun lebih dari 5%" saja? Coba lihat grafik volatilitas di tab Chart:
di 2020–2021 volatilitas harian sering 4–5%, di 2025–2026 sering cuma 1,5–2%. Ambang 5% akan menandai
hampir tiap minggu di 2020 dan hampir tidak pernah di 2025. Z-score menyesuaikan otomatis.

### 2d. Menandai titik

```python
signifikan = df[df["z_score"].abs() >= 2.5]
signifikan["arah"] = np.where(signifikan["return_pct"] > 0, "naik", "turun")
```

`np.where(kondisi, kalau_benar, kalau_salah)` = `if/else` versi satu baris untuk seluruh kolom.

---

## Langkah 3 — Menyambungkan dua tabel lewat tanggal "kira-kira sama"

Tabel titik dan tabel berita sama-sama punya kolom tanggal, tapi tanggalnya sering **selisih satu hari**:
The Fed mengumumkan keputusan pukul 14.00 waktu Washington = 19.00 UTC, dan pasar kripto 24 jam bereaksi
malam itu, yang sebagian masuk ke candle hari berikutnya (candle Yahoo berbasis UTC). Berita akhir pekan
juga sering baru "terasa" di hari Senin.

Jadi kita tidak bisa pakai `merge` biasa yang menuntut tanggal persis sama. Di `cocokkan_berita()`:

```python
for i, baris in titik.iterrows():
    selisih = np.abs((tgl_berita - baris["tanggal"]) / np.timedelta64(1, "D"))  # selisih hari ke SEMUA berita
    idx = selisih.argmin()                                                       # berita paling dekat
    if selisih[idx] <= toleransi_hari:
        ... salin judul, kategori, penjelasan, sumber ...
```

Kalau tidak ada berita dalam toleransi, titiknya dilabeli **"Penyebab belum tercatat"**. Ini keputusan
desain yang disengaja: lebih baik jujur bilang tidak tahu daripada memaksakan berita terdekat yang
sebenarnya seminggu jauhnya.

(Buat yang penasaran: pandas punya `pd.merge_asof()` untuk kasus ini. Latihan 7 mengajak kamu mencobanya.)

---

## Langkah 4 — Tes (`tests/test_deteksi.py`)

Tiap tes polanya sama: **siapkan data kecil yang bisa dihitung di kepala → panggil fungsi → periksa**.

```python
def test_return_harian_sederhana():
    df = deteksi.hitung_return(buat_harga([100, 110, 99]))
    assert df["return_pct"].iloc[1] == pytest.approx(10.0)    # 100 → 110 = +10%
    assert df["return_pct"].iloc[2] == pytest.approx(-10.0)   # 110 → 99  = −10%
```

Tes favorit saya di file itu: `test_volatilitas_tidak_memasukkan_hari_ini`. Dia memastikan `.shift(1)`
benar-benar ada. Kalau suatu hari kamu tidak sengaja menghapus `.shift(1)`, tes itu langsung merah.
Itulah gunanya tes: bukan membuktikan kode benar, tapi **memberi tahu cepat kalau kode jadi salah**.

Jalankan: `python -m pytest tests/ -v`

---

## Langkah 5 — Streamlit: cara berpikir "rerun dari atas"

Streamlit itu unik: **tiap kali kamu menggeser slider atau klik sesuatu, seluruh `app.py` dijalankan ulang
dari baris pertama.** Jadi tidak ada "event handler" seperti di JavaScript. Kamu cukup menulis skrip
dari atas ke bawah, dan Streamlit mengurus sisanya.

```python
ambang_z = st.slider("Ambang z-score", 1.5, 4.0, 2.5)        # 1. baca input
titik = deteksi.deteksi_pergerakan(harga, ambang_z)          # 2. hitung
st.plotly_chart(fig)                                           # 3. tampilkan
```

Geser slider → skrip jalan ulang → `ambang_z` baru → `titik` baru → chart baru. Sesederhana itu.

Dua trik yang dipakai di `app.py`:

- `@st.cache_data` di atas fungsi muat data: supaya CSV tidak dibaca ulang tiap kali slider digeser.
- `st.session_state["chart_utama"]`: Streamlit menyimpan titik mana yang terakhir diklik di sini.
  Karena skrip rerun dari atas, kita bisa **membaca klik sebelum chart digambar**, dan itulah kenapa
  kartu detail bisa muncul *di atas* chart, bukan di bawahnya.

### Anatomi `app.py`

| Bagian | Baris kira-kira | Tugas |
|---|---|---|
| 0. Konfigurasi | atas | `st.set_page_config`, kamus `KATEGORI` (warna + bentuk marker), fungsi `rapikan()` |
| 1. Muat data | `_muat_semua()` | baca dua CSV, di-cache |
| 2. Sidebar | `with st.sidebar:` | slider rentang tanggal, ambang, jendela, toleransi, filter, tombol perbarui |
| 3. Hitung | setelah sidebar | panggil `deteksi.*`, lalu filter sesuai rentang |
| 4. Kartu angka | `st.metric` | harga terakhir, jumlah titik, % terjelaskan, gerakan terbesar |
| 5. Tab | `st.tabs` | chart / daftar / statistik / berita / cara kerja |

---

## Langkah 6 — Plotly: chart yang bisa di-hover dan diklik

Chart utama cuma dua jenis "trace":

```python
fig.add_trace(go.Scatter(x=tanggal, y=close, mode="lines"))              # garis harga
fig.add_trace(go.Scatter(x=tgl_titik, y=close_titik, mode="markers",     # titik per kategori
                         customdata=..., hovertemplate="<b>%{customdata[0]}</b> ..."))
```

Tiga ide yang layak kamu bawa ke project lain:

1. **Satu trace per kategori**, bukan satu trace dengan warna berbeda-beda. Hasilnya legenda bisa diklik
   untuk menyembunyikan satu kategori, dan warnanya konsisten walau difilter.
2. **`customdata`** = data tambahan yang "nebeng" di tiap titik tapi tidak digambar. Hovertemplate
   membacanya dengan `%{customdata[0]}`. Begini caranya tooltip bisa menampilkan judul berita.
3. **`on_select="rerun"`** di `st.plotly_chart` mengubah klik jadi data Python. Tanpa ini, klik cuma
   terjadi di browser dan Python tidak tahu apa-apa.

Soal warna: tiap kategori punya **warna DAN bentuk** (lingkaran, wajik, kotak, segitiga, bintang, silang).
Itu supaya pembaca buta warna tetap bisa membedakan. Garis harga satu warna saja, dan tidak ada sumbu Y ganda,
karena dua sumbu dalam satu chart hampir selalu menyesatkan. Volatilitas digambar di chart terpisah di bawahnya.

---

## Langkah 7 — Kejujuran data (bagian yang bikin project ini beda)

Gampang banget bikin chart yang "membuktikan" apa pun: tinggal pilih berita yang cocok dan abaikan sisanya.
Project ini memasang beberapa rem:

- **Titik abu-abu "belum tercatat"** ditampilkan, bukan disembunyikan. Sekitar seperempat gerakan besar tidak
  punya berita jelas di dataset. Itu informasi penting.
- **Berita yang tidak menggerakkan harga** juga dimasukkan (halving 2024, pemangkasan bunga September 2025),
  supaya kelihatan bahwa pasar sering sudah "menghitung" berita duluan.
- **Tiap baris berita punya link sumber** supaya bisa dicek.
- Tab Cara kerja memuat daftar **keterbatasan**, termasuk kalimat paling penting: korelasi bukan sebab-akibat.

Kebiasaan ini lebih berharga di CV daripada chart yang cantik.

---

## Glosarium cepat

| Istilah | Arti singkat |
|---|---|
| Return | Persen perubahan harga dari periode sebelumnya |
| Volatilitas | Ukuran seberapa liar harga bergerak; di sini = standar deviasi return |
| Standar deviasi (std) | Rata-rata "jarak" data dari rata-ratanya. Kecil = data rapat, besar = data menyebar |
| Z-score | Nilai dibagi standar deviasi: "berapa kali lipat dari normal" |
| Rolling window | Jendela N hari yang bergeser maju tiap hari |
| Look-ahead bias | Memakai informasi yang di dunia nyata belum tersedia saat itu. Dicegah dengan `.shift(1)` |
| Likuidasi | Posisi trader yang pakai utang (leverage) ditutup paksa oleh bursa; mempercepat gerakan harga |
| Priced in | Berita yang sudah diperkirakan pasar sehingga saat diumumkan harga tidak banyak bergerak |
| Hawkish / dovish | Nada bank sentral: hawkish = cenderung mengetat (buruk buat aset berisiko), dovish = melonggarkan |
| FOMC | Rapat The Fed yang memutuskan suku bunga, 8 kali setahun |
| ETF spot | Produk bursa saham yang memegang Bitcoin sungguhan; disetujui SEC Januari 2024 |
| Halving | Hadiah penambang Bitcoin dipotong setengah tiap ~4 tahun |

---

## Setelah ini

1. Kerjakan [LATIHAN.md](LATIHAN.md) dari yang bintang satu.
2. Coba ganti aset: unduh `ETH-USD` dari Yahoo, lihat apakah titik-titiknya jatuh di tanggal yang sama.
3. Ide lanjutan yang masuk akal buat project berikutnya: ambil berita otomatis dari API berita atau RSS,
   lalu pakai model bahasa untuk mengelompokkannya ke lima kategori di sini.
