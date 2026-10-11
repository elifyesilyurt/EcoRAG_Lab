# Narrative chunk boundaries

The recursive splitter used stripped overlap and recursive pieces in a concatenation without a separator. This could create `policy.Sentence` or join adjacent words. It also appended the chosen delimiter to the final split even when no delimiter existed in the source, and omitted the delimiter from recursively split pieces.

Overlap and recursive pieces now retain an explicit newline boundary. Only actual split delimiters are restored, including when a piece is recursively split. This preserves source punctuation without guessing new sentences. Whitespace normalization is allowed; text content must not be invented at boundaries.

Five regression checks cover sentence overlap, word overlap, recursive paragraphs, original terminal punctuation and unchanged short input. The index version is `column-row-evidence-v3`; rebuilds use the existing transactional publication and source hash checks. This change does not repair malformed words already present in PDF extraction, guarantee all headings are separated correctly, or establish semantic completeness of an excerpt.
