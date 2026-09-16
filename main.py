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
        url_original = data.get("url_qrcode", "").strip()

        if not url_original:
            return JSONResponse(content={"erro": "URL ou Chave não fornecida"}, status_code=400)

        entrada_limpa = url_original.replace(" ", "")
        
        # 1. Identificar Chave e Gerar Lista de URLs para tentativa (Fallback)
        urls_testar = []
        if len(entrada_limpa) == 44 and entrada_limpa.isdigit():
            chave = entrada_limpa
            urls_testar = [
                f"https://dfe-portal.svrs.rs.gov.br/Dfe/QrCodeNfce?p={chave}",
                f"https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx?chNFe={chave}",
                f"https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx?p={chave}",
                f"https://dfe-portal.svrs.rs.gov.br/Dfe/QrCodeNfce?p={chave}|2|1|1"
            ]
        else:
            match_param = re.search(r'p=([^&]+)', entrada_limpa)
            match_chave = re.search(r'(\d{44})', entrada_limpa)
            chave = match_chave.group(1) if match_chave else "CHAVE_DESCONHECIDA"
            
            if match_param:
                param_p = match_param.group(1)
                urls_testar = [
                    f"https://dfe-portal.svrs.rs.gov.br/Dfe/QrCodeNfce?p={param_p}",
                    f"https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx?p={param_p}"
                ]
            else:
                urls_testar = [entrada_limpa]

        sh = get_sheet()
        aba_notas = sh.worksheet("Notas")
        aba_produtos = sh.worksheet("Produtos_Comprados")

        # Trava de Duplicidade Dupla
        chaves_notas = set(str(c).strip() for c in aba_notas.col_values(1))
        chaves_produtos = set(str(c).strip() for c in aba_produtos.col_values(2))

        if chave in chaves_notas or chave in chaves_produtos:
            return JSONResponse(content={"msg": f"Nota {chave} já existe no banco."})

        # 2. Raspagem com fallback entre URLs do Governo
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        soup = None
        produtos = []
        nome_mercado = "Mercado Não Identificado"
        valor_total_float = 0.0

        for url_tentativa in urls_testar:
            try:
                response = requests.get(url_tentativa, headers=headers, timeout=12)
                soup_temp = BeautifulSoup(response.text, 'html.parser')
                tabela_temp = soup_temp.find(id="tabResult") or soup_temp.find("table", class_="tabResult")
                
                if tabela_temp and tabela_temp.find_all("tr"):
                    soup = soup_temp
                    tabela_itens = tabela_temp
                    break
            except:
                continue

        if not soup or not tabela_itens:
            return JSONResponse(content={"erro": "Nenhum produto extraído do layout."})

        # 3. Extração dos dados
        nome_mercado_el = soup.find(id="u20") or soup.find("div", class_="txtTopo")
        if nome_mercado_el:
            nome_mercado = nome_mercado_el.text.strip()

        valor_total_el = soup.find(class_="txtMax") or soup.find(id="totalNota")
        if valor_total_el:
            try:
                valor_total_clean = valor_total_el.text.strip().replace(".", "").replace(",", ".")
                valor_total_float = float(re.sub(r'[^\d.]', '', valor_total_clean))
            except:
                valor_total_float = 0.0

        data_emissao = datetime.now().strftime("%d/%m/%Y")

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

            produtos.append([
                cod_prod, chave, nome_prod, "", qtd_float, un_prod, vl_unit_float, vl_total_float, "", 0.0, ""
            ])

        if not produtos:
            return JSONResponse(content={"erro": "Nenhum produto extraído do layout."})

        # 4. Inserção final no Google Sheets
        aba_notas.append_row([
            chave, data_emissao, nome_mercado, valor_total_float, chave, "Processado", url_original
        ])
        aba_produtos.append_rows(produtos)

        return JSONResponse(content={"msg": f"Sucesso! {len(produtos)} itens cadastrados."})

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)