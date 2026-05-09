# Hub Open Finance — Guia Completo

## O que é este projeto?

Este é o **servidor central** do Open Finance da faculdade.
Ele recebe dados de clientes cadastrados em até 3 bancos diferentes
e oferece uma visão consolidada + análise de crédito.

---

## Estrutura de arquivos

```
hub/
├── main.py           ← código do servidor (FastAPI)
├── requirements.txt  ← dependências Python
└── README.md         ← este arquivo
```

Ao rodar o servidor, será criado automaticamente:
```
hub/
└── openfinance.db    ← banco de dados SQLite (gerado na primeira execução)
```

---

## Instalação e execução local

### 1. Instale as dependências

```bash
pip install -r requirements.txt
```

### 2. Inicie o servidor

```bash
uvicorn main:app --reload
```

O servidor estará disponível em: `http://localhost:8000`

### 3. Acesse a documentação interativa

Abra no navegador: `http://localhost:8000/docs`

A documentação do FastAPI (Swagger UI) permite testar todos os endpoints
diretamente pelo browser, sem precisar de Postman ou curl.

---

## Deploy gratuito no Render.com (para acesso pela internet)

### Passo a passo

1. Crie uma conta em https://render.com (grátis, sem cartão de crédito)
2. No dashboard, clique em **New → Web Service**
3. Conecte ao repositório GitHub com os arquivos do Hub
4. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Clique em **Create Web Service**

Em ~2 minutos o Hub estará online com uma URL pública, por exemplo:
```
https://hub-open-finance.onrender.com
```

> **Atenção (plano gratuito):** o servidor "hiberna" após 15 min sem uso.
> A primeira requisição após hibernação demora ~30 segundos para "acordar".
> Isso é normal e não afeta o funcionamento do projeto.

---

## Endpoints disponíveis

### `GET /`
Verifica se o Hub está online.

---

### `POST /bancos/registrar`
Registra um banco e retorna a API Key.
Cada aluno deve chamar **uma única vez** e guardar a chave gerada.

**Body:**
```json
{
  "nome": "Banco Alpha"
}
```

**Resposta:**
```json
{
  "mensagem": "Banco 'Banco Alpha' registrado com sucesso!",
  "banco_id": 1,
  "api_key": "a3f9c2e1d4b7...",
  "aviso": "GUARDE esta API Key! Ela não será exibida novamente."
}
```

---

### `GET /bancos`
Lista todos os bancos registrados (sem expor API Keys).

---

### `POST /clientes`
Cadastra um cliente no Open Finance.

**Cabeçalho obrigatório:**
```
api-key: sua_chave_aqui
```

**Body:**
```json
{
  "cpf": "123.456.789-00",
  "nome": "João da Silva",
  "renda": 5000.00,
  "dividas": 1200.00,
  "adimplente": true
}
```

---

### `GET /clientes/{cpf}`
Retorna os dados consolidados de um cliente em todos os bancos.

**Cabeçalho obrigatório:**
```
api-key: sua_chave_aqui
```

---

### `GET /clientes/{cpf}/analise`
Retorna a análise financeira completa do cliente.

**Cabeçalho obrigatório:**
```
api-key: sua_chave_aqui
```

**Resposta de exemplo:**
```json
{
  "cpf": "12345678900",
  "nome": "João da Silva",
  "score_credito": 720,
  "classificacao_risco": "Médio",
  "renda_media_consolidada": 5000.00,
  "dividas_totais": 1200.00,
  "adimplente": true,
  "limite_credito_sugerido": 7500.00,
  "produtos_sugeridos": ["Cartão Gold", "Empréstimo Pessoal"],
  "bancos_consultados": 2,
  "bancos": ["Banco Alpha", "Banco Beta"]
}
```

---

## Lógica do Score de Crédito

| Faixa    | Classificação | Limite de Crédito       |
|----------|---------------|-------------------------|
| 800–1000 | Baixo         | 3× a renda média        |
| 600–799  | Médio         | 1,5× a renda média      |
| 400–599  | Alto          | 0,5× a renda média      |
| 0–399    | Muito Alto    | Sem limite              |

**Fórmula:**
```
comprometimento = dívidas_totais / renda_média
score_base      = 1000 - (comprometimento × 500)
score_final     = score_base + 100  (se adimplente)
              ou  score_base - 200  (se inadimplente em qualquer banco)
```

---

## Fluxo resumido para os 3 alunos

```
1. O aluno responsável pelo Hub sobe o servidor no Render.com
2. Cada aluno chama POST /bancos/registrar → guarda sua api-key
3. Ao cadastrar um cliente no app do banco → o app chama POST /clientes no Hub
4. Qualquer banco pode consultar GET /clientes/{cpf}/analise para ver a análise
```
