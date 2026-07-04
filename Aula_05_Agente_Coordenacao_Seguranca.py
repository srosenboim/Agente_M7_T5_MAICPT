"""
Aula_05_Agente_Coordenacao_Seguranca.py
-------------------------------------------------------------------
Agente de Coordenação de Disciplinas e Segurança AEC
Framework : Agno | Modelo: Claude (Anthropic) | BIM: ifcopenshell

Uso:
    python Aula_05_Agente_Coordenacao_Seguranca.py
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "skills/seguranca-aec/scripts"))

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.skills import LocalSkills

from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio
from verificar_guarda_corpos import verificar_guarda_corpos


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def detectar_clashes_instalacoes_estrutura(caminho_ifc: str) -> str:
    """Detecta clashes geométricos reais (bounding box 3D) entre:
    (1) instalações x estrutura;
    (2) instalações x instalações de disciplinas diferentes
        (HVAC, Hidráulica, Gás, Elétrica, Comunicação).

    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    clashes = detectar_clashes(caminho_ifc)
    if not clashes:
        return "Nenhum clash encontrado."
    linhas = []
    for c in clashes:
        a, b = c["elemento_a"], c["elemento_b"]
        rotulo = "ESTRUTURA x INSTALAÇÃO" if c["tipo"] == "instalacao_x_estrutura" else "INSTALAÇÃO x INSTALAÇÃO"
        linhas.append(
            f"[{rotulo}] {a['disciplina']} ({a['classe']} '{a['nome']}') "
            f"x {b['disciplina']} ({b['classe']} '{b['nome']}')"
        )
    return f"{len(clashes)} clash(es) encontrado(s):\n" + "\n".join(linhas)


def verificar_distancia_rota_fuga(caminho_ifc: str) -> str:
    """Verifica distância real entre cada porta de apartamento e a
    porta da escada de incêndio mais próxima (NBR 9077).

    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_rota_fuga(caminho_ifc)
    if resultados and "erro" in resultados[0]:
        return resultados[0]["erro"]
    linhas = [
        f"[{'✅ CONFORME' if r['conforme'] else '❌ NÃO CONFORME'}] "
        f"{r['porta_apartamento']} → {r['porta_escada_mais_proxima']}: "
        f"{r['distancia_m']} m (limite: {r['limite_m']} m)"
        for r in resultados
    ]
    return "\n".join(linhas)


def verificar_cobertura_extintores(caminho_ifc: str) -> str:
    """Verifica distância real entre cada porta de apartamento e o
    extintor mais próximo (NBR 12693).

    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_sistema_incendio(caminho_ifc)
    if resultados and "erro" in resultados[0]:
        return resultados[0]["erro"]
    linhas = [
        f"[{'✅ CONFORME' if r['conforme'] else '❌ NÃO CONFORME'}] "
        f"{r['porta_apartamento']} → {r['extintor_mais_proximo']}: "
        f"{r['distancia_m']} m (raio: {r['raio_cobertura_m']} m)"
        for r in resultados
    ]
    return "\n".join(linhas)


def verificar_alturas_guarda_corpo_janela(caminho_ifc: str) -> str:
    """Verifica altura de guarda-corpos e necessidade de proteção
    em janelas com peitoril baixo.

    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_guarda_corpos(caminho_ifc)
    linhas = [
        f"[{'✅ CONFORME' if r['conforme'] else '❌ NÃO CONFORME'}] "
        f"{r['categoria']} '{r['nome']}' ({r['local']}) — "
        f"{r['valores_medidos']} — {r['motivo']}"
        for r in resultados
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  AGENTE DE COORDENAÇÃO E SEGURANÇA AEC")
    print("  Agno + Claude (Anthropic) + ifcopenshell")
    print("=" * 60 + "\n")

    # 1. Chave Anthropic
    chave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not chave:
        print("Informe sua chave Anthropic (console.anthropic.com → API Keys):")
        chave = input("ANTHROPIC_API_KEY: ").strip()
        if not chave:
            print("Chave não informada. Encerrando.")
            sys.exit(1)
        os.environ["ANTHROPIC_API_KEY"] = chave

    # 2. Arquivo IFC
    print("\nInforme o caminho do arquivo IFC do seu projeto:")
    print("(ex: C:\\projetos\\edificio.ifc  ou  modelo_exemplo.ifc)\n")
    caminho_ifc = input("Arquivo IFC: ").strip().strip('"')

    if not os.path.exists(caminho_ifc):
        print(f"\nArquivo não encontrado: {caminho_ifc}")
        print("Verifique o caminho e tente novamente.")
        sys.exit(1)

    if not caminho_ifc.lower().endswith(".ifc"):
        print(f"\nEste arquivo não é um .ifc: {caminho_ifc}")
        print("Por favor exporte seu projeto como IFC:")
        print("  Revit    → Arquivo → Exportar → IFC")
        print("  ArchiCAD → Arquivo → Salvar como → IFC")
        print("  Bonsai   → Arquivo → Exportar → IFC")
        sys.exit(1)

    print(f"\nArquivo IFC encontrado: {caminho_ifc}")
    print("Iniciando análise completa...\n")

    # 3. Criar agente
    agente = Agent(
        name="AgenteCoordenacaoSeguranca",
        model=Claude(id="claude-sonnet-4-6"),
        skills=LocalSkills(os.path.join(os.path.dirname(__file__), "skills")),
        tools=[
            detectar_clashes_instalacoes_estrutura,
            verificar_distancia_rota_fuga,
            verificar_cobertura_extintores,
            verificar_alturas_guarda_corpo_janela,
        ],
        instructions=[
            "Você é um assistente técnico de arquitetura especializado em "
            "compatibilização de projetos e segurança contra incêndio e queda.",
            "Use a skill 'seguranca-aec' como referência normativa.",
            "SEMPRE use as tools para obter dados reais do IFC — nunca invente valores.",
            "Para 'análise geral' ou 'auditoria completa', execute as QUATRO "
            "verificações em sequência: clashes, rota de fuga, extintores, guarda-corpos.",
            "Apresente os resultados de forma clara, separando conformes de não conformes.",
            "Cite sempre o valor medido e o limite normativo de referência.",
            "Responda em português, de forma técnica e objetiva.",
        ],
        markdown=True,
    )

    # 4. Rodar análise completa automaticamente
    pergunta = f"Faça uma auditoria completa do arquivo {caminho_ifc}. Execute todas as verificações: clashes entre instalações e estrutura, clashes entre disciplinas de instalações, rota de fuga, cobertura de extintores e guarda-corpos/janelas. Apresente um relatório completo com todos os resultados."

    agente.print_response(pergunta, stream=True)

    # 5. Modo chat livre depois da análise
    print("\n" + "=" * 60)
    print("Análise concluída. Você pode fazer perguntas adicionais.")
    print("Digite 'sair' para terminar.")
    print("=" * 60 + "\n")

    while True:
        try:
            pergunta = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pergunta:
            continue
        if pergunta.lower() in ("sair", "exit", "quit", "q"):
            break
        agente.print_response(pergunta, stream=True)
        print()


if __name__ == "__main__":
    main()
