# =============================================================
#  Hub Open Finance — Servidor Central
#  Tecnologia: Python + FastAPI + SQLite
#  Execução local:  uvicorn main:app --reload
#  Deploy (Render): uvicorn main:app --host 0.0.0.0 --port $PORT
# =============================================================

import sqlite3
import secrets
import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

# ------------------------------------------------------------
# Configuração da aplicação
# ------------------------------------------------------------
app = FastAPI(
    title="Hub Open Finance",
    description="Servidor central que consolida dados de clientes de múltiplos bancos.",
    version="1.0.0",
)

DATABASE = "openfinance.db"


# ------------------------------------------------------------
# Banco de dados — criação das tabelas na inicialização
# ------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DATABASE)

    # Tabela de bancos registrados (cada aluno registra o seu)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bancos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT    NOT NULL UNIQUE,
            api_key    TEXT    NOT NULL UNIQUE,
            criado_em  TEXT    NOT NULL
        )
    """)

    # Tabela de clientes cadastrados pelos bancos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf           TEXT    NOT NULL,
            nome          TEXT    NOT NULL,
            renda         REAL    NOT NULL,
            dividas       REAL    NOT NULL DEFAULT 0.0,
            adimplente    INTEGER NOT NULL DEFAULT 1,  -- 1 = sim, 0 = não
            banco_id      INTEGER NOT NULL,
            cadastrado_em TEXT    NOT NULL,
            FOREIGN KEY (banco_id) REFERENCES bancos(id),
            UNIQUE(cpf, banco_id)  -- mesmo CPF não pode ser duplicado no mesmo banco
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ------------------------------------------------------------
# Helpers de banco de dados
# ------------------------------------------------------------
def get_conn():
    """Retorna uma conexão SQLite com leitura de colunas por nome."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # permite acessar colunas por nome: row["campo"]
    return conn


# ------------------------------------------------------------
# Modelos de dados (Pydantic valida automaticamente o JSON)
# ------------------------------------------------------------
class BancoRegistro(BaseModel):
    nome: str  # Ex: "Banco Alpha"


class ClienteEntrada(BaseModel):
    cpf:        str
    nome:       str
    renda:      float           # Renda mensal em R$
    dividas:    float = 0.0     # Total de dívidas em R$
    adimplente: bool  = True    # True = sem dívidas em atraso


# ------------------------------------------------------------
# Autenticação via API Key
# Cada banco usa sua própria chave no cabeçalho: api-key: <chave>
# ------------------------------------------------------------
def autenticar(api_key: str = Header(...)):
    """
    Valida a API Key enviada no cabeçalho da requisição.
    Retorna os dados do banco autenticado ou lança erro 401.
    """
    conn = get_conn()
    banco = conn.execute(
        "SELECT * FROM bancos WHERE api_key = ?", (api_key,)
    ).fetchone()
    conn.close()

    if not banco:
        raise HTTPException(status_code=401, detail="API Key inválida. Verifique sua chave.")

    return dict(banco)


# ------------------------------------------------------------
# Endpoint raiz — health check
# ------------------------------------------------------------
@app.get("/", tags=["Geral"])
def status():
    """Verifica se o Hub está online."""
    return {
        "sistema":  "Hub Open Finance",
        "status":   "online",
        "versao":   "1.0.0",
        "endpoints": [
            "POST  /bancos/registrar          → registra um banco",
            "POST  /clientes                  → cadastra cliente (requer api-key)",
            "GET   /clientes/{cpf}            → dados consolidados (requer api-key)",
            "GET   /clientes/{cpf}/analise    → análise completa  (requer api-key)",
            "GET   /bancos                    → lista bancos registrados",
        ],
    }


# ------------------------------------------------------------
# ENDPOINT 1 — Registrar um banco
# POST /bancos/registrar
# Cada aluno chama isso uma vez para obter sua API Key
# ------------------------------------------------------------
@app.post("/bancos/registrar", tags=["Bancos"])
def registrar_banco(dados: BancoRegistro):
    """
    Registra um novo banco no Open Finance e retorna uma API Key única.
    Cada aluno deve chamar este endpoint UMA VEZ e guardar a chave.
    """
    api_key = secrets.token_hex(16)  # gera chave aleatória segura
    agora   = datetime.datetime.now().isoformat()

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO bancos (nome, api_key, criado_em) VALUES (?, ?, ?)",
            (dados.nome, api_key, agora),
        )
        conn.commit()
        banco_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Já existe um banco com o nome '{dados.nome}'.")
    conn.close()

    return {
        "mensagem":  f"Banco '{dados.nome}' registrado com sucesso!",
        "banco_id":  banco_id,
        "api_key":   api_key,
        "aviso":     "GUARDE esta API Key! Ela não será exibida novamente.",
    }


# ------------------------------------------------------------
# ENDPOINT 2 — Listar bancos
# GET /bancos
# ------------------------------------------------------------
@app.get("/bancos", tags=["Bancos"])
def listar_bancos():
    """Lista todos os bancos registrados no Open Finance (sem expor API Keys)."""
    conn = get_conn()
    bancos = conn.execute(
        "SELECT id, nome, criado_em FROM bancos ORDER BY id"
    ).fetchall()
    conn.close()

    return {
        "total":  len(bancos),
        "bancos": [dict(b) for b in bancos],
    }


# ------------------------------------------------------------
# ENDPOINT 3 — Cadastrar cliente
# POST /clientes
# Cabeçalho obrigatório: api-key: <sua_chave>
# ------------------------------------------------------------
@app.post("/clientes", tags=["Clientes"])
def cadastrar_cliente(cliente: ClienteEntrada, banco=Depends(autenticar)):
    """
    Cadastra um cliente no Open Finance.
    O banco que fez a requisição é identificado pela API Key.
    Um mesmo CPF pode estar cadastrado em múltiplos bancos.
    """
    # Remove formatação do CPF (pontos e traço)
    cpf = cliente.cpf.replace(".", "").replace("-", "").strip()

    if len(cpf) != 11 or not cpf.isdigit():
        raise HTTPException(status_code=422, detail="CPF inválido. Use 11 dígitos numéricos.")

    agora = datetime.datetime.now().isoformat()

    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO clientes (cpf, nome, renda, dividas, adimplente, banco_id, cadastrado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cpf, cliente.nome, cliente.renda, cliente.dividas,
             1 if cliente.adimplente else 0, banco["id"], agora),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"CPF {cpf} já cadastrado no {banco['nome']}.",
        )
    conn.close()

    return {
        "mensagem":        f"Cliente '{cliente.nome}' cadastrado com sucesso!",
        "banco_registrou": banco["nome"],
        "cpf":             cpf,
    }


# ------------------------------------------------------------
# ENDPOINT 4 — Consultar dados consolidados de um cliente
# GET /clientes/{cpf}
# Retorna tudo que o Open Finance sabe sobre o CPF
# ------------------------------------------------------------
@app.get("/clientes/{cpf}", tags=["Clientes"])
def consultar_cliente(cpf: str, banco=Depends(autenticar)):
    """
    Retorna os dados consolidados de um cliente em todos os bancos.
    Qualquer banco autenticado pode consultar qualquer CPF.
    """
    cpf = cpf.replace(".", "").replace("-", "").strip()

    conn = get_conn()
    registros = conn.execute(
        """SELECT c.cpf, c.nome, c.renda, c.dividas, c.adimplente,
                  c.cadastrado_em, b.nome AS banco_nome
           FROM clientes c
           JOIN bancos b ON c.banco_id = b.id
           WHERE c.cpf = ?
           ORDER BY c.cadastrado_em""",
        (cpf,),
    ).fetchall()
    conn.close()

    if not registros:
        raise HTTPException(
            status_code=404,
            detail=f"CPF {cpf} não encontrado em nenhum banco do Open Finance.",
        )

    dados = [dict(r) for r in registros]

    return {
        "cpf":           cpf,
        "nome":          dados[0]["nome"],
        "total_bancos":  len(dados),
        "registros": [
            {
                "banco":          d["banco_nome"],
                "renda":          d["renda"],
                "dividas":        d["dividas"],
                "adimplente":     bool(d["adimplente"]),
                "cadastrado_em":  d["cadastrado_em"],
            }
            for d in dados
        ],
    }


# ------------------------------------------------------------
# ENDPOINT 5 — Análise completa do cliente
# GET /clientes/{cpf}/analise
# Consolida dados de todos os bancos e aplica o modelo de análise
# ------------------------------------------------------------
@app.get("/clientes/{cpf}/analise", tags=["Clientes"])
def analisar_cliente(cpf: str, banco=Depends(autenticar)):
    """
    Análise financeira consolidada do cliente:
      - Score de crédito (0 a 1000)
      - Classificação de risco
      - Limite de crédito sugerido
      - Produtos financeiros recomendados
    """
    cpf = cpf.replace(".", "").replace("-", "").strip()

    conn = get_conn()
    registros = conn.execute(
        """SELECT c.renda, c.dividas, c.adimplente, c.nome, b.nome AS banco_nome
           FROM clientes c
           JOIN bancos b ON c.banco_id = b.id
           WHERE c.cpf = ?""",
        (cpf,),
    ).fetchall()
    conn.close()

    if not registros:
        raise HTTPException(status_code=404, detail=f"CPF {cpf} não encontrado.")

    dados = [dict(r) for r in registros]

    # ---- Consolidação dos dados financeiros ----
    renda_media   = sum(d["renda"]   for d in dados) / len(dados)
    dividas_total = sum(d["dividas"] for d in dados)
    adimplente    = all(d["adimplente"] for d in dados)  # inadimplente em qualquer banco = False

    # ---- Cálculo do Score (0 a 1000) ----
    if renda_media > 0:
        comprometimento = dividas_total / renda_media   # proporção dívida/renda
        score = max(0.0, 1000 - comprometimento * 500)  # quanto mais dívida, menor o score
    else:
        score = 0.0

    # Bônus/penalidade por histórico de pagamentos
    score = score + 100 if adimplente else max(0.0, score - 200)
    score = round(min(1000, score))

    # ---- Classificação de risco ----
    if score >= 800:
        risco          = "Baixo"
        limite_credito = renda_media * 3.0
    elif score >= 600:
        risco          = "Médio"
        limite_credito = renda_media * 1.5
    elif score >= 400:
        risco          = "Alto"
        limite_credito = renda_media * 0.5
    else:
        risco          = "Muito Alto"
        limite_credito = 0.0

    # ---- Sugestão de produtos ----
    # ---- Nível de risco por comprometimento ----
    comprometimento_perc = round((dividas_total / renda_media * 100) if renda_media > 0 else 100, 1)

    if not adimplente or comprometimento_perc >= 50:
        nivel_risco = "alto_risco"
    elif comprometimento_perc >= 30:
        nivel_risco = "atencao"
    else:
        nivel_risco = "normal"

    # ---- Sugestão de produtos ----
    produtos = []

    if nivel_risco == "alto_risco":
        produtos = []  # nenhum produto de crédito para alto risco
    else:
        if score >= 700 and renda_media >= 5000:
            produtos.append("Cartão Platinum")
        elif score >= 500:
            produtos.append("Cartão Gold")
        else:
            produtos.append("Cartão Basic")

        if renda_media >= 3000 and adimplente and score >= 500:
            produtos.append("Empréstimo Pessoal")

        if renda_media >= 10000 and score >= 750:
            produtos.append("Investimento Premium")

        if score >= 600 and adimplente and nivel_risco == "normal":
            produtos.append("Crédito Consignado")

    return {
        "cpf":                       cpf,
        "nome":                      dados[0]["nome"],
        "score_credito":             score,
        "classificacao_risco":       risco,
        "nivel_risco":               nivel_risco,
        "comprometimento_perc":      comprometimento_perc,
        "renda_media_consolidada":   round(renda_media, 2),
        "dividas_totais":            round(dividas_total, 2),
        "adimplente":                adimplente,
        "limite_credito_sugerido":   round(limite_credito, 2),
        "produtos_sugeridos":        produtos,
        "bancos_consultados":        len(dados),
        "bancos":                    [d["banco_nome"] for d in dados],
    }

@app.put("/bancos/atualizar-nome", tags=["Bancos"])
def atualizar_nome(dados: BancoRegistro, banco=Depends(autenticar)):
    """Atualiza o nome do banco no Hub."""
    conn = get_conn()
    conn.execute(
        "UPDATE bancos SET nome = ? WHERE id = ?",
        (dados.nome, banco["id"])
    )
    conn.commit()
    conn.close()
    return {"mensagem": f"Nome atualizado para '{dados.nome}' com sucesso!"}
