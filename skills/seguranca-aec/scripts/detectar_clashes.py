"""
detectar_clashes.py
-------------------------------------------------------------------
Detecta clashes (interferências) geométricas reais:

1. entre instalações (dutos, tubulações, eletrodutos, cabos) e
   elementos estruturais (vigas, pilares, lajes, paredes);
2. entre instalações de disciplinas diferentes entre si — ar
   condicionado x hidráulica, hidráulica x gás, elétrica x
   comunicação, e assim por diante — algo essencial em coordenação de
   projetos, já que duas tubulações de disciplinas distintas não podem
   ocupar o mesmo espaço físico.

A disciplina de cada elemento de instalação é lida do property set
customizado `Pset_SegurancaAEC.Disciplina` (ex.: "HVAC", "Hidraulica",
"Gas", "Eletrica", "Comunicacao"). Elementos da MESMA disciplina não
são comparados entre si, pois segmentos consecutivos de uma mesma
tubulação/duto normalmente compartilham conexões e não representam um
clash real.

Estratégia geométrica: para cada elemento, extrai a malha (vértices) já
em coordenadas absolutas do modelo (use-world-coords) e calcula sua
bounding box (AABB). Duas bounding boxes que se sobrepõem nos três
eixos indicam interferência candidata — a mesma técnica usada por
ferramentas de clash detection comerciais como primeira passada
(broad-phase), antes de uma verificação de sólido-a-sólido mais cara.

Uso via linha de comando:
    python detectar_clashes.py modelo.ifc
"""

import json
import sys
from itertools import combinations

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element

CLASSES_ESTRUTURA = ("IfcBeam", "IfcColumn", "IfcSlab", "IfcWall")
CLASSES_INSTALACOES = (
    "IfcDuctSegment", "IfcDuctFitting",
    "IfcPipeSegment", "IfcPipeFitting",
    "IfcCableSegment", "IfcCableCarrierSegment", "IfcCableCarrierFitting",
    "IfcFlowSegment", "IfcFlowFitting",
)


def _settings():
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    return settings


def _bounding_box(model, element, settings):
    """Retorna ((xmin,ymin,zmin), (xmax,ymax,zmax)) em metros, ou None
    se o elemento não tiver representação geométrica."""
    if not element.Representation:
        return None
    shape = ifcopenshell.geom.create_shape(settings, element)
    verts = shape.geometry.verts  # lista plana [x0,y0,z0,x1,y1,z1,...] em metros
    if not verts:
        return None
    xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _sobrepoe(caixa_a, caixa_b, folga_m=0.0):
    (ax0, ay0, az0), (ax1, ay1, az1) = caixa_a
    (bx0, by0, bz0), (bx1, by1, bz1) = caixa_b
    return (
        ax0 - folga_m <= bx1 and bx0 - folga_m <= ax1 and
        ay0 - folga_m <= by1 and by0 - folga_m <= ay1 and
        az0 - folga_m <= bz1 and bz0 - folga_m <= az1
    )


def _disciplina(element):
    return ifcopenshell.util.element.get_pset(element, name="Pset_SegurancaAEC", prop="Disciplina") or "Indefinida"


def detectar_clashes(caminho_ifc: str) -> list:
    model = ifcopenshell.open(caminho_ifc)
    settings = _settings()

    estrutura, instalacoes = {}, {}
    for ifc_class in CLASSES_ESTRUTURA:
        for el in model.by_type(ifc_class):
            if el.id() in estrutura:
                continue
            caixa = _bounding_box(model, el, settings)
            if caixa:
                estrutura[el.id()] = (el, caixa)
    for ifc_class in CLASSES_INSTALACOES:
        for el in model.by_type(ifc_class):
            if el.id() in instalacoes:
                continue
            caixa = _bounding_box(model, el, settings)
            if caixa:
                instalacoes[el.id()] = (el, caixa, _disciplina(el))

    clashes = []

    # 1) Instalações x Estrutura
    for el_estrutura, caixa_estrutura in estrutura.values():
        for el_instalacao, caixa_instalacao, disciplina in instalacoes.values():
            if _sobrepoe(caixa_estrutura, caixa_instalacao):
                clashes.append({
                    "tipo": "instalacao_x_estrutura",
                    "elemento_a": {"classe": el_estrutura.is_a(), "nome": el_estrutura.Name, "disciplina": "Estrutura"},
                    "elemento_b": {"classe": el_instalacao.is_a(), "nome": el_instalacao.Name, "disciplina": disciplina},
                })

    # 2) Instalação x Instalação, apenas entre disciplinas diferentes
    for (el_a, caixa_a, disc_a), (el_b, caixa_b, disc_b) in combinations(instalacoes.values(), 2):
        if disc_a == disc_b:
            continue  # segmentos da mesma disciplina/sistema nao sao considerados clash
        if _sobrepoe(caixa_a, caixa_b):
            clashes.append({
                "tipo": "instalacao_x_instalacao",
                "elemento_a": {"classe": el_a.is_a(), "nome": el_a.Name, "disciplina": disc_a},
                "elemento_b": {"classe": el_b.is_a(), "nome": el_b.Name, "disciplina": disc_b},
            })

    return clashes


def main():
    if len(sys.argv) != 2:
        print("Uso: python detectar_clashes.py <caminho_para_arquivo.ifc>")
        sys.exit(1)
    clashes = detectar_clashes(sys.argv[1])
    print(json.dumps(clashes, indent=2, ensure_ascii=False))
    print(f"\nTotal de clashes encontrados: {len(clashes)}")


if __name__ == "__main__":
    main()

