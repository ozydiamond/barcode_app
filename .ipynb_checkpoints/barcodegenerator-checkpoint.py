import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# ===== Utility: Generate barcode image =====
def generate_barcode(sku: str, desc: str = "", harga: str = "") -> Image.Image:
    code_class = barcode.get_barcode_class("code128")
    code = code_class(sku, writer=ImageWriter())

    buffer = BytesIO()
    code.write(buffer, options={"write_text": False})
    buffer.seek(0)

    barcode_img = Image.open(buffer)

    width, height = barcode_img.size
    extra_height = 80 if desc or harga else 40
    new_img = Image.new("RGB", (width, height + extra_height), "white")
    new_img.paste(barcode_img, (0, 0))

    draw = ImageDraw.Draw(new_img)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()

    # Baris pertama: SKU (selalu ada)
    line1 = f"{sku}" if not desc else f"{sku} - {desc}"
    text_width1 = draw.textlength(line1, font=font)
    draw.text(((width - text_width1) // 2, height + 5), line1, font=font, fill="black")

    # Baris kedua: Harga (opsional)
    if harga:
        line2 = f"Harga: {harga}"
        text_width2 = draw.textlength(line2, font=font)
        draw.text(((width - text_width2) // 2, height + 30), line2, font=font, fill="black")

    return new_img

# ===== Utility: Export ke PDF =====
def export_pdf(df, num_cols=3, filename="barcodes.pdf"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    col_width = width / num_cols
    row_height = 150  # tinggi tiap baris barcode
    x, y = 0, height - row_height

    for i, row in df.iterrows():
        sku, desc, harga = str(row["SKU"]), str(row["Description"]), str(row["Harga"])
        img_buffer = generate_barcode(sku, desc, harga)  # ini BytesIO
        img = ImageReader(img_buffer)  # wrap BytesIO agar bisa dipakai ReportLab

        c.drawImage(img, x + 5, y + 15, width=col_width - 10, height=row_height - 20)

        # teks tambahan
        #c.setFont("Helvetica", 8)
        #c.drawCentredString(x + col_width/2, y + 5, f"{sku} - {desc}")
        #c.drawCentredString(x + col_width/2, y - 5, f"Harga: {harga}")

        x += col_width
        if (i + 1) % num_cols == 0:
            x = 0
            y -= row_height
            if y < row_height:
                c.showPage()
                y = height - row_height

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
            img = generate_barcode(sku.strip(), desc.strip(), harga.strip())
            st.image(img, caption=f"{sku} {('- ' + desc) if desc else ''} {('| Harga: ' + harga) if harga else ''}", use_column_width=True)

            # Download PNG
            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            st.download_button("Download PNG", data=img_buffer.getvalue(), file_name=f"{sku}.png", mime="image/png")
        else:
            st.warning("SKU tidak boleh kosong!")

# ---- Mode CSV ----
else:
    uploaded_file = st.file_uploader("Upload file CSV (harus ada kolom: SKU, Description, Harga)", type=["csv"])
    if uploaded_file is not None:
        import csv
        # Deteksi delimiter otomatis
        sample = uploaded_file.read(1024).decode("utf-8")
        uploaded_file.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        df = pd.read_csv(uploaded_file, delimiter=dialect.delimiter)

        # Validasi kolom
        required_cols = ["SKU", "Description", "Harga"]
        if not all(col in df.columns for col in required_cols):
            st.error(f"CSV harus berisi kolom: {', '.join(required_cols)}")
        else:
            st.success("Data berhasil dimuat ✅")
            st.dataframe(df.head())

            # Preview barcode
            if st.button("Preview Barcode dari CSV"):
                for _, row in df.iterrows():
                    sku = str(row["SKU"])
                    desc = str(row["Description"])
                    harga = str(row["Harga"])
                    img = generate_barcode(sku, desc, harga)
                    st.image(img, caption=f"{sku} - {desc} | Harga: {harga}", use_column_width=True)

            # Pilih jumlah kolom PDF
            num_cols = st.slider("Jumlah kolom per halaman PDF", min_value=3, max_value=6, value=3)

            # Export ke PDF
            if st.button("Export semua ke PDF"):
                pdf_buffer = export_pdf(df, num_cols=num_cols, filename="barcodes.pdf")
                st.download_button("Download PDF", data=pdf_buffer, file_name="barcodes.pdf", mime="application/pdf")

st.caption("Fuad EDP399")


