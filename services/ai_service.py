import os
import re
import json
import unicodedata
from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-3.5-flash"
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
_KEYWORD_STOPWORDS = {
    "para", "com", "sem", "sobre", "entre", "ate", "desde", "como", "quando",
    "onde", "porque", "porem", "tambem", "nao", "sim", "mais", "menos", "muito",
    "muita", "muitos", "muitas", "este", "esta", "esse", "essa", "isso", "aquele",
    "aquela", "ele", "ela", "eles", "elas", "voce", "voces", "seu", "sua", "seus",
    "suas", "ser", "sao", "foi", "foram", "era", "eram", "estar", "esta", "estao",
    "ter", "tem", "tinha", "haver", "fazer", "faz", "pode", "podem", "deve", "devem",
    "the", "and", "for", "with", "you", "your", "our", "will", "are", "not", "have",
    "has", "from", "that", "this", "these", "those", "able", "work", "working", "years",
    "year", "plus", "nice", "team", "teams", "role", "job", "company", "companies",
    "responsabilidades", "atribuicoes", "requisitos", "diferenciais", "beneficios",
    "atividades", "conhecimento", "conhecimentos", "necessario", "desejavel", "vaga",
    "cargo", "area", "atuar", "trabalhar", "nivel", "superior",
    "completo", "ainda", "incluindo", "problemas", "familiaridade", "composition",
    "distribuido", "documentado", "componentizacao", "bibliotecas", "e/ou",
    "merge", "rebase", "side", "multi", "por", "das", "dos", "uma", "nas", "nos",
    "aos", "mas", "que", "buscamos", "boas", "capacidade", "complexos", "empresa",
    "codigo", "limpo", "testavel", "moderno", "ativo", "etc",
    # Termos genéricos que NUNCA devem ser palavras-chave técnicas
    "apaixonado", "apaixonada", "apaixonados", "apaixonadas",
    "sólida", "solida", "sólidos", "sólidas", "solidos", "solidas",
    "estratégico", "estratégica", "estratégicos", "estratégicas",
    "legados", "legado", "levantamento", "levantamentos",
    "desenvolvedor", "desenvolvedora", "desenvolvedores", "desenvolvedoras",
    "pleno", "junior", "sênior", "senior", "estagiario", "estagiária",
    "experiência", "experiencias", "experiencia",
    "principais", "principal", "ciclo", "funcionalidades", "funcionalidade",
    "apoio", "apoiar", "soluções", "solucao", "solucoes",
    "processos", "processo", "ágeis", "agil", "ágil", "agis", "geis",
    "time", "times", "equipe", "equipes",
    # Termos genéricos adicionais comuns em descrições de vaga
    "oferecemos", "oferece", "oferecer", "oferecida", "oferecidos",
    "ambiente", "ambientes", "dinâmico", "dinâmica", "dinâmicos", "dinâmicas",
    "trabalho", "trabalhos", "trabalhando", "trabalhar",
    "técnicos", "técnica", "técnicas", "tecnico",
    "diários", "diária", "diárias",
    "requer", "requerido", "requeridos", "requisitos",
    "conhecimento", "conhecimentos", "domínio", "dominio",
}

# Termos técnicos curtos que valem a pena capturar mesmo com poucos caracteres.
_SHORT_TECH_TOKENS = {"c#", "c++", "js", "ts", "go", "ai", "bi", "ui", "ux", "ml"}

_WORD_RE = re.compile(r"[a-z\u00e0-\u00ff][a-z\u00e0-\u00ff0-9\.\+#/\-]*")


def _strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def _count_keyword(word: str, counts: dict) -> None:
    if len(word) > 18:
        return
    if len(word) < 3 and word not in _SHORT_TECH_TOKENS:
        return
    if _strip_accents(word) in _KEYWORD_STOPWORDS:
        return
    counts[word] = counts.get(word, 0) + 1


def _others_sort_key(word: str):
    if word.endswith("ndo"):
        rank = 0
    elif word.endswith(("ar", "er", "ir")):
        rank = 1
    else:
        rank = 2
    return (rank, -len(word), word)


def _extract_job_keywords(text: str, max_frequent: int = 40, max_others: int = 200):
    counts = {}
    for raw in _WORD_RE.findall((text or "").lower()):
        token = raw.strip(".-/")
        _count_keyword(token, counts)
        if len(token) >= 8:
            for part in re.split(r"[/\-.]", token):
                if part and part != token:
                    _count_keyword(part, counts)

    frequent = sorted(
        [(w, c) for w, c in counts.items() if c >= 2],
        key=lambda item: (-item[1], item[0]),
    )[:max_frequent]
    frequent_set = {w for w, _ in frequent}
    others = sorted(
        (w for w, c in counts.items() if c == 1 and w not in frequent_set),
        key=_others_sort_key,
    )[:max_others]
    return frequent, others


def _format_job_keywords(keywords: list) -> str:
    return ", ".join(f"{w} ({c}x)" if c > 1 else w for w, c in keywords)


def _normalize_for_count(text: str) -> str:
    return _strip_accents(text.lower())


def _count_occurrences_in_text(text: str, word: str) -> int:
    norm_text = _normalize_for_count(text)
    norm_word = _strip_accents(word.lower())
    if not norm_word:
        return 0
    patterns = [re.escape(norm_word)]
    if not norm_word.endswith('s'):
        patterns.append(re.escape(norm_word + 's'))
    else:
        patterns.append(re.escape(norm_word[:-1]))
    total = 0
    for pat in patterns:
        total += len(re.findall(r'\b' + pat + r'\b', norm_text))
    return total


def _adjust_keyword_frequency(data: dict, frequent_keywords: list, other_keywords: list) -> dict:
    all_keywords = {}
    for w, c in frequent_keywords:
        all_keywords[w] = c
    for w in other_keywords:
        all_keywords[w] = 1

    fields_to_check = ["resumo_adaptado", "objetivo_adaptado", "carta_apresentacao", "titulo_adaptado"]
    for i in range(1, 10):
        fields_to_check.append(f"experiencia_adaptada_{i}")

    for w, target in all_keywords.items():
        norm_w = _strip_accents(w.lower())
        skills_text = data.get("skills_adaptadas", "")
        skills_list = [s.strip() for s in skills_text.split(",") if s.strip()]

        total = 0
        for field in fields_to_check:
            text = data.get(field, "")
            total += _count_occurrences_in_text(text, w)

        skills_count = sum(1 for s in skills_list if _strip_accents(s.lower()) == norm_w)
        skills_contribution = min(skills_count, 1)
        total += skills_contribution

        if total > target * 2:
            if skills_count > 1:
                found = False
                new_skills = []
                for s in skills_list:
                    if _strip_accents(s.lower()) == norm_w:
                        if not found:
                            new_skills.append(s)
                            found = True
                    else:
                        new_skills.append(s)
                data["skills_adaptadas"] = ", ".join(new_skills)
                print(f"  Correção: reduzidas duplicatas de '{w}' nas skills")

    return data


def _call_gemini(client, prompt: str) -> str:
    """Chama o Gemini. Levanta exceção em qualquer falha (o chamador faz o fallback)."""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.5,
            response_mime_type="application/json",
            max_output_tokens=8192,
        ),
    )
    return (response.text or "").strip()


def _call_groq(prompt: str) -> str:
    """
    Fallback via Groq. Tenta os modelos em ordem até um responder.
    Levanta RuntimeError com mensagem amigável se nada funcionar.
    """
    try:
        from groq import Groq
    except ImportError as e:
        raise RuntimeError(
            "Fallback do Groq indisponível: o pacote 'groq' não está instalado. "
            "Rode 'pip install -r requirements.txt' e reinicie o aplicativo."
        ) from e

    groq_api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY não configurada. Adicione a chave no arquivo .env para habilitar o fallback automático."
        )

    groq_client = Groq(api_key=groq_api_key, timeout=60)

    # Permite fixar um modelo via env (GROQ_MODEL); os demais viram reserva.
    configured = (os.environ.get("GROQ_MODEL") or "").strip()
    models = ([configured] if configured else []) + [m for m in GROQ_MODELS if m != configured]

    last_err = None
    for model in models:
        try:
            completion = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You must output valid JSON only, without markdown formatting."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            text = (completion.choices[0].message.content or "").strip()
            if text:
                print(f"Fallback via Groq concluído com sucesso (modelo: {model}).")
                return text
            last_err = RuntimeError(f"O modelo {model} retornou resposta vazia.")
        except Exception as e:
            last_err = e
            # Chave inválida costuma aparecer disfarçada de "servidor cheio".
            # Damos uma mensagem específica para o usuário corrigir o .env.
            if getattr(e, "status_code", None) in (401, 403):
                raise RuntimeError(
                    "GROQ_API_KEY inválida ou sem permissão. Verifique a chave no arquivo .env."
                ) from e
            print(f"Erro no Groq (modelo {model}): {e}")

    raise RuntimeError(
        "Nossos servidores de IA estão muito cheios no momento. Por favor, aguarde alguns instantes e tente novamente! "
        "(Gemini e Groq temporariamente indisponíveis)."
) from last_err


def adapt_resume(base_skills: str, job_description: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key or api_key == "":
        raise ValueError("GEMINI_API_KEY não configurada. Por favor, adicione sua chave no arquivo .env")

    # Extrai os termos da vaga para o modelo cobrir tudo sem stuffing.
    frequent_keywords, other_keywords = _extract_job_keywords(job_description)
    frequent_hint = _format_job_keywords(frequent_keywords) if frequent_keywords else \
        "(sem termos recorrentes detectados — cubra os principais termos técnicos da vaga)"
    others_hint = ", ".join(other_keywords) if other_keywords else "(sem termos adicionais relevantes)"

    prompt = f"""
Você é um especialista em recrutamento e redator de currículos otimizados para ATS (Applicant Tracking Systems).
Sua tarefa é analisar as habilidades/experiências passadas de um candidato e a descrição de uma vaga alvo, adaptando os textos rigorosamente sob as seguintes regras:

1. COBERTURA E FREQUÊNCIA EXATA DE PALAVRAS-CHAVE (CRÍTICO): Use as listas [TERMOS-CHAVE FREQUENTES NA VAGA] e [OUTROS TERMOS CITADOS NA VAGA] abaixo. Cada termo na lista [FREQUENTES] tem uma frequência EXATA indicada entre parênteses (ex.: "desenvolvimento (5x)" = o currículo deve conter EXATAMENTE 5 ocorrências). Sua obrigação é FAZER COM QUE O CURRÍCULO CONTE EXATAMENTE essa quantidade de ocorrências para cada termo. Se um termo aparece 5x na vaga, o currículo deve conter exatamente 5 ocorrências (não mais, não menos). Se aparece 2x, o currículo deve conter exatamente 2 ocorrências. Se aparece 1x, exatamente 1 ocorrência. Para os termos da lista [OUTROS], inclua apenas os que tiverem respaldo real no histórico, com no máximo 1 ocorrência cada. Nunca troque um termo da vaga por sinônimo. Use a forma EXATA (singular/plural, gerúndio/infinitivo, siglas e compostos como "PHP/Laravel", "Vue.js"). IMPORTANTE: a regra de VERACIDADE prevalece sobre a cobertura — se um termo da vaga (mesmo frequente) não tiver respaldo no histórico, NÃO invente; use o termo correlato mais próximo que o candidato realmente domina. Inclua também os verbos/gerúndios das responsabilidades na forma original (ex.: desenvolvendo, mantendo, evoluir, consumindo, otimizando, corrigindo).

1a. ANTI-STUFFING CRÍTICO: Se a vaga cita "php" apenas 2x, o currículo DEVE conter exatamente 2 ocorrências de "php" (não mais). Se o histórico do candidato já possui muitas menções a "php", REDUZA as ocorrências para exatamente o número da vaga. Substitua excessos por termos genéricos como "tecnologia", "ferramenta", "linguagem" ou remova a palavra de frases inteiras quando necessário. Esta é uma regra de PRIORIDADE MÁXIMA — o ATS penaliza keyword stuffing severamente.

2. CONTAGEM DE OCORRÊNCIAS (ANTI-STUFFING): Some as ocorrências do texto corrido (título + resumo + descrições de experiência) com as da lista de Habilidades. Cada termo deve aparecer EXATAMENTE o número de vezes indicado na vaga (não ultrapasse, nem fique abaixo). Trate singular e plural como o MESMO termo (ex.: "API" e "APIs" contam juntos). A lista de Habilidades é o lugar canônico das tecnologias: cada tecnologia aparece ali exatamente UMA vez. Mantenha as menções no texto corrido apenas nos espaços restantes após a contagem das Habilidades. Verbos e termos das responsabilidades continuam aparecendo no texto normalmente. Distribua as stacks entre as experiências — não repita a mesma stack em todas. Evite repetir o cargo (ex.: "Desenvolvedor") e o nível (ex.: "Pleno") no texto corrido. Os cabeçalhos 'titulo_experiencia' (Empresa - Cargo - datas) não entram nessa contagem.

3. VERBOS DE AÇÃO (TODA FRASE): A PRIMEIRA palavra de CADA frase do resumo e das descrições de experiência deve ser um verbo de ação forte (ex.: Desenvolvi, Implementei, Liderei, Otimizei, Estruturei, Automatizei, Integrei, Corrigi, Modelei, Analisei, Desenvolvo, Otimizo). NUNCA comece uma frase com substantivo, gerúndio, "Atuação", "Responsável por", "Experiência em" ou termos nominais. Não comece duas frases seguidas com o mesmo verbo.

4. QUANTIFICAÇÃO VERDADEIRA (OBRIGATÓRIA QUANDO POSSÍVEL): Sempre que o histórico permitir CONTAR algo real, inclua o número correspondente: quantidade de projetos, empresas, anos de atuação, sistemas, integrações, entregas, tecnologias ou certificações que estejam EXPLICITAMENTE listados no histórico. Cada descrição de experiência deve conter ao menos uma quantidade verdadeira quando houver algo contável. NUNCA invente percentuais, valores em R$, tamanhos de equipe ou reduções de tempo/custo que não constem no histórico. Se não houver nada contável, mantenha o texto qualitativo.

5. DATAS (SÓ O ANO): Use SEMPRE o formato apenas com o ano — "YYYY". Nunca use mês (nada de "MM/YYYY", "Jan 2026", "Mês YYYY" ou "Month YYYY"), mesmo que o mês apareça no histórico: descarte-o. NUNCA invente o mês. Em período em andamento use "YYYY – Atual" (ex.: "2026 – Atual"); em período encerrado use "YYYY – YYYY" (ex.: "2024 – 2025"); se início e fim forem o mesmo ano, use só "YYYY" (ex.: "2024"). Mantenha sempre o separador "–".

6. SEM SÍMBOLOS OU GRÁFICOS: Nunca use emojis, gráficos ou símbolos. Ao citar proficiência, use palavras (ex: "inglês fluente", "conhecimento avançado").

7. FORMATO CORRIDO (SEM BULLET POINTS): Sistemas ATS podem falhar ao ler bullet points ou colunas. Escreva tudo de forma corrida, separando no máximo por quebras de linha. NUNCA use marcadores de lista. Mantenha cada frase enxuta (aprox. 15 a 25 palavras) para não desequilibrar o tamanho dos tópicos.

8. TÍTULO: Copie o cargo da vaga INCLUINDO o nível/senioridade (ex.: "Desenvolvedor Pleno"), no formato "Cargo | Palavra-Chave 1 | Palavra-Chave 2". O nível nunca pode ser omitido: se a vaga exige "Pleno", o título deve conter "Pleno". Normalize formas com gênero do anúncio (ex.: "Desenvolvedor(a)" vira "Desenvolvedor"; "Analista(a)" vira "Analista").

9. OBJETIVO: Escrever de forma direta o cargo, área e função que gostaria de atuar.

10. RESUMO: Comece com um verbo de ação e um posicionamento profissional (ex.: "Desenvolvo sistemas corporativos..." ou "Construí APIs REST..."). TODAS as frases começam com verbo de ação. Foque em cases do histórico relevantes para a posição, encaixando os termos-chave na frequência correta (sem stuffing) e incluindo números verdadeiros.

11. EXPERIÊNCIAS (Título e Descrição): Crie um campo 'experiencias' que seja uma LISTA (array) JSON contendo objetos para cada empresa do histórico. Cada objeto deve ter 'titulo_experiencia' no formato "Empresa - Cargo - 2026 – Atual" (ou "2024 – 2025"; se início e fim forem o mesmo ano, use só "2024"), usando SEMPRE só o ano, e 'experiencia_adaptada' com a descrição composta por frases iniciadas por verbos de ação, por ao menos uma quantidade verdadeira do histórico e respeitando o TAMANHO definido na regra 17 (4 a 5 linhas).

12. SKILLS (Skillset): Liste, separados por vírgula, TODAS as tecnologias centrais da vaga que o candidato realmente domina. As linguagens, frameworks, bancos de dados e ferramentas exigidos nos requisitos da vaga DEVEM obrigatoriamente aparecer aqui, mesmo que já tenham sido citados no texto. Complete com outras ferramentas relevantes do histórico. Nunca inclua tecnologia que o candidato não tenha.

13. VERACIDADE: Nunca invente experiências, empresas, cargos, tecnologias ou métricas que o candidato não citou.

14. CARTA DE APRESENTAÇÃO: Crie uma cover letter (carta de apresentação) persuasiva e curta (3 a 4 parágrafos), alinhando as experiências base com os requisitos da vaga. Inicie com uma saudação formal/moderna e finalize com uma chamada para ação.

15. FORMATO JSON E QUEBRAS DE LINHA: NUNCA insira quebras de linha reais dentro das strings do JSON (use \\n para quebras na carta de apresentação ou no resumo). NUNCA use aspas duplas (") dentro dos textos (use aspas simples). Seu retorno deve ser um JSON perfeitamente válido e escapado.

16. PONTUAÇÃO: Todos os textos descritivos (resumos, objetivos e descrições de experiências) devem terminar obrigatoriamente com um ponto final (.).

17. TAMANHO DAS DESCRIÇÕES DE EXPERIÊNCIA (LINHAS): Cada 'experiencia_adaptada' deve ocupar de 4 a 5 linhas quando renderizada — o layout do currículo comporta aproximadamente 70 a 80 caracteres por linha. Use como alvo: 4 linhas ≈ 230 a 300 caracteres (~35 a 48 palavras); 5 linhas ≈ 320 a 360 caracteres (~50 a 57 palavras). Escreva a descrição como um único parágrafo corrido, SEM quebras de linha manuais: o número de linhas resulta apenas da quebra automática. Use de 2 a 3 frases (todas iniciando por verbo de ação) para atingir esse tamanho. Quando houver 3 experiências, a SOMA das linhas deve ser EXATAMENTE 13 — isto é, uma experiência com 5 linhas e as outras duas com 4 linhas (ex.: 4/5/4; a ordem não importa). Nunca produza descrição com menos de 4 nem com mais de 5 linhas. A veracidade (regras 4 e 13) prevalece: nunca invente fatos nem encha linguiça para alcançar o tamanho; se o histórico do período for curto, aproxime o tamanho o máximo possível sem inventar.

CHECKLIST FINAL (revise silenciosamente antes de responder):
- CADA termo de [TERMOS-CHAVE FREQUENTES NA VAGA] aparece EXATAMENTE o número de vezes indicado entre parênteses (não mais, não menos)?
- NENHUM termo está em excesso (keyword stuffing)? Se sim, reduza para o número exato da vaga.
- Cada experiência tem pelo menos um número/quantidade verdadeira do histórico (número de projetos, pessoas, sistemas, etc.)?
- Cada termo de [OUTROS TERMOS CITADOS NA VAGA] aparece no máximo 1 vez?
- A primeira palavra de CADA frase (resumo e experiências) é um verbo de ação?
- Cada experiência tem pelo menos um número/quantidade verdadeira do histórico?
- Nenhum percentual, valor em R$ ou tamanho de equipe foi inventado?
- O título inclui o nível/senioridade exato da vaga (ex.: "Pleno")?
- As tecnologias centrais da vaga aparecem na lista de Habilidades (cada uma 1x)?
- Todas as datas estão no formato só-ano ("YYYY", "YYYY – YYYY" ou "YYYY – Atual"), sem mês inventado?
- Cada 'experiencia_adaptada' fica entre 4 e 5 linhas (~230–300 caracteres para 4 linhas; ~320–360 para 5)? Havendo 3 experiências, a soma é exatamente 13 linhas (uma com 5 e duas com 4)?

[TERMOS-CHAVE FREQUENTES NA VAGA — cada termo deve aparecer NO CURRÍCULO exatamente o número de vezes indicado entre parênteses]:
{frequent_hint}

[OUTROS TERMOS CITADOS NA VAGA — inclua apenas os que tiverem respaldo no histórico, no máximo 1 vez cada]:
{others_hint}

[HABILIDADES E EXPERIÊNCIAS BASE DO CANDIDATO]:
{base_skills}

[DESCRIÇÃO DA VAGA ALVO]:
{job_description}

Forneça o resultado EXATAMENTE no formato JSON abaixo, garantindo chaves e formato adequados:
{{
    "titulo_adaptado": "Desenvolvedor Pleno | PHP | Laravel",
    "objetivo_adaptado": "Cargo, área e função que gostaria de atuar.",
    "resumo_adaptado": "Texto corrido com cases de sucesso e experiências relevantes para a posição.",
    "experiencias": [
        {{
            "titulo_experiencia": "Empresa 1 - Cargo - 2026 – Atual",
            "experiencia_adaptada": "Desenvolvi ... Implementei ... Otimizei ...."
        }},
        {{
            "titulo_experiencia": "Empresa 2 - Cargo - 2024 – 2025",
            "experiencia_adaptada": "Criei ... Integrei ... Estruturei ...."
        }},
        {{
            "titulo_experiencia": "Empresa 3 - Cargo - 2024",
            "experiencia_adaptada": "Automatizei ... Documentei ...."
        }}
    ],
    "skills_adaptadas": "PHP, Laravel, Vue.js, MySQL, Redis",
    "carta_apresentacao": "Olá, [Nome ou Empresa]... \\n\\nCorpo da carta focando nos resultados... \\n\\nEncerramento."
}}
"""

    raw_text = ""
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        raw_text = _call_gemini(client, prompt)
        if not raw_text:
            raise RuntimeError("O Gemini retornou uma resposta vazia.")
    except Exception as gemini_err:
        print(f"Erro no Gemini: {gemini_err}")
        print("Alternando imediatamente para o fallback via Groq...")
        raw_text = _call_groq(prompt)

    try:
        from json_repair import repair_json
        
        repaired_string = repair_json(raw_text)
        data = json.loads(repaired_string)
        
        expected_keys = ["titulo_adaptado", "objetivo_adaptado", "resumo_adaptado", "skills_adaptadas", "carta_apresentacao"]
        for key in expected_keys:
            if key not in data:
                data[key] = ""
                
        if "experiencias" in data and isinstance(data["experiencias"], list):
            for i, exp in enumerate(data["experiencias"]):
                idx = i + 1
                data[f"titulo_experiencia_{idx}"] = exp.get("titulo_experiencia", "")
                data[f"experiencia_adaptada_{idx}"] = exp.get("experiencia_adaptada", "")
        else:
            data["titulo_experiencia_1"] = "Falha ao ler experiências."
            data["experiencia_adaptada_1"] = "Falha ao ler experiências."

        data = _adjust_keyword_frequency(data, frequent_keywords, other_keywords)

        return data
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear JSON da IA: {e}")
        print(f"Texto cru retornado: {raw_text}")
        return {
            "titulo_adaptado": "Falha no Título",
            "objetivo_adaptado": "Falha no Objetivo",
            "resumo_adaptado": "Falha ao gerar resumo.",
            "titulo_experiencia_1": "Motivo da Falha:",
            "experiencia_adaptada_1": raw_text,
            "skills_adaptadas": "Falha nas skills",
            "carta_apresentacao": ""
        }
