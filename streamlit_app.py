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

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================
def get_favicon():
    if os.path.exists("iconeaba.png"): return "iconeaba.png"
    return "📘"

st.set_page_config(
    page_title="PEI 360º Pro",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. ESTILO VISUAL (CLEAN MODERN & BARRA DE PROGRESSO)
# ==============================================================================
def aplicar_estilo_visual():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        /* CORES E TIPOGRAFIA */
        :root {
            --primary: #0F52BA; /* Azul Safira - Profissional */
            --secondary: #FF7F50; /* Coral - Destaque */
            --success: #10B981; /* Verde - Progresso */
            --bg-light: #F8FAFC;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #334155;
            background-color: var(--bg-light);
        }

        /* BARRA DE PROGRESSO CUSTOMIZADA */
        .progress-container {
            width: 100%;
            background-color: #E2E8F0;
            border-radius: 10px;
            margin: 20px 0;
            height: 12px;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, var(--primary) 0%, #3B82F6 100%);
            border-radius: 10px;
            transition: width 0.5s ease-in-out;
        }
        .progress-label {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
        }

        /* HEADER */
        .header-unified {
            background-color: white;
            padding: 30px;
            border-radius: 12px;
            border-left: 6px solid var(--primary);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            display: flex; align-items: center; gap: 20px;
            margin-bottom: 10px;
        }
        .header-unified h1 {
            color: var(--primary); margin: 0; font-size: 1.8rem; font-weight: 700;
        }
        .header-unified p {
            color: #64748B; margin: 0; font-size: 0.9rem;
        }

        /* ABAS MAIS LIMPAS */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            height: 40px; border-radius: 8px; background-color: white;
            border: 1px solid #CBD5E1; color: #64748B; font-weight: 600; font-size: 0.85rem;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--primary) !important; color: white !important;
            border-color: var(--primary) !important;
        }

        /* CARDS (Início) */
        .rich-card {
            background: white; padding: 25px; border-radius: 12px;
            border: 1px solid #E2E8F0; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            transition: transform 0.2s; height: 100%;
            text-decoration: none; color: inherit; display: block;
        }
        .rich-card:hover { transform: translateY(-3px); border-color: var(--primary); }
        .rich-card h3 { color: var(--primary); font-size: 1.1rem; font-weight: 700; margin-bottom: 5px; }
        .rich-card p { color: #64748B; font-size: 0.9rem; margin: 0; }
        .rich-icon { font-size: 2rem; color: var(--secondary); margin-bottom: 15px; }

        /* CONTAINERS MAPEAMENTO (Mais limpos) */
        .container-box {
            background-color: white; padding: 20px; border-radius: 12px;
            border: 1px solid #E2E8F0; margin-bottom: 15px;
        }
        .section-title {
            font-size: 1.1rem; font-weight: 700; margin-bottom: 15px; display: flex; align-items: center; gap: 10px;
        }

        /* INPUTS */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
            border-radius: 8px !important; border-color: #CBD5E1 !important;
        }
        .stButton button {
            border-radius: 8px !important; font-weight: 700 !important; text-transform: uppercase;
        }
    </style>
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_visual()

# ==============================================================================
# 3. LISTAS DE DADOS
# ==============================================================================
LISTA_SERIES = ["Educação Infantil", "1º Ano (Fund. I)", "2º Ano (Fund. I)", "3º Ano (Fund. I)", "4º Ano (Fund. I)", "5º Ano (Fund. I)", "6º Ano (Fund. II)", "7º Ano (Fund. II)", "8º Ano (Fund. II)", "9º Ano (Fund. II)", "1ª Série (EM)", "2ª Série (EM)", "3ª Série (EM)"]

LISTAS_BARREIRAS = {
    "Cognitivo": ["Atenção Sustentada", "Memória de Trabalho", "Flexibilidade Cognitiva", "Velocidade Processamento"],
    "Comunicacional": ["Fala", "Compreensão", "Uso Social (Pragmática)", "Vocabulário"],
    "Socioemocional": ["Regulação Emocional", "Tolerância à Frustração", "Interação Social", "Autoestima"],
    "Sensorial/Motor": ["Coordenação Motora", "Hipersensibilidade Auditiva", "Busca Sensorial", "Planejamento Motor"],
    "Acadêmico": ["Leitura", "Escrita", "Cálculo", "Interpretação", "Organização"]
}

LISTA_POTENCIAS = ["Memória Visual", "Musicalidade", "Tecnologia", "Hiperfoco", "Liderança", "Esportes", "Desenho", "Cálculo Mental", "Oralidade", "Criatividade"]
LISTA_PROFISSIONAIS = ["Psicólogo", "Fonoaudiólogo", "Terapeuta Ocupacional", "Neuropediatra", "Psicopedagogo", "Professor de Apoio"]

# ==============================================================================
# 4. GERENCIAMENTO DE ESTADO
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
# 5. LÓGICA DA BARRA DE PROGRESSO (NOVIDADE)
# ==============================================================================
def calcular_progresso():
    pontos = 0
    total_pontos = 6 # Nome, Serie, Diag, Hiperfoco, Barreiras, Estrategias
    
    d = st.session_state.dados
    if d['nome']: pontos += 1
    if d['serie']: pontos += 1
    if d['diagnostico']: pontos += 1
    if d['hiperfoco']: pontos += 1
    if any(d['barreiras_selecionadas'].values()): pontos += 1
    if d['estrategias_ensino'] or d['estrategias_acesso']: pontos += 1
    
    return int((pontos / total_pontos) * 100)

# ==============================================================================
# 6. FUNÇÕES UTILITÁRIAS (BANCO, PDF, IA)
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
        # Lógica simplificada para manter robustez
        barreiras_txt = ""
        for c, i in dados['barreiras_selecionadas'].items():
            if i: barreiras_txt += f"\n[{c}]: " + ", ".join([f"{x} ({dados['niveis_suporte'].get(f'{c}_{x}','Monitorado')})" for x in i])
            
        sys = "Especialista em Educação Inclusiva e BNCC. Gere um PEI estruturado. Use o Hiperfoco do aluno como estratégia de engajamento."
        usr = f"ALUNO: {dados['nome']} ({dados['serie']})\nDIAGNÓSTICO: {dados['diagnostico']}\nHIPERFOCO: {dados['hiperfoco']}\nBARREIRAS: {barreiras_txt}\nLAUDO: {contexto_pdf[:3000]}"
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# Gerador PDF (Mantido o Básico Eficiente)
class PDF_V3(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16); self.set_text_color(0, 78, 146)
        self.cell(0, 10, 'PLANO DE ENSINO INDIVIDUALIZADO', 0, 1, 'C')
        self.ln(10)
    def section_title(self, label):
        self.set_fill_color(240, 240, 240); self.set_font('Arial', 'B', 11)
        self.cell(0, 8, f"  {label}", 0, 1, 'L', fill=True); self.ln(4)

def gerar_pdf_final(dados):
    pdf = PDF_V3(); pdf.add_page()
    pdf.section_title("IDENTIFICAÇÃO")
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, f"Nome: {dados['nome']}\nSérie: {dados['serie']}\nDiagnóstico: {dados['diagnostico']}")
    
    if dados['ia_sugestao']:
        pdf.section_title("PLANO ESTRATÉGICO (IA)")
        texto = dados['ia_sugestao'].replace('**', '').replace('###', '')
        pdf.multi_cell(0, 6, texto.encode('latin-1', 'replace').decode('latin-1'))
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); doc.add_heading('PEI - ' + dados['nome'], 0)
    if dados['ia_sugestao']: doc.add_paragraph(dados['ia_sugestao'])
    b = BytesIO(); doc.save(b); b.seek(0); return b

# ==============================================================================
# 7. INTERFACE UI (PRINCIPAL)
# ==============================================================================
# SIDEBAR
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    api_key = st.text_input("Chave OpenAI:", type="password")
    st.markdown("---")
    st.markdown("#### 📂 Banco Local")
    arquivos = glob.glob(os.path.join(PASTA_BANCO, "*.json"))
    for arq in arquivos:
        nome = os.path.basename(arq).replace(".json", "").replace("_", " ").title()
        c1, c2 = st.columns([3, 1])
        c1.text(nome)
        if c2.button("Abrir", key=arq):
            st.session_state.dados = json.load(open(arq))
            st.rerun()

# HEADER UNIFICADO (COM LOGO)
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 50px;">' if logo_path else ""

st.markdown(f"""
<div class="header-unified">
    {img_html}
    <div>
        <h1>PEI 360º</h1>
        <p>Ecossistema de Inteligência Pedagógica</p>
    </div>
</div>
""", unsafe_allow_html=True)

# BARRA DE PROGRESSO (NOVIDADE)
progresso = calcular_progresso()
st.markdown(f"""
<div class="progress-label">
    <span>Status do Preenchimento</span>
    <span>{progresso}%</span>
</div>
<div class="progress-container">
    <div class="progress-bar" style="width: {progresso}%;"></div>
</div>
""", unsafe_allow_html=True)

# ABAS
abas = ["Início", "Estudante", "Evidências", "Rede", "Mapeamento", "Plano", "Monitoramento", "IA & Doc"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(abas)

with tab0: # INÍCIO
    st.markdown("### <i class='ri-apps-2-line'></i> Fundamentos", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown('<a href="#" class="rich-card"><i class="ri-book-open-line rich-icon"></i><h3>O que é PEI?</h3><p>Conceitos fundamentais.</p></a>', unsafe_allow_html=True)
    with c2: st.markdown('<a href="#" class="rich-card"><i class="ri-scales-3-line rich-icon"></i><h3>Legislação</h3><p>LBI e Decretos.</p></a>', unsafe_allow_html=True)
    with c3: st.markdown('<a href="#" class="rich-card"><i class="ri-brain-line rich-icon"></i><h3>Neurociência</h3><p>Desenvolvimento.</p></a>', unsafe_allow_html=True)
    with c4: st.markdown('<a href="#" class="rich-card"><i class="ri-compass-3-line rich-icon"></i><h3>BNCC</h3><p>Base Nacional.</p></a>', unsafe_allow_html=True)

with tab1: # ESTUDANTE
    st.markdown("### <i class='ri-user-star-line'></i> Dossiê", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([3, 1, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome Completo", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", st.session_state.dados['nasc'])
    st.session_state.dados['serie'] = c3.selectbox("Série", LISTA_SERIES)
    
    c4, c5 = st.columns(2)
    st.session_state.dados['historico'] = c4.text_area("Histórico Escolar", st.session_state.dados['historico'])
    st.session_state.dados['diagnostico'] = c5.text_area("Diagnóstico", st.session_state.dados['diagnostico'])
    
    with st.expander("Anexar Laudo (PDF)"):
        up = st.file_uploader("PDF", type="pdf"); 
        if up: st.session_state.pdf_text = ler_pdf(up)

with tab2: # EVIDÊNCIAS
    st.markdown("### <i class='ri-eye-line'></i> Checklist Rápido", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("APRENDIZAGEM")
        for q in ["Dificuldade de abstração", "Lacunas de base"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c2:
        st.caption("ATENÇÃO")
        for q in ["Oscilação de foco", "Fadiga mental"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c3:
        st.caption("COMPORTAMENTO")
        for q in ["Baixa tolerância à frustração", "Desorganização"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))

with tab3: # REDE
    st.markdown("### <i class='ri-group-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais", LISTA_PROFISSIONAIS, default=st.session_state.dados['rede_apoio'])
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações Clínicas", st.session_state.dados['orientacoes_especialistas'])

with tab4: # MAPEAMENTO (ESTRUTURA APROVADA + DESIGN LIMPO)
    st.markdown("### <i class='ri-map-pin-line'></i> Mapeamento Integral", unsafe_allow_html=True)
    
    # 1. POTENCIALIDADES
    st.markdown('<div class="container-box"><div class="section-title" style="color:#10B981"><i class="ri-lightbulb-flash-line"></i> Potencialidades e Hiperfoco</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    st.session_state.dados['hiperfoco'] = c1.text_input("Hiperfoco (Interesse)", st.session_state.dados['hiperfoco'])
    st.session_state.dados['potencias'] = c2.multiselect("Pontos Fortes", LISTA_POTENCIAS, default=st.session_state.dados['potencias'])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 2. BARREIRAS
    st.markdown('<div class="container-box"><div class="section-title" style="color:#FF7F50"><i class="ri-barricade-line"></i> Barreiras e Suporte</div>', unsafe_allow_html=True)
    c_bar1, c_bar2, c_bar3 = st.columns(3)
    
    def render_cat(col, titulo, chave):
        with col:
            st.markdown(f"**{titulo}**")
            itens = LISTAS_BARREIRAS[chave]
            sel = st.multiselect("Selecione", itens, key=f"ms_{chave}", default=[x for x in st.session_state.dados['barreiras_selecionadas'][chave] if x in itens], label_visibility="collapsed")
            st.session_state.dados['barreiras_selecionadas'][chave] = sel
            if sel:
                for x in sel:
                    k = f"{chave}_{x}"
                    st.session_state.dados['niveis_suporte'][k] = st.select_slider(x, ["Leve", "Monitorado", "Intenso"], value=st.session_state.dados['niveis_suporte'].get(k, "Monitorado"), key=f"sl_{k}")
            st.write("")

    render_cat(c_bar1, "Cognitivo", "Cognitivo")
    render_cat(c_bar1, "Sensorial", "Sensorial/Motor")
    render_cat(c_bar2, "Comunicacional", "Comunicacional")
    render_cat(c_bar2, "Acadêmico", "Acadêmico")
    render_cat(c_bar3, "Socioemocional", "Socioemocional")
    st.markdown('</div>', unsafe_allow_html=True)

with tab5: # PLANO
    st.markdown("### <i class='ri-tools-line'></i> Estratégias", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1. Acesso (DUA)**")
        st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos", ["Tempo Estendido", "Ledor", "Material Ampliado"], default=st.session_state.dados['estrategias_acesso'])
    with c2:
        st.markdown("**2. Ensino**")
        st.session_state.dados['estrategias_ensino'] = st.multiselect("Metodologia", ["Pistas Visuais", "Mapas Mentais", "Gamificação"], default=st.session_state.dados['estrategias_ensino'])
    with c3:
        st.markdown("**3. Avaliação**")
        st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Formato", ["Prova Adaptada", "Prova Oral", "Consulta"], default=st.session_state.dados['estrategias_avaliacao'])

with tab6: # MONITORAMENTO
    st.markdown("### <i class='ri-refresh-line'></i> Monitoramento", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    st.session_state.dados['monitoramento_data'] = c1.date_input("Próxima Revisão", st.session_state.dados.get('monitoramento_data', date.today()))
    st.session_state.dados['status_meta'] = c2.selectbox("Status da Meta", ["Não Iniciado", "Em Andamento", "Atingido"])

with tab7: # IA E DOC
    st.markdown("### <i class='ri-robot-2-line'></i> Inteligência & Exportação", unsafe_allow_html=True)
    if st.button("✨ GERAR SUGESTÃO IA", type="primary"):
        res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
        if res: st.session_state.dados['ia_sugestao'] = res; st.success("Gerado!")
        else: st.error(err)
    
    if st.session_state.dados['ia_sugestao']:
        st.text_area("Sugestão da IA", st.session_state.dados['ia_sugestao'], height=400)
        
        c1, c2 = st.columns(2)
        with c1: st.download_button("📥 Baixar PDF", gerar_pdf_final(st.session_state.dados), "PEI.pdf", "application/pdf")
        with c2: st.download_button("📥 Baixar Word", gerar_docx_final(st.session_state.dados), "PEI.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
        if st.button("Salvar no Banco Local"):
            salvar_aluno(st.session_state.dados); st.rerun()
