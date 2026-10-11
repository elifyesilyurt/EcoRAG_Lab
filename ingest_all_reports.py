import os
import glob
import re
from typing import List, Dict, Any, Optional
import pdfplumber
from esg_tables import get_carbon_emissions_df, get_water_metrics_df, get_energy_metrics_df, get_waste_metrics_df, get_waste_prevention_df, get_carbon_removal_df, get_carbon_removal_disclosures_df
from ingestion_core import table_row_evidence, source_hash, replace_index

DB_PATH = "rag_storage.db"
EMBEDDING_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# Chunking ve filtreleme hiperparametreleri
TARGET_CHUNK_SIZE = 900       # Hedef chunk boyutu — nomic-embed 8192 token destekli, 900 char güvenli pencere
CHUNK_OVERLAP = 150           # Bağlam sürekliliği için örtüşme miktarı
MIN_CHUNK_LENGTH = 200        # Gürültü ve mikro-kırıkları eleyen asgari sınır (< 200 karakter elenir)

# ─── NAVİGASYON / HEADER / FOOTER KALIP LİSTESİ ─────────────────────────────
# PDF sayfa menüleri, gezinme linkleri, dipnot satırları ve yayın bilgileri
# bunlar içerik değil; retrieval kirliliği yaratır, temizlenir.
_NAV_PATTERNS: List[re.Pattern] = [
    # Sayfa gezinme menüsü: "Overview · Customer sustainability · ... · Appendix"
    re.compile(
        r'(?:overview|introduction|appendix|foreword|contents|table of contents)'
        r'(?:\s*[·|•\-]\s*\w[\w\s]+){2,}',
        re.IGNORECASE
    ),
    # Microsoft yayın/telif satırı: "Microsoft 2025 Environmental Sustainability Report"
    re.compile(
        r'microsoft\s+20\d{2}\s+(?:environmental\s+)?sustainability\s+report',
        re.IGNORECASE
    ),
    # Sayfa numarası kalıntısı: satır başında veya sonunda yalnız duran rakam
    re.compile(r'(?:^|\n)\s*\d{1,3}\s*(?:\n|$)'),
    # Dipnot numaraları ve kısa referans satırları: "¹ See appendix for..." veya "1. Source: ..."
    re.compile(r'(?:^|\n)\s*[¹²³⁴⁵⁶⁷⁸⁹¹⁰\d]+[\.\)]\s+.{0,80}(?:\n|$)'),
    # "See page X", "Refer to page X", "For more details see"
    re.compile(r'\b(?:see|refer to|for details see)\s+(?:page|p\.)\s*\d+\b', re.IGNORECASE),
    # Boş navigasyon satırları: sadece sekme/boşluk/pipe/bullet içeren satırlar
    re.compile(r'(?:^|\n)[ \t]*[|•·\-]{1,3}[ \t]*(?:\n|$)'),
]

# ─── GÖRSEL / GRAFİK İÇERİK TANIMLAYICILARI ─────────────────────────────────
# Bu kalıplar, bir chunk'ın grafik verisinden türediğini işaret eder.
# LLM'e bu chunk'tan sayısal çıkarım yapmaması söylenir.
_VISUAL_REF_PATTERNS: List[re.Pattern] = [
    # Açık grafik referansları
    re.compile(
        r'\b(?:figure|chart|graph|illustration|diagram|infographic|'
        r'as shown|see (?:above|below|figure|chart)|refer to (?:figure|chart))\b',
        re.IGNORECASE
    ),
    # Stacked bar / pasta grafik etiket kalıntısı:
    # "14.05% 12 End of Life" gibi grafik dilimi etiketi + lejand artığı
    re.compile(r'\d{1,3}(?:\.\d+)?%\s+\d+\s+[A-Z][a-z]'),
    # Sadece yüzde + küçük sayı dizisi (grafik lejandı): "1% 7% 9% 12%"
    re.compile(r'(?:\d{1,3}(?:\.\d+)?%\s*){3,}'),
]

# ─── GÖRSEL-ONLY SAYFA EŞIĞI ─────────────────────────────────────────────────
# Sayfada bu sayıdan fazla gömülü görsel varsa ve metin < eşiğin altındaysa
# sayfa görsel-ağırlıklı kabul edilir → placeholder chunk eklenir.
VISUAL_PAGE_IMG_THRESHOLD = 2
VISUAL_PAGE_WORD_THRESHOLD = 60


def clean_text(text: str) -> str:
    """Metindeki gereksiz boşlukları, satır kırıklarını ve özel karakterleri temizler."""
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    # Satır sonu hece bölmelerini birleştir (örn. corpo-\nrate -> corporate)
    text = re.sub(r'(\b[a-zA-Z]{2,})-\n\s*([a-zA-Z]{2,}\b)', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_clean_overlap(text: str, target_overlap: int = CHUNK_OVERLAP) -> str:
    """
    Önceki chunk'ın sonundan güvenli bir örtüşme (overlap) penceresi alır.
    Rastgele bir karakter indeksinden değil; öncelikle cümle sonundan (. ! ? \n),
    ikincil olarak büyük harfle başlayan bir kelimeden veya boşluktan hizalayarak başlatır.
    """
    if not text or target_overlap <= 0:
        return ""
    if len(text) <= target_overlap:
        return text

    # Geriye doğru 2 katı kadar bir pencereye bakarak en uygun doğal sınırı ara
    window = text[-min(len(text), int(target_overlap * 2.0)):]

    # 1. Öncelik: Tam cümle başlangıcı (noktalama sonrası büyük harf veya tırnak)
    matches = list(re.finditer(r'(?:[\.\!\?](?:\s+|\n+))([A-Z0-9"“\'])', window))
    if matches:
        best_match = min(matches, key=lambda m: abs((len(window) - m.start(1)) - target_overlap))
        start_idx = best_match.start(1)
        if len(window) - start_idx >= 35:
            return window[start_idx:].strip()

    # 2. Öncelik: Büyük Harfle başlayan bir kelime/başlık/özne sınırı
    cap_matches = list(re.finditer(r'(?:\s+|\n+)([A-Z0-9"“\'])', window))
    if cap_matches:
        best_cap = min(cap_matches, key=lambda m: abs((len(window) - m.start(1)) - target_overlap))
        start_idx = best_cap.start(1)
        if len(window) - start_idx >= 30:
            return window[start_idx:].strip()

    # 3. Öncelik: En yakın kelime sınırı (boşluk)
    cutoff = len(text) - target_overlap
    space_idx = text.find(' ', cutoff)
    if space_idx != -1 and space_idx < len(text) - 20:
        return text[space_idx + 1:].strip()

    return text[-target_overlap:].strip()


def remove_nav_artifacts(text: str) -> str:
    """
    Sayfa menüleri, header/footer kalıntıları ve dipnot satırlarını temizler.
    Temizleme sonrası çok kısa kalan metin MIN_CHUNK_LENGTH filtresiyle elenir.
    """
    for pattern in _NAV_PATTERNS:
        text = pattern.sub(' ', text)
    # Ardışık boşlukları ve boş satırları normalize et
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def classify_visual_content(text: str) -> Optional[str]:
    """
    Chunk metninde grafik referansı veya grafik etiket kalıntısı varsa
    uygun [VISUAL REFERENCE] etiketini döndürür, yoksa None döndürür.

    Dönüş değerleri:
      - "[VISUAL REFERENCE]"     : grafik referanslı metin (sayısal veri yok)
      - "[VISUAL DATA FRAGMENT]" : grafik etiket/lejand artığı (bağlamsız sayılar)
      - None                     : normal metin
    """
    # Standalone axis labels identify charts even without the word "chart".
    if len(re.findall(r"(?m)^\s*\d+(?:[.,]\d+)?[KMB]\s*$", text)) >= 2:
        return "[VISUAL DATA FRAGMENT]"
    # Grafik etiket artığı: bağlamsız yüzde + sayı dizisi
    if _VISUAL_REF_PATTERNS[1].search(text) or _VISUAL_REF_PATTERNS[2].search(text):
        return "[VISUAL DATA FRAGMENT]"
    # Açık grafik referansı ("as shown in chart above" gibi)
    if _VISUAL_REF_PATTERNS[0].search(text):
        return "[VISUAL REFERENCE]"
    return None


def inject_visual_tag(content: str, tag: str) -> str:
    """
    Chunk başlık satırının hemen altına visual uyarı etiketi ekler.
    Böylece DeterministicResolver bu chunk'ları sayısal çıkarım dışında tutabilir.
    """
    lines = content.split('\n', 1)
    if len(lines) == 2:
        header, body = lines
        warning = (
            f"[⚠ {tag} — Bu bölüm grafik/görsel içeriğinden türemiştir. "
            f"Sayısal veriler için PAL motorunu (esg_tables.py) kullanın.]\n"
        )
        return header + '\n' + warning + body
    return content


def recursive_character_splitter(
    text: str,
    chunk_size: int = TARGET_CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    min_length: int = MIN_CHUNK_LENGTH,
    separators: Optional[List[str]] = None
) -> List[str]:
    """
    Metni hiyerarşik ayırıcılar (Paragraf -> Cümle -> Satır -> Kelime) kullanarak
    hedef boyutta akıllı ve sınır-duyarlı parçalara (chunks) böler.
    """
    if separators is None:
        # Cümle sonları (. \n, . , !\n, ?\n) tek satır sonu (\n)'den önce değerlendirilir
        separators = ["\n\n", ".\n", ". ", "!\n", "! ", "?\n", "? ", "\n", "; ", ", ", " ", ""]

    text = clean_text(text)
    if len(text) < min_length:
        return []

    if len(text) <= chunk_size:
        return [text]

    chosen_sep = separators[-1]
    for sep in separators:
        if sep == "":
            chosen_sep = ""
            break
        if sep in text:
            chosen_sep = sep
            break

    splits = text.split(chosen_sep) if chosen_sep != "" else list(text)

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for piece in splits:
        piece_str = piece + chosen_sep if chosen_sep != "" else piece
        piece_len = len(piece_str)

        if piece_len > chunk_size and len(separators) > 1:
            next_seps = separators[separators.index(chosen_sep) + 1:] if chosen_sep in separators else separators[1:]
            sub_chunks = recursive_character_splitter(
                piece,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                min_length=min_length,
                separators=next_seps
            )
            for sc in sub_chunks:
                if current_len + len(sc) <= chunk_size:
                    current_chunk.append(sc)
                    current_len += len(sc)
                else:
                    if current_chunk:
                        combined = clean_text("".join(current_chunk))
                        if len(combined) >= min_length:
                            chunks.append(combined)
                    overlap_sc = extract_clean_overlap("".join(current_chunk), chunk_overlap) if chunk_overlap > 0 else ""
                    current_chunk = [overlap_sc, sc] if overlap_sc else [sc]
                    current_len = sum(len(x) for x in current_chunk)
        else:
            if current_len + piece_len <= chunk_size:
                current_chunk.append(piece_str)
                current_len += piece_len
            else:
                if current_chunk:
                    combined = clean_text("".join(current_chunk))
                    if len(combined) >= min_length:
                        chunks.append(combined)

                if chunk_overlap > 0 and current_chunk:
                    overlap_text = extract_clean_overlap("".join(current_chunk), chunk_overlap)
                    current_chunk = [overlap_text, piece_str] if overlap_text else [piece_str]
                    current_len = sum(len(x) for x in current_chunk)
                else:
                    current_chunk = [piece_str]
                    current_len = piece_len

    if current_chunk:
        combined = clean_text("".join(current_chunk))
        if len(combined) >= min_length:
            chunks.append(combined)

    return chunks


def format_chunk_with_metadata(
    doc_title: str, year: str, page_num: int, content: str,
    is_table: bool = False
) -> str:
    """
    Her chunk'ın başına doküman adı, rapor yılı, sayfa numarası ve içerik tipi ekler.
    """
    tag = "[STRUCTURED TABLE]" if is_table else "[TEXT NARRATIVE]"
    header = f"--- Document: {doc_title} (Report Year: {year}, Page: {page_num}) | Type: {tag} ---\n"
    return header + content.strip()


def table_to_structured_reprs(table: List[List[Any]], min_length: int = MIN_CHUNK_LENGTH) -> List[str]:
    """Compatibility entry point; valid table rows are not narrative micro-garbage."""
    return table_row_evidence(table, TARGET_CHUNK_SIZE)


def extract_year_from_filename(filename: str) -> str:
    """Dosya adından rapor yılını yakalar."""
    match = re.search(r'20\d{2}', filename)
    return match.group(0) if match else "Unknown"


def fix_reversed_chart_text(text: str) -> str:
    """
    PDF grafiklerinde dikey eksenden dolayı tersten okunan sayıları ve birimleri düzeltir
    (örn. '000,662,31' -> '13,266,000', '000,071,8' -> '8,170,000').
    """
    if not text:
        return ""
    # Ters basılmış 3-3-1..2 basamaklı virgüllü sayıları düzelt (örn. 000,662,31 -> 13,266,000)
    text = re.sub(r'\b\d{3},\d{3},\d{1,2}\b', lambda m: m.group(0)[::-1], text)
    # Ters basılmış 3-1..2 basamaklı sayıları düzelt
    text = re.sub(r'\b\d{3},\d{1,2}\b', lambda m: m.group(0)[::-1], text)
    text = text.replace('retaW', 'Water').replace('3 m\nretaW', 'Water (m³)').replace('3 m\nWater', 'Water (m³)')
    return text


def process_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Tek bir PDF dosyasını okur, tabloları ve gövde metinlerini hiyerarşik ve temiz olarak chunk'lara böler."""
    doc_title = os.path.basename(pdf_path)
    year = extract_year_from_filename(doc_title)
    digest = source_hash(pdf_path)
    if year == "Unknown":
        raise ValueError(f"Missing publication year: {doc_title}")
    chunks: List[Dict[str, Any]] = []
    table_count = 0
    nav_cleaned_count = 0

    print(f"\n[INGEST] İşleniyor: {doc_title} (Rapor Yılı: {year})...")
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""
            raw_text = fix_reversed_chart_text(raw_text)
            page_visual_tag = classify_visual_content(raw_text)

            # ── 1. Yapısal Tablo Çıkarımı ────────────────────────────────────
            tables = page.extract_tables()
            for table in tables:
                table_reprs = table_to_structured_reprs(table, min_length=MIN_CHUNK_LENGTH)
                for t_repr in table_reprs:
                    formatted = format_chunk_with_metadata(
                        doc_title, year, page_idx, t_repr, is_table=True
                    )
                    chunks.append({
                        "year": year,
                        "title": f"{doc_title} (p.{page_idx})",
                        "content": formatted,
                        "type": "table", "page": page_idx, "source_sha256": digest
                    })
                    table_count += 1

            # ── 2. Metin Çıkarımı + Navigasyon Temizliği ─────────────────────
            if raw_text:
                cleaned = remove_nav_artifacts(raw_text)
                original_len = len(raw_text)
                if len(cleaned) < original_len * 0.85:
                    nav_cleaned_count += 1

                text_chunks = recursive_character_splitter(
                    cleaned,
                    chunk_size=TARGET_CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                    min_length=MIN_CHUNK_LENGTH
                )

                for t_chunk in text_chunks:
                    formatted = format_chunk_with_metadata(
                        doc_title, year, page_idx, t_chunk, is_table=False
                    )
                    visual_tag = page_visual_tag or classify_visual_content(t_chunk)
                    if visual_tag:
                        formatted = inject_visual_tag(formatted, visual_tag)
                    chunks.append({
                        "year": year,
                        "title": f"{doc_title} (p.{page_idx})",
                        "content": formatted,
                        "type": "text", "page": page_idx, "source_sha256": digest
                    })

    chunks.extend(audited_source_chunks(doc_title, digest))

    print(
        f"  -> {doc_title}: {total_pages} sayfadan {len(chunks)} chunk üretildi "
        f"[tablo: {table_count}, nav-temizlenen sayfa: {nav_cleaned_count}]"
    )
    return chunks


def audited_source_chunks(doc_title, digest):
    """Audited source tables, attached to the actual fact sheet PDF/pages.

    This does not infer missing PDF cells. Values share the source-audited UI
    tables and retain the units after the previously verified conversions.
    """
    source_versions = {
        "Microsoft_2024_Sustainability_Report.pdf":
            "7445f2725f6814d2f960bd439dc7bb3ae5ac57670bd10de9b609aa9403b31595",
        "Microsoft_2025_Sustainability_Report.pdf":
            "7c20672f907103daa14a0c10c1ed8407f693108ad1869836ae348bc7c397aad9",
        "Microsoft_2026_Environmental_Data_Fact_Sheet.pdf":
            "0fd180837df00b3427c3eae484a492224b8f18c381e82a2aed98b04553a197f6",
        "2026-Microsoft-Environmental-Sustainability-Report-PDF.pdf":
            "20918e9fc4a02241f55d12f1f5b6228a832b706499f9963a1a3f91e3d3e693ba",
    }
    if doc_title not in source_versions:
        return []
    if digest != source_versions[doc_title]:
        raise ValueError(f"Audited PDF source version changed: {doc_title}")
    if doc_title in ("Microsoft_2024_Sustainability_Report.pdf", "Microsoft_2025_Sustainability_Report.pdf"):
        publication, fiscal, page = ("2024", "FY23", 19) if "2024" in doc_title else ("2025", "FY24", 21)
        frame = get_carbon_removal_df()
        rows = []
        for _, row in frame.iterrows():
            value = "[NOT REPORTED]" if row[fiscal] != row[fiscal] else f"{row[fiscal]:.0f}"
            content = (f"[SOURCE AUDITED TABLE]\nMetric: {row['Metric']} (mt)\n{fiscal}: {value}\n"
                       "Basis: contracted multi-year future deliveries; allocations are not realized removals or credits retired in that year.")
            rows.append({"year": publication, "title": f"{doc_title} (p.{page})",
                         "content": format_chunk_with_metadata(doc_title, publication, page, content, is_table=True),
                         "type": "audited_table", "page": page, "source_sha256": digest})
        return rows
    water = get_water_metrics_df()
    annual = water['Metric'] == "Water Replenishment (million m3)"
    if "Fact_Sheet" in doc_title:
        sources = ((get_carbon_emissions_df(), 3, "mtCO2e"),
                   (get_energy_metrics_df(), 6, None), (water[~annual], 7, None),
                   (get_waste_metrics_df(), 7, None), (get_waste_prevention_df(), 8, None))
    else:
        sources = ((water[annual], 25, None),)
    chunks = []
    for frame, page, default_unit in sources:
        fiscal = [name for name in frame.columns if name.startswith("FY")]
        table = [["Metric (Unit)"] + [name.replace("_Baseline", "") for name in fiscal]]
        for _, row in frame.iterrows():
            unit = row.get("Unit", default_unit)
            values = [None if row[name] != row[name] else row[name] for name in fiscal]
            table.append([f"{row['Metric']} ({unit})"] + values)
        for content in table_row_evidence(table, TARGET_CHUNK_SIZE):
            chunks.append({
                "year": "2026", "title": f"{doc_title} (p.{page})",
                "content": format_chunk_with_metadata(doc_title, "2026", page,
                    "[SOURCE AUDITED TABLE]\n" + content + ("\nInventory scope: FY25 includes cloud hardware packaging; prior years were not adjusted. Construction/deconstruction waste is excluded. On-site prevention must not be added to off-site diversion." if page in (7, 8) and "Waste" in content else ""), is_table=True),
                "type": "audited_table", "page": page, "source_sha256": digest,
            })
    if doc_title == "2026-Microsoft-Environmental-Sustainability-Report-PDF.pdf":
        disclosure = get_carbon_removal_disclosures_df().iloc[0]
        content = (f"[SOURCE AUDITED TABLE]\nMetric: {disclosure['Metric']} (mt)\n"
                   f"{disclosure['Fiscal_Year']}: {disclosure['Disclosure']}\n"
                   f"Basis: {disclosure['Measurement_Basis']}. Exact total, technology shares and realized removals are not reported here; do not treat 45 million as an exact scalar.")
        chunks.append({"year": "2026", "title": f"{doc_title} (p.32)",
                       "content": format_chunk_with_metadata(doc_title, "2026", 32, content, is_table=True),
                       "type": "audited_table", "page": 32, "source_sha256": digest})
    return chunks


def run_ingestion(pdf_files=None, db_path=DB_PATH, embedder=None):
    """Build all sources/vectors first; atomically publish a validated corpus."""
    pdf_files = sorted(glob.glob("docs/*.pdf") if pdf_files is None else pdf_files)
    if not pdf_files:
        raise ValueError("No PDF sources found")
    all_chunks = []
    manifest = []
    for pdf_path in pdf_files:
        chunks = process_pdf(pdf_path)
        if not chunks:
            raise ValueError(f"No evidence extracted from {pdf_path}")
        all_chunks.extend(chunks)
        manifest.append({"filename": os.path.basename(pdf_path), "sha256": source_hash(pdf_path)})
    if embedder is None:
        # Import/load the heavyweight model only when actual indexing is requested.
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)
    embeddings = embedder.encode(
        [f"search_document: {chunk['content']}" for chunk in all_chunks],
        batch_size=16, show_progress_bar=True, normalize_embeddings=True,
    )
    count = replace_index(db_path, all_chunks, embeddings, EMBEDDING_MODEL_NAME, manifest)
    print(f"[SUCCESS] Published {count} chunks to {db_path}")
    return count


if __name__ == "__main__":
    run_ingestion()
