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
    t = re.sub(r'\[.*?\]', '', texto) 
    t = t.replace('**', '').replace('__', '').replace('### ', '').replace('## ', '').replace('# ', '')
    # Remove emojis para evitar erro no FPDF
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
    return None

def excluir_aluno(nome_arq):
    try: os.remove(os.path.join(PASTA_BANCO, nome_arq)); return True
    except: return False

def calcular_progresso():
    if st.session_state.dados['ia_sugestao']: return 100
    pontos = 0; total = 6 
    d = st.session_state.dados
    if d['nome']: pontos += 1
    if d['serie']: pontos += 1
    if any(d['checklist_evidencias'].values()): pontos += 1
    if d['hiperfoco']: pontos += 1
    if any(d['barreiras_selecionadas'].values()): pontos += 1
    if d['estrategias_ensino']: pontos += 1
    return int((pontos / total) * 90)

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
        .sc-head { font-size: 0.75rem; font-weight: 800; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; color: #4A5568; letter-spacing: 0.5px; z-index: 2; }
        .sc-body { font-size: 0.9rem; line-height: 1.6; color: #2D3748; font-weight: 600; z-index: 2; flex-grow: 1; }
        .bg-icon { position: absolute; bottom: -10px; right: -10px; font-size: 6rem; opacity: 0.08; z-index: 1; pointer-events: none; }
        
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
# 6. INTELIGÊNCIA ARTIFICIAL (TÉCNICA & GAMIFICADA)
# ==============================================================================
@st.cache_data(ttl=3600)
def gerar_saudacao_ia(api_key):
    if not api_key: return "Bem-vindo ao PEI 360º."
    try:
        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Frase curta inspiradora para professor sobre inclusão."}], temperature=0.9)
        return res.choices[0].message.content
    except: return "A inclusão transforma vidas."

@st.cache_data(ttl=3600)
def gerar_noticia_ia(api_key):
    if not api_key: return "Dica: Mantenha o PEI sempre atualizado."
    try:
        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Dica curta sobre legislação de inclusão ou neurociência (máx 2 frases)."}], temperature=0.7)
        return res.choices[0].message.content
    except: return "O cérebro aprende durante toda a vida."

# IA TÉCNICA (COM BOTÃO REGENERAR)
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

# IA LÚDICA (MAPA - COM BOTÃO REGENERAR)
def gerar_roteiro_gamificado(api_key, dados, pei_tecnico, regenerar=False):
    if not api_key: return None, "Configure a API."
    try:
        client = OpenAI(api_key=api_key)
        extra = " (Mude o tom da narrativa e os exemplos)" if regenerar else ""
        
        prompt_sys = f"""
        Você é um Game Master.{extra}
        CONTEXTO: Aluno gosta de {dados['hiperfoco']}.
        BASE TÉCNICA (Referência): {pei_tecnico[:1500]}
        
        SUA MISSÃO: Criar um Roteiro Gamificado EM PRIMEIRA PESSOA ("Eu").
        
        REGRAS ABSOLUTAS:
        1. PROIBIDO mencionar: CID, Diagnóstico, Remédio, Transtorno, "Barreira".
        2. Use Emojis e linguagem motivadora.
        3. Siga EXATAMENTE este template:
        
        [MAPA_TEXTO_GAMIFICADO]
        ⚡ **Meus Superpoderes:**
        (Como uso meu {dados['hiperfoco']} para aprender melhor).
        
        🛡️ **Escudo de Calma:**
        (Técnica de respiração ou pausa para quando estou nervoso).
        
        ⚔️ **Missão na Sala:**
        (O que faço na aula: sentar na frente, pedir silêncio, usar fone).
        
        🎒 **Meu Inventário:**
        (Como organizo minha mochila ou caderno).
        
        🧪 **Poção de Energia:**
        (O que faço no intervalo para descansar).
        
        🤝 **Minha Guilda:**
        (Quem são meus aliados: Mãe, Pai, Professores).
        [FIM_MAPA_TEXTO_GAMIFICADO]
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": "Gere o mapa do aluno."}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 7. GERADORES PDF
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

class PDF_Map_Simple(FPDF):
    def header(self):
        self.set_fill_color(255, 200, 0); self.rect(0, 0, 297, 30, 'F')
        self.set_xy(10, 10); self.set_font('Arial', 'B', 24); self.set_text_color(50, 50, 50)
        self.cell(0, 10, "MEU MAPA DE JORNADA", 0, 1, 'C')

    def draw_section(self, title, content):
        self.ln(5)
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(240, 240, 240) # Cinza claro
        self.cell(0, 10, limpar_texto_pdf(title), 0, 1, 'L', True)
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 6, limpar_texto_pdf(content))
        self.ln(3)

def gerar_pdf_final(dados, tem_anexo):
    pdf = PDF_Classic(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    pdf.section_title("1. IDENTIFICAÇÃO E CONTEXTO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    med_list = []
    if dados['lista_medicamentos']:
        for m in dados['lista_medicamentos']: med_list.append(f"{m['nome']} ({m['posologia']})")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nome:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Série:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, str(dados['serie']), 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, dados['diagnostico']); pdf.ln(2)
    
    if dados['ia_sugestao']:
        pdf.section_title("2. PLANEJAMENTO PEDAGÓGICO")
        t_limpo = re.sub(r'\[.*?\]', '', dados['ia_sugestao'])
        pdf.multi_cell(0, 6, limpar_texto_pdf(t_limpo))
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_pdf_mapa_simples(texto_aluno):
    # PDF em Paisagem ('L')
    pdf = PDF_Map_Simple(orientation='L', format='A4')
    pdf.add_page()
    pdf.set_y(40)
    
    # Parse manual simples dos blocos
    # Divide por quebra de linha dupla
    blocks = texto_aluno.split('\n\n')
    for block in blocks:
        if "**" in block:
            parts = block.split('\n')
            title = parts[0].replace('**', '').replace('⚡', '').replace('🛡️', '').replace('⚔️', '').replace('🎒', '').replace('🧪', '').replace('🤝', '')
            content = " ".join(parts[1:])
            
            if len(title) > 2 and len(content) > 5:
                pdf.draw_section(title, content)
                
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); doc.add_heading('PEI - ' + dados['nome'], 0)
    return BytesIO()

# ==============================================================================
# 8. INTERFACE UI (PRINCIPAL)
# ==============================================================================
# SIDEBAR
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ OpenAI OK")
    else: api_key = st.text_input("Chave OpenAI:", type="password")
    
    st.markdown("### 📂 Carregar Backup")
    uploaded_json = st.file_uploader("Arquivo .json", type="json")
    if uploaded_json:
        try:
            d = json.load(uploaded_json)
            st.session_state.dados.update(d); st.success("Carregado!")
        except: st.error("Erro no arquivo.")
    st.markdown("---")
    if st.button("💾 Salvar no Sistema"):
        ok, msg = salvar_aluno(st.session_state.dados)
        if ok: st.success(msg)

# HEADER
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 110px;">' if logo_path else ""

st.markdown(f"""
<div class="header-unified">
    {img_html}
    <div class="header-subtitle">Ecossistema de Inteligência Pedagógica e Inclusiva</div>
</div>""", unsafe_allow_html=True)

# ABAS (10 ABAS - MAPA NO FINAL)
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento", "Consultoria IA", "Documento", "🗺️ Jornada do Aluno"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab_mapa = st.tabs(abas)

# ... (MANTENDO AS ABAS 0-6 ORIGINAIS) ...
with tab0: st.info("Bem-vindo ao PEI 360º.")
with tab1: 
    st.session_state.dados['nome'] = st.text_input("Nome", st.session_state.dados['nome'])
    st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico", st.session_state.dados['diagnostico'])
with tab2: st.write("Aba Evidências...")
with tab3: st.session_state.dados['rede_apoio'] = st.multiselect("Rede", LISTA_PROFISSIONAIS)
with tab4: st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco", st.session_state.dados['hiperfoco'])
with tab5: st.write("Plano...")
with tab6: st.write("Monitoramento...")

with tab7: # IA (TÉCNICA + REGENERAR)
    render_progresso()
    st.markdown("### <i class='ri-robot-2-line'></i> Consultoria Pedagógica com IA", unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 2])
    with col_left:
        # BOTÃO GERAR
        if st.button("✨ GERAR PEI TÉCNICO", type="primary", use_container_width=True):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: 
                st.session_state.dados['ia_sugestao'] = res
                st.success("PEI Técnico Gerado!")
            else: st.error(err)
        
        # BOTÃO REGENERAR (NOVO)
        if st.session_state.dados['ia_sugestao']:
            if st.button("🔄 Regenerar (Nova Perspectiva)", use_container_width=True):
                 res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text, regenerar=True)
                 if res: st.session_state.dados['ia_sugestao'] = res; st.rerun()

    with col_right:
        if st.session_state.dados['ia_sugestao']:
            st.text_area("PEI Técnico (Editável)", st.session_state.dados['ia_sugestao'], height=400)

with tab8: # DOCUMENTO (MANTIDO DASHBOARD + PDF TÉCNICO)
    render_progresso()
    st.markdown("### <i class='ri-file-pdf-line'></i> Dashboard e Exportação", unsafe_allow_html=True)
    if st.session_state.dados['nome']:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Potencialidades", len(st.session_state.dados['potencias']))
        c2.metric("Barreiras", sum(len(v) for v in st.session_state.dados['barreiras_selecionadas'].values()))
        c3.metric("Hiperfoco", st.session_state.dados['hiperfoco'] or "-")
        c4.metric("Complexidade", calcular_complexidade_pei(st.session_state.dados))
        
        st.divider()
        if st.session_state.dados['ia_sugestao']:
            pdf = gerar_pdf_final(st.session_state.dados, False)
            st.download_button("📥 Baixar PEI Oficial (PDF)", pdf, f"PEI_{st.session_state.dados['nome']}.pdf", "application/pdf", type="primary")

with tab_mapa: # MAPA (GAMIFICADO + PDF SIMPLES)
    render_progresso()
    st.markdown(f"""
    <div style="background: linear-gradient(90deg, #F6E05E 0%, #D69E2E 100%); padding: 25px; border-radius: 20px; color: #2D3748; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h3 style="margin:0; color:#2D3748;">🗺️ Jornada do Aluno</h3>
        <p style="margin:5px 0 0 0; font-weight:600;">Painel de Missões para o Estudante.</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.dados['ia_sugestao']:
        # 1. GERAR
        if not st.session_state.dados['ia_mapa_texto']:
            if st.button("🎮 Gerar Roteiro Gamificado", type="primary"):
                with st.spinner("Criando aventura..."):
                    texto_game, err = gerar_roteiro_gamificado(api_key, st.session_state.dados, st.session_state.dados['ia_sugestao'])
                    if texto_game:
                        clean = texto_game.replace("[MAPA_TEXTO_GAMIFICADO]", "").replace("[FIM_MAPA_TEXTO_GAMIFICADO]", "")
                        st.session_state.dados['ia_mapa_texto'] = clean
                        st.rerun()
        
        # 2. REGENERAR E EXIBIR
        if st.session_state.dados['ia_mapa_texto']:
            if st.button("🔄 Criar Nova Aventura (Regenerar)"):
                 with st.spinner("Reescrevendo..."):
                    texto_game, err = gerar_roteiro_gamificado(api_key, st.session_state.dados, st.session_state.dados['ia_sugestao'], regenerar=True)
                    if texto_game:
                        clean = texto_game.replace("[MAPA_TEXTO_GAMIFICADO]", "").replace("[FIM_MAPA_TEXTO_GAMIFICADO]", "")
                        st.session_state.dados['ia_mapa_texto'] = clean
                        st.rerun()
            
            st.divider()
            st.markdown(st.session_state.dados['ia_mapa_texto'])
            st.divider()
            
            # 3. PDF SIMPLES (SEM IMAGEM, SEM ERRO)
            st.markdown("#### 📤 Exportar")
            pdf_simples = gerar_pdf_mapa_simples(st.session_state.dados['ia_mapa_texto'])
            st.download_button(
                "📥 Baixar Mapa Gamificado (PDF)", 
                pdf_simples, 
                "Mapa_Jornada.pdf", 
                "application/pdf", 
                type="primary",
                use_container_width=True
            )
            
    else:
        st.warning("⚠️ Gere o PEI Técnico na aba 'Consultoria IA' primeiro.")

st.markdown("---")
