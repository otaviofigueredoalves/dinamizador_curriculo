import os
from playwright.sync_api import sync_playwright

def scrape_linkedin_job(url: str) -> str:
    """
    Scrapes the job description from a job URL (LinkedIn or Indeed) using Playwright.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            description = ""
            
            if "indeed.com" in url:
                try:
                    page.wait_for_selector("#jobDescriptionText", timeout=10000)
                    description = page.inner_text("#jobDescriptionText")
                except:
                    description = page.inner_text("body")
            else:
                # Lógica original para LinkedIn
                try:
                    page.wait_for_selector(".show-more-less-html__markup", timeout=10000)
                    description = page.inner_text(".show-more-less-html__markup")
                except Exception:
                    try:
                        page.wait_for_selector(".jobs-description__content", timeout=5000)
                        description = page.inner_text(".jobs-description__content")
                    except Exception:
                        description = page.inner_text("body")
                        
            browser.close()
            return " ".join(description.split())
    except Exception as e:
        print(f"Erro no scraping: {e}")
        return ""

def scrape_linkedin_title_company(url: str) -> dict:
    """
    Extrai rapidamente apenas o título da vaga e a empresa para validação.
    Suporta LinkedIn e Indeed.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # O Indeed muitas vezes tem proteções pesadas que impedem o status "load" de ser concluído.
            # wait_until="domcontentloaded" faz com que o script continue assim que o HTML base chegar.
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            title = "Não encontrado"
            company = "Não encontrado"
            
            page_title = page.title() 
            
            if "indeed.com" in url.lower():
                if page_title:
                    parts = page_title.split(" - ")
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        company = "Empresa no Indeed"
                        try:
                            company_elem = page.query_selector('[data-testid="inlineHeader-companyName"]')
                            if company_elem:
                                company = company_elem.inner_text().strip()
                        except:
                            pass
            else:
                if page_title:
                    parts = page_title.split(" at ")
                    if len(parts) == 2:
                        title = parts[0].strip()
                        company = parts[1].split(" | ")[0].strip()
                    else:
                        parts = page_title.split(" | ")
                        if len(parts) > 1:
                            title = parts[0].strip()
                            
            browser.close()
            return {"title": title, "company": company}
    except Exception as e:
        print(f"Erro no scraping de título: {e}")
        return {"title": "Erro ao buscar", "company": "Erro ao buscar"}

def scrape_linkedin_profile(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)
            text = page.inner_text("body")
            browser.close()
            return " ".join(text.split())
    except Exception as e:
        print(f"Erro no scraping de perfil: {e}")
        return ""
