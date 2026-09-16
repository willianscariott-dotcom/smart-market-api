import re
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import gspread

app = FastAPI(title="Smart Market RS - Extrator NFC-e")

class NotaRequest(BaseModel):
    id_fila: Optional[str] = None
    url_qrcode: str

def get_google_sheet():
    gc = gspread.service_account(filename="credentials.json")
    return gc.open("Smart_Market_DB")

def get_mock_data():
    """Retorna dados simulados com base no cupom impresso do SDB Comercio de Alimentos"""
    chave = "43260909477652012100651160000561511509135615"
    return {
        "id_nota": chave,
        "data_compra": "2026-09-01 15:13:24",
        "mercado_nome": "SDB COMERCIO DE ALIMENTOS LTDA",
        "valor_total": 194.59,
        "url_qrcode": "SIMULACAO_LOCAL",
        "itens": [
            {"ean": "7898080663733", "descricao": "BEB ENERGY BALY 473ML", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 5.49, "valor_total": 5.49},
            {"ean": "2904", "descricao": "BANANA CATURRA KG", "quantidade": 1.555, "unidade": "KG", "valor_unitario": 2.98, "valor_total": 4.63},
            {"ean": "7896883000045", "descricao": "QUEIJO MUS SO LEITE 800G", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 38.90, "valor_total": 38.90},
            {"ean": "7898623593442", "descricao": "BATATA BOBS 1 05KG CONG", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 19.98, "valor_total": 19.98},
            {"ean": "7898103557872", "descricao": "PAO FORMA VITAL 400G INT", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 6.99, "valor_total": 6.99},
            {"ean": "7891079014288", "descricao": "LAMEN NISSIN 85G CALAB", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 2.98, "valor_total": 2.98},
            {"ean": "7891150050938", "descricao": "LAVA ROUP LIQ BRILHANTE", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 39.90, "valor_total": 39.90},
            {"ean": "7891107101621", "descricao": "O SOYA PT 900ML", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 7.65, "valor_total": 7.65},
            {"ean": "7898956109792", "descricao": "SUCO SUQ 900ML BERGAMOTA", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 10.98, "valor_total": 10.98},
            {"ean": "7896412800122", "descricao": "MAC ORQUIDEA 500G", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 3.99, "valor_total": 3.99},
            {"ean": "7896004011608", "descricao": "CEREAL MAT KELLOGGS 200G", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 15.89, "valor_total": 15.89},
            {"ean": "7896716311034", "descricao": "PRESUNTO PAMPLONA 1KG", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 27.90, "valor_total": 27.90},
            {"ean": "7898215152002", "descricao": "LEIT CON PIRACA 395G", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 5.85, "valor_total": 5.85},
            {"ean": "7896534621810", "descricao": "OVOS PRATA C30 GDE BCO", "quantidade": 1.0, "unidade": "UN", "valor_unitario": 17.90, "valor_total": 17.90}
        ]
    }

def processar_e_gravar(dados_req: NotaRequest):
    sheet = get_google_sheet()
    ws_notas = sheet.worksheet("Notas")
    ws_produtos = sheet.worksheet("Produtos_Comprados")

    # Verifica se é chamada em modo de simulação
    if dados_req.url_qrcode.strip().upper() == "MOCK":
        dados_nota = get_mock_data()
    else:
        # Modo real de extração
        chave_acesso = re.search(r"\d{44}", dados_req.url_qrcode)
        chave_id = chave_acesso.group(0) if chave_acesso else f"NOTE_{int(datetime.now().timestamp())}"
        
        # Faz raspagem real se tiver URL válida
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(dados_req.url_qrcode, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        itens = []
        # Fallback básico para requisição real
        dados_nota = {
            "id_nota": chave_id,
            "data_compra": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mercado_nome": "Mercado RS",
            "valor_total": 0.0,
            "url_qrcode": dados_req.url_qrcode,
            "itens": itens
        }

    # 1. Checa duplicidade
    chaves_existentes = ws_notas.col_values(1)
    if dados_nota["id_nota"] in chaves_existentes:
        print(f"Nota {dados_nota['id_nota']} já existe no banco.")
        return

    # 2. Grava Cabeçalho na aba 'Notas'
    ws_notas.append_row([
        dados_nota["id_nota"],
        dados_nota["data_compra"],
        dados_nota["mercado_nome"],
        dados_nota["valor_total"],
        dados_nota["id_nota"],
        "PROCESSADO",
        dados_nota["url_qrcode"]
    ])

    # 3. Grava Itens na aba 'Produtos_Comprados'
    novos_itens = []
    for idx, item in enumerate(dados_nota["itens"], start=1):
        id_produto = f"{dados_nota['id_nota']}_{idx}"
        novos_itens.append([
            id_produto,
            dados_nota["id_nota"],
            item["descricao"],
            "Alimentação",
            item["quantidade"],
            item["unidade"],
            item["valor_unitario"],
            item["valor_total"],
            item["ean"],
            0.0,
            ""
        ])

    if novos_itens:
        ws_produtos.append_rows(novos_itens)
        print(f"Sucesso! {len(novos_itens)} itens cadastrados na planilha.")

@app.post("/processar-nota")
def api_processar_nota(payload: NotaRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(processar_e_gravar, payload)
    return {"status": "queued", "message": "Processamento iniciado."}