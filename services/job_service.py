"""
Serviço de busca de vagas: detecta a stack principal do candidato a partir
do texto base do currículo e busca vagas compatíveis (LinkedIn, Indeed, Gupy
e outros) via Google Jobs da SerpAPI.
"""
import os
import re
from urllib.parse import quote

import requests

# Famílias de tecnologia: chave canônica + aliases (regex, case-insensitive)
TECH_FAMILIES = [
    {
        "id": "php",
        "label": "PHP",
        "plain": "PHP",
        "search_label": "Desenvolvedor PHP",
        "aliases": [r"\bphp\b", r"\blaravel\b", r"\bwordpress\b", r"\bcodeigniter\b", r"\bmagento\b", r"\bsymfony\b", r"\bdrupal\b"],
    },
    {
        "id": "python",
        "label": "Python",
        "plain": "Python",
        "search_label": "Desenvolvedor Python",
        "aliases": [r"\bpython\b", r"\bdjango\b", r"\bflask\b", r"\bfastapi\b", r"\bpandas\b", r"\bselenium\b"],
    },
    {
        "id": "javascript",
        "label": "JavaScript",
        "plain": "JavaScript",
        "search_label": "Desenvolvedor JavaScript",
        "aliases": [r"\bjavascript\b", r"\btypescript\b", r"\breact\b", r"\bvue\b", r"\bangular\b", r"\bnode\.?js\b", r"\bnext\.?js\b"],
    },
    {
        "id": "java",
        "label": "Java",
        "plain": "Java",
        "search_label": "Desenvolvedor Java",
        "aliases": [r"\bjava\b", r"\bspring\b", r"\bhibernate\b"],
    },
    {
        "id": "csharp",
        "label": "C# / .NET",
        "plain": "C# .NET",
        "search_label": "Desenvolvedor C# .NET",
        "aliases": [r"\bc#\b", r"\bcsharp\b", r"\.net\b", r"\basp\.net\b"],
    },
    {
        "id": "go",
        "label": "Go (Golang)",
        "plain": "Go",
        "search_label": "Desenvolvedor Go",
        # '\bgo\b' sozinho gera muitos falsos-positivos ("go live", "go-to-market")
        "aliases": [r"\bgolang\b", r"\bgo lang\b"],
    },
    {
        "id": "ruby",
        "label": "Ruby",
        "plain": "Ruby",
        "search_label": "Desenvolvedor Ruby",
        "aliases": [r"\bruby\b", r"\bon rails\b", r"\brails\b"],
    },
    {
        "id": "mobile",
        "label": "Mobile",
        "plain": "Mobile",
        "search_label": "Desenvolvedor Mobile",
        "aliases": [r"\bflutter\b", r"\bkotlin\b", r"\bswift\b", r"\breact native\b", r"\bandroid\b", r"\bios\b"],
    },
    {
        "id": "data",
        "label": "Dados / BI",
        "plain": "Dados",
        "search_label": "Analista de Dados",
        "aliases": [r"\bsql\b", r"\bpower bi\b", r"\bmysql\b", r"\bpostgresql\b", r"\bmongodb\b", r"\bairflow\b", r"\bspark\b", r"\bdatabricks\b", r"\betl\b"],
    },
    {
        "id": "cloud",
        "label": "DevOps / Cloud",
        "plain": "DevOps",
        "search_label": "DevOps Engineer",
        "aliases": [r"\bdocker\b", r"\bkubernetes\b", r"\bk8s\b", r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bterraform\b", r"\bci/cd\b", r"\bjenkins\b", r"\banible\b"],
    },
    {
        "id": "frontend",
        "label": "Front-end",
        "plain": "Front-end",
        "search_label": "Desenvolvedor Front-end",
        "aliases": [r"\bhtml5?\b", r"\bcss3?\b", r"\bsass\b", r"\bscss\b", r"\btailwind\b"],
    },
    {
        "id": "qa",
        "label": "QA",
        "plain": "QA",
        "search_label": "Analista de QA",
        "aliases": [r"\bqualidade de software\b", r"\bqa\b", r"\bcypress\b", r"\bjest\b", r"\bqualidade\b", r"\btestes automatizados\b"],
    },
]

# Alias que indicam área/nível, usados para montar a busca quando não há stack clara
ROLE_ALIASES = [
    (r"\bdesenvolvedor\b|\bdeveloper\b|\bdev\b|\bprogramador\b", "Desenvolvedor"),
    (r"\bengenheiro\b|\bengineer\b", "Engenheiro"),
    (r"\banalista\b|\banalyst\b", "Analista"),
]


def _detect_family(text: str):
    """Retorna a família de tecnologia mais citada no texto (ou None).

    Desempate: em caso de empate na pontuação, vence a primeira família
    listada (a lista está ordenada por prioridade).
    """
    lower = text.lower()
    best = None
    best_score = 0
    for fam in TECH_FAMILIES:
        score = 0
        for alias in fam["aliases"]:
            score += len(re.findall(alias, lower))
        if score > best_score:
            best_score = score
            best = fam
    return best


def _detect_role(text: str) -> str:
    lower = text.lower()
    for pattern, label in ROLE_ALIASES:
        if re.search(pattern, lower):
            return label
    return "Desenvolvedor"


def build_search_query(base_text: str, explicit_query: str = "") -> dict:
    """
    Constrói a query de busca a partir do currículo do candidato.

    Se o usuário fornecer uma query explícita, ela vence. Caso contrário,
    detecta a stack (ex: muito PHP -> 'Desenvolvedor PHP').
    """
    query = explicit_query.strip()
    family = _detect_family(base_text) if base_text else None
    role = _detect_role(base_text) if base_text else "Desenvolvedor"

    if not query:
        if family:
            if role == "Desenvolvedor":
                query = family["search_label"]
            else:
                # Papéis não-dev: concatena o papel com o termo limpo da stack
                # (evita queries estranhas como "Dados / BI")
                query = f"{role} {family.get('plain', family['label'])}".strip()
        else:
            query = role

    return {
        "query": query,
        "family_label": family["label"] if family else None,
        "detected_stack": family["id"] if family else None,
    }


def _pick_apply_link(job: dict) -> str:
    """
    Prioriza um link aplicável real (LinkedIn/Indeed/Gupy) em vez do share_link
    do Google Jobs, que exige login/redirecionamento do Google.
    """
    preferred = ["linkedin.com/jobs", "indeed.com/viewjob", "gupy.io", "linkedin.com/jobs/view"]
    apply_options = job.get("apply_options") or []
    fallback = ""
    for opt in apply_options:
        link = (opt.get("link") or "").lower()
        if not fallback:
            fallback = opt.get("link") or ""
        for pref in preferred:
            if pref in link:
                return opt.get("link") or ""
    if fallback:
        return fallback
    return job.get("share_link") or ""


# Nomes de país não são aceitos pelo Google Jobs (a API exige cidade).
# Quando o usuário digita só "Brasil"/"Brazil", repetimos a busca sem o
# filtro de local (o gl=br já limita o resultado ao Brasil).
_COUNTRY_ONLY_LOCATIONS = {"brasil", "brazil", "br", "todo o brasil", "em todo o brasil", "brasil inteiro"}

# Palavras que indicam intenção de trabalho remoto no campo de local.
_REMOTE_LOCATION_KEYWORDS = (
    "remoto", "remote", "home office", "homeoffice", "home-office",
    "a distancia", "a distância", "à distância", "100% remoto",
    "hibrido", "híbrido", "hybrid", "work from home", "wfh",
    "em qualquer lugar", "anywhere",
)

# Palavras de ligação usadas quando o usuário combina cidade + remoto
# (ex: "São Paulo, Remoto"). Não contam como cidade nem como remoto puro.
_CONNECTOR_WORDS = {"e", "ou", "em", "na", "no", "de", "do", "da", "para", "com", "a", "o", "as", "os"}


def _is_country_only(location: str) -> bool:
    return location.strip().lower() in _COUNTRY_ONLY_LOCATIONS


def _strip_remote_country(loc: str) -> str:
    """
    Remove palavras remotas, de país, pontuação e dígitos de um local.
    Ex.: "são paulo, remoto" -> "são paulo" ; "rio de janeiro" fica intacto.

    Usa boundaries de palavra (\b) para os nomes de país para não corromper
    cidades — ex.: 'brasil' não pode remover o prefixo de "brasília", e 'br'
    não pode comer o 'br' de "brasil" (a ordem de iteração de um set é
    arbitrária, então substring replace seria não-determinístico).
    Palavras remotas não têm colisão realista com nomes de cidade, então o
    substring replace é seguro para elas.
    """
    rest = loc
    for kw in _REMOTE_LOCATION_KEYWORDS:
        rest = rest.replace(kw, " ")
    for c in _COUNTRY_ONLY_LOCATIONS:
        rest = re.sub(r"\b" + re.escape(c) + r"\b", " ", rest)
    # remove pontuação e dígitos (ex.: o "100" de "100% remoto")
    rest = re.sub(r"[^\wà-ÿ\s]", " ", rest)
    rest = re.sub(r"\b\d+\b", " ", rest)
    return rest


def _remaining_city_words(loc: str) -> list:
    """
    Termos que parecem cidade após remover palavras remotas/pais.
    Remove também conectores ("são paulo, remoto" -> ['são', 'paulo']) — aqui
    isso é correto: só precisamos saber se *sobrou* algo que seja cidade.
    """
    return [w for w in _strip_remote_country(loc).split() if w not in _CONNECTOR_WORDS]


def _has_city_token(loc: str) -> bool:
    """Descobre se sobrou um termo de cidade após remover palavras remotas/pais."""
    return bool(_remaining_city_words(loc))


def _clean_city_location(location: str) -> str:
    """
    Extrai só a cidade de entradas mistas: "São Paulo, Remoto" -> "são paulo".
    Usada antes de chamar a API (que rejeita "Remoto" no campo location).

    Mantém conectores que fazem parte do nome da cidade: "Rio de Janeiro"
    deve continuar "rio de janeiro" (e não "rio janeiro") para a API resolver.
    """
    text = location.strip().lower()
    if not text:
        return location.strip()
    words = _strip_remote_country(text).split()
    if not words:
        return location.strip()
    return " ".join(words)


def _classify_location(location: str) -> str:
    """
    Classifica o local digitado pelo usuário.

    Retorna:
    - 'remote'  -> só intenção remota (ex.: "remoto", "home office")
    - 'national'-> país/vazio/todo o Brasil (Google Jobs exige cidade)
    - 'city'    -> cidade concreta, pode listar vagas internamente.
                   Combinações "cidade + remoto" caem aqui (a vaga remota
                   ainda é listada na busca da cidade pelo Google).
    """
    loc = location.strip().lower()
    if not loc:
        return "national"
    if _is_country_only(location):
        return "national"
    has_remote_kw = any(kw in loc for kw in _REMOTE_LOCATION_KEYWORDS)
    if has_remote_kw and not _has_city_token(loc):
        return "remote"
    return "city"


def _build_deep_links(query: str, location: str, mode: str = "city") -> list:
    """
    Monta links de busca direta nos portais (abertos em nova aba).
    O Google Jobs/SerpAPI não permite embutir os portais nem listar vagas
    remotas/nacionais, então estes atalhos são o caminho para esses casos.
    """
    q = quote(query)
    if mode in ("remote", "national"):
        loc_for_search = "Brasil"
    else:
        loc_for_search = location.strip() or "Brasil"

    links = [
        {
            "site": "LinkedIn",
            "label": "Buscar no LinkedIn",
            "url": f"https://www.linkedin.com/jobs/search/?keywords={q}&location={quote(loc_for_search)}"
                   + ("&f_WT=2" if mode == "remote" else ""),
        },
        {
            "site": "Indeed",
            "label": "Buscar no Indeed",
            "url": f"https://br.indeed.com/jobs?q={q}&l={quote(loc_for_search)}",
        },
        {
            "site": "Gupy",
            "label": "Buscar no Gupy",
            "url": f"https://portal.gupy.io/job-search/term?terms={q}",
        },
        {
            "site": "Programathor",
            "label": "Buscar no Programathor",
            "url": f"https://programathor.com.br/jobs?search={q}",
        },
    ]
    return links


def _extract_error(data) -> str:
    """Extrai a mensagem de erro da resposta da SerpAPI com segurança.

    O campo 'error' pode vir como objeto (não string) — convertemos para
    string para nunca quebrar chamadas .lower() posteriores.
    """
    if not isinstance(data, dict):
        return ""
    return str(data.get("error") or "")


def search_jobs(query: str, location: str = "", limit: int = 10) -> dict:
    """
    Busca vagas no Google Jobs via SerpAPI.

    Regras:
    - Erros de rede/timeout viram mensagens amigáveis (sem vazar a URL/chave).
    - Se o local informado for rejeitado pela API (ex.: país sem cidade),
      repetimos a busca sem o filtro de local.
    - "Nenhum resultado" não é tratado como erro: vira lista vazia.
    """
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        return {
            "error": "SERPAPI_KEY não configurada. Adicione sua chave no arquivo .env para buscar vagas.",
            "jobs": [],
        }

    def _call(loc: str):
        params = {
            "engine": "google_jobs",
            "q": query,
            "gl": "br",
            "hl": "pt",
            "api_key": api_key,
        }
        if loc and loc.strip():
            params["location"] = loc.strip()
        try:
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
            return resp.status_code, resp.json()
        except (requests.exceptions.RequestException, ValueError):
            # Nunca incluímos a URL na mensagem: ela contém a api_key.
            return 0, {}

    # Observação: o fluxo da app (suggest_jobs) só chama search_jobs com
    # cidade concreta (mode='city'); países/remoto/vazio já são filtrados antes.
    # Ainda assim mantemos proteção contra locais rejeitados pela API.
    status, data = _call(location)
    error_msg = _extract_error(data)

    # Local rejeitado (ex.: cidade inválida) -> repete uma única vez sem local.
    if error_msg and "location" in error_msg.lower() and location.strip():
        status, data = _call("")
        error_msg = _extract_error(data)

    # Só trata como "sem resultados" a frase exata que o Google Jobs retorna.
    no_results = "hasn't returned any results" in error_msg.lower()

    if status == 0:
        return {"error": "Não foi possível consultar o buscador de vagas agora. Tente novamente em instantes.", "jobs": []}
    if status != 200 or (error_msg and not no_results):
        return {"error": error_msg or "O buscador de vagas retornou um erro. Confira sua chave SERPAPI_KEY.", "jobs": []}

    if not isinstance(data, dict):
        return {"error": "Resposta inesperada do buscador de vagas. Tente novamente.", "jobs": []}
    jobs_raw = data.get("jobs_results") or []
    jobs = []
    for j in jobs_raw[:limit]:
        extensions = j.get("detected_extensions") or {}
        jobs.append({
            "title": j.get("title") or "Vaga sem título",
            "company": j.get("company_name") or "Empresa não informada",
            "location": j.get("location") or "",
            "via": j.get("via") or "",
            "description": j.get("description") or "",
            "link": _pick_apply_link(j),
            "share_link": j.get("share_link") or "",
            "posted_at": extensions.get("posted_at") or "",
            "schedule_type": extensions.get("schedule_type") or "",
        })

    return {"jobs": jobs}


def suggest_jobs(base_text: str, explicit_query: str = "", location: str = "", limit: int = 10) -> dict:
    """
    Orquestra: detecta stack -> monta query -> busca vagas.

    O Google Jobs (via SerpAPI) só lista vagas com cidade concreta. Para
    buscas remotas, nacionais ou com local vazio, pulamos a chamada cara da
    API (que retornaria vazio) e entregamos atalhos de busca nos portais.
    """
    build = build_search_query(base_text, explicit_query)
    mode = _classify_location(location)

    # Cidade limpa: remove "remoto"/país/ligações de entradas mistas
    # (ex.: "São Paulo, Remoto" -> "são paulo") para a API aceitar o local.
    search_location = _clean_city_location(location) if mode == "city" else location

    if mode == "city":
        result = search_jobs(build["query"], location=search_location, limit=limit)
    else:
        # Remoto/país/vazio: o Google Jobs não lista internamente.
        result = {"jobs": []}

    result.update({
        "query_used": build["query"],
        "detected_stack": build["detected_stack"],
        "family_label": build["family_label"],
        "location_mode": mode,
        "location_used": search_location,
        "deep_links": _build_deep_links(build["query"], search_location, mode=mode),
    })
    return result
