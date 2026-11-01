"""
app.py - Bitcoin vs Berita Dunia
=================================
Jalankan dengan:   streamlit run app.py

Alur besar file ini (baca dari atas ke bawah):
  1. Import + konfigurasi halaman + warna
  2. Muat data (harga BTC + berita) dengan cache
  3. Sidebar: rentang tanggal, ambang deteksi, filter kategori
  4. Deteksi pergerakan signifikan -> cocokkan dengan berita
  5. Tampilkan: kartu angka -> tab chart / daftar titik / statistik / berita / cara kerja

Catatan gaya: tiap bagian punya komentar "APA" dan "KENAPA". Istilah asing?
Cek docs/BELAJAR.md.
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import deteksi
from src.ambil_harga import perbarui_csv
from src.muat_data import muat_berita, muat_harga

# ----------------------------------------------------------------------------
# 0. KONFIGURASI HALAMAN & WARNA
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Bitcoin vs Berita Dunia", page_icon="₿", layout="wide")

# Satu kategori = satu warna + satu bentuk marker. Urutannya TETAP supaya warna
# tidak berubah saat kategori difilter. Bentuk marker membantu pembaca buta warna.
KATEGORI = {
    "trump_politik_as": {"label": "Trump & politik AS", "warna": "#eb6834", "simbol": "circle"},
    "the_fed_makro":    {"label": "The Fed & makroekonomi", "warna": "#1baf7a", "simbol": "diamond"},
    "geopolitik":       {"label": "Geopolitik", "warna": "#eda100", "simbol": "square"},
    "regulasi":         {"label": "Regulasi kripto", "warna": "#e87ba4", "simbol": "triangle-up"},
    "kripto_internal":  {"label": "Internal kripto (bursa, ETF, halving)", "warna": "#6250d6", "simbol": "star"},
    "belum tercatat":   {"label": "Penyebab belum tercatat", "warna": "#9a9892", "simbol": "x"},
}
WARNA_HARGA = "#2a78d6"
WARNA_NAIK, WARNA_TURUN = "#1baf7a", "#e34948"
TEMPLATE = "plotly_white"


def rapikan(fig: go.Figure, tinggi: int = 420) -> go.Figure:
    """Gaya seragam semua grafik: grid tipis, margin kecil, legenda di atas."""
    fig.update_layout(
        template=TEMPLATE,
        height=tinggi,
        margin=dict(l=10, r=20, t=70, b=10),
        title=dict(y=0.98, yanchor="top", x=0, xanchor="left", font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#eceae5", zeroline=False)
    return fig


def label_kategori(k: str) -> str:
    return KATEGORI.get(k, KATEGORI["belum tercatat"])["label"]


def format_usd(x: float) -> str:
    return f"${x:,.0f}"


# ----------------------------------------------------------------------------
# 1. MUAT DATA (dengan cache supaya tidak baca CSV tiap klik)
# ----------------------------------------------------------------------------
@st.cache_data
def _muat_semua():
    return muat_harga(), muat_berita()


harga_semua, berita_semua = _muat_semua()

# ----------------------------------------------------------------------------
# 2. SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Pengaturan")

    tgl_min, tgl_maks = harga_semua["tanggal"].min().date(), harga_semua["tanggal"].max().date()
    rentang = st.slider(
        "Rentang tanggal",
        min_value=tgl_min, max_value=tgl_maks,
        value=(date(2024, 1, 1), tgl_maks),
        format="MMM YYYY",
        help="Geser untuk zoom ke periode tertentu. Deteksi tetap dihitung dari seluruh data.",
    )

    st.subheader("Detection")
    ambang_z = st.slider(
        "Ambang z-score |z| ≥", 1.5, 4.0, deteksi.AMBANG_Z_DEFAULT, 0.1,
        help="Berapa kali lipat dari gejolak normal supaya sebuah hari dianggap signifikan. "
             "Makin kecil, makin banyak titik.",
    )
    jendela = st.slider(
        "Jendela volatilitas (hari)", 10, 90, deteksi.JENDELA_DEFAULT, 5,
        help="Berapa hari ke belakang untuk mengukur 'gejolak normal'.",
    )
    toleransi = st.slider(
        "Toleransi tanggal berita (± hari)", 0, 3, deteksi.TOLERANSI_HARI_DEFAULT,
        help="Berita boleh selisih berapa hari dari tanggal pergerakan. Pasar kripto 24 jam, "
             "berita malam di AS sering baru terlihat di candle esok hari (UTC).",
    )

    st.subheader("Display")
    kategori_pilih = st.multiselect(
        "Kategori penyebab",
        options=list(KATEGORI.keys()),
        default=list(KATEGORI.keys()),
        format_func=label_kategori,
    )
    skala_log = st.toggle("Log scale", value=False,
                          help="Berguna kalau rentang panjang: kenaikan 7k→70k kelihatan proporsional.")
    mode_belajar = st.toggle("🎓 Learning mode", value=False,
                             help="Tampilkan penjelasan rumus + kode di bawah tiap grafik.")

    st.divider()
    if st.button("🔄 Update harga dari Yahoo Finance", use_container_width=True):
        try:
            with st.spinner("Mengambil harga..."):
                baru = perbarui_csv()
            st.cache_data.clear()
            st.success(f"Berhasil: {len(baru)} hari, terakhir {baru['tanggal'].max().date()}")
            st.rerun()
        except Exception as e:  # noqa: BLE001 - tampilkan apa pun errornya ke pengguna
            st.error(f"Gagal update ({type(e).__name__}). App tetap pakai CSV lokal.")
    st.caption(f"Data harga: {tgl_min} → {tgl_maks} ({len(harga_semua):,} hari). "
               f"Berita: {len(berita_semua)} peristiwa.")

# ----------------------------------------------------------------------------
# 3. HITUNG: deteksi -> cocokkan berita -> filter
# ----------------------------------------------------------------------------
harga_lengkap = deteksi.hitung_z_score(harga_semua, jendela)          # semua hari + kolom z_score
titik_semua = deteksi.deteksi_pergerakan(harga_semua, ambang_z, jendela)
titik_semua = deteksi.cocokkan_berita(titik_semua, berita_semua, toleransi)

mulai, akhir = pd.Timestamp(rentang[0]), pd.Timestamp(rentang[1])
harga = harga_lengkap[(harga_lengkap["tanggal"] >= mulai) & (harga_lengkap["tanggal"] <= akhir)]
titik = titik_semua[
    (titik_semua["tanggal"] >= mulai) & (titik_semua["tanggal"] <= akhir)
    & (titik_semua["kategori"].isin(kategori_pilih))
].reset_index(drop=True)
berita = berita_semua[(berita_semua["tanggal"] >= mulai) & (berita_semua["tanggal"] <= akhir)]

# ----------------------------------------------------------------------------
# 4. JUDUL + KARTU ANGKA
# ----------------------------------------------------------------------------
st.title("₿ Bitcoin vs Berita Dunia")
st.markdown(
    "Chart harga Bitcoin dengan **titik otomatis** di hari-hari pergerakan ekstrem. "
    "Arahkan kursor ke titik untuk melihat berita besarnya; **klik** titik untuk detail dan sumber. "
    "Titik abu-abu = pergerakan besar yang penyebabnya belum tercatat di dataset."
)

ring = deteksi.ringkasan(titik)
terakhir = harga_semua.iloc[-1]
sebelum = harga_semua.iloc[-2]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Harga terakhir", format_usd(terakhir["close"]),
          f"{(terakhir['close'] / sebelum['close'] - 1) * 100:+.2f}% vs kemarin")
k2.metric("Titik signifikan (rentang ini)", ring["total"], f"{ring['naik']} naik · {ring['turun']} turun",
          delta_color="off")
k3.metric("Punya penjelasan berita", f"{ring['persen_terjelaskan']:.0f}%",
          f"{ring['terjelaskan']} dari {ring['total']}", delta_color="off")
if not titik.empty:
    ekstrem = titik.loc[titik["return_pct"].abs().idxmax()]
    k4.metric("Gerakan terbesar", f"{ekstrem['return_pct']:+.1f}%",
              f"{ekstrem['tanggal'].date()} · {ekstrem['judul'][:40]}", delta_color="off")
else:
    k4.metric("Gerakan terbesar", "—")

tab_chart, tab_daftar, tab_stat, tab_berita, tab_cara = st.tabs(
    ["📈 Chart", "📋 Flagged days", "📊 Stats", "📰 All news", "🧭 How it works"]
)

# ----------------------------------------------------------------------------
# 5A. TAB CHART: garis harga + titik berwarna per kategori
# ----------------------------------------------------------------------------
with tab_chart:
    # ---- Kartu detail titik yang diklik (dibaca dari state widget chart di bawah) ----
    # Streamlit menyimpan hasil klik di st.session_state["chart_utama"], jadi kita bisa
    # menampilkan kartunya DI ATAS chart supaya langsung terlihat tanpa scroll.
    dipilih = None
    state = st.session_state.get("chart_utama")
    poin = state.selection.points if state and state.selection else []
    poin_titik = [p for p in poin if p.get("customdata")]
    if poin_titik:
        tgl_klik = pd.Timestamp(poin_titik[0]["x"]).normalize()
        cocok = titik[titik["tanggal"] == tgl_klik]
        dipilih = cocok.iloc[0] if not cocok.empty else None

    if dipilih is None:
        st.info("👆 Klik salah satu titik di chart untuk membaca penyebabnya. "
                "Atau pakai tab **Flagged days** untuk memilih dari tabel.")
    else:
        warna = KATEGORI.get(dipilih["kategori"], KATEGORI["belum tercatat"])["warna"]
        arah_ikon = "📈" if dipilih["arah"] == "naik" else "📉"
        with st.container(border=True):
            st.markdown(
                f"<span style='background:{warna};color:white;padding:2px 10px;border-radius:12px;"
                f"font-size:0.85em'>{label_kategori(dipilih['kategori'])}</span>",
                unsafe_allow_html=True,
            )
            st.subheader(f"{arah_ikon} {dipilih['judul']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tanggal", f"{dipilih['tanggal']:%d %b %Y}")
            c2.metric("Return harian", f"{dipilih['return_pct']:+.2f}%")
            c3.metric("Z-score", f"{dipilih['z_score']:+.1f}",
                      help="Gerak hari itu dibagi volatilitas 'normal' periode sebelumnya")
            c4.metric("Harga tutup", format_usd(dipilih["close"]))
            st.write(dipilih["penjelasan"])
            if dipilih["sumber_url"]:
                st.markdown(f"🔗 Sumber: [{dipilih['sumber_url'][:70]}...]({dipilih['sumber_url']})")
            if dipilih["selisih_hari"] and int(dipilih["selisih_hari"]) > 0:
                st.caption(f"Catatan: tanggal berita selisih {int(dipilih['selisih_hari'])} hari "
                           f"dari tanggal pergerakan (beda zona waktu / reaksi pasar tertunda).")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=harga["tanggal"], y=harga["close"], mode="lines", name="Harga penutupan (USD)",
        line=dict(color=WARNA_HARGA, width=2),
        hoverinfo="skip",   # hover garis dimatikan supaya tidak "merebut" tooltip dari titik di atasnya
    ))
    # Satu trace per kategori supaya legendanya bisa diklik untuk sembunyi/tampil.
    for kode, gaya in KATEGORI.items():
        sub = titik[titik["kategori"] == kode]
        if sub.empty:
            continue
        ukuran = 9 + sub["z_score"].abs().clip(upper=8) * 1.3   # makin ekstrem makin besar, min 9px
        fig.add_trace(go.Scatter(
            x=sub["tanggal"], y=sub["close"], mode="markers", name=gaya["label"],
            marker=dict(color=gaya["warna"], size=ukuran, symbol=gaya["simbol"],
                        line=dict(color="white", width=2)),
            customdata=sub[["judul", "return_pct", "z_score", "kategori"]].assign(
                kategori=lambda d: d["kategori"].map(label_kategori)).to_numpy(),
            selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=0.55)),
            hovertemplate="<b>%{customdata[0]}</b><br>%{x|%d %b %Y} · %{customdata[3]}"
                          "<br>Close %{y:$,.0f} · Return <b>%{customdata[1]:+.1f}%</b> (z = %{customdata[2]:.1f})"
                          "<br><i>Klik titik untuk detail & sumber</i><extra></extra>",
        ))
    fig.update_yaxes(title="Harga BTC (USD)", type="log" if skala_log else "linear", tickprefix="$")
    rapikan(fig, tinggi=520)
    fig.update_layout(title=f"Harga Bitcoin {rentang[0]:%b %Y} – {rentang[1]:%b %Y}, "
                            f"{len(titik)} titik signifikan (|z| ≥ {ambang_z})",
                      hovermode="closest", dragmode="pan",
                      legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0),
                      margin=dict(l=10, r=20, t=50, b=10))
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, spikecolor="#c3c2b7",
                     spikedash="solid", spikesnap="data")

    st.plotly_chart(fig, use_container_width=True, on_select="rerun",
                    selection_mode="points", key="chart_utama")

    # ---- Grafik kedua: volatilitas (BUKAN sumbu ganda, sengaja dipisah) ----
    st.markdown("#### Gejolak pasar dari waktu ke waktu")
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(
        x=harga["tanggal"], y=harga["volatilitas_pct"], mode="lines",
        name=f"Volatilitas {jendela} hari (std return, %)", line=dict(color=WARNA_HARGA, width=2),
        fill="tozeroy", fillcolor="rgba(42,120,214,0.10)",
        hovertemplate="%{x|%d %b %Y}<br>Volatilitas %{y:.2f}%<extra></extra>",
    ))
    fig_vol.update_yaxes(title="Std return harian (%)", ticksuffix="%")
    rapikan(fig_vol, tinggi=260)
    fig_vol.update_layout(title=f"Volatilitas bergulir {jendela} hari: 'ukuran normal' yang jadi pembagi z-score",
                          showlegend=False)
    st.plotly_chart(fig_vol, use_container_width=True)

    if mode_belajar:
        with st.expander("🎓 Learning mode: bagaimana titik-titik ini ditemukan?", expanded=True):
            st.markdown(
                r"""
**Langkah 1. Return harian** = seberapa persen harga berubah dari kemarin.

$$r_t = \frac{close_t - close_{t-1}}{close_{t-1}} \times 100$$

**Langkah 2. Volatilitas** = standar deviasi return selama N hari *sebelum* hari ini.
Ini "ukuran gejolak normal" pasar saat itu.

**Langkah 3. Z-score** = return hari ini dibagi volatilitas: *"hari ini gerak berapa kali lipat dari biasanya?"*

$$z_t = \frac{r_t}{\sigma_{t-1,\,N}}$$

**Langkah 4.** Kalau $|z_t| \ge$ ambang (slider di kiri), hari itu jadi titik di chart.

Kenapa tidak pakai aturan "turun lebih dari 5%" saja? Karena 5% di 2020 (pasar sangat bergejolak) itu biasa,
sedangkan 5% di 2025 itu kejadian besar. Lihat grafik volatilitas di atas: tingginya beda jauh antar tahun.
Z-score otomatis menyesuaikan.

```python
# src/deteksi.py (inti)
df["return_pct"]      = df["close"].pct_change() * 100
df["volatilitas_pct"] = df["return_pct"].rolling(jendela).std().shift(1)   # .shift(1) = pakai data SEBELUM hari ini
df["z_score"]         = df["return_pct"] / df["volatilitas_pct"]
signifikan = df[df["z_score"].abs() >= ambang_z]
```

**Langkah 5. Cocokkan dengan berita.** Untuk tiap titik, cari berita di `data/berita_besar.csv`
yang tanggalnya paling dekat. Kalau selisihnya ≤ toleransi (default 1 hari) → itu "penyebabnya".
Kalau tidak ada → ditandai abu-abu "belum tercatat". **Kita tidak mengarang penyebab.**
                """
            )

# ----------------------------------------------------------------------------
# 5B. TAB DAFTAR TITIK
# ----------------------------------------------------------------------------
with tab_daftar:
    st.markdown(f"**{len(titik)} pergerakan signifikan** di rentang {rentang[0]} – {rentang[1]}. "
                "Urutkan dengan klik judul kolom.")
    if titik.empty:
        st.warning("Tidak ada titik di rentang/kategori ini. Coba turunkan ambang z-score.")
    else:
        tampil = titik[["tanggal", "close", "return_pct", "z_score", "kategori", "judul", "sumber_url"]].copy()
        tampil["kategori"] = tampil["kategori"].map(label_kategori)
        st.dataframe(
            tampil.sort_values("tanggal", ascending=False),
            use_container_width=True, hide_index=True, height=420,
            column_config={
                "tanggal": st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"),
                "close": st.column_config.NumberColumn("Close (USD)", format="$%,.0f"),
                "return_pct": st.column_config.NumberColumn("Return", format="%+.1f%%"),
                "z_score": st.column_config.NumberColumn("Z-score", format="%+.1f"),
                "kategori": "Kategori",
                "judul": st.column_config.TextColumn("Penyebab (berita)", width="large"),
                "sumber_url": st.column_config.LinkColumn("Sumber", display_text="buka"),
            },
        )
        st.download_button("⬇️ Download tabel ini (CSV)", tampil.to_csv(index=False).encode(),
                           "titik_signifikan.csv", "text/csv")

        st.markdown("#### Baca detail satu titik")
        opsi = {f"{r.tanggal:%d %b %Y}  ·  {r.return_pct:+.1f}%  ·  {r.judul}": i
                for i, r in titik.sort_values("tanggal", ascending=False).iterrows()}
        pilihan = st.selectbox("Pilih tanggal", list(opsi.keys()))
        d = titik.loc[opsi[pilihan]]
        with st.container(border=True):
            st.markdown(f"**{label_kategori(d['kategori'])}** · {d['tanggal']:%d %B %Y} · "
                        f"return **{d['return_pct']:+.2f}%** (z = {d['z_score']:+.1f})")
            st.write(d["penjelasan"])
            if d["sumber_url"]:
                st.markdown(f"🔗 [{d['sumber_url']}]({d['sumber_url']})")

# ----------------------------------------------------------------------------
# 5C. TAB STATISTIK
# ----------------------------------------------------------------------------
with tab_stat:
    if titik.empty:
        st.warning("Tidak ada titik untuk dihitung.")
    else:
        kol1, kol2 = st.columns(2)

        # Berapa titik per kategori? (urutan & warna tetap mengikuti KATEGORI)
        hitung = titik["kategori"].value_counts().reindex(list(KATEGORI.keys())).dropna()
        fig_kat = go.Figure(go.Bar(
            x=hitung.values, y=[label_kategori(k) for k in hitung.index], orientation="h",
            marker=dict(color=[KATEGORI[k]["warna"] for k in hitung.index], cornerradius=4),
            text=hitung.values, textposition="outside",
            hovertemplate="%{y}: %{x} titik<extra></extra>",
        ))
        fig_kat.update_yaxes(autorange="reversed")
        fig_kat.update_xaxes(range=[0, hitung.max() * 1.25], title="Jumlah titik signifikan")
        rapikan(fig_kat, 360)
        fig_kat.update_layout(title="Penyebab apa yang paling sering membuat BTC bergejolak?", showlegend=False)
        kol1.plotly_chart(fig_kat, use_container_width=True)

        # Rata-rata besar gerakan per kategori (nilai mutlak)
        rata = titik.groupby("kategori")["return_pct"].agg(lambda s: s.abs().mean()).reindex(hitung.index)
        fig_rata = go.Figure(go.Bar(
            x=rata.values, y=[label_kategori(k) for k in rata.index], orientation="h",
            marker=dict(color=[KATEGORI[k]["warna"] for k in rata.index], cornerradius=4),
            text=[f"{v:.1f}%" for v in rata.values], textposition="outside",
            hovertemplate="%{y}: rata-rata |return| %{x:.1f}%<extra></extra>",
        ))
        fig_rata.update_yaxes(autorange="reversed")
        fig_rata.update_xaxes(range=[0, rata.max() * 1.25], title="Rata-rata |return| harian (%)")
        rapikan(fig_rata, 360)
        fig_rata.update_layout(title="Kategori mana yang gerakannya paling besar?", showlegend=False)
        kol2.plotly_chart(fig_rata, use_container_width=True)

        # 15 berita dengan reaksi harga terbesar (naik = hijau, turun = merah)
        top = titik.reindex(titik["return_pct"].abs().sort_values(ascending=False).index).head(15)
        top = top[top["kategori"] != "belum tercatat"]
        fig_top = go.Figure(go.Bar(
            x=top["return_pct"], y=[f"{t:%d %b %Y} · {j[:48]}" for t, j in zip(top["tanggal"], top["judul"])],
            orientation="h",
            marker=dict(color=[WARNA_NAIK if v > 0 else WARNA_TURUN for v in top["return_pct"]], cornerradius=4),
            text=[f"{v:+.1f}%" for v in top["return_pct"]], textposition="outside",
            customdata=top["kategori"].map(label_kategori),
            hovertemplate="%{y}<br>Return %{x:+.1f}%<br>%{customdata}<extra></extra>",
        ))
        fig_top.update_yaxes(autorange="reversed", tickfont=dict(size=11))
        batas = top["return_pct"].abs().max() * 1.3
        fig_top.update_xaxes(range=[-batas, batas], title="Return harian (%)", ticksuffix="%", zeroline=True,
                             zerolinecolor="#c3c2b7")
        rapikan(fig_top, 520)
        fig_top.update_layout(title="Berita mana yang reaksinya paling besar? (hijau naik, merah turun)",
                              showlegend=False, margin=dict(l=10, r=20, t=70, b=10))
        st.plotly_chart(fig_top, use_container_width=True)

        # Titik per tahun
        per_tahun = titik.groupby(titik["tanggal"].dt.year).size()
        fig_thn = go.Figure(go.Bar(
            x=per_tahun.index.astype(str), y=per_tahun.values,
            marker=dict(color=WARNA_HARGA, cornerradius=4), text=per_tahun.values, textposition="outside",
            hovertemplate="%{x}: %{y} titik<extra></extra>",
        ))
        fig_thn.update_yaxes(range=[0, per_tahun.max() * 1.25], title="Jumlah titik")
        rapikan(fig_thn, 300)
        fig_thn.update_layout(title="Berapa hari ekstrem per tahun? (ambang z-score menyesuaikan gejolak, "
                                    "jadi angkanya bisa dibandingkan antar tahun)", showlegend=False)
        st.plotly_chart(fig_thn, use_container_width=True)

        if mode_belajar:
            with st.expander("🎓 Learning mode: groupby dalam satu baris", expanded=True):
                st.code(
                    'hitung = titik["kategori"].value_counts()                     # berapa titik per kategori\n'
                    'rata   = titik.groupby("kategori")["return_pct"].agg(lambda s: s.abs().mean())\n'
                    'per_tahun = titik.groupby(titik["tanggal"].dt.year).size()   # .dt.year ambil tahunnya saja',
                    language="python",
                )
                st.markdown("Hati-hati menafsirkan: **korelasi bukan sebab-akibat**. Berita yang kita pasangkan "
                            "adalah *penjelasan yang paling masuk akal*, bukan bukti. Baca bagian 'Keterbatasan' "
                            "di tab How it works.")

# ----------------------------------------------------------------------------
# 5D. TAB SEMUA BERITA
# ----------------------------------------------------------------------------
with tab_berita:
    st.markdown(f"**{len(berita)} peristiwa** di rentang ini, dari total {len(berita_semua)} di "
                "`data/berita_besar.csv`. Kolom *reaksi* = return BTC di hari itu (apa pun besarnya).")
    reaksi = harga_lengkap.set_index("tanggal")["return_pct"]
    tampil_b = berita.copy()
    tampil_b["reaksi_pct"] = tampil_b["tanggal"].map(reaksi)
    tampil_b["kategori"] = tampil_b["kategori"].map(label_kategori)
    st.dataframe(
        tampil_b[["tanggal", "kategori", "judul", "reaksi_pct", "penjelasan", "sumber_url"]]
        .sort_values("tanggal", ascending=False),
        use_container_width=True, hide_index=True, height=520,
        column_config={
            "tanggal": st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"),
            "kategori": "Kategori",
            "judul": st.column_config.TextColumn("Peristiwa", width="medium"),
            "reaksi_pct": st.column_config.NumberColumn("Reaksi BTC", format="%+.1f%%"),
            "penjelasan": st.column_config.TextColumn("Penjelasan", width="large"),
            "sumber_url": st.column_config.LinkColumn("Sumber", display_text="buka"),
        },
    )
    st.caption("Mau menambah berita? Edit CSV-nya saja, tidak perlu sentuh kode. Lihat docs/LATIHAN.md.")

# ----------------------------------------------------------------------------
# 5E. TAB CARA KERJA
# ----------------------------------------------------------------------------
with tab_cara:
    st.graphviz_chart(
        f"""
        digraph {{
          rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
          yahoo [label="Yahoo Finance\\n(BTC-USD harian)", fillcolor="#cde2fb"];
          csvh  [label="data/btc_harga_harian.csv", fillcolor="#cde2fb"];
          csvb  [label="data/berita_besar.csv\\n(disusun manual, {len(berita_semua)} peristiwa)", fillcolor="#fde3d8"];
          det   [label="src/deteksi.py\\nreturn → volatilitas → z-score", fillcolor="#f0efec"];
          coc   [label="cocokkan_berita()\\n±1 hari", fillcolor="#f0efec"];
          app   [label="app.py (Streamlit + Plotly)\\nchart + titik + detail", fillcolor="#d9f3e9"];
          yahoo -> csvh [label="src/ambil_harga.py"]; csvh -> det -> coc -> app; csvb -> coc;
        }}
        """
    )
    st.markdown(
        """
### Sumber data
- **Harga**: Yahoo Finance `BTC-USD`, harga penutupan harian (UTC) sejak 1 Jan 2020. Gratis, tanpa API key.
  Snapshot disimpan di `data/btc_harga_harian.csv`; tombol di sidebar memperbaruinya.
- **Berita**: disusun manual di `data/berita_besar.csv` dari berita arus utama (Reuters, CNBC, Bloomberg,
  CoinDesk), rilis resmi (The Fed, SEC, BLS), dan Wikipedia untuk peristiwa besar. Tiap baris punya link sumber.

### Keterbatasan (penting dibaca)
1. **Korelasi ≠ sebab-akibat.** Berita yang berdekatan tanggalnya *kemungkinan* penyebab, bukan bukti.
   Sering ada beberapa faktor sekaligus (makro + likuidasi + sentimen).
2. **Pemilihan berita subjektif.** Dataset dikurasi satu orang dan bisa bias ke berita yang "terkenal".
   Titik abu-abu menunjukkan ada pergerakan besar yang belum ada catatannya.
3. **Harga harian menyembunyikan intraday.** Crash yang terjadi dan pulih dalam hari yang sama (flash crash)
   bisa tidak terdeteksi.
4. **Zona waktu.** Candle harian Yahoo berbasis UTC; berita sore hari AS masuk ke candle hari berikutnya.
   Karena itu ada toleransi ±1 hari.
5. **Bukan saran investasi.** Ini proyek belajar analisis data.
        """
    )
