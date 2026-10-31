# 🏋️ Latihan

Urut dari yang paling gampang. Bintang = tingkat kesulitan. Tiap latihan punya petunjuk dan cara
mengecek apakah jawabanmu benar. Kerjakan di branch baru (`git checkout -b latihan-1`) supaya kalau
rusak tinggal balik.

---

### Latihan 1 — Lengkapi titik abu-abu (edit CSV saja) ⭐

Buka app, pilih rentang 2023 saja, dan cari titik abu-abu **"Penyebab belum tercatat"**. Ada beberapa, misalnya
**15 Februari 2023 (+9,4%)** dan **17 Maret 2023 (+9,5%)**.

1. Cari di Google: `bitcoin price february 15 2023` dan baca 2–3 sumber berbeda.
2. Tambahkan satu baris di `data/berita_besar.csv`:
   ```
   2023-02-15,<judul singkat>,<kategori>,<penjelasan 1-2 kalimat>,<link>
   ```
   Kategori harus salah satu dari: `trump_politik_as`, `the_fed_makro`, `geopolitik`, `regulasi`, `kripto_internal`.
   Kalau salah ketik, app akan berhenti dengan pesan error yang menyebutkan kategori yang salah (sengaja).
3. Refresh app. Titiknya harus berubah warna dan angka "Punya penjelasan berita" naik.

**Cek:** `python -m pytest tests/ -v` tetap hijau. Kalau penjelasanmu mengandung koma, bungkus dengan tanda kutip
`"..."` seperti baris lain.

---

### Latihan 2 — Ganti ambang default ⭐

Di `src/deteksi.py` ada `AMBANG_Z_DEFAULT = 2.5`. Ubah jadi `3.0`, jalankan tes dan buka app.

Perhatikan dua hal: jumlah titik turun drastis, dan angka "Punya penjelasan berita" berubah. Tulis di komentar
atas konstanta itu: ambang berapa yang menurutmu paling pas, dan kenapa. Pelajaran: mengubah satu angka default
bisa mengubah "cerita" seluruh dashboard, jadi angka itu harus bisa dipertanggungjawabkan.

---

### Latihan 3 — Kolom baru: "berapa hari sampai pulih?" ⭐⭐

Untuk tiap titik **turun**, hitung berapa hari sampai harga penutupan kembali ke level sebelum jatuh.

1. Di `src/deteksi.py`, buat fungsi `hari_pemulihan(harga: pd.DataFrame, tanggal_jatuh) -> int | None`.
   Petunjuk: ambil `close` sehari sebelum jatuh, lalu cari baris pertama setelah tanggal itu yang `close`-nya
   ≥ nilai tadi. Kembalikan selisih harinya, atau `None` kalau belum pulih sampai akhir data.
2. Tulis tesnya dulu dengan data mini: `[100, 90, 95, 101]` → jatuh di hari ke-2, pulih di hari ke-4 → 2 hari.
3. Tampilkan sebagai kolom di tab **Daftar titik**.

Pertanyaan refleksi: crash mana yang paling lama pulihnya, dan apa kategorinya?

---

### Latihan 4 — Grafik: rata-rata return per hari dalam seminggu ⭐⭐

Mitos di komunitas kripto: "harga sering jatuh di akhir pekan karena likuiditas tipis". Cek sendiri.

```python
harga["hari"] = harga["tanggal"].dt.day_name()
rata = harga.groupby("hari")["return_pct"].mean()
```

Buat bar chart di tab Statistik. Urutkan Senin→Minggu (petunjuk: `.reindex([...])`), beri warna satu hue saja
karena ini satu ukuran, bukan kategori. Apakah mitosnya benar di data 2020–2026?

---

### Latihan 5 — Fungsi baru + tes: "berita tanpa reaksi" ⭐⭐

Tab **Semua berita** sudah menampilkan reaksi harga di tiap tanggal berita. Buat fungsi
`berita_tanpa_reaksi(berita, harga_lengkap, ambang_z=1.0)` yang mengembalikan berita yang |z-score| hari itu
di bawah ambang. Tampilkan jumlahnya sebagai `st.metric` di tab itu.

Tulis dua tes: satu untuk berita yang jelas bereaksi (12 Maret 2020) harus *tidak* masuk daftar, satu untuk
berita yang diperkirakan datar (17 September 2025, pemangkasan bunga yang sudah diperkirakan) harus masuk.

---

### Latihan 6 — Zoom otomatis ke titik yang diklik ⭐⭐⭐

Saat titik diklik, rentang chart tetap. Buat supaya ada tombol **"Zoom ±30 hari"** di kartu detail yang
mengubah slider rentang tanggal.

Petunjuk: beri slider di sidebar `key="rentang"`; Streamlit mengizinkan mengubah `st.session_state["rentang"]`
*sebelum* widget-nya digambar. Karena skrip rerun dari atas, kamu perlu menyimpan permintaan zoom di
`st.session_state` lalu memprosesnya di bagian paling atas skrip. Ini latihan terbaik untuk benar-benar paham
model "rerun dari atas" Streamlit.

---

### Latihan 7 — Ganti loop dengan `pd.merge_asof` ⭐⭐⭐

`cocokkan_berita()` memakai `for` loop. Untuk 100 titik itu cepat, tapi pandas punya fungsi khusus untuk
"gabungkan berdasarkan kunci terdekat": `pd.merge_asof(..., direction="nearest", tolerance=pd.Timedelta(days=1))`.

Tulis ulang fungsinya dengan `merge_asof` **tanpa mengubah tesnya**. Kalau semua tes tetap hijau, kamu baru saja
melakukan *refactoring* yang aman. Bandingkan kecepatannya dengan `%timeit` di notebook untuk 100.000 baris palsu.

---

### Latihan 8 — Aset kedua: Ethereum ⭐⭐⭐

1. Tambahkan parameter `simbol` di `ambil_harga_yahoo()` (default `"BTC-USD"`), lalu unduh `ETH-USD` ke
   `data/eth_harga_harian.csv`.
2. Tambahkan `st.selectbox("Aset", ["BTC", "ETH"])` di sidebar yang menentukan CSV mana yang dimuat.
3. Pertanyaan risetnya: apakah titik-titik ETH jatuh di tanggal yang sama dengan BTC? Hitung berapa persen
   tanggal signifikan yang sama-sama muncul di keduanya.

Kalau mau lebih jauh: tampilkan keduanya di satu chart dengan **indeks** (harga dibagi harga hari pertama × 100)
supaya skalanya sebanding, bukan dengan dua sumbu Y.

---

### Latihan 9 — Mini riset (tanpa kode) ⭐⭐⭐

Pilih 5 titik yang sudah punya berita dan cari **sumber kedua** untuk masing-masing. Catat di
`data/SUMBER_DATA.md`: apakah kedua sumber setuju soal penyebabnya? Minimal satu dari lima biasanya akan
punya penjelasan berbeda. Tulis satu paragraf: bagaimana kamu memutuskan penyebab "utama" ketika sumber tidak sepakat?

Ini latihan paling penting, karena dataset berita di project ini adalah bagian yang paling subjektif.

---

## Sudah selesai semua?

Push ke GitHub, perbarui bagian "Temuan menarik" di README dengan angka terbarumu, lalu lanjut ke project
berikutnya. Ide yang nyambung: ambil berita otomatis dari RSS/API dan klasifikasikan ke lima kategori ini
secara otomatis, supaya dataset tidak perlu dikurasi tangan lagi.
