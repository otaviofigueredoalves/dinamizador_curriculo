import os
from docxtpl import DocxTemplate

def process_resume_template(input_path: str, output_path: str, context: dict):
    """
    Carrega o template DOCX, injeta as variáveis (contexto) e salva um novo DOCX.
    As variáveis esperadas no template Word devem estar entre colchetes duplos ou duplas chaves,
    ex: {{ resumo_adaptado }} e {{ experiencia_adaptada }}
    """
    doc = DocxTemplate(input_path)
    doc.render(context)
    doc.save(output_path)

import docx

def extract_text_from_docx(file_path: str) -> str:
    """
    Usado para ler as experiências passadas do usuário diretamente do seu CV original.
    """
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text and not text.startswith("{{") and not text.endswith("}}"):
                full_text.append(text)
        return "\n".join(full_text)
    except Exception as e:
        print(f"Erro ao extrair texto do DOCX: {e}")
        return ""

import subprocess

def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str:
    """
    Converte um arquivo DOCX para PDF usando LibreOffice (modo headless).
    Retorna o caminho do arquivo PDF gerado.
    """
    try:
        # Chama o libreoffice em background para fazer a conversão
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", docx_path, "--outdir", output_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Constrói o caminho final esperado do PDF
        base_name = os.path.basename(docx_path)
        pdf_name = os.path.splitext(base_name)[0] + ".pdf"
        return os.path.join(output_dir, pdf_name)
    except subprocess.CalledProcessError as e:
        print(f"Erro ao converter para PDF: {e.stderr.decode()}")
        return ""
