"""
verificar_rota_fuga.py
-------------------------------------------------------------------
Verifica rota de fuga usando APENAS parâmetros nativos do IFC.

Identifica portas corta-fogo da escada de incêndio por:
1. PredefinedType == "EMERGENCY" (padrão IFC4)
2. ObjectType contendo "corta" ou "emergency" ou "fire" (Revit/ArchiCAD)
3. Name contendo "corta" ou "escada" ou "emergencia" (fallback)

Portas normais de apartamento: qualquer IfcDoor que não seja corta-fogo.

Limite: 30 m (NBR 9077) — ajustável em LIMITE_DISTANCIA_FUGA_M.
"""

import json
import math
import sys

import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.unit

LIMITE_DISTANCIA_FUGA_M = 30.0


def _e_porta_corta_fogo(door):
    """Identifica porta corta-fogo por atributos nativos do IFC."""
    # 1. PredefinedType nativo IFC4
    pt = getattr(door, "PredefinedType", None)
    if pt and str(pt).upper() in ("EMERGENCY", "FIRE", "FIRERESISTANT"):
        return True
    # 2. ObjectType (campo livre preenchido no Revit/ArchiCAD)
    ot = getattr(door, "ObjectType", None) or ""
    if any(k in ot.lower() for k in ("corta", "emergency", "fire", "cf ", "escada")):
        return True
    # 3. Name como último recurso
    nm = door.Name or ""
    if any(k in nm.lower() for k in ("corta", "emergencia", "escada incendio", "fire", "cf")):
        return True
    return False


def _pos_metros(element, escala):
    m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
    x, y = m[0, 3], m[1, 3]
    return x * escala, y * escala


def _dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def verificar_rota_fuga(caminho_ifc: str) -> list:
    model = ifcopenshell.open(caminho_ifc)
    escala = ifcopenshell.util.unit.calculate_unit_scale(model)

    corta_fogo = [d for d in model.by_type("IfcDoor") if _e_porta_corta_fogo(d)]
    apartamento = [d for d in model.by_type("IfcDoor") if not _e_porta_corta_fogo(d)]

    if not corta_fogo:
        return [{"erro": "Nenhuma porta corta-fogo de escada de incêndio encontrada. "
                         "Verifique se o PredefinedType='EMERGENCY' ou ObjectType contém 'corta'/'fire'."}]
    if not apartamento:
        return [{"erro": "Nenhuma porta de apartamento encontrada no modelo."}]

    resultados = []
    for apto in apartamento:
        pos_apto = _pos_metros(apto, escala)
        mais_proxima, menor_dist = None, float("inf")
        for cf in corta_fogo:
            d = _dist(pos_apto, _pos_metros(cf, escala))
            if d < menor_dist:
                menor_dist, mais_proxima = d, cf
        conforme = menor_dist <= LIMITE_DISTANCIA_FUGA_M
        resultados.append({
            "porta_apartamento": apto.Name,
            "porta_escada_mais_proxima": mais_proxima.Name,
            "distancia_m": round(menor_dist, 2),
            "limite_m": LIMITE_DISTANCIA_FUGA_M,
            "conforme": conforme,
            "motivo": (
                f"Distância {menor_dist:.1f} m {'dentro do' if conforme else 'EXCEDE o'} "
                f"limite de {LIMITE_DISTANCIA_FUGA_M:.0f} m (NBR 9077)."
            ),
        })
    return resultados


def main():
    if len(sys.argv) != 2:
        print("Uso: python verificar_rota_fuga.py <arquivo.ifc>")
        sys.exit(1)
    print(json.dumps(verificar_rota_fuga(sys.argv[1]), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
