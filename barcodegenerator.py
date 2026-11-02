import csv
from io import BytesIO
from textwrap import wrap

import barcode
import pandas as pd
import streamlit as st
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


# ===== Helper: bersihkan nilai (hindari "nan") =====
def clean(v) -> str:
    s = "" if v is None else str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def fmt_harga(h) -> str:
    h = clean(h)
    if not h:
        return ""
    try:
        angka = int(round(float(h.replace(",", "."))))
        return "Rp " + f"{angka:,}".replace(",", ".")
    except ValueError:
        return h  # sudah berupa teks (mis. "Rp 129.900"), pakai apa adanya


# ===== PNG untuk mode single / preview =====
def generate_barcode(sku: str, desc: str = "", harga: str = "") -> Image.Image:
    code_class = barcode.get_barcode_class("code128")
    code = code_class(sku, writer=ImageWriter())

    buffer = BytesIO()
    code.write(buffer, options={"write_text": False})
    buffer.seek(0)
    barcode_img = Image.open(buffer)

    width, height = barcode_img.size
    new_img = Image.new("RGB", (width, height + 160), "white")
    new_img.paste(barcode_img, (0, 0))

    draw = ImageDraw.Draw(new_img)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    y = height + 5
    tw = draw.textlength(sku, font=font)
    draw.text(((width - tw) // 2, y), sku, font=font, fill="black")
    y += 25

    if desc:
        for line in wrap(desc, width=max(1, width // 12)):
            tw = draw.textlength(line, font=font)
            draw.text(((width - tw) // 2, y), line, font=font, fill="black")
            y += 20

    if harga:
        line3 = f"Harga: {harga}"
        tw = draw.textlength(line3, font=font)
        draw.text(((width - tw) // 2, y + 5), line3, font=font, fill="black")

    return new_img


# ===== PDF: gambar satu label secara vektor =====
def draw_label(c, x, y, w, h, sku, desc, harga):
    """x,y = pojok kiri-bawah sel; w,h = ukuran sel."""
    pad = 2 * mm
    inner_w = w - 2 * pad
    cx = x + w / 2

    # --- Bar (vektor, tajam & mudah discan) ---
    modules = barcode.get_barcode_class("code128")(sku).build()[0]
    module_w = min(inner_w / len(modules), 0.6 * mm)
    bars_w = module_w * len(modules)
    bars_h = h * 0.40
    bx = cx - bars_w / 2
    by = y + h - pad - bars_h

    c.setFillColorRGB(0, 0, 0)
    i = 0
    while i < len(modules):
        if modules[i] == "1":
            j = i
            while j < len(modules) and modules[j] == "1":
                j += 1
            c.rect(bx + i * module_w, by, (j - i) * module_w, bars_h, stroke=0, fill=1)
            i = j
        else:
            i += 1

    # --- Teks ---
    ty = by - 3.2 * mm
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(cx, ty, sku)
    ty -= 3.2 * mm

    if desc:
        font, size, lead = "Helvetica", 6.5, 7.2
        lines = simpleSplit(desc, font, size, inner_w)
        if len(lines) > 3:
            lines = lines[:3]
            lines[-1] = lines[-1].rstrip()[:-1] + "…"
        c.setFont(font, size)
        for ln in lines:
            c.drawCentredString(cx, ty, ln)
            ty -= lead

    if harga:
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(cx, ty - 0.5 * mm, harga)


# ===== Export PDF =====
def export_pdf(df, num_cols=5, num_rows=8, margin_mm=10, show_grid=False):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    m = margin_mm * mm

    cell_w = (page_w - 2 * m) / num_cols
    cell_h = (page_h - 2 * m) / num_rows
    per_page = num_cols * num_rows

    for n, (_, row) in enumerate(df.iterrows()):
        if n > 0 and n % per_page == 0:
            c.showPage()

        pos = n % per_page
        col, r = pos % num_cols, pos // num_cols
        x = m + col * cell_w
        y = page_h - m - (r + 1) * cell_h

        if show_grid:  # garis bantu potong
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setLineWidth(0.3)
            c.rect(x, y, cell_w, cell_h, stroke=1, fill=0)

        sku = clean(row["SKU"])
        if not sku:
            continue
        draw_label(c, x, y, cell_w, cell_h, sku, clean(row["Description"]), fmt_harga(row["Harga"]))

    c.save()
    buffer.seek(0)
    return buffer


# ===== Streamlit App =====
st.title("🎯 Barcode Generator")

mode = st.radio("Pilih mode:", ["Input SKU Satu per Satu", "Upload CSV"])

# ---- Mode Single Input ----
if mode == "Input SKU Satu per Satu":
    sku = st.text_input("Masukkan SKU (wajib)")
    desc = st.text_input("Masukkan Description (opsional)")
    harga = st.text_input("Masukkan Harga (opsional)")

    if st.button("Generate Barcode"):
        if sku.strip():
            img = generate_barcode(sku.strip(), desc.strip(), fmt_harga(harga))
            st.image(img, caption=f"{sku} {('- ' + desc) if desc else ''}", use_container_width=True)

            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            st.download_button("Download PNG", data=img_buffer.getvalue(), file_name=f"{sku}.png", mime="image/png")
        else:
            st.warning("SKU tidak boleh kosong!")

# ---- Mode CSV ----
else:
    uploaded_file = st.file_uploader("Upload file CSV (harus ada kolom: SKU, Description, Harga)", type=["csv"])
    if uploaded_file is not None:
        sample = uploaded_file.read(2048).decode("utf-8", errors="ignore")
        uploaded_file.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;").delimiter
        except csv.Error:
            delimiter = ","

        # dtype=str -> SKU tidak berubah jadi angka (nol di depan aman), kosong = ""
        df = pd.read_csv(uploaded_file, delimiter=delimiter, dtype=str, keep_default_na=False)
        df.columns = [col.strip() for col in df.columns]

        required_cols = ["SKU", "Description", "Harga"]
        if not all(col in df.columns for col in required_cols):
            st.error(f"CSV harus berisi kolom: {', '.join(required_cols)}")
        else:
            st.success(f"Data berhasil dimuat ✅ ({len(df)} baris)")
            st.dataframe(df.head())

            if st.button("Preview Barcode dari CSV"):
                for _, row in df.head(20).iterrows():
                    img = generate_barcode(clean(row["SKU"]), clean(row["Description"]), fmt_harga(row["Harga"]))
                    st.image(img, use_container_width=True)
                if len(df) > 20:
                    st.caption("Preview dibatasi 20 baris pertama.")

            with st.expander("⚙️ Pengaturan PDF", expanded=False):
                c1, c2, c3 = st.columns(3)
                num_cols = c1.number_input("Kolom per halaman", 2, 8, 5)
                num_rows = c2.number_input("Baris per halaman", 3, 15, 8)
                margin_mm = c3.number_input("Margin (mm)", 5, 25, 10)
                show_grid = st.checkbox("Tampilkan garis bantu potong", value=False)

            if st.button("Export semua ke PDF"):
                with st.spinner("Membuat PDF..."):
                    st.session_state["pdf_bytes"] = export_pdf(
                        df, int(num_cols), int(num_rows), int(margin_mm), show_grid
                    ).getvalue()

            if "pdf_bytes" in st.session_state:
                st.download_button(
                    "Download PDF",
                    data=st.session_state["pdf_bytes"],
                    file_name="barcodes.pdf",
                    mime="application/pdf",
                )

st.caption("Fuad EDP399")
