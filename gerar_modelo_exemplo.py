"""
gerar_modelo_exemplo.py
-------------------------------------------------------------------
Gera modelo IFC sintético usando APENAS parâmetros nativos do IFC —
sem nenhum pset customizado — para que os scripts funcionem com
qualquer IFC real exportado do Revit ou ArchiCAD.

Elementos e como são identificados nativamente:
- IfcDoor com PredefinedType="DOOR"        → porta normal de apartamento
- IfcDoor com PredefinedType="EMERGENCY"   → porta corta-fogo da escada
- IfcFireSuppressionTerminal ObjectType="Extinguisher"  → extintor
- IfcFireSuppressionTerminal ObjectType="Sprinkler"     → sprinkler
- Estrutura: IfcBeam, IfcColumn, IfcSlab
- Instalações: IfcDuctSegment(HVAC), IfcPipeSegment(Hidráulica/Gás),
               IfcCableCarrierSegment(Elétrica), IfcCableSegment(Comunicação),
               IfcPipeSegment(Incêndio)
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
    ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Edificio Exemplo")
    length = ifcopenshell.api.unit.add_si_unit(model, unit_type="LENGTHUNIT", prefix="MILLI")
    ifcopenshell.api.unit.assign_unit(model, units=[length])
    context = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        model, context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=context
    )
    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Lote")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="Edificio Exemplo")
    storey = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Pavimento Tipo")
    project = model.by_type("IfcProject")[0]
    ifcopenshell.api.aggregate.assign_object(model, relating_object=project, products=[site])
    ifcopenshell.api.aggregate.assign_object(model, relating_object=site, products=[building])
    ifcopenshell.api.aggregate.assign_object(model, relating_object=building, products=[storey])
    return model, storey, body


def criar_caixa(model, storey, body, ifc_class, nome, dim_xyz, posicao_xyz,
                object_type=None, predefined_type=None):
    dx, dy, dz = dim_xyz
    px, py, pz = posicao_xyz
    elemento = ifcopenshell.api.root.create_entity(model, ifc_class=ifc_class, name=nome)
    if object_type:
        elemento.ObjectType = object_type
    if predefined_type and hasattr(elemento, 'PredefinedType'):
        try:
            elemento.PredefinedType = predefined_type
        except:
            pass
    ifcopenshell.api.spatial.assign_container(model, products=[elemento], relating_structure=storey)
    perfil = model.createIfcRectangleProfileDef(ProfileType="AREA", XDim=dx, YDim=dy)
    rep = ifcopenshell.api.geometry.add_profile_representation(
        model, context=body, profile=perfil, depth=dz / 1000.0, cardinal_point="bottom left"
    )
    ifcopenshell.api.geometry.assign_representation(model, product=elemento, representation=rep)
    matrix = ifcopenshell.util.placement.get_local_placement(elemento.ObjectPlacement)
    matrix[0:, 3][:3] = (px, py, pz)
    ifcopenshell.api.geometry.edit_object_placement(model, product=elemento, matrix=matrix, is_si=False)
    return elemento


def criar_ponto(model, storey, ifc_class, nome, posicao_xyz,
                object_type=None, predefined_type=None,
                overall_width=None, overall_height=None):
    elemento = ifcopenshell.api.root.create_entity(model, ifc_class=ifc_class, name=nome)
    if object_type:
        elemento.ObjectType = object_type
    if predefined_type and hasattr(elemento, 'PredefinedType'):
        try:
            elemento.PredefinedType = predefined_type
        except:
            pass
    if overall_width and hasattr(elemento, 'OverallWidth'):
        elemento.OverallWidth = overall_width
    if overall_height and hasattr(elemento, 'OverallHeight'):
        elemento.OverallHeight = overall_height
    ifcopenshell.api.spatial.assign_container(model, products=[elemento], relating_structure=storey)
    matrix = ifcopenshell.util.placement.get_local_placement(elemento.ObjectPlacement)
    matrix[0:, 3][:3] = posicao_xyz
    ifcopenshell.api.geometry.edit_object_placement(model, product=elemento, matrix=matrix, is_si=False)
    return elemento


def main():
    model, storey, body = novo_modelo()

    # ----- Estrutura -----
    criar_caixa(model, storey, body, "IfcColumn", "Pilar P1", (300, 300, 3000), (0, 0, 0))
    criar_caixa(model, storey, body, "IfcBeam",   "Viga V1",  (4000, 300, 400), (2000, 0, 2800))

    # ----- Instalações com ObjectType como disciplina -----
    # HVAC — clash com viga
    criar_caixa(model, storey, body, "IfcDuctSegment", "Duto Ar Condicionado D1",
                (2000, 200, 200), (3500, 50, 2900), object_type="HVAC")
    criar_caixa(model, storey, body, "IfcDuctSegment", "Duto Ar Condicionado D2",
                (2000, 200, 200), (3500, 50, 500), object_type="HVAC")

    # Hidráulica — clash com viga e HVAC
    criar_caixa(model, storey, body, "IfcPipeSegment", "Tubulacao Hidraulica H1",
                (2000, 20, 100), (3500, 150, 2950), object_type="Hidraulica")

    # Elétrica — clash com viga, HVAC e hidráulica
    criar_caixa(model, storey, body, "IfcCableCarrierSegment", "Eletroduto E1",
                (2000, 20, 50), (3500, 150, 2960), object_type="Eletrica")

    # Gás — isolado, sem clash
    criar_caixa(model, storey, body, "IfcPipeSegment", "Tubulacao Gas G1",
                (2000, 20, 100), (3500, 500, 500), object_type="Gas")

    # Comunicação — isolado, sem clash
    criar_caixa(model, storey, body, "IfcCableSegment", "Cabo Comunicacao C1",
                (200, 20, 20), (8000, 50, 500), object_type="Comunicacao")

    # Incêndio (tubulação de sprinkler) — isolado
    criar_caixa(model, storey, body, "IfcPipeSegment", "Tubulacao Incendio I1",
                (2000, 20, 20), (3500, 800, 2900), object_type="Incendio")

    # ----- Portas — identificadas por PredefinedType -----
    # Porta corta-fogo da escada de incêndio → PredefinedType = EMERGENCY
    criar_ponto(model, storey, "IfcDoor", "Porta Corta-Fogo Escada",
                (0, 8000, 0), predefined_type="EMERGENCY",
                overall_width=1100, overall_height=2100)

    # Portas normais de apartamento → PredefinedType = DOOR
    criar_ponto(model, storey, "IfcDoor", "Porta Apto 101",
                (15000, 14000, 0), predefined_type="DOOR",
                overall_width=900, overall_height=2100)
    criar_ponto(model, storey, "IfcDoor", "Porta Apto 110",
                (40000, 30000, 0), predefined_type="DOOR",
                overall_width=900, overall_height=2100)

    # ----- Extintores — ObjectType = "Extinguisher" -----
    criar_ponto(model, storey, "IfcFireSuppressionTerminal", "Extintor PQS 1",
                (15000, 18000, 0), object_type="Extinguisher")
    criar_ponto(model, storey, "IfcFireSuppressionTerminal", "Extintor PQS 2",
                (10000, 10000, 0), object_type="Extinguisher")

    # ----- Sprinklers — ObjectType = "Sprinkler" -----
    # Sprinkler cobre Apto 101 (próximo)
    criar_ponto(model, storey, "IfcFireSuppressionTerminal", "Sprinkler 01",
                (15000, 14500, 0), object_type="Sprinkler")
    # Sprinkler longe do Apto 110 (fora do raio)
    criar_ponto(model, storey, "IfcFireSuppressionTerminal", "Sprinkler 02",
                (10000, 10500, 0), object_type="Sprinkler")

    model.write(OUTPUT_PATH)
    print(f"Modelo gerado: {OUTPUT_PATH}")
    print(f"Portas: {len(model.by_type('IfcDoor'))}")
    print(f"Fire terminals: {len(model.by_type('IfcFireSuppressionTerminal'))}")


if __name__ == "__main__":
    main()
