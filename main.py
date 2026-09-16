import os
import json
import re
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

app = FastAPI(title="Smart Market RS - Extrator NFC-e")

# Permissões do Google Sheets E Google Drive (Impede o erro 403)
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CREDENTIALS_FILE = 'credentials.json'

def get_sheet():
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    # Certifique-se de que o nome é EXATAMENTE o mesmo da sua planilha no Google Drive
    sh = gc.open('Smart_Market_DB') 
    return sh

@app.get("/")
def read_root():
    return {"status": "API Online"}

@app.post("/processar-nota")
async def processar_nota(request: Request):
    try:
        data = await request.json()
        url = data.get("url_qrcode", "").strip()

        if not url:
            return JSONResponse(content={"erro": "URL não fornecida"}, status_code=400)

        sh = get_sheet()
        aba_notas = sh.worksheet("Notas")
        aba_produtos = sh.worksheet("Produtos_Comprados")

        # --- MOCK DE TESTE ---
        if url.upper() == "MOCK":
            chaves_existentes = aba_notas.col_values(1)
            if "MOCK_CHAVE_123" in chaves_existentes:
                return JSONResponse(content={"msg": "Nota MOCK já existe."})
            
            aba_notas.append_row(["MOCK_CHAVE_123", "Mercado Mock", "00.000.000/0001-00", datetime.now().strftime("%d/%m/%Y %H:%M"), 50.00, url])
            aba_produtos.append_rows([
                ["MOCK_CHAVE_123", "Arroz 5kg MOCK", 1.0, "UN", 25.00, 25.00, "111"],
                ["MOCK_CHAVE_123", "Feijão 1kg MOCK", 2.0, "UN", 12.50, 25.00, "222"]
            ])
            return JSONResponse(content={"msg": "Sucesso! MOCK cadastrado."})


        # --- EXTRAÇÃO REAL (PORTAL SVRS RS) ---
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Extrair Chave de Acesso (da URL)
        match = re.search(r'p=(\d{44})', url)
        chave = match.group(1) if match else "CHAVE_DESCONHECIDA"

        # Trava de Duplicidade
        chaves_existentes = aba_notas.col_values(1)
        if chave in chaves_existentes:
            print(f"Nota {chave} já existe no banco.")
            return JSONResponse(content={"msg": f"Nota {chave} já existe no banco."})

        # 2. Extrair dados do Cabeçalho da Nota
        nome_mercado_el = soup.find(id="u20") or soup.find("div", class_="txtTopo")
        nome_mercado = nome_mercado_el.text.strip() if nome_mercado_el else "Mercado Não Identificado"
        
        cnpj_el = soup.find("div", class_="text")
        cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', cnpj_el.text).group() if (cnpj_el and re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', cnpj_el.text)) else ""

        # Processa o Valor Total da Nota convertendo vírgula para ponto (Float)
        valor_total_el = soup.find(class_="txtMax") or soup.find(id="totalNota")
        valor_total_raw = valor_total_el.text.strip() if valor_total_el else "0,00"
        try:
            valor_total_clean = valor_total_raw.replace(".", "").replace(",", ".").strip()
            valor_total_float = float(re.sub(r'[^\d.]', '', valor_total_clean))
        except:
            valor_total_float = 0.0

        data_emissao = datetime.now().strftime("%d/%m/%Y")

        # 3. Extrair Produtos (Estrutura SVRS)
        produtos = []
        tabela_itens = soup.find(id="tabResult")
        
        if tabela_itens:
            linhas = tabela_itens.find_all("tr")
            for tr in linhas:
                nome_el = tr.find("span", class_="txtTit")
                if not nome_el:
                    continue # Pula se não for linha de produto
                
                nome_prod = nome_el.text.strip()
                
                cod_el = tr.find("span", class_="RCod")
                cod_prod = re.sub(r'\D', '', cod_el.text) if cod_el else ""
                
                qtd_el = tr.find("span", class_="Rqtd")
                qtd_raw = qtd_el.text.replace("Qtde.:", "").strip() if qtd_el else "1"
                try:
                    qtd_float = float(qtd_raw.replace(",", "."))
                except:
                    qtd_float = 1.0
                
                un_el = tr.find("span", class_="RUN")
                un_prod = un_el.text.replace("UN: ", "").strip() if un_el else "UN"
                
                # Converte Valor Unitário ("2,99" -> 2.99)
                vl_unit_el = tr.find("span", class_="RvlUnit")
                vl_unit_raw = vl_unit_el.text.replace("Vl. Unit.:", "").strip() if vl_unit_el else "0,00"
                try:
                    vl_unit_clean = vl_unit_raw.replace(".", "").replace(",", ".")
                    vl_unit_float = float(re.sub(r'[^\d.]', '', vl_unit_clean))
                except:
                    vl_unit_float = 0.0
                
                # Converte Valor Total do Item ("2,99" -> 2.99)
                vl_total_el = tr.find("span", class_="valor")
                vl_total_raw = vl_total_el.text.strip() if vl_total_el else "0,00"
                try:
                    vl_total_clean = vl_total_raw.replace(".", "").replace(",", ".")
                    vl_total_float = float(re.sub(r'[^\d.]', '', vl_total_clean))
                except:
                    vl_total_float = 0.0

                # Insere o array com valores numéricos reais
                # Estrutura: ID_Nota, Nome, Qtd, UN, Vl Unit, Vl Total, Código
                produtos.append([chave, nome_prod, qtd_float, un_prod, vl_unit_float, vl_total_float, cod_prod])

        if not produtos:
            return JSONResponse(content={"erro": "Nenhum produto extraído. Layout da nota incompatível."})

        # 4. Inserir no Sheets
        aba_notas.append_row([chave, nome_mercado, cnpj, data_emissao, valor_total_float, url])
        aba_produtos.append_rows(produtos)

        print(f"Sucesso! {len(produtos)} itens cadastrados.")
        return JSONResponse(content={"msg": f"Sucesso! {len(produtos)} itens cadastrados na planilha."})

    except Exception as e:
        print("Erro interno:", str(e))
        return JSONResponse(content={"erro": str(e)}, status_code=500)