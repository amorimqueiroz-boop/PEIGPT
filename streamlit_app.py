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
    return "👾"

st.set_page_config(
    page_title="PEI 360º Gamified",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. SISTEMA DE GAMIFICAÇÃO (PIXEL ART)
# ==============================================================================
# Sorteia o tema apenas uma vez por sessão
if 'tema_jogo' not in st.session_state:
    st.session_state.tema_jogo = random.choice(['dino', 'hero', 'builder'])

def get_avatar_url():
    tema = st.session_state.tema_jogo
    # GIFs de Pixel Art (Links públicos estáveis)
    urls = {
        'dino': "https://media.tenor.com/fSsxHOga_B8AAAAi/dino-chrome.gif", # Dino clássico correndo
        'hero': "https://media.tenor.com/fDWqG7J9bVQAAAAi/8-bit-walking.gif", # Heroi RPG andando
        'builder': "https://media.tenor.com/GfSXjy8qD8MAAAAi/miner-minecraft.gif" # Minecraft style
    }
    return urls.get(tema, urls['dino'])

def calcular_progresso():
    pontos = 0
    total_pontos = 7 
    d = st.session_state.dados
    if d['nome']: pontos += 1
    if d['serie']: pontos += 1
    if d['diagnostico']: pontos += 1
    if any(d['checklist_evidencias'].values()): pontos += 1
    if d['hiperfoco']: pontos += 1
    if any(d['barreiras_selecionadas'].values()): pontos += 1
    if d['estrategias_ensino'] or d['estrategias_acesso']: pontos += 1
    
    return int((pontos / total_pontos) * 100)

def renderizar_barra_gamificada():
    progresso = calcular_progresso()
    avatar = get_avatar_url()
    
    # HTML/CSS Injetado localmente para performance
    st.markdown(f"""
    <style>
        .pixel-track {{
            width: 100%;
            height: 4px;
            background-color: #E2E8F0;
            border-radius: 2px;
            position: relative;
            margin: 30px 0 20px 0;
            display: flex;
            align-items: center;
        }}
        .pixel-fill {{
            height: 100%;
            width: {progresso}%;
            background: linear-gradient(90deg, #48BB78 0%, #0F52BA 100%);
            border-radius: 2px;
            transition: width 0.5s ease;
        }}
        .pixel-avatar {{
            position: absolute;
            left: {max(0, progresso - 3)}%; /* Ajuste para centralizar */
            bottom: 6px; /* Fica em cima da linha */
            width: 40px;
            height: 40px;
            image-rendering: pixelated; /* Garante o visual 8-bit */
            transition: left 0.5s ease;
            z-index: 10;
        }}
        .pixel-badge {{
            position: absolute;
            right: 0;
            top: -25px;
            font-family: 'Courier New', monospace;
            font-size: 0.75rem;
            font-weight: 800;
            color: #0F52BA;
            background: #EBF8FF;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #BEE3F8;
        }}
    </style>
    
    <div class="pixel-track">
        <div class="pixel-badge">LEVEL {int(progresso/20) + 1} • {progresso}%</div>
        <img src="{avatar}" class="pixel-avatar">
        <div class="pixel-fill"></div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 3. ESTILO VISUAL (BASE BLINDADA)
# ==============================================================================
def aplicar_estilo_visual():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #2D3748; }
        :root { --primary: #0F52BA; --secondary: #FF6B6B; --card-radius: 12px; }

        /* HEADER */
        .header-unified {
            background-color: white; padding: 25px; border-radius: var(--card-radius);
            border-left: 5px solid var(--primary);
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
            display: flex; align-items: center; gap: 20px;
        }
        .header-unified h1 { color: var(--primary); margin: 0; font-size: 1.5rem; font-weight: 800; }
        .header-unified p { color: #718096; margin: 0; font-size: 0.9rem; }

        /* ABAS */
        .stTabs [data-baseweb="tab-list"] { gap: 5px; }
        .stTabs [data-baseweb="tab"] {
            height: 40px; border-radius: 8px; background-color: white;
            border: 1px solid #E2E8F0; font-weight: 600; color: #718096; font-size: 0.85rem;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--primary) !important; color: white !important;
        }

        /* CARDS */
        .rich-card {
            background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #E2E8F0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02); transition: all 0.2s ease; cursor: pointer;
            text-align: left; height: 180px; display: flex; flex-direction: column; justify-content: center;
            text-decoration: none; color: inherit;
        }
        .rich-card:hover { transform: translateY(-3px); border-color: var(--primary); }
        .rich-card h3 { margin: 10px 0 5px 0; font-size: 1.1rem; color: var(--primary); font-weight: 700; }
        .rich-icon { font-size: 2rem; color: var(--secondary); margin-bottom: 10px; }
        
        /* INPUTS */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { 
            border-radius: 8px !important; border-color: #E2E8F0 !important; 
        }
        div[data-testid="column"] .stButton button { 
            border-radius: 8px !important; font-weight: 700 !important; text-transform: uppercase; 
        }
    </style>
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_visual()

# ==============================================================================
# 4. LISTAS DE DADOS
# ==============================================================================
LISTA_SERIES = ["Educação Infantil", "1º Ano (Fund. I)", "2º Ano (Fund. I)", "3º Ano (Fund. I)", "4º Ano (Fund. I)", "5º Ano (Fund. I)", "6º Ano (Fund. II)", "7º Ano (Fund. II)", "8º Ano (Fund. II)", "9º Ano (Fund. II)", "1ª Série (EM)", "2ª Série (EM)", "3ª Série (EM)"]

LISTAS_BARREIRAS = {
    "Cognitivo": ["Atenção Sustentada", "Memória Operacional", "Flexibilidade", "Velocidade Processamento"],
    "Comunicacional": ["Expressão Verbal", "Compreensão", "Pragmática", "Vocabulário"],
    "Socioemocional": ["Regulação Emocional", "Frustração", "Interação Pares", "Autoestima"],
    "Sensorial/Motor": ["Coordenação Fina", "Hipersensibilidade", "Busca Sensorial", "Planejamento Motor"],
    "Acadêmico": ["Leitura", "Escrita", "Cálculo", "Interpretação", "Organização"]
}

LISTA_POTENCIAS = ["Memória Visual", "Musicalidade", "Tecnologia", "Hiperfoco", "Liderança", "Esportes", "Desenho", "Cálculo Mental", "Oralidade", "Criatividade"]
LISTA_PROFISSIONAIS = ["Psicólogo", "Fonoaudiólogo", "Terapeuta Ocupacional", "Neuropediatra", "Psiquiatra", "Psicopedagogo", "Professor de Apoio", "AT"]

# ==============================================================================
# 5. GERENCIAMENTO DE ESTADO
# ==============================================================================
default_state = {
    'nome': '', 'nasc': date(2015, 1, 1), 'serie': None, 'turma': '', 'diagnostico': '', 
    'lista_medicamentos': [], 'composicao_familiar': '', 'historico': '', 'familia': '', 
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
# 6. UTILITÁRIOS (BANCO, PDF, IA)
# ==============================================================================
PASTA_BANCO = "banco_alunos"
if not os.path.exists(PASTA_BANCO): os.makedirs(PASTA_BANCO)

def finding_logo():
    possiveis = ["360.png", "logo.png", "iconeaba.png"]
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
    texto = texto.replace('**', '').replace('__', '').replace('### ', '').replace('## ', '').replace('# ', '')
    return re.sub(r'[^\x00-\xff]', '', texto)

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

def consultar_gpt_pedagogico(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ Configure a Chave API."
    try:
        client = OpenAI(api_key=api_key)
        evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        meds = "\n".join([f"- {m['nome']}" for m in dados['lista_medicamentos']])
        map_txt = ""
        for c, i in dados['barreiras_selecionadas'].items():
            if i: map_txt += f"\n[{c}]: " + ", ".join([f"{x} ({dados['niveis_suporte'].get(f'{c}_{x}','Monitorado')})" for x in i])
        
        estrat = f"Acesso: {', '.join(dados['estrategias_acesso'])} {dados['outros_acesso']}\nEnsino: {', '.join(dados['estrategias_ensino'])} {dados['outros_ensino']}\nAvaliação: {', '.join(dados['estrategias_avaliacao'])}"
        
        monit = f"Status: {dados.get('status_meta')}. Parecer: {dados.get('parecer_geral')}. Ações: {', '.join(dados.get('proximos_passos_select', []))}."

        sys = "Especialista em Educação Inclusiva. GERE RELATÓRIO TÉCNICO (6 SEÇÕES). USE CAIXA ALTA NOS TÍTULOS NUMERADOS. FOCO NA BNCC E HIPERFOCO."
        usr = f"ALUNO: {dados['nome']}\nDIAG: {dados['diagnostico']}\nMEDS: {meds}\nHIST: {dados['historico']}\nEVID: {evid}\nBARREIRAS: {map_txt}\nHIPERFOCO: {dados['hiperfoco']}\nESTRATÉGIAS: {estrat}\nMONITORAMENTO: {monit}\nLAUDO: {contexto_pdf[:5000]}"
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 7. GERADOR PDF
# ==============================================================================
class PDF_V3(FPDF):
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
    pdf = PDF_V3(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    pdf.section_title("1. IDENTIFICAÇÃO E CONTEXTO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    
    med_str = "; ".join([f"{m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']]) if dados['lista_medicamentos'] else "Não informado."
    diag = dados['diagnostico'] if dados['diagnostico'] else ("Vide laudo." if tem_anexo else "Não informado")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nome:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nascimento:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, str(dados['nasc']), 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Série/Turma:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, f"{dados['serie']} - {dados['turma']}", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, diag); pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Medicação:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, med_str); pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Família:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, dados['composicao_familiar'])

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
        for linha in dados['ia_sugestao'].split('\n'):
            l = limpar_texto_pdf(linha)
            if re.match(r'^[1-6]\.', l.strip()) and l.strip().isupper():
                pdf.ln(4); pdf.set_fill_color(240, 248, 255); pdf.set_text_color(0, 78, 146); pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"  {l}", 0, 1, 'L', fill=True); pdf.set_text_color(0); pdf.set_font("Arial", size=10)
            elif l.strip().endswith(':') and len(l) < 70:
                pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(0, 6, l); pdf.set_font("Arial", size=10)
            else: pdf.multi_cell(0, 6, l)
    
    if dados.get('monitoramento_data'):
        pdf.section_title("CRONOGRAMA DE REVISÃO E MONITORAMENTO")
        pdf.set_font("Arial", size=10)
        pp = ', '.join(dados.get('proximos_passos_select', []))
        txt = f"Previsão de Revisão: {dados['monitoramento_data'].strftime('%d/%m/%Y')}\n\nStatus da Meta: {dados.get('status_meta','-')}\n\nParecer Geral: {dados.get('parecer_geral','-')}\n\nPróximos Passos: {pp}"
        pdf.multi_cell(0, 6, limpar_texto_pdf(txt))

    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); style = doc.styles['Normal']; style.font.name = 'Arial'; style.font.size = Pt(11)
    doc.add_heading('PLANO DE ENSINO INDIVIDUALIZADO', 0)
    doc.add_paragraph(f"Estudante: {dados['nome']}")
    if dados['ia_sugestao']: doc.add_paragraph(dados['ia_sugestao'])
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0); return buffer

# ==============================================================================
# 8. INTERFACE UI (PRINCIPAL)
# ==============================================================================
# SIDEBAR
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ OpenAI OK")
    else: api_key = st.text_input("Chave OpenAI:", type="password")
    
    st.markdown("---")
    st.caption("📂 Gestão de Casos")
    st.info("Para salvar, use as opções de Rascunho na aba 'Documento'.")
    st.markdown("---")
    data_atual = date.today().strftime("%d/%m/%Y")
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0;'><b>PEI 360º v17.0</b><br>Gamified Edition<br><b>Rodrigo A. Queiroz</b><br>{data_atual}</div>", unsafe_allow_html=True)

# HEADER
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 60px;">' if logo_path else ""
st.markdown(f"""<div class="header-unified">{img_html}<div><p style="margin:0;">Ecossistema de Inteligência Pedagógica e Inclusiva</p></div></div>""", unsafe_allow_html=True)

# ABAS
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento", "Consultoria IA", "Documento"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(abas)

with tab0: # INÍCIO
    if api_key:
        with st.spinner("Gerando inspiração..."):
            saudacao = gerar_saudacao_ia(api_key)
            noticia = gerar_noticia_ia(api_key)
        
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #004E92 0%, #000428 100%); padding: 20px; border-radius: 16px; color: white; margin-bottom: 20px; box-shadow: 0 8px 15px rgba(0,78,146,0.2);">
            <div style="display:flex; gap:15px; align-items:center;">
                <i class="ri-sparkling-fill" style="font-size: 2rem; color: #FFD700;"></i>
                <div><h3 style="color:white; margin:0; font-size: 1.3rem;">Olá, Educador(a)!</h3><p style="margin:5px 0 0 0; opacity:0.9;">{saudacao}</p></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("### <i class='ri-apps-2-line'></i> Fundamentos", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown("""<a href="https://diversa.org.br/educacao-inclusiva/" target="_blank" style="text-decoration:none;"><div class="rich-card"><i class="ri-book-open-line rich-icon"></i><h3>O que é PEI?</h3><p>Conceitos fundamentais da Educação Inclusiva.</p></div></a>""", unsafe_allow_html=True)
    with c2: st.markdown("""<a href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm" target="_blank" style="text-decoration:none;"><div class="rich-card"><i class="ri-scales-3-line rich-icon"></i><h3>Legislação</h3><p>Lei Brasileira de Inclusão (LBI) e Decretos.</p></div></a>""", unsafe_allow_html=True)
    with c3: st.markdown("""<a href="https://institutoneurosaber.com.br/" target="_blank" style="text-decoration:none;"><div class="rich-card"><i class="ri-brain-line rich-icon"></i><h3>Neurociência</h3><p>Artigos sobre desenvolvimento atípico.</p></div></a>""", unsafe_allow_html=True)
    with c4: st.markdown("""<a href="http://basenacionalcomum.mec.gov.br/" target="_blank" style="text-decoration:none;"><div class="rich-card"><i class="ri-compass-3-line rich-icon"></i><h3>BNCC</h3><p>Base Nacional Comum Curricular Oficial.</p></div></a>""", unsafe_allow_html=True)

    if api_key:
        st.markdown(f"""<div class="highlight-card"><i class="ri-lightbulb-flash-fill" style="font-size: 2rem; color: #F6AD55;"></i><div><h4 style="margin:0; color:#2D3748;">Destaque do Dia (IA)</h4><p style="margin:5px 0 0 0; font-size:0.9rem; color:#4A5568;">{noticia}</p></div></div>""", unsafe_allow_html=True)
    
    st.write(""); st.write("")
    st.caption("🚀 **Novidades v17.0:** Barra de Progresso Gamificada 8-Bit (Acompanhe sua jornada!).")

with tab1: # ESTUDANTE
    renderizar_barra_gamificada() # BARRA DE PROGRESSO AQUI (EMBAIXO DA ABA)
    st.markdown("### <i class='ri-user-star-line'></i> Dossiê do Estudante", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome Completo", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)))
    
    try:
        serie_idx = LISTA_SERIES.index(st.session_state.dados['serie']) if st.session_state.dados['serie'] in LISTA_SERIES else 0
    except: serie_idx = 0
    
    st.session_state.dados['serie'] = c3.selectbox("Série/Ano", LISTA_SERIES, index=serie_idx, placeholder="Selecione...")
    st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'])
    st.markdown("---")
    c1, c2 = st.columns(2)
    st.session_state.dados['historico'] = c1.text_area("Histórico Escolar", st.session_state.dados['historico'], help="Resuma a trajetória escolar: retenções, mudanças de escola e avanços recentes.")
    st.session_state.dados['familia'] = c2.text_area("Contexto Familiar", st.session_state.dados['familia'], help="Quem acompanha os estudos? Há questões familiares impactando?")
    st.session_state.dados['composicao_familiar'] = st.text_input("Composição Familiar", st.session_state.dados['composicao_familiar'])
    st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico", st.session_state.dados['diagnostico'])
    
    with st.container(border=True):
        st.markdown("**Controle de Medicação**")
        c1, c2, c3 = st.columns([3, 2, 1])
        nm = c1.text_input("Nome Med", key="nm_med")
        pos = c2.text_input("Posologia", key="pos_med")
        if c3.button("➕ Add"):
            st.session_state.dados['lista_medicamentos'].append({"nome": nm, "posologia": pos, "escola": False}); st.rerun()
        for i, m in enumerate(st.session_state.dados['lista_medicamentos']):
            c_a, c_b, c_c = st.columns([4, 2, 1])
            with c_a: st.markdown(f"**{m['nome']}**")
            with c_b: m['escola'] = st.checkbox("Na Escola?", m['escola'], key=f"esc_{i}")
            with c_c: 
                if st.button("🗑️", key=f"del_{i}"): st.session_state.dados['lista_medicamentos'].pop(i); st.rerun()
    
    with st.expander("📎 Anexar Laudo"):
        up = st.file_uploader("PDF", type="pdf"); 
        if up: st.session_state.pdf_text = ler_pdf(up)

with tab2: # EVIDÊNCIAS
    renderizar_barra_gamificada()
    st.markdown("### <i class='ri-search-eye-line'></i> Coleta de Evidências", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Currículo**")
        for q in ["Estagnação na aprendizagem", "Dificuldade de generalização", "Dificuldade de abstração", "Lacuna em pré-requisitos"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c2:
        st.markdown("**Atenção**")
        for q in ["Oscilação de foco", "Fadiga mental rápida", "Dificuldade de iniciar tarefas", "Esquecimento recorrente"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c3:
        st.markdown("**Comportamento**")
        for q in ["Dependência de mediação (1:1)", "Baixa tolerância à frustração", "Desorganização de materiais", "Recusa de tarefas"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))

with tab3: # REDE
    renderizar_barra_gamificada()
    st.markdown("### <i class='ri-team-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais", LISTA_PROFISSIONAIS, default=st.session_state.dados['rede_apoio'], placeholder="Selecione...")
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações", st.session_state.dados['orientacoes_especialistas'])

with tab4: # MAPEAMENTO (VISUAL IDÊNTICO AOS PRINTS - BLINDADO)
    renderizar_barra_gamificada()
    st.markdown("### <i class='ri-map-pin-user-line'></i> Mapeamento Integral", unsafe_allow_html=True)
    
    # CONTAINER 1: POTENCIALIDADES
    with st.container(border=True):
        st.markdown("#### <i class='ri-lightbulb-flash-line' style='color:#004E92'></i> Potencialidades e Hiperfoco", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        st.session_state.dados['hiperfoco'] = c1.text_input("Hiperfoco", st.session_state.dados['hiperfoco'], placeholder="Ex: Minecraft, Dinossauros...")
        p_val = [p for p in st.session_state.dados.get('potencias', []) if p in LISTA_POTENCIAS]
        st.session_state.dados['potencias'] = c2.multiselect("Pontos Fortes", LISTA_POTENCIAS, default=p_val, placeholder="Selecione...")
    
    st.divider()
    
    # CONTAINER 2: BARREIRAS
    with st.container(border=True):
        st.markdown("#### <i class='ri-barricade-line' style='color:#FF6B6B'></i> Barreiras e Nível de Suporte", unsafe_allow_html=True)
        c_bar1, c_bar2, c_bar3 = st.columns(3)
        
        def render_cat_barreira(coluna, titulo, chave_json):
            with coluna:
                st.markdown(f"**{titulo}**")
                itens = LISTAS_BARREIRAS[chave_json]
                b_salvas = [b for b in st.session_state.dados['barreiras_selecionadas'].get(chave_json, []) if b in itens]
                sel = st.multiselect("Selecione:", itens, key=f"ms_{chave_json}", default=b_salvas, placeholder="Selecione...", label_visibility="collapsed")
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

with tab5: # PLANO (VISUAL CARDS)
    renderizar_barra_gamificada()
    st.markdown("### <i class='ri-tools-line'></i> Plano de Ação Estratégico", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 1. Acesso (DUA)")
            st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos", ["Tempo Estendido", "Apoio Leitura/Escrita", "Material Ampliado", "Tecnologia Assistiva", "Sala Silenciosa"], default=st.session_state.dados['estrategias_acesso'], placeholder="Selecione...")
            st.session_state.dados['outros_acesso'] = st.text_input("Prática Personalizada (Acesso)", st.session_state.dados['outros_acesso'], placeholder="Ex: Ledor humano, Mesa adaptada...")
    with c2:
        with st.container(border=True):
            st.markdown("#### 2. Ensino")
            st.session_state.dados['estrategias_ensino'] = st.multiselect("Metodologia", ["Fragmentação de Tarefas", "Pistas Visuais", "Mapas Mentais", "Modelagem", "Ensino Híbrido"], default=st.session_state.dados['estrategias_ensino'], placeholder="Selecione...")
            st.session_state.dados['outros_ensino'] = st.text_input("Prática Pedagógica (Ensino)", st.session_state.dados['outros_ensino'], placeholder="Ex: Uso de Material Dourado, Gamificação...")
    with c3:
        with st.container(border=True):
            st.markdown("#### 3. Avaliação")
            st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Formato", ["Prova Adaptada", "Prova Oral", "Consulta Permitida", "Portfólio", "Autoavaliação"], default=st.session_state.dados['estrategias_avaliacao'], placeholder="Selecione...")

with tab6: # MONITORAMENTO (CLICÁVEL)
    renderizar_barra_gamificada()
    st.markdown("### <i class='ri-loop-right-line'></i> Monitoramento e Metas", unsafe_allow_html=True)
    st.info("Preencha os dados abaixo para gerar o ciclo de revisão do PEI.")
    
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.dados['monitoramento_data'] = st.date_input("Próxima Revisão", value=st.session_state.dados.get('monitoramento_data', None))
    with c2:
        st.session_state.dados['status_meta'] = st.selectbox("Status da Meta Atual", ["Não Iniciado", "Em Andamento", "Parcialmente Atingido", "Atingido", "Superado"], index=0, placeholder="Selecione...")

    st.write("")
    st.markdown("#### Parecer e Próximos Passos")
    c3, c4 = st.columns(2)
    with c3:
        st.session_state.dados['parecer_geral'] = st.selectbox("Parecer Geral", ["Manter Estratégias", "Aumentar Suporte", "Reduzir Suporte (Autonomia)", "Alterar Metodologia", "Encaminhar para Especialista"], index=0, placeholder="Selecione...")
    with c4:
        st.session_state.dados['proximos_passos_select'] = st.multiselect("Ações Futuras (Multipla escolha)", ["Reunião com Família", "Encaminhamento Clínico", "Adaptação de Material", "Mudança de Lugar em Sala", "Novo PEI", "Observação em Sala"], placeholder="Selecione...")

with tab7: # IA
    renderizar_barra_gamificada()
    st.markdown("### <i class='ri-robot-2-line'></i> Consultoria IA", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("""<div style="background:#F0F4FF; padding:15px; border-radius:12px; border-left: 4px solid #004E92; color: #2D3748; font-size: 0.95rem;"><b>IA Pedagógica:</b> Cruzamento de dados com BNCC e Neurociência.</div>""", unsafe_allow_html=True)
        with st.expander("🔍 Ver detalhes do processamento"):
            st.markdown("- **BNCC:** Habilidades do Ano vs. Recomposição.\n- **Neurociência:** Funções Executivas.\n- **Engajamento:** Uso do Hiperfoco.")
        
        if st.button("GERAR PLANO AGORA", type="primary"):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: st.session_state.dados['ia_sugestao'] = res; st.success("Sucesso!")
            else: st.error(err)
    with c2:
        if st.session_state.dados['ia_sugestao']: st.text_area("Texto", st.session_state.dados['ia_sugestao'], height=600)

with tab8: # DOCUMENTO & GESTÃO
    st.markdown("### <i class='ri-file-pdf-line'></i> Documento & Gestão", unsafe_allow_html=True)
    if st.session_state.dados['ia_sugestao']:
        c1, c2 = st.columns(2)
        with c1:
            pdf = gerar_pdf_final(st.session_state.dados, len(st.session_state.pdf_text)>0)
            st.download_button("📥 Baixar PDF Pro", pdf, f"PEI_{st.session_state.dados['nome']}.pdf", "application/pdf", type="primary")
        with c2:
            docx = gerar_docx_final(st.session_state.dados)
            st.download_button("📥 Baixar Word", docx, f"PEI_{st.session_state.dados['nome']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            
            st.write("")
            st.markdown("##### 💾 Gestão de Rascunhos")
            json_dados = json.dumps(st.session_state.dados, default=str)
            st.download_button("Baixar Arquivo do Aluno (.json)", json_dados, f"PEI_{st.session_state.dados['nome']}.json", "application/json")
            
            uploaded_json = st.file_uploader("Carregar Arquivo do Aluno", type="json")
            if uploaded_json:
                try:
                    d = json.load(uploaded_json)
                    if 'nasc' in d: d['nasc'] = date.fromisoformat(d['nasc'])
                    if d.get('monitoramento_data'): d['monitoramento_data'] = date.fromisoformat(d['monitoramento_data'])
                    st.session_state.dados.update(d); st.success("Dados carregados!"); st.rerun()
                except: st.error("Erro no arquivo.")
    
    st.divider()
    st.markdown("#### 🗂️ Banco de Estudantes (Local)")
    arquivos = glob.glob(os.path.join(PASTA_BANCO, "*.json"))
    if not arquivos: 
        st.caption("Nenhum estudante salvo no servidor local. Use a opção 'Baixar Arquivo' acima para garantir seus dados.")
    else:
        for arq in arquivos:
            nome = os.path.basename(arq).replace(".json", "").replace("_", " ").title()
            c1, c2, c3 = st.columns([6, 2, 2])
            c1.markdown(f"👤 **{nome}**")
            if c2.button("📂 Abrir", key=f"load_{arq}"):
                d = carregar_aluno(os.path.basename(arq))
                if d: st.session_state.dados = d; st.success("Carregado!"); st.rerun()
            if c3.button("🗑️", key=f"del_{arq}"): excluir_aluno(os.path.basename(arq)); st.rerun()
            
    if st.button("Salvar no Banco Local"):
        ok, msg = salvar_aluno(st.session_state.dados)
        if ok: st.success(msg); st.rerun()
        else: st.error(msg)

st.markdown("---")
