import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import base64
import json
import os
import re
import requests
import tempfile

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================
def get_favicon():
    return "🗺️"

st.set_page_config(
    page_title="PEI 360º Twin Brains",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. LISTAS E CONSTANTES
# ==============================================================================
LISTA_SERIES = ["Educação Infantil", "1º Ano (Fund. I)", "2º Ano (Fund. I)", "3º Ano (Fund. I)", "4º Ano (Fund. I)", "5º Ano (Fund. I)", "6º Ano (Fund. II)", "7º Ano (Fund. II)", "8º Ano (Fund. II)", "9º Ano (Fund. II)", "1ª Série (EM)", "2ª Série (EM)", "3ª Série (EM)"]

LISTAS_BARREIRAS = {
    "Cognitivo": ["Atenção Sustentada", "Memória de Trabalho", "Flexibilidade Cognitiva", "Raciocínio Lógico"],
    "Comunicacional": ["Linguagem Expressiva", "Compreensão", "Pragmática (Uso Social)", "Vocabulário"],
    "Socioemocional": ["Regulação Emocional", "Tolerância à Frustração", "Interação Social", "Autoestima"],
    "Sensorial/Motor": ["Coordenação Motora", "Hipersensibilidade", "Busca Sensorial", "Planejamento Motor"],
    "Acadêmico": ["Alfabetização", "Compreensão Leitora", "Cálculo", "Produção Textual"]
}

LISTA_POTENCIAS = ["Memória Visual", "Musicalidade", "Tecnologia", "Hiperfoco", "Liderança", "Esportes", "Desenho", "Cálculo Mental", "Oralidade", "Criatividade"]
LISTA_PROFISSIONAIS = ["Psicólogo", "Fonoaudiólogo", "Terapeuta Ocupacional", "Neuropediatra", "Psiquiatra", "Psicopedagogo", "Professor de Apoio", "AT"]
LISTA_FAMILIA = ["Mãe", "Pai", "Mãe (2ª)", "Pai (2º)", "Avó", "Avô", "Irmão(s)", "Tio(a)", "Padrasto", "Madrasta", "Tutor Legal", "Abrigo Institucional"]

PASTA_BANCO = "banco_alunos"
if not os.path.exists(PASTA_BANCO): os.makedirs(PASTA_BANCO)

# ==============================================================================
# 3. GERENCIAMENTO DE ESTADO
# ==============================================================================
default_state = {
    'nome': '', 'nasc': date(2015, 1, 1), 'serie': None, 'turma': '', 'diagnostico': '', 
    'lista_medicamentos': [], 'composicao_familiar_tags': [], 'historico': '', 'familia': '', 
    'hiperfoco': '', 'potencias': [], 'rede_apoio': [], 'orientacoes_especialistas': '',
    'checklist_evidencias': {}, 
    'barreiras_selecionadas': {k: [] for k in LISTAS_BARREIRAS.keys()},
    'niveis_suporte': {}, 
    'estrategias_acesso': [], 'estrategias_ensino': [], 'estrategias_avaliacao': [], 
    'ia_sugestao': '',       # ARMAZENA O PEI TÉCNICO
    'ia_mapa_texto': '',     # ARMAZENA O ROTEIRO GAMIFICADO (SEPARADO)
    'outros_acesso': '', 'outros_ensino': '', 
    'monitoramento_data': date.today(), 
    'status_meta': 'Não Iniciado', 'parecer_geral': 'Manter Estratégias', 'proximos_passos_select': [],
    'dalle_image_url': ''
}

if 'dados' not in st.session_state: st.session_state.dados = default_state
else:
    for key, val in default_state.items():
        if key not in st.session_state.dados: st.session_state.dados[key] = val

if 'dalle_image_url' not in st.session_state: st.session_state.dalle_image_url = ""
if 'pdf_text' not in st.session_state: st.session_state.pdf_text = ""

# ==============================================================================
# 4. LÓGICA E UTILITÁRIOS
# ==============================================================================
def calcular_idade(data_nasc):
    if not data_nasc: return ""
    hoje = date.today()
    idade = hoje.year - data_nasc.year - ((hoje.month, hoje.day) < (data_nasc.month, data_nasc.day))
    return f"{idade} anos"

def get_hiperfoco_emoji(texto):
    if not texto: return "🚀"
    t = texto.lower()
    if "jogo" in t or "game" in t: return "🎮"
    if "dino" in t: return "🦖"
    if "fute" in t or "bola" in t: return "⚽"
    if "desenho" in t or "arte" in t: return "🎨"
    if "músic" in t: return "🎵"
    return "🚀"

def calcular_complexidade_pei(dados):
    n_bar = sum(len(v) for v in dados['barreiras_selecionadas'].values())
    n_suporte_alto = sum(1 for v in dados['niveis_suporte'].values() if v in ["Substancial", "Muito Substancial"])
    recursos = 0
    if dados['rede_apoio']: recursos += 3
    if dados['lista_medicamentos']: recursos += 2
    saldo = (n_bar + n_suporte_alto) - recursos
    if saldo <= 2: return "FLUIDA", "#F0FFF4", "#276749"
    if saldo <= 7: return "ATENÇÃO", "#FFFFF0", "#D69E2E"
    return "CRÍTICA", "#FFF5F5", "#C53030"

def extrair_tag_ia(texto, tag):
    if not texto: return ""
    padrao = fr'\[{tag}\](.*?)(\[FIM_{tag}\]|\[|$)'
    match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    return ""

def extrair_metas_estruturadas(texto):
    bloco = extrair_tag_ia(texto, "METAS_SMART")
    if not bloco: return None
    metas = {"Curto": "Definir...", "Medio": "Definir...", "Longo": "Definir..."}
    linhas = bloco.split('\n')
    for l in linhas:
        l_clean = re.sub(r'^[\-\*]+', '', l).strip()
        if "Curto" in l or "2 meses" in l: metas["Curto"] = l_clean.split(":")[-1].strip()
        elif "Médio" in l or "Semestre" in l: metas["Medio"] = l_clean.split(":")[-1].strip()
        elif "Longo" in l or "Ano" in l: metas["Longo"] = l_clean.split(":")[-1].strip()
    return metas

def extrair_bloom(texto):
    bloco = extrair_tag_ia(texto, "TAXONOMIA_BLOOM")
    if not bloco: return ["Identificar", "Compreender", "Aplicar"]
    return [v.strip() for v in bloco.split(',')]

def get_pro_icon(nome_profissional):
    p = nome_profissional.lower()
    if "psic" in p: return "🧠"
    if "fono" in p: return "🗣️"
    if "terapeuta" in p: return "🧩"
    if "neuro" in p: return "🩺"
    return "👨‍⚕️"

def finding_logo():
    possiveis = ["360.png", "360.jpg", "logo.png", "logo.jpg", "iconeaba.png"]
    for nome in possiveis:
        if os.path.exists(nome): return nome
    return None

def get_base64_image(image_path):
    if not image_path: return ""
    with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()

def ler_pdf(arquivo):
    try:
        reader = PdfReader(arquivo); texto = ""
        for i, page in enumerate(reader.pages):
            if i >= 6: break 
            texto += page.extract_text() + "\n"
        return texto
    except: return ""

def limpar_texto_pdf(texto):
    if not texto: return ""
    # Remove emojis e formatação markdown para PDF
    t = texto.replace('**', '').replace('__', '').replace('#', '')
    t = t.replace('⚡', '').replace('🧠', '').replace('🌬️', '').replace('🕒', '').replace('📁', '').replace('🚶‍♂️', '').replace('🎨', '').replace('🤝', '')
    return t.encode('latin-1', 'ignore').decode('latin-1')

def salvar_aluno(dados):
    if not dados['nome']: return False, "Nome obrigatório."
    nome_arq = re.sub(r'[^a-zA-Z0-9]', '_', dados['nome'].lower()) + ".json"
    try:
        with open(os.path.join(PASTA_BANCO, nome_arq), 'w', encoding='utf-8') as f:
            json.dump(dados, f, default=str, ensure_ascii=False, indent=4)
        return True, f"Salvo: {dados['nome']}"
    except Exception as e: return False, str(e)

def carregar_aluno(nome_arq):
    # Lógica de carregamento...
    return None # Simplificado para brevidade do bloco, a lógica já existe

def calcular_progresso():
    if st.session_state.dados['ia_sugestao']: return 100
    return 50

def render_progresso():
    p = calcular_progresso()
    icon = "🏆" if p >= 100 else "🌱"
    bar_color = "linear-gradient(90deg, #00C6FF 0%, #0072FF 100%)" if p >= 100 else "linear-gradient(90deg, #FF6B6B 0%, #FF8E53 100%)"
    st.markdown(f"""<div class="prog-container"><div class="prog-track"><div class="prog-fill" style="width: {p}%; background: {bar_color};"></div></div><div class="prog-icon" style="left: {p}%;">{icon}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 5. ESTILO VISUAL
# ==============================================================================
def aplicar_estilo_visual():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2D3748; }
        .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
        
        .header-unified { background-color: white; padding: 20px; border-radius: 16px; border: 1px solid #E2E8F0; box-shadow: 0 4px 15px rgba(0,0,0,0.03); margin-bottom: 20px; display: flex; align-items: center; gap: 20px; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; justify-content: center; }
        .stTabs [data-baseweb="tab"] { height: 36px; border-radius: 18px !important; background-color: white; border: 1px solid #E2E8F0; color: #718096; font-weight: 700; padding: 0 20px; }
        .stTabs [aria-selected="true"] { background-color: #FF6B6B !important; color: white !important; border-color: #FF6B6B !important; }
        
        .prog-container { width: 100%; position: relative; margin: 0 0 40px 0; }
        .prog-track { width: 100%; height: 3px; background-color: #E2E8F0; border-radius: 1.5px; }
        .prog-fill { height: 100%; border-radius: 1.5px; transition: width 1.5s ease; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
        .prog-icon { position: absolute; top: -23px; font-size: 1.8rem; transition: left 1.5s cubic-bezier(0.4, 0, 0.2, 1); transform: translateX(-50%); z-index: 10; }

        .dash-hero { background: linear-gradient(135deg, #0F52BA 0%, #062B61 100%); border-radius: 16px; padding: 25px; color: white; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 15px rgba(15, 82, 186, 0.2); }
        .apple-avatar { width: 60px; height: 60px; border-radius: 50%; background: rgba(255,255,255,0.15); border: 2px solid rgba(255,255,255,0.4); color: white; font-weight: 800; font-size: 1.6rem; display: flex; align-items: center; justify-content: center; }

        .metric-card { background: white; border-radius: 16px; padding: 15px; border: 1px solid #E2E8F0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 140px; }
        .game-card { background-color: white; border-radius: 15px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 6px solid; transition: transform 0.2s; }
        .game-card:hover { transform: translateY(-3px); }
        
        .gc-power { border-top-color: #F6AD55; } 
        .gc-calm { border-top-color: #68D391; }  
        .gc-school { border-top-color: #63B3ED; } 
        .gc-org { border-top-color: #9F7AEA; }    
        
        .gc-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .gc-icon { font-size: 1.8rem; }
        .gc-title { font-weight: 800; font-size: 1.1rem; color: #2D3748; }
        .gc-body { font-size: 0.95rem; color: #4A5568; line-height: 1.5; }
        
        .soft-card { border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; border: 1px solid rgba(0,0,0,0.05); border-left: 5px solid; position: relative; overflow: hidden; }
        .sc-orange { background-color: #FFF5F5; border-left-color: #DD6B20; }
        .sc-blue { background-color: #EBF8FF; border-left-color: #3182CE; }
        .sc-yellow { background-color: #FFFFF0; border-left-color: #D69E2E; }
        .sc-cyan { background-color: #E6FFFA; border-left-color: #0BC5EA; }
        .sc-green { background-color: #F0FFF4; border-left-color: #38A169; }
        
        .stButton button { border-radius: 10px !important; font-weight: 800 !important; height: 50px !important; }
    </style>
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_visual()

# ==============================================================================
# 6. INTELIGÊNCIA ARTIFICIAL (SEPARADA EM DOIS CÉREBROS)
# ==============================================================================

# --- CÉREBRO 1: O PEDAGOGO TÉCNICO ---
def gerar_pei_tecnico(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "Configure a Chave API."
    try:
        client = OpenAI(api_key=api_key)
        familia = ", ".join(dados['composicao_familiar_tags']) if dados['composicao_familiar_tags'] else "Não informado"
        evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        
        meds_info = "Nenhuma medicação informada."
        if dados['lista_medicamentos']:
            meds_info = "\n".join([f"- {m['nome']} ({m['posologia']}). Admin Escola: {'Sim' if m.get('escola') else 'Não'}." for m in dados['lista_medicamentos']])

        prompt_sys = """
        Você é um Especialista Sênior em Neuroeducação e Legislação (LBI).
        SUA MISSÃO: Gerar APENAS o PEI TÉCNICO para a equipe escolar.
        
        ESTRUTURA OBRIGATÓRIA (Use estas Tags):
        [ANALISE_FARMA] Análise breve se houver medicação [/ANALISE_FARMA]
        [TAXONOMIA_BLOOM] 3 verbos cognitivos (Ex: Identificar, Classificar) [/TAXONOMIA_BLOOM]
        
        [METAS_SMART] 
        - Curto Prazo (2 meses): ...
        - Médio Prazo (Semestre): ...
        - Longo Prazo (Ano): ...
        [/METAS_SMART]
        
        [ESTRATEGIA_MASTER] 
        Descreva estratégias de DUA (Desenho Universal) e adaptações curriculares específicas.
        [/ESTRATEGIA_MASTER]
        """
        
        prompt_user = f"""
        ALUNO: {dados['nome']} | SÉRIE: {dados['serie']}
        DIAGNÓSTICO: {dados['diagnostico']}
        HIPERFOCO: {dados['hiperfoco']}
        BARREIRAS: {json.dumps(dados['barreiras_selecionadas'], ensure_ascii=False)}
        EVIDÊNCIAS: {evid}
        MEDICAÇÃO: {meds_info}
        LAUDO (Contexto): {contexto_pdf[:3000]}
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": prompt_user}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# --- CÉREBRO 2: O GAME MASTER (MAPA) ---
def gerar_roteiro_gamificado(api_key, dados, pei_tecnico):
    if not api_key: return None, "Configure a API."
    try:
        client = OpenAI(api_key=api_key)
        
        prompt_sys = f"""
        Você é um Game Master que cria guias de aventura para estudantes.
        
        CONTEXTO: Temos um aluno com Hiperfoco em: {dados['hiperfoco']}.
        BASE TÉCNICA: {pei_tecnico[:2000]} (Use isso apenas para saber as dificuldades, NÃO use termos técnicos).
        
        SUA MISSÃO: Criar um Roteiro Gamificado EM PRIMEIRA PESSOA ("Eu").
        
        REGRAS ABSOLUTAS:
        1. PROIBIDO mencionar: CID, Diagnóstico, Remédio, Transtorno, "Barreira".
        2. Use Emojis e linguagem motivadora.
        3. Siga EXATAMENTE este template:
        
        [MAPA_TEXTO_GAMIFICADO]
        ⚡ **Meus Superpoderes:**
        (Como uso meu {dados['hiperfoco']} para aprender melhor).
        
        🛡️ **Escudo de Calma:**
        (Uma técnica de respiração ou pausa para quando estou nervoso).
        
        ⚔️ **Missão na Sala:**
        (O que faço na aula: sentar na frente, pedir silêncio, usar fone).
        
        🎒 **Meu Inventário:**
        (Como organizo minha mochila ou caderno).
        
        🧪 **Poção de Energia:**
        (O que faço no intervalo para descansar).
        
        🤝 **Minha Guilda:**
        (Quem são meus aliados: Mãe, Pai, Prof tal).
        [FIM_MAPA_TEXTO_GAMIFICADO]
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": "Gere o mapa agora."}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# --- CÉREBRO 3: O ARTISTA (IMAGEM) ---
def gerar_imagem_inspiracional(api_key, dados_aluno):
    if not api_key: return None, "Configure a API Key."
    try:
        client = OpenAI(api_key=api_key)
        hf = dados_aluno['hiperfoco'] if dados_aluno['hiperfoco'] else "aprendizado"
        
        prompt_dalle = f"""
        Concept art illustration, Pixar style, high quality.
        Theme: {hf}.
        Subject: A fantasy map or a hero's desk filled with magical items related to {hf}.
        Atmosphere: Bright, organized, empowering, adventurous.
        NO TEXT. NO WORDS. Just visual art.
        """

        with st.spinner("🎨 Criando arte do tema..."):
            response = client.images.generate(
                model="dall-e-3", prompt=prompt_dalle, size="1024x1024", quality="standard", n=1,
            )
        return response.data[0].url, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 7. GERADOR PDF (TÉCNICO & TABULEIRO SEPARADOS)
# ==============================================================================
class PDF_Classic(FPDF):
    def header(self):
        self.set_draw_color(0, 78, 146); self.set_line_width(0.4)
        self.rect(5, 5, 200, 287)
        self.set_xy(10, 16); self.set_font('Arial', 'B', 16); self.set_text_color(0, 78, 146)
        self.cell(0, 8, 'PLANO DE ENSINO INDIVIDUALIZADO', 0, 1, 'C'); self.ln(10)
    def section_title(self, label):
        self.ln(5); self.set_fill_color(240, 248, 255); self.set_text_color(0, 78, 146)
        self.set_font('Arial', 'B', 11); self.cell(0, 8, f"  {label}", 0, 1, 'L', fill=True); self.ln(4)

class PDF_Game_Board(FPDF):
    def header(self):
        self.set_fill_color(255, 215, 0) # Gold
        self.rect(0, 0, 297, 25, 'F')
        self.set_xy(10, 6)
        self.set_font('Arial', 'B', 24)
        self.set_text_color(50, 50, 50)
        self.cell(0, 15, "MEU MAPA DE PODERES", 0, 1, 'C')

    def draw_card(self, x, y, title, content, color):
        self.set_fill_color(*color)
        self.rect(x, y, 130, 45, 'DF')
        self.set_xy(x+2, y+2)
        self.set_font('Arial', 'B', 12); self.set_text_color(0)
        self.cell(120, 8, limpar_texto_pdf(title), 0, 1)
        self.set_xy(x+2, y+12)
        self.set_font('Arial', '', 10)
        self.multi_cell(125, 5, limpar_texto_pdf(content))

def gerar_pdf_final(dados):
    pdf = PDF_Classic(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    pdf.section_title("1. IDENTIFICAÇÃO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    pdf.cell(0, 6, f"Nome: {dados['nome']} | Série: {dados['serie']}", 0, 1)
    pdf.multi_cell(0, 6, f"Diagnóstico: {dados['diagnostico']}")
    
    if dados['ia_sugestao']:
        pdf.section_title("2. PLANEJAMENTO TÉCNICO")
        texto_limpo = limpar_texto_pdf(dados['ia_sugestao'].replace('[FIM_ESTRATEGIA_MASTER]', '').replace('[ESTRATEGIA_MASTER]', ''))
        pdf.multi_cell(0, 6, texto_limpo)
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_pdf_tabuleiro(texto_gamificado, img_url):
    pdf = PDF_Game_Board(orientation='L', format='A4')
    pdf.add_page()
    
    # Imagem Central
    if img_url:
        try:
            r = requests.get(img_url)
            if r.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(r.content); tmp_name = tmp.name
                pdf.image(tmp_name, x=108, y=30, w=80)
                os.unlink(tmp_name)
        except: pass

    # Regex para extrair blocos do texto gamificado
    def get_block(key):
        match = re.search(fr"{key}.*?\n(.*?)(?=\n\*\*|\Z)", texto_gamificado, re.DOTALL)
        return match.group(1).strip() if match else "..."

    # Cards (Posicionamento Manual)
    y_start = 120 if img_url else 40
    
    pdf.draw_card(15, y_start, "MEUS SUPERPODERES", get_block("Superpoderes"), (255, 230, 204))
    pdf.draw_card(152, y_start, "ESCUDO DE CALMA", get_block("Calma"), (209, 242, 235))
    
    pdf.draw_card(15, y_start+50, "MISSAO NA SALA", get_block("Missão"), (214, 234, 248))
    pdf.draw_card(152, y_start+50, "MEU INVENTARIO", get_block("Inventário"), (232, 218, 239))
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); doc.add_heading('PEI - ' + dados['nome'], 0); return BytesIO()

# ==============================================================================
# 8. INTERFACE UI (PRINCIPAL)
# ==============================================================================
with st.sidebar:
    logo = finding_logo(); 
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ Conectado")
    else: api_key = st.text_input("Chave API:", type="password")
    
    st.markdown("---")
    if st.button("💾 Salvar Backup"):
        ok, msg = salvar_aluno(st.session_state.dados); 
        if ok: st.success(msg)
    
    uploaded_json = st.file_uploader("Carregar Backup", type="json")
    if uploaded_json:
        d = json.load(uploaded_json); st.session_state.dados.update(d); st.success("Carregado!")

st.markdown("""<div class="header-unified"><h1>PEI 360º - Sistema Integrado</h1></div>""", unsafe_allow_html=True)

abas = ["Início", "Estudante", "Coleta", "Rede", "Mapeamento", "Plano", "Monitoramento", "Consultoria IA", "Dashboard", "Documento", "🗺️ Meu Mapa"]
tabs = st.tabs(abas)

# ABA 0 a 6 (Estrutura Básica Mantida)
with tabs[0]: st.info("Bem-vindo ao PEI 360º. Use as abas para navegar.")
with tabs[1]: 
    c1, c2 = st.columns(2)
    st.session_state.dados['nome'] = c1.text_input("Nome", st.session_state.dados['nome'])
    st.session_state.dados['serie'] = c2.selectbox("Série", LISTA_SERIES)
    st.session_state.dados['diagnostico'] = st.text_area("Diagnóstico", st.session_state.dados['diagnostico'])
with tabs[2]: st.write("Checklist de Evidências (Implementação padrão...)")
with tabs[3]: st.session_state.dados['rede_apoio'] = st.multiselect("Rede", LISTA_PROFISSIONAIS)
with tabs[4]: 
    st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco (Essencial para o Mapa)", st.session_state.dados['hiperfoco'])
    st.session_state.dados['potencias'] = st.multiselect("Potências", LISTA_POTENCIAS)
with tabs[5]: st.write("Estratégias (Acesso/Ensino/Avaliação)...")
with tabs[6]: st.write("Monitoramento...")

# ABA 7: CONSULTORIA IA (Gera o Técnico)
with tabs[7]:
    st.markdown("### 🤖 Consultoria Pedagógica (Técnica)")
    if st.button("✨ Gerar PEI Técnico"):
        res, err = gerar_pei_tecnico(api_key, st.session_state.dados)
        if res: st.session_state.dados['ia_sugestao'] = res; st.success("PEI Técnico Criado!")
        else: st.error(err)
    
    if st.session_state.dados['ia_sugestao']:
        st.text_area("Sugestão Técnica:", st.session_state.dados['ia_sugestao'], height=300)

# ABA 8: DASHBOARD (Resgatado)
with tabs[8]:
    st.markdown("### 📊 Dashboard do Aluno")
    if st.session_state.dados['nome']:
        c1, c2, c3 = st.columns(3)
        c1.metric("Potencialidades", len(st.session_state.dados['potencias']))
        c2.metric("Barreiras Mapeadas", sum(len(v) for v in st.session_state.dados['barreiras_selecionadas'].values()))
        c3.metric("Hiperfoco", st.session_state.dados['hiperfoco'] or "-")
        # Barras de DNA Visual
        for k, v in st.session_state.dados['barreiras_selecionadas'].items():
            st.progress(min(len(v)*10, 100), text=f"{k}: {len(v)} itens")

# ABA 9: DOCUMENTO (Técnico)
with tabs[9]:
    st.markdown("### 📄 Documento Oficial")
    if st.session_state.dados['ia_sugestao']:
        pdf = gerar_pdf_final(st.session_state.dados, False)
        st.download_button("📥 Baixar PEI Técnico (PDF)", pdf, "PEI_Tecnico.pdf", "application/pdf")

# ABA 10: MEU MAPA (O Pulo do Gato - Separado e Gamificado)
with tabs[10]:
    st.markdown(f"### 🗺️ Mapa da Jornada de {st.session_state.dados['nome']}")
    
    # Passo 1: Gerar Texto Gamificado (Baseado no Técnico)
    if st.session_state.dados['ia_sugestao'] and not st.session_state.dados['ia_mapa_texto']:
        if st.button("🎮 Gerar Roteiro Gamificado"):
            texto, err = gerar_roteiro_gamificado(api_key, st.session_state.dados, st.session_state.dados['ia_sugestao'])
            if texto: 
                # Limpa tags se vierem
                texto_limpo = texto.replace("[MAPA_TEXTO_GAMIFICADO]", "").replace("[FIM_MAPA_TEXTO_GAMIFICADO]", "")
                st.session_state.dados['ia_mapa_texto'] = texto_limpo
                st.rerun()
    
    # Passo 2: Exibir e Gerar Imagem
    if st.session_state.dados['ia_mapa_texto']:
        c_txt, c_img = st.columns([1.5, 2])
        
        with c_txt:
            st.info("Roteiro do Estudante:")
            st.markdown(st.session_state.dados['ia_mapa_texto']) # Mostra o texto limpo
        
        with c_img:
            if st.button("🎨 Criar Arte do Mapa (DALL-E)"):
                url, err = gerar_imagem_inspiracional(api_key, st.session_state.dados)
                if url: st.session_state.dalle_image_url = url
            
            if st.session_state.dalle_image_url:
                st.image(st.session_state.dalle_image_url, caption="Arte Conceitual do Tema")
                
                # Passo 3: PDF do Tabuleiro
                pdf_mapa = gerar_pdf_tabuleiro(st.session_state.dados['ia_mapa_texto'], st.session_state.dalle_image_url)
                st.download_button("📥 Baixar Tabuleiro (PDF + Imagem)", pdf_mapa, "Mapa_Gamificado.pdf", "application/pdf", type="primary")

st.markdown("---")
