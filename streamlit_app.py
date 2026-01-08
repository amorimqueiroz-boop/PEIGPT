import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import base64
import os
import re

# --- FUNÇÃO FAVICON ---
def get_favicon():
    if os.path.exists("iconeaba.png"): return "iconeaba.png"
    if os.path.exists("360.png"): return "360.png"
    return "📘"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="PEI 360º | Sistema Inclusivo",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILO VISUAL CORAL & BLUE (ARCO PALETTE) ---
st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
    
    <style>
    /* 1. GLOBAL & CORES */
    html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2D3748; }
    :root { 
        --brand-blue: #004E92;      /* Azul Institucional */
        --brand-coral: #FF6B6B;     /* Coral de Destaque */
        --bg-light: #F7FAFC; 
        --card-shadow: 0 4px 6px rgba(0,0,0,0.04);
    }
    
    /* 2. HEADER */
    .header-container {
        padding: 25px; 
        background: #FFFFFF; 
        border-radius: 20px; 
        border: 1px solid #EDF2F7; 
        border-left: 8px solid var(--brand-blue); 
        box-shadow: var(--card-shadow); 
        margin-bottom: 30px;
        display: flex; align-items: center; gap: 25px;
    }
    
    /* 3. ABAS (CORAL QUANDO SELECIONADO) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px; background-color: transparent; padding: 10px 0;
        justify-content: flex-start; flex-wrap: wrap;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px; background-color: #FFFFFF; border-radius: 20px;
        border: 1px solid #CBD5E0; color: #4A5568; padding: 0 20px;
        font-weight: 700; font-size: 0.9rem; flex-grow: 0; transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--brand-coral) !important;
        color: white !important;
        border-color: var(--brand-coral) !important;
        box-shadow: 0 4px 10px rgba(255, 107, 107, 0.3);
    }

    /* 4. CARDS */
    .feature-card {
        background: white; padding: 25px; border-radius: 20px;
        border: 1px solid #EDF2F7; box-shadow: var(--card-shadow);
        height: 100%; transition: all 0.3s ease;
        display: flex; flex-direction: column; align-items: flex-start;
    }
    .feature-card:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,0,0,0.06); border-color: var(--brand-blue); }
    
    .icon-box {
        width: 45px; height: 45px; background: #E3F2FD; border-radius: 12px;
        display: flex; align-items: center; justify-content: center; margin-bottom: 15px; flex-shrink: 0;
    }
    .icon-box i { font-size: 22px; color: var(--brand-blue); }
    
    .feature-card h4 { color: var(--brand-blue); font-weight: 800; font-size: 1.1rem; margin-bottom: 8px; line-height: 1.3; }
    .feature-card p { font-size: 0.95rem; color: #718096; line-height: 1.5; margin: 0; }

    /* 5. INPUTS & BOTÕES */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 12px !important; border: 1px solid #CBD5E0 !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--brand-blue) !important; box-shadow: 0 0 0 2px rgba(0, 78, 146, 0.2) !important;
    }
    
    div[data-testid="column"] .stButton button[kind="primary"] {
        background-color: var(--brand-coral) !important; 
        color: white !important; border: none !important; border-radius: 12px !important; 
        font-weight: 700 !important; height: 3.5em !important; width: 100%; transition: 0.3s !important;
    }
    div[data-testid="column"] .stButton button[kind="primary"]:hover {
        background-color: #E53E3E !important; transform: scale(1.02) !important;
    }

    div[data-testid="column"] .stButton button[kind="secondary"] {
        background-color: transparent !important; color: var(--brand-blue) !important;
        border: 2px solid var(--brand-blue) !important; border-radius: 12px !important; 
        font-weight: 700 !important; height: 3.5em !important; width: 100%;
    }
    div[data-testid="column"] .stButton button[kind="secondary"]:hover {
        background-color: #EBF8FF !important;
    }

    span[data-baseweb="tag"] { background-color: #EBF8FF !important; border: 1px solid #90CDF4 !important; }
    span[data-baseweb="tag"] span { color: #004E92 !important; }
    div[data-testid="stFileUploader"] section { background-color: #F8FAFC; border: 1px dashed #A0AEC0; }
    
    @media (max-width: 768px) {
        .header-container { flex-direction: column; text-align: center; gap: 15px; }
        .header-text { border-left: none !important; padding-left: 0 !important; border-top: 1px solid #CBD5E0; padding-top: 10px; width: 100%; }
        .stTabs [data-baseweb="tab"] { flex-grow: 1; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---
def finding_logo():
    possiveis = ["360.png", "360.jpg", "logo.png", "logo.jpg"]
    for nome in possiveis:
        if os.path.exists(nome): return nome
    return None

def get_base64_image(image_path):
    if not image_path: return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def ler_pdf(arquivo):
    if arquivo is None: return ""
    try:
        reader = PdfReader(arquivo)
        texto = ""
        for page in reader.pages: texto += page.extract_text() + "\n"
        return texto
    except Exception as e: return f"Erro: {e}"

def limpar_markdown(texto):
    if not texto: return ""
    texto = texto.replace('**', '').replace('__', '')
    texto = texto.replace('### ', '').replace('## ', '').replace('# ', '')
    return texto

def limpar_para_pdf(texto):
    if not texto: return ""
    texto = texto.replace('**', '').replace('__', '')
    texto = texto.replace('### ', '').replace('## ', '').replace('# ', '')
    texto = texto.replace('* ', '• ')
    texto = re.sub(r'[^\x00-\x7F\xA0-\xFF]', '', texto) 
    return texto

# --- INTELIGÊNCIA (AGORA COM HISTÓRICO) ---
def consultar_ia(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ A chave de API não foi detectada."
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        serie = dados['serie'] if dados['serie'] else ""
        foco_bncc = "Campos de Experiência" if "Infantil" in serie else "Habilidades Essenciais"

        prompt_sistema = """
        Você é um Especialista Sênior em Inclusão e Neurociência.
        Gere um parecer técnico para um documento oficial (PEI).
        Seja direto, técnico e empático.
        """
        
        contexto_extra = f"\n📄 LAUDO:{contexto_pdf[:3000]}" if contexto_pdf else ""
        nasc_str = str(dados.get('nasc', ''))
        
        # INJETANDO HISTÓRICO E FAMÍLIA NO PROMPT
        prompt_usuario = f"""
        Estudante: {dados['nome']} | Série: {serie} | Diag: {dados['diagnostico']} | Hiperfoco: {dados['hiperfoco']}
        
        HISTÓRICO ESCOLAR: {dados['historico']}
        CONTEXTO FAMILIAR: {dados['familia']}
        
        Barreiras: {', '.join(dados['b_sensorial'] + dados['b_cognitiva'] + dados['b_social'])}
        Estratégias da Escola: {', '.join(dados['estrategias_acesso'] + dados['estrategias_ensino'])}
        {contexto_extra}
        
        GERE O TEXTO NESTA ESTRUTURA (Sem repetir nome/idade no início):
        
        1. SÍNTESE DO CONTEXTO
        (Resuma brevemente o histórico escolar e familiar, conectando com o diagnóstico e como isso impacta a inclusão hoje).
        
        2. ANÁLISE NEUROFUNCIONAL
        (Explique como o cérebro deste aluno aprende melhor usando o Hiperfoco como alavanca).
        
        3. ESTRATÉGIA BNCC ({foco_bncc})
        (Cite 1 objetivo de aprendizagem central da série e como ele deve ser flexibilizado na prática).
        
        4. RECOMENDAÇÕES DE ROTINA
        (Valide as estratégias escolhidas e sugira uma rotina prática).
        """
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
            temperature=0.7, stream=False
        )
        return response.choices[0].message.content, None
    except Exception as e: return None, f"Erro DeepSeek: {str(e)}"

# --- PDF ---
class PDF(FPDF):
    def header(self):
        logo = finding_logo()
        if logo:
            self.image(logo, x=10, y=8, w=25)
            x = 40
        else: x = 10
        self.set_font('Arial', 'B', 16); self.set_text_color(0, 78, 146)
        self.cell(x)
        # TÍTULO LIMPO (SEM "PEI -")
        self.cell(0, 10, 'PLANO DE ENSINO INDIVIDUALIZADO', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()} | Documento Confidencial', 0, 0, 'C')

def gerar_pdf_nativo(dados):
    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", size=11)
    def txt(t): return str(t).encode('latin-1', 'replace').decode('latin-1')

    # 1. Identificação
    pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0, 78, 146)
    pdf.cell(0, 10, txt("1. IDENTIFICAÇÃO DO ESTUDANTE"), 0, 1)
    pdf.set_font("Arial", size=11); pdf.set_text_color(0)
    
    nasc = dados.get('nasc'); d_nasc = nasc.strftime('%d/%m/%Y') if nasc else "-"
    pdf.multi_cell(0, 7, txt(f"Nome: {dados['nome']} | Série: {dados['serie']}\nNascimento: {d_nasc}\nDiagnóstico: {dados['diagnostico']}"))
    pdf.ln(3)

    # 2. Estratégias
    pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0, 78, 146)
    pdf.cell(0, 10, txt("2. ESTRATÉGIAS EDUCACIONAIS"), 0, 1)
    pdf.set_font("Arial", size=11); pdf.set_text_color(0)
    
    if dados['estrategias_acesso']:
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, txt("Acesso e Organização:"), 0, 1); pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 7, txt(limpar_para_pdf(', '.join(dados['estrategias_acesso']))))
    
    if dados['estrategias_ensino']:
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, txt("Metodologia e Ensino:"), 0, 1); pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 7, txt(limpar_para_pdf(', '.join(dados['estrategias_ensino']))))
        
    if dados['estrategias_avaliacao']:
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, txt("Avaliação Diferenciada:"), 0, 1); pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 7, txt(limpar_para_pdf(', '.join(dados['estrategias_avaliacao']))))
    
    # 3. Parecer IA
    if dados['ia_sugestao']:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0, 78, 146)
        pdf.cell(0, 10, txt("3. PARECER TÉCNICO PEDAGÓGICO"), 0, 1)
        pdf.set_font("Arial", size=11); pdf.set_text_color(50)
        conteudo_ia = limpar_para_pdf(dados['ia_sugestao'])
        pdf.multi_cell(0, 6, txt(conteudo_ia))

    pdf.ln(15); pdf.set_draw_color(0); pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.cell(0, 10, txt("Coordenação Pedagógica / Direção Escolar"), 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def gerar_docx_final(dados):
    doc = Document(); style = doc.styles['Normal']; style.font.name = 'Arial'; style.font.size = Pt(11)
    doc.add_heading('PLANO DE ENSINO INDIVIDUALIZADO', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Nome: {dados['nome']} | Série: {dados['serie']}")
    
    doc.add_heading('Estratégias', level=1)
    doc.add_paragraph(f"Acesso: {', '.join(dados['estrategias_acesso'])}")
    doc.add_paragraph(f"Ensino: {', '.join(dados['estrategias_ensino'])}")
    
    if dados['ia_sugestao']:
        doc.add_heading('Parecer Técnico', level=1)
        doc.add_paragraph(limpar_markdown(dados['ia_sugestao']))
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0)
    return buffer

# --- ESTADO INICIAL ---
if 'dados' not in st.session_state:
    st.session_state.dados = {
        'nome': '', 'nasc': None, 'serie': None, 'escola': '', 'tem_laudo': False, 'diagnostico': '', 
        'rede_apoio': [], 'historico': '', 'familia': '', 'hiperfoco': '', 'potencias': [], 
        'b_sensorial': [], 'sup_sensorial': '🟡 Monitorado',
        'b_cognitiva': [], 'sup_cognitiva': '🟡 Monitorado',
        'b_social': [], 'sup_social': '🟡 Monitorado',
        'estrategias_acesso': [], 'estrategias_ensino': [], 'estrategias_avaliacao': [],
        'ia_sugestao': ''
    }
for k in ['estrategias_ensino', 'estrategias_avaliacao', 'rede_apoio']:
    if k not in st.session_state.dados: st.session_state.dados[k] = []
if 'nasc' not in st.session_state.dados: st.session_state.dados['nasc'] = None
if 'pdf_text' not in st.session_state: st.session_state.pdf_text = ""

# --- SIDEBAR ---
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'DEEPSEEK_API_KEY' in st.secrets:
        api_key = st.secrets['DEEPSEEK_API_KEY']; st.success("✅ Chave Segura")
    else: api_key = st.text_input("Chave API:", type="password")
    st.markdown("---"); st.info("Versão 2.18 | Context Aware")

# --- CABEÇALHO ---
logo = finding_logo()
header_html = ""
if logo:
    mime = "image/png" if logo.lower().endswith("png") else "image/jpeg"
    b64 = get_base64_image(logo)
    header_html = f"""
    <div class="header-container">
        <img src="data:{mime};base64,{b64}" class="header-logo" style="max-height: 105px; width: auto;"> 
        <div class="header-text" style="border-left: 2px solid #E2E8F0; padding-left: 25px;">
            <p style="margin: 0; color: #004E92; font-weight: 700; font-size: 1.2rem;">Planejamento Educacional Individualizado</p>
        </div>
    </div>
    """
else:
    header_html = '<div style="padding: 25px; background: white; border-radius: 20px; border: 1px solid #EDF2F7; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-bottom: 30px;"><h1 style="color: #004E92; margin: 0;">PEI 360º</h1></div>'
st.markdown(header_html, unsafe_allow_html=True)

# ABAS
abas = ["Início", "Estudante", "Mapeamento", "Plano de Ação", "Assistente de IA", "Documento"]
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(abas)

# 1. HOME
with tab1:
    st.markdown("### <i class='ri-dashboard-line'></i> Ecossistema de Inclusão", unsafe_allow_html=True)
    st.write("")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="feature-card">
            <div class="icon-box"><i class="ri-book-open-line"></i></div>
            <h4>O que é o PEI?</h4>
            <p>O PEI não é burocracia, é <b>acessibilidade</b>. É o documento oficial que registra como a escola flexibiliza o ensino para o estudante.</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="feature-card">
            <div class="icon-box"><i class="ri-scales-3-line"></i></div>
            <h4>Legislação (Res. Dez/2025)</h4>
            <p>O PEI é <b>obrigatório</b> para estudantes com barreiras de aprendizagem, <b>independente de laudo médico fechado</b>. A escola deve garantir o suporte.</p>
        </div>
        """, unsafe_allow_html=True)
    st.write("")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("""
        <div class="feature-card">
            <div class="icon-box"><i class="ri-brain-line"></i></div>
            <h4>Neurociência</h4>
            <p>Foco nas <b>Funções Executivas</b>. Entendemos "como" o cérebro processa a informação para criar estratégias assertivas.</p>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown("""
        <div class="feature-card">
            <div class="icon-box"><i class="ri-compass-3-line"></i></div>
            <h4>Base Nacional (BNCC)</h4>
            <p>Não criamos currículo paralelo. <b>Flexibilizamos</b> o oficial. O estudante acessa as mesmas Habilidades Essenciais da série, por caminhos diferentes.</p>
        </div>
        """, unsafe_allow_html=True)

# 2. ESTUDANTE
with tab2:
    st.markdown("### <i class='ri-user-3-line'></i> Dossiê do Estudante", unsafe_allow_html=True)
    st.info("Preencha os dados de identificação e contexto.")
    c1, c2, c3 = st.columns([2, 1, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome do Estudante", st.session_state.dados['nome'])
    val_nasc = st.session_state.dados.get('nasc')
    st.session_state.dados['nasc'] = c2.date_input("Data de Nascimento", val_nasc, format="DD/MM/YYYY")
    st.session_state.dados['serie'] = c3.selectbox("Série/Ano", ["Ed. Infantil", "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano", "6º Ano", "7º Ano", "8º Ano", "9º Ano", "Ensino Médio"], index=None, placeholder="Selecione...")
    
    st.markdown("---")
    st.markdown("##### <i class='ri-history-line'></i> Contexto Escolar", unsafe_allow_html=True)
    ch, cf = st.columns(2)
    st.session_state.dados['historico'] = ch.text_area("Histórico Escolar", st.session_state.dados['historico'], placeholder="Trajetória, retenções, relação com colegas...")
    st.session_state.dados['familia'] = cf.text_area("Escuta da Família", st.session_state.dados['familia'], placeholder="Expectativas, rotina em casa, autonomia...")

    st.markdown("---")
    st.markdown("##### <i class='ri-stethoscope-line'></i> Saúde e Diagnóstico", unsafe_allow_html=True)
    c_diag, c_rede = st.columns(2)
    st.session_state.dados['diagnostico'] = c_diag.text_input("Diagnóstico (ou hipótese)", st.session_state.dados['diagnostico'])
    val_rede = st.session_state.dados.get('rede_apoio', [])
    st.session_state.dados['rede_apoio'] = c_rede.multiselect("Rede de Apoio:", ["Psicólogo", "Fonoaudiólogo", "Neuropediatra", "TO", "Psicopedagogo", "AT"], default=val_rede, placeholder="Selecione...")
    
    st.write("")
    with st.expander("📂 Anexar Laudo Médico (PDF)"):
        uploaded_file = st.file_uploader("Upload do arquivo", type="pdf", key="uploader_tab2")
        if uploaded_file is not None:
            texto = ler_pdf(uploaded_file)
            if texto: st.session_state.pdf_text = texto; st.success("✅ Laudo integrado!")

# 3. MAPEAMENTO
with tab3:
    st.markdown("### <i class='ri-rocket-line'></i> Potencialidades", unsafe_allow_html=True)
    c_pot1, c_pot2 = st.columns(2)
    st.session_state.dados['hiperfoco'] = c_pot1.text_input("Hiperfoco / Áreas de Interesse")
    st.session_state.dados['potencias'] = c_pot2.multiselect("Pontos Fortes", ["Memória Visual", "Tecnologia", "Artes", "Oralidade", "Lógica"], placeholder="Selecione...")
    
    st.markdown("### <i class='ri-barricade-line'></i> Barreiras & Suporte", unsafe_allow_html=True)
    
    with st.expander("Sensorial e Físico", expanded=True):
        st.markdown("#### <i class='ri-eye-line'></i> Perfil Sensorial", unsafe_allow_html=True)
        st.session_state.dados['b_sensorial'] = st.multiselect("Barreiras Identificadas:", ["Hipersensibilidade", "Busca Sensorial", "Seletividade", "Motora"], key="b_sens", placeholder="Selecione...")
        st.write("Nível de Suporte:")
        st.session_state.dados['sup_sensorial'] = st.select_slider("", ["🟢 Autônomo", "🟡 Monitorado", "🟠 Substancial", "🔴 Muito Substancial"], value="🟡 Monitorado", key="s_sens")
    
    with st.expander("Cognitivo"):
        st.markdown("#### <i class='ri-brain-line'></i> Perfil Cognitivo", unsafe_allow_html=True)
        st.session_state.dados['b_cognitiva'] = st.multiselect("Barreiras Identificadas:", ["Atenção Dispersa", "Memória Curta", "Rigidez Mental", "Processamento Lento"], key="b_cog", placeholder="Selecione...")
        st.write("Nível de Suporte:")
        st.session_state.dados['sup_cognitiva'] = st.select_slider("", ["🟢 Autônomo", "🟡 Monitorado", "🟠 Substancial", "🔴 Muito Substancial"], value="🟡 Monitorado", key="s_cog")
    
    with st.expander("Social e Emocional"):
        st.markdown("#### <i class='ri-group-line'></i> Perfil Social", unsafe_allow_html=True)
        st.session_state.dados['b_social'] = st.multiselect("Barreiras Identificadas:", ["Isolamento", "Baixa Tolerância à Frustração", "Interpretação Literal"], key="b_soc", placeholder="Selecione...")
        st.write("Nível de Suporte:")
        st.session_state.dados['sup_social'] = st.select_slider("", ["🟢 Autônomo", "🟡 Monitorado", "🟠 Substancial", "🔴 Muito Substancial"], value="🟡 Monitorado", key="s_soc")

# 4. PLANO DE AÇÃO
with tab4:
    st.markdown("### <i class='ri-checkbox-circle-line'></i> Definição de Estratégias", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("""
        <div class="feature-card">
            <div class="icon-box"><i class="ri-layout-masonry-line"></i></div>
            <h4>1. Acesso & Rotina</h4>
            <p>Recursos para garantir que o aluno "esteja" na aula com qualidade.</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos:", ["Tempo estendido (+25%)", "Apoio à Leitura e Escrita", "Material Ampliado", "Tablet", "Sala Silenciosa", "Pausas"], placeholder="Selecione...")

    with col_b:
        st.markdown("""
        <div class="feature-card">
            <div class="icon-box"><i class="ri-pencil-ruler-2-line"></i></div>
            <h4>2. Metodologia</h4>
            <p>Como o professor deve ensinar o conteúdo.</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.session_state.dados['estrategias_ensino'] = st.multiselect("Estratégias:", ["Fragmentação de Tarefas", "Pistas Visuais", "Mapa Mental", "Redução de Volume", "Multisensorial"], placeholder="Selecione...")

    st.markdown("---")
    st.markdown("""
    <div class="feature-card">
        <div class="icon-box"><i class="ri-file-list-3-line"></i></div>
        <h4>3. Avaliação</h4>
        <p>Como o aluno pode demonstrar o que aprendeu.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Avaliação:", ["Prova Oral", "Sem Distratores", "Consulta Roteiro", "Trabalho/Projeto", "Enunciados Curtos"], placeholder="Selecione...")

# 5. ASSISTENTE DE IA
with tab5:
    col_ia_left, col_ia_right = st.columns([1, 2])
    with col_ia_left:
        st.markdown("### <i class='ri-robot-line'></i> Consultor Inteligente", unsafe_allow_html=True)
        st.info("Minha análise processa o histórico, laudo e barreiras para sugerir um plano pedagógico fundamentado.")
        
        status = "✅ Anexado" if st.session_state.pdf_text else "⚪ Sem anexo"
        st.caption(f"Contexto: {status}")
        
        if st.button("✨ Gerar Parecer do Especialista", type="primary"):
            if not st.session_state.dados['nome']: st.warning("Preencha o nome.")
            else:
                with st.spinner("Analisando Histórico, BNCC e Neurociência..."):
                    res, err = consultar_ia(api_key, st.session_state.dados, st.session_state.pdf_text)
                    if err: st.error(err)
                    else: st.session_state.dados['ia_sugestao'] = res; st.success("Concluído!")
    
    with col_ia_right:
        st.markdown("### <i class='ri-file-text-line'></i> Parecer Técnico", unsafe_allow_html=True)
        if st.session_state.dados['ia_sugestao']:
            st.markdown(f"""
            <div style="background-color: white; padding: 25px; border-radius: 12px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.02); line-height: 1.8;">
                {st.session_state.dados["ia_sugestao"].replace(chr(10), "<br>")}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("O parecer técnico aparecerá aqui após o processamento.")

# 6. DOCUMENTO
with tab6:
    st.markdown("<div style='text-align:center; padding: 30px;'>", unsafe_allow_html=True)
    if st.session_state.dados['nome']:
        c_btn, c_info = st.columns([1, 3])
        with c_btn:
            docx = gerar_docx_final(st.session_state.dados)
            st.download_button("📥 Baixar em Word", docx, f"PEI_{st.session_state.dados['nome']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="secondary")
            st.write("")
            pdf = gerar_pdf_nativo(st.session_state.dados)
            st.download_button("📄 Baixar em PDF", pdf, f"PEI_{st.session_state.dados['nome']}.pdf", "application/pdf", type="primary")
        with c_info:
            st.success("✅ Documento Gerado com Sucesso!")
            st.markdown("Selecione o formato ideal para sua necessidade: **Word** para editar ou **PDF** para arquivar.")
    else:
        st.warning("Preencha o nome do estudante para liberar os downloads.")
    st.markdown("</div>", unsafe_allow_html=True)

# --- RODAPÉ ---
st.markdown("""
<div style="text-align: center; margin-top: 50px; color: #A0AEC0; font-size: 0.85rem; border-top: 1px solid #E2E8F0; padding-top: 20px;">
    Criado e desenvolvido por Rodrigo Queiroz | Versão 2.18
</div>
""", unsafe_allow_html=True)
