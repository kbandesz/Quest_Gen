
import io, math, re
from typing import Tuple
from pypdf import PdfReader
import mammoth  # for docx to text

def _read_pdf(f) -> str:
    reader = PdfReader(f)
    texts=[]
    for p in reader.pages:
        try:
            texts.append(p.extract_text() or "")
        except Exception:
            continue
    return "\n".join(texts)

def _read_docx(f) -> str:
    b = f.read() if hasattr(f,"read") else f
    result = mammoth.extract_raw_text(io.BytesIO(b))
    return result.value or ""

def _read_txt(f)->str:
    return f.read().decode("utf-8", errors="ignore") if hasattr(f,"read") else f.decode("utf-8", errors="ignore")

def extract_text_and_tokens(uploaded_file) -> Tuple[str,int]:
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        text=_read_pdf(uploaded_file)
    elif name.endswith(".docx"):
        text=_read_docx(uploaded_file)
    elif name.endswith(".txt"):
        text=_read_txt(uploaded_file)
    else:
        raise ValueError("Unsupported file type")
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'[ \t]+',' ',text).strip()
    words=len(re.findall(r"\S+",text))
    tokens=math.ceil(words/0.75)
    return text, tokens
