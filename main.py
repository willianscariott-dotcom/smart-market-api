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

        # --- TRATAMENTO DE ENTRADA (URL Completa ou Apenas Chave de 44 dígitos) ---
        entrada_limpa = url_original.replace(" ", "")
        
        # Se o usuário digitou apenas a chave de 44 números
        if len(entrada_limpa) == 44 and entrada_limpa.isdigit():
            chave = entrada_limpa
            url = f"https://dfe-portal.svrs.rs.gov.br/Dfe/QrCodeNfce?p={chave}"
        else:
            # Se for um link de QR Code lido pela câmera
            match_param = re.search(r'p=([^&]+)', entrada_limpa)
            if match_param:
                param_p = match_param.group(1)
                url = f"https://dfe-portal.svrs.rs.gov.br/Dfe/QrCodeNfce?p={param_p}"
            elif re.search(r'\d{44}', entrada_limpa):
                chave_44 = re.search(r'\d{44}', entrada_limpa).group()
                url = f"https://dfe-portal.svrs.rs.gov.br/Dfe/QrCodeNfce?p={chave_44}"
            else:
                url = entrada_limpa
                
        # 1. Extrair Chave de Acesso definitiva da URL montada
        match_chave = re.search(r'(\d{44})', url)
        chave = match_chave.group(1) if match_chave else "CHAVE_DESCONHECIDA"

        sh = get_sheet()
        aba_notas = sh.worksheet("Notas")
        aba_produtos = sh.worksheet("Produtos_Comprados")

        # TRAVA DUPLA DE DUPLICIDADE: Checa nas duas abas antes de inserir
        chaves_notas = set(str(c).strip() for c in aba_notas.col_values(1))
        chaves_produtos = set(str(c).strip() for c in aba_produtos.col_values(2))

        if chave in chaves_notas or chave in chaves_produtos:
            print(f"Nota {chave} já existe no banco.")
            return JSONResponse(content={"msg": f"Nota {chave} já existe no banco."})

        # --- RASPAGEM DA PÁGINA ---
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 2. Extrair dados do Cabeçalho
        nome_mercado_el = soup.find(id="u20") or soup.find("div", class_="txtTopo")
        nome_mercado = nome_mercado_el.text.strip() if nome_mercado_el else "Mercado Não Identificado"

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

                # A: ID_Produto | B: ID_Nota | C: Nome_Produto | D: Categoria | E: Quantidade | F: Unidade_Medida | G: Preco_Unitario | H: Preco_Total | I: Marca | J: Desconto | K: Observacoes
                produtos.append([
                    cod_prod,
                    chave,
                    nome_prod,
                    "",
                    qtd_float,
                    un_prod,
                    vl_unit_float,
                    vl_total_float,
                    "",
                    0.0,
                    ""
                ])

        if not produtos:
            return JSONResponse(content={"erro": "Nenhum produto extraído do layout."})

        # 4. Inserir na aba Notas (A: ID_Nota | B: Data_Compra | C: Mercado | D: Valor_Total | E: Chave_Acesso | F: Status | G: Observacoes)
        aba_notas.append_row([
            chave,
            data_emissao,
            nome_mercado,
            valor_total_float,
            chave,
            "Processado",
            url_original
        ])

        # Inserir na aba Produtos_Comprados
        aba_produtos.append_rows(produtos)

        print(f"Sucesso! {len(produtos)} itens cadastrados.")
        return JSONResponse(content={"msg": f"Sucesso! {len(produtos)} itens cadastrados na planilha."})

    except Exception as e:
        print("Erro interno:", str(e))
        return JSONResponse(content={"erro": str(e)}, status_code=500)