"""
colorir_auditoria_ifc.py
-------------------------------------------------------------------
Gera uma cópia do IFC com elementos coloridos por resultado:
  - Clash (interferência geométrica)  → AMARELO
  - Não conforme (rota de fuga, extintor, sprinkler fora do raio) → VERMELHO
  - Conforme → cor original mantida (sem material atribuído)

CORREÇÃO: elementos agora são localizados por GlobalId (model.by_guid),
não mais por Name. Nomes duplicados são comuns em modelos reais
(ex.: "Porta 01" repetida em vários pavimentos) e a busca por nome
pintava TODAS as instâncias com aquele nome, mesmo as que não tinham
clash/não-conformidade nenhuma. Os scripts de verificação já devolvem
"global_id" em cada resultado — usamos isso diretamente.

Usa ifcopenshell.api.style e ifcopenshell.api.material nativos,
exatamente como ensinado na Aula 02 da disciplina.
"""

import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.style
import ifcopenshell.util.representation

sys.path.append(str(Path(__file__).parent))
from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio


def _criar_material_cor(model, body_context, nome, r, g, b):
    material = ifcopenshell.api.material.add_material(model, name=nome)
    style = ifcopenshell.api.style.add_style(model, name=nome)
    ifcopenshell.api.style.add_surface_style(
        model, style=style, ifc_class="IfcSurfaceStyleShading",
        attributes={
            "SurfaceColour": {"Name": None, "Red": r, "Green": g, "Blue": b},
            "Transparency": 0.0,
        },
    )
    if body_context:
        ifcopenshell.api.style.assign_material_style(
            model, material=material, style=style, context=body_context
        )
    return material


def _por_guid(model, global_id):
    """Busca um elemento por GlobalId, sem ambiguidade de nome.
    Retorna None se o GlobalId não existir mais no modelo (não deveria
    acontecer, já que é o mesmo arquivo, mas não quebra se acontecer)."""
    if not global_id:
        return None
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def colorir_auditoria(caminho_ifc_entrada: str, caminho_ifc_saida: str) -> dict:
    model = ifcopenshell.open(caminho_ifc_entrada)

    body_context = ifcopenshell.util.representation.get_context(
        model, context="Model", subcontext="Body"
    )

    # Criar materiais
    mat_vermelho = _criar_material_cor(model, body_context, "Auditoria_NaoConforme", 0.9, 0.0, 0.0)
    mat_amarelo = _criar_material_cor(model, body_context, "Auditoria_Clash", 1.0, 0.8, 0.0)

    elementos_clash = set()
    elementos_nao_conformes = set()

    # --- Clashes (amarelo) — localizados por GlobalId ---
    try:
        clashes = detectar_clashes(caminho_ifc_entrada)
        for c in clashes:
            for lado in ("elemento_a", "elemento_b"):
                el = _por_guid(model, c[lado].get("global_id"))
                if el:
                    elementos_clash.add(el.id())
    except Exception:
        pass

    # --- Rota de fuga (vermelho nos não conformes) — por GlobalId ---
    try:
        resultados_fuga = verificar_rota_fuga(caminho_ifc_entrada)
        for r in resultados_fuga:
            if not r.get("conforme") and r.get("global_id"):
                el = _por_guid(model, r["global_id"])
                if el:
                    elementos_nao_conformes.add(el.id())
    except Exception:
        pass

    # --- Sistema de incêndio (vermelho nos não conformes) — por GlobalId ---
    try:
        resultados_incendio = verificar_sistema_incendio(caminho_ifc_entrada)
        for r in resultados_incendio:
            if not r.get("conforme"):
                guid = r.get("porta_global_id") or r.get("global_id")
                if guid:
                    el = _por_guid(model, guid)
                    if el:
                        elementos_nao_conformes.add(el.id())
    except Exception:
        pass

    # Aplicar cores — clash tem prioridade sobre não conforme
    contagem = {"clash": 0, "nao_conforme": 0, "original": 0}

    todos_elementos = list(model.by_type("IfcProduct"))
    for el in todos_elementos:
        tem_geo = bool(el.Representation)
        if el.id() in elementos_clash:
            if tem_geo:
                ifcopenshell.api.material.assign_material(model, products=[el], material=mat_amarelo)
            pset = ifcopenshell.api.pset.add_pset(model, product=el, name="Pset_Auditoria")
            ifcopenshell.api.pset.edit_pset(model, pset=pset, properties={"Status": "CLASH", "Cor": "Amarelo"})
            contagem["clash"] += 1
        elif el.id() in elementos_nao_conformes:
            if tem_geo:
                ifcopenshell.api.material.assign_material(model, products=[el], material=mat_vermelho)
            pset = ifcopenshell.api.pset.add_pset(model, product=el, name="Pset_Auditoria")
            ifcopenshell.api.pset.edit_pset(model, pset=pset, properties={"Status": "NAO_CONFORME", "Cor": "Vermelho"})
            contagem["nao_conforme"] += 1
        else:
            if tem_geo:
                contagem["original"] += 1

    model.write(caminho_ifc_saida)
    return contagem
