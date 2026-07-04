# Agente de Coordenação e Segurança AEC

**Módulo 7, Tema 5 — MAICPT**
**Aluno:** Sergio Rosenboim — Arquiteto | BIM, Data & AI for Construction
**Framework:** Agno | **Modelo:** Claude Sonnet (Anthropic) | **BIM:** ifcopenshell

Mesmo padrão ensinado na Aula 04 pelo professor Carlos Dias.

---

## O problema

Um coordenador de projetos, antes de uma reunião de compatibilização ou
vistoria, precisa responder a partir de um único modelo IFC:

1. Há **interferências físicas** entre instalações (HVAC, hidráulica, gás,
   elétrica, comunicação, incêndio) e a estrutura — e entre as próprias
   disciplinas entre si?
2. As **rotas de fuga** (distância porta de apartamento → porta corta-fogo
   da escada) estão dentro do limite normativo?
3. Os **extintores** e **sprinklers** cobrem adequadamente o pavimento?

---

## Estrutura

```
.
├── playground.py                  ← ponto de entrada (interface web + backend)
├── Aula_05_Agente_...py           ← modo terminal (alternativo)
├── gerar_modelo_exemplo.py        ← gera o IFC sintético de teste
├── modelo_exemplo.ifc             ← IFC de teste já gerado
├── .env.example                   ← copie para .env se preferir usar variável de ambiente
├── requirements.txt
├── agent-ui/                      ← frontend alternativo (agent-ui do Agno)
└── skills/
    └── seguranca-aec/
        ├── SKILL.md               ← base normativa do agente
        └── scripts/
            ├── detectar_clashes.py           ← geometria 3D (ifcopenshell.geom)
            ├── verificar_rota_fuga.py        ← PredefinedType nativo IFC
            └── verificar_sistema_incendio.py ← IfcFireSuppressionTerminal nativo
```

---

## Como as verificações usam o IFC nativo

Todas as verificações usam **apenas classes e atributos nativos do IFC** —
sem nenhum pset customizado. Funcionam com qualquer IFC exportado do
Revit, ArchiCAD ou Bonsai.

| Verificação | Técnica ifcopenshell | Atributo IFC usado |
|---|---|---|
| A — Clashes | `ifcopenshell.geom` — bounding box 3D real | Geometria dos elementos |
| B — Rota de fuga | `util.placement` + `util.unit` | `IfcDoor.PredefinedType = EMERGENCY` |
| C — Extintores | `util.placement` + `util.unit` | `IfcFireSuppressionTerminal.ObjectType = "Extinguisher"` |
| C — Sprinklers | `util.placement` + `util.unit` | `IfcFireSuppressionTerminal.ObjectType = "Sprinkler"` |

---

## Instalação

```bash
pip install agno ifcopenshell anthropic fastapi uvicorn python-dotenv
```

Node.js (para o agent-ui alternativo): https://nodejs.org

---

## Como executar

```bash
python playground.py
```

O navegador abre automaticamente em **http://localhost:7777** com:

1. **Tela de configuração** — informe a chave Anthropic e o caminho do arquivo IFC
2. **Menu de verificações** — escolha o que verificar
3. **Resultado** — relatório com tabelas em markdown

---

## Verificações disponíveis

| Botão | Verificação | Norma |
|---|---|---|
| A | Clashes geométricos — todas disciplinas × estrutura + entre si | Boa prática BIM |
| B | Rota de fuga — porta apartamento → porta corta-fogo escada | NBR 9077 (≤ 30 m) |
| C | Sistema de incêndio — extintores + sprinklers | NBR 12693 (≤ 20 m) / NBR 10897 (≤ 4 m) |
| D | Análise completa — todas as verificações | — |

---

## Resultado esperado com o modelo_exemplo.ifc

| Verificação | Resultado |
|---|---|
| **Clashes** | 3 encontrados: Viga V1 × HVAC, Viga V1 × Hidráulica, Viga V1 × Elétrica |
| **Rota de fuga** | Apto 101: 16,16 m ✅ conforme / Apto 110: 45,65 m ❌ excede 30 m |
| **Extintores** | Porta Corta-Fogo: 10,2 m ✅ / Apto 101: 4,0 m ✅ / Apto 110: 27,7 m ❌ |
| **Sprinklers** | Apto 101: 0,5 m ✅ / Apto 110: 29,4 m ❌ fora do raio de 4 m |

---

## Observação importante

Os limites numéricos (30 m de rota de fuga, 20 m de extintor, 4 m de
sprinkler) são **parâmetros de referência**. Em projeto real, confirme
com a norma vigente e o Corpo de Bombeiros local, pois variam com a
classe de risco, altura da edificação e presença de sprinklers.

---

## Como usar com um IFC real do Revit ou ArchiCAD

1. Exporte o IFC do seu software BIM:
   - Revit → Arquivo → Exportar → IFC
   - ArchiCAD → Arquivo → Salvar como → IFC
   - Bonsai → Arquivo → Exportar → IFC

2. Rode `python playground.py`

3. Na tela de configuração, informe o caminho do seu arquivo `.ifc`

4. O agente detecta automaticamente os elementos por tipo nativo:
   - Portas corta-fogo: `IfcDoor` com `PredefinedType = EMERGENCY`
   - Extintores: `IfcFireSuppressionTerminal` com `ObjectType = Extinguisher`
   - Sprinklers: `IfcFireSuppressionTerminal` com `ObjectType = Sprinkler`
