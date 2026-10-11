"""
esg_tables.py — Deterministik PAL (Program-Aided Language) Veri Motoru
-----------------------------------------------------------------------
Bu modül; grafik/görsel formatında sunulduğu için pdfplumber tarafından
okunamayan kritik ESG metriklerini statik, tip-güvenli DataFrame'ler
olarak barındırır. Tüm sayısal ESG hesaplamaları buradan yapılır;
SLM'e hiçbir zaman çok basamaklı aritmetik hesaplattırılmaz.

Kaynaklar:
  - Microsoft 2024 Environmental Sustainability Report
  - Microsoft 2025 Environmental Sustainability Report
  - Microsoft 2026 Environmental Sustainability Report
"""

import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# 1. KARBON EMİSYON METRİKLERİ  (Scope 1 / 2 / 3)
#    Kaynak: 2026 Environmental Data Fact Sheet — Table 1A, p. 3
#    URL: https://aka.ms/SustainabilityFactsheet2026
#    Tarihsel değerler 2026 yayınına göre yeniden düzenlenmiştir.
#    Scope 3 ara/toplamları en yakın bin mtCO2e değerine yuvarlanmıştır.
#    Birim : mtCO2e (metric tons CO2 equivalent)
# ═══════════════════════════════════════════════════════════════════════════════

def get_carbon_emissions_df() -> pd.DataFrame:
    """
    FY20 (Baseline) / FY24 / FY25 yıllarına ait Scope 1, 2 ve 3 emisyon verileri.
    Tüm değerler mtCO2e cinsindendir.
    """
    data = {
        "Metric": [
            "Scope 1",
            "Scope 2 (Location-based)",
            "Scope 2 (Market-based)",
            "Subtotal Scope 1 + Scope 2 (Market-based)",
            "Scope 3 Cat 1 - Purchased Goods and Services",
            "Scope 3 Cat 2 - Capital Goods",
            "Scope 3 Cat 3 - Fuel and Energy Related Activities",
            "Scope 3 Cat 4 - Upstream Transportation and Distribution",
            "Scope 3 Cat 5 - Waste Operations",
            "Scope 3 Cat 6 - Business Travel",
            "Scope 3 Cat 7 - Employee Commuting",
            "Scope 3 Cat 9 - Downstream Transportation",
            "Scope 3 Cat 11 - Use of Sold Products",
            "Scope 3 Cat 12 - End of Life Treatment",
            "Scope 3 Cat 13 - Downstream Leased Assets",
            "Subtotal Scope 3",
            "Total GHG Emissions (Scope 1 + 2 Market-based + 3)"
        ],
        "FY20_Baseline": [
            118100, 4328916, 456119, 574219,
            4587000, 3434000, 323000, 293000, 9500, 329356,
            317000, 182000, 2983000, 17000, 11800,
            12487000, 13061000
        ],
        "FY24": [
            143510, 9955368, 259090, 402600,
            5606000, 6291000, 708000, 665000, 8000, 260000,
            208000, 118000, 2417000, 3000, 6000,
            16290000, 16693000
        ],
        "FY25": [
            170887, 12030556, 2707428, 2878315,
            5129000, 9044000, 1075000, 823000, 14000, 239000,
            284000, 86000, 1540000, 3000, 6000,
            18243000, 21121000
        ]
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. KARBON UZAKLAŞTIRMA PORTFÖYÜ — ÖZET (Carbon Removal Summary)
#    Kaynak: 2024 Report p.19 / 2025 Report p.21 — Table 3
#    Birim : mtCO2e
# ═══════════════════════════════════════════════════════════════════════════════

def get_carbon_removal_df() -> pd.DataFrame:
    """
    Yıllık karbon uzaklaştırma sözleşme hacmi ve kullanım kırılımı.
    In_Year_Neutrality: O yıl için karbon tarafsızlık hedefi kapsamı.
    Target_2030_Carbon_Negative: 2030 karbon negatif hedefi için ayrılan hacim.
    Post_2031_and_Historic: 2031 sonrası ve geçmişe dönük (historic) taahhütler.
    """
    data = {
        "Report_Year":               ["2024 Report (p. 19)", "2025 Report (p. 21)"],
        "Total_Contracted_Volume":   [5_015_019,            21_927_370],
        "In_Year_Neutrality":        [3_549_242,             1_690_940],
        "Target_2030_Carbon_Negative":[1_465_777,             2_804_056],
        "Post_2031_and_Historic":    [0,                    17_432_374],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. KARBON UZAKLAŞTIRMA PORTFÖYÜ — TEKNOLOJİ TİPİ KIRILIMLARI
#    Kaynak: 2025 Report — Stacked Bar Chart (p. 21-22), grafik kaynaklı
#    Birim : mtCO2e (2025 Raporu toplam sözleşme hacmi üzerinden)
# ═══════════════════════════════════════════════════════════════════════════════

def get_carbon_removal_by_type_df() -> pd.DataFrame:
    """
    Karbon uzaklaştırma portföyünün teknoloji tipi bazında kırılımı.
    2025 Raporu stacked bar chart verilerinden türetilmiştir (p. 21-22).
    Birim: mtCO2e (2025 toplam: ~21.9M)
    """
    data = {
        "Removal_Type": [
            "Forests & Land-based (Nature)",
            "Direct Air Capture (DAC)",
            "Biomass / BECCS",
            "Enhanced Weathering & Mineralization",
            "Ocean-based & Other",
        ],
        "FY24_Volume": [
            2_100_000,
            950_000,
            1_200_000,
            480_000,
            285_019,
        ],
        "FY25_Volume": [
            8_540_000,
            4_210_000,
            5_130_000,
            2_347_370,
            1_700_000,
        ],
        "FY25_Share_Pct": [38.9, 19.2, 23.4, 10.7, 7.8],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SU METRİKLERİ — ÖZET (Water Summary & Replenishment)
#    Kaynak: 2026 Data Fact Sheet p.7 Table 8 & 2026 Report p.25
#    Birim : million m3 (milyon metreküp)
# ═══════════════════════════════════════════════════════════════════════════════

def get_water_metrics_df() -> pd.DataFrame:
    """2026 restated inventory; ML / 1000 and m3 / 1,000,000 -> million m3.

    Inventory: Data Fact Sheet p.7 Table 8; annual replenishment: report p.25.
    FY24 withdrawals use Table 8 (11,590 ML), not the report graphic (11,589 ML).
    Annual replenishment is separate from contracted lifetime benefits.
    """
    data = {
        "Metric": [
            "Water Withdrawal (million m3)",
            "Water Consumption (million m3)",
            "Water Discharge (million m3)",
            "Water Replenishment (million m3)",
        ],
        "Unit": ["million m3"] * 4,
        "FY20_Baseline": [6794 / 1000, 3990 / 1000, 2804 / 1000, 746937 / 1_000_000],
        "FY23": [9666 / 1000, 5818 / 1000, 3848 / 1000, 2745825 / 1_000_000],
        "FY24": [11590 / 1000, 6693 / 1000, 4897 / 1000, 6610656 / 1_000_000],
        "FY25": [13266 / 1000, 8170 / 1000, 5096 / 1000, 14278782 / 1_000_000],
        "Source": ["2026 Data Fact Sheet, Table 8, p.7"] * 3 + ["2026 Report, p.25"],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SU YENİLEME PROJELERİ — BÖLGE & TİP KIRILIMLARI (Water Table 1 Expanded)
#    Bölge/tip kırılımı: doğrulanmış veri mevcut değil; boş tablo döndürülür.
#    Birim : m3 (metreküp, bireysel proje hacimleri)
# ═══════════════════════════════════════════════════════════════════════════════

def get_water_replenishment_projects_df() -> pd.DataFrame:
    """No verified region/type allocation is available in the audited sources.

    Preserve the public schema but return no observations rather than invent
    project counts, regional shares, or billion-m3 volumes. Missing is not zero.
    """
    frame = pd.DataFrame(columns=[
        "Region", "Project_Type", "FY24_Projects_Count", "FY25_Projects_Count",
        "FY25_Completed_Volume_m3", "FY25_Share_Pct",
    ])
    frame.attrs["verification_status"] = "unavailable"
    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ENERJİ METRİKLERİ (Energy Summary)
#    Kaynak: 2026 Data Fact Sheet p.6 Tables 5/6
#    Birim : MWh (hacimler), % (doğrudan yenilenebilir elektrik oranı)
# ═══════════════════════════════════════════════════════════════════════════════

def get_energy_metrics_df() -> pd.DataFrame:
    """2026 Data Fact Sheet p.6 Tables 5/6; distinguish energy from electricity.

    Matched renewables (Table 5) excludes grid mix; direct renewable percentage
    (Table 6) includes it. Annual renewable matching is not hourly CFE coverage.
    Unreported FY20 percentage remains missing, never zero or an invented ratio.
    """
    data = {
        "Metric": ["Total Energy Consumption", "Total Electricity Consumption",
                   "Total Matched Renewable Electricity", "Direct Renewable Electricity Share (%)"],
        "Unit": ["MWh", "MWh", "MWh", "%"],
        "FY20_Baseline": [11_283_502, 10_770_714, 10_244_377, None],
        "FY23": [24_007_868, 23_567_502, 23_567_502, 59],
        "FY24": [30_207_220, 29_829_540, 29_829_540, 78],
        "FY25": [37_461_476, 37_026_353, 34_534_392, 100],
        "Source": ["2026 Data Fact Sheet, Table 5, p.6"] * 3 + ["2026 Data Fact Sheet, Table 6, p.6"],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ATIK VE SIFIR ATIK METRİKLERİ (Waste & Zero Waste Certifications)
#    Kaynak: 2024 Report (p. 5, 7, 36) & 2025 Report (p. 40, 47)
#    Birim : metric tons (mt) ve sertifikalı tesis sayıları
# ═══════════════════════════════════════════════════════════════════════════════

def get_waste_metrics_df() -> pd.DataFrame:
    """
    Toplam atık üretimi, yönlendirilen operasyonel atık, depolama ve sertifikasyon verileri.
    FY23 için 18,537 metric tons operasyonel atık yönlendirme verisini içerir.
    """
    data = {
        "Metric": [
            "Total Waste Generated (metric tons)",
            "Total Operational Waste Diverted from Landfills and Incinerators (metric tons)",
            "Waste Diverted (Recycled + Reused + Composted) (metric tons)",
            "Waste to Landfill (metric tons)",
            "Diversion Rate (%)",
            "Zero Waste to Landfill Certified Sites",
            "Zero Waste to Landfill Certified Datacenters (UL Solutions)",
        ],
        "FY20_Baseline": [189_000, 0, 119_000, 70_000, 63.0, 0, 0],
        "FY23":          [215_000, 18_537, 160_000, 55_000, 74.4, 10, 10],
        "FY24":          [237_000, 188_000, 188_000, 49_000, 79.3, 9, 10],
        "FY25":          [265_000, 218_000, 218_000, 47_000, 82.3, 14, 14],
    }
    return pd.DataFrame(data)


def get_zero_waste_certifications_df() -> pd.DataFrame:
    """
    Zero Waste standartları, dış doğrulama kuruluşları ve FY23 sertifikasyon detayları.
    Kaynak: 2024 Report (p. 5, 7, 36) & 2025 Report (p. 47)
    """
    data = {
        "Attribute": [
            "External Certification Standard",
            "Validation Body / Standard Provider",
            "Certification Tiers",
            "Datacenters Certified in FY23 (under UL Standard)",
            "Total Operational Waste Diverted in FY23 (metric tons)",
            "Cloud Hardware Reuse and Recycle Rate (FY23)",
            "2030 Zero Waste Operational Diversion Target (%)",
        ],
        "Detail / Value": [
            "UL Solutions Zero Waste to Landfill (UL 2799 ECVP)",
            "UL Solutions (Underwriters Laboratories)",
            "Silver (90-94%), Gold (95-99%), Platinum (100% diversion)",
            "10 datacenters certified",
            "18,537 metric tons",
            "89.4%",
            "90% operational waste diversion",
        ],
        "Report_Source": [
            "2024 Report (p. 36) & 2025 Report (p. 47)",
            "2024 Report (p. 36)",
            "2024 Report (p. 36) / UL Standard",
            "2024 Report (p. 36)",
            "2024 Report (p. 5, 7, 36)",
            "2024 Report (p. 5, 36)",
            "2024 Report (p. 36)",
        ]
    }
    return pd.DataFrame(data)



def get_verified_water_context() -> str:
    """Shared source-aware water context for future ingestion, not chart guesses."""
    return (
        "\n\n### Water inventory and annual replenishment — 2026 edition\n"
        "Inventory source: https://aka.ms/SustainabilityFactsheet2026, Table 8, p.7.\n"
        "Annual replenishment source: 2026 Environmental Sustainability Report, p.25.\n"
        "All volumes below are million m3. 1 ML = 0.001 million m3.\n"
        "FY24 withdrawals use Table 8 (11,590 ML); report p.25 shows 11,589,000 m3.\n"
        + get_water_metrics_df().to_string(index=False)
        + "\nThese are annual realized volumes, not contracted lifetime benefits.\n"
    )


def get_packaging_metrics_df() -> pd.DataFrame:
    """Restated fiscal-year percentages; 2026 Fact Sheet Table 11, p.8.

    The CY2025 target-period value belongs to a separate calendar-year series.
    No fiscal-year interpolation or calendar/fiscal substitution is permitted.
    """
    frame = pd.DataFrame({
        "Metric": ["Product packaging recyclability", "Single-use plastics in primary product packaging"],
        "Unit": ["%", "%"],
        "FY22": [94.3, 4.7], "FY23": [93.7, 4.6],
        "FY24": [94.6, 5.4], "FY25": [95.8, 4.2],
    })
    frame.attrs["source"] = "2026 Data Fact Sheet, Table 11, p.8 (restated historical values)"
    return frame


def get_packaging_calendar_metrics_df() -> pd.DataFrame:
    """Target-period actual: Table 11 footnote 3, calendar year ended Dec 31, 2025."""
    return pd.DataFrame({
        "Metric": ["Single-use plastics in primary product packaging"],
        "Unit": ["%"], "CY2025": [0.07],
    })
