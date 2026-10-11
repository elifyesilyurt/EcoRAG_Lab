"""UI-independent ESG domain and intent routing."""

import re

from dynamic_math_engine import is_mathematical_query


def is_esg_query(query: str) -> bool:
    if not query:
        return False
    q = query.lower()
    
    # Doğrudan ESG / Çevre dışı soru kalıpları
    out_of_domain_patterns = [
        "ne zaman kuruldu", "kurucusu kim", "kuruculari", "kim kurdu", "hisse fiyati", 
        "hisse senedi", "borsa degeri", "piyasa degeri", "gelir tablosu", "net kar",
        "ceo kim", "satadya", "satya nadella", "bill gates", "paul allen",
        "windows 11", "windows 10", "xbox", "office 365", "playstation", "fifa",
        "cpu saat", "saat hizi", "ghz", "onbellek", "gecikme suresi", "ping", "latency",
        "when was microsoft founded", "who founded microsoft", "stock price", "market cap",
        "who is the ceo", "quarterly revenue", "net profit", "operating income"
    ]
    if any(p in q for p in out_of_domain_patterns):
        return False

    esg_keywords = {
        "karbon", "carbon", "emisyon", "emission", "emissions", "ghg", "sera", "gazi", "gazı",
        "scope", "scope 1", "scope 2", "scope 3", "net zero", "net sıfır", "net sifir",
        "su", "water", "yenileme", "replenish", "replenishment", "cekim", "çekim", "withdrawal",
        "havza", "watershed", "atik", "atık", "waste", "sifir atik", "sıfır atık", "zero waste",
        "cop", "çöp", "landfill", "geri donusum", "geri dönüşüm", "recycle", "recycling",
        "plastik", "plastic", "ambalaj", "packaging", "döngüsel", "dongusel", "circular",
        "enerji", "energy", "elektrik", "electricity", "yenilenebilir", "renewable", "mwh", "kwh",
        "ppa", "rec", "veri merkezi", "datacenter", "datacenters", "bulut", "cloud",
        "surdurulebilirlik", "sürdürülebilirlik", "sustainability", "cevre", "çevre", "environmental",
        "esg", "iklim", "climate", "biyoçesitlilik", "biyoçeşitlilik", "biodiversity",
        "ekosistem", "ecosystem", "orman", "forest", "agac", "ağaç",
        "fido", "ul", "ul 2799", "dac", "beccs", "biyokutle", "biyokütle", "biomass",
        "2024", "2025", "2026", "fy20", "fy23", "fy24", "fy25", "fy26", "rapor", "raporu", "report",
        "target", "hedef", "hedefler", "pillar", "taahhut", "taahhüt", "commitment",
        "hollanda", "madrid", "quincy", "boydton", "queretaro", "phoenix", "london"
    }
    
    # Short domain tokens must be words: "ul" in "calculate" is not an ESG signal.
    short_tokens = {"su", "ul", "rec", "cop"}
    if any(bool(re.search(r"\b" + re.escape(k) + r"\b", q)) if k in short_tokens else k in q
           for k in esg_keywords):
        return True
    return False

def classify_esg_intent(query: str) -> str:
    """Apply domain rejection, numeric intent, then topic-specific narratives.

    Keyword routing is a temporary heuristic. Numeric intent must not be
    shadowed by water/energy/carbon/packaging summary keywords. Domain filtering
    remains unchanged for the separate domain-coverage stage.
    """
    if not query:
        return "out_of_domain"
    if not is_esg_query(query):
        return "out_of_domain"

    q = query.lower()

    # Numeric operations outrank broad topic summaries, after the domain gate.
    if is_mathematical_query(query):
        return "mathematical_query"

    # Policy/strategy comparisons need report narratives, not fixed FY25 metric tables.
    if (re.search(r"\b(?:compare|karşılaştır\w*)\b", q)
            and re.search(r"\b(?:polic\w*|strateg\w*|politika\w*|strateji\w*)\b", q)):
        return "general_rag"

    # 1. Packaging & Single-Use Plastic
    if any(k in q for k in ["tek kullanımlık plastik", "single-use plastic", "ambalaj", "packaging", "plastic packaging"]) and any(k in q for k in ["oran", "percentage", "rate", "yolculuk", "trajectory", "düşüş", "reduction", "trend", "2026", "2025", "0.07", "cihaz", "device", "primer", "birincil", "primary"]):
        return "packaging_plastic"

    # 2. Zero Waste & Circularity
    if any(k in q for k in ["sıfır atık", "zero waste", "circular center", "döngüsel", "donanım", "hardware", "ul 2799", "true zero", "atık", "waste"]) and any(k in q for k in ["standart", "standard", "sertifika", "certificate", "certification", "yeniden kullanım", "reuse", "ömrü biten", "veri merkezi", "datacenter", "datacenters", "değişim", "kurtarılan", "merkezler", "diversion", "diverted", "progress", "rate", "goal", "hedef", "target"]):
        return "zero_waste_circularity"

    # 3. Carbon Removal Portfolio (Tablo 3 & Portföy Büyümesi)
    if any(k in q for k in ["karbon uzaklaştırma", "carbon removal", "cdr", "tablo 3", "table 3", "dac", "direct air capture", "biomass", "biyokütle", "uzaklaştırma portföy", "uzaklaştırma hacmi", "removal portfolio", "contracted carbon removal", "removal volume"]):
        return "carbon_removal"

    # 6. Water Stewardship & Replenishment & Acoustic AI Leaks (use regex word boundary for 'su')
    is_water = bool(re.search(r"\bsu\b", q)) or any(k in q for k in ["water", "fido", "akustik sızıntı", "acoustic leak", "replenishment"])
    if is_water and any(k in q for k in ["yenileme", "replenish", "replenishment", "hacim", "volume", "ikmal", "kaçak", "leak", "leaks", "sızıntı", "belediye", "municipal", "başarı", "achievement", "hedef", "target", "çekim", "withdrawal", "m³", "milyon m", "million m", "goal", "pozitif", "positive"]):
        return "water_stewardship"

    # 4. Carbon Commitments (2030, 2050, CFE, PPA)
    if any(k in q for k in ["2030", "2050", "karbon negatif", "carbon negative", "tarihsel emisyon", "historical emission", "historical emissions", "cfe", "karbonsuz elektrik", "carbon-free electricity", "ppa", "temiz enerji sözleşme", "clean energy", "power purchase", "taahhüt", "commitment", "commitments"]) and not any(k in q for k in ["kategori 1", "kategori 2", "scope 3 kat", "category 1", "category 2"]):
        return "carbon_commitments"

    # 5. Carbon Trend & Scopes & GHG Delta
    if any(k in q for k in ["scope", "sera gazı", "emisyon", "emission", "emissions", "ghg"]) and any(k in q for k in ["trend", "artış", "increase", "growth", "kategori 1", "kategori 2", "category 1", "category 2", "cat 1", "cat 2", "toplam", "total", "değiş", "change", "delta", "büyüme", "fy20", "fy25", "fark", "difference", "pay", "share"]):
        return "carbon_trend_scope"

    # 8. RAG Hibrit Korpus Arama
    return "general_rag"
