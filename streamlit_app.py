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
import glob # ADICIONADO PARA CORRIGIR O ERRO

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================
def get_favicon():
    if os.path.exists("iconeaba.png"): return "iconeaba.png"
    return "📘"

st.set_page_config(
    page_title="PEI 360º",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cria pasta local para Banco de Dados
PASTA_BANCO = "banco_alunos"
if not os.path.exists(PASTA_BANCO):
    os.makedirs(PASTA_BANCO)

# ==============================================================================
# 2. AUTO-REPARO DE DADOS (BLINDAGEM)
# ==============================================================================
default_state = {
    'nome': '', 
    'nasc': date(2015, 1, 1), 
    'serie': None, 
    'turma': '', 
    'diagnostico': '', 
    'lista_medicamentos': [], 
    'composicao_familiar': '', 
    'historico': '', 
    'familia': '', 
    'hiperfoco': '', 
    'potencias': [],
    'rede_apoio': [], 
    'orientacoes_especialistas': '',
    'checklist_evidencias': {}, 
    'barreiras_selecionadas': {'Cognitivo': [], 'Comunicacional': [], 'Socioemocional': [], 'Sensorial/Motor': [], 'Acadêmico': []},
    'niveis_suporte': {}, 
    'estrategias_acesso': [], 
    'estrategias_ensino': [], 
    'estrategias_avaliacao': [], 
    'ia_sugestao': '',
    'outros_acesso': '', 
    'outros_ensino': '', 
    'monitoramento_data': None, 
    'monitoramento_indicadores': '', 
    'monitoramento_proximos': ''
}

if 'dados' not in st.session_state:
    st.session_state.dados = default_state
else:
    for key, val in default_state.items():
        if key not in st.session_state.dados:
            st.session_state.dados[key] = val

if 'pdf_text' not in st.session_state: st.session_state.pdf_text = ""

# ==============================================================================
# 3. UTILITÁRIOS E BANCO
# ==============================================================================
def finding_logo():
    possiveis = ["360.png", "360.jpg", "logo.png", "logo.jpg", "iconeaba.png"]
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
        for i, page in enumerate(reader.pages):
            if i >= 6: break 
            texto += page.extract_text() + "\n"
        return texto
    except Exception as e: return f"Erro ao ler PDF: {e}"

def limpar_texto_pdf(texto):
    if not texto: return ""
    texto = texto.replace('**', '').replace('__', '')
    texto = texto.replace('### ', '').replace('## ', '').replace('# ', '')
    texto = texto.replace('* ', '-') 
    texto = re.sub(r'[^\x00-\xff]', '', texto) 
    return texto

def salvar_aluno(dados):
    if not dados['nome']: return False, "Nome obrigatório."
    nome_arq = re.sub(r'[^a-zA-Z0-9]', '_', dados['nome'].lower()) + ".json"
    caminho = os.path.join(PASTA_BANCO, nome_arq)
    try:
        with open(caminho, 'w', encoding='utf-8') as f: json.dump(dados, f, default=str, ensure_ascii=False, indent=4)
        return True, f"Estudante '{dados['nome']}' salvo com sucesso!"
    except Exception as e: return False, str(e)

def carregar_aluno(nome_arq):
    caminho = os.path.join(PASTA_BANCO, nome_arq)
    try:
        with open(caminho, 'r', encoding='utf-8') as f: d = json.load(f)
        if 'nasc' in d: d['nasc'] = date.fromisoformat(d['nasc'])
        if d.get('monitoramento_data'): d['monitoramento_data'] = date.fromisoformat(d['monitoramento_data'])
        return d
    except: return None

def excluir_aluno(nome_arq):
    try: os.remove(os.path.join(PASTA_BANCO, nome_arq)); return True
    except: return False

# ==============================================================================
# 4. INTELIGÊNCIA ARTIFICIAL
# ==============================================================================
@st.cache_data(ttl=3600)
def gerar_destaque_inclusao(api_key):
    if not api_key: return "Dica: A Lei 13.146 (LBI) garante o direito ao PEI. Mantenha os registros sempre atualizados."
    try:
        client = OpenAI(api_key=api_key)
        prompt = "Escreva uma curiosidade curta ou dica importante sobre Educação Inclusiva, Neurociência ou a legislação brasileira recente. Máximo 2 frases. Use tom inspirador."
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.8)
        return res.choices[0].message.content
    except: return "A inclusão escolar é um direito garantido que transforma a sociedade."

@st.cache_data(ttl=3600)
def gerar_saudacao(api_key):
    if not api_key: return "Bem-vindo ao PEI 360º."
    try:
        client = OpenAI(api_key=api_key)
        prompt = "Escreva uma frase curta de boas vindas para um professor que vai começar um PEI."
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.8)
        return res.choices[0].message.content
    except: return "Bem-vindo ao PEI 360º."

def consultar_gpt_inovacao(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ Configure a Chave API."
    try:
        client = OpenAI(api_key=api_key)
        evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        meds = "\n".join([f"- {m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']])
        map_txt = ""
        for c, i in dados['barreiras_selecionadas'].items():
            if i: map_txt += f"\n[{c}]: " + ", ".join([f"{x} ({dados['niveis_suporte'].get(f'{c}_{x}','Monitorado')})" for x in i])
        
        extra_ac = f" | Outros: {dados.get('outros_acesso','')}"
        extra_en = f" | Outros: {dados.get('outros_ensino','')}"
        estrat = f"Acesso: {', '.join(dados['estrategias_acesso'])}{extra_ac}\nEnsino: {', '.join(dados['estrategias_ensino'])}{extra_en}\nAvaliação: {', '.join(dados['estrategias_avaliacao'])}"

        sys = "Especialista em Educação Inclusiva. GERE O RELATÓRIO TÉCNICO SEGUINDO A NUMERAÇÃO 1 A 6 EM CAIXA ALTA. SEM TÍTULO DE CAPA."
        usr = f"ALUNO: {dados['nome']}\nDIAG: {dados['diagnostico']}\nMEDS: {meds}\nHIST: {dados['historico']}\nEVID: {evid}\nBARREIRAS: {map_txt}\nHIPERFOCO: {dados['hiperfoco']}\nESTRATÉGIAS: {estrat}\nLAUDO: {contexto_pdf[:5000]}"
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 5. GERADOR PDF
# ==============================================================================
class PDF_V3(FPDF):
    def header(self):
        self.set_draw_color(0, 78, 146); self.set_line_width(0.4)
        self.rect(5, 5, 200, 287)
        logo = finding_logo()
        if logo: 
            self.image(logo, 10, 10, 30) # Logo Grande
            x_offset = 45 
        else: x_offset = 12
        self.set_xy(x_offset, 16); self.set_font('Arial', 'B', 16); self.set_text_color(0, 78, 146)
        self.cell(0, 8, 'PLANO DE ENSINO INDIVIDUALIZADO', 0, 1, 'L')
        self.set_xy(x_offset, 23); self.set_font('Arial', 'I', 10); self.set_text_color(100)
        self.cell(0, 5, 'Documento Oficial de Planejamento Pedagógico', 0, 1, 'L')
        self.ln(20)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, f'Gerado via PEI 360º | Página {self.page_no()}', 0, 0, 'C')
    def section_title(self, label):
        self.ln(8); self.set_fill_color(240, 248, 255); self.set_text_color(0, 78, 146)
        self.set_font('Arial', 'B', 11); self.cell(0, 8, f"  {label}", 0, 1, 'L', fill=True); self.ln(4)

def gerar_pdf_final(dados, tem_anexo):
    pdf = PDF_V3(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    
    # 1. Identificação
    pdf.section_title("1. IDENTIFICAÇÃO E CONTEXTO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    med_str = "; ".join([f"{m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']]) if dados['lista_medicamentos'] else "Não informado."
    diag = dados['diagnostico'] if dados['diagnostico'] else ("Vide laudo anexo." if tem_anexo else "Não informado")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nome:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nascimento:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, str(dados['nasc']), 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Série/Turma:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, f"{dados['serie']} - {dados['turma']}", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, diag); pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Medicação:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, med_str); pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Família:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, dados['composicao_familiar'])

    # 2. Evidências
    evidencias = [k.replace('?', '') for k, v in dados['checklist_evidencias'].items() if v]
    if evidencias:
        pdf.section_title("2. PONTOS DE ATENÇÃO (EVIDÊNCIAS)")
        pdf.set_font("Arial", size=10); pdf.multi_cell(0, 6, limpar_texto_pdf('; '.join(evidencias) + '.'))

    # 3. Mapeamento
    if any(dados['barreiras_selecionadas'].values()):
        pdf.section_title("3. MAPEAMENTO DE BARREIRAS E NÍVEIS DE SUPORTE")
        for cat, itens in dados['barreiras_selecionadas'].items():
            if itens:
                pdf.set_font("Arial", 'B', 10); pdf.cell(0, 6, f"{cat}:", 0, 1)
                pdf.set_font("Arial", size=10)
                for i in itens:
                    niv = dados['niveis_suporte'].get(f"{cat}_{i}", "Monitorado")
                    pdf.cell(5); pdf.cell(0, 6, f"- {i}: Suporte {niv}", 0, 1)
                pdf.ln(2)

    # 4. Relatório IA
    if dados['ia_sugestao']:
        pdf.ln(5); pdf.set_text_color(0); pdf.set_font("Arial", '', 10)
        for linha in dados['ia_sugestao'].split('\n'):
            l = limpar_texto_pdf(linha)
            if re.match(r'^[1-6]\.', l.strip()) and l.strip().isupper():
                pdf.ln(4); pdf.set_fill_color(240, 248, 255); pdf.set_text_color(0, 78, 146); pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"  {l}", 0, 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", size=10)
            elif l.strip().endswith(':') and len(l) < 70:
                pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(0, 6, l); pdf.set_font("Arial", size=10)
            else: pdf.multi_cell(0, 6, l)
    
    # 5. Monitoramento
    if dados.get('monitoramento_data'):
        pdf.section_title("CRONOGRAMA DE REVISÃO E MONITORAMENTO")
        pdf.set_font("Arial", size=10)
        txt = f"Revisão: {dados['monitoramento_data'].strftime('%d/%m/%Y')}\n\nIndicadores:\n{dados.get('monitoramento_indicadores','')}\n\nPróximos Passos:\n{dados.get('monitoramento_proximos','')}"
        pdf.multi_cell(0, 6, limpar_texto_pdf(txt))

    pdf.ln(25); y = pdf.get_y(); 
    if y > 250: pdf.add_page(); y = 40
    pdf.line(20, y, 90, y); pdf.line(120, y, 190, y)
    pdf.set_font("Arial", 'I', 8); pdf.text(35, y+5, "Coordenação / Direção"); pdf.text(135, y+5, "Família / Responsável")
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); style = doc.styles['Normal']; style.font.name = 'Arial'; style.font.size = Pt(11)
    doc.add_heading('PLANO DE ENSINO INDIVIDUALIZADO', 0)
    doc.add_paragraph(f"Estudante: {dados['nome']}")
    if dados['ia_sugestao']: doc.add_paragraph(dados['ia_sugestao'])
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0); return buffer

# ==============================================================================
# 6. INTERFACE UI (CSS PROTEGIDO E DESIGN CORRIGIDO)
# ==============================================================================
# IMPORTANTE: Usei aspas triplas normais (não f-string) para o CSS para não dar erro
st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2D3748; }
    :root { --brand-blue: #004E92; --brand-coral: #FF6B6B; --card-radius: 16px; }
    div[data-baseweb="tab-highlight"] { background-color: transparent !important; }
    
    /* CABEÇALHO LIMPO */
    .header-unified {
        background-color: white; padding: 20px 40px; border-radius: var(--card-radius);
        border: 1px solid #EDF2F7; box-shadow: 0 4px 12px rgba(0,0,0,0.04); margin-bottom: 25px;
        display: flex; align-items: center; gap: 25px;
    }
    .header-unified p { color: #004E92; margin: 0; font-size: 1.4rem; font-weight: 800; }

    /* ABAS PÍLULA (PILLS) */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 10px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] {
        height: 42px; border-radius: 20px;
        padding: 0 25px; background-color: white; border: 1px solid #E2E8F0;
        font-weight: 700; color: #718096; font-size: 0.85rem; text-transform: uppercase;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--brand-coral) !important; color: white !important;
        border-color: var(--brand-coral) !important; box-shadow: 0 4px 10px rgba(255, 107, 107, 0.3);
    }

    /* CARDS RICOS E ANIMADOS DA HOME */
    .rich-card {
        background-color: white; padding: 30px; border-radius: 16px; border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: all 0.3s ease; cursor: pointer;
        text-align: left; height: 240px; display: flex; flex-direction: column; justify-content: flex-start;
        text-decoration: none; color: inherit; position: relative; overflow: hidden;
    }
    .rich-card:hover { transform: translateY(-8px); border-color: var(--brand-blue); box-shadow: 0 15px 30px rgba(0,78,146,0.15); }
    .rich-card h3 { margin: 15px 0 10px 0; font-size: 1.2rem; color: var(--brand-blue); font-weight: 800; }
    .rich-card p { font-size: 0.9rem; color: #718096; line-height: 1.5; }
    .rich-icon { font-size: 3rem; color: var(--brand-coral); margin-bottom: 15px; }
    
    /* CARD DE DESTAQUE IA */
    .highlight-card {
        background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); border-left: 6px solid #FFD700;
        border-radius: 12px; padding: 20px; margin-top: 15px; margin-bottom: 20px;
        display: flex; align-items: center; gap: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    }

    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius: 12px !important; border-color: #E2E8F0 !important; }
    div[data-testid="column"] .stButton button { border-radius: 12px !important; font-weight: 800 !important; text-transform: uppercase; height: 50px !important; }
    </style>
""", unsafe_allow_html=True)

# SIDEBAR (Limpa)
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ OpenAI OK")
    else: api_key = st.text_input("Chave OpenAI:", type="password")
    st.markdown("---")
    data_atual = date.today().strftime("%d/%m/%Y")
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0;'><b>PEI 360º v6.2</b><br>Rodrigo A. Queiroz</div>", unsafe_allow_html=True)

# CABEÇALHO (LOGO + TEXTO)
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 60px;">' if logo_path else ""
st.markdown(f"""
<div class="header-unified">
    {img_html}
    <div><p>Ecossistema de Inteligência Pedagógica e Inclusiva</p></div>
</div>
""", unsafe_allow_html=True)

# ABAS (NOMES ORIGINAIS COMPLETOS)
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento", "Consultoria IA", "Documento"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(abas)

with tab0: # INÍCIO (PORTAL RICO)
    
    # BOAS VINDAS IA
    if api_key:
        with st.spinner("Carregando inspiração..."):
            saudacao = gerar_saudacao(api_key)
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #004E92 0%, #000428 100%); padding: 25px; border-radius: 16px; color: white; margin-bottom: 20px; box-shadow: 0 8px 20px rgba(0,78,146,0.25);">
            <div style="display:flex; gap:15px; align-items:center;">
                <i class="ri-sparkling-fill" style="font-size: 2.2rem; color: #FFD700;"></i>
                <div>
                    <h2 style="color:white; margin:0; font-size: 1.5rem;">Olá, Educador(a)!</h2>
                    <p style="margin:5px 0 0 0; opacity:0.95; font-size: 1rem; line-height: 1.4;">{saudacao}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 4 CARDS ORIGINAIS (RICOS E CLICÁVEIS)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""
        <a href="https://diversa.org.br/educacao-inclusiva/" target="_blank" style="text-decoration:none;">
            <div class="rich-card">
                <i class="ri-book-open-line rich-icon"></i>
                <h3>O que é PEI?</h3>
                <p>Compreenda o Plano de Ensino Individualizado como um instrumento jurídico e pedagógico.</p>
            </div>
        </a>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <a href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm" target="_blank" style="text-decoration:none;">
            <div class="rich-card">
                <i class="ri-scales-3-line rich-icon"></i>
                <h3>Legislação</h3>
                <p>Acesse na íntegra a Lei Brasileira de Inclusão (LBI) e os novos decretos.</p>
            </div>
        </a>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <a href="https://institutoneurosaber.com.br/" target="_blank" style="text-decoration:none;">
            <div class="rich-card">
                <i class="ri-brain-line rich-icon"></i>
                <h3>Neurociência</h3>
                <p>Artigos científicos sobre desenvolvimento atípico e neuroplasticidade.</p>
            </div>
        </a>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown("""
        <a href="http://basenacionalcomum.mec.gov.br/" target="_blank" style="text-decoration:none;">
            <div class="rich-card">
                <i class="ri-compass-3-line rich-icon"></i>
                <h3>BNCC</h3>
                <p>Consulte as Competências Gerais e Habilidades essenciais.</p>
            </div>
        </a>
        """, unsafe_allow_html=True)

    # ÁREA DE DESTAQUE IA (RODAPÉ)
    if api_key:
        destaque = gerar_destaque_inclusao(api_key)
        st.markdown(f"""
        <div class="highlight-card">
            <i class="ri-lightbulb-flash-fill" style="font-size: 2.5rem; color: #F6AD55;"></i>
            <div>
                <h4 style="margin:0; color:#2D3748;">💡 Destaque do Dia (IA)</h4>
                <p style="margin:5px 0 0 0; font-size:0.95rem; color:#4A5568;">{destaque}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab1: # ESTUDANTE
    st.markdown("### <i class='ri-user-star-line'></i> Dossiê do Estudante", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome Completo", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)))
    st.session_state.dados['serie'] = c3.selectbox("Série", ["Infantil", "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano", "6º Ano", "7º Ano", "8º Ano", "9º Ano", "Ensino Médio"])
    st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'])
    st.markdown("---")
    c1, c2 = st.columns(2)
    st.session_state.dados['historico'] = c1.text_area("Histórico Escolar", st.session_state.dados['historico'])
    st.session_state.dados['familia'] = c2.text_area("Contexto Familiar", st.session_state.dados['familia'])
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
    st.markdown("### <i class='ri-search-eye-line'></i> Coleta de Evidências", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Currículo**")
        for q in ["Não avança?", "Dificuldade generalizar?", "Interpretação?"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c2:
        st.markdown("**Atenção**")
        for q in ["Se perde?", "Esquece rápido?", "Demora iniciar?"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c3:
        st.markdown("**Comportamento**")
        for q in ["Explicação 1:1?", "Frustração?", "Desorganização?"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))

with tab3: # REDE
    st.markdown("### <i class='ri-team-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais", ["Psicólogo", "Fono", "Neuro", "Psicopedagogo"], default=st.session_state.dados['rede_apoio'])
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações", st.session_state.dados['orientacoes_especialistas'])

with tab4: # MAPA
    st.markdown("### <i class='ri-map-pin-user-line'></i> Potencialidades & Barreiras", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        st.session_state.dados['hiperfoco'] = c1.text_input("Hiperfoco", st.session_state.dados['hiperfoco'])
        st.session_state.dados['potencias'] = c2.multiselect("Potências", ["Memória", "Lógica", "Criatividade", "Artes"], default=st.session_state.dados['potencias'])
    st.divider()
    cats = {"Cognitivo": ["Atenção", "Memória"], "Comunicacional": ["Expressão", "Compreensão"], "Socioemocional": ["Interação", "Regulação"]}
    cols = st.columns(3); idx=0
    for c, i in cats.items():
        with cols[idx%3]:
            with st.container():
                st.markdown(f"**{c}**")
                sel = st.multiselect("Barreiras", i, key=f"bar_{c}", default=st.session_state.dados['barreiras_selecionadas'].get(c, []))
                st.session_state.dados['barreiras_selecionadas'][c] = sel
                for x in sel: st.session_state.dados['niveis_suporte'][f"{c}_{x}"] = st.select_slider(x, ["Autônomo", "Monitorado", "Substancial"], key=f"sl_{x}")
        idx+=1

with tab5: # PLANO
    st.markdown("### <i class='ri-tools-line'></i> Plano de Ação", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.dados['estrategias_acesso'] = st.multiselect("Acesso", ["Tempo Estendido", "Apoio à Leitura e Escrita"], default=st.session_state.dados['estrategias_acesso'])
        st.session_state.dados['outros_acesso'] = st.text_input("Outros (Acesso)", st.session_state.dados['outros_acesso'])
    with c2:
        st.session_state.dados['estrategias_ensino'] = st.multiselect("Ensino", ["Pistas Visuais", "Fragmentação"], default=st.session_state.dados['estrategias_ensino'])
        st.session_state.dados['outros_ensino'] = st.text_input("Outros (Ensino)", st.session_state.dados['outros_ensino'])
    with c3:
        st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Avaliação", ["Prova Adaptada", "Oral"], default=st.session_state.dados['estrategias_avaliacao'])

with tab6: # MONITORAMENTO
    st.markdown("### <i class='ri-loop-right-line'></i> Monitoramento (PDCA)", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    st.session_state.dados['monitoramento_data'] = c1.date_input("Próxima Revisão", value=st.session_state.dados.get('monitoramento_data', None))
    st.session_state.dados['monitoramento_indicadores'] = c2.text_area("Indicadores de Sucesso", st.session_state.dados['monitoramento_indicadores'])
    st.session_state.dados['monitoramento_proximos'] = st.text_area("Próximos Passos", st.session_state.dados['monitoramento_proximos'])

with tab7: # IA
    st.markdown("### <i class='ri-robot-2-line'></i> Consultoria IA", unsafe_allow_html=True)
    if st.button("Gerar Plano", type="primary"):
        res, err = consultar_gpt_inovacao(api_key, st.session_state.dados, st.session_state.pdf_text)
        if res: st.session_state.dados['ia_sugestao'] = res
    if st.session_state.dados['ia_sugestao']: st.text_area("Editor", st.session_state.dados['ia_sugestao'], height=500)

with tab8: # DOCUMENTO
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
            if st.button("💾 Salvar no Banco"):
                ok, msg = salvar_aluno(st.session_state.dados)
                if ok: st.success(msg); st.rerun()
                else: st.error(msg)

    st.divider()
    st.markdown("#### 🗂️ Banco de Estudantes")
    arquivos = glob.glob(os.path.join(PASTA_BANCO, "*.json"))
    if not arquivos: st.caption("Vazio.")
    for arq in arquivos:
        nome = os.path.basename(arq).replace(".json", "").replace("_", " ").title()
        c1, c2, c3 = st.columns([6, 2, 2])
        c1.markdown(f"👤 **{nome}**")
        if c2.button("📂 Abrir", key=f"load_{arq}"):
            d = carregar_aluno(os.path.basename(arq))
            if d: st.session_state.dados = d; st.success("Carregado!"); st.rerun()
        if c3.button("🗑️", key=f"del_{arq}"): excluir_aluno(os.path.basename(arq)); st.rerun()

st.markdown("---")
