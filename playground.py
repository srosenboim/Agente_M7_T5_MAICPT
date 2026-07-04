"""
playground.py — Agente de Coordenação e Segurança AEC
Framework: Agno | Modelo: Claude Sonnet | BIM: ifcopenshell
"""

import os, sys, json, webbrowser, threading, time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(str(Path(__file__).parent / "skills/seguranca-aec/scripts"))

from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

agente_global = None
ifc_paths = {"arch": None, "struct": None, "mep": None, "exemplo": None}

def ifc_ativo():
    """Retorna o primeiro IFC disponível para análise."""
    for key in ["arch", "struct", "mep", "exemplo"]:
        p = ifc_paths.get(key)
        if p and Path(p).exists():
            return p
    return None

def todos_ifc():
    """Retorna todos os IFCs disponíveis."""
    return [p for p in ifc_paths.values() if p and Path(p).exists()]

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
HTML = open(Path(__file__).parent / "interface.html", encoding="utf-8").read() if (Path(__file__).parent / "interface.html").exists() else ""

@app.get("/", response_class=HTMLResponse)
async def home():
    html_path = Path(__file__).parent / "interface.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def api_status():
    return JSONResponse({
        "agente_inicializado": agente_global is not None,
        "ifc_ativo": ifc_ativo(),
        "ifcs": {k: v for k, v in ifc_paths.items() if v},
        "pasta_projeto": str(Path(__file__).parent),
    })

# ---------------------------------------------------------------------------
# Upload IFC
# ---------------------------------------------------------------------------
@app.post("/api/upload-ifc")
async def upload_ifc(request: Request):
    form = await request.form()
    tipo = form.get("tipo", "exemplo")  # arch, struct, mep, exemplo
    arquivo = form.get("file")
    if not arquivo:
        return JSONResponse({"erro": "Nenhum arquivo enviado."}, status_code=400)
    import shutil
    destino = Path(__file__).parent / arquivo.filename
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    ifc_paths[tipo] = str(destino)
    return JSONResponse({"status": "ok", "tipo": tipo, "arquivo": arquivo.filename, "caminho": str(destino)})

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
@app.post("/api/setup")
async def api_setup(request: Request):
    global agente_global
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    usar_exemplo = data.get("usar_exemplo", False)

    if not api_key:
        return JSONResponse({"erro": "Chave não informada."}, status_code=400)

    if usar_exemplo:
        exemplo = Path(__file__).parent / "modelo_exemplo.ifc"
        if not exemplo.exists():
            return JSONResponse({"erro": "modelo_exemplo.ifc não encontrado na pasta do projeto."}, status_code=400)
        ifc_paths["exemplo"] = str(exemplo)

    if not ifc_ativo():
        return JSONResponse({"erro": "Nenhum arquivo IFC carregado. Escolha um arquivo ou use o modelo de exemplo."}, status_code=400)

    os.environ["ANTHROPIC_API_KEY"] = api_key

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
            "compatibilização de projetos BIM e segurança contra incêndio.",
            "Use a skill 'seguranca-aec' como referência normativa.",
            "SEMPRE chame as tools para obter dados reais do modelo IFC. "
            "Nunca invente ou estime valores — sem chamar as tools você não sabe o que está no modelo.",
            "Para clashes, chame 'detectar_clashes_instalacoes_estrutura'.",
            "Para rota de fuga, chame 'verificar_distancia_rota_fuga'.",
            "Para extintores e sprinklers, chame 'verificar_sistema_incendio_completo'.",
            "Na análise completa, chame as TRÊS tools em sequência.",
            "Use os nomes EXATOS retornados pelas tools — nunca renomeie elementos.",
            "Sprinklers: verificação por cobertura de área (m²/cabeça), não por distância até portas.",
            "Apresente resultados em português com tabelas markdown.",
        ],
        markdown=True,
        debug_mode=False,
    )

    # Salva configuração
    env_path = Path(__file__).parent / ".env"
    with open(env_path, "w") as f:
        f.write(f"ANTHROPIC_API_KEY={api_key}\n")
        if ifc_paths.get("exemplo"):
            f.write(f"IFC_EXEMPLO={ifc_paths['exemplo']}\n")

    return JSONResponse({"status": "ok", "ifc_ativo": ifc_ativo(), "ifcs": {k: v for k, v in ifc_paths.items() if v}})

# ---------------------------------------------------------------------------
# Streaming — professor vê o agente rodando em tempo real
# ---------------------------------------------------------------------------
@app.post("/api/stream-verificar")
async def stream_verificar(request: Request):
    """SSE — transmite o agente pensando + resultado em tempo real."""
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)
    data = await request.json()
    tipo = data.get("tipo", "d")

    mensagens = {
        "a": "Use a tool 'detectar_clashes_instalacoes_estrutura' para detectar todos os clashes geométricos no modelo IFC carregado.",
        "b": "Use a tool 'verificar_distancia_rota_fuga' para verificar a rota de fuga do modelo IFC carregado.",
        "c": "Use a tool 'verificar_sistema_incendio_completo' para verificar o sistema de incêndio (extintores e sprinklers) do modelo IFC carregado.",
        "d": "Use as três tools em sequência: 'detectar_clashes_instalacoes_estrutura', depois 'verificar_distancia_rota_fuga', depois 'verificar_sistema_incendio_completo'. Apresente relatório completo com tabelas e resumo executivo.",
    }

    from agno.run.agent import RunEvent

    async def gerar_eventos():
        try:
            yield f"data: {json.dumps({'tipo': 'inicio', 'msg': 'Agente iniciado...'})}\n\n"

            conteudo_final = ""

            for evento in agente_global.run(mensagens.get(tipo, mensagens["d"]), stream=True, stream_events=True):
                ev = evento.event if hasattr(evento, 'event') else None

                if ev == RunEvent.tool_call_started:
                    tool_name = getattr(evento, 'tool_name', '') or getattr(evento, 'tool', {})
                    if hasattr(tool_name, 'get'):
                        tool_name = tool_name.get('name', 'tool')
                    yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': str(tool_name)})}\n\n"

                elif ev == RunEvent.tool_call_completed:
                    tool_name = getattr(evento, 'tool_name', '') or ''
                    tool_result = ''
                    if hasattr(evento, 'content'):
                        tool_result = str(evento.content)[:500]
                    yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': str(tool_name), 'resultado': tool_result})}\n\n"

                elif ev == RunEvent.run_content:
                    delta = ''
                    if hasattr(evento, 'content') and evento.content:
                        delta = str(evento.content)
                    elif hasattr(evento, 'delta') and evento.delta:
                        delta = str(evento.delta)
                    if delta:
                        conteudo_final += delta
                        yield f"data: {json.dumps({'tipo': 'conteudo', 'delta': delta})}\n\n"

                elif ev == RunEvent.run_completed:
                    if not conteudo_final and hasattr(evento, 'content') and evento.content:
                        conteudo_final = evento.get_content_as_string() if hasattr(evento, 'get_content_as_string') else str(evento.content)
                        yield f"data: {json.dumps({'tipo': 'conteudo', 'delta': conteudo_final})}\n\n"
                    yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"
                    return

        except Exception as e:
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': str(e)})}\n\n"

    return StreamingResponse(gerar_eventos(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ---------------------------------------------------------------------------
# Chat livre (sem streaming)
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def api_chat(request: Request):
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)
    data = await request.json()
    mensagem = data.get("mensagem", "").strip()
    if not mensagem:
        return JSONResponse({"erro": "Mensagem vazia."}, status_code=400)
    try:
        response = agente_global.run(mensagem)
        resultado = response.get_content_as_string() if hasattr(response, "get_content_as_string") else str(response.content)
        return JSONResponse({"resultado": resultado})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)

# ---------------------------------------------------------------------------
# Viewer 3D
# ---------------------------------------------------------------------------
@app.get("/api/viewer-data")
async def viewer_data():
    ifc = ifc_ativo()
    if not ifc:
        return JSONResponse({"erro": "Nenhum arquivo IFC carregado."}, status_code=400)
    try:
        import ifcopenshell.geom
        import ifcopenshell.util.unit as ifc_unit
        from colorir_auditoria_ifc import colorir_auditoria

        model = ifcopenshell.open(ifc)
        escala = ifc_unit.calculate_unit_scale(model)
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)

        # Identifica elementos com problema
        clash_nomes, nc_nomes = set(), set()
        try:
            for c in detectar_clashes(ifc):
                clash_nomes.add(c["elemento_a"]["nome"])
                clash_nomes.add(c["elemento_b"]["nome"])
        except: pass
        try:
            for r in verificar_rota_fuga(ifc):
                if not r.get("conforme") and "porta_apartamento" in r:
                    nc_nomes.add(r["porta_apartamento"])
        except: pass
        try:
            for r in verificar_sistema_incendio(ifc):
                if not r.get("conforme"):
                    porta = r.get("porta") or r.get("porta_apartamento")
                    if porta: nc_nomes.add(porta)
        except: pass

        elementos = []
        for el in model.by_type("IfcProduct"):
            if not el.Representation:
                continue
            try:
                shape = ifcopenshell.geom.create_shape(settings, el)
                v = shape.geometry.verts
                xs, ys, zs = v[0::3], v[1::3], v[2::3]
                nome = el.Name or el.is_a()
                if nome in clash_nomes:
                    cor, status = "#f59e0b", "CLASH"
                elif nome in nc_nomes:
                    cor, status = "#ef4444", "NÃO CONFORME"
                else:
                    cor, status = "#6b7280", "OK"
                elementos.append({
                    "nome": nome, "tipo": el.is_a(), "cor": cor, "status": status,
                    "bbox": {"xmin": min(xs), "xmax": max(xs), "ymin": min(ys), "ymax": max(ys), "zmin": min(zs), "zmax": max(zs)}
                })
            except: continue

        if not elementos:
            return JSONResponse({"erro": "Nenhum elemento com geometria 3D encontrado. Use o modelo_exemplo.ifc para visualização 3D."})
        return JSONResponse({"elementos": elementos, "total": len(elementos)})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)

# ---------------------------------------------------------------------------
# Download IFC auditado
# ---------------------------------------------------------------------------
@app.get("/api/download-ifc-auditado")
async def download_ifc_auditado():
    ifc = ifc_ativo()
    if not ifc or not Path(ifc).exists():
        return JSONResponse({"erro": "Arquivo IFC não encontrado. Faça uma análise primeiro."}, status_code=400)
    try:
        from colorir_auditoria_ifc import colorir_auditoria
        nome_saida = Path(ifc).stem + "_auditado.ifc"
        saida_abs = Path(__file__).parent / nome_saida
        colorir_auditoria(ifc, str(saida_abs))
        if not saida_abs.exists():
            return JSONResponse({"erro": "Falha ao gerar arquivo IFC auditado."}, status_code=500)
        return FileResponse(
            path=str(saida_abs),
            filename=nome_saida,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{nome_saida}"'}
        )
    except Exception as e:
        return JSONResponse({"erro": f"Erro: {str(e)}"}, status_code=500)

# ---------------------------------------------------------------------------
# Nova análise (troca IFC mantendo chave)
# ---------------------------------------------------------------------------
@app.post("/api/trocar-ifc")
async def api_trocar_ifc(request: Request):
    global agente_global
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)
    data = await request.json()
    tipo = data.get("tipo", "exemplo")
    usar_exemplo = data.get("usar_exemplo", False)
    if usar_exemplo:
        exemplo = Path(__file__).parent / "modelo_exemplo.ifc"
        ifc_paths["exemplo"] = str(exemplo)
        for k in ["arch", "struct", "mep"]:
            ifc_paths[k] = None
    return JSONResponse({"status": "ok", "ifc_ativo": ifc_ativo()})

# ---------------------------------------------------------------------------
# Tools — usam ifc_ativo() automaticamente
# ---------------------------------------------------------------------------
def detectar_clashes_instalacoes_estrutura() -> str:
    """Detecta clashes geométricos reais (bounding box 3D) entre todas as
    disciplinas de instalações entre si e com a estrutura.
    Não requer parâmetros — usa o modelo IFC carregado no sistema.
    """
    ifc = ifc_ativo()
    if not ifc:
        return "Nenhum arquivo IFC carregado. Configure o agente primeiro."
    try:
        clashes = detectar_clashes(ifc)
        if not clashes:
            return "Nenhum clash encontrado no modelo."
        linhas = []
        for c in clashes:
            a, b = c["elemento_a"], c["elemento_b"]
            rotulo = "ESTRUTURA x INSTALAÇÃO" if c["tipo"] == "instalacao_x_estrutura" else "INSTALAÇÃO x INSTALAÇÃO"
            linhas.append(f"[{rotulo}] {a['disciplina']} '{a['nome']}' x {b['disciplina']} '{b['nome']}'")
        return f"Arquivo analisado: {Path(ifc).name}\n{len(clashes)} clash(es) encontrado(s):\n" + "\n".join(linhas)
    except Exception as e:
        return f"Erro ao analisar clashes: {str(e)}"

def verificar_distancia_rota_fuga() -> str:
    """Verifica distância real entre portas de apartamento e porta corta-fogo
    da escada de incêndio (NBR 9077).
    Não requer parâmetros — usa o modelo IFC carregado no sistema.
    """
    ifc = ifc_ativo()
    if not ifc:
        return "Nenhum arquivo IFC carregado."
    try:
        resultados = verificar_rota_fuga(ifc)
        if resultados and "erro" in resultados[0]:
            return f"Arquivo analisado: {Path(ifc).name}\n{resultados[0]['erro']}"
        linhas = [
            f"[{'CONFORME' if r['conforme'] else 'NÃO CONFORME'}] {r['porta_apartamento']} → {r['porta_escada_mais_proxima']}: {r['distancia_m']} m (limite: {r['limite_m']} m)"
            for r in resultados
        ]
        return f"Arquivo analisado: {Path(ifc).name}\n" + "\n".join(linhas)
    except Exception as e:
        return f"Erro ao verificar rota de fuga: {str(e)}"

def verificar_sistema_incendio_completo() -> str:
    """Verifica cobertura de extintores (raio de alcance, NBR 12693) e
    sprinklers (densidade de área por cabeça, NBR 10897).
    Não requer parâmetros — usa o modelo IFC carregado no sistema.
    """
    ifc = ifc_ativo()
    if not ifc:
        return "Nenhum arquivo IFC carregado."
    try:
        resultados = verificar_sistema_incendio(ifc)
        if resultados and "erro" in resultados[0]:
            return f"Arquivo analisado: {Path(ifc).name}\n{resultados[0]['erro']}"
        linhas = [
            f"[{r.get('categoria','')}] [{'CONFORME' if r.get('conforme') else 'NÃO CONFORME'}] {r.get('motivo','')}"
            for r in resultados
        ]
        return f"Arquivo analisado: {Path(ifc).name}\n" + "\n".join(linhas)
    except Exception as e:
        return f"Erro ao verificar sistema de incêndio: {str(e)}"

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
    print("\n  Acesse: http://localhost:7777\n")

    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="localhost", port=7777)
