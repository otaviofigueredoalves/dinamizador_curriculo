import os
import json
from google import genai
from google.genai import types

def adapt_resume(base_skills: str, job_description: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key or api_key == "":
        raise ValueError("GEMINI_API_KEY não configurada. Por favor, adicione sua chave no arquivo .env")

    client = genai.Client(api_key=api_key)

    prompt = f"""
Você é um especialista em recrutamento e redator de currículos otimizados para ATS (Applicant Tracking Systems).
Sua tarefa é analisar as habilidades/experiências passadas de um candidato e a descrição de uma vaga alvo, adaptando os textos rigorosamente sob as seguintes regras:
1. FOCO EM PALAVRAS-CHAVE: Extraia e utilize as palavras-chave exatas da vaga, dando atenção extrema a siglas de metodologias e métricas de negócio exigidas (ex: OKRs, KPIs, Scrum, etc.). A ausência dessas siglas, se pedidas na vaga, reprova o candidato.
2. SEM SÍMBOLOS OU GRÁFICOS: Nunca use emojis, gráficos ou símbolos. Ao citar proficiência, use palavras (ex: "inglês fluente", "conhecimento avançado").
3. FORMATO CORRIDO (SEM BULLET POINTS): Sistemas ATS podem falhar ao ler bullet points ou colunas. Escreva tudo de forma corrida, separando no máximo por quebras de linha. NUNCA use marcadores de lista.
4. TÍTULO: Deve seguir o formato exato: "Cargo | Palavra-Chave 1 | Palavra-Chave 2"
5. OBJETIVO: Escrever de forma direta o cargo, área e função que gostaria de atuar.
6. HIGHLIGHTS (Resumo): Foque em cases de sucesso e experiências do histórico que sejam altamente relevantes para a posição atual. Adapte os cases conforme necessário para a vaga.
23. 7. EXPERIÊNCIAS (Título e Descrição): Crie um campo 'experiencias' que seja uma LISTA (array) JSON contendo objetos para cada empresa do histórico. Cada objeto deve ter 'titulo_experiencia' com o cabeçalho ("Empresa - Cargo - Senioridade 20XX - 20XX") e 'experiencia_adaptada' com a descrição.
24. 8. SKILLS (Skillset): Liste apenas ferramentas e recursos que o candidato tem vivência e que tenham relevância direta para a área/vaga. Separar por vírgula.
25. 9. VERACIDADE: Nunca invente experiências que o candidato não citou.
26. FORMATO JSON E QUEBRAS DE LINHA: NUNCA insira quebras de linha reais dentro das strings do JSON. Se precisar quebrar linha, use ESTRITAMENTE os caracteres '\\n' escapados. Seu retorno deve ser um JSON válido.

[HABILIDADES E EXPERIÊNCIAS BASE DO CANDIDATO]:
{base_skills}

[DESCRIÇÃO DA VAGA ALVO]:
{job_description}

Forneça o resultado EXATAMENTE no formato JSON abaixo, garantindo chaves e formato adequados:
{{
    "titulo_adaptado": "Cargo | Palavra-Chave 1 | Palavra-Chave 2",
    "objetivo_adaptado": "Cargo, área e função que gostaria de atuar.",
    "resumo_adaptado": "Texto corrido com cases de sucesso e experiências relevantes para a posição.",
    "experiencias": [
        {{
            "titulo_experiencia": "Empresa 1 - Cargo - Senioridade   20XX – 20XX",
            "experiencia_adaptada": "Descrição das funções, crescimento, eventos importantes e ferramentas da empresa 1."
        }},
        {{
            "titulo_experiencia": "Empresa 2 - Cargo - Senioridade   20XX – 20XX",
            "experiencia_adaptada": "Descrição das funções, crescimento, eventos importantes e ferramentas da empresa 2."
        }}
    ],
    "skills_adaptadas": "Ferramenta 1, Ferramenta 2, Recurso 3"
}}
"""

    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="application/json",
            max_output_tokens=4096,
        )
    )

    try:
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"):
            raw_text = "```".join(raw_text.rsplit("```", 1)[0:1])
        raw_text = raw_text.strip()
        
        # Usa strict=False para permitir quebras de linha reais que a IA gera por engano
        try:
            data = json.loads(raw_text, strict=False)
        except json.JSONDecodeError:
            # Fallback iterativo caso haja lixo ou chaves extras no fim
            while raw_text and not raw_text.endswith("}"):
                raw_text = raw_text[:-1]
            data = json.loads(raw_text, strict=False)
        
        expected_keys = ["titulo_adaptado", "objetivo_adaptado", "resumo_adaptado", "skills_adaptadas"]
        for key in expected_keys:
            if key not in data:
                data[key] = ""
                
        # Achatar a lista de experiências para variáveis numeradas _1, _2, _3...
        if "experiencias" in data and isinstance(data["experiencias"], list):
            for i, exp in enumerate(data["experiencias"]):
                idx = i + 1
                data[f"titulo_experiencia_{idx}"] = exp.get("titulo_experiencia", "")
                data[f"experiencia_adaptada_{idx}"] = exp.get("experiencia_adaptada", "")
        else:
            # Caso a IA falhe em gerar o array, gera o _1 vazio pra não quebrar o template
            data["titulo_experiencia_1"] = "Falha ao ler experiências."
            data["experiencia_adaptada_1"] = "Falha ao ler experiências."
                
        return data
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear JSON da IA: {e}")
        print(f"Texto cru retornado: {response.text}")
        return {
            "titulo_adaptado": "Falha no Título",
            "objetivo_adaptado": "Falha no Objetivo",
            "resumo_adaptado": "Falha ao gerar resumo.",
            "experiencia_adaptada": response.text,
            "skills_adaptadas": "Falha nas skills"
        }
