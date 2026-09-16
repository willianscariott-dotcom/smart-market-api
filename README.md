# Smart Market RS - Monitor & Economia em Compras

Aplicativo pessoal de controle financeiro de mercados, histórico de preços por item e inteligência de decisão para compras no Rio Grande do Sul (SEFAZ-RS).

## 🎯 Objetivos
* Monitorar e comparar preços de produtos entre diferentes estabelecimentos.
* Identificar automaticamente o mercado com melhor custo-benefício para uma lista de compras mensal.
* Manter histórico temporal de preços por produto/EAN para análise de inflação pessoal.
* Processar cupons fiscais via QR Code sem custo e sem digitação manual.

## 🛠 Tech Stack
* **Frontend Mobile / Desktop:** AppSheet (Google Workspace)
* **Banco de Dados:** Google Sheets
* **Backend Extrator / API:** Python (FastAPI + BeautifulSoup + gspread)
* **Hospedagem API:** Render / PythonAnywhere / Supabase Edge (Tier Gratuito)