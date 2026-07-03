# Agente de Coordenação e Segurança AEC

**Módulo 7, Tema 5 — MAICPT**
**Aluno:** Sergio Rosenboim — Arquiteto | BIM, Data & AI for Construction
**Framework:** Agno | **Modelo:** Claude Sonnet (Anthropic) | **BIM:** ifcopenshell

Mesmo padrão ensinado na Aula 04 pelo professor Carlos Dias.

---

## Estrutura

```
.
├── playground.py                  ← backend AgentOS (porta 7777)
├── Aula_05_Agente_...py           ← modo terminal (alternativo)
├── modelo_exemplo.ifc             ← IFC de teste
├── .env.example                   ← copie para .env e adicione a chave
├── requirements.txt
├── agent-ui/                      ← frontend Next.js (chat web)
└── skills/
    └── seguranca-aec/
        ├── SKILL.md
        └── scripts/
            ├── detectar_clashes.py
            ├── verificar_rota_fuga.py
            ├── verificar_sistema_incendio.py
            └── verificar_guarda_corpos.py
```

---

## Instalação

### Python

```bash
pip install agno ifcopenshell anthropic fastapi uvicorn python-dotenv
```

### Chave Anthropic

```bash
copy .env.example .env
notepad .env
```

Substitua pela sua chave:
```
ANTHROPIC_API_KEY=sk-ant-SUA-CHAVE-AQUI
```

Chave em: https://console.anthropic.com → API Keys

### Node.js (para o agent-ui)

Precisa ter Node.js 18+ instalado: https://nodejs.org

---

## Como executar

### Terminal 1 — backend

```bash
python playground.py
```

### Terminal 2 — frontend

```bash
cd agent-ui
npm install -g pnpm
pnpm install
pnpm dev
```

### Navegador

Abra: **http://localhost:3000**

Selecione o agente `AgenteCoordenacaoSeguranca` e pergunte:

```
Faça uma análise geral do modelo_exemplo.ifc
```

---

## Resultado esperado

| Verificação | Resultado |
|---|---|
| Clashes | 6 encontrados (estrutura × HVAC/Hidráulica/Elétrica + entre disciplinas) |
| Rota de fuga | Apto 101: 16,16 m ✅ / Apto 110: 45,65 m ❌ |
| Extintores | Apto 101: 4,0 m ✅ / Apto 110: 27,73 m ❌ |
| Guarda-corpos | Varanda 101 ✅ / Varanda 110 ❌ / Janela 110 ❌ |
