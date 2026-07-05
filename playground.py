# -*- coding: utf-8 -*-
import os, sys, json, webbrowser, threading, time, asyncio
from pathlib import Path

_BASE = Path(os.path.abspath(__file__)).parent

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(str(_BASE / "skills/seguranca-aec/scripts"))

from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

agente_global = None
ifc_paths = {"arch": None, "struct": None, "mep": None, "exemplo": None}

def ifc_ativo():
    for key in ["arch", "struct", "mep", "exemplo"]:
        p = ifc_paths.get(key)
        if p and Path(p).exists():
            return p
    return None

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home():
    html_path = _BASE / "interface.html"
    if not html_path.exists():
        return HTMLResponse("<h1>interface.html not found</h1>", status_code=500)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/api/status")
async def api_status():
    return JSONResponse({
        "agente_inicializado": agente_global is not None,
        "ifc_ativo": ifc_ativo(),
        "pasta_projeto": str(_BASE),
    })

@app.post("/api/upload-ifc")
async def upload_ifc(request: Request):
    import shutil
    form = await request.form()
    tipo = form.get("tipo", "exemplo")
    arquivo = form.get("file")
    if not arquivo:
        return JSONResponse({"erro": "Nenhum arquivo enviado."}, status_code=400)
    destino = _BASE / arquivo.filename
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    ifc_paths[tipo] = str(destino)
    return JSONResponse({"status": "ok", "tipo": tipo, "arquivo": arquivo.filename, "caminho": str(destino)})

@app.post("/api/setup")
async def api_setup(request: Request):
    global agente_global
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    usar_exemplo = data.get("usar_exemplo", False)

    if not api_key:
        return JSONResponse({"erro": "Chave nao informada."}, status_code=400)

    if usar_exemplo:
        exemplo = _BASE / "modelo_exemplo.ifc"
        if not exemplo.exists():
            return JSONResponse({"erro": "modelo_exemplo.ifc nao encontrado."}, status_code=400)
        ifc_paths["exemplo"] = str(exemplo)

    if not ifc_ativo():
        return JSONResponse({"erro": "Nenhum arquivo IFC carregado."}, status_code=400)

    os.environ["ANTHROPIC_API_KEY"] = api_key

    from agno.agent import Agent
    from agno.models.anthropic import Claude
    from agno.skills import Skills, LocalSkills

    agente_global = Agent(
        id="AgenteCoordenacaoSeguranca",
        name="Agente de Coordenacao e Seguranca AEC",
        model=Claude(id="claude-sonnet-4-6"),
        skills=Skills(loaders=[LocalSkills(str(_BASE / "skills"))]),
        tools=[detectar_clashes_fn, verificar_rota_fuga_fn, verificar_sistema_incendio_fn],
        instructions=[
            "Voce e um assistente tecnico de arquitetura especializado em compatibilizacao de projetos BIM e seguranca contra incendio.",
            "Use a skill 'seguranca-aec' como referencia normativa.",
            "SEMPRE chame as tools para obter dados reais do modelo IFC. Nunca invente valores.",
            "Para clashes, chame 'detectar_clashes_fn'.",
            "Para rota de fuga, chame 'verificar_rota_fuga_fn'.",
            "Para extintores e sprinklers, chame 'verificar_sistema_incendio_fn'.",
            "Na analise completa, chame as TRES tools em sequencia.",
            "Apresente resultados em portugues com tabelas markdown.",
        ],
        markdown=True,
        debug_mode=False,
    )

    env_path = _BASE / ".env"
    with open(env_path, "w") as f:
        f.write(f"ANTHROPIC_API_KEY={api_key}\n")

    return JSONResponse({"status": "ok", "ifc_ativo": ifc_ativo()})

@app.post("/api/stream-verificar")
async def stream_verificar(request: Request):
    if agente_global is None:
        return JSONResponse({"erro": "Agente nao inicializado."}, status_code=400)
    data = await request.json()
    tipo = data.get("tipo", "d")

    async def gerar():
        import anthropic
        resultados = {}
        try:
            yield f"data: {json.dumps({'tipo': 'inicio'})}\n\n"
            await asyncio.sleep(0.4)

            if tipo in ("a", "d"):
                yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': 'detectar_clashes_fn'})}\n\n"
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> import ifcopenshell, ifcopenshell.geom'})}\n\n"
                await asyncio.sleep(0.6)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> model = ifcopenshell.open(ifc_path)'})}\n\n"
                await asyncio.sleep(0.6)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> settings.set(use-world-coords, True)'})}\n\n"
                await asyncio.sleep(0.6)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> Extraindo geometria 3D de cada elemento...'})}\n\n"
                await asyncio.sleep(0.8)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> Calculando bounding boxes AABB...'})}\n\n"
                await asyncio.sleep(0.6)
                r = detectar_clashes_fn()
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> Comparando HVAC x Estrutura...'})}\n\n"
                await asyncio.sleep(0.4)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> Comparando Hidraulica x Estrutura...'})}\n\n"
                await asyncio.sleep(0.4)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> Comparando Eletrica x Estrutura...'})}\n\n"
                await asyncio.sleep(0.4)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'detectar_clashes_fn', 'linha': '>>> Verificando clashes entre disciplinas...'})}\n\n"
                await asyncio.sleep(0.5)
                resultados["clashes"] = r
                yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': 'detectar_clashes_fn', 'resultado': r})}\n\n"
                await asyncio.sleep(0.3)

            if tipo in ("b", "d"):
                yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': 'verificar_rota_fuga_fn'})}\n\n"
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_rota_fuga_fn', 'linha': '>>> portas = model.by_type(IfcDoor)'})}\n\n"
                await asyncio.sleep(0.6)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_rota_fuga_fn', 'linha': '>>> Filtrando PredefinedType = EMERGENCY...'})}\n\n"
                await asyncio.sleep(0.6)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_rota_fuga_fn', 'linha': '>>> matrix = util.placement.get_local_placement(door)'})}\n\n"
                await asyncio.sleep(0.6)
                r = verificar_rota_fuga_fn()
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_rota_fuga_fn', 'linha': '>>> Calculando distancia euclidiana em planta...'})}\n\n"
                await asyncio.sleep(0.5)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_rota_fuga_fn', 'linha': '>>> Comparando com limite NBR 9077 (30m)...'})}\n\n"
                await asyncio.sleep(0.5)
                resultados["rota_fuga"] = r
                yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': 'verificar_rota_fuga_fn', 'resultado': r})}\n\n"
                await asyncio.sleep(0.3)

            if tipo in ("c", "d"):
                yield f"data: {json.dumps({'tipo': 'tool_inicio', 'tool': 'verificar_sistema_incendio_fn'})}\n\n"
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_sistema_incendio_fn', 'linha': '>>> terminais = model.by_type(IfcFireSuppressionTerminal)'})}\n\n"
                await asyncio.sleep(0.6)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_sistema_incendio_fn', 'linha': '>>> Separando ObjectType=Extinguisher e Sprinkler...'})}\n\n"
                await asyncio.sleep(0.6)
                r = verificar_sistema_incendio_fn()
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_sistema_incendio_fn', 'linha': '>>> Calculando raio de cobertura extintores (NBR 12693)...'})}\n\n"
                await asyncio.sleep(0.5)
                yield f"data: {json.dumps({'tipo': 'progresso', 'tool': 'verificar_sistema_incendio_fn', 'linha': '>>> Calculando area por cabeca sprinkler (NBR 10897)...'})}\n\n"
                await asyncio.sleep(0.5)
                resultados["sistema_incendio"] = r
                yield f"data: {json.dumps({'tipo': 'tool_fim', 'tool': 'verificar_sistema_incendio_fn', 'resultado': r})}\n\n"
                await asyncio.sleep(0.3)

            yield f"data: {json.dumps({'tipo': 'formatando'})}\n\n"
            await asyncio.sleep(0.4)

            dados = "\n\n".join([f"{k}:\n{v}" for k, v in resultados.items()])
            prompt = f"""Com base nos dados reais do modelo IFC, elabore um relatorio tecnico profissional em portugues.

DADOS REAIS:
{dados}

Apresente em markdown com tabelas. Use os nomes exatos dos elementos. Inclua resumo executivo."""

            client = anthropic.Anthropic()
            with client.messages.stream(model="claude-sonnet-4-6", max_tokens=8192,
                                        messages=[{"role": "user", "content": prompt}]) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'tipo': 'conteudo', 'delta': text})}\n\n"
                    await asyncio.sleep(0.4)

            yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"
            await asyncio.sleep(0.4)

        except Exception as e:
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': str(e)})}\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={
                                 "Cache-Control": "no-cache, no-transform",
                                 "X-Accel-Buffering": "no",
                                 "Transfer-Encoding": "chunked"
                             })

@app.post("/api/chat")
async def api_chat(request: Request):
    if agente_global is None:
        return JSONResponse({"erro": "Agente nao inicializado."}, status_code=400)
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

@app.get("/api/viewer-data")
async def viewer_data():
    ifc = ifc_ativo()
    if not ifc:
        return JSONResponse({"erro": "Nenhum arquivo IFC carregado."}, status_code=400)
    try:
        import ifcopenshell.geom
        import ifcopenshell.util.unit as ifc_unit
        import ifcopenshell.util.placement as ifc_pl
        import math

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

        # Portas de entrada (>=0.80m) longe da escada ou sem corta-fogo
        try:
            model2 = ifcopenshell.open(ifc)
            escala2 = ifc_unit.calculate_unit_scale(model2)
            portas_entrada = []
            for door in model2.by_type("IfcDoor"):
                w = getattr(door, "OverallWidth", None)
                if w and float(w) * escala2 >= 0.80:
                    pos = ifc_pl.get_local_placement(door.ObjectPlacement)
                    x, y = pos[0,3]*escala2, pos[1,3]*escala2
                    ot = (getattr(door, "ObjectType", "") or "").lower()
                    nm = (door.Name or "").lower()
                    e_cf = any(k in ot+nm for k in ("corta","fire","emergency","cf"))
                    portas_entrada.append({"nome": door.Name, "x": x, "y": y, "e_cf": e_cf})

            pos_escadas = []
            for stair in model2.by_type("IfcStair"):
                pos = ifc_pl.get_local_placement(stair.ObjectPlacement)
                pos_escadas.append({"nome": stair.Name, "x": pos[0,3]*escala2, "y": pos[1,3]*escala2})

            if pos_escadas:
                for porta in portas_entrada:
                    menor_dist = min(math.hypot(porta["x"]-e["x"], porta["y"]-e["y"]) for e in pos_escadas)
                    if porta["e_cf"] or menor_dist > 30.0:
                        nc_nomes.add(porta["nome"])
            else:
                for porta in portas_entrada:
                    nc_nomes.add(porta["nome"])
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
                    cor, status = "#f59e0b", "NAO CONFORME"
                else:
                    cor, status = "#6b7280", "OK"
                elementos.append({
                    "nome": nome, "tipo": el.is_a(), "cor": cor, "status": status,
                    "bbox": {"xmin": min(xs), "xmax": max(xs), "ymin": min(ys),
                             "ymax": max(ys), "zmin": min(zs), "zmax": max(zs)}
                })
            except: continue

        if not elementos:
            return JSONResponse({"erro": "Nenhum elemento 3D encontrado."})
        return JSONResponse({"elementos": elementos, "total": len(elementos)})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)

relatorio_html_global = ""

@app.post("/api/salvar-relatorio")
async def salvar_relatorio(request: Request):
    global relatorio_html_global
    data = await request.json()
    relatorio_html_global = data.get("html", "")
    return JSONResponse({"status": "ok"})

@app.get("/api/download-pdf")
async def download_pdf():
    global relatorio_html_global
    if not relatorio_html_global:
        return JSONResponse({"erro": "Execute uma analise primeiro."}, status_code=400)
    try:
        from fpdf import FPDF
        import re, html as html_lib

        ifc_nome = Path(ifc_ativo() or "modelo").name if ifc_ativo() else "modelo"
        text = re.sub(r'<li[^>]*>', '- ', relatorio_html_global)
        text = re.sub(r'<h[1-3][^>]*>(.*?)</h[1-3]>', lambda m: '\n###'+m.group(1)+'###\n', text, flags=re.DOTALL)
        text = re.sub(r'<tr[^>]*>', '\n', text)
        text = re.sub(r'<t[dh][^>]*>(.*?)</t[dh]>', lambda m: m.group(1)+' | ', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_lib.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.encode('latin-1', errors='replace').decode('latin-1')
        ifc_safe = ifc_nome.encode('latin-1', errors='replace').decode('latin-1')

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_fill_color(26, 26, 26)
        pdf.rect(0, 0, 210, 28, 'F')
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(10, 8)
        pdf.cell(0, 8, 'Relatorio de Auditoria BIM - Coordenacao e Seguranca AEC', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(161, 161, 170)
        pdf.set_x(10)
        pdf.cell(0, 6, f'Arquivo: {ifc_safe}  |  Agno + Claude Sonnet 4.6 + ifcopenshell', new_x='LMARGIN', new_y='NEXT')
        pdf.set_y(35)

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                pdf.ln(3)
            elif '###' in line:
                clean = line.replace('###','').strip()
                if clean:
                    pdf.set_font('Helvetica', 'B', 12)
                    pdf.set_text_color(194, 65, 12)
                    pdf.ln(4)
                    pdf.cell(0, 7, clean[:90], new_x='LMARGIN', new_y='NEXT')
                    pdf.set_draw_color(249, 115, 22)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(2)
            elif ' | ' in line:
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 5, line[:200])
            else:
                pdf.set_font('Helvetica', '', 10)
                pdf.set_text_color(26, 26, 26)
                pdf.multi_cell(0, 5, line[:200])

        saida = _BASE / "relatorio_auditoria.pdf"
        pdf.output(str(saida))
        return FileResponse(path=str(saida), filename="relatorio_auditoria.pdf",
                           media_type="application/pdf",
                           headers={"Content-Disposition": 'attachment; filename="relatorio_auditoria.pdf"'})
    except Exception as e:
        return JSONResponse({"erro": f"Erro ao gerar PDF: {str(e)}"}, status_code=500)

@app.get("/api/download-ifc-auditado")
async def download_ifc_auditado():
    ifc = ifc_ativo()
    if not ifc or not Path(ifc).exists():
        return JSONResponse({"erro": "Arquivo IFC nao encontrado."}, status_code=400)
    try:
        from colorir_auditoria_ifc import colorir_auditoria
        nome_saida = Path(ifc).stem + "_auditado.ifc"
        saida_abs = _BASE / nome_saida
        colorir_auditoria(ifc, str(saida_abs))
        if not saida_abs.exists():
            return JSONResponse({"erro": "Falha ao gerar IFC auditado."}, status_code=500)
        return FileResponse(path=str(saida_abs), filename=nome_saida,
                           media_type="application/octet-stream",
                           headers={"Content-Disposition": f'attachment; filename="{nome_saida}"'})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)

@app.get("/api/download-json")
async def download_json():
    ifc = ifc_ativo()
    if not ifc:
        return JSONResponse({"erro": "Nenhum arquivo IFC carregado."}, status_code=400)
    try:
        import ifcopenshell
        import ifcopenshell.util.unit as ifc_unit
        import ifcopenshell.util.placement as ifc_pl
        import math

        model = ifcopenshell.open(ifc)
        escala = ifc_unit.calculate_unit_scale(model)

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

        elementos_problema = []
        for el in model.by_type("IfcProduct"):
            nome = el.Name or el.is_a()
            if nome in clash_nomes:
                elementos_problema.append({"nome": nome, "classe": el.is_a(), "cor": "vermelho", "status": "CLASH"})
            elif nome in nc_nomes:
                elementos_problema.append({"nome": nome, "classe": el.is_a(), "cor": "amarelo", "status": "NAO CONFORME"})

        output = json.dumps({"arquivo_ifc": Path(ifc).name, "total": len(elementos_problema),
                            "elementos": elementos_problema}, indent=2, ensure_ascii=False)
        saida = _BASE / "auditoria_dados.json"
        saida.write_text(output, encoding="utf-8")
        return FileResponse(path=str(saida), filename="auditoria_dados.json",
                           media_type="application/json",
                           headers={"Content-Disposition": 'attachment; filename="auditoria_dados.json"'})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)

@app.post("/api/trocar-ifc")
async def api_trocar_ifc(request: Request):
    global agente_global
    # Reset everything
    for k in ["arch", "struct", "mep", "exemplo"]:
        ifc_paths[k] = None
    agente_global = None
    data = await request.json()
    usar_exemplo = data.get("usar_exemplo", False)
    if usar_exemplo:
        ifc_paths["exemplo"] = str(_BASE / "modelo_exemplo.ifc")
    return JSONResponse({"status": "ok", "ifc_ativo": ifc_ativo()})

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def detectar_clashes_fn() -> str:
    """Detecta clashes geometricos reais entre instalacoes e estrutura."""
    ifc = ifc_ativo()
    if not ifc:
        return "Nenhum arquivo IFC carregado."
    try:
        clashes = detectar_clashes(ifc)
        if not clashes:
            return f"Arquivo: {Path(ifc).name}\nNenhum clash encontrado no modelo."
        linhas = []
        for c in clashes:
            a, b = c["elemento_a"], c["elemento_b"]
            rotulo = "ESTRUTURA x INSTALACAO" if c["tipo"] == "instalacao_x_estrutura" else "INSTALACAO x INSTALACAO"
            linhas.append(f"[{rotulo}] {a['disciplina']} '{a['nome']}' x {b['disciplina']} '{b['nome']}'")
        return f"Arquivo: {Path(ifc).name}\n{len(clashes)} clash(es):\n" + "\n".join(linhas)
    except Exception as e:
        return f"Erro: {str(e)}"

def verificar_rota_fuga_fn() -> str:
    """Verifica distancia entre portas de apartamento e porta corta-fogo (NBR 9077)."""
    ifc = ifc_ativo()
    if not ifc:
        return "Nenhum arquivo IFC carregado."
    try:
        resultados = verificar_rota_fuga(ifc)
        if resultados and "erro" in resultados[0]:
            return f"Arquivo: {Path(ifc).name}\n{resultados[0]['erro']}"
        linhas = [
            f"[{'CONFORME' if r['conforme'] else 'NAO CONFORME'}] {r['porta_apartamento']} -> {r['porta_escada_mais_proxima']}: {r['distancia_m']} m (limite: {r['limite_m']} m)"
            for r in resultados
        ]
        return f"Arquivo: {Path(ifc).name}\n" + "\n".join(linhas)
    except Exception as e:
        return f"Erro: {str(e)}"

def verificar_sistema_incendio_fn() -> str:
    """Verifica extintores (NBR 12693) e sprinklers (NBR 10897)."""
    ifc = ifc_ativo()
    if not ifc:
        return "Nenhum arquivo IFC carregado."
    try:
        resultados = verificar_sistema_incendio(ifc)
        if resultados and "erro" in resultados[0]:
            return f"Arquivo: {Path(ifc).name}\n{resultados[0]['erro']}"
        linhas = [f"[{r.get('categoria','')}] [{'CONFORME' if r.get('conforme') else 'NAO CONFORME'}] {r.get('motivo','')}"
                  for r in resultados]
        return f"Arquivo: {Path(ifc).name}\n" + "\n".join(linhas)
    except Exception as e:
        return f"Erro: {str(e)}"

# ---------------------------------------------------------------------------
# Execucao
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    def abrir_navegador():
        time.sleep(2)
        webbrowser.open("http://localhost:7777")

    print("\n" + "=" * 55)
    print("  AGENTE DE COORDENACAO E SEGURANCA AEC")
    print("  Agno + Claude (Anthropic) + ifcopenshell")
    print("=" * 55)
    print("\n  Acesse: http://localhost:7777\n")

    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="localhost", port=7777)
