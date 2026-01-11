import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from docx.shared import Pt
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import base64
import json
import os
import re
import glob
import random

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
# 2. LISTAS DE DADOS (TOP LEVEL)
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
    'ia_sugestao': '', 'outros_acesso': '', 'outros_ensino': '', 
    'monitoramento_data': None, 
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
PASTA_BANCO = "banco_alunos"
if not os.path.exists(PASTA_BANCO): os.makedirs(PASTA_BANCO)

def get_hiperfoco_emoji(texto):
    if not texto: return "🚀"
    t = texto.lower()
    if "jogo" in t or "game" in t or "minecraft" in t or "roblox" in t or "mario" in t: return "🎮"
    if "dino" in t or "jurassic" in t: return "🦖"
    if "fute" in t or "bola" in t or "esporte" in t: return "⚽"
    if "desenho" in t or "arte" in t or "pintar" in t: return "🎨"
    if "músic" in t or "piano" in t or "violão" in t: return "🎵"
    if "anim" in t or "gato" in t or "cachorro" in t: return "🐾"
    if "carro" in t or "trem" in t or "rodas" in t: return "🏎️"
    if "espaço" in t or "astronomia" in t: return "🪐"
    if "leitura" in t or "livro" in t: return "📚"
    if "pok" in t: return "⚡"
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
    padrao = fr'\[{tag}\](.*?)(\[|$)'
    match = re.search(padrao, texto, re.DOTALL)
    if match: return match.group(1).strip()
    return ""

def extrair_linhas_bncc(texto):
    padrao = r'([A-Z]{2}\d{1,2}[A-Z]{2,3}\d{2,3}.*?)(?=\n|$)'
    if not texto: return []
    linhas = re.findall(padrao, texto)
    return list(set([l.strip().replace('**', '') for l in linhas if len(l) > 10]))

def extrair_resumo_estrategia(texto):
    if not texto: return "Plano ainda não gerado."
    conteudo = extrair_tag_ia(texto, "ESTRATEGIA_MASTER")
    if not conteudo and "ESTRATÉGIAS" in texto:
        partes = texto.split("ESTRATÉGIAS")
        conteudo = partes[1].split("ADAPTAÇÕES")[0] if "ADAPTAÇÕES" in partes[1] else partes[1]
    
    if conteudo:
        conteudo = re.sub(r'^[\d\.\s\🧩\-\*]+', '', conteudo.strip())
        return conteudo.strip()
    return "Gere o plano na aba IA para ver o resumo estratégico."

def get_pro_icon(nome_profissional):
    p = nome_profissional.lower()
    if "psic" in p: return "🧠"
    if "fono" in p: return "🗣️"
    if "terapeuta" in p or "ocupacional" in p: return "🧩"
    if "neuro" in p or "médic" in p or "psiquiatra" in p: return "🩺"
    if "prof" in p or "apoio" in p: return "🍎"
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
    return re.sub(r'[^\x00-\xff]', '', t)

def salvar_aluno(dados):
    if not dados['nome']: return False, "Nome obrigatório."
    nome_arq = re.sub(r'[^a-zA-Z0-9]', '_', dados['nome'].lower()) + ".json"
    try:
        with open(os.path.join(PASTA_BANCO, nome_arq), 'w', encoding='utf-8') as f:
            json.dump(dados, f, default=str, ensure_ascii=False, indent=4)
        return True, f"Salvo: {dados['nome']}"
    except Exception as e: return False, str(e)

def carregar_aluno(nome_arq):
    try:
        with open(os.path.join(PASTA_BANCO, nome_arq), 'r', encoding='utf-8') as f: d = json.load(f)
        if 'nasc' in d: d['nasc'] = date.fromisoformat(d['nasc'])
        if d.get('monitoramento_data'): d['monitoramento_data'] = date.fromisoformat(d['monitoramento_data'])
        return d
    except: return None

def excluir_aluno(nome_arq):
    try: os.remove(os.path.join(PASTA_BANCO, nome_arq)); return True
    except: return False

def calcular_progresso():
    if st.session_state.dados['ia_sugestao']: return 100
    pontos = 0
    total = 6 
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
    # BARRA LARANJA DURANTE O PROCESSO
    bar_color = "linear-gradient(90deg, #FF6B6B 0%, #FF8E53 100%)"
    
    if p >= 20: icon = "🚀"
    if p >= 50: icon = "🛸"
    if p >= 80: icon = "🌌"
    
    # CHEGADA: AZUL CELESTE/CIANO (ACESSO/SUCESSO)
    if p >= 100: 
        icon = "🏆"
        bar_color = "linear-gradient(90deg, #00C6FF 0%, #0072FF 100%)" 
    
    st.markdown(f"""
    <div class="prog-container">
        <div class="prog-track"><div class="prog-fill" style="width: {p}%; background: {bar_color};"></div></div>
        <div class="prog-icon" style="left: {p}%;">{icon}</div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 5. ESTILO VISUAL (CSS GLOBAL)
# ==============================================================================
def aplicar_estilo_visual():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2D3748; }
        .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
        div[data-baseweb="tab-border"], div[data-baseweb="tab-highlight"] { display: none !important; }
        
        /* HEADER COM LOGO E SUBTÍTULO APENAS */
        .header-unified {
            background-color: white; padding: 20px 40px; border-radius: 16px;
            border: 1px solid #E2E8F0; box-shadow: 0 4px 15px rgba(0,0,0,0.03); margin-bottom: 20px;
            display: flex; align-items: center; gap: 20px;
        }
        .header-subtitle { color: #718096; font-size: 1.1rem; font-weight: 700; margin: 0; letter-spacing: 0.5px; }

        /* ABAS CLEAN */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; margin-bottom: 20px; justify-content: center; }
        .stTabs [data-baseweb="tab"] { height: 36px; border-radius: 18px !important; background-color: white; border: 1px solid #E2E8F0; color: #718096; font-weight: 700; font-size: 0.85rem; padding: 0 20px; transition: all 0.2s ease; }
        .stTabs [aria-selected="true"] { background-color: #FF6B6B !important; color: white !important; border-color: #FF6B6B !important; box-shadow: 0 4px 10px rgba(255, 107, 107, 0.3); }
        
        /* BARRA DE PROGRESSO */
        .prog-container { width: 100%; position: relative; margin: 0 0 40px 0; }
        .prog-track { width: 100%; height: 3px; background-color: #E2E8F0; border-radius: 1.5px; }
        .prog-fill { height: 100%; border-radius: 1.5px; transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1), background 1.5s ease; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
        .prog-icon { position: absolute; top: -23px; font-size: 1.8rem; transition: left 1.5s cubic-bezier(0.4, 0, 0.2, 1); transform: translateX(-50%); z-index: 10; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.15)); }

        /* DASHBOARD HERO */
        .dash-hero { background: linear-gradient(135deg, #0F52BA 0%, #062B61 100%); border-radius: 16px; padding: 25px; color: white; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 15px rgba(15, 82, 186, 0.2); }
        .apple-avatar { width: 60px; height: 60px; border-radius: 50%; background: rgba(255,255,255,0.15); border: 2px solid rgba(255,255,255,0.4); color: white; font-weight: 800; font-size: 1.6rem; display: flex; align-items: center; justify-content: center; }

        /* METRIC CARDS */
        .metric-card { background: white; border-radius: 16px; padding: 15px; border: 1px solid #E2E8F0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 160px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
        .css-donut { width: 70px; height: 70px; border-radius: 50%; background: conic-gradient(var(--fill) var(--p), #EDF2F7 0); display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
        .css-donut::after { content: ""; position: absolute; width: 54px; height: 54px; border-radius: 50%; background: white; }
        .d-val { position: absolute; z-index: 2; font-size: 1.3rem; font-weight: 800; color: #2D3748; }
        .d-lbl { text-transform: uppercase; font-size: 0.65rem; color: #718096; font-weight: 700; letter-spacing: 0.5px; text-align: center; }
        .comp-icon-box { margin-bottom: 5px; }

        /* DETAIL CARDS */
        .soft-card { border-radius: 12px; padding: 25px; min-height: 260px; height: 100%; display: flex; flex-direction: column; box-shadow: 0 2px 5px rgba(0,0,0,0.02); border: 1px solid rgba(0,0,0,0.05); border-left: 5px solid; position: relative; overflow: hidden; }
        .sc-orange { background-color: #FFF5F5; border-left-color: #DD6B20; }
        .sc-blue { background-color: #EBF8FF; border-left-color: #3182CE; }
        .sc-yellow { background-color: #FFFFF0; border-left-color: #D69E2E; }
        .sc-cyan { background-color: #E6FFFA; border-left-color: #0BC5EA; }
        .sc-green { background-color: #F0FFF4; border-left-color: #38A169; }
        .sc-head { font-size: 0.75rem; font-weight: 800; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; color: #4A5568; letter-spacing: 0.5px; z-index: 2; }
        .sc-body { font-size: 0.9rem; line-height: 1.6; color: #2D3748; font-weight: 600; z-index: 2; flex-grow: 1; }
        .bg-icon { position: absolute; bottom: -10px; right: -10px; font-size: 6rem; opacity: 0.08; z-index: 1; pointer-events: none; }
        .bncc-li { margin-bottom: 8px; padding-left: 10px; border-left: 3px solid #3182CE; font-size: 0.85rem; }
        .rede-chip { display: inline-flex; align-items: center; background: white; padding: 6px 12px; border-radius: 20px; margin: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-size: 0.85rem; font-weight: 700; color: #2C5282; }

        /* DNA BARS */
        .dna-legend { font-size: 0.8rem; color: #718096; margin-bottom: 15px; background: #F7FAFC; padding: 10px; border-radius: 8px; font-style: italic; display: flex; align-items: center; gap: 6px;}
        .dna-bar-container { margin-bottom: 12px; }
        .dna-bar-flex { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 4px; color: #4A5568; font-weight: 600; }
        .dna-bar-bg { width: 100%; height: 6px; background: #E2E8F0; border-radius: 3px; overflow: hidden; }
        .dna-bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }

        /* UI ELEMENTS */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] { border-radius: 10px !important; border-color: #E2E8F0 !important; }
        div[data-testid="column"] .stButton button { border-radius: 10px !important; font-weight: 800 !important; height: 50px !important; background-color: #0F52BA !important; color: white !important; border: none !important; }
        div[data-testid="column"] .stButton button:hover { background-color: #0A3D8F !important; }
        div[data-baseweb="checkbox"] div[class*="checked"] { background-color: #0F52BA !important; border-color: #0F52BA !important; }
        .ia-side-box { background: #F8FAFC; border-radius: 16px; padding: 25px; border: 1px solid #E2E8F0; text-align: left; margin-bottom: 20px; }
        .form-section-title { display: flex; align-items: center; gap: 10px; color: #0F52BA; font-weight: 700; font-size: 1.1rem; margin-top: 20px; margin-bottom: 15px; border-bottom: 2px solid #F7FAFC; padding-bottom: 5px; }
        
        /* RESTAURAR CORES VIBRANTES DA HOME */
        .rich-card-link { text-decoration: none; color: inherit; display: block; height: 100%; }
        .rich-card { background-color: white; padding: 30px 20px; border-radius: 16px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: all 0.3s ease; height: 250px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; position: relative; overflow: hidden; }
        .rich-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(15, 82, 186, 0.1); border-color: #BEE3F8;}
        .rich-card h3 { margin: 15px 0 10px 0; font-size: 1.1rem; color: #0F52BA; font-weight: 800; }
        .rich-card p { font-size: 0.85rem; color: #718096; line-height: 1.4; margin: 0; }
        
        .icon-box { width: 65px; height: 65px; border-radius: 15px; display: flex; align-items: center; justify-content: center; font-size: 2rem; margin-bottom: 15px; }
        .ic-blue { background-color: #EBF8FF !important; color: #3182CE !important; }
        .ic-gold { background-color: #FFFFF0 !important; color: #D69E2E !important; }
        .ic-pink { background-color: #FFF5F7 !important; color: #D53F8C !important; }
        .ic-green { background-color: #F0FFF4 !important; color: #38A169 !important; }
    </style>
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_visual()

# ==============================================================================
# 6. INTELIGÊNCIA ARTIFICIAL (ULTIMATE PROMPT)
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

def consultar_gpt_pedagogico(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ Configure a Chave API."
    try:
        client = OpenAI(api_key=api_key)
        familia = ", ".join(dados['composicao_familiar_tags']) if dados['composicao_familiar_tags'] else "Não informado"
        evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        
        meds_info = "Nenhuma medicação informada."
        if dados['lista_medicamentos']:
            meds_info = "\n".join([f"- {m['nome']} ({m['posologia']}). Admin Escola: {'Sim' if m.get('escola') else 'Não'}." for m in dados['lista_medicamentos']])

        # --- PROMPT V69.0 (ULTIMATE AUTHORITY) ---
        prompt_sys = """
        Você é um Especialista Sênior em Neuroeducação, Inclusão, Currículo BNCC e Legislação Educacional Brasileira.
        
        SUA MISSÃO: Cruzar dados clínicos e escolares para criar um PEI Assertivo, Científico e Legalmente Embasado.
        
        --- DOCUMENTOS NORTEADORES OBRIGATÓRIOS ---
        Baseie suas diretrizes nestes referenciais:
        1. NOTA TÉCNICA SEESP/MEC nº 24/2010: Fundamental para o AEE e plano individualizado.
        2. MANUAL PEI (UNESP/ENICÉIA MENDES): Referência em Ensino Colaborativo.
        3. DUA (Desenho Universal para Aprendizagem): Múltiplas formas de engajamento e expressão.
        4. TANNÚS-VALADÃO & MENDES: O "passo a passo" acadêmico do PEI.
        5. INSTITUTO RODRIGO MENDES: Flexibilização curricular.
        
        --- REGRAS DE OURO ---
        1. USE AS TAGS EXATAS (Essenciais para o sistema).
        2. LINGUAGEM TÉCNICA: Use "ZDP (Vygotsky)", "Andaimagem", "Funções Executivas".
        3. ASSERTIVIDADE: Use "Recomenda-se", "É imperativo". Evite "pode ser".
        
        --- ESTRUTURA DA RESPOSTA ---
        
        1. 🌟 AVALIAÇÃO DE REPERTÓRIO (QUEM É O ESTUDANTE):
           Foque no que ele JÁ CONSEGUE fazer (Potencialidades), não apenas no déficit. Cruze diagnóstico + histórico + evidências.
        
        [ANALISE_FARMA]
        Analise os fármacos ({meds}). Indique efeitos colaterais (sono, sede, irritabilidade) e o impacto pedagógico direto.
        [FIM_ANALISE_FARMA]
        
        [MATRIZ_BNCC]
        Liste habilidades cirúrgicas. Formato Obrigatório:
        - RECOMPOSIÇÃO: [CÓDIGO] Descrição.
        - ANO VIGENTE: [CÓDIGO] Descrição.
        [FIM_MATRIZ_BNCC]
        
        [ESTRATEGIA_MASTER]
        Escreva UMA estratégia prática usando o Hiperfoco ("{hiperfoco}") como alavanca de aprendizagem (Scaffolding). Seja específico no "como fazer".
        [FIM_ESTRATEGIA_MASTER]
        
        2. 🎯 METAS SMART (Sespecíficas, Mensuráveis, Atingíveis, Relevantes, Temporais):
           - Curto Prazo (2 meses).
           - Médio Prazo (Semestre).
           - Longo Prazo (Ano Letivo).
        
        3. 🧩 DIRETRIZES DE ADAPTAÇÃO E CRONOGRAMA:
           - Acesso ao Currículo (DUA): Cite estratégias concretas.
           - Adaptação de Conteúdo: Priorização de objetivos essenciais da BNCC.
           - Avaliação Diferenciada: Prova oral, ledor, tempo estendido (Cite a Lei/Decreto se couber).
           - Cronograma de Revisão: Sugira periodicidade (ex: bimestral).
        """.format(hiperfoco=dados['hiperfoco'], meds=meds_info, serie=dados['serie'])
        
        prompt_user = f"""
        ALUNO: {dados['nome']} | SÉRIE: {dados['serie']}
        DIAGNÓSTICO: {dados['diagnostico']}
        MEDICAÇÃO: {meds_info}
        HIPERFOCO: {dados['hiperfoco']}
        BARREIRAS: {json.dumps(dados['barreiras_selecionadas'], ensure_ascii=False)}
        EVIDÊNCIAS: {evid}
        
        DOCUMENTOS ANEXOS (RESUMO DO LAUDO):
        {contexto_pdf[:3000] if contexto_pdf else "Apenas checklist do professor disponível."}
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": prompt_user}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 7. GERADOR PDF
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
        for m in dados['lista_medicamentos']:
            obs = m.get('obs', '')
            esc = " (Administrado na Escola)" if m.get('escola') else ""
            txt = f"{m['nome']} ({m['posologia']}){esc}"
            if obs: txt += f" [Obs: {obs}]"
            med_list.append(txt)
    med_str = "; ".join(med_list) if med_list else "Não informado."
    fam_str = ", ".join(dados['composicao_familiar_tags']) if dados['composicao_familiar_tags'] else "Não informado."
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nome:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nascimento:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, str(dados['nasc']), 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Série/Turma:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, f"{dados['serie']} - {dados['turma']}", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, dados['diagnostico']); pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Medicação:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, med_str); pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Família:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, fam_str)
    evid = [k.replace('?', '') for k, v in dados['checklist_evidencias'].items() if v]
    if evid:
        pdf.section_title("2. PONTOS DE ATENÇÃO")
        pdf.set_font("Arial", size=10); pdf.multi_cell(0, 6, limpar_texto_pdf('; '.join(evid) + '.'))
    if any(dados['barreiras_selecionadas'].values()):
        pdf.section_title("3. MAPEAMENTO DE SUPORTE")
        for c, i in dados['barreiras_selecionadas'].items():
            if i:
                pdf.set_font("Arial", 'B', 10); pdf.cell(0, 6, f"{c}:", 0, 1)
                pdf.set_font("Arial", size=10)
                for x in i:
                    niv = dados['niveis_suporte'].get(f"{c}_{x}", "Monitorado")
                    pdf.cell(5); pdf.cell(0, 6, f"- {x}: Suporte {niv}", 0, 1)
                pdf.ln(2)
    if dados['ia_sugestao']:
        pdf.ln(5); pdf.set_text_color(0); pdf.set_font("Arial", '', 10)
        t_limpo = re.sub(r'\[.*?\]', '', dados['ia_sugestao'])
        for linha in t_limpo.split('\n'):
            l = limpar_texto_pdf(linha)
            if re.match(r'^[1-6]\.', l.strip()) and l.strip().isupper():
                pdf.ln(4); pdf.set_fill_color(240, 248, 255); pdf.set_text_color(0, 78, 146); pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"  {l}", 0, 1, 'L', fill=True); pdf.set_text_color(0); pdf.set_font("Arial", size=10)
            elif l.strip().endswith(':') and len(l) < 70:
                pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(0, 6, l); pdf.set_font("Arial", size=10)
            else: pdf.multi_cell(0, 6, l)
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); doc.add_heading('PEI - ' + dados['nome'], 0)
    if dados['ia_sugestao']:
        t_limpo = re.sub(r'\[.*?\]', '', dados['ia_sugestao'])
        doc.add_paragraph(t_limpo)
    b = BytesIO(); doc.save(b); b.seek(0); return b

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
            if 'nasc' in d: d['nasc'] = date.fromisoformat(d['nasc'])
            if d.get('monitoramento_data'): d['monitoramento_data'] = date.fromisoformat(d['monitoramento_data'])
            st.session_state.dados.update(d); st.success("Carregado!")
        except: st.error("Erro no arquivo.")
    st.markdown("---")
    if st.button("💾 Salvar no Sistema", use_container_width=True):
        ok, msg = salvar_aluno(st.session_state.dados)
        if ok: st.success(msg)
        else: st.error(msg)
    st.markdown("---")
    data_atual = date.today().strftime("%d/%m/%Y")
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0;'><b>PEI 360º v69.0 Authority</b><br>Criado e desenvolvido por<br><b>Rodrigo A. Queiroz</b><br>{data_atual}</div>", unsafe_allow_html=True)

# HEADER
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 110px;">' if logo_path else ""

st.markdown(f"""
<div class="header-unified">
    {img_html}
    <div class="header-subtitle">Ecossistema de Inteligência Pedagógica e Inclusiva</div>
</div>""", unsafe_allow_html=True)

# ABAS
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento", "Consultoria IA", "Documento"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(abas)

with tab0: # INÍCIO
    if api_key:
        with st.spinner("Gerando inspiração..."):
            try:
                client = OpenAI(api_key=api_key)
                saudacao = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Frase curta inspiradora para professor sobre inclusão."}]).choices[0].message.content
                noticia = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Dica curta sobre legislação de inclusão ou neurociência."}]).choices[0].message.content
            except:
                saudacao = "A inclusão transforma vidas."
                noticia = "O PEI é um direito garantido por lei."
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #0F52BA 0%, #004E92 100%); padding: 25px; border-radius: 20px; color: white; margin-bottom: 30px; box-shadow: 0 10px 25px rgba(15, 82, 186, 0.25);">
            <div style="display:flex; gap:20px; align-items:center;">
                <div style="background:rgba(255,255,255,0.2); padding:12px; border-radius:50%;"><i class="ri-sparkling-2-fill" style="font-size: 2rem; color: #FFD700;"></i></div>
                <div><h3 style="color:white; margin:0; font-size: 1.4rem;">Olá, Educador(a)!</h3><p style="margin:5px 0 0 0; opacity:0.95; font-size:1rem;">{saudacao}</p></div>
            </div>
        </div>""", unsafe_allow_html=True)
    
    st.markdown("### <i class='ri-apps-2-line'></i> Fundamentos", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown("""<a href="https://diversa.org.br/educacao-inclusiva/" target="_blank" class="rich-card-link"><div class="rich-card"><div class="icon-box ic-blue"><i class="ri-book-open-line"></i></div><h3>O que é PEI?</h3><p>Conceitos fundamentais da inclusão escolar.</p></div></a>""", unsafe_allow_html=True)
    with c2: st.markdown("""<a href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm" target="_blank" class="rich-card-link"><div class="rich-card"><div class="icon-box ic-gold"><i class="ri-scales-3-line"></i></div><h3>Legislação</h3><p>Lei Brasileira de Inclusão e Decretos.</p></div></a>""", unsafe_allow_html=True)
    with c3: st.markdown("""<a href="https://institutoneurosaber.com.br/" target="_blank" class="rich-card-link"><div class="rich-card"><div class="icon-box ic-pink"><i class="ri-brain-line"></i></div><h3>Neurociência</h3><p>Artigos sobre desenvolvimento atípico.</p></div></a>""", unsafe_allow_html=True)
    with c4: st.markdown("""<a href="http://basenacionalcomum.mec.gov.br/" target="_blank" class="rich-card-link"><div class="rich-card"><div class="icon-box ic-green"><i class="ri-compass-3-line"></i></div><h3>BNCC</h3><p>Currículo oficial e adaptações.</p></div></a>""", unsafe_allow_html=True)
    if api_key: st.markdown(f"""<div class="highlight-card"><i class="ri-lightbulb-flash-fill" style="font-size: 2rem; color: #F59E0B;"></i><div><h4 style="margin:0; color:#1E293B;">Insight de Inclusão</h4><p style="margin:5px 0 0 0; font-size:0.9rem; color:#64748B;">{noticia}</p></div></div>""", unsafe_allow_html=True)

with tab1: # ESTUDANTE
    render_progresso()
    st.markdown("<div class='form-section-title'><i class='ri-user-smile-line'></i> Identidade & Matrícula</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome Completo", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)))
    try: serie_idx = LISTA_SERIES.index(st.session_state.dados['serie']) if st.session_state.dados['serie'] in LISTA_SERIES else 0
    except: serie_idx = 0
    st.session_state.dados['serie'] = c3.selectbox("Série/Ano", LISTA_SERIES, index=serie_idx, placeholder="Selecione...")
    st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'])
    st.markdown("<div class='form-section-title'><i class='ri-hospital-line'></i> Contexto Clínico & Familiar</div>", unsafe_allow_html=True)
    st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico", st.session_state.dados['diagnostico'])
    c_hist, c_fam = st.columns(2)
    st.session_state.dados['historico'] = c_hist.text_area("Histórico Escolar", st.session_state.dados['historico'])
    st.session_state.dados['familia'] = c_fam.text_area("Dinâmica Familiar", st.session_state.dados['familia'])
    st.session_state.dados['composicao_familiar_tags'] = st.multiselect("Quem mora com o aluno?", LISTA_FAMILIA, default=st.session_state.dados['composicao_familiar_tags'])
    with st.container(border=True):
        usa_med = st.toggle("💊 O aluno faz uso contínuo de medicação?", value=len(st.session_state.dados['lista_medicamentos']) > 0)
        
        # --- LISTA DE MEDICAMENTOS (CORRIGIDA) ---
        if usa_med:
            c1, c2, c3 = st.columns([3, 2, 2])
            nm = c1.text_input("Nome", key="nm_med")
            pos = c2.text_input("Posologia", key="pos_med")
            admin_escola = c3.checkbox("Administrado na escola?", key="adm_esc")
            if st.button("Adicionar"):
                st.session_state.dados['lista_medicamentos'].append({"nome": nm, "posologia": pos, "obs": "", "escola": admin_escola}); st.rerun()
        
        # O LOOP DEVE FICAR FORA DO IF DE ADICIONAR PARA APARECER SEMPRE
        if st.session_state.dados['lista_medicamentos']:
            st.write("---")
            for i, m in enumerate(st.session_state.dados['lista_medicamentos']):
                tag = " [NA ESCOLA]" if m.get('escola') else ""
                c_txt, c_btn = st.columns([5, 1])
                c_txt.info(f"💊 **{m['nome']}** ({m['posologia']}){tag}")
                if c_btn.button("Excluir", key=f"del_{i}"): 
                    st.session_state.dados['lista_medicamentos'].pop(i); st.rerun()

    with st.expander("📎 Anexar Laudo (PDF)"):
        up = st.file_uploader("Upload", type="pdf", label_visibility="collapsed")
        if up: st.session_state.pdf_text = ler_pdf(up)

with tab2: # EVIDÊNCIAS
    render_progresso()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='form-section-title'><i class='ri-book-open-line'></i> Pedagógico</div>", unsafe_allow_html=True)
        for q in ["Estagnação na aprendizagem", "Dificuldade de generalização", "Dificuldade de abstração", "Lacuna em pré-requisitos"]:
            st.session_state.dados['checklist_evidencias'][q] = st.toggle(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c2:
        st.markdown("<div class='form-section-title'><i class='ri-brain-line'></i> Cognitivo</div>", unsafe_allow_html=True)
        for q in ["Oscilação de foco", "Fadiga mental rápida", "Dificuldade de iniciar tarefas", "Esquecimento recorrente"]:
            st.session_state.dados['checklist_evidencias'][q] = st.toggle(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c3:
        st.markdown("<div class='form-section-title'><i class='ri-emotion-line'></i> Comportamental</div>", unsafe_allow_html=True)
        for q in ["Dependência de mediação (1:1)", "Baixa tolerância à frustração", "Desorganização de materiais", "Recusa de tarefas"]:
            st.session_state.dados['checklist_evidencias'][q] = st.toggle(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))

with tab3: # REDE
    render_progresso()
    st.markdown("### <i class='ri-team-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais:", LISTA_PROFISSIONAIS, default=st.session_state.dados['rede_apoio'])
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações Clínicas Importantes", st.session_state.dados['orientacoes_especialistas'])

with tab4: # MAPEAMENTO
    render_progresso()
    with st.container(border=True):
        st.markdown("#### <i class='ri-lightbulb-flash-line' style='color:#0F52BA'></i> Potencialidades e Hiperfoco", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        st.session_state.dados['hiperfoco'] = c1.text_input("Hiperfoco", st.session_state.dados['hiperfoco'])
        p_val = [p for p in st.session_state.dados.get('potencias', []) if p in LISTA_POTENCIAS]
        st.session_state.dados['potencias'] = c2.multiselect("Pontos Fortes", LISTA_POTENCIAS, default=p_val)
    st.divider()
    with st.container(border=True):
        st.markdown("#### <i class='ri-barricade-line' style='color:#FF6B6B'></i> Barreiras e Nível de Suporte", unsafe_allow_html=True)
        c_bar1, c_bar2, c_bar3 = st.columns(3)
        def render_cat_barreira(coluna, titulo, chave_json):
            with coluna:
                st.markdown(f"**{titulo}**")
                itens = LISTAS_BARREIRAS[chave_json]
                b_salvas = [b for b in st.session_state.dados['barreiras_selecionadas'].get(chave_json, []) if b in itens]
                sel = st.multiselect("Selecione:", itens, key=f"ms_{chave_json}", default=b_salvas, label_visibility="collapsed")
                st.session_state.dados['barreiras_selecionadas'][chave_json] = sel
                if sel:
                    for x in sel:
                        st.session_state.dados['niveis_suporte'][f"{chave_json}_{x}"] = st.select_slider(x, ["Autônomo", "Monitorado", "Substancial", "Muito Substancial"], value=st.session_state.dados['niveis_suporte'].get(f"{chave_json}_{x}", "Monitorado"), key=f"sl_{chave_json}_{x}")
                st.write("")
        render_cat_barreira(c_bar1, "Cognitivo", "Cognitivo")
        render_cat_barreira(c_bar1, "Sensorial/Motor", "Sensorial/Motor")
        render_cat_barreira(c_bar2, "Comunicacional", "Comunicacional")
        render_cat_barreira(c_bar2, "Acadêmico", "Acadêmico")
        render_cat_barreira(c_bar3, "Socioemocional", "Socioemocional")

with tab5: # PLANO
    render_progresso()
    st.markdown("### <i class='ri-tools-line'></i> Plano de Ação Estratégico", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 1. Acesso (DUA)")
            st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos", ["Tempo Estendido", "Apoio Leitura/Escrita", "Material Ampliado", "Tecnologia Assistiva", "Sala Silenciosa"], default=st.session_state.dados['estrategias_acesso'])
            st.session_state.dados['outros_acesso'] = st.text_input("Prática Personalizada (Acesso)", st.session_state.dados['outros_acesso'])
    with c2:
        with st.container(border=True):
            st.markdown("#### 2. Ensino")
            st.session_state.dados['estrategias_ensino'] = st.multiselect("Metodologia", ["Fragmentação de Tarefas", "Pistas Visuais", "Mapas Mentais", "Modelagem", "Ensino Híbrido"], default=st.session_state.dados['estrategias_ensino'])
            st.session_state.dados['outros_ensino'] = st.text_input("Prática Pedagógica (Ensino)", st.session_state.dados['outros_ensino'])
    with c3:
        with st.container(border=True):
            st.markdown("#### 3. Avaliação")
            st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Formato", ["Prova Adaptada", "Prova Oral", "Consulta Permitida", "Portfólio", "Autoavaliação"], default=st.session_state.dados['estrategias_avaliacao'])

with tab6: # MONITORAMENTO
    render_progresso()
    st.markdown("### <i class='ri-loop-right-line'></i> Monitoramento e Metas", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.session_state.dados['monitoramento_data'] = st.date_input("Próxima Revisão", value=st.session_state.dados.get('monitoramento_data', None))
    with c2: st.session_state.dados['status_meta'] = st.selectbox("Status da Meta Atual", ["Não Iniciado", "Em Andamento", "Parcialmente Atingido", "Atingido", "Superado"], index=0)
    st.write("")
    c3, c4 = st.columns(2)
    with c3: st.session_state.dados['parecer_geral'] = st.selectbox("Parecer Geral", ["Manter Estratégias", "Aumentar Suporte", "Reduzir Suporte (Autonomia)", "Alterar Metodologia", "Encaminhar para Especialista"], index=0)
    with c4: st.session_state.dados['proximos_passos_select'] = st.multiselect("Ações Futuras", ["Reunião com Família", "Encaminhamento Clínico", "Adaptação de Material", "Mudança de Lugar em Sala", "Novo PEI", "Observação em Sala"])

with tab7: # IA
    render_progresso()
    st.markdown("### <i class='ri-robot-2-line'></i> Assistente Pedagógico Inteligente", unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.markdown("""<div class="ia-side-box"><h4 style="color:#0F52BA; margin-top:0;">🤖 Consultoria IA</h4><p style="font-size:0.9rem; color:#64748B;">Vou analisar o <b>Hiperfoco</b>, <b>Barreiras</b> e <b>Medicação</b> para criar um plano alinhado à BNCC.</p></div>""", unsafe_allow_html=True)
        nome_aluno = st.session_state.dados['nome'].split()[0] if st.session_state.dados['nome'] else "o estudante"
        if st.button(f"✨ GERAR PLANO PARA {nome_aluno.upper()}", type="primary", use_container_width=True):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: 
                st.session_state.dados['ia_sugestao'] = res
                effect = random.choice(['balloons', 'snow'])
                if effect == 'balloons': st.balloons()
                else: st.snow()
            else: st.error(err)
        
        with st.expander("📚 Referências Bibliográficas e Base Teórica"):
            st.markdown("""
            **1. Documentos Norteadores**
            * NOTA TÉCNICA SEESP/MEC nº 24/2010.
            * DUA - Desenho Universal para a Aprendizagem.
            
            **2. Autores de Referência**
            * MENDES, Enicéia Gonçalves (Ensino Colaborativo).
            * MANTOAN, Maria Teresa Eglér (Inclusão Total).
            * PLETSCH, Márcia Denise (Políticas Públicas).
            """)

    with col_right:
        if st.session_state.dados['ia_sugestao']:
            with st.expander("🔍 Entenda a Lógica (Calibragem)"):
                st.markdown("""**Como este plano foi construído:**\n* **Filtro Vygotsky:** Identificação da Zona de Desenvolvimento Proximal.\n* **Análise Farmacológica:** Impacto da medicação na aprendizagem.\n* **Alinhamento BNCC:** Habilidades de recomposição vs. ano corrente.""")
            st.markdown(st.session_state.dados['ia_sugestao'])
            st.info("📝 **Personalize:** O texto acima é editável.")
            novo_texto = st.text_area("Editor de Conteúdo", value=st.session_state.dados['ia_sugestao'], height=400, key="editor_ia")
            st.session_state.dados['ia_sugestao'] = novo_texto
        else:
            st.info(f"👈 Clique no botão ao lado para gerar o plano de {nome_aluno}.")

with tab8: # DASHBOARD FINAL (ESTÁVEL)
    render_progresso()
    st.markdown("### <i class='ri-file-pdf-line'></i> Dashboard e Exportação", unsafe_allow_html=True)
    if st.session_state.dados['nome']:
        init_avatar = st.session_state.dados['nome'][0].upper() if st.session_state.dados['nome'] else "?"
        st.markdown(f"""
        <div class="dash-hero">
            <div style="display:flex; align-items:center; gap:20px;">
                <div class="apple-avatar">{init_avatar}</div>
                <div style="color:white;"><h1>{st.session_state.dados['nome']}</h1><p>{st.session_state.dados['serie']}</p></div>
            </div>
            <div>
                <div style="text-align:right; font-size:0.8rem; opacity:0.8;">STATUS</div>
                <div style="font-size:1.2rem; font-weight:bold;">{st.session_state.dados['status_meta']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 4 COLUNAS NO TOPO
        c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
        with c_kpi1:
            n_pot = len(st.session_state.dados['potencias'])
            color_p = "#38A169" if n_pot > 0 else "#CBD5E0"
            st.markdown(f"""<div class="metric-card"><div class="css-donut" style="--p: {n_pot*10}%; --fill: {color_p};"><div class="d-val">{n_pot}</div></div><div class="d-lbl">Potencialidades</div></div>""", unsafe_allow_html=True)
        with c_kpi2:
            n_bar = sum(len(v) for v in st.session_state.dados['barreiras_selecionadas'].values())
            color_b = "#E53E3E" if n_bar > 5 else "#DD6B20"
            st.markdown(f"""<div class="metric-card"><div class="css-donut" style="--p: {n_bar*5}%; --fill: {color_b};"><div class="d-val">{n_bar}</div></div><div class="d-lbl">Barreiras</div></div>""", unsafe_allow_html=True)
        with c_kpi3:
             hf = st.session_state.dados['hiperfoco'] or "-"
             hf_emoji = get_hiperfoco_emoji(hf)
             st.markdown(f"""<div class="metric-card"><div style="font-size:2.5rem;">{hf_emoji}</div><div style="font-weight:800; font-size:1.1rem; color:#2D3748; margin:10px 0;">{hf}</div><div class="d-lbl">Hiperfoco</div></div>""", unsafe_allow_html=True)
        with c_kpi4:
             # NÍVEL DE ATENÇÃO (LÓGICA BLINDADA)
             txt_comp, bg_c, txt_c = calcular_complexidade_pei(st.session_state.dados)
             st.markdown(f"""<div class="metric-card" style="background-color:{bg_c}; border-color:{txt_c};"><div class="comp-icon-box"><i class="ri-error-warning-line" style="color:{txt_c}; font-size: 2rem;"></i></div><div style="font-weight:800; font-size:1.1rem; color:{txt_c}; margin:5px 0;">{txt_comp}</div><div class="d-lbl" style="color:{txt_c};">Nível de Atenção</div></div>""", unsafe_allow_html=True)

        st.write("")
        
        # GRID DOS CARDS DE DETALHE
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            # CARD 1: MEDICAÇÃO (ANALISE IA + LISTA)
            analise_farma = extrair_tag_ia(st.session_state.dados['ia_sugestao'], "ANALISE_FARMA") or "Aguardando análise da IA..."
            lista_meds = []
            for m in st.session_state.dados['lista_medicamentos']:
                tag = " (Escola)" if m.get('escola') else ""
                lista_meds.append(f"{m['nome']}{tag}")
            
            txt_meds = ", ".join(lista_meds) if lista_meds else "Sem medicação."
            
            if st.session_state.dados['lista_medicamentos']:
                st.markdown(f"""<div class="soft-card sc-orange"><div class="sc-head"><i class="ri-medicine-bottle-fill" style="color:#DD6B20;"></i> Atenção Farmacológica</div><div class="sc-body"><b>Em uso:</b> {txt_meds}<br><br><b>Análise:</b> {analise_farma}</div><div class="bg-icon">💊</div></div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="soft-card sc-green"><div class="sc-head"><i class="ri-checkbox-circle-fill" style="color:#38A169;"></i> Medicação</div><div class="sc-body">Nenhuma medicação informada.</div><div class="bg-icon">✅</div></div>""", unsafe_allow_html=True)
            
            st.write("")
            
            # CARD 3: ESTRATÉGIA (ASSERTIVA)
            estrategia = extrair_tag_ia(st.session_state.dados['ia_sugestao'], "ESTRATEGIA_MASTER")
            if not estrategia: estrategia = "Gere o plano na aba IA."
            st.markdown(f"""<div class="soft-card sc-yellow"><div class="sc-head"><i class="ri-lightbulb-flash-fill" style="color:#D69E2E;"></i> Estratégia Principal</div><div class="sc-body" style="font-style:italic;">"{estrategia}"</div><div class="bg-icon">💡</div></div>""", unsafe_allow_html=True)

        with c_r2:
            # CARD 2: BNCC (LISTA LIMPA)
            raw_bncc = extrair_tag_ia(st.session_state.dados['ia_sugestao'], "MATRIZ_BNCC")
            if raw_bncc:
                linhas = [l.strip() for l in raw_bncc.split('\n') if l.strip()]
                html_lista = "".join([f'<div class="bncc-li">{l}</div>' for l in linhas])
            else:
                linhas_bncc = extrair_linhas_bncc(st.session_state.dados['ia_sugestao'])
                html_lista = "".join([f'<div class="bncc-li">{l}</div>' for l in linhas_bncc]) if linhas_bncc else "Gere o plano na aba IA."

            st.markdown(f"""<div class="soft-card sc-blue"><div class="sc-head"><i class="ri-compass-3-fill" style="color:#3182CE;"></i> Matriz BNCC</div><div class="sc-body">{html_lista}</div><div class="bg-icon">🎯</div></div>""", unsafe_allow_html=True)
            
            st.write("")

            # CARD 4: REDE E ACOMPANHAMENTO (MERGED)
            rede_html = ""
            if st.session_state.dados['rede_apoio']:
                for prof in st.session_state.dados['rede_apoio']:
                    icon = get_pro_icon(prof)
                    rede_html += f'<span class="rede-chip">{icon} {prof}</span> '
            else:
                rede_html = "<span style='opacity:0.6;'>Sem rede de apoio.</span>"
            
            passos = ", ".join(st.session_state.dados['proximos_passos_select']) if st.session_state.dados['proximos_passos_select'] else "Não definidos"
            
            st.markdown(f"""
            <div class="soft-card sc-cyan">
                <div class="sc-head"><i class="ri-team-fill" style="color:#0BC5EA;"></i> Rede e Acompanhamento</div>
                <div class="sc-body">
                    <div style="margin-bottom:15px;">{rede_html}</div>
                    <div style="border-top:1px solid rgba(0,0,0,0.05); padding-top:10px; font-size:0.85rem;">
                        <b>Parecer:</b> {st.session_state.dados['parecer_geral']}<br>
                        <b>Próximos Passos:</b> {passos}
                    </div>
                </div>
                <div class="bg-icon">🤝</div>
            </div>""", unsafe_allow_html=True)

        st.write("")
        st.markdown("##### 🧬 DNA de Suporte (Detalhamento)")
        st.markdown('<div class="dna-legend"><i class="ri-information-fill"></i> Barras maiores indicam áreas que exigem mais adaptação e suporte intenso.</div>', unsafe_allow_html=True)
        dna_c1, dna_c2 = st.columns(2)
        areas = list(LISTAS_BARREIRAS.keys())
        for i, area in enumerate(areas):
            qtd = len(st.session_state.dados['barreiras_selecionadas'].get(area, []))
            val = min(qtd * 20, 100)
            target = dna_c1 if i < 3 else dna_c2
            
            color = "#3182CE"
            if val > 40: color = "#DD6B20"
            if val > 70: color = "#E53E3E"
            
            target.markdown(f"""
            <div class="dna-bar-container">
                <div class="dna-bar-flex"><span>{area}</span><span>{qtd} barreiras</span></div>
                <div class="dna-bar-bg"><div class="dna-bar-fill" style="width:{val}%; background:{color};"></div></div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    if st.session_state.dados['ia_sugestao']:
        c1, c2 = st.columns(2)
        with c1:
            pdf = gerar_pdf_final(st.session_state.dados, len(st.session_state.pdf_text)>0)
            st.download_button("📥 Baixar PDF Oficial", pdf, f"PEI_{st.session_state.dados['nome']}.pdf", "application/pdf", type="primary")
        with c2:
            docx = gerar_docx_final(st.session_state.dados)
            st.download_button("📥 Baixar Word Editável", docx, f"PEI_{st.session_state.dados['nome']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.write("")
            json_dados = json.dumps(st.session_state.dados, default=str)
            st.download_button("💾 Baixar Arquivo do Aluno (.json)", json_dados, f"PEI_{st.session_state.dados['nome']}.json", "application/json")

st.markdown("---")
