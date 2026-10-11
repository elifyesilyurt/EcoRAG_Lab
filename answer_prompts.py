"""Shared production/evaluation prompts for evidence-grounded narrative answers."""
from temporal_scope import temporal_evidence_instruction


def build_rag_prompts(context: str, query: str, lang: str):
    if lang == 'tr':
        system = ('Sen Microsoft Sürdürülebilirlik Raporları uzmanısın. Soruyu doğrudan yanıtla. '
                  'Yalnızca bağlamdaki kanıtları kullan. İstenen bilgi yoksa açıkça belirt. '
                  'Kaynak sayfasını belirt; rapor yılı ile mali yılı, mali yıl ile takvim yılını ayır. ')
        user = f'Bağlam:\n{context}\n\nSoru: {query}'
    else:
        system = ('You are a Microsoft Sustainability Report expert. Answer directly using only context evidence. '
                  'Explicitly state when requested information is unavailable. Cite source pages. '
                  'Distinguish publication years, fiscal years and calendar years. ')
        user = f'Context:\n{context}\n\nQuestion: {query}'
    system += ('Qualified disclosures (more than, nearly, approximately) are not exact scalars. '
               'Contracted future deliveries are not realized annual removals. Missing allocations are not zero. '
               'Do not invent technology shares, certifications or target achievement from aggregate data. ')
    return system + temporal_evidence_instruction(query), user
