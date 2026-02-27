import re
texto = 'DRA. WITKER / DRA LUCO / DR PEREZ / Dr. Soto / dra. ana / dr martin'
clean_text = re.sub(r'(?i)\bDr[a]?\b\.?\s*', '', texto)
print(repr(clean_text))
