"""
playground.py
-------------------------------------------------------------------
Agente de Coordenação e Segurança AEC
Interface web própria — um único comando sobe tudo.

Uso:
    python playground.py
    Abre http://localhost:7777 no navegador automaticamente.

4 verificações com IFC nativo (sem pset customizado):
  A — Clashes: todas disciplinas × estrutura + entre si
  B — Rota de fuga: porta normal × porta corta-fogo (PredefinedType nativo)
  C — Sistema de incêndio: extintores + sprinklers (IfcFireSuppressionTerminal)
  D — Análise completa
"""

import os
import sys
import json
import webbrowser
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(str(Path(__file__).parent / "skills/seguranca-aec/scripts"))

from detectar_clashes import detectar_clashes
from verificar_rota_fuga import verificar_rota_fuga
from verificar_sistema_incendio import verificar_sistema_incendio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

agente_global = None
ifc_path_global = "modelo_exemplo.ifc"

# ---------------------------------------------------------------------------
# Interface HTML
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agente de Coordenação e Segurança AEC</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Geist', 'Segoe UI', sans-serif; background: #09090b; color: #fafafa; min-height: 100vh; display: flex; }

  /* Sidebar */
  .sidebar {
    width: 260px; min-height: 100vh; background: #09090b;
    border-right: 1px solid #1f1f1f; display: flex; flex-direction: column;
    padding: 16px 12px; flex-shrink: 0;
  }
  .sidebar-logo {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 8px 20px; border-bottom: 1px solid #1f1f1f; margin-bottom: 16px;
  }
  .logo-icon {
    width: 32px; height: 32px; background: #f97316;
    border-radius: 8px; display: flex; align-items: center; justify-content: center;
    font-size: 16px; font-weight: 700; color: #09090b;
  }
  .logo-text { font-size: 15px; font-weight: 600; color: #fafafa; }
  .logo-sub { font-size: 11px; color: #71717a; }
  .sidebar-section { margin-bottom: 24px; }
  .sidebar-label { font-size: 11px; font-weight: 600; color: #52525b; text-transform: uppercase; letter-spacing: 0.8px; padding: 0 8px; margin-bottom: 8px; }
  .sidebar-item {
    display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 8px;
    font-size: 13px; color: #a1a1aa; cursor: default;
  }
  .sidebar-item.active { background: #1c1c1e; color: #fafafa; }
  .sidebar-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; flex-shrink: 0; }
  .sidebar-dot.orange { background: #f97316; }
  .sidebar-tag {
    margin-left: auto; font-size: 10px; background: #1c1c1e;
    border: 1px solid #2a2a2a; padding: 2px 6px; border-radius: 4px; color: #71717a;
  }
  .new-chat-btn {
    margin-top: auto; width: 100%; background: #1c1c1e; border: 1px solid #2a2a2a;
    border-radius: 8px; padding: 10px; color: #a1a1aa; font-size: 13px;
    cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;
    font-family: inherit; transition: all 0.15s;
  }
  .new-chat-btn:hover { background: #2a2a2a; color: #fafafa; }

  /* Main area */
  .main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }

  /* Setup screen */
  .setup-area {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 40px 24px;
  }
  .setup-card {
    width: 100%; max-width: 560px;
    background: #0f0f10; border: 1px solid #1f1f1f; border-radius: 16px; padding: 40px;
  }
  .agent-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: #1c1c1e; border: 1px solid #2a2a2a; border-radius: 20px;
    padding: 6px 14px; margin-bottom: 24px; font-size: 13px; color: #a1a1aa;
  }
  .setup-title { font-size: 26px; font-weight: 600; color: #fafafa; margin-bottom: 6px; }
  .setup-subtitle { font-size: 14px; color: #71717a; margin-bottom: 32px; line-height: 1.6; }
  .setup-subtitle strong { color: #f97316; }
  .field { margin-bottom: 20px; }
  .field label { display: block; font-size: 12px; font-weight: 500; color: #71717a; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px; }
  .field input {
    width: 100%; background: #09090b; border: 1px solid #2a2a2a; border-radius: 10px;
    padding: 12px 14px; color: #fafafa; font-size: 14px; font-family: inherit;
    transition: border-color 0.15s; outline: none;
  }
  .field input:focus { border-color: #f97316; }
  .field input::placeholder { color: #3f3f46; }
  .field .hint { font-size: 13px; color: #71717a; margin-top: 8px; line-height: 1.6; }
  .field .hint strong { color: #a1a1aa; }
  .btn-start {
    width: 100%; background: #f97316; color: #09090b; border: none; border-radius: 10px;
    padding: 14px; font-size: 15px; font-weight: 600; cursor: pointer; font-family: inherit;
    transition: background 0.15s; margin-top: 8px;
  }
  .btn-start:hover { background: #ea6c0a; }
  .btn-start:disabled { background: #1c1c1e; color: #3f3f46; cursor: not-allowed; }
  .error-box {
    background: #1a0a0a; border: 1px solid #7f1d1d; border-radius: 8px;
    padding: 12px 14px; color: #fca5a5; font-size: 13px; margin-top: 16px; display: none;
  }

  /* Chat screen */
  .chat-area { flex: 1; display: none; flex-direction: column; }
  .chat-header {
    padding: 16px 24px; border-bottom: 1px solid #1f1f1f;
    display: flex; align-items: center; justify-content: space-between;
  }
  .chat-header-info { display: flex; align-items: center; gap: 10px; }
  .chat-header-name { font-size: 15px; font-weight: 600; }
  .chat-header-model { font-size: 12px; color: #52525b; background: #1c1c1e; padding: 3px 8px; border-radius: 6px; }
  .reset-link { font-size: 13px; color: #52525b; cursor: pointer; background: none; border: none; font-family: inherit; }
  .reset-link:hover { color: #a1a1aa; }

  /* Empty state with starters */
  .chat-empty {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 40px 24px;
  }
  .chat-empty-icon { font-size: 48px; margin-bottom: 16px; }
  .chat-empty-title { font-size: 22px; font-weight: 600; margin-bottom: 8px; }
  .chat-empty-sub { font-size: 14px; color: #71717a; margin-bottom: 40px; text-align: center; max-width: 400px; line-height: 1.6; }
  .starters { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; width: 100%; max-width: 640px; }
  .starter-btn {
    background: #0f0f10; border: 1px solid #1f1f1f; border-radius: 12px;
    padding: 16px 18px; cursor: pointer; text-align: left; transition: all 0.15s;
    font-family: inherit;
  }
  .starter-btn:hover { border-color: #f97316; background: #1a0f05; }
  .starter-letter {
    display: inline-block; background: #f9731622; border: 1px solid #f97316;
    color: #f97316; width: 26px; height: 26px; border-radius: 6px;
    text-align: center; line-height: 26px; font-weight: 700; font-size: 13px;
    margin-bottom: 10px;
  }
  .starter-title { font-size: 14px; font-weight: 600; color: #fafafa; margin-bottom: 4px; }
  .starter-desc { font-size: 12px; color: #71717a; line-height: 1.5; }
  .starter-full { grid-column: 1 / -1; background: #0a150a; border-color: #166534; }
  .starter-full:hover { border-color: #22c55e; background: #0d1a0d; }
  .starter-full .starter-letter { background: #22c55e22; border-color: #22c55e; color: #22c55e; }

  /* Messages */
  .messages-area { flex: 1; overflow-y: auto; padding: 24px; display: none; }
  .messages-area.visible { display: block; }
  .msg { margin-bottom: 24px; display: flex; gap: 12px; }
  .msg-user { flex-direction: row-reverse; }
  .msg-avatar {
    width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600;
  }
  .msg-avatar.user { background: #f97316; color: #09090b; }
  .msg-avatar.agent { background: #1c1c1e; border: 1px solid #2a2a2a; }
  .msg-bubble { max-width: 80%; }
  .msg-user .msg-bubble { background: #1c1c1e; border-radius: 12px 2px 12px 12px; padding: 12px 16px; font-size: 14px; }
  .msg-agent-content { font-size: 14px; line-height: 1.7; color: #d4d4d8; }
  .msg-agent-content h1, .msg-agent-content h2, .msg-agent-content h3 { color: #fafafa; margin: 16px 0 8px; }
  .msg-agent-content h2 { color: #f97316; font-size: 16px; }
  .msg-agent-content h3 { color: #60a5fa; font-size: 14px; }
  .msg-agent-content p { margin: 8px 0; }
  .msg-agent-content table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  .msg-agent-content th { background: #1c1c1e; padding: 8px 12px; text-align: left; color: #71717a; font-size: 11px; text-transform: uppercase; border: 1px solid #2a2a2a; }
  .msg-agent-content td { padding: 8px 12px; border: 1px solid #1f1f1f; }
  .msg-agent-content tr:nth-child(even) td { background: #0f0f10; }
  .msg-agent-content strong { color: #fafafa; }
  .msg-agent-content ul, .msg-agent-content ol { padding-left: 20px; margin: 8px 0; }
  .msg-agent-content li { margin: 4px 0; }

  /* Input bar */
  .input-bar {
    padding: 16px 24px; border-top: 1px solid #1f1f1f;
    display: none; align-items: flex-end; gap: 10px;
  }
  .input-bar.visible { display: flex; }
  .input-wrap { flex: 1; background: #0f0f10; border: 1px solid #2a2a2a; border-radius: 12px; padding: 12px 14px; }
  .input-wrap textarea {
    width: 100%; background: none; border: none; color: #fafafa; font-size: 14px;
    font-family: inherit; resize: none; outline: none; line-height: 1.5; min-height: 24px; max-height: 120px;
  }
  .input-wrap textarea::placeholder { color: #3f3f46; }
  .send-btn {
    width: 40px; height: 40px; background: #f97316; border: none; border-radius: 10px;
    cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    transition: background 0.15s;
  }
  .send-btn:hover { background: #ea6c0a; }
  .send-btn:disabled { background: #1c1c1e; cursor: not-allowed; }
  .send-btn svg { width: 16px; height: 16px; fill: #09090b; }

  /* Loading */
  .typing { display: flex; gap: 4px; align-items: center; padding: 8px 0; }
  .typing-dot { width: 6px; height: 6px; border-radius: 50%; background: #71717a; animation: bounce 1.2s infinite; }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce { 0%,60%,100% { transform: translateY(0); } 30% { transform: translateY(-6px); } }
</style>
</head>
<body>

<!-- SIDEBAR -->
<div class="sidebar">
  <div class="sidebar-logo">
    <div class="logo-icon">🏗</div>
    <div>
      <div class="logo-text">Agno</div>
      <div class="logo-sub">AgentOS</div>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label">Agente</div>
    <div class="sidebar-item active">
      <div class="sidebar-dot"></div>
      Coordenação AEC
      <span class="sidebar-tag">ativo</span>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label">Modelo</div>
    <div class="sidebar-item">
      <div class="sidebar-dot orange"></div>
      claude-sonnet-4-6
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label">Framework</div>
    <div class="sidebar-item" style="flex-direction:column;align-items:flex-start;gap:4px;">
      <span style="color:#a1a1aa;font-size:12px;">🤖 Agno</span>
      <span style="color:#a1a1aa;font-size:12px;">🧠 Claude (Anthropic)</span>
      <span style="color:#a1a1aa;font-size:12px;">📐 ifcopenshell</span>
    </div>
  </div>

  <button class="new-chat-btn" onclick="novoChat()">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
    Novo chat
  </button>
</div>

<!-- MAIN -->
<div class="main">

  <!-- SETUP SCREEN -->
  <div class="setup-area" id="setupArea">
    <div class="setup-card">
      <div class="agent-badge">
        <span>🏗</span>
        <span>Agente de Coordenação e Segurança AEC</span>
      </div>
      <div class="setup-title">Configuração inicial</div>
      <div class="setup-subtitle">
        Agente construído com <strong>Agno</strong> + <strong>Claude</strong> + <strong>ifcopenshell</strong>.<br>
        Informe sua chave da Anthropic e o arquivo IFC do projeto para começar.
      </div>

      <div class="field">
        <label>Chave Anthropic API Key</label>
        <input type="password" id="apiKey" placeholder="sk-ant-..." />
        <div class="hint">Obtenha em <strong>console.anthropic.com</strong> → API Keys</div>
      </div>

      <div class="field">
        <label>Arquivo IFC do projeto</label>
        <input type="text" id="ifcPath" placeholder="modelo_exemplo.ifc" />
        <div class="hint">Deixe em branco para usar o modelo de exemplo incluído sem carregar outro arquivo. Para usar seu próprio projeto, informe o caminho completo do arquivo .ifc exportado do Revit, ArchiCAD ou Bonsai.</div>
      </div>

      <button class="btn-start" id="btnSetup" onclick="setup()">Iniciar agente →</button>
      <div class="error-box" id="setupError"></div>
    </div>
  </div>

  <!-- CHAT SCREEN -->
  <div class="chat-area" id="chatArea">
    <div class="chat-header">
      <div class="chat-header-info">
        <div style="width:32px;height:32px;background:#f97316;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;">🏗</div>
        <div>
          <div class="chat-header-name">Agente de Coordenação e Segurança AEC</div>
          <div style="font-size:12px;color:#52525b;" id="ifcLabel">modelo_exemplo.ifc</div>
        </div>
        <span class="chat-header-model">claude-sonnet-4-6</span>
      </div>
      <button class="reset-link" onclick="resetar()">⚙ Reconfigurar</button>
      <div style="display:flex;gap:8px;">
        <button onclick="abrirViewer()" style="font-size:13px;color:#60a5fa;background:#0a1628;border:1px solid #1d4ed8;border-radius:6px;padding:6px 14px;cursor:pointer;font-family:inherit;">
          🔍 Ver em 3D
        </button>
        <a href="/api/download-ifc-auditado"
           style="font-size:13px;color:#f97316;text-decoration:none;background:#1a0f05;border:1px solid #f97316;border-radius:6px;padding:6px 14px;cursor:pointer;"
           download>
          ⬇ Baixar IFC auditado
        </a>
      </div>
    </div>

    <!-- Empty state -->
    <div class="chat-empty" id="chatEmpty">
      <div class="chat-empty-icon">🏗</div>
      <div class="chat-empty-title">O que deseja verificar?</div>
      <div class="chat-empty-sub">Selecione uma verificação abaixo ou digite sua pergunta.</div>
      <div class="starters">
        <div class="starter-btn" onclick="enviarStarter('a')">
          <div class="starter-letter">A</div>
          <div class="starter-title">Clashes Geométricos</div>
          <div class="starter-desc">Interferências 3D reais entre todas as disciplinas de instalações e estrutura</div>
        </div>
        <div class="starter-btn" onclick="enviarStarter('b')">
          <div class="starter-letter">B</div>
          <div class="starter-title">Rota de Fuga</div>
          <div class="starter-desc">Distância entre portas de apartamento e porta corta-fogo da escada (NBR 9077)</div>
        </div>
        <div class="starter-btn" onclick="enviarStarter('c')">
          <div class="starter-letter">C</div>
          <div class="starter-title">Sistema de Incêndio</div>
          <div class="starter-desc">Cobertura de extintores e sprinklers (NBR 12693 / NBR 10897)</div>
        </div>
        <div class="starter-btn starter-full" onclick="enviarStarter('d')">
          <div class="starter-letter">D</div>
          <div class="starter-title">Análise Completa — todas as verificações</div>
          <div class="starter-desc">Executa as três verificações em sequência com relatório completo e resumo executivo</div>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div class="messages-area" id="messagesArea"></div>

    <!-- Input -->
    <div class="input-bar" id="inputBar">
      <div class="input-wrap">
        <textarea id="msgInput" placeholder="Pergunte algo sobre o modelo IFC..." rows="1"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();enviar()}"
          oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
      </div>
      <button class="send-btn" id="sendBtn" onclick="enviar()">
        <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
      </button>
    </div>
  </div>

</div>

<script>
const MENSAGENS = {
  a: 'Detecte todos os clashes geométricos no modelo IFC. Apresente separado por tipo: estrutura × instalação e instalação × instalação entre disciplinas diferentes.',
  b: 'Verifique a rota de fuga. Calcule a distância de cada porta de apartamento até a porta corta-fogo da escada e compare com o limite da NBR 9077.',
  c: 'Verifique o sistema de incêndio. Analise a cobertura de extintores (NBR 12693) e sprinklers (NBR 10897) em relação às portas do pavimento.',
  d: 'Faça uma auditoria completa. Execute as TRÊS verificações: clashes geométricos, rota de fuga e sistema de incêndio. Apresente relatório completo com tabelas e resumo executivo.'
};

let temMensagens = false;

function mostrarChat() {
  document.getElementById('setupArea').style.display = 'none';
  document.getElementById('chatArea').style.display = 'flex';
  document.getElementById('inputBar').classList.add('visible');
}

async function setup() {
  const apiKey = document.getElementById('apiKey').value.trim();
  const ifcPath = document.getElementById('ifcPath').value.trim() || 'modelo_exemplo.ifc';
  const btn = document.getElementById('btnSetup');
  const erro = document.getElementById('setupError');
  if (!apiKey) { erro.textContent = 'Informe sua chave Anthropic API Key.'; erro.style.display = 'block'; return; }
  btn.disabled = true; btn.textContent = 'Iniciando agente...'; erro.style.display = 'none';
  try {
    const res = await fetch('/api/setup', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({api_key: apiKey, ifc_path: ifcPath}) });
    const data = await res.json();
    if (data.erro) { erro.textContent = data.erro; erro.style.display = 'block'; btn.disabled = false; btn.textContent = 'Iniciar agente →'; return; }
    document.getElementById('ifcLabel').textContent = data.ifc;
    mostrarChat();
  } catch(e) { erro.textContent = 'Erro ao conectar com o backend.'; erro.style.display = 'block'; btn.disabled = false; btn.textContent = 'Iniciar agente →'; }
}

function adicionarMensagem(texto, tipo) {
  if (!temMensagens) {
    document.getElementById('chatEmpty').style.display = 'none';
    document.getElementById('messagesArea').classList.add('visible');
    temMensagens = true;
  }
  const area = document.getElementById('messagesArea');
  const div = document.createElement('div');
  div.className = 'msg ' + (tipo === 'user' ? 'msg-user' : '');
  if (tipo === 'user') {
    div.innerHTML = `<div class="msg-avatar user">S</div><div class="msg-bubble"><div style="font-size:14px;color:#fafafa">${texto}</div></div>`;
  } else if (tipo === 'loading') {
    div.id = 'loadingMsg';
    div.innerHTML = `<div class="msg-avatar agent">🏗</div><div class="typing"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
  } else {
    div.innerHTML = `<div class="msg-avatar agent">🏗</div><div class="msg-bubble"><div class="msg-agent-content">${marked.parse(texto)}</div></div>`;
  }
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return div;
}

async function enviarStarter(tipo) {
  const labels = {a:'Clashes Geométricos', b:'Rota de Fuga (NBR 9077)', c:'Sistema de Incêndio', d:'Análise Completa'};
  adicionarMensagem(labels[tipo], 'user');
  adicionarMensagem('', 'loading');
  document.getElementById('sendBtn').disabled = true;
  try {
    const res = await fetch('/api/verificar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tipo})});
    const data = await res.json();
    document.getElementById('loadingMsg')?.remove();
    adicionarMensagem(data.erro || data.resultado || 'Sem resultado.', 'agent');
  } catch(e) {
    document.getElementById('loadingMsg')?.remove();
    adicionarMensagem('Erro ao obter resultado.', 'agent');
  }
  document.getElementById('sendBtn').disabled = false;
}

async function enviar() {
  const input = document.getElementById('msgInput');
  const texto = input.value.trim();
  if (!texto) return;
  input.value = ''; input.style.height = 'auto';
  adicionarMensagem(texto, 'user');
  adicionarMensagem('', 'loading');
  document.getElementById('sendBtn').disabled = true;
  try {
    const res = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mensagem: texto})});
    const data = await res.json();
    document.getElementById('loadingMsg')?.remove();
    adicionarMensagem(data.erro || data.resultado || 'Sem resultado.', 'agent');
  } catch(e) {
    document.getElementById('loadingMsg')?.remove();
    adicionarMensagem('Erro ao obter resultado.', 'agent');
  }
  document.getElementById('sendBtn').disabled = false;
}

function novoChat() {
  if (!document.getElementById('chatArea').style.display || document.getElementById('chatArea').style.display === 'none') return;
  temMensagens = false;
  document.getElementById('messagesArea').innerHTML = '';
  document.getElementById('messagesArea').classList.remove('visible');
  document.getElementById('chatEmpty').style.display = 'flex';
}

function resetar() {
  document.getElementById('setupArea').style.display = 'flex';
  document.getElementById('chatArea').style.display = 'none';
  novoChat();
}
</script>
<!-- VIEWER 3D MODAL -->
<div id="viewerModal" style="display:none;position:fixed;inset:0;background:#000000cc;z-index:1000;align-items:center;justify-content:center;">
  <div style="background:#09090b;border:1px solid #1f1f1f;border-radius:16px;width:90vw;max-width:1000px;height:80vh;display:flex;flex-direction:column;overflow:hidden;">
    <div style="padding:16px 24px;border-bottom:1px solid #1f1f1f;display:flex;align-items:center;justify-content:space-between;">
      <div>
        <div style="font-size:15px;font-weight:600;">Visualizador 3D — Auditoria BIM</div>
        <div style="font-size:12px;color:#52525b;margin-top:2px;">
          <span style="color:#f59e0b">■</span> Clash &nbsp;
          <span style="color:#ef4444">■</span> Não conforme &nbsp;
          <span style="color:#6b7280">■</span> Conforme
        </div>
      </div>
      <button onclick="fecharViewer()" style="background:none;border:none;color:#71717a;font-size:20px;cursor:pointer;padding:4px;">✕</button>
    </div>
    <div style="flex:1;position:relative;">
      <canvas id="viewerCanvas" style="width:100%;height:100%;display:block;"></canvas>
      <div id="viewerLoading" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:#09090b;flex-direction:column;gap:12px;">
        <div class="spinner"></div>
        <div style="font-size:13px;color:#71717a;">Carregando geometria do IFC...</div>
      </div>
      <div id="viewerTooltip" style="position:absolute;top:12px;left:12px;background:#0f0f10;border:1px solid #2a2a2a;border-radius:8px;padding:8px 12px;font-size:12px;display:none;max-width:200px;"></div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
// ---- Visualizador 3D ----
let viewerScene, viewerCamera, viewerRenderer, viewerAnimId;
let viewerIsDragging = false, viewerLastMouse = {x:0, y:0};
let viewerSpherical = {theta: Math.PI/4, phi: Math.PI/3, radius: 15};
let viewerTarget = {x:0, y:0, z:0};

function abrirViewer() {
  document.getElementById('viewerModal').style.display = 'flex';
  document.getElementById('viewerLoading').style.display = 'flex';
  iniciarViewer();
}

function fecharViewer() {
  document.getElementById('viewerModal').style.display = 'none';
  if (viewerAnimId) cancelAnimationFrame(viewerAnimId);
  if (viewerRenderer) { viewerRenderer.dispose(); viewerRenderer = null; }
}

async function iniciarViewer() {
  try {
    const res = await fetch('/api/viewer-data');
    const data = await res.json();
    if (data.erro) { alert(data.erro); return; }

    const canvas = document.getElementById('viewerCanvas');
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w; canvas.height = h;

    if (viewerRenderer) viewerRenderer.dispose();
    viewerScene = new THREE.Scene();
    viewerScene.background = new THREE.Color(0x09090b);

    viewerCamera = new THREE.PerspectiveCamera(45, w/h, 0.01, 1000);

    viewerRenderer = new THREE.WebGLRenderer({canvas, antialias: true});
    viewerRenderer.setSize(w, h);
    viewerRenderer.setPixelRatio(window.devicePixelRatio);

    // Grid
    const grid = new THREE.GridHelper(20, 20, 0x1f1f1f, 0x1f1f1f);
    viewerScene.add(grid);

    // Luz
    viewerScene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(5, 10, 5);
    viewerScene.add(dir);

    // Centro dos elementos
    let cx=0, cy=0, cz=0, n=0;
    data.elementos.forEach(el => {
      cx += (el.bbox.xmin+el.bbox.xmax)/2;
      cy += (el.bbox.ymin+el.bbox.ymax)/2;
      cz += (el.bbox.zmin+el.bbox.zmax)/2;
      n++;
    });
    if (n > 0) { viewerTarget = {x:cx/n, y:cz/n, z:cy/n}; }

    // Elementos como boxes
    data.elementos.forEach(el => {
      const b = el.bbox;
      const dx = Math.max(b.xmax-b.xmin, 0.05);
      const dy = Math.max(b.zmax-b.zmin, 0.05);
      const dz = Math.max(b.ymax-b.ymin, 0.05);
      const geo = new THREE.BoxGeometry(dx, dy, dz);
      const mat = new THREE.MeshLambertMaterial({
        color: new THREE.Color(el.cor),
        transparent: el.status === 'OK',
        opacity: el.status === 'OK' ? 0.6 : 0.9,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(
        (b.xmin+b.xmax)/2 - viewerTarget.x,
        (b.zmin+b.zmax)/2 - viewerTarget.y,
        (b.ymin+b.ymax)/2 - viewerTarget.z
      );
      mesh.userData = {nome: el.nome, tipo: el.tipo, status: el.status};
      viewerScene.add(mesh);

      // Wireframe para elementos com problema
      if (el.status !== 'OK') {
        const wf = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({color: el.cor, linewidth: 2})
        );
        wf.position.copy(mesh.position);
        viewerScene.add(wf);
      }
    });

    document.getElementById('viewerLoading').style.display = 'none';
    atualizarCamera();
    animar();
    adicionarControles(canvas);

  } catch(e) {
    document.getElementById('viewerLoading').innerHTML = `<div style="color:#f85149">Erro: ${e.message}</div>`;
  }
}

function atualizarCamera() {
  const {theta, phi, radius} = viewerSpherical;
  viewerCamera.position.set(
    radius * Math.sin(phi) * Math.cos(theta) + viewerTarget.x,
    radius * Math.cos(phi) + viewerTarget.y,
    radius * Math.sin(phi) * Math.sin(theta) + viewerTarget.z
  );
  viewerCamera.lookAt(viewerTarget.x, viewerTarget.y, viewerTarget.z);
}

function animar() {
  viewerAnimId = requestAnimationFrame(animar);
  viewerRenderer.render(viewerScene, viewerCamera);
}

function adicionarControles(canvas) {
  canvas.addEventListener('mousedown', e => { viewerIsDragging=true; viewerLastMouse={x:e.clientX,y:e.clientY}; });
  canvas.addEventListener('mouseup', () => { viewerIsDragging=false; });
  canvas.addEventListener('mousemove', e => {
    if (!viewerIsDragging) return;
    const dx = e.clientX - viewerLastMouse.x;
    const dy = e.clientY - viewerLastMouse.y;
    viewerSpherical.theta -= dx * 0.01;
    viewerSpherical.phi = Math.max(0.1, Math.min(Math.PI-0.1, viewerSpherical.phi - dy * 0.01));
    viewerLastMouse = {x:e.clientX, y:e.clientY};
    atualizarCamera();
  });
  canvas.addEventListener('wheel', e => {
    viewerSpherical.radius = Math.max(1, viewerSpherical.radius + e.deltaY * 0.01);
    atualizarCamera();
  });
}
</script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=HTML)


@app.post("/api/setup")
async def api_setup(request: Request):
    global agente_global, ifc_path_global
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    ifc = data.get("ifc_path", "modelo_exemplo.ifc").strip() or "modelo_exemplo.ifc"

    if not api_key:
        return JSONResponse({"erro": "Chave não informada."}, status_code=400)
    if not Path(ifc).exists():
        return JSONResponse({"erro": f"Arquivo IFC não encontrado: {ifc}"}, status_code=400)

    os.environ["ANTHROPIC_API_KEY"] = api_key
    ifc_path_global = ifc

    from agno.agent import Agent
    from agno.models.anthropic import Claude
    from agno.skills import Skills, LocalSkills

    agente_global = Agent(
        id="AgenteCoordenacaoSeguranca",
        name="Agente de Coordenação e Segurança AEC",
        model=Claude(id="claude-sonnet-4-6"),
        skills=Skills(loaders=[LocalSkills(str(Path(__file__).parent / "skills"))]),
        tools=[
            detectar_clashes_instalacoes_estrutura,
            verificar_distancia_rota_fuga,
            verificar_sistema_incendio_completo,
        ],
        instructions=[
            "Você é um assistente técnico de arquitetura especializado em "
            "compatibilização de projetos e segurança contra incêndio.",
            "Use a skill 'seguranca-aec' como referência normativa.",
            f"O arquivo IFC do projeto está em: {ifc}",
            f"Use sempre o arquivo '{ifc}' nas tools.",
            "Para clashes use 'detectar_clashes_instalacoes_estrutura'.",
            "Para rota de fuga use 'verificar_distancia_rota_fuga'.",
            "Para extintores e sprinklers use 'verificar_sistema_incendio_completo'.",
            "Na análise completa execute as TRÊS verificações em sequência.",
            "Apresente resultados com tabelas markdown, conformes e não conformes separados.",
            "Responda em português, de forma técnica e objetiva.",
        ],
        markdown=True,
        debug_mode=False,
    )

    with open(Path(__file__).parent / ".env", "w") as f:
        f.write(f"ANTHROPIC_API_KEY={api_key}\nIFC_PATH={ifc}\n")

    return JSONResponse({"status": "ok", "ifc": ifc})


@app.post("/api/verificar")
async def api_verificar(request: Request):
    global agente_global, ifc_path_global
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)

    data = await request.json()
    tipo = data.get("tipo", "d")

    mensagens = {
        "a": f"Detecte todos os clashes geométricos no arquivo {ifc_path_global}. Apresente separado por tipo: estrutura x instalação e instalação x instalação entre disciplinas diferentes.",
        "b": f"Verifique a rota de fuga no arquivo {ifc_path_global}. Calcule a distância de cada porta até a porta corta-fogo da escada e compare com o limite da NBR 9077.",
        "c": f"Verifique o sistema de incêndio no arquivo {ifc_path_global}. Analise a cobertura de extintores (NBR 12693) e sprinklers (NBR 10897) em relação às portas do pavimento.",
        "d": f"Faça uma auditoria completa do arquivo {ifc_path_global}. Execute as TRÊS verificações: clashes geométricos, rota de fuga e sistema de incêndio (extintores + sprinklers). Apresente relatório completo com tabelas e resumo executivo.",
    }

    try:
        response = agente_global.run(mensagens.get(tipo, mensagens["d"]))
        resultado = response.get_content_as_string() if hasattr(response, 'get_content_as_string') else str(response.content)
        return JSONResponse({"resultado": resultado})
    except Exception as e:
        return JSONResponse({"erro": f"Erro: {str(e)}"}, status_code=500)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def detectar_clashes_instalacoes_estrutura(caminho_ifc: str) -> str:
    """Detecta clashes geométricos reais (bounding box 3D) entre todas as
    disciplinas de instalações entre si e com a estrutura.
    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    clashes = detectar_clashes(caminho_ifc)
    if not clashes:
        return "Nenhum clash encontrado."
    linhas = []
    for c in clashes:
        a, b = c["elemento_a"], c["elemento_b"]
        rotulo = "ESTRUTURA x INSTALAÇÃO" if c["tipo"] == "instalacao_x_estrutura" else "INSTALAÇÃO x INSTALAÇÃO"
        linhas.append(f"[{rotulo}] {a['disciplina']} '{a['nome']}' x {b['disciplina']} '{b['nome']}'")
    return f"{len(clashes)} clash(es):\n" + "\n".join(linhas)


def verificar_distancia_rota_fuga(caminho_ifc: str) -> str:
    """Verifica distância real entre portas de apartamento e porta corta-fogo
    da escada de incêndio, usando PredefinedType nativo do IFC (NBR 9077).
    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_rota_fuga(caminho_ifc)
    if resultados and "erro" in resultados[0]:
        return resultados[0]["erro"]
    return "\n".join([
        f"[{'CONFORME' if r['conforme'] else 'NÃO CONFORME'}] {r['porta_apartamento']} → {r['porta_escada_mais_proxima']}: {r['distancia_m']} m (limite: {r['limite_m']} m)"
        for r in resultados
    ])


def verificar_sistema_incendio_completo(caminho_ifc: str) -> str:
    """Verifica cobertura de extintores e sprinklers usando IfcFireSuppressionTerminal
    nativo do IFC, calculando distância até as portas do pavimento.
    Args:
        caminho_ifc: caminho para o arquivo .ifc.
    """
    resultados = verificar_sistema_incendio(caminho_ifc)
    if resultados and "erro" in resultados[0]:
        return resultados[0]["erro"]
    return "\n".join([
        f"[{r.get('categoria','')}] [{('CONFORME' if r.get('conforme') else 'NÃO CONFORME')}] {r.get('motivo','')}"
        for r in resultados
    ])


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    def abrir_navegador():
        time.sleep(2)
        webbrowser.open("http://localhost:7777")

    print("\n" + "=" * 55)
    print("  AGENTE DE COORDENAÇÃO E SEGURANÇA AEC")
    print("  Agno + Claude (Anthropic) + ifcopenshell")
    print("=" * 55)
    print("\n  Acesse: http://localhost:7777")
    print("  Abrindo navegador automaticamente...\n")

    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="localhost", port=7777)


@app.post("/api/chat")
async def api_chat(request: Request):
    global agente_global, ifc_path_global
    if agente_global is None:
        return JSONResponse({"erro": "Agente não inicializado."}, status_code=400)
    data = await request.json()
    mensagem = data.get("mensagem", "").strip()
    if not mensagem:
        return JSONResponse({"erro": "Mensagem vazia."}, status_code=400)
    try:
        response = agente_global.run(mensagem)
        resultado = response.get_content_as_string() if hasattr(response, "get_content_as_string") else str(response.content)
        return JSONResponse({"resultado": resultado})
    except Exception as e:
        return JSONResponse({"erro": f"Erro: {str(e)}"}, status_code=500)


@app.get("/api/viewer-data")
async def viewer_data():
    """Retorna geometria e cores de auditoria para o visualizador 3D."""
    if not ifc_path_global or not Path(ifc_path_global).exists():
        return JSONResponse({"erro": "Arquivo IFC não encontrado."}, status_code=400)
    try:
        import ifcopenshell.geom
        import ifcopenshell.util.unit as ifc_unit
        from detectar_clashes import detectar_clashes
        from verificar_rota_fuga import verificar_rota_fuga
        from verificar_sistema_incendio import verificar_sistema_incendio

        model = ifcopenshell.open(ifc_path_global)
        escala = ifc_unit.calculate_unit_scale(model)
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)

        # Identifica elementos com problema
        clash_nomes = set()
        nc_nomes = set()

        try:
            for c in detectar_clashes(ifc_path_global):
                clash_nomes.add(c["elemento_a"]["nome"])
                clash_nomes.add(c["elemento_b"]["nome"])
        except: pass

        try:
            for r in verificar_rota_fuga(ifc_path_global):
                if not r.get("conforme") and "porta_apartamento" in r:
                    nc_nomes.add(r["porta_apartamento"])
        except: pass

        try:
            for r in verificar_sistema_incendio(ifc_path_global):
                if not r.get("conforme"):
                    porta = r.get("porta") or r.get("porta_apartamento")
                    if porta: nc_nomes.add(porta)
        except: pass

        elementos = []
        for el in model.by_type("IfcProduct"):
            if not el.Representation:
                continue
            try:
                shape = ifcopenshell.geom.create_shape(settings, el)
                v = shape.geometry.verts
                xs, ys, zs = v[0::3], v[1::3], v[2::3]
                nome = el.Name or el.is_a()
                if nome in clash_nomes:
                    cor = "#f59e0b"  # amarelo
                    status = "CLASH"
                elif nome in nc_nomes:
                    cor = "#ef4444"  # vermelho
                    status = "NÃO CONFORME"
                else:
                    cor = "#6b7280"  # cinza
                    status = "OK"
                elementos.append({
                    "nome": nome,
                    "tipo": el.is_a(),
                    "cor": cor,
                    "status": status,
                    "bbox": {
                        "xmin": min(xs), "xmax": max(xs),
                        "ymin": min(ys), "ymax": max(ys),
                        "zmin": min(zs), "zmax": max(zs),
                    }
                })
            except:
                continue

        return JSONResponse({"elementos": elementos, "total": len(elementos)})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)



async def download_ifc_auditado():
    """Gera o IFC auditado com cores (clash=amarelo, não conforme=vermelho) e serve para download."""
    if not ifc_path_global or not Path(ifc_path_global).exists():
        return JSONResponse({"erro": "Arquivo IFC não encontrado."}, status_code=400)
    try:
        from colorir_auditoria_ifc import colorir_auditoria
        saida = Path(ifc_path_global).stem + "_auditado.ifc"
        contagem = colorir_auditoria(ifc_path_global, saida)
        return FileResponse(
            path=saida,
            filename=saida,
            media_type="application/octet-stream",
            headers={"X-Clash": str(contagem["clash"]), "X-NaoConforme": str(contagem["nao_conforme"])}
        )
    except Exception as e:
        return JSONResponse({"erro": f"Erro ao gerar IFC: {str(e)}"}, status_code=500)
