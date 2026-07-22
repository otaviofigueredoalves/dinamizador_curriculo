import os
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from services.scraper import scrape_linkedin_job, scrape_linkedin_title_company, scrape_linkedin_profile
from services.pdf_service import extract_text_from_pdf
from services.ai_service import adapt_resume
from services.doc_service import process_resume_template, extract_text_from_docx, convert_docx_to_pdf

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape-info', methods=['POST'])
def scrape_info():
    data = request.get_json()
    url = data.get('url', '')
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400
    
    info = scrape_linkedin_title_company(url)
    return jsonify(info)

@app.route('/api/scrape-profile', methods=['POST'])
def scrape_profile():
    if 'pdf_file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
        
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400
        
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        
        text = extract_text_from_pdf(input_path)
        if not text:
            return jsonify({"error": "Falha ao extrair texto do PDF."}), 400
            
        return jsonify({"text": text})
    return jsonify({"error": "Formato inválido. Apenas .pdf"}), 400

@app.route('/process', methods=['POST'])
def process():
    if 'template_file' not in request.files:
        return "Nenhum arquivo enviado", 400
        
    file = request.files['template_file']
    linkedin_url = request.form.get('linkedin_url', '')
    user_skills = request.form.get('user_skills', '')
    
    if file.filename == '':
        return "Nenhum arquivo selecionado", 400
        
    if file and file.filename.endswith('.docx'):
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        try:
            linkedin_url = request.form.get('linkedin_url', '').strip()
            
            job_description = ""
            if linkedin_url.startswith('http'):
                job_description = scrape_linkedin_job(linkedin_url)
                if not job_description or "Security Check" in job_description:
                    # Fallback, caso o scrape falhe, vamos tentar rodar mesmo assim (mas a qualidade cai)
                    job_description = "Falha ao extrair vaga. Baseie-se apenas na tentativa de URL: " + linkedin_url
            else:
                # O usuário colou o texto bruto da vaga (ex: contorno do Cloudflare do Indeed)
                job_description = linkedin_url
                
            extracted_cv_text = extract_text_from_docx(input_path)
            
            # Junta o que o usuário escreveu nas tags com o que já existia no arquivo base
            combined_skills_and_history = extracted_cv_text
            if user_skills.strip():
                combined_skills_and_history = f"[INFORMAÇÕES EXTRAS/SKILLS DO USUÁRIO]:\n{user_skills}\n\n[CONTEÚDO EXTRAÍDO DO CURRÍCULO BASE]:\n{extracted_cv_text}"
                
            result_context = adapt_resume(combined_skills_and_history, job_description)
            
            raw_title = result_context.get("titulo_adaptado", "CV")
            job_title = raw_title.split("|")[0].strip()
            
            safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', job_title)
            safe_title = re.sub(r'\s+', '-', safe_title).upper()
            if not safe_title:
                safe_title = "CURRICULO"
                
            date_str = datetime.now().strftime("%Y%m%d")
            
            output_filename = f"CV_{safe_title}-{date_str}.docx"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            process_resume_template(input_path, output_path, result_context)
            convert_docx_to_pdf(output_path, app.config['UPLOAD_FOLDER'])
            
            try:
                os.remove(input_path)
            except Exception:
                pass
                
            return jsonify({
                "success": True, 
                "filename": output_filename,
                "carta_apresentacao": result_context.get("carta_apresentacao", ""),
                "message": "Currículo adaptado com sucesso!"
            })
        except Exception as e:
            try:
                os.remove(input_path)
            except Exception:
                pass
            
            error_msg = str(e)
            if "503" in error_msg and "UNAVAILABLE" in error_msg:
                error_msg = "Os servidores da IA do Google estão sobrecarregados no momento. Por favor, tente novamente em alguns segundos."
                
            return jsonify({"success": False, "error": error_msg}), 500

@app.route('/download/<file_type>/<filename>')
def download_file(file_type, filename):
    if file_type == 'pdf':
        base = os.path.splitext(filename)[0]
        actual_filename = base + ".pdf"
        mimetype = "application/pdf"
    elif file_type == 'docx':
        actual_filename = filename
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        return "Tipo inválido", 400
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], actual_filename, as_attachment=True, mimetype=mimetype)

if __name__ == '__main__':
    # O Gunicorn é quem irá chamar o app em produção. 
    # Esta linha só roda se executar manualmente via `python app.py` (usado apenas em dev).
    app.run(host='0.0.0.0', port=5000, debug=False)
