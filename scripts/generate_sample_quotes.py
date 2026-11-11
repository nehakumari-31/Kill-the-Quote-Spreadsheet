import os
import sys
import fitz
import docx
import openpyxl
from PIL import Image, ImageDraw, ImageFont
import pandas as pd

def generate_sample_quotes():
    os.makedirs('sample_quotes', exist_ok=True)
    xl = pd.ExcelFile('RFx_Master_Updated.xlsx')
    df_items = pd.read_excel(xl, 'Line Items')
    df_items = df_items[pd.to_numeric(df_items['Line #'], errors='coerce').notna()].copy()
    df_items['Line #'] = df_items['Line #'].astype(int)

    df_norm = pd.read_excel(xl, 'Normalized Comparison')
    df_norm = df_norm[pd.to_numeric(df_norm['Line #'], errors='coerce').notna()].copy()
    df_norm['Line #'] = df_norm['Line #'].astype(int)

    # 1. Generate V1_Apex_Quote.xlsx
    wb1 = openpyxl.Workbook()
    ws1 = wb1.active
    ws1.title = 'Commercial Quote'
    headers1 = ['Line #', 'Item Code', 'Item Description', 'Quoted Price', 'Quoted UoM', 'Currency', 'Delivery Plant', 'GST', 'Lead Time (Days)', 'Payment Terms', 'Notes']
    ws1.append(headers1)
    for _, r in df_norm.iterrows():
        l_no = int(r['Line #'])
        code = str(r['Item Code'])
        item_row = df_items[df_items['Line #'] == l_no].iloc[0]
        desc = str(item_row['Item Description'])
        loc = str(item_row['Delivery Location'])
        v1_landed = float(r['V1 Landed (Apex)'])
        if l_no == 1:
            price = 6120.0
            uom = 'per 1000 Nos'
            notes = 'Rate is ₹6,120 per 1,000 Nos'
        elif l_no == 2:
            price = 10350.0
            uom = 'per 1000 Nos'
            notes = 'Rate is ₹10,350 per 1,000 Nos'
        else:
            price = v1_landed
            uom = 'Nos' if l_no not in [23, 24, 29] else str(item_row['UoM'])
            notes = 'Direct piece rate inclusive of freight'
        ws1.append([l_no, code, desc, price, uom, 'INR', loc, '18% extra', 7, 'Net 30 days (1.5% prompt payment discount if paid in 10 days)', notes])
    wb1.save('sample_quotes/V1_Apex_Quote.xlsx')
    print('Created V1_Apex_Quote.xlsx')

    # 2. Generate V2_PackTech_Quote.pdf using PyMuPDF (fitz)
    doc2 = fitz.open()
    page = doc2.new_page(width=595, height=842) # A4
    page.insert_text(fitz.Point(50, 45), 'PACKTECH SOLUTIONS INDIA PVT LTD', fontsize=16, fontname='helv', color=(0.1, 0.2, 0.5))
    page.insert_text(fitz.Point(50, 62), 'Official Commercial Quotation - Ref: PTS-2026-RFX-017', fontsize=10, fontname='helv', color=(0.3, 0.3, 0.3))
    page.insert_text(fitz.Point(50, 75), 'Date: 15-Nov-2026 | Plant: Peenya Industrial Area, Bengaluru | ISO 9001:2015 Exp: 2027', fontsize=8, fontname='helv', color=(0.4, 0.4, 0.4))
    page.insert_text(fitz.Point(50, 88), 'Terms: Net 45 days | Freight: Included to Pune, Bhiwandi, Bengaluru | GST: 18% Extra', fontsize=8, fontname='helv', color=(0.4, 0.4, 0.4))
    page.draw_line(fitz.Point(50, 95), fitz.Point(545, 95), color=(0.7, 0.7, 0.7), width=1)

    y = 110
    page.insert_text(fitz.Point(50, y), 'Line #', fontsize=8, fontname='helv', color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(90, y), 'Item Code', fontsize=8, fontname='helv', color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(150, y), 'Description', fontsize=8, fontname='helv', color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(380, y), 'UoM', fontsize=8, fontname='helv', color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(430, y), 'Rate (INR)', fontsize=8, fontname='helv', color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(490, y), 'Delivery', fontsize=8, fontname='helv', color=(0.1, 0.1, 0.1))
    page.draw_line(fitz.Point(50, y+4), fitz.Point(545, y+4), color=(0.2, 0.2, 0.2), width=0.8)
    y += 16

    for _, r in df_norm.iterrows():
        l_no = int(r['Line #'])
        code = str(r['Item Code'])
        item_row = df_items[df_items['Line #'] == l_no].iloc[0]
        desc = str(item_row['Item Description'])[:38]
        uom = str(item_row['UoM'])
        rate = float(r['V2 Landed (PackTech)'])
        loc = 'Pune' if 'Pune' in str(item_row['Delivery Location']) else ('Bhiwandi' if 'Bhiwandi' in str(item_row['Delivery Location']) else 'Peenya')
        
        if y > 800:
            page = doc2.new_page(width=595, height=842)
            y = 50
        
        page.insert_text(fitz.Point(55, y), str(l_no), fontsize=7.5, fontname='helv')
        page.insert_text(fitz.Point(90, y), code, fontsize=7.5, fontname='helv')
        page.insert_text(fitz.Point(150, y), desc, fontsize=7.5, fontname='helv')
        page.insert_text(fitz.Point(380, y), uom, fontsize=7.5, fontname='helv')
        page.insert_text(fitz.Point(430, y), f'Rs {rate:.2f}', fontsize=7.5, fontname='helv')
        page.insert_text(fitz.Point(490, y), loc, fontsize=7.5, fontname='helv')
        y += 18

    doc2.save('sample_quotes/V2_PackTech_Quote.pdf')
    doc2.close()
    print('Created V2_PackTech_Quote.pdf')

    # 3. Generate V3_Global_Quote.docx
    doc3 = docx.Document()
    doc3.add_heading('GLOBAL CORRUGATORS LTD (INTERNATIONAL)', 0)
    doc3.add_paragraph('Quotation Reference: GC-EXP-2026-092 | Date: 14-Nov-2026')
    doc3.add_paragraph('Currency: USD ($) | Incoterms: CIF Nhava Sheva / Bhiwandi DC | Payment: LC at sight / Net 60 days')
    doc3.add_paragraph('Important Note: Quotes are in USD. FX rate applied by buyer at settlement. Lines 10, 21, 25, 30 are not quoted (Line 10 & 30 require 7-ply capability which is not available in our plant; Line 21 & 25 tooling omitted).')

    tbl3 = doc3.add_table(rows=1, cols=5)
    tbl3.style = 'Table Grid'
    hdr_cells = tbl3.rows[0].cells
    hdr_cells[0].text = 'Line #'
    hdr_cells[1].text = 'Item Code'
    hdr_cells[2].text = 'Description'
    hdr_cells[3].text = 'Price (USD)'
    hdr_cells[4].text = 'Remarks & Source Citation'

    for _, r in df_norm.iterrows():
        l_no = int(r['Line #'])
        code = str(r['Item Code'])
        item_row = df_items[df_items['Line #'] == l_no].iloc[0]
        desc = str(item_row['Item Description'])
        row_cells = tbl3.add_row().cells
        row_cells[0].text = str(l_no)
        row_cells[1].text = code
        row_cells[2].text = desc
        
        val3 = r['V3 Landed (Global USD)']
        if l_no in [10, 30]:
            row_cells[3].text = 'NOT QUOTED'
            row_cells[4].text = 'NOT QUOTED: 7-ply (BCB) triple wall capability not available (Failed Gate Q6)'
        elif l_no in [21, 25]:
            row_cells[3].text = 'NOT QUOTED'
            row_cells[4].text = 'NOT QUOTED: Line omitted due to specialized tooling constraints'
        else:
            usd_rate = round(float(val3) / 84.50, 4)
            row_cells[3].text = f'${usd_rate:.4f}'
            row_cells[4].text = f'USD ${usd_rate:.4f} /Nos (FOB Nhava Sheva basis)'

    doc3.save('sample_quotes/V3_Global_Quote.docx')
    print('Created V3_Global_Quote.docx')

    # 4. Generate V4_Balaji_Quote.png
    img = Image.new('RGB', (1200, 1600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (1200, 110)], fill=(240, 244, 250))
    draw.text((40, 25), 'SRI BALAJI PACKAGING INDUSTRIES', fill=(20, 40, 80))
    draw.text((40, 55), 'MIDC Phase II, Chakan, Pune · Tel: +91 2135 289901 · quotes@balajipackaging.in', fill=(80, 80, 80))
    draw.text((40, 80), 'Quotation Ref: SBP-2026-1188 · Date: 12-Nov-2026 · Valid for 30 days', fill=(100, 100, 100))

    draw.rectangle([(750, 20), (1160, 95)], fill=(254, 242, 242), outline=(220, 38, 38), width=2)
    draw.text((760, 28), 'AUDIT NOTICE / ATTACHMENT STATUS:', fill=(185, 28, 28))
    draw.text((760, 48), 'ISO 9001:2015 Cert Ref: QA-9001-2023', fill=(150, 0, 0))
    draw.text((760, 68), 'STATUS: EXPIRED OCTOBER 2026 (Renewal Pending)', fill=(200, 0, 0))

    y = 130
    draw.rectangle([(30, y), (1170, y+30)], fill=(225, 235, 245))
    draw.text((40, y+8), 'Line', fill=(10, 20, 40))
    draw.text((80, y+8), 'Code', fill=(10, 20, 40))
    draw.text((150, y+8), 'Description', fill=(10, 20, 40))
    draw.text((700, y+8), 'UoM', fill=(10, 20, 40))
    draw.text((780, y+8), 'Unit Rate (INR)', fill=(10, 20, 40))
    draw.text((920, y+8), 'Terms / Notes', fill=(10, 20, 40))
    y += 35

    for _, r in df_norm.iterrows():
        l_no = int(r['Line #'])
        code = str(r['Item Code'])
        item_row = df_items[df_items['Line #'] == l_no].iloc[0]
        desc = str(item_row['Item Description'])[:50]
        uom = str(item_row['UoM'])
        v4_price = float(r['V4 Landed (Balaji)'])
        
        draw.text((40, y), str(l_no), fill=(20, 20, 20))
        draw.text((80, y), code, fill=(20, 20, 20))
        draw.text((150, y), desc, fill=(20, 20, 20))
        draw.text((700, y), uom, fill=(20, 20, 20))
        draw.text((780, y), f'Rs. {v4_price:.2f}', fill=(10, 100, 20))
        draw.text((920, y), 'Ex-factory Chakan, GST extra', fill=(80, 80, 80))
        y += 36
        draw.line([(30, y-4), (1170, y-4)], fill=(230, 230, 230), width=1)

    draw.text((40, 1500), 'Declaration: Monthly corrugated board capacity 280 TPM. Testing conducted via external vendor lab.', fill=(120, 120, 120))
    draw.text((40, 1530), 'Authorized Signatory: Sri Balaji Packaging Industries (Stamp & Signature)', fill=(40, 40, 40))

    img.save('sample_quotes/V4_Balaji_Quote.png')
    print('Created V4_Balaji_Quote.png')

    # 5. Generate V5_StandardBox_Quote.eml
    eml_content = """From: sales.quotes@standardboxcorp.com
To: procurement.team@vedahomeappliances.com
Subject: Standard Box Corp - Commercial Quotation & Rate Card for RFx-CORR-2026-017
Date: Mon, 16 Nov 2026 14:30:00 +0530
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Dear Procurement Team,

Standard Box Corp is pleased to submit our formal rate card and commercial terms for RFx-CORR-2026-017:

1. SHIPPERS & LIGHT CARTONS (Lines 1 to 4):
   - Rate: Quoted on weight basis at ₹38.00 per kg board weight + applicable delivery freight.
   - Line 1 (CP-001): ₹38.00/kg + freight (estimated board weight 0.142 kg).
   - Line 2 (CP-002): ₹38.00/kg + freight (estimated board weight 0.218 kg).
   - Line 3 (CP-003): ₹38.00/kg + freight (estimated board weight 0.318 kg).
   - Line 4 (CP-004): ₹38.00/kg + freight (estimated board weight 0.419 kg).

2. MASTER CARTONS (Lines 5 to 9, and Line 20):
   - Rate: Quoted on weight basis at ₹42.00 per kg board weight + applicable delivery freight.
   - Line 5 (CP-005): ₹42.00/kg + freight.
   - Line 6 (CP-006): ₹42.00/kg + freight.
   - Line 7 (CP-007): ₹42.00/kg + freight.
   - Line 8 (CP-008): ₹42.00/kg + freight.
   - Line 9 (CP-009): ₹42.00/kg + freight.
   - Line 20 (CP-020): ₹42.00/kg + freight.

3. REPEAT SKUs (Lines 10 to 24):
   - Quoted as 'Same as last year' (please refer to our FY25 purchase orders with Veda Home Appliances).
   - Subject to 3.6% paper indexation adjustment as per agreement.

4. MOISTURE BARRIER EXPORT CARTONS (Lines 26 & 27):
   - Notice: We DO NOT provide moisture-barrier treatment (Failed Gate Q7 technical capability).
   - We quote standard Kraft board without barrier coating.

5. NEW SKUs (Lines 25, 27, 28, 29, 30):
   - Quote stated as 'Same as last year' (Note: Buyer please note these are new items with no prior PO reference on file -> UNRESOLVED).

COMMERCIAL TERMS:
- Payment Terms: Net 30 days.
- Delivery Terms: Ex-works Bhiwandi warehouse. Freight extra: Pune ₹1.20/kg, Bhiwandi ₹2.20/kg, Bengaluru ₹4.50/kg.
- GST: 18% extra.
- Validity: 30 days from date of quote.

Sincerely,
Rajesh Sharma
General Manager - Key Accounts
Standard Box Corp, Bhiwandi
"""
    with open('sample_quotes/V5_StandardBox_Quote.eml', 'w') as f:
        f.write(eml_content)
    print('Created V5_StandardBox_Quote.eml')

if __name__ == '__main__':
    generate_sample_quotes()
