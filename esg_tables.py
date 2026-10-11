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
    """Contracted future-delivery commitments, not realized annual removals.

    Exact FY23/FY24 values: 2024 p.19 and 2025 p.21 Carbon Table 3.
    FY25 exact totals/allocations are not reported by the 2026 report.
    Missing cells are not zero; the FY25 lower-bound disclosure is separate.
    """
    return pd.DataFrame({
        "Metric": ["Total Contracted Carbon Removal", "Contracted In-year Neutrality Allocation",
                   "Contracted FY2030 Carbon Negative Allocation", "Contracted FY2031+ and Historic Allocation"],
        "Unit": ["mt"] * 4,
        "FY23": [5015019, 3549242, 1465777, None],
        "FY24": [21927370, 1690940, 2804056, 17432374],
        "FY25": [None] * 4,
    })


def get_carbon_removal_disclosures_df() -> pd.DataFrame:
    """Qualified FY25 disclosure: 2026 report pp.32–33; not an exact scalar."""
    return pd.DataFrame({
        "Fiscal_Year": ["FY25"], "Metric": ["Total Contracted Carbon Removal"],
        "Disclosure": ["More than 45 million metric tons"],
        "Measurement_Basis": ["Contracted future deliveries over the next three decades; not realized FY25 removal"],
        "Source": ["2026 Environmental Sustainability Report, pp.32–33"],
    })


def get_carbon_removal_by_type_df() -> pd.DataFrame:
    """Unavailable audited technology-volume shares; do not infer from totals."""
    frame = pd.DataFrame(columns=["Removal_Type", "FY23_Volume", "FY24_Volume", "FY25_Volume", "FY25_Share_Pct"])
    frame.attrs["unavailable_reason"] = "Technology volumes and percentages have not been source-audited."
    return frame


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
    """Off-site operational inventory: 2026 Fact Sheet Table 9, p.7, mt.

    FY25 includes cloud hardware packaging; prior years were not adjusted.
    Construction/deconstruction waste is outside this inventory's scope.
    """
    frame = pd.DataFrame({
        "Metric": ["Total Waste Generated", "Total Operational Waste Diverted",
                   "Waste Directed to Disposal", "Non-hazardous Waste Landfilled"],
        "Unit": ["mt"] * 4,
        "FY20": [40571, 29153, 11418, 10848],
        "FY21": [22518, 15278, 7240, 6957],
        "FY22": [29596, 17149, 12447, 12204],
        "FY23": [36392, 24663, 11729, 11510],
        "FY24": [41290, 28285, 13005, 12637],
        "FY25": [58868, 36149, 22719, 21540],
    })
    frame.attrs["source"] = "2026 Data Fact Sheet Table 9, p.7"
    frame.attrs["scope_change"] = "FY25 includes cloud hardware packaging; earlier years were not adjusted."
    return frame


def get_waste_prevention_df() -> pd.DataFrame:
    """On-site prevention is separate from off-site inventory: Table 10, p.8."""
    return pd.DataFrame({
        "Metric": ["Waste Reused On-site", "Waste Reduced On-site", "Total Waste Prevented"],
        "Unit": ["mt"] * 3, "FY24": [4949, 433, 5382], "FY25": [4961, 2685, 7646],
    })


def get_zero_waste_certifications_df() -> pd.DataFrame:
    """No audited site-count/tier series: missing evidence must not become zero."""
    frame = pd.DataFrame(columns=["Attribute", "Detail / Value", "Report_Source"])
    frame.attrs["unavailable_reason"] = "Site counts and certification tiers have not been source-audited."
    return frame


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
