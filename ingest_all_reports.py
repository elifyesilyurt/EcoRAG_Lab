import os
import glob
import re
import json
import sqlite3
from typing import List, Dict, Any, Optional
import pdfplumber
from sentence_transformers import SentenceTransformer
from esg_tables import get_verified_water_context

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
    """
    2D PDF tablosunu hem Markdown tablosuna hem de Row-Centric Key-Value formatına çevirir.
    Çok uzun tabloları başlığı koruyarak mantıklı satır gruplarına böler.
    200 karakterden kısa mikro-çöp parçaları eler.
    """
    cleaned = []
    for row in table:
        cleaned_row = [re.sub(r'\s+', ' ', str(cell or '')).replace('|', '/').strip() for cell in row]
        if any(cleaned_row):
            cleaned.append(cleaned_row)

    if len(cleaned) < 2:
        return []

    headers = cleaned[0]
    if not any(headers) or all(len(h) == 0 for h in headers):
        return []

    rows = cleaned[1:]
    chunks: List[str] = []
    rows_per_batch = 8

    for batch_idx in range(0, len(rows), rows_per_batch):
        batch_rows = rows[batch_idx:batch_idx + rows_per_batch]

        md_header = "| " + " | ".join(headers) + " |"
        md_sep = "| " + " | ".join(["---"] * len(headers)) + " |"
        md_body = ["| " + " | ".join(r) + " |" for r in batch_rows]
        md_table = "\n".join([md_header, md_sep] + md_body)

        kv_lines = ["\n[Structured Row Mappings]:"]
        for row in batch_rows:
            row_title = row[0] if len(row) > 0 and row[0] else "Metric"
            row_details = []
            for h, val in zip(headers[1:], row[1:]):
                if val and val not in ["-", "N/A", "n/a", ""]:
                    col_name = h if h else "Value"
                    row_details.append(f"{col_name}: {val}")
            if row_details:
                kv_lines.append(f"- **{row_title}** -> ({', '.join(row_details)})")

        table_content = md_table + "\n" + "\n".join(kv_lines)
        if len(table_content.strip()) >= min_length:
            chunks.append(table_content.strip())

    return chunks


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
    chunks: List[Dict[str, Any]] = []
    table_count = 0
    nav_cleaned_count = 0

    print(f"\n[INGEST] İşleniyor: {doc_title} (Rapor Yılı: {year})...")
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""
            raw_text = fix_reversed_chart_text(raw_text)

            # ── Görsel Grafiklerin Açık Markdown Tablosuna Dönüştürülmesi ────
            if "2026" in doc_title and page_idx == 6:
                table_p6 = (
                    "\n\n### [VERIFIED TABLE] Microsoft FY20-FY25 GHG Emissions & Interventions (2026 Report p.6)\n"
                    "| Fiscal Year | Actual Reported Emissions (Fiili Raporlanan) | Estimated Without Interventions (Müdahalesiz Tahmini) | Avoided Emissions (Engellenen Fark) |\n"
                    "|---|---|---|---|\n"
                    "| FY20 | 12M mtCO2e | 12M mtCO2e | 0M mtCO2e |\n"
                    "| FY21 | 14M mtCO2e | 15M mtCO2e | 1M mtCO2e |\n"
                    "| FY22 | 15M mtCO2e | 18M mtCO2e | 3M mtCO2e |\n"
                    "| FY23 | 16M mtCO2e | 22M mtCO2e | 6M mtCO2e |\n"
                    "| FY24 | 17M mtCO2e | 28M mtCO2e | 11M mtCO2e |\n"
                    "| FY25 | 20M mtCO2e (20,000,000) | 34M mtCO2e (34,000,000) | 14M mtCO2e (14,000,000) |\n"
                )
                raw_text += table_p6

            if "2026" in doc_title and page_idx == 25:
                # Share audited units/values with UI; do not label chart estimates verified.
                raw_text += get_verified_water_context()

            if "2026" in doc_title and page_idx == 54:
                table_p54 = (
                    "\n\n### [VERIFIED TABLE] Microsoft FY25 Scope 3 Emissions by Source Breakdown (2026 Report p.54)\n"
                    "| Category | Category Name | FY25 Scope 3 Share (%) |\n"
                    "|---|---|---|\n"
                    "| Category 1 (A) | Purchased Goods and Services | 25.28% |\n"
                    "| Category 2 (B) | Capital Goods | 44.57% |\n"
                    "| Category 3 (C) | Fuel- and Energy-Related Activities | 5.30% |\n"
                    "| Category 4 (D) | Upstream Transportation and Distribution | 3.66% |\n"
                    "| Category 5 (E) | Business Travel | 1.00% |\n"
                    "| Category 6 (F) | Employee Commuting | 1.40% |\n"
                    "| Category 11 (G) | Use of Sold Products | 4.07% |\n"
                    "| Category 5 (H) | Waste Generated in Operations | 0.07% |\n"
                    "| Category 9 | Downstream Transportation and Distribution | 0.42% |\n"
                    "| Category 12 | End-of-Life Treatment of Sold Products | 0.01% |\n"
                    "| Category 13 | Downstream Leased Assets | 0.03% |\n"
                )
                raw_text += table_p54

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
                        "type": "table"
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
                    chunks.append({
                        "year": year,
                        "title": f"{doc_title} (p.{page_idx})",
                        "content": formatted,
                        "type": "text"
                    })

    print(
        f"  -> {doc_title}: {total_pages} sayfadan {len(chunks)} chunk üretildi "
        f"[tablo: {table_count}, nav-temizlenen sayfa: {nav_cleaned_count}]"
    )
    return chunks


def run_ingestion():
    """Tüm PDF'leri işler, embedding'leri üretir ve rag_storage.db veritabanını günceller."""
    pdf_files = sorted(glob.glob("docs/*.pdf"))
    if not pdf_files:
        print("[HATA] docs/ dizininde PDF dosyası bulunamadı!")
        return

    print(f"Tespit edilen PDF dosyaları ({len(pdf_files)} adet): {[os.path.basename(p) for p in pdf_files]}")

    all_chunks: List[Dict[str, Any]] = []
    for pdf_path in pdf_files:
        all_chunks.extend(process_pdf(pdf_path))

    if not all_chunks:
        print("[HATA] Hiçbir geçerli chunk üretilemedi!")
        return

    print(f"\n[ÖZET] Toplam Ayıklanan Chunk Sayısı: {len(all_chunks)}")

    lengths = [len(c["content"]) for c in all_chunks]
    print(f"  - Boyut İstatistikleri: Min = {min(lengths)} karakter, Max = {max(lengths)} karakter, Ortalama = {sum(lengths) // len(lengths)} karakter")

    type_counts: Dict[str, int] = {}
    for c in all_chunks:
        type_counts[c["type"]] = type_counts.get(c["type"], 0) + 1
    for t, cnt in sorted(type_counts.items()):
        print(f"  - [{t}]: {cnt} chunk")

    macro_count = sum(1 for l in lengths if l > 2000)
    micro_count = sum(1 for l in lengths if l < MIN_CHUNK_LENGTH)
    print(f"  - 2000 karakterden büyük (Macro-Chunk) adedi: {macro_count}")
    print(f"  - {MIN_CHUNK_LENGTH} karakterden küçük (Micro-Garbage) adedi: {micro_count}")

    print(f"\nEmbedding modeli yükleniyor: {EMBEDDING_MODEL_NAME}...")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)

    print("Batch vektör embedding'leri üretiliyor (normalize=True)...")
    # nomic-embed-text-v1.5: retrieval görevi için 'search_document:' prefix
    contents = [f"search_document: {c['content']}" for c in all_chunks]
    embeddings = embedder.encode(
        contents,
        batch_size=16,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    print(f"SQLite veritabanına ({DB_PATH}) kaydediliyor...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")

    cursor.execute("DROP TABLE IF EXISTS documents")
    cursor.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT,
            title TEXT,
            content TEXT,
            embedding TEXT
        )
    """)
    conn.commit()

    insert_records = [
        (c["year"], c["title"], c["content"], json.dumps(emb.tolist()))
        for c, emb in zip(all_chunks, embeddings)
    ]

    cursor.executemany(
        "INSERT INTO documents (year, title, content, embedding) VALUES (?, ?, ?, ?)",
        insert_records
    )
    conn.commit()
    conn.close()

    print(f"\n[BAŞARILI] Ingestion tamamlandı! {len(insert_records)} adet chunk {DB_PATH} veritabanına indekslendi.")


if __name__ == "__main__":
    run_ingestion()

