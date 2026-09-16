# Arquitetura do Sistema e Estrutura de Dados

## 1\. Fluxo de Dados Integrado

\[ Celular / AppSheet ]

│ (1. Bipa QR Code)

▼

\[ Tabela 'Fila\_Notas' (Google Sheets) ]

│ (2. Dispara Webhook HTTP POST)

▼

\[ API Python (Backend Inovador) ]

│ (3. Raspagem na SEFAZ-RS via BeautifulSoup)

│ (4. Validação de Duplicidade por Chave de Acesso)

▼

\[ Google Sheets API (gspread) ]

│ (5. Insere Cabeçalho em 'Notas' e Itens em 'Produtos\_Comprados')

▼

\[ AppSheet Atualizado Automaticamente ]





\## 2. Modelagem do Banco de Dados (Google Sheets)



\### Aba 1: `Notas` (Cabeçalho da Compra)

\* `ID\_Nota` (Text, Primary Key - Chave de 44 dígitos da SEFAZ)

\* `Data\_Compra` (DateTime)

\* `Mercado\_Nome` (Text)

\* `Mercado\_CNPJ` (Text)

\* `Valor\_Total` (Decimal)

\* `URL\_QRCode` (Text)

\* `Data\_Cadastro` (DateTime)



\### Aba 2: `Produtos\_Comprados` (Itens Detalhados)

\* `ID\_Item` (Text, Primary Key - Auto)

\* `ID\_Nota` (Text, Foreign Key -> `Notas.ID\_Nota`)

\* `EAN` (Text - Código de Barras)

\* `Descricao` (Text)

\* `Categoria` (Text - Alimentação, Limpeza, Hortifrúti, etc.)

\* `Quantidade` (Decimal)

\* `Unidade` (Text - UN, KG, L)

\* `Valor\_Unitario` (Decimal)

\* `Valor\_Total` (Decimal)

\* `Data\_Compra` (Date - Herda da Nota para facilitar filtros)

\* `Mercado\_Nome` (Text - Herda da Nota)



\### Aba 3: `Fila\_Notas` (Gerenciamento de Erros/Re-tentativas)

\* `ID\_Fila` (Text)

\* `URL\_QRCode` (Text)

\* `Status` (Text - PENDENTE, PROCESSADO, ERRO)

\* `Mensagem\_Erro` (Text)

\* `Data\_Tentativa` (DateTime)



\### Aba 4: `Lista\_Desejos` (Simulador de Economia)

\* `ID\_Lista` (Text)

\* `EAN` (Text)

\* `Descricao` (Text)

\* `Quantidade\_Desejada` (Decimal)

