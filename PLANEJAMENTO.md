# Roteiro de Execução Passo a Passo (Roadmap)

## Fase 1: Base de Dados no Google Sheets

* \[ ] Criar a Planilha "Smart\_Market\_DB" no Google Drive.
* \[ ] Criar e formatar as 4 abas: `Notas`, `Produtos\_Comprados`, `Fila\_Notas` e `Lista\_Desejos`.
* \[ ] Gerar as credenciais de Serviço da API do Google (arquivo `credentials.json`) para permitir que o Python escreva na planilha.

## Fase 2: Backend Extrator em Python

* \[ ] Criar o projeto Python com `FastAPI`, `BeautifulSoup4`, `requests` e `gspread`.
* \[ ] Escrever o algoritmo de Web Scraping para a página da SEFAZ-RS (extração de CNPJ, Razão Social, Data e Tabela de Itens).
* \[ ] Implementar trava de duplicidade: verificar se a `Chave\_Acesso` já existe na aba `Notas`.
* \[ ] Criar o endpoint `POST /processar-nota` que insere os dados na planilha e atualiza o status na aba `Fila\_Notas`.
* \[ ] Fazer hospedagem gratuita da API no Render ou PythonAnywhere.

## Fase 3: Construção do App no AppSheet

* \[ ] Conectar o AppSheet à planilha "Smart\_Market\_DB".
* \[ ] Configurar tabelas, tipos de dados e relacionamentos (Ex: `ID\_Nota` em `Produtos\_Comprados` como Ref para `Notas`).
* \[ ] Criar formulário de captura com leitor de QR Code integrado na aba `Fila\_Notas`.
* \[ ] Criar a visão do "Simulador de Compras" com fórmula de cálculo de melhor mercado.
* \[ ] Configurar Categorização de Produtos (mapeamento por palavras-chave ou seleção manual).

## Fase 4: Automação e Integração

* \[ ] Criar Bot/Automation no AppSheet: Ao adicionar linha em `Fila\_Notas`, chamar a API Python via Webhook.
* \[ ] Criar botão de ação manual "Reprocessar" na tela de Fila de Notas.

## Fase 5: Validação e Ajustes

* \[ ] Fazer testes reais bipando 5 notas fiscais de mercados diferentes no RS.
* \[ ] Validar margem de erro nos preços e nomes de produtos.
* \[ ] Ajustar a inteligência do simulador para desconsiderar preços com mais de 90 dias.

