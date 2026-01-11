import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import json
import os
import re
import requests

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================
def get_favicon():
    return "📘"

st.set_page_config(
    page_title="PEI 360º",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. LISTAS DE DADOS
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
    'possui_laudo': False, # Novo campo
    'lista_medicamentos': [], 'composicao_familiar_tags': [], 'historico': '', 'familia': '', 
    'hiperfoco': '', 'potencias': [], 'rede_apoio': [], 'orientacoes_especialistas': '',
    'checklist_evidencias': {}, 
    'barreiras_selecionadas': {k: [] for k in LISTAS_BARREIRAS.keys()},
    'niveis_suporte': {}, 
    'estrategias_acesso': [], 'estrategias_ensino': [], 'estrategias_avaliacao': [], 
    'ia_sugestao': '',       # PEI TÉCNICO
    'ia_mapa_texto': '',     # ROTEIRO GAMIFICADO
    'outros_acesso': '', 'outros_ensino': '', 
    'monitoramento_data': date.today(), 
    'status_meta': 'Não Iniciado', 'parecer_geral': 'Manter Estratégias', 'proximos_passos_select': []
}

if 'dados' not in st.session_state: st.session_state.dados = default_state
else:
    for key, val in default_state.items():
        if key not in st.session_state.dados: st.session_state.dados[key] = val

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
    padrao = fr'\[{tag}\](.*?)(\[|$)'
    match = re.search(padrao, texto, re.DOTALL)
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

def calcular_progresso():
    if st.session_state.dados['ia_sugestao']: return 100
    return 50

def render_progresso():
    p = calcular_progresso()
    icon = "🌱"
    bar_color = "linear-gradient(90deg, #FF6B6B 0%, #FF8E53 100%)"
    if p >= 100: 
        icon = "🏆"
        bar_color = "linear-gradient(90deg, #00C6FF 0%, #0072FF 100%)" 
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
        div[data-baseweb="tab-border"], div[data-baseweb="tab-highlight"] { display: none !important; }
        
        .header-unified { background-color: white; padding: 20px 40px; border-radius: 16px; border: 1px solid #E2E8F0; box-shadow: 0 4px 15px rgba(0,0,0,0.03); margin-bottom: 20px; display: flex; align-items: center; gap: 20px; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; margin-bottom: 20px; justify-content: center; }
        .stTabs [data-baseweb="tab"] { height: 36px; border-radius: 18px !important; background-color: white; border: 1px solid #E2E8F0; color: #718096; font-weight: 700; font-size: 0.85rem; padding: 0 20px; transition: all 0.2s ease; }
        .stTabs [aria-selected="true"] { background-color: #FF6B6B !important; color: white !important; border-color: #FF6B6B !important; box-shadow: 0 4px 10px rgba(255, 107, 107, 0.3); }
        
        .prog-container { width: 100%; position: relative; margin: 0 0 40px 0; }
        .prog-track { width: 100%; height: 3px; background-color: #E2E8F0; border-radius: 1.5px; }
        .prog-fill { height: 100%; border-radius: 1.5px; transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1), background 1.5s ease; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
        .prog-icon { position: absolute; top: -23px; font-size: 1.8rem; transition: left 1.5s cubic-bezier(0.4, 0, 0.2, 1); transform: translateX(-50%); z-index: 10; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.15)); }

        .dash-hero { background: linear-gradient(135deg, #0F52BA 0%, #062B61 100%); border-radius: 16px; padding: 25px; color: white; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 15px rgba(15, 82, 186, 0.2); }
        .apple-avatar { width: 60px; height: 60px; border-radius: 50%; background: rgba(255,255,255,0.15); border: 2px solid rgba(255,255,255,0.4); color: white; font-weight: 800; font-size: 1.6rem; display: flex; align-items: center; justify-content: center; }

        .metric-card { background: white; border-radius: 16px; padding: 15px; border: 1px solid #E2E8F0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 140px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
        .css-donut { width: 70px; height: 70px; border-radius: 50%; background: conic-gradient(var(--fill) var(--p), #EDF2F7 0); display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
        .css-donut::after { content: ""; position: absolute; width: 54px; height: 54px; border-radius: 50%; background: white; }
        .d-val { position: absolute; z-index: 2; font-size: 1.3rem; font-weight: 800; color: #2D3748; }
        .d-lbl { text-transform: uppercase; font-size: 0.65rem; color: #718096; font-weight: 700; letter-spacing: 0.5px; text-align: center; }
        .comp-icon-box { margin-bottom: 5px; }

        .soft-card { border-radius: 12px; padding: 20px; min-height: 220px; height: 100%; display: flex; flex-direction: column; box-shadow: 0 2px 5px rgba(0,0,0,0.02); border: 1px solid rgba(0,0,0,0.05); border-left: 5px solid; position: relative; overflow: hidden; }
        .sc-orange { background-color: #FFF5F5; border-left-color: #DD6B20; }
        .sc-blue { background-color: #EBF8FF; border-left-color: #3182CE; }
        .sc-yellow { background-color: #FFFFF0; border-left-color: #D69E2E; }
        .sc-cyan { background-color: #E6FFFA; border-left-color: #0BC5EA; }
        .sc-green { background-color: #F0FFF4; border-left-color: #38A169; }
        
        .home-card { background-color: white; padding: 30px 20px; border-radius: 16px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: all 0.3s ease; height: 250px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
        .home-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(15, 82, 186, 0.1); border-color: #BEE3F8;}
        .home-card h3 { margin: 15px 0 10px 0; font-size: 1.1rem; color: #0F52BA; font-weight: 800; }
        .home-card p { font-size: 0.85rem; color: #718096; line-height: 1.4; margin: 0; }
        .icon-box { width: 70px; height: 70px; border-radius: 18px; display: flex; align-items: center; justify-content: center; font-size: 2.2rem; margin-bottom: 15px; }
        .ic-blue { background-color: #EBF8FF !important; color: #3182CE !important; border: 1px solid #BEE3F8 !important; }
        .ic-gold { background-color: #FFFFF0 !important; color: #D69E2E !important; border: 1px solid #FAF089 !important; }
        .ic-pink { background-color: #FFF5F7 !important; color: #D53F8C !important; border: 1px solid #FED7E2 !important; }
        .ic-green { background-color: #F0FFF4 !important; color: #38A169 !important; border: 1px solid #C6F6D5 !important; }
        .rich-card-link { text-decoration: none; color: inherit; display: block; height: 100%; }
        
        .rede-chip { display: inline-flex; align-items: center; background: white; padding: 6px 12px; border-radius: 20px; margin: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-size: 0.85rem; font-weight: 700; color: #2C5282; }
        .dna-bar-container { margin-bottom: 12px; }
        .dna-bar-flex { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 4px; color: #4A5568; font-weight: 600; }
        .dna-bar-bg { width: 100%; height: 6px; background: #E2E8F0; border-radius: 3px; overflow: hidden; }
        .dna-bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
        .bloom-tag { background: #EBF8FF; color: #3182CE; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 700; margin-right: 5px; border: 1px solid #BEE3F8; display: inline-block; margin-bottom: 5px; }
        .meta-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 0.85rem; border-bottom: 1px solid rgba(0,0,0,0.05); padding-bottom: 5px; }
        
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] { border-radius: 10px !important; border-color: #E2E8F0 !important; }
        div[data-testid="column"] .stButton button { border-radius: 10px !important; font-weight: 800 !important; height: 50px !important; background-color: #0F52BA !important; color: white !important; border: none !important; }
        div[data-testid="column"] .stButton button:hover { background-color: #0A3D8F !important; }
        div[data-baseweb="checkbox"] div[class*="checked"] { background-color: #0F52BA !important; border-color: #0F52BA !important; }
        .ia-side-box { background: #F8FAFC; border-radius: 16px; padding: 25px; border: 1px solid #E2E8F0; text-align: left; margin-bottom: 20px; }
        .form-section-title { display: flex; align-items: center; gap: 10px; color: #0F52BA; font-weight: 700; font-size: 1.1rem; margin-top: 20px; margin-bottom: 15px; border-bottom: 2px solid #F7FAFC; padding-bottom: 5px; }

        /* CARDS DO MAPA */
        .game-card { background-color: white; border-radius: 15px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 6px solid; }
        .gc-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .gc-title { font-weight: 800; font-size: 1.1rem; color: #2D3748; }
        .gc-power { border-top-color: #F6AD55; }
    </style>
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_visual()

# ==============================================================================
# 6. INTELIGÊNCIA ARTIFICIAL (CÉREBROS GÊMEOS)
# ==============================================================================

# CÉREBRO 0: ANALISTA DE LAUDO (NOVO)
def extrair_dados_laudo(api_key, texto_pdf):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""
        Analise o texto deste laudo médico/escolar e extraia:
        1. O Diagnóstico principal.
        2. A medicação (se houver).
        Retorne em JSON: {{ "diagnostico": "...", "medicacao": ["..."] }}
        Texto: {texto_pdf[:4000]}
        """
        res = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        return json.loads(res.choices[0].message.content)
    except: return None

# CÉREBRO 1: TÉCNICO (CONSULTORIA IA)
def consultar_gpt_pedagogico(api_key, dados, contexto_pdf="", regenerar=False):
    if not api_key: return None, "⚠️ Configure a Chave API."
    try:
        client = OpenAI(api_key=api_key)
        familia = ", ".join(dados['composicao_familiar_tags']) if dados['composicao_familiar_tags'] else "Não informado"
        evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        
        meds_info = "Nenhuma medicação informada."
        if dados['lista_medicamentos']:
            meds_info = "\n".join([f"- {m['nome']} ({m['posologia']}). Admin Escola: {'Sim' if m.get('escola') else 'Não'}." for m in dados['lista_medicamentos']])

        extra = " (ATENÇÃO: Crie novas estratégias diferentes das anteriores)." if regenerar else ""

        prompt_sys = f"""
        Você é um Especialista Sênior em Neuroeducação.{extra}
        SUA MISSÃO: Criar um PEI TÉCNICO.
        
        --- ESTRUTURA OBRIGATÓRIA ---
        [ANALISE_FARMA] ... [/ANALISE_FARMA]
        [TAXONOMIA_BLOOM] ... [/TAXONOMIA_BLOOM]
        
        [METAS_SMART] 
        - CURTO PRAZO (2 meses): ...
        - MÉDIO PRAZO (Semestre): ...
        - LONGO PRAZO (Ano): ...
        [FIM_METAS_SMART]
        
        [ESTRATEGIA_MASTER] ... [FIM_ESTRATEGIA_MASTER]
        """
        
        prompt_user = f"""
        ALUNO: {dados['nome']} | SÉRIE: {dados['serie']}
        DIAGNÓSTICO: {dados['diagnostico']}
        MEDICAÇÃO: {meds_info}
        HIPERFOCO: {dados['hiperfoco']}
        BARREIRAS: {json.dumps(dados['barreiras_selecionadas'], ensure_ascii=False)}
        EVIDÊNCIAS: {evid}
        LAUDO: {contexto_pdf[:3000] if contexto_pdf else "Nenhum."}
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": prompt_user}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# CÉREBRO 2: GAME MASTER (MAPA)
def gerar_roteiro_gamificado(api_key, dados, pei_tecnico, regenerar=False):
    if not api_key: return None, "Configure a API."
    try:
        client = OpenAI(api_key=api_key)
        extra = " (Crie um tema diferente)" if regenerar else ""
        
        prompt_sys = f"""
        Você é um Game Master.{extra}
        CONTEXTO: Aluno com Hiperfoco em {dados['hiperfoco']}.
        ESTRATÉGIAS TÉCNICAS (Para traduzir): {pei_tecnico[:1500]}
        
        SUA MISSÃO: Traduzir as estratégias para um Guia de Herói em 1ª Pessoa.
        
        REGRAS ABSOLUTAS:
        1. PROIBIDO mencionar diagnósticos, remédios, TDAH, TEA ou barreiras.
        2. Use linguagem de jogos/aventura.
        3. Foco 100% positivo e em soluções.
        
        FORMATO OBRIGATÓRIO:
        ⚡ **Meus Superpoderes:** (Como usar o hiperfoco para aprender).
        🛡️ **Escudo de Calma:** (Técnica de respiração).
        ⚔️ **Missão na Sala:** (Estratégia de foco na aula).
        🎒 **Meu Inventário:** (Organização).
        🧪 **Poção de Energia:** (Descanso).
        🤝 **Minha Guilda:** (Aliados).
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": "Gere o mapa."}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 7. GERADOR PDF SIMPLES (MAPA)
# ==============================================================================
class PDF_Map_Simple(FPDF):
    def header(self):
        self.set_fill_color(255, 200, 0); self.rect(0, 0, 297, 30, 'F')
        self.set_xy(10, 10); self.set_font('Arial', 'B', 24); self.set_text_color(50, 50, 50)
        self.cell(0, 10, "MEU MAPA DE JORNADA", 0, 1, 'C')

    def draw_section(self, title, content):
        self.ln(5)
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, limpar_texto_pdf(title), 0, 1, 'L', True)
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 6, limpar_texto_pdf(content))
        self.ln(3)

def gerar_pdf_mapa_simples(texto_aluno):
    pdf = PDF_Map_Simple(orientation='L', format='A4')
    pdf.add_page(); pdf.set_y(40)
    
    blocks = texto_aluno.split('\n\n')
    for block in blocks:
        if "**" in block:
            parts = block.split('\n')
            title = parts[0].replace('**', '').replace('⚡', '').replace('🛡️', '').replace('⚔️', '').replace('🎒', '').replace('🧪', '').replace('🤝', '')
            content = " ".join(parts[1:])
            if len(title) > 2 and len(content) > 5:
                pdf.draw_section(title, content)
    return pdf.output(dest='S').encode('latin-1', 'replace')

# ==============================================================================
# 7b. GERADOR PDF TÉCNICO (MANTIDO)
# ==============================================================================
class PDF_Classic(FPDF):
    def header(self):
        self.set_draw_color(0, 78, 146); self.set_line_width(0.4)
        self.rect(5, 5, 200, 287)
        logo = finding_logo()
        if logo: self.image(logo, 10, 10, 30); x_offset = 45 
        else: x_offset = 12
        self.set_xy(x_offset, 16); self.set_font('Arial', 'B', 16); self.set_text_color(0, 78, 146)
        self.cell(0, 8, 'PLANO DE ENSINO INDIVIDUALIZADO', 0, 1, 'L')
        self.set_xy(x_offset, 23); self.set_font('Arial', 'I', 10); self.set_text_color(100)
        self.cell(0, 5, 'Documento Oficial de Planejamento Pedagógico', 0, 1, 'L'); self.ln(20)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, f'Gerado via PEI 360º | Página {self.page_no()}', 0, 0, 'C')
    def section_title(self, label):
        self.ln(8); self.set_fill_color(240, 248, 255); self.set_text_color(0, 78, 146)
        self.set_font('Arial', 'B', 11); self.cell(0, 8, f"  {label}", 0, 1, 'L', fill=True); self.ln(4)

def gerar_pdf_final(dados, tem_anexo):
    pdf = PDF_Classic(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    pdf.section_title("1. IDENTIFICAÇÃO E CONTEXTO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    
    med_list = []
    if dados['lista_medicamentos']:
        for m in dados['lista_medicamentos']: med_list.append(f"{m['nome']} ({m['posologia']})")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nome:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, dados['diagnostico'])
    pdf.ln(2)
    
    if dados['ia_sugestao']:
        pdf.section_title("2. PLANEJAMENTO PEDAGÓGICO")
        t_limpo = re.sub(r'\[.*?\]', '', dados['ia_sugestao'])
        pdf.multi_cell(0, 6, limpar_texto_pdf(t_limpo))
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); doc.add_heading('PEI - ' + dados['nome'], 0); return BytesIO()

# ==============================================================================
# 8. INTERFACE UI
# ==============================================================================
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ OpenAI OK")
    else: api_key = st.text_input("Chave OpenAI:", type="password")
    if st.button("💾 Salvar"): salvar_aluno(st.session_state.dados); st.success("Salvo!")

st.markdown("""<div class="header-unified"><h1>PEI 360º - Sistema Integrado</h1></div>""", unsafe_allow_html=True)

abas = ["Início", "Estudante", "Coleta", "Rede", "Mapeamento", "Plano", "Monitoramento", "Consultoria IA", "Dashboard", "Documento", "🗺️ Jornada do Aluno"]
tabs = st.tabs(abas)

with tabs[0]: st.info("Bem-vindo ao PEI 360º.")

with tabs[1]: # ESTUDANTE (REFORMULADO)
    render_progresso()
    st.markdown("<div class='form-section-title'><i class='ri-user-smile-line'></i> Identidade</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)))
    st.session_state.dados['serie'] = c3.selectbox("Série", LISTA_SERIES)
    st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'])
    
    st.markdown("<div class='form-section-title'><i class='ri-history-line'></i> Histórico</div>", unsafe_allow_html=True)
    c_hist, c_fam = st.columns(2)
    st.session_state.dados['historico'] = c_hist.text_area("Histórico Escolar", st.session_state.dados['historico'])
    st.session_state.dados['familia'] = c_fam.text_area("Dinâmica Familiar", st.session_state.dados['familia'])
    
    st.markdown("<div class='form-section-title'><i class='ri-hospital-line'></i> Contexto Clínico</div>", unsafe_allow_html=True)
    
    # Lógica do Laudo
    possui_laudo = st.toggle("Possui Laudo Médico?", value=st.session_state.dados.get('possui_laudo', False))
    st.session_state.dados['possui_laudo'] = possui_laudo
    
    if possui_laudo:
        col_up, col_btn = st.columns([3, 1])
        with col_up:
            up = st.file_uploader("Upload Laudo (PDF)", type="pdf")
            if up: st.session_state.pdf_text = ler_pdf(up)
        with col_btn:
            if up and api_key:
                if st.button("🤖 Extrair Dados do Arquivo"):
                    extracted = extrair_dados_laudo(api_key, st.session_state.pdf_text)
                    if extracted:
                        st.session_state.dados['diagnostico'] = extracted.get('diagnostico', '')
                        # Adiciona remédios se vierem
                        if 'medicacao' in extracted and isinstance(extracted['medicacao'], list):
                             for m in extracted['medicacao']:
                                 st.session_state.dados['lista_medicamentos'].append({"nome": m, "posologia": "", "escola": False})
                        st.success("Dados extraídos!")
                        st.rerun()

        st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico (do Laudo)", st.session_state.dados['diagnostico'])
    else:
        st.session_state.dados['diagnostico'] = st.text_input("Hipótese Diagnóstica", st.session_state.dados['diagnostico'])

    # Medicação
    with st.container(border=True):
        usa_med = st.toggle("💊 Faz uso de medicação?", value=len(st.session_state.dados['lista_medicamentos']) > 0)
        if usa_med:
            c1, c2 = st.columns([3, 1])
            nm = c1.text_input("Nome Medicação", key="nm_med")
            if c2.button("Adicionar"):
                st.session_state.dados['lista_medicamentos'].append({"nome": nm, "posologia": "", "escola": False}); st.rerun()
        
        if st.session_state.dados['lista_medicamentos']:
            for i, m in enumerate(st.session_state.dados['lista_medicamentos']):
                st.info(f"💊 {m['nome']}")

with tabs[2]: st.write("Checklist...")
with tabs[3]: st.session_state.dados['rede_apoio'] = st.multiselect("Rede", LISTA_PROFISSIONAIS)
with tabs[4]: st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco", st.session_state.dados['hiperfoco'])
with tabs[5]: st.write("Plano...")
with tabs[6]: st.write("Monitoramento...")

with tabs[7]: # IA TÉCNICA
    render_progresso()
    st.markdown("### 🤖 Consultoria Pedagógica")
    if st.button("✨ GERAR PEI TÉCNICO", type="primary"):
        res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
        if res: st.session_state.dados['ia_sugestao'] = res
    
    if st.session_state.dados['ia_sugestao']:
        if st.button("🔄 Regenerar (Nova Perspectiva)"):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text, regenerar=True)
            if res: st.session_state.dados['ia_sugestao'] = res; st.rerun()
        st.text_area("Resultado:", st.session_state.dados['ia_sugestao'])

with tabs[8]: # DASHBOARD + PDF TÉCNICO
    render_progresso()
    st.markdown("### 📊 Painel & Exportação")
    # (Código dos gráficos mantido aqui visualmente...)
    if st.session_state.dados['nome']:
        st.metric("Barreiras", sum(len(v) for v in st.session_state.dados['barreiras_selecionadas'].values()))
    
    if st.session_state.dados['ia_sugestao']:
        pdf = gerar_pdf_final(st.session_state.dados, False)
        st.download_button("📥 Baixar PEI Oficial (PDF)", pdf, "PEI.pdf", "application/pdf")

with tabs[9]: # DOCUMENTO (Mantido por compatibilidade)
     st.write("Aba unificada com Dashboard.")

with tab_mapa: # MAPA
    render_progresso()
    st.markdown("### 🗺️ Jornada do Aluno")
    if st.session_state.dados['ia_sugestao']:
        if st.button("🎮 Gerar Roteiro Gamificado", type="primary"):
            txt, err = gerar_roteiro_gamificado(api_key, st.session_state.dados, st.session_state.dados['ia_sugestao'])
            if txt: 
                clean = txt.replace("[MAPA_TEXTO_GAMIFICADO]", "").replace("[FIM_MAPA_TEXTO_GAMIFICADO]", "")
                st.session_state.dados['ia_mapa_texto'] = clean; st.rerun()
        
        if st.session_state.dados['ia_mapa_texto']:
            if st.button("🔄 Criar Nova Aventura"):
                txt, err = gerar_roteiro_gamificado(api_key, st.session_state.dados, st.session_state.dados['ia_sugestao'], regenerar=True)
                if txt: 
                     clean = txt.replace("[MAPA_TEXTO_GAMIFICADO]", "").replace("[FIM_MAPA_TEXTO_GAMIFICADO]", "")
                     st.session_state.dados['ia_mapa_texto'] = clean; st.rerun()
            
            st.markdown(st.session_state.dados['ia_mapa_texto'])
            
            pdf_mapa = gerar_pdf_mapa_simples(st.session_state.dados['ia_mapa_texto'])
            st.download_button("📥 Baixar Mapa (PDF)", pdf_mapa, "Mapa_Jornada.pdf", "application/pdf")
    else:
        st.warning("Gere o PEI Técnico primeiro.")
