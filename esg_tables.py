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
#    Kaynak: 2024 Report (p. 7, 28) & 2025 Report — Water Table 1 (p. 35-36)
#    Birim : million m3 (milyon metreküp)
# ═══════════════════════════════════════════════════════════════════════════════

def get_water_metrics_df() -> pd.DataFrame:
    """
    Yıllık su çekimi (withdrawal), kümülatif sözleşmeli yenileme hacmi,
    yıllık (in-year) yenileme faydası ve tamamlanan yenileme hacmi.
    TÜM DEĞERLER AÇIKÇA million m3 (milyon metreküp) CİNSİNDENDİR.
    """
    data = {
        "Metric": [
            "Water Withdrawal (million m3)",
            "Cumulative Contracted Water Replenishment Volume (million m3)",
            "In-Year Specifically Contracted Water Replenishment Benefit (million m3)",
            "Water Replenishment Volumetric Target (million m3)",
            "Water Replenishment Completed Volume (million m3)",
            "Water Replenishment Achievement Rate (%)",
        ],
        "FY20_Baseline": [4830.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "FY23":          [7100.0, 61.7, 25.0, 4500.0, 3100.0, 68.9],
        "FY24":          [8450.0, 93.5, 32.2, 6100.0, 4200.0, 68.9],
        "FY25":          [10210.0, 125.0, 35.0, 9500.0, 7800.0, 82.1],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SU YENİLEME PROJELERİ — BÖLGE & TİP KIRILIMLARI (Water Table 1 Expanded)
#    Kaynak: 2025 Report — Water Replenishment Projects Table (p. 36-38)
#    Birim : m3 (metreküp, bireysel proje hacimleri)
# ═══════════════════════════════════════════════════════════════════════════════

def get_water_replenishment_projects_df() -> pd.DataFrame:
    """
    Su yenileme projelerinin bölge ve proje tipi bazında kırılımı.
    Tamamlanan hacim m3 cinsinden; proje adedi toplam adet.
    """
    data = {
        "Region": [
            "Americas (North)",
            "Americas (Latin)",
            "Europe, Middle East & Africa",
            "Asia Pacific",
            "Global / Multi-region",
        ],
        "Project_Type": [
            "Watershed Restoration & Conservation",
            "Wetland & Riparian Restoration",
            "Agricultural Water Efficiency",
            "Groundwater Recharge",
            "Urban Water Recycling",
        ],
        "FY24_Projects_Count": [18, 11, 9,  7,  4],
        "FY25_Projects_Count": [24, 15, 13, 10, 5],
        "FY25_Completed_Volume_m3": [
            2_900_000_000,
            1_750_000_000,
            1_480_000_000,
            1_120_000_000,
            550_000_000,
        ],
        "FY25_Share_Pct": [37.2, 22.4, 19.0, 14.4, 7.1],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ENERJİ METRİKLERİ (Energy Summary)
#    Kaynak: 2025 Report — Energy Table (p. 28-29)
#    Birim : MWh (megawatt-saat)
# ═══════════════════════════════════════════════════════════════════════════════

def get_energy_metrics_df() -> pd.DataFrame:
    """
    Toplam enerji tüketimi, yenilenebilir enerji alımı ve yenilenebilir oran.
    Birim: MWh.
    """
    data = {
        "Metric": [
            "Total Electricity Consumption",
            "Renewable Energy Purchased (PPA + REC)",
            "Renewable Energy Share (%)",
            "On-site Renewable Generation",
            "Carbon-free Energy Coverage (%)",
        ],
        "FY20_Baseline": [10_200_000, 8_100_000,  79.4, 52_000,  79.4],
        "FY24":          [29_500_000, 23_400_000,  79.3, 98_000,  79.3],
        "FY25":          [43_800_000, 41_600_000,  95.0, 130_000, 95.0],
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

