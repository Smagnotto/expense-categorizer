import pandas as pd
import re
import json
import os
from collections import defaultdict
from difflib import SequenceMatcher
from datetime import datetime

ARQUIVO_MEMORIA = "memoria.json"
ARQUIVO_HISTORICO = "historico_transacoes.json"

# =========================
# 🧠 MEMÓRIA
# =========================
def carregar_memoria():
    if not os.path.exists(ARQUIVO_MEMORIA):
        return {}
    with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_memoria(memoria):
    with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, indent=2, ensure_ascii=False)

# =========================
# 📚 HISTÓRICO DE TRANSAÇÕES
# =========================
def carregar_historico(caminho_historico):
    if not os.path.exists(caminho_historico):
        return set()

    with open(caminho_historico, "r", encoding="utf-8") as f:
        return set(json.load(f))


def salvar_historico(historico, caminho_historico):
    with open(caminho_historico, "w", encoding="utf-8") as f:
        json.dump(
            sorted(list(historico)),
            f,
            indent=2,
            ensure_ascii=False
        )


def gerar_chave_transacao(t):
    descricao = re.sub(r"\s+", " ", t["descricao"].strip().lower())

    parcelamento = ""
    if pd.notna(t["parcelamento"]):
        parcelamento = str(t["parcelamento"]).strip().lower()

    return (
        f"{t['data']}|"
        f"{descricao}|"
        f"{parcelamento}|"
        f"{t['valor']:.2f}"
    )

# =========================
# 🧠 SIMILARIDADE
# =========================
def parecido(a, b):
    return SequenceMatcher(None, a, b).ratio()

#==========================
# MESES EM PORTUGUES
#==========================
MESES_PT =  {
    'janeiro': '01', 'fevereiro': '02', 'marco': '03', 'março': '03',
    'abril': '04', 'maio': '05', 'junho': '06', 'julho': '07',
    'agosto': '08', 'setembro': '09', 'outubro': '10',
    'novembro': '11', 'dezembro': '12'
}

# =========================
# EXTRAIR MÊS/ANO DO NOME
# =========================
def extrair_mes_ano(nome_base): 
    #Tenta padrão DD-YYYY (ex: 07-2026)
    m = re.search(r'(\d{2})-(\d{4})', nome_base)
    if m:
        return m.group(1), m.group(2)
    
    # Tenta nome do mês em português + ano (ex: junho2026)
    nome_lower = nome_base.lower()
    for nome_mes, num_mes in MESES_PT.items():
        m = re.search(
            rf'({re.escape(nome_mes)})(\d{{4}})',
            nome_lower,
            re.IGNORECASE
        )
        if m:
            return num_mes, m.group(2)

    raise ValueError('Não foi possível extrair mês/ano do nome do arquivo')

# =========================
# LER TRANSAÇÕES DO EXCEL
# =========================
def ler_transacoes_excel(caminho):
    df_raw = pd.read_excel(caminho, header=None)

    #Encontra a linha do cabeçalho (contém 'Data' e 'Lançamento')
    header_row = None
    for i, row in df_raw.iterrows():
        valores = row.values.tolist()
        if 'Data' in valores and 'Lançamento' in valores:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Cabeçalho 'Data'/'Lançamento' não encontrado no Excel")
    
    df = pd.read_excel(caminho, header=header_row)

    #Filtra apenas as colunas necessárias
    df = df[['Data', 'Lançamento','Parcelamento', 'Valor']].copy()

    #Remove linhas sem data, sem valor (linhas de subtotal, rodapé, etc...)
    df = df.dropna(subset=['Data', 'Valor'])
    df = df[df['Lançamento'].notna()]

    df= df[df['Valor'] > 0]

    transacoes = []
    for _, row in df.iterrows():
        data = pd.to_datetime(row['Data']).strftime('%d/%m/%Y')
        lancamento = str(row['Lançamento']).strip()
        parcelamento = row['Parcelamento']
        valor = float(row['Valor'])

        transacoes.append({
            'data': data,
            'descricao': lancamento,
            'parcelamento': parcelamento,
            'valor': valor,
            'categoria': None
        })

    return transacoes

# =========================
# 🤖 CLASSIFICADOR INTELIGENTE + TREINO
# =========================
def classificar(descricao, parcelamento, valor, memoria):
    d = descricao.lower()

    # 1️⃣ match exato
    if d in memoria:
        return memoria[d]

    # 2️⃣ contém
    for chave in memoria:
        if chave in d:
            return memoria[chave]

    # 3️⃣ similaridade
    melhor_match = None
    melhor_score = 0

    for chave in memoria:
        score = parecido(d, chave)
        if score > melhor_score:
            melhor_score = score
            melhor_match = chave

    if melhor_score > 0.75:
        return memoria[melhor_match]

    # 4️⃣ regra base
    categoria = classificar_base(descricao)

    #Combina lançamento + parcelamento na descrição
    if pd.notna(parcelamento) and str(parcelamento).strip():
        descricao = f"{descricao} - {str(parcelamento).strip()}"

    # 🔥 5️⃣ TREINO AUTOMÁTICO (APRENDIZADO)
    print(f"\n🔎 {descricao} - R${valor:.2f}")
    print(f"👉 Sugestão: {categoria}")

    resp = input("Está correto? (Enter=sim / digite nova categoria): ").strip()

    if resp:
        categoria = resp

    # salvar aprendizado
    memoria[d] = categoria
    salvar_memoria(memoria)

    return categoria


# =========================
# 📏 CLASSIFICADOR BASE
# =========================
def classificar_base(descricao):
    d = descricao.lower()

    if any(x in d for x in ["ifood", "food", "burger", "pizza", "lanch", "ifd"]):
        return "Alimentação"

    elif "99food" in d:
        return "Alimentação"

    elif "99" in d:
        return "Transporte"

    elif any(x in d for x in ["drogaria", "hospital"]):
        return "Saúde"

    elif "mercado" in d:
        return "Mercado"

    elif "pet" in d:
        return "Pets"

    elif any(x in d for x in ["apple", "anuidade"]):
        return "Assinaturas"

    else:
        return "Outros"


# =========================
# SALVAR EXCEL
# =========================
def salvar_excel(transacoes, caminho):
    rows = [{
        'Data': t['data'],
        'Descrição': t['descricao'],
        'Valor': t['valor'],
        'Conta': 'Pessoal',
        'Categoria': t['categoria']
    } for t in transacoes]

    df = pd.DataFrame(rows)
    df.to_excel(caminho, index=False)

# =========================
# RESUMO
# =========================
def resumo_por_categoria(transacoes):
    resumo = defaultdict(float)
    total_geral = 0.0

    for t in transacoes:
        resumo[t["categoria"]] += t["valor"]
        total_geral += t["valor"]

    return resumo, total_geral


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    arquivo_entrada = input("Informe o caminho da planilha excel: ")

    # Nome base
    nome_base = os.path.splitext(os.path.basename(arquivo_entrada))[0]

    # Extrair mês e ano com regex
    mes, ano = extrair_mes_ano(nome_base)

    # Diretório base
    diretorio_base = os.path.dirname(arquivo_entrada)

    # Criar estrutura: /ano/mes
    diretorio_final = os.path.join(diretorio_base, ano, mes)
    os.makedirs(diretorio_final, exist_ok=True)

    # Caminhos finais
    caminho_excel = os.path.join(diretorio_final, f"categorizado_{datetime.now().strftime("%d.%m.%Y_%H:%M:%S")}.xlsx")
    caminho_historico = os.path.join(diretorio_final, ARQUIVO_HISTORICO)

    memoria = carregar_memoria()
    historico = carregar_historico(caminho_historico)

    # =========================
    # LER FATURA
    # =========================
    transacoes = ler_transacoes_excel(arquivo_entrada)

    print(f"✅ {len(transacoes)} transações encontradas")

    # =========================
    # REMOVER DUPLICADAS
    # =========================
    novas_transacoes = []

    for t in transacoes:
        chave = gerar_chave_transacao(t)

        if chave not in historico:
            t["_chave"] = chave
            novas_transacoes.append(t)

    print(f"🆕 {len(novas_transacoes)} novas transações")

    if not novas_transacoes:
        print("\n✅ Nenhuma nova transação encontrada.")
        exit()

    # =========================
    # CLASSIFICAR
    # =========================
    for t in novas_transacoes:
        t["categoria"] = classificar(
            t["descricao"],
            t["parcelamento"],
            t["valor"],
            memoria
        )

    # =========================
    # ATUALIZAR HISTÓRICO
    # =========================
    for t in novas_transacoes:
        historico.add(t["_chave"])
        del t["_chave"]

    salvar_historico(historico, caminho_historico)

    # =========================
    # GERAR EXCEL
    # =========================
    salvar_excel(novas_transacoes, caminho_excel)

    print(f"\n💾 Excel salvo em: {caminho_excel}")

    # =========================
    # RESUMO
    # =========================
    print("\n📊 RESUMO POR CATEGORIA:")

    resumo, total_geral = resumo_por_categoria(novas_transacoes)

    for categoria, valor in sorted(resumo.items(), key=lambda x: x[1], reverse=True):
        percentual = (valor / total_geral) * 100 if total_geral > 0 else 0
        print(f"{categoria}: R$ {valor:.2f} ({percentual:.2f}%)")

    print(f"\n💰 TOTAL GERAL: R$ {total_geral:.2f}")