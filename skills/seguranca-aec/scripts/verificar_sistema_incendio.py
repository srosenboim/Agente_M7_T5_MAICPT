"""
verificar_sistema_incendio.py
-------------------------------------------------------------------
Verifica o sistema de proteção contra incêndio usando classes IFC nativas:

EXTINTORES (IfcFireSuppressionTerminal, ObjectType contendo "extinguisher"/"extintor"):
  Calcula distância de cada extintor até as portas do pavimento.
  Critério: nenhuma porta deve estar a mais de 20 m de um extintor (NBR 12693).

SPRINKLERS (IfcFireSuppressionTerminal, ObjectType contendo "sprinkler"):
  Verifica existência e densidade de cobertura:
  - Conta o número de sprinklers no pavimento
  - Estima a área do pavimento pelo bounding box dos elementos
  - Calcula área coberta por cabeça sprinkler
  - Compara com NBR 10897: máximo de 12 m² por cabeça (risco leve)
    ou 9 m² por cabeça (risco ordinário)

Esta abordagem reflete a prática real de inspeção predial e coordenação
BIM: sprinklers são verificados por cobertura de área, não por distância
até uma porta específica.
"""

import json
import math
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.unit

RAIO_EXTINTOR_M = 20.0
AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2 = 12.0
AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2 = 9.0


def _tipo_terminal(element):
    ot = (getattr(element, "ObjectType", "") or "").lower()
    nm = (element.Name or "").lower()
    if "sprinkler" in ot or "sprinkler" in nm:
        return "sprinkler"
    return "extintor"


def _pos_metros(element, escala):
    m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
    return m[0, 3] * escala, m[1, 3] * escala


def _dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _area_pavimento_m2(model, escala):
    """Estima a área do pavimento pelo bounding box de todos os elementos
    com geometria 3D. Usado quando não há IfcSpace definido no modelo."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    xs, ys = [], []
    for el in model.by_type("IfcProduct"):
        if not el.Representation:
            continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, el)
            v = shape.geometry.verts
            xs.extend(v[0::3])
            ys.extend(v[1::3])
        except:
            continue
    if not xs:
        return None
    # Converte de unidades do modelo para metros via escala
    dx = (max(xs) - min(xs))
    dy = (max(ys) - min(ys))
    return round(dx * dy, 1)


def verificar_sistema_incendio(caminho_ifc: str) -> list:
    model = ifcopenshell.open(caminho_ifc)
    escala = ifcopenshell.util.unit.calculate_unit_scale(model)

    terminais = model.by_type("IfcFireSuppressionTerminal")
    extintores = [(t, _pos_metros(t, escala)) for t in terminais if _tipo_terminal(t) == "extintor"]
    sprinklers = [t for t in terminais if _tipo_terminal(t) == "sprinkler"]
    portas = [(d, _pos_metros(d, escala)) for d in model.by_type("IfcDoor")]

    resultados = []

    # --- EXTINTORES: verificação por distância até portas ---
    resultados.append({
        "categoria": "Resumo",
        "extintores_encontrados": len(extintores),
        "sprinklers_encontrados": len(sprinklers),
        "conforme": True,
        "motivo": f"{len(extintores)} extintor(es) e {len(sprinklers)} sprinkler(s) encontrados no modelo.",
    })

    if not extintores:
        resultados.append({
            "categoria": "Extintores",
            "conforme": False,
            "motivo": "Nenhum extintor (IfcFireSuppressionTerminal com ObjectType 'Extinguisher') encontrado.",
        })
    else:
        for porta, pos_porta in portas:
            mais_proximo, menor_dist = None, float("inf")
            for ext, pos_ext in extintores:
                d = _dist(pos_porta, pos_ext)
                if d < menor_dist:
                    menor_dist, mais_proximo = d, ext
            conforme = menor_dist <= RAIO_EXTINTOR_M
            resultados.append({
                "categoria": "Extintor",
                "porta": porta.Name,
                "extintor_mais_proximo": mais_proximo.Name,
                "distancia_m": round(menor_dist, 2),
                "raio_m": RAIO_EXTINTOR_M,
                "conforme": conforme,
                "motivo": (
                    f"Extintor mais próximo de '{porta.Name}' está a {menor_dist:.1f} m — "
                    f"{'dentro do' if conforme else 'FORA do'} raio de {RAIO_EXTINTOR_M:.0f} m (NBR 12693)."
                ),
            })

    # --- SPRINKLERS: verificação por cobertura de área ---
    if not sprinklers:
        resultados.append({
            "categoria": "Sprinklers",
            "conforme": False,
            "motivo": "Nenhum sprinkler (IfcFireSuppressionTerminal com ObjectType 'Sprinkler') encontrado no modelo. "
                      "Verificar se o sistema de chuveiros automáticos foi modelado no IFC.",
        })
    else:
        area_m2 = _area_pavimento_m2(model, escala)

        if area_m2 is None or area_m2 <= 0:
            resultados.append({
                "categoria": "Sprinklers",
                "quantidade": len(sprinklers),
                "conforme": None,
                "motivo": f"{len(sprinklers)} sprinkler(s) encontrado(s). "
                          "Não foi possível calcular a área do pavimento automaticamente — "
                          "adicione IfcSpace ao modelo para verificação precisa de cobertura.",
            })
        else:
            area_por_cabeca = round(area_m2 / len(sprinklers), 1)
            conforme_leve = area_por_cabeca <= AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2
            conforme_ordinario = area_por_cabeca <= AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2

            resultados.append({
                "categoria": "Sprinklers",
                "quantidade": len(sprinklers),
                "area_pavimento_m2": area_m2,
                "area_por_cabeca_m2": area_por_cabeca,
                "limite_risco_leve_m2": AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2,
                "limite_risco_ordinario_m2": AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2,
                "conforme_risco_leve": conforme_leve,
                "conforme_risco_ordinario": conforme_ordinario,
                "conforme": conforme_leve,
                "nomes_sprinklers": [s.Name for s in sprinklers],
                "motivo": (
                    f"{len(sprinklers)} sprinkler(s) para área estimada de {area_m2} m². "
                    f"Área por cabeça: {area_por_cabeca} m²/cabeça. "
                    f"Risco leve (≤ {AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2} m²/cabeça): "
                    f"{'✅ CONFORME' if conforme_leve else '❌ NÃO CONFORME'}. "
                    f"Risco ordinário (≤ {AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2} m²/cabeça): "
                    f"{'✅ CONFORME' if conforme_ordinario else '❌ NÃO CONFORME'} (NBR 10897)."
                ),
            })

    return resultados


def main():
    if len(sys.argv) != 2:
        print("Uso: python verificar_sistema_incendio.py <arquivo.ifc>")
        sys.exit(1)
    print(json.dumps(verificar_sistema_incendio(sys.argv[1]), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
