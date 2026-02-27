import re
texto = 'DRA. WITKER / DRA LUCO / DR PEREZ / Dr. Soto'
clean_text = re.sub(r'(?i)\b(?:Dr|Dra)\.?\s*', '', texto)
print(repr(clean_text))
