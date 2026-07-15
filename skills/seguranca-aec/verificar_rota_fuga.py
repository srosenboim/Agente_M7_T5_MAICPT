"""
verificar_rota_fuga.py
-------------------------------------------------------------------
Verifica rota de fuga (distância porta de apartamento → porta corta-fogo
da escada mais próxima, NO MESMO PAVIMENTO).

Identifica o TIPO de cada porta em camadas, da mais confiável para a
mais fraca:

    1) Padrão OFICIAL do schema IFC — Pset_DoorCommon.FireExit /
       Pset_DoorCommon.FireRating (property set padronizado pelo
       buildingSMART, não é algo customizado deste projeto) e, quando
       válido, o PredefinedType nativo. NOTA: "EMERGENCY"/"FIRE" NÃO são
       valores válidos de PredefinedType para IfcDoor no IFC4 — o enum
       IfcDoorTypeEnum só aceita DOOR/GATE/TRAPDOOR/USERDEFINED/
       NOTDEFINED. Por isso o sinal nativo real e confiável é o Pset
       oficial Pset_DoorCommon, não o PredefinedType.
    2) Pset customizado do projeto Pset_RoteiroFuga.Tipo (explicitamente
       definido por quem modelou/auditou este projeto especificamente)
    3) Nome do elemento + Material do Pset (fallback textual — cobre
       nomenclatura técnica como "P-60", "P-90", "P-120", e também
       Revit/ArchiCAD que só preenchem ObjectType/Name)
    4) IA — quando nenhuma camada acima resolve, a porta é reportada
       como "indefinido" para revisão humana ou do agente de IA, e NÃO
       é silenciosamente descartada nem classificada por adivinhação.

Também usa (quando presentes) os atributos de dimensionamento:
    - Porta de apartamento: 80 cm padrão / 90 cm cobertura (penthouse)
    - Porta corta-fogo: mínimo de 90 cm (P-60/P-90/P-120)
Essas larguras são informativas (não redefinem o tipo sozinhas — ver
_identificar_porta), e ficam nos resultados para auditoria.

IMPORTANTE: a distância calculada é uma distância em linha reta entre
as posições de inserção das portas, NÃO a distância real percorrida
pela rota de fuga (corredores, desvios). Trate o resultado como uma
aproximação para triagem, não como o valor oficial de conformidade —
a rota real deve ser conferida em planta com o caminho de circulação.

Limite: 30 m (NBR 9077) — ajustável em LIMITE_DISTANCIA_FUGA_M.
"""
import json
import math
import sys

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit

LIMITE_DISTANCIA_FUGA_M = 30.0

TERMOS_CORTA_FOGO = (
    "corta-fogo", "corta fogo", "cortafogo", "p-60", "p-90", "p-120",
    "p60", "p90", "p120", "escada incendio", "escada de incendio",
    "emergencia", "fire door",
)
TERMOS_APARTAMENTO = ("apartamento", "apto", "unidade")
VALORES_FIRE_RATING_VAZIOS = ("", "0", "none", "nenhum", "n/a", "na")


def _identificar_porta(door):
    """Classifica a porta como 'corta_fogo' ou 'apartamento' em camadas.
    Retorna um dict com tipo, camada usada, e um motivo legível para
    auditoria. Nunca inventa um tipo quando não há sinal suficiente —
    nesse caso retorna tipo='indefinido' (camada 'ia')."""

    pset_common = ifcopenshell.util.element.get_pset(door, "Pset_DoorCommon") or {}
    pset_custom = ifcopenshell.util.element.get_pset(door, "Pset_RoteiroFuga") or {}
    tipo_custom = str(pset_custom.get("Tipo") or "").strip().lower().replace("-", "_")
    material_pset = str(pset_custom.get("Material") or "").strip().lower()

    pt = str(getattr(door, "PredefinedType", "") or "").upper()
    nome = (door.Name or "").lower()

    fire_exit = pset_common.get("FireExit")
    fire_rating = str(pset_common.get("FireRating") or "").strip().lower()

    # Camada 1: padrão OFICIAL do schema IFC (Pset_DoorCommon é definido
    # pelo buildingSMART, não é uma invenção deste projeto). É checado
    # ANTES do pset customizado porque reflete o vocabulário padrão que
    # qualquer IFC real (Revit/ArchiCAD/Bonsai) pode preencher, mesmo sem
    # conhecer este projeto específico.
    if pt in ("EMERGENCY", "FIRE", "FIRERESISTANT"):  # defensivo; fora do
        # enum padrão IFC4 (não deveria ocorrer num IFC válido), mas não
        # custa checar caso um software escreva um valor não-padrão.
        return {"tipo": "corta_fogo", "camada": "nativo", "confianca": "alta",
                "motivo": f"PredefinedType = {pt} (fora do enum padrão IFC4)"}
    if fire_exit is True:
        return {"tipo": "corta_fogo", "camada": "pset_padrao_ifc", "confianca": "alta",
                "motivo": "Pset_DoorCommon.FireExit = True (property set oficial buildingSMART)"}
    if fire_rating and fire_rating not in VALORES_FIRE_RATING_VAZIOS:
        return {"tipo": "corta_fogo", "camada": "pset_padrao_ifc", "confianca": "alta",
                "motivo": f"Pset_DoorCommon.FireRating = '{pset_common.get('FireRating')}' "
                          f"(property set oficial buildingSMART)"}

    # Camada 2: Pset customizado deste projeto — explícito, mas específico
    # deste modelo/skill, não um padrão universal do IFC.
    if tipo_custom in ("corta_fogo",):
        return {"tipo": "corta_fogo", "camada": "pset_customizado", "confianca": "alta",
                "motivo": "Pset_RoteiroFuga.Tipo = Corta_Fogo"}
    if tipo_custom == "apartamento":
        return {"tipo": "apartamento", "camada": "pset_customizado", "confianca": "alta",
                "motivo": "Pset_RoteiroFuga.Tipo = Apartamento"}

    # Camada 3: nome do elemento + material (fallback textual)
    if any(t in nome for t in TERMOS_CORTA_FOGO) or material_pset == "metal":
        return {"tipo": "corta_fogo", "camada": "nome_ou_material", "confianca": "media",
                "motivo": "Nome ou Pset_RoteiroFuga.Material='Metal' indicam porta corta-fogo"}
    if pt == "DOOR" or any(t in nome for t in TERMOS_APARTAMENTO) or material_pset == "madeira":
        return {"tipo": "apartamento", "camada": "nativo_ou_nome", "confianca": "media",
                "motivo": "PredefinedType=DOOR, nome ou material='Madeira' indicam porta de apartamento"}

    # Camada 4: nenhuma camada determinística resolveu
    return {"tipo": "indefinido", "camada": "ia", "confianca": "baixa",
            "motivo": "Nenhuma camada (pset/nativo/nome) permitiu classificar esta porta; "
                      "recomenda-se revisão manual ou assistida por IA."}


def _variante_apartamento(door):
    """Classifica largura de porta de apartamento como padrão (80cm) ou
    cobertura/penthouse (90cm), apenas informativo."""
    largura = getattr(door, "OverallWidth", None)
    if largura is None:
        return None
    if largura >= 890:
        return "cobertura_90cm"
    if largura >= 780:
        return "padrao_80cm"
    return "largura_atipica"


def _pos_metros(element, escala):
    m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
    x, y = m[0, 3], m[1, 3]
    return x * escala, y * escala


def _dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _pavimento(element):
    container = ifcopenshell.util.element.get_container(element)
    if container is None:
        return None, "Sem_Pavimento"
    return container.id(), (container.Name or f"Pavimento_{container.id()}")


def verificar_rota_fuga(caminho_ifc: str) -> list:
    model = ifcopenshell.open(caminho_ifc)
    escala = ifcopenshell.util.unit.calculate_unit_scale(model)

    portas_classificadas = []
    for door in model.by_type("IfcDoor"):
        info = _identificar_porta(door)
        pav_id, pav_nome = _pavimento(door)
        portas_classificadas.append({
            "elemento": door,
            "info": info,
            "pavimento_id": pav_id,
            "pavimento_nome": pav_nome,
            "variante_largura": _variante_apartamento(door) if info["tipo"] == "apartamento" else None,
        })

    corta_fogo = [p for p in portas_classificadas if p["info"]["tipo"] == "corta_fogo"]
    apartamento = [p for p in portas_classificadas if p["info"]["tipo"] == "apartamento"]
    indefinidas = [p for p in portas_classificadas if p["info"]["tipo"] == "indefinido"]

    # IMPORTANTE: as checagens de erro ficam ANTES de qualquer outra coisa e
    # retornam uma lista de UM item só, no mesmo formato do script original
    # ({"erro": "..."} como resultados[0]). O playground.py consome esta
    # função através de um wrapper que faz `resultados[0]["erro"]` e depois
    # acessa `r['porta_apartamento']`, `r['distancia_m']` etc. SEM .get() —
    # ou seja, ele quebra (KeyError) se qualquer item da lista não tiver
    # exatamente essas chaves. Isso não é cosmético: com o IFC de exemplo
    # real do curso (portas sem PredefinedType/Pset, nomeadas genericamente
    # "Door"), todas as portas caem em "indefinido" e este caminho é
    # acionado. Por isso todo item abaixo carrega o conjunto completo de
    # chaves, mesmo quando o valor é None/placeholder.
    if not corta_fogo:
        return [{"erro": "Nenhuma porta corta-fogo de escada de incêndio encontrada. "
                          "Verifique Pset_RoteiroFuga.Tipo, PredefinedType='EMERGENCY' "
                          "ou o nome da porta."}]
    if not apartamento:
        return [{"erro": "Nenhuma porta de apartamento encontrada no modelo."}]

    resultados = []

    for p in indefinidas:
        resultados.append({
            "categoria": "Porta_Nao_Classificada",
            "porta_apartamento": p["elemento"].Name,
            "porta_escada_mais_proxima": "N/D",
            "global_id": p["elemento"].GlobalId,
            "pavimento": p["pavimento_nome"],
            "distancia_m": None,
            "limite_m": LIMITE_DISTANCIA_FUGA_M,
            "conforme": None,
            "motivo": p["info"]["motivo"],
        })

    # Agrupa por pavimento: só compara apartamento e corta-fogo do MESMO
    # pavimento. Uma rota de fuga não atravessa pavimentos (exceto pela
    # própria escada), então comparar entre andares gera falso-positivo.
    for apto in apartamento:
        pos_apto = _pos_metros(apto["elemento"], escala)
        candidatas = [cf for cf in corta_fogo if cf["pavimento_id"] == apto["pavimento_id"]]

        if not candidatas:
            resultados.append({
                "porta_apartamento": apto["elemento"].Name,
                "porta_escada_mais_proxima": "N/D",
                "global_id": apto["elemento"].GlobalId,
                "pavimento": apto["pavimento_nome"],
                "distancia_m": None,
                "limite_m": LIMITE_DISTANCIA_FUGA_M,
                "conforme": False,
                "motivo": f"Nenhuma porta corta-fogo encontrada no mesmo pavimento "
                          f"('{apto['pavimento_nome']}'). Verifique se a escada de incêndio "
                          f"deste pavimento foi modelada/classificada corretamente.",
            })
            continue

        mais_proxima, menor_dist = None, float("inf")
        for cf in candidatas:
            d = _dist(pos_apto, _pos_metros(cf["elemento"], escala))
            if d < menor_dist:
                menor_dist, mais_proxima = d, cf

        conforme = menor_dist <= LIMITE_DISTANCIA_FUGA_M
        resultados.append({
            "porta_apartamento": apto["elemento"].Name,
            "global_id": apto["elemento"].GlobalId,
            "pavimento": apto["pavimento_nome"],
            "variante_porta": apto["variante_largura"],
            "camada_identificacao": apto["info"]["camada"],
            "porta_escada_mais_proxima": mais_proxima["elemento"].Name,
            "distancia_m": round(menor_dist, 2),
            "limite_m": LIMITE_DISTANCIA_FUGA_M,
            "conforme": conforme,
            "motivo": (
                f"Distância em linha reta {menor_dist:.1f} m (mesmo pavimento: "
                f"'{apto['pavimento_nome']}') {'dentro do' if conforme else 'EXCEDE o'} "
                f"limite de {LIMITE_DISTANCIA_FUGA_M:.0f} m (NBR 9077). "
                f"Esta é uma aproximação em linha reta — confirme a distância real "
                f"percorrida pelo corredor em planta."
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
