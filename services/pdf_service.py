import pypdf

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extrair dados do PDF exportado pelo LinkedIn.
    """
    try:
        text_content = []
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text.strip())
        
        return "\n".join(text_content)
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        return ""
