---
name: seguranca-aec
description: Verifica clashes geometricos entre instalacoes e estrutura, distancia de rota de fuga entre apartamentos e escada de incendio, cobertura de extintores e altura de guarda-corpos/peitoris em modelos IFC, usando ifcopenshell (geometria 3D, placement e psets).
---

# Skill: seguranca-aec — Coordenação de Disciplinas e Segurança em Modelos BIM (IFC)

## Quando usar esta skill

Use esta skill sempre que o usuário pedir para:
- detectar **clashes/interferências** entre instalações (dutos, tubulações, eletrodutos, cabos) e estrutura (vigas, pilares, lajes, paredes), e também **entre instalações de disciplinas diferentes entre si** (ar condicionado x hidráulica, hidráulica x gás, elétrica x comunicação, etc.);
- verificar a **distância da rota de fuga** entre portas de apartamento e a porta da escada de incêndio;
- verificar a **cobertura de extintores** em relação às unidades/apartamentos;
- verificar a **altura de guarda-corpos** em varandas/sacadas e a necessidade de proteção em **janelas com peitoril baixo**.

## Conhecimento de referência usado nas avaliações

| Verificação | Critério adotado | Referência |
|---|---|---|
| Clash instalações × estrutura, e instalação × instalação (disciplinas diferentes) | Sobreposição de bounding box 3D real (não property set); mesma disciplina não conta como clash | Boa prática de coordenação BIM (compatibilização) |
| Rota de fuga (porta apto → porta escada) | Distância ≤ 30 m (parâmetro ajustável) | NBR 9077 (saídas de emergência) |
| Cobertura de extintores | Distância ≤ 20 m até o extintor mais próximo (parâmetro ajustável) | NBR 12693 |
| Guarda-corpo | Altura ≥ 0,92 m | NBR 9050 / boas práticas de segurança contra queda |
| Janela com peitoril baixo | Peitoril < 1,00 m exige proteção complementar | Boas práticas de segurança contra queda |

Os limites numéricos usados nas avaliações ficam declarados como
constantes no topo de cada script (ex.: `LIMITE_DISTANCIA_FUGA_M`,
`RAIO_COBERTURA_EXTINTOR_M`, `ALTURA_MIN_GUARDA_CORPO_M`), para que a
explicação do agente nunca divirja do que foi de fato calculado. Esses
valores são parâmetros de referência didáticos — em um projeto real,
devem ser confirmados com a norma vigente e com o Corpo de Bombeiros
local, pois variam por classe de risco, altura da edificação e
existência de chuveiro automático (sprinklers).

## Como o modelo IFC representa os dados

- **Estrutura/instalações** (`IfcBeam`, `IfcColumn`, `IfcDuctSegment`,
  `IfcPipeSegment`, `IfcCableCarrierSegment`, `IfcCableSegment` etc.):
  avaliadas pela **geometria 3D real** (`ifcopenshell.geom`), extraindo
  a malha de cada elemento em coordenadas absolutas e comparando
  bounding boxes. Cada elemento de instalação carrega no
  `Pset_SegurancaAEC` a propriedade `Disciplina` (ex.: `"HVAC"`,
  `"Hidraulica"`, `"Gas"`, `"Eletrica"`, `"Comunicacao"`), usada para
  decidir se duas instalações que se sobrepõem são, de fato, um clash
  (disciplinas diferentes) ou apenas segmentos conectados do mesmo
  sistema (mesma disciplina, ignorados).
- **Portas, extintores, guarda-corpos, janelas**: avaliados pela
  **posição** (`ObjectPlacement`, via `ifcopenshell.util.placement` e
  `ifcopenshell.util.unit` para converter para metros) e por um
  property set customizado `Pset_SegurancaAEC` (mesmo padrão de Pset
  customizado das Aulas 02/04), que guarda o tipo do elemento (ex.:
  porta de apartamento vs. porta de escada) e, quando aplicável,
  dimensões como altura de guarda-corpo ou peitoril.

## Ferramentas (scripts) disponíveis nesta skill

1. **`scripts/detectar_clashes.py`** — `detectar_clashes(caminho_ifc)`.
   Geometria 3D real via `ifcopenshell.geom` (bounding box, world
   coordinates). Retorna a lista de pares estrutura×instalação com
   interferência.
2. **`scripts/verificar_rota_fuga.py`** — `verificar_rota_fuga(caminho_ifc)`.
   Distância em planta entre cada porta de apartamento e a porta de
   escada de incêndio mais próxima.
3. **`scripts/verificar_sistema_incendio.py`** — `verificar_sistema_incendio(caminho_ifc)`.
   Distância entre cada porta de apartamento e o extintor mais próximo.
4. **`scripts/verificar_guarda_corpos.py`** — `verificar_guarda_corpos(caminho_ifc)`.
   Altura de guarda-corpos e necessidade de proteção em janelas com
   peitoril baixo.

## Como responder

- Sempre **chame a tool correspondente** em vez de estimar — não
  invente posições, distâncias ou alturas que não estejam no modelo.
- Ao reportar um clash, cite as duas classes/elementos envolvidos e,
  se possível, as coordenadas da bounding box.
- Ao reportar uma não conformidade de rota de fuga ou de extintor,
  cite a distância medida e o limite adotado, deixando claro que é um
  parâmetro de referência a confirmar com a norma/Corpo de Bombeiros
  aplicável ao projeto real.
- Se uma propriedade ou geometria esperada não existir no IFC, informe
  isso explicitamente em vez de assumir conformidade.
- Mantenha a resposta objetiva e técnica, adequada para uso em reunião
  de compatibilização de projetos ou relatório de vistoria.
