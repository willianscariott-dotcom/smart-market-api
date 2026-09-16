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

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CREDENTIALS_FILE = 'credentials.json'

def get_sheet():
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(credentials)
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

        # --- EXTRAÇÃO REAL (PORTAL SVRS RS) ---
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Extrair Chave de Acesso
        match = re.search(r'p=(\d{44})', url)
        chave = match.group(1) if match else "CHAVE_DESCONHECIDA"

        # Trava de Duplicidade
        chaves_existentes = aba_notas.col_values(1)
        if chave in chaves_existentes:
            print(f"Nota {chave} já existe no banco.")
            return JSONResponse(content={"msg": f"Nota {chave} já existe no banco."})

        # 2. Extrair dados do Cabeçalho
        nome_mercado_el = soup.find(id="u20") or soup.find("div", class_="txtTopo")
        nome_mercado = nome_mercado_el.text.strip() if nome_mercado_el else "Mercado Não Identificado"
        
        cnpj_el = soup.find("div", class_="text")
        cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', cnpj_el.text).group() if (cnpj_el and re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', cnpj_el.text)) else ""

        valor_total_el = soup.find(class_="txtMax") or soup.find(id="totalNota")
        valor_total_raw = valor_total_el.text.strip() if valor_total_el else "0,00"
        try:
            valor_total_clean = valor_total_raw.replace(".", "").replace(",", ".").strip()
            valor_total_float = float(re.sub(r'[^\d.]', '', valor_total_clean))
        except:
            valor_total_float = 0.0

        data_emissao = datetime.now().strftime("%d/%m/%Y")

        # 3. Extrair Produtos alinhados com a planilha:
        # A: ID_Produto | B: ID_Nota | C: Nome_Produto | D: Categoria | E: Quantidade | F: Unidade_Medida | G: Preco_Unitario | H: Preco_Total | I: Marca | J: Desconto | K: Observacoes
        produtos = []
        tabela_itens = soup.find(id="tabResult")
        
        if tabela_itens:
            linhas = tabela_itens.find_all("tr")
            for tr in linhas:
                nome_el = tr.find("span", class_="txtTit")
                if not nome_el:
                    continue
                
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
                
                vl_unit_el = tr.find("span", class_="RvlUnit")
                vl_unit_raw = vl_unit_el.text.replace("Vl. Unit.:", "").strip() if vl_unit_el else "0,00"
                try:
                    vl_unit_clean = vl_unit_raw.replace(".", "").replace(",", ".")
                    vl_unit_float = float(re.sub(r'[^\d.]', '', vl_unit_clean))
                except:
                    vl_unit_float = 0.0
                
                vl_total_el = tr.find("span", class_="valor")
                vl_total_raw = vl_total_el.text.strip() if vl_total_el else "0,00"
                try:
                    vl_total_clean = vl_total_raw.replace(".", "").replace(",", ".")
                    vl_total_float = float(re.sub(r'[^\d.]', '', vl_total_clean))
                except:
                    vl_total_float = 0.0

                # Linha com 11 colunas exatas da sua planilha:
                produtos.append([
                    cod_prod,          # A: ID_Produto
                    chave,             # B: ID_Nota
                    nome_prod,         # C: Nome_Produto
                    "",                # D: Categoria
                    qtd_float,         # E: Quantidade
                    un_prod,           # F: Unidade_Medida
                    vl_unit_float,     # G: Preco_Unitario
                    vl_total_float,    # H: Preco_Total
                    "",                # I: Marca
                    0.0,               # J: Desconto
                    ""                 # K: Observacoes
                ])

        if not produtos:
            return JSONResponse(content={"erro": "Nenhum produto extraído."})

        # 4. Inserir nas abas
        aba_notas.append_row([chave, nome_mercado, cnpj, data_emissao, valor_total_float, url])
        aba_produtos.append_rows(produtos)

        return JSONResponse(content={"msg": f"Sucesso! {len(produtos)} itens cadastrados."})

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)