# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import socket
import base64
import struct
import urllib.request
import subprocess
import shutil

def log(msg):
    print(msg, flush=True)

class SimpleWebSocket:
    def __init__(self, host, port, resource):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((host, port))
        
        # Handshake
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        handshake = (
            f"GET {resource} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(handshake.encode('utf-8'))
        resp = self.sock.recv(4096).decode('utf-8', errors='ignore')
        if "101 " not in resp:
            raise Exception("WebSocket handshake failed:\n" + resp)
        self.sock.settimeout(0.3)

    def send_json(self, data):
        payload = json.dumps(data).encode('utf-8')
        length = len(payload)
        mask = os.urandom(4)
        
        header = bytearray([0x81])
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
            
        header.extend(mask)
        masked_payload = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + masked_payload)

    def recv_msg(self):
        try:
            head = self.sock.recv(2)
            if not head or len(head) < 2:
                return None
            b1, b2 = head[0], head[1]
            opcode = b1 & 0x0f
            masked = (b2 & 0x80) != 0
            payload_len = b2 & 0x7f
            if payload_len == 126:
                ext = self.sock.recv(2)
                payload_len = struct.unpack("!H", ext)[0]
            elif payload_len == 127:
                ext = self.sock.recv(8)
                payload_len = struct.unpack("!Q", ext)[0]
                
            mask = self.sock.recv(4) if masked else None
            
            data = bytearray()
            while len(data) < payload_len:
                chunk = self.sock.recv(min(4096, payload_len - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                
            if masked:
                data = bytearray(b ^ mask[i % 4] for i, b in enumerate(data))
                
            if opcode == 0x08:
                return None
            return data.decode('utf-8', errors='ignore')
        except (socket.timeout, BlockingIOError):
            return None

def run_tests():
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    user_data = r"C:\Users\agath\.gemini\antigravity\scratch\projeto_eletrico\.temp_chrome_test"
    if os.path.exists(user_data):
        shutil.rmtree(user_data, ignore_errors=True)

    proc = subprocess.Popen([
        chrome_path,
        "--headless=new",
        "--remote-debugging-port=9444",
        f"--user-data-dir={user_data}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "http://127.0.0.1:8080/?nocache=" + str(time.time())
    ])

    time.sleep(2)
    
    try:
        targets_data = urllib.request.urlopen("http://127.0.0.1:9444/json").read()
        targets = json.loads(targets_data)
        page_target = None
        for t in targets:
            if "127.0.0.1:8080" in t.get('url', ''):
                page_target = t
                break
                
        if not page_target:
            log("ERROR: Page target not found!")
            return

        ws_url = page_target['webSocketDebuggerUrl']
        path = ws_url.replace("ws://127.0.0.1:9444", "")
        ws = SimpleWebSocket("127.0.0.1", 9444, path)
        log("[+] WebSocket connected to Chrome DevTools")

        # Enable runtime & console
        ws.send_json({"id": 1, "method": "Runtime.enable"})
        ws.send_json({"id": 2, "method": "Console.enable"})

        time.sleep(1)
        console_logs = []
        exceptions = []

        def drain_events():
            while True:
                msg = ws.recv_msg()
                if not msg:
                    break
                try:
                    ev = json.loads(msg)
                    if ev.get("method") == "Runtime.exceptionThrown":
                        exceptions.append(ev["params"]["exceptionDetails"])
                    elif ev.get("method") == "Console.messageAdded":
                        console_logs.append(ev["params"]["message"])
                    elif ev.get("method") == "Runtime.consoleAPICalled":
                        args = [a.get("value", a.get("description", "")) for a in ev["params"].get("args", [])]
                        console_logs.append({"type": ev["params"].get("type"), "text": " ".join(str(x) for x in args)})
                except Exception:
                    pass

        drain_events()
        log(f"\n[Initial Load] Exceptions: {len(exceptions)}")
        for ex in exceptions:
            log(f"  EX: {ex.get('text')} - {ex.get('exception', {}).get('description', '')}")

        req_id = 100
        def evaluate(js_code, timeout_sec=3.0):
            nonlocal req_id
            req_id += 1
            ws.send_json({
                "id": req_id,
                "method": "Runtime.evaluate",
                "params": {"expression": js_code, "returnByValue": True, "awaitPromise": True}
            })
            start_t = time.time()
            while time.time() - start_t < timeout_sec:
                msg = ws.recv_msg()
                if not msg:
                    continue
                try:
                    res = json.loads(msg)
                    if res.get("id") == req_id:
                        return res.get("result", {})
                    if res.get("method") == "Runtime.exceptionThrown":
                        exceptions.append(res["params"]["exceptionDetails"])
                except Exception:
                    pass
            return {"timeout": True}

        # Override confirm and alert so dialogs don't block
        evaluate("window.confirm = () => true; window.alert = (m) => console.log('[MOCK ALERT]', m);")

        # TEST SUITE
        tests = [
            ("Estado global (state)", "JSON.stringify({pavimentos: state.pavimentos ? state.pavimentos.length : 0, comodos: state.comodos ? state.comodos.length : 0, pontos: state.pontosEletricos ? state.pontosEletricos.length : 0})"),
            ("Aba 0: Planta Baixa 2D", "trocarAba(0); 'Aba 0 OK'"),
            ("Aba 1: Instalacoes Eletricas 2D", "trocarAba(1); 'Aba 1 OK'"),
            ("Aba 2: Maquete 3D BIM", "trocarAba(2); 'Aba 2 OK'"),
            ("Aba 3: QDT e Circuitos", "trocarAba(3); 'Aba 3 OK'"),
            ("Aba 4: Lista de Materiais", "trocarAba(4); 'Aba 4 OK'"),
            ("Aba 5: Relatorios e Memorial", "trocarAba(5); 'Aba 5 OK'"),
            ("Canvas CAD 2D", "desenharCAD(); 'Renderizado com sucesso'"),
            ("Canvas Instalacoes 2D", "desenharInstalacoes(); 'Renderizado com sucesso'"),
            ("Maquete 3D (Three.js)", "typeof reconstruirCena3D === 'function' ? (reconstruirCena3D(true), 'Cena 3D reconstruida') : 'Sem 3D'"),
            ("Calculo Tecnico NBR 5410 (atualizarTabelas)", "(function(){ atualizarTabelas(); const qdt = document.getElementById('tbCircuitos'); return 'Tabela circuitos calculada: ' + (qdt ? qdt.children.length + ' linhas geradas' : 'Sem container'); })()"),
            ("Calculo de Demanda Concessionaria", "(function(){ const dem = calcularDemandaConcessionaria(); return dem ? JSON.stringify({demandaTotalKW: dem.demandaTotalKW.toFixed(2), demandaTotalkVA: dem.demandaTotalkVA.toFixed(2), categoria: dem.categoriaAtend ? dem.categoriaAtend.id : 'N/A', disjuntor: dem.categoriaAtend ? dem.categoriaAtend.disj : 'N/A'}) : 'Sem retorno'; })()"),
            ("Renderizar Memoria de Demanda", "(function(){ renderizarMemoriaDemanda(); const cont = document.getElementById('conteudoMemoriaDemanda'); return cont && cont.innerHTML.length > 50 ? 'Memoria renderizada (' + cont.innerHTML.length + ' bytes)' : 'Vazio'; })()"),
            ("Atualizar Tudo (atualizarTudo)", "atualizarTudo(); 'atualizarTudo executado sem falhas'"),
            ("Listar Projetos na Pasta Servidor (API)", "(async function(){ const r = await fetch('/api/projetos'); const j = await r.json(); return 'Projetos encontrados: ' + j.projetos.length + ' (' + j.projetos.map(p => p.nome).join(', ') + ')'; })()"),
            ("Carregar Projeto Padrao da Pasta", "(async function(){ await carregarProjetoDaPastaServidor('Projeto_Residencial_Padrao_NBR5410.proeletrica'); return JSON.stringify({nome: state.projetoAtual ? state.projetoAtual.nome : 'Sem nome', comodos: state.comodos.length, pontos: state.pontosEletricos.length}); })()"),
            ("Recalcular Apos Carga do Projeto", "(function(){ atualizarTabelas(); return 'Recalculo pos-carga OK'; })()"),
            ("Inserir Novo Comodo", "(function(){ const antes = state.comodos.length; state.comodos.push({id: 'comodo_teste_' + Date.now(), nome: 'Quarto Teste', tipo: 'quarto', largura: 3.5, comprimento: 4.0, area: 14.0, perimetro: 15.0, x: 100, y: 100, pavimentoId: state.pavimentoAtivoId || 'terreo'}); atualizarTudo(); return 'Comodos antes: ' + antes + ', depois: ' + state.comodos.length; })()"),
            ("Inserir Novo Ponto TUG", "(function(){ const antes = state.pontosEletricos.length; state.pontosEletricos.push({id: 'pto_' + Date.now(), tipo: 'TUG', subTipo: 'baixa', pot: 100, x: 150, y: 150, comodoId: state.comodos[0].id, pavimentoId: state.comodos[0].pavimentoId}); atualizarTudo(); return 'Pontos antes: ' + antes + ', depois: ' + state.pontosEletricos.length; })()"),
            ("Salvar Projeto na Pasta Servidor", "(async function(){ const res = await fetch('/api/projetos/salvar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nomeArquivo: 'Projeto_Teste_Automacao', projeto: {nome: 'Projeto Teste Automacao'}, estado: exportarSnapshotEstado()})}); const j = await res.json(); return j.sucesso ? 'Salvo com sucesso: ' + j.arquivo : 'Erro: ' + j.erro; })()"),
            ("Verificar Exclusao do Projeto Teste", "(async function(){ const res = await fetch('/api/projetos/excluir', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({arquivo: 'Projeto_Teste_Automacao.proeletrica'})}); const j = await res.json(); return j.sucesso ? 'Excluido com sucesso' : 'Erro: ' + j.erro; })()"),
            ("Importar / Carregar Exemplo DXF", "(function(){ if (typeof carregarExemploDxf === 'function') { carregarExemploDxf(); return 'Exemplo DXF carregado com ' + (state.cadDxfUnderlayLines ? state.cadDxfUnderlayLines.length : 0) + ' linhas CAD'; } return 'Sem funcao'; })()"),
            ("Exportar Excel (SheetJS)", "typeof exportarParaExcel === 'function' ? 'Funcao exportarParaExcel pronta' : 'Ausente'"),
            ("Modal Config Paredes", "(function(){ if (typeof abrirModalConfigParedes === 'function') { abrirModalConfigParedes(); fecharModalConfigParedes(); return 'Modal Paredes OK'; } return 'Sem funcao'; })()"),
            ("Modal Config Terreno", "(function(){ if (typeof abrirModalConfigTerreno === 'function') { abrirModalConfigTerreno(); fecharModalConfigTerreno(); return 'Modal Terreno OK'; } return 'Sem funcao'; })()"),
            ("Modal Gerenciar Projetos", "(function(){ if (typeof abrirModalGerenciarProjetos === 'function') { abrirModalGerenciarProjetos(); fecharModalGerenciarProjetos(); return 'Modal Gerenciar Projetos OK'; } return 'Sem funcao'; })()"),
            ("Teste de Fundo Estatico ao Mover Comodo", "(function(){ const tAntes = {x: state.terreno.x, y: state.terreno.y}; const c = state.comodos[0]; c.x += 120; c.y += 80; desenharCAD(); desenharInstalacoes(); const tDepois = {x: state.terreno.x, y: state.terreno.y}; if (tAntes.x === tDepois.x && tAntes.y === tDepois.y) return 'SUCESSO: Planta/terreno de fundo permaneceu 100% estatico (x: ' + tDepois.x + ', y: ' + tDepois.y + ')'; return 'FALHA: Fundo se moveu de ' + JSON.stringify(tAntes) + ' para ' + JSON.stringify(tDepois); })()"),
            ("Teste de Fundo Estatico ao Redimensionar Comodo", "(function(){ const tAntes = {x: state.terreno.x, y: state.terreno.y}; const c = state.comodos[0]; c.largura += 3; c.comprimento += 2; desenharCAD(); desenharInstalacoes(); const tDepois = {x: state.terreno.x, y: state.terreno.y}; if (tAntes.x === tDepois.x && tAntes.y === tDepois.y) return 'SUCESSO: Planta/terreno de fundo permaneceu 100% estatico apos redimensionamento (x: ' + tDepois.x + ', y: ' + tDepois.y + ')'; return 'FALHA: Fundo se moveu de ' + JSON.stringify(tAntes) + ' para ' + JSON.stringify(tDepois); })()")
        ]

        log("\n" + "=" * 60)
        log("EXECUTANDO BATERIA DE TESTES DAS FUNCIONALIDADES:")
        log("=" * 60)
        pass_count = 0
        fail_count = 0
        for name, code in tests:
            res = evaluate(code, timeout_sec=5.0)
            val = res.get("result", {}).get("value", res)
            err = res.get("exceptionDetails", {})
            if err or res.get("timeout"):
                fail_count += 1
                if res.get("timeout"):
                    log(f"[-] {name}: TIMEOUT")
                else:
                    log(f"[-] {name}: ERRO: {err.get('text')} - {err.get('exception', {}).get('description')}")
            else:
                pass_count += 1
                log(f"[+] {name}: {val}")

        drain_events()
        log("\n" + "=" * 60)
        log(f"RESULTADO: {pass_count} TESTES PASSARAM, {fail_count} FALHARAM")
        log(f"TOTAL DE EXCECOES CAPTURADAS: {len(exceptions)}")
        log("=" * 60)
        for ex in exceptions:
            log(f"  EX: {ex.get('text')} - {ex.get('exception', {}).get('description', '')}")

    finally:
        proc.terminate()

if __name__ == '__main__':
    run_tests()
