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
    """SSE — roda scripts diretamente e transmite progresso em tempo real."""
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)
    data = await request.json()
    tipo = data.get("tipo", "d")

    async def gerar_eventos():
        import anthropic
        resultados = {}

        try:
            yield f"data: {json.dumps({'tipo': 'inicio', 'msg': 'Agente iniciado...'})}\n\n"

            # Roda scripts diretamente — garante dados reais
            if tipo in ("a", "d"):
                yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': 'detectar_clashes_instalacoes_estrutura'})}\n\n"
                resultado_a = detectar_clashes_instalacoes_estrutura()
                resultados["clashes"] = resultado_a
                yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': 'detectar_clashes_instalacoes_estrutura', 'resultado': resultado_a[:300]})}\n\n"

            if tipo in ("b", "d"):
                yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': 'verificar_distancia_rota_fuga'})}\n\n"
                resultado_b = verificar_distancia_rota_fuga()
                resultados["rota_fuga"] = resultado_b
                yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': 'verificar_distancia_rota_fuga', 'resultado': resultado_b[:300]})}\n\n"

            if tipo in ("c", "d"):
                yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': 'verificar_sistema_incendio_completo'})}\n\n"
                resultado_c = verificar_sistema_incendio_completo()
                resultados["sistema_incendio"] = resultado_c
                yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': 'verificar_sistema_incendio_completo', 'resultado': resultado_c[:300]})}\n\n"

            # Manda dados reais para Claude formatar
            yield f"data: {json.dumps({'tipo': 'formatando', 'msg': 'Claude formatando relatório...'})}\n\n"

            titulos = {
                "a": "Clashes Geométricos",
                "b": "Rota de Fuga (NBR 9077)",
                "c": "Sistema de Incêndio (NBR 12693 / NBR 10897)",
                "d": "Auditoria Completa"
            }

            dados_texto = "\n\n".join([f"**{k}:**\n{v}" for k, v in resultados.items()])
            prompt = f"""Com base nos dados reais obtidos pelo ifcopenshell do modelo IFC, elabore um relatório técnico profissional em português.

DADOS REAIS DO MODELO IFC:
{dados_texto}

Apresente em markdown com tabelas, separando conformes de não conformes.
Use os nomes EXATOS dos elementos retornados pelos dados acima.
Inclua um resumo executivo no final.
Sprinklers: verificação por cobertura de área (m²/cabeça), não por distância."""

            # Streaming do Claude via anthropic direto
            client = anthropic.Anthropic()
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'tipo': 'conteudo', 'delta': text})}\n\n"

            yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': str(e)})}\n\n"

    return StreamingResponse(
        gerar_eventos(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

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
        # Lógica correta de rota de fuga:
        # 1. Portas de entrada (>=0.80m) longe da escada → marca a porta
        # 2. Porta de escada que não é corta-fogo → marca a porta
        # 3. Escada sem nenhuma porta → marca a escada
        try:
            import ifcopenshell.util.unit as _ifc_unit
            import ifcopenshell.util.placement as _ifc_pl
            import math as _math
            model_temp = ifcopenshell.open(ifc)
            _escala = _ifc_unit.calculate_unit_scale(model_temp)

            # Separa portas por tamanho
            portas_entrada = []  # >= 0.80m
            for door in model_temp.by_type("IfcDoor"):
                w = getattr(door, "OverallWidth", None)
                if w and float(w) * _escala >= 0.80:
                    pos = _ifc_pl.get_local_placement(door.ObjectPlacement)
                    x, y = pos[0,3] * _escala, pos[1,3] * _escala
                    pt = getattr(door, "PredefinedType", None)
                    ot = (getattr(door, "ObjectType", "") or "").lower()
                    nm = (door.Name or "").lower()
                    e_corta_fogo = any(k in ot+nm for k in ("corta","fire","emergency","cf"))
                    portas_entrada.append({
                        "nome": door.Name, "x": x, "y": y,
                        "e_corta_fogo": e_corta_fogo, "w": float(w)*_escala
                    })

            # Posições das escadas
            pos_escadas = []
            for stair in model_temp.by_type("IfcStair"):
                pos = _ifc_pl.get_local_placement(stair.ObjectPlacement)
                pos_escadas.append({
                    "nome": stair.Name,
                    "x": pos[0,3] * _escala,
                    "y": pos[1,3] * _escala
                })

            LIMITE_FUGA = 30.0  # metros

            if pos_escadas:
                for porta in portas_entrada:
                    # Distância até escada mais próxima
                    menor_dist = min(
                        _math.hypot(porta["x"]-e["x"], porta["y"]-e["y"])
                        for e in pos_escadas
                    )
                    if porta["e_corta_fogo"]:
                        # Porta de escada sem ser corta-fogo — marca amarelo
                        nc_nomes.add(porta["nome"])
                    elif menor_dist > LIMITE_FUGA:
                        # Porta longe da escada — marca amarelo
                        nc_nomes.add(porta["nome"])
            else:
                # Sem escadas identificadas — marca todas as portas de entrada
                for porta in portas_entrada:
                    nc_nomes.add(porta["nome"])
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
                    cor, status = "#ef4444", "CLASH"
                elif nome in nc_nomes:
                    cor, status = "#f59e0b", "NÃO CONFORME"
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
# Download JSON — dados brutos dos elementos com problema
# ---------------------------------------------------------------------------
@app.get("/api/download-json")
async def download_json():
    ifc = ifc_ativo()
    if not ifc:
        return JSONResponse({"erro": "Nenhum arquivo IFC carregado."}, status_code=400)
    try:
        import ifcopenshell.geom
        import ifcopenshell.util.unit as ifc_unit

        model = ifcopenshell.open(ifc)
        escala = ifc_unit.calculate_unit_scale(model)
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)

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
        try:
            model_temp = ifcopenshell.open(ifc)
            for door in model_temp.by_type("IfcDoor"):
                w = getattr(door, "OverallWidth", None)
                if w is not None and float(w) < 0.80:
                    nc_nomes.add(door.Name)
        except: pass

        elementos_problema = []
        for el in model.by_type("IfcProduct"):
            nome = el.Name or el.is_a()
            if nome in clash_nomes:
                elementos_problema.append({
                    "nome": nome, "classe": el.is_a(),
                    "cor": "vermelho", "status": "CLASH",
                    "motivo": "Interferência geométrica com outro elemento"
                })
            elif nome in nc_nomes:
                elementos_problema.append({
                    "nome": nome, "classe": el.is_a(),
                    "cor": "amarelo", "status": "NÃO CONFORME",
                    "motivo": "Elemento não atende critério normativo"
                })

        output = json.dumps({
            "arquivo_ifc": Path(ifc).name,
            "total_problemas": len(elementos_problema),
            "elementos": elementos_problema
        }, indent=2, ensure_ascii=False)

        saida = Path(__file__).parent / "auditoria_dados.json"
        saida.write_text(output, encoding="utf-8")
        return FileResponse(path=str(saida), filename="auditoria_dados.json",
                           media_type="application/json",
                           headers={"Content-Disposition": 'attachment; filename="auditoria_dados.json"'})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Download PDF — relatório formatado
# ---------------------------------------------------------------------------
relatorio_html_global = ""

@app.post("/api/salvar-relatorio")
async def salvar_relatorio(request: Request):
    """Salva o conteúdo HTML do relatório para download posterior."""
    global relatorio_html_global
    data = await request.json()
    relatorio_html_global = data.get("html", "")
    return JSONResponse({"status": "ok"})

@app.get("/api/download-pdf")
async def download_pdf():
    global relatorio_html_global
    if not relatorio_html_global:
        return JSONResponse({"erro": "Nenhum relatorio gerado ainda. Execute uma analise primeiro."}, status_code=400)
    try:
        from fpdf import FPDF
        import re, html as html_lib

        ifc_nome = Path(ifc_ativo() or "modelo").name if ifc_ativo() else "modelo"

        # Convert HTML to plain text
        text = re.sub(r'<li[^>]*>', '- ', relatorio_html_global)
        text = re.sub(r'<h[1-3][^>]*>(.*?)</h[1-3]>', lambda m: chr(10)+'###'+m.group(1)+'###'+chr(10), text, flags=re.DOTALL)
        text = re.sub(r'<tr[^>]*>', chr(10), text)
        text = re.sub(r'<t[dh][^>]*>(.*?)</t[dh]>', lambda m: m.group(1)+' | ', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_lib.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', chr(10)+chr(10), text)
        # Encode to latin-1 safely
        text = text.encode('latin-1', errors='replace').decode('latin-1')
        ifc_safe = ifc_nome.encode('latin-1', errors='replace').decode('latin-1')

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Header
        pdf.set_fill_color(26, 26, 26)
        pdf.rect(0, 0, 210, 28, 'F')
        pdf.set_font('Helvetica', 'B', 15)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(10, 8)
        pdf.cell(0, 8, 'Relatorio de Auditoria BIM - Coordenacao e Seguranca AEC', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(161, 161, 170)
        pdf.set_x(10)
        pdf.cell(0, 6, f'Arquivo: {ifc_safe}  |  Agno + Claude Sonnet 4.6 + ifcopenshell', new_x='LMARGIN', new_y='NEXT')
        pdf.set_y(35)

        for line in text.split(chr(10)):
            line = line.strip()
            if not line:
                pdf.ln(3)
            elif '###' in line:
                clean = line.replace('###','').strip()
                pdf.set_font('Helvetica', 'B', 12)
                pdf.set_text_color(194, 65, 12)
                pdf.ln(4)
                if clean:
                    pdf.cell(0, 7, clean[:90], new_x='LMARGIN', new_y='NEXT')
                pdf.set_draw_color(249, 115, 22)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(2)
            elif ' | ' in line:
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(50, 50, 50)
                pdf.set_fill_color(243, 244, 246)
                pdf.multi_cell(0, 5, line[:200])
            elif line.startswith('-'):
                pdf.set_font('Helvetica', '', 10)
                pdf.set_text_color(26, 26, 26)
                pdf.set_x(15)
                pdf.multi_cell(180, 5, line[:200])
            else:
                pdf.set_font('Helvetica', '', 10)
                pdf.set_text_color(26, 26, 26)
                pdf.multi_cell(0, 5, line[:200])

        saida = Path(__file__).parent / "relatorio_auditoria.pdf"
        pdf.output(str(saida))
        return FileResponse(
            path=str(saida),
            filename="relatorio_auditoria.pdf",
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="relatorio_auditoria.pdf"'}
        )
    except Exception as e:
        return JSONResponse({"erro": f"Erro ao gerar PDF: {str(e)}"}, status_code=500)
