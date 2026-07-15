# Agente de Coordenação e Segurança AEC

**Módulo 7, Tema 5 — MAICPT**
**Aluno:** Sergio Rosenboim — Arquiteto | BIM, Data & AI for Construction
**Framework:** Agno | **Modelo:** Claude Sonnet 4.6 (Anthropic) | **BIM:** ifcopenshell

---

## O que é

Um agente de IA que audita um modelo IFC (Revit, ArchiCAD, Bonsai ou qualquer
outro software BIM) e responde três perguntas que todo coordenador de projeto
precisa checar antes de uma reunião de compatibilização ou vistoria:

1. Há **interferências físicas** (clashes) entre instalações (HVAC,
   hidráulica, gás, elétrica, comunicação, incêndio) e a estrutura — e entre
   as próprias disciplinas de instalação entre si?
2. As **rotas de fuga** (porta de apartamento → porta corta-fogo da escada,
   por pavimento) estão dentro do limite normativo?
3. Os **extintores** e **sprinklers** cobrem adequadamente cada pavimento?

O agente nunca inventa números: toda resposta vem de dados extraídos de
verdade do arquivo IFC via `ifcopenshell`, e o Claude só formata/explica o
que os scripts encontraram.

---

## Como instalar e rodar

### Pré-requisitos

- **Python 3.10+** → https://www.python.org/downloads *(Windows: marque "Add Python to PATH")*
- **Git** → https://git-scm.com
- Uma **chave de API da Anthropic** → obtenha em [console.anthropic.com](https://console.anthropic.com) → API Keys

### Passo a passo

**1. Clonar o repositório:**
```bash
git clone https://github.com/srosenboim/Agente_M7_T5_MAICPT.git
cd Agente_M7_T5_MAICPT
```

**2. Instalar as dependências:**
```bash
pip install -r requirements.txt
```

**3. (Opcional) Gerar o modelo IFC de teste do zero:**
```bash
python gerar_modelo_exemplo.py
```
> O repositório já vem com um `modelo_exemplo.ifc` pronto — só rode este
> comando se quiser regenerá-lo (por exemplo, depois de editar o gerador).

**4. Rodar o agente:**
```bash
python playground.py
```
Isso abre automaticamente `http://localhost:7777` no navegador.

**5. Na tela inicial:**
1. Cole sua chave da API da Anthropic
2. Clique em **"Usar modelo de exemplo incluído"** (testa direto, sem precisar
   de um IFC próprio) — ou em **"Selecionar arquivo(s) IFC"** para subir o seu
3. Clique em iniciar o agente e escolha uma das 4 verificações

---

## Verificações disponíveis

| Botão | Verificação | Norma de referência |
|---|---|---|
| **A** | Clashes geométricos — instalações × estrutura + entre disciplinas de instalação | Boa prática BIM |
| **B** | Rota de fuga — porta de apartamento → porta corta-fogo da escada, por pavimento | NBR 9077 (≤ 30 m) |
| **C** | Sistema de incêndio — extintores + sprinklers, por pavimento | NBR 12693 (≤ 20 m) / NBR 10897 (≤ 12 m²/cabeça) |
| **D** | Análise completa — todas as verificações em sequência | — |

Existe também um modo terminal alternativo
(`Aula_05_Agente_Coordenacao_Seguranca.py`), que roda as mesmas verificações
por linha de comando e inclui uma quarta checagem — guarda-corpos e altura
de peitoril de janela (`verificar_guarda_corpos.py`) — ainda não conectada à
interface web.

---

## Como o agente identifica os elementos no IFC

Este é o diferencial deste projeto em relação a uma verificação IFC comum:
**cada elemento é identificado em 4 camadas**, da mais confiável para a mais
fraca. Isso é necessário porque, na prática, nem todo IFC exportado usa a
classe ou o atributo "certo" — famílias de fabricante viram
`IfcBuildingElementProxy`, softwares diferentes preenchem campos diferentes,
e às vezes a única pista disponível é o nome do elemento.

```
1. Classe/atributo NATIVO e padrão do schema IFC
   (ex.: Pset_DoorCommon.FireExit — property set oficial buildingSMART,
    não uma invenção deste projeto)
        ↓ se não resolver
2. Pset CUSTOMIZADO deste projeto
   (Pset_SegurancaIncendio, Pset_RoteiroFuga, Pset_Instalacao)
        ↓ se não resolver
3. NOME do elemento
   (inclui nomes de fabricante conhecidos: Ansul, Kidde, Amerex...)
        ↓ se não resolver
4. Fica marcado como "indefinido" para revisão humana ou da IA —
   NUNCA é descartado nem classificado por adivinhação
```

### Psets customizados usados

| Pset | Onde é aplicado | Propriedades |
|---|---|---|
| `Pset_SegurancaIncendio` | Extintores, sprinklers, detectores | `Tipo`, `Agente_Extintor`, `Capacidade_kg`, `Raio_Cobertura_m` |
| `Pset_RoteiroFuga` | Portas | `Tipo` (Corta_Fogo/Apartamento), `Material`, `Resistencia_Fogo_min`, `Largura_Livre_m` |
| `Pset_Instalacao` | Dutos, tubulações, eletrodutos, cabos | `Disciplina`, `Fabricante`, `Modelo` |

Além destes, o script de rota de fuga também reconhece o Pset **oficial**
`Pset_DoorCommon` (`FireExit`, `FireRating`) — o property set padronizado
pelo buildingSMART, que tem prioridade sobre o Pset customizado por ser mais
próximo do "nativo" do schema.

> **Nota técnica:** `PredefinedType = "EMERGENCY"` **não é um valor válido**
> para `IfcDoor` no schema IFC4 (o enum `IfcDoorTypeEnum` só aceita
> `DOOR`/`GATE`/`TRAPDOOR`/`USERDEFINED`/`NOTDEFINED`). Por isso a
> identificação de porta corta-fogo usa `Pset_DoorCommon.FireExit` como
> sinal nativo real, e não esse atributo.

---

## Estrutura do repositório

```
.
├── playground.py                          ← ponto de entrada (interface web + backend Agno)
├── interface.html                         ← interface visual
├── gerar_modelo_exemplo.py                ← gera o modelo_exemplo.ifc de teste
├── modelo_exemplo.ifc                     ← IFC de teste incluído
├── Aula_05_Agente_Coordenacao_Seguranca.py ← modo terminal (alternativo, 4 verificações)
├── requirements.txt
├── .env.example
└── skills/
    └── seguranca-aec/
        ├── SKILL.md
        └── scripts/
            ├── detectar_clashes.py         ← clashes 3D reais (bounding box)
            ├── verificar_rota_fuga.py      ← distância porta apto → escada
            ├── verificar_sistema_incendio.py ← extintores + sprinklers
            ├── verificar_guarda_corpos.py   ← guarda-corpos/janelas (só modo terminal)
            └── colorir_auditoria_ifc.py     ← gera IFC colorido (clash=amarelo, não conforme=vermelho)
```

---

## Resultado esperado com o `modelo_exemplo.ifc` incluído

| Verificação | Resultado |
|---|---|
| **Clashes** | 6 encontrados: Viga V1 × HVAC, Hidráulica, Elétrica (estrutura) + HVAC×Hidráulica, HVAC×Elétrica, Hidráulica×Elétrica (entre disciplinas) |
| **Rota de fuga** | Porta Apto 101: 16,16 m ✅ / Porta Apto 110 Cobertura: 45,65 m ❌ excede 30 m / Porta Apto 205: 27,73 m ✅ |
| **Extintores** | Todas as 4 portas conformes (4,0 a 10,2 m) — testando os 3 métodos de identificação (nativo, pset, nome) ao mesmo tempo |
| **Sprinklers** | Pavimento Tipo: 17,1 m²/cabeça ❌ acima do limite de 12 m²/cabeça (NBR 10897) |

O modelo de exemplo mistura de propósito os 3 métodos de identificação de
extintor (classe nativa, Pset customizado, nome de fabricante) e inclui uma
porta sem nenhum Pset preenchido, para validar que o fallback funciona.

---

## Como usar com um IFC real (Revit, ArchiCAD, Bonsai)

1. Exporte o IFC do seu software BIM:
   - **Revit** → Arquivo → Exportar → IFC
   - **ArchiCAD** → Arquivo → Salvar como → IFC
   - **Bonsai** → Arquivo → Exportar → IFC
2. Rode `python playground.py` e suba o arquivo pela interface
3. O agente identifica os elementos automaticamente pelas 4 camadas descritas
   acima — não é necessário preencher os Psets customizados para o IFC
   funcionar; eles são usados quando presentes, mas o sistema também
   funciona com IFCs "crus", caindo nas camadas de nome/fallback.

---

## Observação importante

Os limites numéricos (30 m de rota de fuga, 20 m de extintor, 12 m²/cabeça
de sprinkler) são **parâmetros de referência**. Em projeto real, confirme
com a norma vigente e o Corpo de Bombeiros local, pois variam com a classe
de risco, altura da edificação e presença de outros sistemas de proteção.

A distância de rota de fuga é calculada em **linha reta** entre as portas —
não é a distância real percorrida pelo corredor. Trate como uma triagem
inicial, não como o valor oficial de conformidade.
