# Dinamizador de Currículo 🚀

O **Dinamizador de Currículo** é um sistema inteligente movido por Inteligência Artificial (Gemini) projetado para otimizar e adaptar currículos para sistemas ATS (Applicant Tracking Systems) de forma dinâmica e automatizada. 

Ele cruza as suas experiências base com a descrição de uma vaga específica (LinkedIn, Indeed ou texto livre) e injeta o resultado formatado e otimizado com palavras-chave diretamente em um documento Word, gerando também a versão final em PDF.

---

## ⚙️ Como Funciona
1. **Coleta de Dados:** O sistema raspa (scrape) as informações e requisitos da vaga escolhida através do link do LinkedIn/Indeed ou via texto colado.
2. **Processamento (IA):** O motor de IA analisa o histórico do candidato (extraído do template base) e recria os textos focando estritamente em palavras-chave da vaga, sem invenções, evitando formatações complexas que quebram a leitura dos ATS.
3. **Geração do Documento:** Usando bibliotecas de processamento Word (`docxtpl`), as variáveis geradas pela IA são fundidas no arquivo `.docx` fornecido e, em seguida, convertidas para PDF via LibreOffice Headless.

---

## 🛠️ Como Usar (Ambiente Local)

1. Clone o repositório.
2. Crie um arquivo `.env` na raiz do projeto com a sua chave secreta da Google (e opcionalmente da GroqCloud para assumir gratuitamente se a quota do Gemini estourar):
   ```env
   GEMINI_API_KEY=sua_chave_aqui
   GROQ_API_KEY=sua_chave_groq_opcional
   SERPAPI_KEY=sua_chave_serpapi_opcional
   ```
   > 💡 **SERPAPI_KEY** é opcional e habilita a **Central de Vagas** (busca automática de vagas compatíveis com a stack do seu currículo, agregando LinkedIn/Indeed/Gupy via Google Jobs). Crie sua chave gratuita em [serpapi.com](https://serpapi.com) (100 buscas/mês no plano free). Sem essa chave, o resto do app funciona normalmente.
3. Crie e ative um ambiente virtual Python.
4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   playwright install --with-deps chromium
   ```
5. *(Opcional para Linux)* Para a geração de PDF, é necessário ter o LibreOffice instalado no seu sistema operacional (`sudo apt install libreoffice`).
6. Rode a aplicação:
   ```bash
   python app.py
   ```
7. Acesse `http://127.0.0.1:5000` no seu navegador.

---

## 🐳 Como Usar (Produção / Docker)
O projeto já conta com um `Dockerfile` preparado para a nuvem. Ele baixa o LibreOffice, os navegadores sem interface e expõe o servidor robusto Gunicorn:
```bash
# Iniciar o container em plano de fundo:
docker compose up -d --build
```
*Nota: Recomenda-se um servidor com pelo menos 1GB de RAM para suportar a geração simultânea via Gunicorn e LibreOffice.*

---

## 📝 Regras do Template DOCX (Guia de Variáveis)

**Você pode usar o template base incluso no projeto (`curriculo_ats_template.docx`) ou criar o seu próprio modelo do zero!** 
A única exigência para usar qualquer documento Word é que você insira as tags de variáveis (listadas abaixo) nos lugares onde deseja que a Inteligência Artificial atue.

> ⚠️ **Informações Estáticas (Edição Manual):** O sistema foca apenas em dinamizar suas áreas profissionais de acordo com a vaga. Textos fixos como seu Nome, Telefones, Bairro, Nível de Idiomas e Formação Acadêmica NÃO são alterados pela IA. Eles devem ser editados por você de forma manual direto no seu arquivo DOCX, sem o uso de chaves.
>
> 📅 **Datas no template (padronização manual):** a IA padroniza apenas as datas dos blocos dinâmicos (resumo e experiências) — ela não acessa os campos fixos. Para não perder pontos no ATS por "formatos de data inconsistentes", normalize também as datas da Formação, Certificações e demais seções estáticas usando o formato **só-ano `YYYY`** (ex.: `2026 – Atual`) e use sempre "Atual" no período em andamento. A IA também padroniza as datas dinâmicas nesse mesmo formato.

Nos blocos dinâmicos do seu documento, insira as tags abaixo. Você pode formatar as tags como quiser (Negrito, Azul, Itálico), e o sistema herdará essa formatação!

### Cabeçalho
- **`{{ titulo_adaptado }}`**
  *(Ex: Desenvolvedor PHP | APIs | MySQL)*
- **`{{ objetivo_adaptado }}`**
  *(Ex: Atuar como desenvolvedor...)*
- **`{{ resumo_adaptado }}`**
  *(Texto corrido com seus highlights adaptados à vaga).*

### Experiências Profissionais
A IA agora mapeia suas experiências de forma numerada. Você deve colocar o título e a descrição de cada experiência separadamente para manter a formatação distinta:

**Experiência 1:**
- **`{{ titulo_experiencia_1 }}`** *(Coloque em Negrito no Word)*
- **`{{ experiencia_adaptada_1 }}`** *(Deixe sem formatação)*

**Experiência 2:**
- **`{{ titulo_experiencia_2 }}`** *(Coloque em Negrito no Word)*
- **`{{ experiencia_adaptada_2 }}`** *(Deixe sem formatação)*

*(Faça isso para o número de experiências (3, 4) que você tem em seu template).*

### Habilidades (Skillset)
- **`{{ skills_adaptadas }}`**
  *(Lista formatada por vírgulas contendo apenas as tecnologias exigidas e que você possui).*

---

## 🏆 Créditos
O arquivo base/molde (`curriculo_ats_template.docx`) que inspira o sucesso deste gerador foi idealizado de forma gratuita pela excelente **Mel (melarchangelo9@gmail.com)**. Todo o mérito do design focado em ATS (cores, divisões e fontes limpas) pertence a ela. 

Deixo também um agradecimento especial ao canal **Dev Magro**, pois foi assistindo ao [vídeo dele sobre a importância deste template para programadores](https://www.youtube.com/watch?v=Gx1H330JOgQ&t=172s) que surgiu a inspiração inicial para criar essa automação.

O motor de Inteligência Artificial, o processamento de texto e a arquitetura web (todo o código) deste projeto foram desenvolvidos 100% por **[Otávio Alves (@otaviofigueredoalves)](https://github.com/otaviofigueredoalves)** de forma independente para ajudar a comunidade tech. 
Acesse o template visual original no Google Docs: [Clique Aqui](https://docs.google.com/document/d/1TmiWHUhvlLMlAK0vtEziA9JQ85idSCtX/edit).
