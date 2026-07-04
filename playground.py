"""
playground.py
-------------------------------------------------------------------
Agente de Coordenação e Segurança AEC
Interface web própria — um único comando sobe tudo.

Uso:
    python playground.py
    Abre http://localhost:7777 no navegador automaticamente.

4 verificações com IFC nativo (sem pset customizado):
  A — Clashes: todas disciplinas × estrutura + entre si
  B — Rota de fuga: porta normal × porta corta-fogo (PredefinedType nativo)
  C — Sistema de incêndio: extintores + sprinklers (IfcFireSuppressionTerminal)
  D — Análise completa
"""

import os
import sys
import json
import webbrowser
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(str(Path(__file__).parent / "skills/seguranca-aec/scripts"))

from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

agente_global = None
ifc_path_global = "modelo_exemplo.ifc"

# ---------------------------------------------------------------------------
# Interface HTML
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agente de Coordenação e Segurança AEC</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }
  .header { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 18px; font-weight: 600; color: #f0883e; }
  .header p { font-size: 13px; color: #8b949e; }
  .badge { background: #1f6feb22; border: 1px solid #1f6feb; color: #58a6ff; padding: 2px 10px; border-radius: 20px; font-size: 12px; }
  .container { max-width: 920px; margin: 40px auto; padding: 0 24px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 40px; }
  .card h2 { font-size: 22px; margin-bottom: 8px; }
  .subtitle { color: #8b949e; font-size: 14px; margin-bottom: 32px; }
  .field { margin-bottom: 20px; }
  .field label { display: block; font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
  .field input { width: 100%; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; color: #e6edf3; font-size: 14px; transition: border-color 0.2s; }
  .field input:focus { outline: none; border-color: #f0883e; }
  .field .hint { font-size: 12px; color: #8b949e; margin-top: 6px; }
  .btn-primary { background: #f0883e; color: #0d1117; border: none; border-radius: 8px; padding: 13px 32px; font-size: 15px; font-weight: 700; cursor: pointer; width: 100%; transition: background 0.2s; margin-top: 8px; }
  .btn-primary:hover { background: #e07535; }
  .btn-primary:disabled { background: #30363d; color: #8b949e; cursor: not-allowed; }
  .error-msg { background: #ff000022; border: 1px solid #f85149; border-radius: 8px; padding: 12px 16px; color: #f85149; font-size: 13px; margin-top: 16px; display: none; }
  .menu-screen { display: none; }
  .menu-header { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; }
  .ifc-info { font-size: 13px; color: #8b949e; }
  .ifc-info strong { color: #58a6ff; }
  .reset-btn { background: none; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; padding: 6px 14px; font-size: 12px; cursor: pointer; }
  .reset-btn:hover { border-color: #f85149; color: #f85149; }
  .menu-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .menu-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; cursor: pointer; transition: all 0.2s; text-align: left; }
  .menu-card:hover { border-color: #f0883e; background: #1c2128; transform: translateY(-2px); }
  .menu-card .letra { display: inline-block; background: #f0883e22; border: 1px solid #f0883e; color: #f0883e; width: 32px; height: 32px; border-radius: 8px; text-align: center; line-height: 32px; font-weight: 700; font-size: 16px; margin-bottom: 12px; }
  .menu-card h3 { font-size: 15px; font-weight: 600; color: #f0f6fc; margin-bottom: 6px; }
  .menu-card p { font-size: 12px; color: #8b949e; line-height: 1.5; }
  .menu-card-full { grid-column: 1 / -1; background: #1f2d1f; border-color: #3fb950; }
  .menu-card-full:hover { border-color: #3fb950; background: #243024; }
  .menu-card-full .letra { background: #3fb95022; border-color: #3fb950; color: #3fb950; }
  .results-screen { display: none; }
  .results-header { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 16px 24px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; }
  .back-btn { background: none; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; padding: 8px 16px; font-size: 13px; cursor: pointer; }
  .back-btn:hover { border-color: #f0883e; color: #f0883e; }
  .results-title { font-size: 16px; font-weight: 600; color: #f0f6fc; }
  .loading { text-align: center; padding: 60px; color: #8b949e; }
  .spinner { width: 40px; height: 40px; border: 3px solid #30363d; border-top-color: #f0883e; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .results-content { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 32px; line-height: 1.7; }
  .results-content h1, .results-content h2, .results-content h3 { color: #f0f6fc; margin: 20px 0 10px; }
  .results-content h1 { font-size: 20px; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
  .results-content h2 { font-size: 17px; color: #f0883e; }
  .results-content h3 { font-size: 15px; color: #58a6ff; }
  .results-content p { margin: 10px 0; color: #c9d1d9; font-size: 14px; }
  .results-content ul, .results-content ol { padding-left: 24px; margin: 10px 0; }
  .results-content li { margin: 6px 0; color: #c9d1d9; font-size: 14px; }
  .results-content table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }
  .results-content th { background: #21262d; padding: 10px 14px; text-align: left; color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; border: 1px solid #30363d; }
  .results-content td { padding: 10px 14px; border: 1px solid #30363d; color: #c9d1d9; }
  .results-content tr:nth-child(even) td { background: #161b22; }
  .results-content tr:nth-child(odd) td { background: #0d1117; }
  .results-content strong { color: #f0f6fc; }
  .results-content code { background: #21262d; border-radius: 4px; padding: 2px 6px; font-size: 12px; color: #f0883e; }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>🏗️ Agente de Coordenação e Segurança AEC</h1>
    <p>Análise de modelos BIM (IFC) com Inteligência Artificial</p>
  </div>
  <span class="badge">Agno + Claude + ifcopenshell</span>
</div>

<!-- SETUP -->
<div class="container" id="setupScreen">
  <div class="card">
    <h2>Configuração inicial</h2>
    <p class="subtitle">Informe sua chave da Anthropic e o arquivo IFC do seu projeto.</p>
    <div class="field">
      <label>Chave Anthropic API Key</label>
      <input type="password" id="apiKey" placeholder="sk-ant-..." />
      <p class="hint">Obtenha em <strong>console.anthropic.com</strong> → API Keys</p>
    </div>
    <div class="field">
      <label>Arquivo IFC do projeto</label>
      <input type="text" id="ifcPath" placeholder="modelo_exemplo.ifc" />
      <p class="hint">Deixe em branco para usar o modelo de exemplo incluído sem carregar outro arquivo</p>
    </div>
    <button class="btn-primary" id="btnSetup" onclick="setup()">Iniciar agente →</button>
    <div class="error-msg" id="setupError"></div>
  </div>
</div>

<!-- MENU -->
<div class="container menu-screen" id="menuScreen">
  <div class="menu-header">
    <div>
      <div style="font-size:15px;font-weight:600;margin-bottom:4px;">O que deseja verificar?</div>
      <div class="ifc-info">Modelo: <strong id="ifcLabel">modelo_exemplo.ifc</strong></div>
    </div>
    <button class="reset-btn" onclick="resetar()">⚙ Reconfigurar</button>
  </div>
  <div class="menu-grid">
    <div class="menu-card" onclick="verificar('a')">
      <div class="letra">A</div>
      <h3>Clashes Geométricos</h3>
      <p>Interferências 3D reais entre todas as disciplinas de instalações entre si e com a estrutura</p>
    </div>
    <div class="menu-card" onclick="verificar('b')">
      <div class="letra">B</div>
      <h3>Rota de Fuga</h3>
      <p>Distância real entre portas de apartamento e porta corta-fogo da escada de incêndio (NBR 9077)</p>
    </div>
    <div class="menu-card" onclick="verificar('c')">
      <div class="letra">C</div>
      <h3>Sistema de Incêndio</h3>
      <p>Cobertura de extintores e sprinklers em relação às portas do pavimento (NBR 12693 / NBR 10897)</p>
    </div>
    <div class="menu-card-full menu-card" onclick="verificar('d')">
      <div class="letra">D</div>
      <h3>Análise Completa — todas as verificações</h3>
      <p>Executa as três verificações em sequência com relatório completo e resumo executivo</p>
    </div>
  </div>
</div>

<!-- RESULTS -->
<div class="container results-screen" id="resultsScreen">
  <div class="results-header">
    <button class="back-btn" onclick="voltarMenu()">← Voltar ao menu</button>
    <div class="results-title" id="resultsTitle">Resultado</div>
    <div></div>
  </div>
  <div id="loadingDiv" class="loading">
    <div class="spinner"></div>
    <p>Analisando o modelo IFC...</p>
    <p style="font-size:12px;margin-top:8px;">O agente está lendo a geometria e consultando as normas</p>
  </div>
  <div class="results-content" id="resultsContent" style="display:none;"></div>
</div>

<script>
const TITULOS = {
  a: 'Clashes Geométricos',
  b: 'Rota de Fuga (NBR 9077)',
  c: 'Sistema de Incêndio (NBR 12693 / NBR 10897)',
  d: 'Análise Completa'
};

function mostrar(t) {
  document.getElementById('setupScreen').style.display = t==='setup'?'block':'none';
  document.getElementById('menuScreen').style.display = t==='menu'?'block':'none';
  document.getElementById('resultsScreen').style.display = t==='results'?'block':'none';
}

async function setup() {
  const apiKey = document.getElementById('apiKey').value.trim();
  const ifcPath = document.getElementById('ifcPath').value.trim() || 'modelo_exemplo.ifc';
  const btn = document.getElementById('btnSetup');
  const erro = document.getElementById('setupError');
  if (!apiKey) { erro.textContent='Informe sua chave Anthropic API Key.'; erro.style.display='block'; return; }
  btn.disabled=true; btn.textContent='Iniciando agente...'; erro.style.display='none';
  try {
    const res = await fetch('/api/setup', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({api_key:apiKey, ifc_path:ifcPath})});
    const data = await res.json();
    if (data.erro) { erro.textContent=data.erro; erro.style.display='block'; btn.disabled=false; btn.textContent='Iniciar agente →'; return; }
    document.getElementById('ifcLabel').textContent=data.ifc;
    mostrar('menu');
  } catch(e) { erro.textContent='Erro ao conectar com o backend.'; erro.style.display='block'; btn.disabled=false; btn.textContent='Iniciar agente →'; }
}

async function verificar(tipo) {
  document.getElementById('resultsTitle').textContent=TITULOS[tipo];
  document.getElementById('loadingDiv').style.display='block';
  document.getElementById('resultsContent').style.display='none';
  mostrar('results');
  try {
    const res = await fetch('/api/verificar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tipo})});
    const data = await res.json();
    document.getElementById('loadingDiv').style.display='none';
    document.getElementById('resultsContent').style.display='block';
    document.getElementById('resultsContent').innerHTML = data.erro ? `<p style="color:#f85149">${data.erro}</p>` : marked.parse(data.resultado||'');
  } catch(e) {
    document.getElementById('loadingDiv').style.display='none';
    document.getElementById('resultsContent').style.display='block';
    document.getElementById('resultsContent').innerHTML='<p style="color:#f85149">Erro ao obter resultado.</p>';
  }
}

function voltarMenu() { mostrar('menu'); }
function resetar() { mostrar('setup'); }
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=HTML)


@app.post("/api/setup")
async def api_setup(request: Request):
    global agente_global, ifc_path_global
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    ifc = data.get("ifc_path", "modelo_exemplo.ifc").strip() or "modelo_exemplo.ifc"

    if not api_key:
        return JSONResponse({"erro": "Chave não informada."}, status_code=400)
    if not Path(ifc).exists():
        return JSONResponse({"erro": f"Arquivo IFC não encontrado: {ifc}"}, status_code=400)

    os.environ["ANTHROPIC_API_KEY"] = api_key
    ifc_path_global = ifc

    from agno.agent import Agent
    from agno.models.anthropic import Claude
    from agno.skills import Skills, LocalSkills

    agente_global = Agent(
        id="AgenteCoordenacaoSeguranca",
        name="Agente de Coordenação e Segurança AEC",
        model=Claude(id="claude-sonnet-4-6"),
        skills=Skills(loaders=[LocalSkills(str(Path(__file__).parent / "skills"))]),
        tools=[
            detectar_clashes_instalacoes_estrutura,
            verificar_distancia_rota_fuga,
            verificar_sistema_incendio_completo,
        ],
        instructions=[
            "Você é um assistente técnico de arquitetura especializado em "
            "compatibilização de projetos e segurança contra incêndio.",
            "Use a skill 'seguranca-aec' como referência normativa.",
            f"O arquivo IFC do projeto está em: {ifc}",
            f"Use sempre o arquivo '{ifc}' nas tools.",
            "Para clashes use 'detectar_clashes_instalacoes_estrutura'.",
            "Para rota de fuga use 'verificar_distancia_rota_fuga'.",
            "Para extintores e sprinklers use 'verificar_sistema_incendio_completo'.",
            "Na análise completa execute as TRÊS verificações em sequência.",
            "Apresente resultados com tabelas markdown, conformes e não conformes separados.",
            "Responda em português, de forma técnica e objetiva.",
        ],
        markdown=True,
        debug_mode=False,
    )

    with open(Path(__file__).parent / ".env", "w") as f:
        f.write(f"ANTHROPIC_API_KEY={api_key}\nIFC_PATH={ifc}\n")

    return JSONResponse({"status": "ok", "ifc": ifc})


@app.post("/api/verificar")
async def api_verificar(request: Request):
    global agente_global, ifc_path_global
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)

    data = await request.json()
    tipo = data.get("tipo", "d")

    mensagens = {
        "a": f"Detecte todos os clashes geométricos no arquivo {ifc_path_global}. Apresente separado por tipo: estrutura x instalação e instalação x instalação entre disciplinas diferentes.",
        "b": f"Verifique a rota de fuga no arquivo {ifc_path_global}. Calcule a distância de cada porta até a porta corta-fogo da escada e compare com o limite da NBR 9077.",
        "c": f"Verifique o sistema de incêndio no arquivo {ifc_path_global}. Analise a cobertura de extintores (NBR 12693) e sprinklers (NBR 10897) em relação às portas do pavimento.",
        "d": f"Faça uma auditoria completa do arquivo {ifc_path_global}. Execute as TRÊS verificações: clashes geométricos, rota de fuga e sistema de incêndio (extintores + sprinklers). Apresente relatório completo com tabelas e resumo executivo.",
    }

    try:
        response = agente_global.run(mensagens.get(tipo, mensagens["d"]))
        resultado = response.get_content_as_string() if hasattr(response, 'get_content_as_string') else str(response.content)
        return JSONResponse({"resultado": resultado})
    except Exception as e:
        return JSONResponse({"erro": f"Erro: {str(e)}"}, status_code=500)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def detectar_clashes_instalacoes_estrutura(caminho_ifc: str) -> str:
    """Detecta clashes geométricos reais (bounding box 3D) entre todas as
    disciplinas de instalações entre si e com a estrutura.
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
        linhas.append(f"[{rotulo}] {a['disciplina']} '{a['nome']}' x {b['disciplina']} '{b['nome']}'")
    return f"{len(clashes)} clash(es):\n" + "\n".join(linhas)


def verificar_distancia_rota_fuga(caminho_ifc: str) -> str:
    """Verifica distância real entre portas de apartamento e porta corta-fogo
    da escada de incêndio, usando PredefinedType nativo do IFC (NBR 9077).
    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_rota_fuga(caminho_ifc)
    if resultados and "erro" in resultados[0]:
        return resultados[0]["erro"]
    return "\n".join([
        f"[{'CONFORME' if r['conforme'] else 'NÃO CONFORME'}] {r['porta_apartamento']} → {r['porta_escada_mais_proxima']}: {r['distancia_m']} m (limite: {r['limite_m']} m)"
        for r in resultados
    ])


def verificar_sistema_incendio_completo(caminho_ifc: str) -> str:
    """Verifica cobertura de extintores e sprinklers usando IfcFireSuppressionTerminal
    nativo do IFC, calculando distância até as portas do pavimento.
    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_sistema_incendio(caminho_ifc)
    if resultados and "erro" in resultados[0]:
        return resultados[0]["erro"]
    return "\n".join([
        f"[{r.get('categoria','')}] [{('CONFORME' if r.get('conforme') else 'NÃO CONFORME')}] {r.get('motivo','')}"
        for r in resultados
    ])


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    def abrir_navegador():
        time.sleep(2)
        webbrowser.open("http://localhost:7777")

    print("\n" + "=" * 55)
    print("  AGENTE DE COORDENAÇÃO E SEGURANÇA AEC")
    print("  Agno + Claude (Anthropic) + ifcopenshell")
    print("=" * 55)
    print("\n  Acesse: http://localhost:7777")
    print("  Abrindo navegador automaticamente...\n")

    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="localhost", port=7777)
