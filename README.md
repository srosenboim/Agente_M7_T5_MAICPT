# Agente de Coordenação e Segurança AEC

**Módulo 7, Tema 5 — MAICPT**
**Aluno:** Sergio Rosenboim — Arquiteto | BIM, Data & AI for Construction
**Framework:** Agno | **Modelo:** Claude Sonnet 4.6 (Anthropic) | **BIM:** ifcopenshell

---

## Como instalar e rodar

### Pré-requisitos

- **Python 3.10+** → https://www.python.org/downloads *(Windows: marque "Add Python to PATH")*
- **Git** → https://git-scm.com

---

### Passo a passo

**1. Clonar o repositório:**
```bash
git clone https://github.com/srosenboim/Agente_M7_T5_MAICPT.git
```

**2. Entrar na pasta:**
```bash
cd Agente_M7_T5_MAICPT
```

**3. Instalar dependências:**
```bash
pip install -r requirements.txt
```

**4. Rodar o agente:**
```bash
python playground.py
```

**5. Abrir no navegador:**
```
http://localhost:7777
```

---

### Primeira vez que abrir

1. Informe sua **chave Anthropic API Key** → obtenha em [console.anthropic.com](https://console.anthropic.com) → API Keys
2. Selecione seu arquivo **IFC** ou deixe em branco para usar o modelo de exemplo incluído
3. Clique em **Iniciar agente**

---

## O problema que o agente resolve

Um coordenador de projetos, antes de uma reunião de compatibilização ou vistoria, precisa responder a partir de um único modelo IFC:

1. Há **interferências físicas** entre instalações (HVAC, hidráulica, gás, elétrica, comunicação) e a estrutura — e entre as próprias disciplinas entre si?
2. As **rotas de fuga** estão dentro do limite normativo?
3. Os **extintores** e **sprinklers** cobrem adequadamente o pavimento?

---

## Verificações disponíveis

| Botão | Verificação | Norma |
|---|---|---|
| **A** | Clashes geométricos — instalações x estrutura + entre disciplinas | Boa prática BIM |
| **B** | Rota de fuga — porta apartamento → porta corta-fogo da escada | NBR 9077 (30 m) |
| **C** | Sistema de incêndio — extintores + sprinklers | NBR 12693 / NBR 10897 |
| **D** | Análise completa — todas as verificações | — |

---

## Estrutura do repositório

```
.
├── playground.py                  ← ponto de entrada (interface web + backend Agno)
├── interface.html                 ← interface visual
├── modelo_exemplo.ifc             ← IFC de teste incluído
├── requirements.txt
└── skills/
    └── seguranca-aec/
        ├── SKILL.md
        └── scripts/
            ├── detectar_clashes.py
            ├── verificar_rota_fuga.py
            └── verificar_sistema_incendio.py
```

---

## Como usar com IFC real

Exporte do seu software BIM (Revit, ArchiCAD, Bonsai) e selecione na tela de configuração.

O agente detecta automaticamente por tipo nativo do IFC — sem configuração extra.

---

## Observação

Os limites numéricos são parâmetros de referência. Confirme com a norma vigente e o Corpo de Bombeiros local para projetos reais.
