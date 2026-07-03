"""
gerar_modelo_exemplo.py
-------------------------------------------------------------------
Gera um modelo IFC sintético ("modelo_exemplo.ifc") com geometria real
(não apenas property sets) para servir de base de testes do Agente de
Coordenação e Segurança AEC:

- Estrutura: pilar e viga (IfcColumn, IfcBeam) com representação 3D.
- Instalações: dois dutos (IfcDuctSegment) — um propositalmente
  cruzando a viga (clash) e outro livre (sem clash).
- Portas: porta de apartamento e porta da escada de incêndio, em
  posições com distâncias diferentes (uma dentro do limite de rota de
  fuga, outra fora).
- Sistema de incêndio: dois extintores (IfcFireSuppressionTerminal),
  um dentro do raio de cobertura de uma das portas, outro fora.
- Guarda-corpos e janelas: uma varanda com guarda-corpo conforme, uma
  com guarda-corpo baixo, e uma janela com peitoril baixo sem proteção.

Execução:
    python gerar_modelo_exemplo.py
"""

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.util.placement

OUTPUT_PATH = "modelo_exemplo.ifc"


def novo_modelo():
    model = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Edificio Exemplo - Coordenacao e Seguranca")

    length = ifcopenshell.api.unit.add_si_unit(model, unit_type="LENGTHUNIT", prefix="MILLI")
    ifcopenshell.api.unit.assign_unit(model, units=[length])

    context = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=context
    )

    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Lote")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="Edificio Exemplo")
    storey = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Pavimento Tipo")

    project = model.by_type("IfcProject")[0]
    ifcopenshell.api.aggregate.assign_object(model, relating_object=project, products=[site])
    ifcopenshell.api.aggregate.assign_object(model, relating_object=site, products=[building])
    ifcopenshell.api.aggregate.assign_object(model, relating_object=building, products=[storey])

    return model, storey, body


def criar_caixa(model, storey, body, ifc_class, nome, dim_xyz, posicao_xyz, dados_pset=None):
    """Cria um elemento com representacao de caixa (perfil retangular
    extrudado) posicionado pelo canto minimo (posicao_xyz) com as
    dimensoes dim_xyz = (largura X, profundidade Y, altura Z), em mm.
    """
    dx, dy, dz = dim_xyz
    px, py, pz = posicao_xyz

    elemento = ifcopenshell.api.root.create_entity(model, ifc_class=ifc_class, name=nome)
    ifcopenshell.api.spatial.assign_container(model, products=[elemento], relating_structure=storey)

    perfil = model.createIfcRectangleProfileDef(ProfileType="AREA", XDim=dx, YDim=dy)
    representacao = ifcopenshell.api.geometry.add_profile_representation(
        model, context=body, profile=perfil, depth=dz / 1000.0, cardinal_point="bottom left"
    )
    ifcopenshell.api.geometry.assign_representation(model, product=elemento, representation=representacao)

    matrix = ifcopenshell.util.placement.get_local_placement(elemento.ObjectPlacement)
    matrix[0:, 3][:3] = (px, py, pz)
    ifcopenshell.api.geometry.edit_object_placement(model, product=elemento, matrix=matrix, is_si=False)

    if dados_pset:
        pset = ifcopenshell.api.pset.add_pset(model, product=elemento, name="Pset_SegurancaAEC")
        ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=dados_pset)

    return elemento


def criar_ponto(model, storey, ifc_class, nome, posicao_xyz, dados_pset=None):
    """Cria um elemento pontual (sem representacao 3D), util para
    portas, extintores e guarda-corpos avaliados por posicao/pset.
    """
    elemento = ifcopenshell.api.root.create_entity(model, ifc_class=ifc_class, name=nome)
    ifcopenshell.api.spatial.assign_container(model, products=[elemento], relating_structure=storey)

    matrix = ifcopenshell.util.placement.get_local_placement(elemento.ObjectPlacement)
    matrix[0:, 3][:3] = posicao_xyz
    ifcopenshell.api.geometry.edit_object_placement(model, product=elemento, matrix=matrix, is_si=False)

    if dados_pset:
        pset = ifcopenshell.api.pset.add_pset(model, product=elemento, name="Pset_SegurancaAEC")
        ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=dados_pset)

    return elemento


def main():
    model, storey, body = novo_modelo()

    # ----- Estrutura -----
    # Pilar de 300x300, do piso (z=0) ate 3000 mm
    criar_caixa(model, storey, body, "IfcColumn", "Pilar P1", (300, 300, 3000), (0, 0, 0))
    # Viga de 4000x300x400, no topo do pavimento (z=2800 a 3200), de x=2000 a x=6000
    criar_caixa(model, storey, body, "IfcBeam", "Viga V1", (4000, 300, 400), (2000, 0, 2800))

    # ----- Instalações -----
    # Cada elemento de instalação recebe Disciplina no Pset_SegurancaAEC,
    # para permitir checar clash tanto contra a estrutura quanto entre
    # disciplinas diferentes (ar x hidráulica, hidráulica x elétrica, etc.)

    # HVAC (ar-condicionado): Duto D1 passa por dentro da viga V1 -> CLASH com a estrutura
    criar_caixa(model, storey, body, "IfcDuctSegment", "Duto Ar Condicionado D1",
                (2000, 200, 200), (3500, 50, 2900), dados_pset={"Disciplina": "HVAC"})
    # HVAC: Duto D2, no piso, longe de tudo -> SEM clash
    criar_caixa(model, storey, body, "IfcDuctSegment", "Duto Ar Condicionado D2",
                (2000, 200, 200), (3500, 50, 500), dados_pset={"Disciplina": "HVAC"})

    # Hidráulica: Tubulação H1 cruza a mesma região do Duto D1 -> CLASH HVAC x Hidráulica
    criar_caixa(model, storey, body, "IfcPipeSegment", "Tubulacao Hidraulica H1",
                (2000, 20, 100), (3500, 150, 2950), dados_pset={"Disciplina": "Hidraulica"})

    # Elétrica: Eletroduto E1 cruza tanto o Duto D1 quanto a Tubulação H1 -> CLASH triplo
    criar_caixa(model, storey, body, "IfcCableCarrierSegment", "Eletroduto E1",
                (2000, 20, 50), (3500, 150, 2960), dados_pset={"Disciplina": "Eletrica"})

    # Gás: Tubulação G1, isolada -> SEM clash com nenhuma outra disciplina
    criar_caixa(model, storey, body, "IfcPipeSegment", "Tubulacao Gas G1",
                (2000, 20, 100), (3500, 500, 500), dados_pset={"Disciplina": "Gas"})

    # Comunicação: Cabo C1, isolado -> SEM clash com nenhuma outra disciplina
    criar_caixa(model, storey, body, "IfcCableSegment", "Cabo Comunicacao C1",
                (200, 20, 20), (8000, 50, 500), dados_pset={"Disciplina": "Comunicacao"})

    # ----- Rota de fuga: portas -----
    # Porta da escada de incendio (referencia para o calculo de distancia)
    criar_ponto(model, storey, "IfcDoor", "Porta Escada de Incendio",
                (0, 8000, 0), {"Tipo": "EscadaIncendio"})
    # Porta de apartamento dentro do limite (distancia ~20 m)
    criar_ponto(model, storey, "IfcDoor", "Porta Apto 101",
                (15000, 14000, 0), {"Tipo": "Apartamento"})
    # Porta de apartamento fora do limite (distancia ~45 m)
    criar_ponto(model, storey, "IfcDoor", "Porta Apto 110",
                (40000, 30000, 0), {"Tipo": "Apartamento"})

    # ----- Sistema de incendio: extintores -----
    # Extintor proximo da Porta Apto 101 (dentro do raio de cobertura, ~5 m)
    criar_ponto(model, storey, "IfcFireSuppressionTerminal", "Extintor Corredor 1",
                (15000, 18000, 0), {"TipoAgente": "PQS", "CapacidadeKg": 6})
    # Extintor distante da Porta Apto 110 (fora do raio de cobertura, >20 m)
    criar_ponto(model, storey, "IfcFireSuppressionTerminal", "Extintor Corredor 2",
                (10000, 10000, 0), {"TipoAgente": "PQS", "CapacidadeKg": 6})

    # ----- Guarda-corpos e janelas -----
    criar_ponto(model, storey, "IfcRailing", "Guarda-corpo Varanda 101",
                (15000, 14500, 0), {"Altura_m": 1.05, "Local": "Varanda Apto 101"})
    criar_ponto(model, storey, "IfcRailing", "Guarda-corpo Varanda 110",
                (40000, 30500, 0), {"Altura_m": 0.80, "Local": "Varanda Apto 110"})
    criar_ponto(model, storey, "IfcWindow", "Janela Quarto 101",
                (15500, 14000, 0), {"AlturaPeitoril_m": 1.10, "AlturaGuarda_m": None, "Local": "Quarto Apto 101"})
    criar_ponto(model, storey, "IfcWindow", "Janela Quarto 110",
                (40500, 30000, 0), {"AlturaPeitoril_m": 0.40, "AlturaGuarda_m": None, "Local": "Quarto Apto 110"})

    model.write(OUTPUT_PATH)
    print(f"Modelo gerado com sucesso: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
