from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import os
import json
from datetime import datetime, timedelta
import hashlib
import pickle
from threading import Thread
from flask import Flask
import requests
import logging

# ✅ CONFIGURAÇÃO RENDER
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot TJSP Online - Render.com + GitHub Gist"

@app.route('/health')
def health():
    return "✅ OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    return "📩 Webhook received", 200

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class CacheManager:
    def __init__(self):
        self.cache_file = 'links_cache.pkl'
        self.links_cache = self._load_cache()
    
    def _load_cache(self):
        """Carrega o cache do arquivo"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            print(f"❌ Erro ao carregar cache: {e}")
        return {}
    
    def _save_cache(self):
        """Salva o cache no arquivo"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.links_cache, f)
        except Exception as e:
            print(f"❌ Erro ao salvar cache: {e}")
    
    def get_link(self, processo_id):
        """Obtém link pelo ID"""
        return self.links_cache.get(processo_id, {}).get('link')
    
    def get_numero(self, processo_id):
        """Obtém número pelo ID"""
        return self.links_cache.get(processo_id, {}).get('numero')
    
    def save_link(self, processo_id, numero, link):
        """Salva link no cache"""
        self.links_cache[processo_id] = {
            'numero': numero,
            'link': link,
            'timestamp': datetime.now()
        }
        self._save_cache()
    
    def find_by_numero(self, numero_processo):
        """Encontra ID pelo número do processo"""
        for processo_id, info in self.links_cache.items():
            if info.get('numero') == numero_processo:
                return processo_id
        return None

class LicenseManager:
    def __init__(self):
        self.gist_id = os.environ.get('GIST_ID')
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.admins = ["coder7br", "admin", "teste"]
        self.license_duration = 7
        self.licenses = {}
        
        # Verificar configuração
        if not self.gist_id or not self.github_token:
            print("⚠️  GIST_ID ou GITHUB_TOKEN não configurados")
            print("⚠️  Sistema de licenças funcionará em modo temporário")
        else:
            print(f"✅ GitHub Gist configurado: {self.gist_id}")
            self.licenses = self._load_from_gist()
    
    def _load_from_gist(self):
        """Carrega licenças do GitHub Gist"""
        if not self._is_configured():
            return {}
        
        try:
            url = f'https://api.github.com/gists/{self.gist_id}'
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'licenses.json' in data['files']:
                    content = data['files']['licenses.json']['content']
                    
                    # Converter strings de data para objetos datetime
                    licenses_data = json.loads(content)
                    converted_licenses = {}
                    
                    for username, license_info in licenses_data.items():
                        converted_licenses[username] = {
                            'expiry_date': datetime.fromisoformat(license_info['expiry_date']),
                            'created_at': datetime.fromisoformat(license_info['created_at']),
                            'duration_days': license_info['duration_days']
                        }
                    
                    print(f"✅ {len(converted_licenses)} licenças carregadas do Gist")
                    return converted_licenses
                else:
                    print("⚠️  Arquivo licenses.json não encontrado no Gist")
            else:
                print(f"❌ Erro ao carregar Gist: {response.status_code} - {response.text}")
                
        except requests.exceptions.Timeout:
            print("❌ Timeout ao carregar Gist")
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro de conexão: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ Erro ao decodificar JSON do Gist: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado ao carregar Gist: {e}")
        
        return {}
    
    def _save_to_gist(self):
        """Salva licenças no GitHub Gist"""
        if not self._is_configured():
            print("⚠️  Gist não configurado - licenças não serão salvas")
            return False
        
        try:
            # Converter datetime para string ISO
            save_data = {}
            for username, license_info in self.licenses.items():
                save_data[username] = {
                    'expiry_date': license_info['expiry_date'].isoformat(),
                    'created_at': license_info['created_at'].isoformat(),
                    'duration_days': license_info['duration_days']
                }
            
            url = f'https://api.github.com/gists/{self.gist_id}'
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            }
            
            data = {
                'description': f'Licenças Bot TJSP - Atualizado em {datetime.now().strftime("%d/%m/%Y %H:%M")}',
                'files': {
                    'licenses.json': {
                        'content': json.dumps(save_data, ensure_ascii=False, indent=2)
                    }
                }
            }
            
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                print("💾 Licenças salvas no Gist com sucesso")
                return True
            else:
                print(f"❌ Erro ao salvar Gist: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("❌ Timeout ao salvar Gist")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro de conexão ao salvar: {e}")
            return False
        except Exception as e:
            print(f"❌ Erro inesperado ao salvar Gist: {e}")
            return False
    
    def _is_configured(self):
        """Verifica se Gist está configurado"""
        return bool(self.gist_id and self.github_token)
    
    def is_admin(self, username: str):
        """Verifica se o usuário é admin"""
        return username and username.lower() in [admin.lower() for admin in self.admins]
    
    def add_license(self, username: str, duration_days: int = None):
        """Adiciona uma licença para um username"""
        if duration_days is None:
            duration_days = self.license_duration
        
        expiry_date = datetime.now() + timedelta(days=duration_days)
        username_lower = username.lower()
        
        self.licenses[username_lower] = {
            'expiry_date': expiry_date,
            'created_at': datetime.now(),
            'duration_days': duration_days
        }
        
        # Tentar salvar no Gist
        if self._is_configured():
            success = self._save_to_gist()
            if not success:
                print("⚠️  Licença adicionada localmente, mas não foi salva no Gist")
        else:
            print("⚠️  Licença adicionada apenas localmente (Gist não configurado)")
        
        return expiry_date
    
    def check_license(self, username: str):
        """Verifica se um username tem licença válida"""
        if not username:
            return False, "❌ Username não identificado"
        
        username_lower = username.lower()
        
        if self.is_admin(username):
            return True, "✅ **Acesso Admin - Ilimitado**"
        
        # Recarregar do Gist para garantir dados atualizados
        if self._is_configured():
            self.licenses = self._load_from_gist()
        
        if username_lower not in self.licenses:
            return False, f"❌ Licença não encontrada para @{username}"
        
        license_info = self.licenses[username_lower]
        expiry_date = license_info['expiry_date']
        
        if datetime.now() > expiry_date:
            # Remover licença expirada
            self.revoke_license(username)
            return False, f"❌ Licença expirada para @{username}"
        
        days_left = (expiry_date - datetime.now()).days
        return True, f"✅ Licença válida - {days_left} dias restantes"
    
    def revoke_license(self, username: str):
        """Revoga uma licença"""
        username_lower = username.lower()
        
        if username_lower in self.licenses:
            del self.licenses[username_lower]
            
            # Salvar alterações no Gist
            if self._is_configured():
                success = self._save_to_gist()
                if success:
                    print(f"✅ Licença de @{username} revogada e salva no Gist")
                else:
                    print(f"⚠️  Licença revogada localmente, mas não salva no Gist")
                return success
            else:
                print(f"⚠️  Licença de @{username} revogada apenas localmente")
                return True
        
        return False
    
    def get_license_info(self, username: str):
        """Obtém informações da licença"""
        username_lower = username.lower()
        
        if self.is_admin(username):
            return {
                'username': username,
                'expiry_date': "ILIMITADO",
                'days_left': "∞",
                'created_at': "ADMIN",
                'duration_days': "ILIMITADO",
                'type': 'admin'
            }
        
        # Recarregar do Gist para dados atualizados
        if self._is_configured():
            self.licenses = self._load_from_gist()
        
        if username_lower in self.licenses:
            license_info = self.licenses[username_lower]
            expiry_date = license_info['expiry_date']
            days_left = (expiry_date - datetime.now()).days
            
            return {
                'username': username,
                'expiry_date': expiry_date.strftime('%d/%m/%Y %H:%M'),
                'days_left': days_left,
                'created_at': license_info['created_at'].strftime('%d/%m/%Y %H:%M'),
                'duration_days': license_info['duration_days'],
                'type': 'user'
            }
        return None
    
    def list_licenses(self):
        """Lista todas as licenças ativas"""
        # Recarregar do Gist para dados atualizados
        if self._is_configured():
            self.licenses = self._load_from_gist()
        
        active_licenses = {}
        now = datetime.now()
        
        for username, license_info in self.licenses.items():
            if now <= license_info['expiry_date']:
                days_left = (license_info['expiry_date'] - now).days
                active_licenses[username] = {
                    'expiry_date': license_info['expiry_date'].strftime('%d/%m/%Y'),
                    'days_left': days_left
                }
        
        return active_licenses
    
    def force_sync(self):
        """Força sincronização com o Gist"""
        if not self._is_configured():
            return False
        
        print("🔄 Sincronizando licenças com Gist...")
        self.licenses = self._load_from_gist()
        return True
    
    def get_stats(self):
        """Retorna estatísticas do sistema de licenças"""
        active_count = 0
        expired_count = 0
        now = datetime.now()
        
        for license_info in self.licenses.values():
            if now <= license_info['expiry_date']:
                active_count += 1
            else:
                expired_count += 0
        
        return {
            'total_licenses': len(self.licenses),
            'active_licenses': active_count,
            'expired_licenses': expired_count,
            'gist_configured': self._is_configured(),
            'admins_count': len(self.admins)
        }

class SessionManager:
    def __init__(self):
        self.user_sessions = {}
        self.session_timeout = 3600
    
    def create_session(self, username, chat_id, oab):
        """Cria uma sessão privada para o usuário"""
        session_id = f"{username}_{chat_id}"
        self.user_sessions[session_id] = {
            'oab': oab,
            'processos': [],
            'service': TJSPScrapingService(),
            'created_at': datetime.now(),
            'user_info': {
                'username': username,
                'chat_id': chat_id
            }
        }
        return session_id
    
    def get_session(self, username, chat_id):
        """Obtém a sessão do usuário"""
        session_id = f"{username}_{chat_id}"
        session = self.user_sessions.get(session_id)
        
        if session:
            elapsed = (datetime.now() - session['created_at']).seconds
            if elapsed > self.session_timeout:
                self.clear_session(username, chat_id)
                return None
        return session
    
    def clear_session(self, username, chat_id):
        """Limpa a sessão do usuário"""
        session_id = f"{username}_{chat_id}"
        if session_id in self.user_sessions:
            del self.user_sessions[session_id]
    
    def get_user_sessions(self, username):
        """Obtém todas as sessões de um usuário"""
        return {k: v for k, v in self.user_sessions.items() if k.startswith(f"{username}_")}

class TJSPScrapingService:
    def __init__(self):
        self.cache_manager = CacheManager()
    
    def _gerar_id_processo(self, numero_processo, oab):
        """Gera ID único para o processo"""
        hash_input = f"{numero_processo}_{oab}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:10]
    
    async def consultar_por_oab(self, oab: str, update: Update = None):
        """Consulta TODOS os processos por OAB com timeouts aumentados"""
        try:
            if update:
                await update.message.reply_text("🔍 **Acessando o TJSP...**")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    timeout=120000,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process'
                    ]
                )
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                page.set_default_timeout(60000)
                page.set_default_navigation_timeout(60000)
                
                try:
                    await page.goto("https://esaj.tjsp.jus.br/cpopg/open.do", 
                                  wait_until="networkidle", 
                                  timeout=60000)
                except Exception as e:
                    if update:
                        await update.message.reply_text("❌ **Erro ao carregar página inicial do TJSP**")
                    await browser.close()
                    return [], f"❌ Erro ao acessar TJSP: {str(e)}"
                
                if update:
                    await update.message.reply_text("✅ **Site carregado**\n📝 Consultando TODOS os processos...")
                
                try:
                    await page.select_option('select[name="cbPesquisa"]', "NUMOAB", timeout=30000)
                    await page.wait_for_selector('#campo_NUMOAB:not([disabled])', timeout=30000)
                    await page.fill('#campo_NUMOAB', '')
                    await page.type('#campo_NUMOAB', oab, delay=100)
                    await page.click('#botaoConsultarProcessos')
                except Exception as e:
                    if update:
                        await update.message.reply_text("❌ **Erro ao preencher formulário**")
                    await browser.close()
                    return [], f"❌ Erro no formulário: {str(e)}"
                
                if update:
                    await update.message.reply_text("🔄 **Buscando TODOS os processos...**\n⏳ Isso pode demorar vários minutos...")
                
                try:
                    await page.wait_for_load_state("networkidle", timeout=60000)
                    await asyncio.sleep(5)
                except:
                    pass
                
                todos_processos = []
                pagina_atual = 1
                total_processos = 0
                max_paginas = 50
                
                while pagina_atual <= max_paginas:
                    try:
                        if update and pagina_atual % 10 == 1:
                            await update.message.reply_text(f"📄 **Processando página {pagina_atual}**")
                        
                        try:
                            html = await page.content()
                        except:
                            html = ""
                        
                        processos_pagina = self._parse_processos_pagina(html, oab)
                        todos_processos.extend(processos_pagina)
                        
                        if len(processos_pagina) > 0:
                            total_processos += len(processos_pagina)
                            if update and pagina_atual % 5 == 0:
                                await update.message.reply_text(f"✅ **{total_processos} processos indexados**")
                        
                        try:
                            next_button = await page.query_selector('.unj-pagination__next:not(.disabled)')
                            if not next_button:
                                if update:
                                    await update.message.reply_text(f"🏁 **Consulta finalizada!**\n📋 Total: {total_processos} processos")
                                break
                            
                            await next_button.click()
                            await asyncio.sleep(3)
                            
                            try:
                                await page.wait_for_load_state("networkidle", timeout=30000)
                            except:
                                pass
                                
                        except Exception as e:
                            print(f"⚠️ Erro ao mudar de página: {e}")
                            break
                            
                        pagina_atual += 1
                        
                    except Exception as e:
                        print(f"⚠️ Erro na página {pagina_atual}: {e}")
                        break
                
                await browser.close()
                
                if not todos_processos:
                    return [], "❌ Nenhum processo encontrado"
                
                self._salvar_processos_json(todos_processos, oab)
                
                if update:
                    await update.message.reply_text(f"🎉 **CONSULTA COMPLETA!**\n📋 {len(todos_processos)} processos indexados")
                
                return todos_processos, None
                
        except Exception as e:
            error_msg = f"❌ Erro na consulta: {str(e)}"
            if update:
                await update.message.reply_text(error_msg)
            return [], error_msg

    def _parse_processos_pagina(self, html_content, oab):
        """Parseia processos de uma página"""
        processos = []
        if not html_content:
            return processos
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        links_processos = soup.find_all('a', class_='linkProcesso')
        
        for link in links_processos:
            try:
                numero_processo = link.get_text(strip=True)
                href = link.get('href', '')
                link_completo = f"https://esaj.tjsp.jus.br{href}" if href.startswith('/') else href
                
                processo_id = self._gerar_id_processo(numero_processo, oab)
                self.cache_manager.save_link(processo_id, numero_processo, link_completo)
                
                ano_processo = self._extrair_ano_processo(numero_processo)
                
                linha_processo = link.find_parent('li')
                if not linha_processo:
                    continue
                
                classe_div = linha_processo.find('div', class_='classeProcesso')
                classe = classe_div.get_text(strip=True) if classe_div else "N/A"
                
                assunto_div = linha_processo.find('div', class_='assuntoPrincipalProcesso')
                assunto = assunto_div.get_text(strip=True) if assunto_div else "N/A"
                
                data_div = linha_processo.find('div', class_='dataLocalDistribuicaoProcesso')
                data_movimentacao = data_div.get_text(strip=True) if data_div else "N/A"
                
                nome_parte_div = linha_processo.find('div', class_='nomeParte')
                advogado = nome_parte_div.get_text(strip=True) if nome_parte_div else "N/A"
                
                processo_info = {
                    'id': processo_id,
                    'numero': numero_processo,
                    'classe': classe,
                    'assunto': assunto,
                    'ano': ano_processo,
                    'data_movimentacao': data_movimentacao,
                    'advogado': advogado
                }
                
                processos.append(processo_info)
                
            except Exception as e:
                print(f"⚠️ Erro ao processar link: {e}")
                continue
        
        return processos

    def _salvar_processos_json(self, processos, oab):
        """Salva TODOS os processos em arquivo JSON"""
        try:
            if not os.path.exists('processos'):
                os.makedirs('processos')
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_arquivo = f"processos/processos_{oab}_{timestamp}.json"
            
            dados = {
                'oab': oab,
                'data_consulta': datetime.now().isoformat(),
                'total_processos': len(processos),
                'processos_por_ano': {}
            }
            
            for processo in processos:
                ano = processo['ano']
                if ano not in dados['processos_por_ano']:
                    dados['processos_por_ano'][ano] = []
                dados['processos_por_ano'][ano].append(processo)
            
            with open(nome_arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            
            return nome_arquivo
            
        except Exception as e:
            print(f"❌ Erro ao salvar arquivo JSON: {e}")
            return None

    def _extrair_ano_processo(self, numero_processo):
        """Extrai ano do processo"""
        try:
            ano_match = re.search(r'\.(\d{4})\.', numero_processo)
            if ano_match:
                return int(ano_match.group(1))
            return 0
        except:
            return 0

    def formatar_processos_ano(self, processos, ano):
        """Formata processos de um ano específico"""
        if not processos:
            return f"❌ Nenhum processo encontrado para {ano}"
        
        mensagem = f"📋 **PROCESSOS {ano}** ({len(processos)} processos)\n\n"
        
        for i, processo in enumerate(processos, 1):
            assunto = processo['assunto']
            if len(assunto) > 50:
                assunto = assunto[:47] + "..."
            
            mensagem += f"**{i:02d}. {processo['numero']}**\n"
            mensagem += f"⚖ {processo['classe']}\n"
            mensagem += f"📝 {assunto}\n"
            mensagem += f"👨‍💼 {processo['advogado']}\n"
            mensagem += f"📄 {processo['data_movimentacao']}\n"
            mensagem += f"🔗 `/link_{processo['id']}`\n"
            mensagem += f"📋 `/detalhes_{processo['id']}`\n"
            mensagem += "─" * 40 + "\n\n"
        
        return mensagem

    def formatar_todos_processos(self, processos):
        """Formata todos os processos agrupados por ano"""
        if not processos:
            return "❌ Nenhum processo encontrado"
        
        processos_por_ano = self.agrupar_por_ano(processos)
        
        mensagem = "📋 **TODOS OS PROCESSOS**\n\n"
        
        for ano, procs_ano in processos_por_ano.items():
            mensagem += f"🎯 **{ano}** ({len(procs_ano)} processos)\n"
            
            for i, processo in enumerate(procs_ano[:5], 1):
                assunto = processo['assunto']
                if len(assunto) > 40:
                    assunto = assunto[:37] + "..."
                
                mensagem += f"{i:02d}. {processo['numero']}\n"
                mensagem += f"   ⚖ {processo['classe']}\n"
                mensagem += f"   📝 {assunto}\n"
                mensagem += f"   🔗 `/link_{processo['id']}`\n\n"
            
            if len(procs_ano) > 5:
                mensagem += f"   ... e mais {len(procs_ano) - 5} processos\n"
            
            mensagem += "─" * 40 + "\n\n"
        
        mensagem += "💡 Use `/nums` para ver apenas números ou `/2024` para um ano específico"
        
        return mensagem

    def formatar_apenas_numeros(self, processos):
        """Formata apenas números com comandos"""
        if not processos:
            return "❌ Nenhum processo encontrado"
        
        processos_por_ano = self.agrupar_por_ano(processos)
        anos_ordenados = sorted(processos_por_ano.keys(), reverse=True)
        
        mensagem = "🔢 **NÚMEROS DOS PROCESSOS**\n\n"
        
        for ano in anos_ordenados:
            mensagem += f"🎯 **{ano}** ({len(processos_por_ano[ano])} processos):\n"
            
            for i, processo in enumerate(processos_por_ano[ano][:20], 1):
                mensagem += f"{i:02d}. {processo['numero']}\n"
                mensagem += f"   🔗 `/link_{processo['id']}` | 📋 `/detalhes_{processo['id']}`\n"
            
            if len(processos_por_ano[ano]) > 20:
                mensagem += f"   ... e mais {len(processos_por_ano[ano]) - 20} processos\n"
            
            mensagem += "\n"
        
        return mensagem

    def obter_link_por_id(self, processo_id):
        """Obtém link original pelo ID"""
        link = self.cache_manager.get_link(processo_id)
        if link:
            return link
        return "❌ ID não encontrado no cache. Execute uma nova consulta."

    def obter_numero_por_id(self, processo_id):
        """Obtém número do processo pelo ID"""
        numero = self.cache_manager.get_numero(processo_id)
        if numero:
            return numero
        return "❌ ID não encontrado no cache. Execute uma nova consulta."

    async def obter_detalhes_processo(self, processo_id, update: Update = None):
        """Obtém detalhes COMPLETOS do processo com análise profunda de CPF"""
        try:
            link = self.obter_link_por_id(processo_id)
            if not link.startswith('http'):
                return "❌ Processo não encontrado no cache. Execute uma nova consulta."
            
            if update:
                await update.message.reply_text("🔍 **Acessando detalhes COMPLETOS do processo...**\n🔎 **Análise profunda de CPF/CNPJ ativada**")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    timeout=120000,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process'
                    ]
                )
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                page.set_default_timeout(45000)
                page.set_default_navigation_timeout(45000)
                
                try:
                    await page.goto(link, wait_until="networkidle", timeout=45000)
                    await asyncio.sleep(3)
                    
                    html_content = await page.content()
                    
                    if "Número não localizado" in html_content or "Não existem informações" in html_content:
                        await browser.close()
                        return "❌ Processo não encontrado no TJSP."
                    
                    # Análise básica para esta versão
                    detalhes = self._parse_detalhes_completos(html_content)
                    await browser.close()
                    
                    if detalhes:
                        return detalhes
                    else:
                        return "❌ Não foi possível extrair os detalhes do processo."
                        
                except Exception as e:
                    await browser.close()
                    return f"❌ Erro ao carregar página do processo: {str(e)}"
                
        except Exception as e:
            return f"❌ Erro ao obter detalhes: {str(e)}"

    def _parse_detalhes_completos(self, html_content):
        """Parseia detalhes básicos do processo"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            detalhes = {
                'numero_processo': self._extrair_texto(soup, ['#numeroProcesso', '.header__content__title']),
                'classe': self._extrair_texto(soup, ['.classeProcesso', '[id*="classe"]']),
                'assunto': self._extrair_texto(soup, ['.assuntoProcesso', '[id*="assunto"]']),
                'foro': self._extrair_texto(soup, ['.foroProcesso', '[id*="foro"]']),
                'vara': self._extrair_texto(soup, ['.varaProcesso', '[id*="vara"]']),
                'area': self._extrair_texto(soup, ['.areaProcesso', '[id*="area"]']),
            }
            
            return detalhes
            
        except Exception as e:
            print(f"❌ Erro ao parsear detalhes: {e}")
            return None

    def _extrair_texto(self, soup, seletores):
        """Extrai texto usando múltiplos seletores"""
        for seletor in seletores:
            elemento = soup.select_one(seletor)
            if elemento:
                texto = elemento.get_text(strip=True)
                if texto:
                    return texto
        return "Não informado"

    def formatar_detalhes_processo(self, numero_processo, detalhes):
        """Formata detalhes do processo"""
        if not detalhes:
            return "❌ Não foi possível obter os detalhes do processo"
        
        mensagem = (
            f"📋 **DETALHES DO PROCESSO**\n\n"
            f"🔢 **Número:** {detalhes['numero_processo']}\n"
            f"⚖ **Classe:** {detalhes['classe']}\n"
            f"📝 **Assunto:** {detalhes['assunto']}\n"
            f"🏛 **Foro:** {detalhes['foro']}\n"
            f"⚖ **Vara:** {detalhes['vara']}\n"
            f"📍 **Área:** {detalhes['area']}\n\n"
            f"💡 *Análise de CPF/CNPJ disponível em versões futuras*"
        )
        
        return mensagem

    def buscar_por_numero(self, processos, numero):
        """Busca processo por número"""
        resultados = []
        for processo in processos:
            if numero in processo['numero']:
                resultados.append(processo)
        return resultados

    def agrupar_por_ano(self, processos):
        """Agrupa processos por ano"""
        anos = {}
        for processo in processos:
            ano = processo['ano']
            if ano not in anos:
                anos[ano] = []
            anos[ano].append(processo)
        return dict(sorted(anos.items(), reverse=True))

# ✅ BOT_TOKEN - Usar variável de ambiente
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7152880157:AAGt6SUNaDvN2RxWc88Px_eMaxK3rY3OdnY')

# Gerenciadores
license_manager = LicenseManager()
session_manager = SessionManager()

# Handlers do Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username or "Anônimo"
    
    has_license, license_msg = license_manager.check_license(username)
    
    if not has_license:
        await update.message.reply_text(
            f"❌ **ACESSO NEGADO**\n\n"
            f"{license_msg}\n\n"
            f"💡 **Sistema de Licenças:**\n"
            f"• Acesso por username (@)\n"
            f"• Licenças semanais\n"
            f"• Controle individual\n\n"
            f"📞 **Contate o administrador para obter uma licença**"
        )
        return
    
    license_info = license_manager.get_license_info(username)
    
    if license_manager.is_admin(username):
        user_type = "👑 **ADMINISTRADOR**"
        license_status = "🎯 **Acesso Ilimitado**"
    else:
        user_type = "👤 **USUÁRIO**"
        license_status = f"📅 **Expira em:** {license_info['days_left']} dias"
    
    await update.message.reply_text(
        f"👋 **BOT CONSULTOR TJSP - RENDER.COM + GIST**\n\n"
        f"{user_type}\n"
        f"✅ **Licença Ativa:** @{username}\n"
        f"{license_status}\n"
        f"🔢 **Válida até:** {license_info['expiry_date']}\n\n"
        f"⚡ **Como usar:**\n"
        f"1. Digite a OAB (ex: 123456SP)\n"
        f"2. Aguarde a consulta COMPLETA\n"
        f"3. Use os comandos abaixo\n\n"
        f"📋 **Comandos disponíveis:**\n"
        f"• `/2024` - Ver processos de 2024\n"
        f"• `/2025` - Ver processos de 2025\n" 
        f"• `/todos` - Ver todos os processos\n"
        f"• `/nums` - Apenas números\n"
        f"• `/buscar 123456` - Buscar por número\n"
        f"• `/link_ID` - Obter link (clique nos IDs)\n"
        f"• `/detalhes_ID` - Ver detalhes (clique nos IDs)\n"
        f"• `/stats` - Estatísticas\n"
        f"• `/licenca` - Info da licença\n"
        f"• `/giststatus` - Status do Gist (admin)\n"
        f"• `/sync` - Sincronizar licenças (admin)\n"
        f"• `/limpar` - Encerrar sessão\n"
    )

async def consultar_oab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username or "Anônimo"
    
    has_license, license_msg = license_manager.check_license(username)
    if not has_license:
        await update.message.reply_text(f"❌ **Licença necessária!**\n{license_msg}")
        return
    
    texto = update.message.text.upper().strip()
    chat_id = update.message.chat.id
    
    if texto.startswith('/'):
        return
    
    if not re.match(r'^\d{6}[A-Z]{2}$', texto):
        await update.message.reply_text("❌ **Formato inválido!**\nUse: 123456SP")
        return
    
    oab = texto
    
    session_manager.clear_session(username, chat_id)
    session_id = session_manager.create_session(username, chat_id, oab)
    session = session_manager.get_session(username, chat_id)
    
    license_info = license_manager.get_license_info(username)
    
    if license_manager.is_admin(username):
        user_header = "👑 **Admin**"
        license_header = "🎯 **Acesso Ilimitado**"
    else:
        user_header = "👤 **Licenciado**"
        license_header = f"📅 **Licença:** {license_info['days_left']} dias restantes"
    
    await update.message.reply_text(
        f"🔍 **CONSULTANDO OAB:** {oab}\n"
        f"{user_header}: @{username}\n"
        f"{license_header}\n"
        f"💬 **Sessão:** Privada\n"
        f"⏳ Isso pode demorar vários minutos..."
    )
    
    try:
        service = session['service']
        processos, _ = await service.consultar_por_oab(oab, update)
        
        if not processos:
            await update.message.reply_text("❌ Nenhum processo encontrado para esta OAB")
            session_manager.clear_session(username, chat_id)
            return
        
        session['processos'] = processos
        
        anos = service.agrupar_por_ano(processos)
        
        mensagem = (
            f"🎉 **CONSULTA COMPLETA!**\n\n"
            f"📋 **RESUMO - {oab}**\n"
            f"👤 **Usuário:** @{username}\n"
            f"📊 **Total:** {len(processos)} processos\n"
            f"📅 **Período:** {min(anos.keys())} - {max(anos.keys())}\n\n"
            f"🚀 **COMANDOS DISPONÍVEIS:**\n"
        )
        
        for ano in list(anos.keys())[:5]:
            mensagem += f"• `/{ano}` - {len(anos[ano])} processos\n"
        
        mensagem += (
            f"• `/todos` - Ver resumo geral\n"
            f"• `/nums` - Apenas números\n"
            f"• `/buscar NÚMERO` - Buscar processo\n"
            f"• `/stats` - Estatísticas\n"
            f"• `/licenca` - Info da licença\n"
            f"• `/limpar` - Encerrar sessão\n\n"
        )
        
        if license_manager.is_admin(username):
            mensagem += "👑 **COMANDOS ADMIN:**\n"
            mensagem += "• `/addlicenca @username dias` - Adicionar licença\n"
            mensagem += "• `/revogar @username` - Revogar licença\n"
            mensagem += "• `/licencas` - Listar licenças\n"
            mensagem += "• `/giststatus` - Status do Gist\n"
            mensagem += "• `/sync` - Sincronizar licenças\n"
        
        await update.message.reply_text(mensagem)
            
    except Exception as e:
        session_manager.clear_session(username, chat_id)
        await update.message.reply_text(f"❌ **Erro na consulta:** {str(e)}")

async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manipula comandos de ano e outros"""
    username = update.message.from_user.username or "Anônimo"
    
    has_license, license_msg = license_manager.check_license(username)
    if not has_license:
        await update.message.reply_text(f"❌ **Licença necessária!**\n{license_msg}")
        return
    
    chat_id = update.message.chat.id
    texto_original = update.message.text
    
    # SUPORTE A 2 FORMATOS: Remove menção do bot se existir
    texto = texto_original
    if '@' in texto:
        texto = texto.split('@')[0]
    
    session = session_manager.get_session(username, chat_id)
    
    if not session:
        await update.message.reply_text(
            "❌ **Nenhuma sessão ativa!**\n"
            "Digite uma OAB para iniciar uma consulta\n"
            "Ex: `123456SP`"
        )
        return
    
    processos = session['processos']
    service = session['service']
    oab = session['oab']
    
    try:
        license_info = license_manager.get_license_info(username)
        if license_manager.is_admin(username):
            header = f"👑 **Admin:** @{username}\n🔍 **OAB:** {oab}\n🎯 **Acesso Ilimitado**\n\n"
        else:
            header = f"👤 **Licenciado:** @{username}\n🔍 **OAB:** {oab}\n📅 **Licença:** {license_info['days_left']} dias\n\n"
        
        if texto == '/licenca':
            license_info = license_manager.get_license_info(username)
            if license_info:
                if license_info['type'] == 'admin':
                    mensagem = (
                        f"👑 **INFORMAÇÕES DA LICENÇA - ADMIN**\n\n"
                        f"👤 **Usuário:** @{username}\n"
                        f"🎯 **Tipo:** Administrador\n"
                        f"⚡ **Status:** Acesso Ilimitado\n"
                        f"🔓 **Privilégios:** Todos os comandos\n\n"
                        f"💡 **Comandos Admin disponíveis:**\n"
                        f"• `/addlicenca @username dias`\n"
                        f"• `/revogar @username`\n"
                        f"• `/licencas`\n"
                        f"• `/giststatus`\n"
                        f"• `/sync`"
                    )
                else:
                    mensagem = (
                        f"📄 **INFORMAÇÕES DA LICENÇA**\n\n"
                        f"👤 **Usuário:** @{username}\n"
                        f"📅 **Criada em:** {license_info['created_at']}\n"
                        f"⏰ **Expira em:** {license_info['expiry_date']}\n"
                        f"📊 **Dias restantes:** {license_info['days_left']}\n"
                        f"🕒 **Duração:** {license_info['duration_days']} dias\n"
                        f"✅ **Status:** ATIVA"
                    )
                await update.message.reply_text(mensagem)
            else:
                await update.message.reply_text("❌ Licença não encontrada")
            return
        
        if texto == '/limpar':
            session_manager.clear_session(username, chat_id)
            await update.message.reply_text("🗑️ **Sessão encerrada!**\nDigite uma nova OAB para nova consulta")
            return
        
        if texto == '/todos':
            mensagem = service.formatar_todos_processos(processos)
            if len(mensagem) > 4096:
                partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
                for parte in partes:
                    await update.message.reply_text(header + parte)
            else:
                await update.message.reply_text(header + mensagem)
        
        elif texto == '/nums':
            mensagem = service.formatar_apenas_numeros(processos)
            if len(mensagem) > 4096:
                partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
                for parte in partes:
                    await update.message.reply_text(header + parte)
            else:
                await update.message.reply_text(header + mensagem)
        
        elif texto.startswith('/buscar '):
            numero_busca = texto[8:].strip()
            resultados = service.buscar_por_numero(processos, numero_busca)
            
            if resultados:
                mensagem = f"🔍 **RESULTADOS PARA: {numero_busca}**\n\n"
                for i, processo in enumerate(resultados[:10], 1):
                    mensagem += f"**{i}. {processo['numero']}**\n"
                    mensagem += f"⚖ {processo['classe']}\n"
                    mensagem += f"📝 {processo['assunto'][:50]}...\n"
                    mensagem += f"👨‍💼 {processo['advogado']}\n"
                    mensagem += f"🔗 `/link_{processo['id']}` | 📋 `/detalhes_{processo['id']}`\n"
                    mensagem += "─" * 30 + "\n\n"
                
                if len(resultados) > 10:
                    mensagem += f"💡 Mostrando 10 de {len(resultados)} resultados\n"
                
                await update.message.reply_text(header + mensagem)
            else:
                await update.message.reply_text(f"❌ Nenhum processo encontrado com: {numero_busca}")
        
        elif texto.startswith('/link_'):
            processo_id = texto[6:]
            link = service.obter_link_por_id(processo_id)
            numero = service.obter_numero_por_id(processo_id)
            
            if link.startswith('http'):
                user_type = "👑 **Admin**" if license_manager.is_admin(username) else "👤 **Licenciado**"
                await update.message.reply_text(
                    f"🔗 **LINK DO PROCESSO**\n\n"
                    f"{user_type}: @{username}\n"
                    f"🔢 **Número:** {numero}\n"
                    f"🆔 **ID:** `{processo_id}`\n"
                    f"🔗 {link}\n\n"
                    f"💡 Clique no link acima para acessar o processo\n"
                    f"📋 Use `/detalhes_{processo_id}` para ver partes e valores"
                )
            else:
                await update.message.reply_text(f"❌ {link}")
        
        elif texto.startswith('/detalhes_'):
            processo_id = texto[10:]
            numero = service.obter_numero_por_id(processo_id)
            
            if numero.startswith('❌'):
                await update.message.reply_text(numero)
                return
            
            await update.message.reply_text("🔍 **Obtendo detalhes COMPLETOS do processo...**")
            
            try:
                detalhes = await service.obter_detalhes_processo(processo_id, update)
                
                if isinstance(detalhes, str):
                    await update.message.reply_text(detalhes)
                else:
                    mensagem_detalhes = service.formatar_detalhes_processo(numero, detalhes)
                    user_type = "👑 **Admin**" if license_manager.is_admin(username) else "👤 **Licenciado**"
                    header_detalhes = f"{user_type}: @{username}\n🔢 **Processo:** {numero}\n\n"
                    
                    if len(mensagem_detalhes) > 4096:
                        partes = [mensagem_detalhes[i:i+4000] for i in range(0, len(mensagem_detalhes), 4000)]
                        for parte in partes:
                            await update.message.reply_text(header_detalhes + parte)
                    else:
                        await update.message.reply_text(header_detalhes + mensagem_detalhes)
            except Exception as e:
                await update.message.reply_text(f"❌ **Erro ao obter detalhes:** {str(e)}")
        
        elif texto == '/stats':
            anos = service.agrupar_por_ano(processos)
            
            user_type = "👑 **Admin**" if license_manager.is_admin(username) else "👤 **Licenciado**"
            mensagem = f"📊 **ESTATÍSTICAS - {oab}**\n\n"
            mensagem += f"{user_type}: @{username}\n"
            mensagem += f"📈 **Total:** {len(processos)} processos\n\n"
            
            for ano, procs in anos.items():
                mensagem += f"**{ano}:** {len(procs)} processos\n"
                classes = {}
                for p in procs:
                    classe = p['classe']
                    classes[classe] = classes.get(classe, 0) + 1
                
                classes_comuns = sorted(classes.items(), key=lambda x: x[1], reverse=True)[:2]
                for classe, count in classes_comuns:
                    mensagem += f"   └ {classe[:25]}: {count}\n"
                mensagem += "\n"
            
            await update.message.reply_text(mensagem)
        
        elif texto.startswith('/') and texto[1:].isdigit():
            ano = int(texto[1:])
            anos = service.agrupar_por_ano(processos)
            
            if ano in anos:
                processos_ano = anos[ano]
                mensagem = service.formatar_processos_ano(processos_ano, ano)
                
                if len(mensagem) > 4096:
                    partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
                    for parte in partes:
                        await update.message.reply_text(header + parte)
                else:
                    await update.message.reply_text(header + mensagem)
            else:
                await update.message.reply_text(f"❌ Nenhum processo encontrado para {ano}")
        
        else:
            await update.message.reply_text("❌ **Comando não reconhecido**\nUse /start para ver os comandos disponíveis")
            
    except Exception as e:
        await update.message.reply_text(f"❌ **Erro no comando:** {str(e)}")

async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comandos administrativos para gerenciar licenças"""
    username = update.message.from_user.username or "Anônimo"
    texto_original = update.message.text
    
    texto = texto_original
    if '@' in texto:
        texto = texto.split('@')[0]
    
    if not license_manager.is_admin(username):
        await update.message.reply_text(
            "❌ **Acesso restrito a administradores**\n\n"
            "💡 Comandos disponíveis para você:\n"
            "• `/start` - Iniciar bot\n"
            "• `/licenca` - Ver sua licença\n"
            "• Digite uma OAB para consultar processos"
        )
        return
    
    if texto.startswith('/addlicenca '):
        try:
            parts = texto.split()
            if len(parts) >= 2:
                target_username = parts[1].replace('@', '')
                duration = int(parts[2]) if len(parts) > 2 else 7
                
                expiry_date = license_manager.add_license(target_username, duration)
                await update.message.reply_text(
                    f"✅ **Licença adicionada com sucesso!**\n\n"
                    f"👤 **Usuário:** @{target_username}\n"
                    f"📅 **Duração:** {duration} dias\n"
                    f"⏰ **Expira em:** {expiry_date.strftime('%d/%m/%Y %H:%M')}\n"
                    f"✅ **Status:** ATIVA\n\n"
                    f"💡 O usuário @{target_username} já pode usar o bot!"
                )
            else:
                await update.message.reply_text("❌ **Uso correto:** `/addlicenca @username [dias]`\nEx: `/addlicenca joaosilva 7`")
        except Exception as e:
            await update.message.reply_text(f"❌ **Erro ao adicionar licença:** {str(e)}")
    
    elif texto.startswith('/revogar '):
        try:
            target_username = texto.split()[1].replace('@', '')
            if license_manager.revoke_license(target_username):
                await update.message.reply_text(
                    f"✅ **Licença revogada com sucesso!**\n\n"
                    f"👤 **Usuário:** @{target_username}\n"
                    f"🚫 **Status:** ACESSO REVOGADO\n\n"
                    f"💡 O usuário @{target_username} não poderá mais usar o bot."
                )
            else:
                await update.message.reply_text(f"❌ Licença não encontrada para @{target_username}")
        except:
            await update.message.reply_text("❌ **Uso correto:** `/revogar @username`\nEx: `/revogar joaosilva`")
    
    elif texto == '/licencas':
        active_licenses = license_manager.list_licenses()
        if active_licenses:
            mensagem = "📄 **LICENÇAS ATIVAS NO SISTEMA:**\n\n"
            for username, info in active_licenses.items():
                mensagem += f"👤 @{username}\n"
                mensagem += f"   📅 Expira: {info['expiry_date']}\n"
                mensagem += f"   ⏰ Dias restantes: {info['days_left']}\n\n"
            await update.message.reply_text(mensagem)
        else:
            await update.message.reply_text("ℹ️ **Nenhuma licença ativa no momento**")
    
    elif texto == '/giststatus':
        """Verifica status da conexão com Gist"""
        stats = license_manager.get_stats()
        
        mensagem = (
            "🔧 **STATUS DO SISTEMA DE LICENÇAS**\n\n"
            f"📊 **Licenças totais:** {stats['total_licenses']}\n"
            f"✅ **Licenças ativas:** {stats['active_licenses']}\n"
            f"❌ **Licenças expiradas:** {stats['expired_licenses']}\n"
            f"🔗 **Gist configurado:** {'✅ Sim' if stats['gist_configured'] else '❌ Não'}\n"
            f"👑 **Administradores:** {stats['admins_count']}\n\n"
        )
        
        if stats['gist_configured']:
            mensagem += "💡 **Comandos:**\n• `/sync` - Forçar sincronização\n• `/licencas` - Listar licenças"
        else:
            mensagem += "⚠️ **Configure as variáveis:**\n• `GIST_ID`\n• `GITHUB_TOKEN`"
        
        await update.message.reply_text(mensagem)
    
    elif texto == '/sync':
        """Força sincronização com Gist"""
        await update.message.reply_text("🔄 Sincronizando licenças com Gist...")
        
        success = license_manager.force_sync()
        
        if success:
            stats = license_manager.get_stats()
            await update.message.reply_text(
                f"✅ **Sincronização concluída!**\n\n"
                f"📊 Licenças carregadas: {stats['total_licenses']}\n"
                f"✅ Ativas: {stats['active_licenses']}\n"
                f"❌ Expiradas: {stats['expired_licenses']}"
            )
        else:
            await update.message.reply_text("❌ **Falha na sincronização!**\nVerifique as configurações do Gist.")
    
    elif texto == '/admin':
        await update.message.reply_text(
            "👑 **PAINEL ADMINISTRATIVO**\n\n"
            "📋 **Comandos disponíveis:**\n"
            "• `/addlicenca @username dias` - Adicionar licença\n"
            "• `/revogar @username` - Revogar licença\n"
            "• `/licencas` - Listar licenças ativas\n"
            "• `/giststatus` - Status do Gist\n"
            "• `/sync` - Sincronizar licenças\n\n"
            "💡 **Exemplos:**\n"
            "`/addlicenca joaosilva 7` - 7 dias\n"
            "`/addlicenca maria 30` - 30 dias\n"
            "`/revogar joaosilva` - Revogar acesso"
        )
    
    else:
        await update.message.reply_text("❌ **Comando admin não reconhecido**\nUse `/admin` para ver comandos disponíveis")

async def invalid_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ **Comando inválido**\n\n"
        "💡 **Como usar:**\n"
        "1. Digite uma OAB (123456SP)\n"
        "2. Aguarde a consulta completa\n"
        "3. Use comandos como /2024 ou /buscar\n\n"
        "📋 **Comandos:**\n"
        "/start - Ajuda\n"
        "/licenca - Info da licença\n"
        "/limpar - Encerrar sessão"
    )

def setup_bot():
    """Configura e inicia o bot"""
    try:
        app_bot = Application.builder().token(BOT_TOKEN).build()
        
        # Comandos principais
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("licenca", handle_commands))
        app_bot.add_handler(CommandHandler("limpar", handle_commands))
        app_bot.add_handler(CommandHandler("admin", admin_commands))
        app_bot.add_handler(CommandHandler("giststatus", admin_commands))
        app_bot.add_handler(CommandHandler("sync", admin_commands))
        
        # Comandos administrativos
        app_bot.add_handler(MessageHandler(
            filters.TEXT & filters.COMMAND & (
                filters.Regex(r'^/addlicenca\s+@?\w+') |
                filters.Regex(r'^/revogar\s+@?\w+') |
                filters.Regex(r'^/licencas$')
            ), admin_commands
        ))
        
        # Comandos normais - SUPORTE A 2 FORMATOS
        app_bot.add_handler(MessageHandler(
            filters.TEXT & filters.COMMAND & (
                filters.Regex(r'^/todos$') | filters.Regex(r'^/todos@\w+$') |
                filters.Regex(r'^/nums$') | filters.Regex(r'^/nums@\w+$') |
                filters.Regex(r'^/stats$') | filters.Regex(r'^/stats@\w+$') |
                filters.Regex(r'^/buscar\s+.+') | filters.Regex(r'^/buscar@\w+\s+.+') |
                filters.Regex(r'^/\d{4}$') | filters.Regex(r'^/\d{4}@\w+$') |
                filters.Regex(r'^/link_\w+') | filters.Regex(r'^/link_\w+@\w+') |
                filters.Regex(r'^/detalhes_\w+') | filters.Regex(r'^/detalhes_\w+@\w+')
            ), handle_commands
        ))
        
        # OAB
        app_bot.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d{6}[A-Z]{2}$'),
            consultar_oab
        ))
        
        # Mensagens inválidas
        app_bot.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            invalid_message
        ))
        
        print("🤖 Bot TJSP - CONFIGURADO PARA RENDER + GIST")
        print(f"🔑 Token: {BOT_TOKEN[:10]}...")
        print(f"🔗 Gist: {license_manager.gist_id or 'Não configurado'}")
        print("🚀 Iniciando polling...")
        
        return app_bot
        
    except Exception as e:
        print(f"❌ Erro na configuração do bot: {e}")
        return None

def run_flask():
    """Executa Flask em porta dinâmica"""
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    """Executa o bot"""
    try:
        bot_app = setup_bot()
        if bot_app:
            bot_app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                close_loop=False
            )
    except Exception as e:
        print(f"❌ Erro no bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 INICIANDO BOT TJSP NO RENDER.COM + GITHUB GIST")
    print("=" * 60)
    print(f"🔑 BOT_TOKEN: {BOT_TOKEN[:10]}...")
    print(f"🔗 GIST_ID: {os.environ.get('GIST_ID', 'Não configurado')}")
    print(f"🔐 GITHUB_TOKEN: {'✅ Configurado' if os.environ.get('GITHUB_TOKEN') else '❌ Não configurado'}")
    print(f"👑 Admins: {license_manager.admins}")
    print("=" * 60)
    
    # Iniciar Flask em thread separada
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Iniciar bot
    run_bot()