# -*- coding: utf-8 -*-
"""
Servidor Web Local para PRO-ELÉTRICA CAD NBR 5410
Permite abrir a aplicação em qualquer navegador na rede local (Wi-Fi / LAN)
e gerencia o salvamento/carregamento direto de projetos na pasta 'projetos/'.
"""

import os
import sys
import json
import socket
import datetime
import subprocess
import http.server
import socketserver
import webbrowser
from urllib.parse import unquote, parse_qs, urlparse

# Configura codificação do console para UTF-8 de forma segura
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PORTA_PADRAO = 8080
DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_PROJETOS = os.path.join(DIRETORIO_BASE, 'projetos')

os.makedirs(PASTA_PROJETOS, exist_ok=True)

def obter_ips_locais():
    ips = []
    try:
        nome_host = socket.gethostname()
        for ip in socket.gethostbyname_ex(nome_host)[2]:
            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                ips.append(ip)
    except Exception:
        pass
    
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            ips.append("127.0.0.1")
    return list(dict.fromkeys(ips))

def desenhar_banner(ip_principal, porta):
    url_local = f"http://localhost:{porta}"
    url_rede = f"http://{ip_principal}:{porta}"

    print("\n" + "=" * 70)
    print("   [+] PRO-ELÉTRICA CAD NBR 5410 - SERVIDOR WEB ATIVO COM PASTA DE PROJETOS")
    print("=" * 70)
    print("\n  O software esta pronto para ser aberto em QUALQUER dispositivo!")
    print(f"\n  >> PASTA DE PROJETOS SALVOS:\n     {PASTA_PROJETOS}")
    print("\n  >> NO CELULAR OU TABLET (Conectado ao mesmo Wi-Fi):")
    print(f"     URL: {url_rede}")
    print("\n  >> NESTE COMPUTADOR:")
    print(f"     URL: {url_local}")
    print("\n" + "-" * 70)
    print("  [Pressione CTRL + C para encerrar o servidor]")
    print("=" * 70 + "\n")

def sanitizar_nome_arquivo(nome):
    if not nome:
        nome = "projeto"
    # Remove caracteres inválidos para nomes de arquivos
    caracteres_validos = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ"
    nome_limpo = "".join(c for c in nome if c in caracteres_validos).strip()
    if not nome_limpo:
        nome_limpo = "projeto"
    if not nome_limpo.lower().endswith('.proeletrica'):
        nome_limpo += '.proeletrica'
    return nome_limpo

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def responder_json(self, status, dados):
        corpo = json.dumps(dados, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        parsed = urlparse(self.path)
        caminho = unquote(parsed.path)

        # Rota de status do servidor e pasta
        if caminho == '/api/status':
            self.responder_json(200, {
                'status': 'online',
                'pasta_projetos': PASTA_PROJETOS,
                'total_projetos': len([f for f in os.listdir(PASTA_PROJETOS) if f.lower().endswith('.proeletrica')])
            })
            return

        # Rota para listar arquivos salvos na pasta 'projetos'
        if caminho == '/api/projetos':
            try:
                arquivos = []
                for f in os.listdir(PASTA_PROJETOS):
                    if f.lower().endswith('.proeletrica'):
                        caminho_completo = os.path.join(PASTA_PROJETOS, f)
                        stats = os.stat(caminho_completo)
                        mod_dt = datetime.datetime.fromtimestamp(stats.st_mtime)
                        
                        nome_projeto = f[:-12]
                        resumo = {}
                        try:
                            with open(caminho_completo, 'r', encoding='utf-8') as arq_json:
                                dados = json.load(arq_json)
                                if 'projeto' in dados and isinstance(dados['projeto'], dict):
                                    nome_projeto = dados['projeto'].get('nome', nome_projeto)
                                if 'estado' in dados and isinstance(dados['estado'], dict):
                                    est = dados['estado']
                                    resumo = {
                                        'pavimentos': len(est.get('pavimentos', [])),
                                        'comodos': len(est.get('comodos', [])),
                                        'pontos': len(est.get('pontosEletricos', []))
                                    }
                        except Exception:
                            pass

                        arquivos.append({
                            'arquivo': f,
                            'nome': nome_projeto,
                            'tamanho_bytes': stats.st_size,
                            'modificado_em': mod_dt.strftime('%d/%m/%Y %H:%M:%S'),
                            'timestamp': stats.st_mtime,
                            'resumo': resumo
                        })
                
                # Ordena pelos mais recentes primeiro
                arquivos.sort(key=lambda x: x['timestamp'], reverse=True)
                self.responder_json(200, {'sucesso': True, 'projetos': arquivos, 'pasta': PASTA_PROJETOS})
            except Exception as e:
                self.responder_json(500, {'sucesso': False, 'erro': str(e)})
            return

        # Rota para carregar um projeto específico da pasta 'projetos'
        if caminho == '/api/projetos/carregar':
            params = parse_qs(parsed.query)
            nome_arq = params.get('arquivo', [''])[0]
            nome_arq = os.path.basename(nome_arq) # Evita path traversal

            caminho_completo = os.path.join(PASTA_PROJETOS, nome_arq)
            if not os.path.exists(caminho_completo):
                self.responder_json(404, {'sucesso': False, 'erro': 'Arquivo de projeto não encontrado.'})
                return

            try:
                with open(caminho_completo, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                self.responder_json(200, {'sucesso': True, 'arquivo': nome_arq, 'dados': dados})
            except Exception as e:
                self.responder_json(500, {'sucesso': False, 'erro': f'Erro ao ler arquivo: {str(e)}'})
            return

        # Rota padrão para página inicial
        if caminho in ('/', ''):
            if os.path.exists('index.html'):
                self.path = '/index.html'
            elif os.path.exists('Projeto elétrico.html'):
                self.path = '/Projeto%20el%C3%A9trico.html'
        
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        caminho = unquote(parsed.path)

        length = int(self.headers.get('Content-Length', 0))
        corpo_raw = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'

        # Salvar projeto diretamente na pasta 'projetos/'
        if caminho == '/api/projetos/salvar':
            try:
                payload = json.loads(corpo_raw)
                nome_base = payload.get('nomeArquivo') or (payload.get('projeto', {}).get('nome')) or 'Projeto_Eletrico'
                nome_arq = sanitizar_nome_arquivo(nome_base)
                
                caminho_arquivo = os.path.join(PASTA_PROJETOS, nome_arq)

                # Salva com formatação bonita e UTF-8
                with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

                print(f"[+] Projeto salvo com sucesso: {caminho_arquivo}")
                self.responder_json(200, {
                    'sucesso': True,
                    'mensagem': f'Projeto gravado na pasta com sucesso!',
                    'arquivo': nome_arq,
                    'caminho': caminho_arquivo
                })
            except Exception as e:
                print(f"[-] Erro ao salvar projeto: {e}")
                self.responder_json(500, {'sucesso': False, 'erro': str(e)})
            return

        # Excluir projeto da pasta
        if caminho == '/api/projetos/excluir':
            try:
                payload = json.loads(corpo_raw)
                nome_arq = os.path.basename(payload.get('arquivo', ''))
                caminho_completo = os.path.join(PASTA_PROJETOS, nome_arq)
                if os.path.exists(caminho_completo):
                    os.remove(caminho_completo)
                    self.responder_json(200, {'sucesso': True, 'mensagem': f'Arquivo "{nome_arq}" excluído.'})
                else:
                    self.responder_json(404, {'sucesso': False, 'erro': 'Arquivo não encontrado.'})
            except Exception as e:
                self.responder_json(500, {'sucesso': False, 'erro': str(e)})
            return

        # Abrir a pasta 'projetos' no Explorador de Arquivos do Windows
        if caminho == '/api/projetos/abrir_pasta':
            try:
                if sys.platform.startswith('win'):
                    os.startfile(PASTA_PROJETOS)
                elif sys.platform.startswith('darwin'):
                    subprocess.Popen(['open', PASTA_PROJETOS])
                else:
                    subprocess.Popen(['xdg-open', PASTA_PROJETOS])
                self.responder_json(200, {'sucesso': True, 'pasta': PASTA_PROJETOS})
            except Exception as e:
                self.responder_json(500, {'sucesso': False, 'erro': str(e)})
            return

        self.responder_json(404, {'sucesso': False, 'erro': 'Rota não encontrada'})

def main():
    diretorio = os.path.dirname(os.path.abspath(__file__))
    os.chdir(diretorio)

    ips = obter_ips_locais()
    ip_principal = ips[0] if ips else "127.0.0.1"

    porta = PORTA_PADRAO
    servidor = None

    for p in range(porta, porta + 10):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            servidor = socketserver.TCPServer(('0.0.0.0', p), CustomHandler)
            porta = p
            break
        except OSError:
            continue

    if not servidor:
        print(f"Erro: Nao foi possivel vincular o servidor as portas {PORTA_PADRAO}-{PORTA_PADRAO+9}")
        sys.exit(1)

    desenhar_banner(ip_principal, porta)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor finalizado com sucesso.")
        servidor.server_close()

if __name__ == '__main__':
    main()
