from pypdf import PdfReader, PdfWriter
import re
import csv
import json
import os
from collections import defaultdict
from difflib import SequenceMatcher

ARQUIVO_MEMORIA = "memoria.json"

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
# 🧠 SIMILARIDADE
# =========================
def parecido(a, b):
    return SequenceMatcher(None, a, b).ratio()


# =========================
# DESBLOQUEAR PDF
# =========================
def desbloquear_pdf(caminho_entrada, caminho_saida, senha):
    try:
        reader = PdfReader(caminho_entrada)

        if reader.is_encrypted:
            reader.decrypt(senha)

        writer = PdfWriter()

        for pagina in reader.pages:
            writer.add_page(pagina)

        with open(caminho_saida, "wb") as f:
            writer.write(f)

        return True
    except:
        return False


# =========================
# EXTRAIR TEXTO
# =========================
def extrair_texto_pdf(caminho):
    reader = PdfReader(caminho)
    texto = ""

    for pagina in reader.pages:
        texto += pagina.extract_text() + "\n"

    return texto



# =========================
# 🤖 CLASSIFICADOR INTELIGENTE + TREINO
# =========================
def classificar(descricao, memoria):
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

    # 🔥 5️⃣ TREINO AUTOMÁTICO (APRENDIZADO)
    print(f"\n🔎 {descricao}")
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

    if any(x in d for x in ["ifood", "food", "burger", "pizza", "lanch"]):
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
# EXTRAIR TRANSAÇÕES
# =========================
def extrair_transacoes(texto):
    linhas = texto.split("\n")
    transacoes = []

    capturando = False
    padrao = re.compile(r"^(\d{2}/\d{2})\s+(.+?)\s+(\d+,\d{2})$")

    for linha in linhas:
        linha = linha.strip()

        if "Continua..." in linha:
            capturando = True
            continue

        if "ENVIO MENS.AUTOMATICA" in linha:
            break

        if not capturando:
            continue

        match = padrao.match(linha)

        if match:
            data, descricao, valor = match.groups()
            valor = float(valor.replace(",", "."))

            transacoes.append({
                "data": data,
                "descricao": descricao,
                "valor": valor,
                "categoria": None
            })

    return transacoes


# =========================
# SALVAR CSV
# =========================
def salvar_csv(transacoes, caminho):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["data", "descricao", "valor", "categoria"]
        )
        writer.writeheader()
        writer.writerows(transacoes)


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
    arquivo_entrada = "C:\\faturas\\Fatura_07-2026.pdf"
    senha = "45086"

    # Nome base
    nome_base = os.path.splitext(os.path.basename(arquivo_entrada))[0]

    # Extrair mês e ano com regex
    match = re.search(r"(\d{2})-(\d{4})", nome_base)

    if match:
        mes, ano = match.groups()
    else:
        raise ValueError("Não foi possível extrair mês/ano do nome do arquivo")

    # Diretório base
    diretorio_base = os.path.dirname(arquivo_entrada)

    # Criar estrutura: /ano/mes
    diretorio_final = os.path.join(diretorio_base, ano, mes)

    # Criar pasta se não existir
    os.makedirs(diretorio_final, exist_ok=True)

    # Caminhos finais
    arquivo_saida = os.path.join(diretorio_final, f"{nome_base}_desbloqueada.pdf")
    caminho_txt = os.path.join(diretorio_final, f"{nome_base}.txt")
    caminho_csv = os.path.join(diretorio_final, f"{nome_base}.csv")

    memoria = carregar_memoria()

    # 1. Desbloquear
    if not desbloquear_pdf(arquivo_entrada, arquivo_saida, senha):
        print("❌ Erro ao desbloquear PDF")
        exit()

    # 2. Extrair texto
    texto = extrair_texto_pdf(arquivo_saida)

    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write(texto)

    # 3. Extrair transações
    transacoes = extrair_transacoes(texto)

    # 4. Classificar com aprendizado
    for t in transacoes:
        t["categoria"] = classificar(t["descricao"], memoria)

    # 5. Salvar CSV
    salvar_csv(transacoes, caminho_csv)

    # 6. Resumo
    print("\n📊 RESUMO POR CATEGORIA:")
    resumo, total_geral = resumo_por_categoria(transacoes)

    for categoria, valor in sorted(resumo.items(), key=lambda x: x[1], reverse=True):
        percentual = (valor / total_geral) * 100 if total_geral > 0 else 0
        print(f"{categoria}: R$ {valor:.2f} ({percentual:.2f}%)")

    print(f"\n💰 TOTAL GERAL: R$ {total_geral:.2f}")