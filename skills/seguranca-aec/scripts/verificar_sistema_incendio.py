"""
verificar_sistema_incendio.py
-------------------------------------------------------------------
Verifica o sistema de proteção contra incêndio, agrupado POR PAVIMENTO:

EXTINTORES:
  Calcula distância de cada porta até o extintor mais próximo NO MESMO
  PAVIMENTO. Critério: nenhuma porta deve estar a mais de 20 m de um
  extintor (NBR 12693).

SPRINKLERS:
  Por pavimento: conta sprinklers, estima a área do pavimento e calcula
  a densidade de cobertura (m² por cabeça), comparando com a NBR 10897
  (12 m²/cabeça risco leve, 9 m²/cabeça risco ordinário).

Identificação dos terminais de incêndio em CAMADAS (da mais confiável
para a mais fraca), cobrindo os 3 cenários mais comuns em projetos
reais — nem todo extintor é modelado com a classe IFC "certa":

    1) Classe nativa IfcFireSuppressionTerminal + ObjectType nativo
       ("Extinguisher"/"Sprinkler") — cenário ideal, ex.: biblioteca
       BIM bem configurada.
    2) Pset customizado Pset_SegurancaIncendio.Tipo — cobre elementos
       modelados como IfcBuildingElementProxy (comum quando a família
       do fabricante não usa a classe IFC correta).
    3) Nome do elemento — inclui marcas de fabricante conhecidas
       (Ansul, Kidde, Amerex) como último fallback textual.
    4) IA — terminais de classe correta (IfcFireSuppressionTerminal)
       mas sem ObjectType/Pset/nome conclusivos ficam marcados como
       "indefinido" para revisão, em vez de serem descartados ou
       adivinhados.

Elementos de classe genérica (IfcBuildingElementProxy) só entram na
análise se tiverem ALGUM sinal (Pset ou nome) de que são equipamento de
incêndio — do contrário qualquer proxy do modelo (mobiliário, outros
equipamentos) viraria ruído no relatório.
"""

import json
import math
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit

RAIO_EXTINTOR_M = 20.0
AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2 = 12.0
AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2 = 9.0

CLASSES_CANDIDATAS = ("IfcFireSuppressionTerminal", "IfcBuildingElementProxy")
FABRICANTES_EXTINTOR = ("ansul", "kidde", "amerex", "extintor", "extinguisher")
TERMOS_SPRINKLER = ("sprinkler", "chuveiro automatico")


def _identificar_terminal_incendio(el):
    """Classifica um elemento candidato como 'extintor', 'sprinkler',
    'detector' ou None (não é um terminal de incêndio reconhecível).
    Retorna dict {tipo, camada, confianca, motivo} ou None."""

    pset = ifcopenshell.util.element.get_pset(el, "Pset_SegurancaIncendio") or {}
    tipo_pset = str(pset.get("Tipo") or "").strip().lower()
    object_type = (getattr(el, "ObjectType", "") or "").lower()
    nome = (el.Name or "").lower()

    e_classe_nativa = el.is_a("IfcFireSuppressionTerminal")

    # Camada 1: classe nativa correta + ObjectType nativo
    if e_classe_nativa:
        if "extinguisher" in object_type or "extintor" in object_type:
            return {"tipo": "extintor", "camada": "nativo", "confianca": "alta",
                    "motivo": f"IfcFireSuppressionTerminal com ObjectType='{el.ObjectType}'"}
        if "sprinkler" in object_type:
            return {"tipo": "sprinkler", "camada": "nativo", "confianca": "alta",
                    "motivo": f"IfcFireSuppressionTerminal com ObjectType='{el.ObjectType}'"}
        if "detect" in object_type:
            return {"tipo": "detector", "camada": "nativo", "confianca": "alta",
                    "motivo": f"IfcFireSuppressionTerminal com ObjectType='{el.ObjectType}'"}

    # Camada 2: Pset customizado
    if tipo_pset == "extintor":
        return {"tipo": "extintor", "camada": "pset", "confianca": "alta",
                "motivo": "Pset_SegurancaIncendio.Tipo = Extintor"}
    if tipo_pset == "sprinkler":
        return {"tipo": "sprinkler", "camada": "pset", "confianca": "alta",
                "motivo": "Pset_SegurancaIncendio.Tipo = Sprinkler"}
    if tipo_pset == "detector":
        return {"tipo": "detector", "camada": "pset", "confianca": "alta",
                "motivo": "Pset_SegurancaIncendio.Tipo = Detector"}

    # Camada 3: nome do elemento (inclui marcas de fabricante conhecidas)
    if any(f in nome for f in FABRICANTES_EXTINTOR):
        return {"tipo": "extintor", "camada": "nome", "confianca": "media",
                "motivo": f"Nome '{el.Name}' contém termo associado a extintor"}
    if any(t in nome for t in TERMOS_SPRINKLER):
        return {"tipo": "sprinkler", "camada": "nome", "confianca": "media",
                "motivo": f"Nome '{el.Name}' contém termo associado a sprinkler"}

    # Camada 4: classe nativa correta mas sem sinal suficiente para
    # decidir extintor/sprinkler/detector — não descarta, marca para IA.
    if e_classe_nativa:
        return {"tipo": "indefinido", "camada": "ia", "confianca": "baixa",
                "motivo": "IfcFireSuppressionTerminal sem ObjectType/Pset/nome conclusivos; "
                          "recomenda-se revisão manual ou assistida por IA."}

    # Proxy genérico sem nenhum sinal de incêndio: não é um terminal de
    # incêndio para efeitos desta verificação.
    return None


def _pos_metros(element, escala):
    m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
    return m[0, 3] * escala, m[1, 3] * escala


def _dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _pavimento(element):
    container = ifcopenshell.util.element.get_container(element)
    if container is None:
        return None, "Sem_Pavimento"
    return container.id(), (container.Name or f"Pavimento_{container.id()}")


def _area_pavimento_m2(model, storey, escala):
    """Estima a área de UM pavimento específico.
    1) Preferência: soma das áreas de IfcSpace contidos no pavimento
       (Pset_SpaceCommon.GrossFloorArea ou NetFloorArea).
    2) Fallback: bounding box XY dos elementos com geometria contidos
       nesse pavimento (não do edifício inteiro)."""

    # 1) IfcSpace, quando disponível — mais preciso que bounding box
    areas_space = []
    for space in model.by_type("IfcSpace"):
        if ifcopenshell.util.element.get_container(space) != storey:
            continue
        pset_common = ifcopenshell.util.element.get_pset(space, "Pset_SpaceCommon") or {}
        area = pset_common.get("GrossFloorArea") or pset_common.get("NetFloorArea")
        if area:
            areas_space.append(area)
    if areas_space:
        return round(sum(areas_space), 1), "IfcSpace"

    # 2) Fallback: bounding box dos elementos DESTE pavimento apenas
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    xs, ys = [], []
    for el in model.by_type("IfcProduct"):
        if not el.Representation:
            continue
        if ifcopenshell.util.element.get_container(el) != storey:
            continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, el)
            v = shape.geometry.verts
            xs.extend(v[0::3])
            ys.extend(v[1::3])
        except Exception:
            continue
    if not xs:
        return None, None
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    return round(dx * dy, 1), "bounding_box_aproximado"


def verificar_sistema_incendio(caminho_ifc: str) -> list:
    model = ifcopenshell.open(caminho_ifc)
    escala = ifcopenshell.util.unit.calculate_unit_scale(model)

    candidatos = []
    for ifc_class in CLASSES_CANDIDATAS:
        candidatos.extend(model.by_type(ifc_class))

    terminais_identificados = []
    for el in candidatos:
        info = _identificar_terminal_incendio(el)
        if info is None:
            continue
        pav_id, pav_nome = _pavimento(el)
        terminais_identificados.append({
            "elemento": el, "info": info, "pavimento_id": pav_id, "pavimento_nome": pav_nome,
        })

    extintores = [t for t in terminais_identificados if t["info"]["tipo"] == "extintor"]
    sprinklers = [t for t in terminais_identificados if t["info"]["tipo"] == "sprinkler"]
    indefinidos = [t for t in terminais_identificados if t["info"]["tipo"] == "indefinido"]

    portas = []
    for d in model.by_type("IfcDoor"):
        pav_id, pav_nome = _pavimento(d)
        portas.append({"elemento": d, "pavimento_id": pav_id, "pavimento_nome": pav_nome})

    resultados = []

    # IMPORTANTE: o Aula_05_Agente_Coordenacao_Seguranca.py (modo terminal,
    # já em produção) consome esta lista fazendo r['porta_apartamento'],
    # r['extintor_mais_proximo'], r['distancia_m'], r['raio_cobertura_m']
    # DIRETO POR COLCHETE, em TODOS os itens da lista, sem filtrar por
    # categoria. Por isso, mesmo os itens que não são sobre uma porta
    # específica (Resumo, Sprinklers, terminal não classificado) carregam
    # essas 4 chaves com valores placeholder — nunca ficam ausentes.
    CHAVES_BASE = {"porta_apartamento": "N/D", "extintor_mais_proximo": "N/D",
                   "distancia_m": None, "raio_cobertura_m": RAIO_EXTINTOR_M}

    resultados.append({
        **CHAVES_BASE,
        "categoria": "Resumo",
        "extintores_encontrados": len(extintores),
        "sprinklers_encontrados": len(sprinklers),
        "terminais_nao_classificados": len(indefinidos),
        "conforme": None,
        "motivo": (f"{len(extintores)} extintor(es), {len(sprinklers)} sprinkler(s) e "
                   f"{len(indefinidos)} terminal(is) de incêndio não classificado(s) encontrados. "
                   f"Este resumo é apenas uma contagem, não um veredito de conformidade — "
                   f"veja os itens abaixo."),
    })

    for t in indefinidos:
        resultados.append({
            **CHAVES_BASE,
            "categoria": "Terminal_Nao_Classificado",
            "elemento": t["elemento"].Name,
            "global_id": t["elemento"].GlobalId,
            "pavimento": t["pavimento_nome"],
            "conforme": None,
            "motivo": t["info"]["motivo"],
        })

    # --- EXTINTORES: verificação por distância até portas, por pavimento ---
    if not extintores:
        resultados.append({
            **CHAVES_BASE,
            "categoria": "Extintores",
            "conforme": False,
            "motivo": "Nenhum extintor identificado (nem por ObjectType nativo, nem por "
                      "Pset_SegurancaIncendio, nem por nome de fabricante).",
        })
    else:
        for porta in portas:
            candidatos_pav = [e for e in extintores if e["pavimento_id"] == porta["pavimento_id"]]
            if not candidatos_pav:
                resultados.append({
                    **CHAVES_BASE,
                    "categoria": "Extintor",
                    "porta_apartamento": porta["elemento"].Name, "porta_global_id": porta["elemento"].GlobalId,
                    "pavimento": porta["pavimento_nome"],
                    "conforme": False,
                    "motivo": f"Nenhum extintor encontrado no pavimento "
                              f"'{porta['pavimento_nome']}'.",
                })
                continue
            pos_porta = _pos_metros(porta["elemento"], escala)
            mais_proximo, menor_dist = None, float("inf")
            for ext in candidatos_pav:
                d = _dist(pos_porta, _pos_metros(ext["elemento"], escala))
                if d < menor_dist:
                    menor_dist, mais_proximo = d, ext
            conforme = menor_dist <= RAIO_EXTINTOR_M
            resultados.append({
                "categoria": "Extintor",
                "porta_apartamento": porta["elemento"].Name, "porta_global_id": porta["elemento"].GlobalId,
                "pavimento": porta["pavimento_nome"],
                "extintor_mais_proximo": mais_proximo["elemento"].Name,
                "camada_identificacao": mais_proximo["info"]["camada"],
                "distancia_m": round(menor_dist, 2),
                "raio_cobertura_m": RAIO_EXTINTOR_M,
                "conforme": conforme,
                "motivo": (
                    f"Extintor mais próximo de '{porta['elemento'].Name}' (pavimento "
                    f"'{porta['pavimento_nome']}') está a {menor_dist:.1f} m — "
                    f"{'dentro do' if conforme else 'FORA do'} raio de {RAIO_EXTINTOR_M:.0f} m (NBR 12693)."
                ),
            })

    # --- SPRINKLERS: verificação por cobertura de área, por pavimento ---
    if not sprinklers:
        resultados.append({
            **CHAVES_BASE,
            "categoria": "Sprinklers",
            "conforme": False,
            "motivo": "Nenhum sprinkler identificado (nem por ObjectType nativo, nem por "
                      "Pset_SegurancaIncendio, nem por nome). Verificar se o sistema de "
                      "chuveiros automáticos foi modelado no IFC.",
        })
    else:
        pavimentos_com_sprinkler = {}
        for s in sprinklers:
            pavimentos_com_sprinkler.setdefault(s["pavimento_id"], {"nome": s["pavimento_nome"], "itens": []})
            pavimentos_com_sprinkler[s["pavimento_id"]]["itens"].append(s)

        for pav_id, dados in pavimentos_com_sprinkler.items():
            pav_nome = dados["nome"]
            qtd = len(dados["itens"])
            # storey object precisa ser recuperado para _area_pavimento_m2
            storey_obj = ifcopenshell.util.element.get_container(dados["itens"][0]["elemento"])
            area_m2, metodo_area = _area_pavimento_m2(model, storey_obj, escala)

            if area_m2 is None or area_m2 <= 0:
                resultados.append({
                    **CHAVES_BASE,
                    "categoria": "Sprinklers",
                    "pavimento": pav_nome,
                    "quantidade": qtd,
                    "conforme": None,
                    "motivo": f"{qtd} sprinkler(s) no pavimento '{pav_nome}'. Não foi possível "
                              f"calcular a área do pavimento automaticamente — adicione IfcSpace "
                              f"ao modelo para verificação precisa de cobertura.",
                })
                continue

            area_por_cabeca = round(area_m2 / qtd, 1)
            conforme_leve = area_por_cabeca <= AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2
            conforme_ordinario = area_por_cabeca <= AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2

            resultados.append({
                **CHAVES_BASE,
                "categoria": "Sprinklers",
                "pavimento": pav_nome,
                "quantidade": qtd,
                "area_pavimento_m2": area_m2,
                "area_metodo": metodo_area,
                "area_por_cabeca_m2": area_por_cabeca,
                "limite_risco_leve_m2": AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2,
                "limite_risco_ordinario_m2": AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2,
                "conforme_risco_leve": conforme_leve,
                "conforme_risco_ordinario": conforme_ordinario,
                "conforme": conforme_leve,
                "nomes_sprinklers": [s["elemento"].Name for s in dados["itens"]],
                "motivo": (
                    f"{qtd} sprinkler(s) no pavimento '{pav_nome}' para área "
                    f"{'estimada por bounding box' if metodo_area == 'bounding_box_aproximado' else 'calculada via IfcSpace'} "
                    f"de {area_m2} m². Área por cabeça: {area_por_cabeca} m²/cabeça. "
                    f"Risco leve (≤ {AREA_MAX_POR_SPRINKLER_RISCO_LEVE_M2} m²/cabeça): "
                    f"{'CONFORME' if conforme_leve else 'NÃO CONFORME'}. "
                    f"Risco ordinário (≤ {AREA_MAX_POR_SPRINKLER_RISCO_ORDINARIO_M2} m²/cabeça): "
                    f"{'CONFORME' if conforme_ordinario else 'NÃO CONFORME'} (NBR 10897)."
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
