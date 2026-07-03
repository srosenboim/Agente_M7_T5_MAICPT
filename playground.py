"""
playground.py
-------------------------------------------------------------------
Backend do agente — mesmo padrão ensinado na Aula 04 pelo professor.

Como executar:
    1. python playground.py          ← sobe em http://localhost:7777

    2. Em outro terminal, suba o agent-ui:
       cd agent-ui
       pnpm install
       pnpm dev                      ← abre http://localhost:3000

    3. No navegador, acesse http://localhost:3000
       Selecione o agente e converse.

Requisitos:
    pip install agno ifcopenshell anthropic fastapi uvicorn python-dotenv
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env se existir
load_dotenv()

# Se não tiver chave, pergunta e salva no .env
if True:
    print("\n" + "=" * 60)
    print("  AGENTE DE COORDENAÇÃO E SEGURANÇA AEC")
    print("=" * 60)
    print("\nChave Anthropic não encontrada.")
    print("Obtenha em: https://console.anthropic.com → API Keys\n")
    chave = input("Cole sua ANTHROPIC_API_KEY aqui: ").strip()
    if not chave:
        print("Chave não informada. Encerrando.")
        sys.exit(1)
    os.environ["ANTHROPIC_API_KEY"] = chave

    # Pergunta o arquivo IFC junto
    print("\nInforme o caminho do arquivo IFC do seu projeto.")
    print("(pressione Enter para usar o modelo de exemplo incluído sem carregar outro arquivo)\n")
    ifc = input("Caminho do arquivo IFC: ").strip().strip('"')
    if not ifc:
        ifc = "modelo_exemplo.ifc"
    os.environ["IFC_PATH"] = ifc

    # Salva tudo no .env para próximas execuções
    env_path = Path(__file__).parent / ".env"
    with open(env_path, "w") as f:
        f.write(f"ANTHROPIC_API_KEY={chave}\n")
        f.write(f"IFC_PATH={ifc}\n")
    print(f"\n✅ Configuração salva em .env — não será perguntada novamente.")
    print(f"   Modelo IFC: {ifc}\n")

# Valida o arquivo IFC
IFC_PATH = os.environ.get("IFC_PATH", "modelo_exemplo.ifc")
if not Path(IFC_PATH).exists():
    print(f"\n❌ Arquivo IFC não encontrado: {IFC_PATH}")
    print("   Coloque o arquivo .ifc na pasta do projeto e delete o .env para reconfigurar.")
    sys.exit(1)

sys.path.append(str(Path(__file__).parent / "skills/seguranca-aec/scripts"))

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.skills import Skills, LocalSkills
from agno.os import AgentOS

from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio
from verificar_guarda_corpos import verificar_guarda_corpos


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def detectar_clashes_instalacoes_estrutura(caminho_ifc: str) -> str:
    """Detecta clashes geométricos reais (bounding box 3D) entre:
    (1) instalações x estrutura (vigas, pilares, lajes, paredes);
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
# Agente — mesmo padrão da Aula 04
# ---------------------------------------------------------------------------

model = Claude(id="claude-sonnet-4-6")

agente = Agent(
    id="AgenteCoordenacaoSeguranca",
    name="Agente de Coordenação e Segurança AEC",
    model=model,
    skills=Skills(loaders=[LocalSkills("./skills")]),
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
        f"O arquivo IFC do projeto está em: {IFC_PATH}",
        f"Quando o usuário pedir qualquer análise, use sempre o arquivo '{IFC_PATH}' como caminho.",
        "Para análise de clashes, use a tool 'detectar_clashes_instalacoes_estrutura'.",
        "Para rota de fuga, use 'verificar_distancia_rota_fuga'.",
        "Para extintores, use 'verificar_cobertura_extintores'.",
        "Para guarda-corpos e janelas, use 'verificar_alturas_guarda_corpo_janela'.",
        "Quando o usuário pedir 'análise geral' ou 'auditoria completa', "
        "execute as QUATRO verificações em sequência sem pedir confirmação.",
        "Responda em português, de forma técnica e objetiva.",
    ],
    markdown=True,
    debug_mode=False,
)

# AgentOS — mesmo padrão da Aula 04
agent_os = AgentOS(
    id="AgenteCoordenacaoSeguranca",
    description="Agente de Coordenação de Disciplinas e Segurança AEC — detecta clashes e verifica critérios de segurança em modelos IFC",
    agents=[agente],
)

app = agent_os.get_app()

# ---------------------------------------------------------------------------
# Execução — sobe backend + frontend automaticamente
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import subprocess
    import threading
    import time
    import webbrowser

    agent_ui_path = Path(__file__).parent / "agent-ui"

    def subir_frontend():
        """Sobe o agent-ui (Next.js) em segundo plano."""
        if not agent_ui_path.exists():
            return
        # instala dependências se necessário
        subprocess.run(
            "npm install -g pnpm && pnpm install",
            cwd=str(agent_ui_path),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.Popen(
            "pnpm dev",
            cwd=str(agent_ui_path),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def abrir_navegador():
        """Aguarda o frontend subir e abre o navegador."""
        time.sleep(8)
        webbrowser.open("http://localhost:3000")

    print("\n✅ Iniciando backend em http://localhost:7777")
    print("🚀 Iniciando interface web em http://localhost:3000")
    print("🌐 O navegador abrirá automaticamente em alguns segundos...\n")

    threading.Thread(target=subir_frontend, daemon=True).start()
    threading.Thread(target=abrir_navegador, daemon=True).start()

    agent_os.serve(app="playground:app", reload=False)
