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
    return "📘"

st.set_page_config(
    page_title="PEI 360º",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. ESTILO VISUAL (FIX ABAS + ÍCONES VETORIAIS + CORES VIBRANTES)
# ==============================================================================
def aplicar_estilo_visual():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2D3748; }
        :root { --brand-blue: #004E92; --brand-coral: #FF6B6B; --card-radius: 16px; }
        
        /* FIX DE LAYOUT E REMOÇÃO DA "LINHA FANTASMA" */
        .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; }
        div[data-baseweb="tab-border"] { display: none !important; }
        div[data-baseweb="tab-highlight"] { visibility: hidden !important; } /* Oculta a linha padrão */
        
        /* BARRA DE PROGRESSO COM ÍCONE VETORIAL */
        .minimal-track {
            width: 100%; height: 6px; background-color: #EDF2F7; border-radius: 3px;
            position: relative; margin: 5px 0 35px 0; /* Espaço ajustado */
        }
        .minimal-fill {
            height: 100%; background: linear-gradient(90deg, var(--brand-coral) 0%, #FF8E53 100%);
            border-radius: 3px;
            transition: width 0.6s cubic-bezier(0.25, 1, 0.5, 1);
            box-shadow: 0 2px 5px rgba(255, 107, 107, 0.3);
        }
        .minimal-cursor-icon {
            position: absolute; top: -16px; 
            font-size: 1.8rem; /* Ícone maior */
            color: var(--brand-coral);
            transition: left 0.6s cubic-bezier(0.25, 1, 0.5, 1);
            transform: translateX(-50%); z-index: 10;
            background: white; border-radius: 50%; /* Fundo branco para destacar o ícone */
            width: 35px; height: 35px; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        /* HEADER */
        .header-unified {
            background-color: white; padding: 20px 40px; border-radius: 16px;
            border: 1px solid #E2E8F0; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 20px;
            display: flex; align-items: center; gap: 25px;
        }
        .header-unified span { 
            color: #004E92; font-size: 1.3rem; font-weight: 800; letter-spacing: -0.5px;
        }

        /* ABAS ESTILO PÍLULA (PERFEITAS) */
        .stTabs [data-baseweb="tab-list"] { gap: 12px; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] {
            height: 42px; border-radius: 21px !important; 
            background-color: white; border: 1px solid #E2E8F0;
            color: #718096; font-weight: 700; font-size: 0.85rem; padding: 0 25px;
            transition: all 0.2s ease;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--brand-coral) !important; color: white !important; 
            border-color: var(--brand-coral) !important;
            box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3);
            transform: translateY(-1px);
        }

        /* CARDS MULTICOLORIDOS (INÍCIO) */
        .rich-card {
            background-color: white; padding: 30px; border-radius: 20px; border: 1px solid #EDF2F7;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: all 0.3s ease; cursor: pointer;
            text-align: left; height: 260px; display: flex; flex-direction: column; justify-content: flex-start;
            text-decoration: none; color: inherit; position: relative; overflow: hidden;
        }
        .rich-card:hover { transform: translateY(-8px); box-shadow: 0 15px 30px rgba(0,0,0,0.08); }
        
        .rich-card h3 { margin: 15px 0 10px 0; font-size: 1.25rem; color: #2D3748; font-weight: 800; }
        .rich-card p { font-size: 0.95rem; color: #718096; line-height: 1.6; }
        
        /* Ícones Específicos */
        .icon-box {
            width: 60px; height: 60px; border-radius: 14px; display: flex; align-items: center; justify-content: center;
            font-size: 2rem; margin-bottom: 15px;
        }
        .icon-blue { background-color: #EBF8FF; color: #3182CE; }
        .icon-gold { background-color: #FFFFF0; color: #D69E2E; }
        .icon-pink { background-color: #FFF5F7; color: #D53F8C; }
        .icon-green { background-color: #F0FFF4; color: #38A169; }

        /* INPUTS E BOTÕES */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] { 
            border-radius: 12px !important; border-color: #E2E8F0 !important; 
        }
        div[data-testid="column"] .stButton button { 
            border-radius: 12px !important; font-weight: 800 !important; height: 55px !important; 
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
# 4. GERENCIAMENTO DE ESTADO
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
# 5. UTILITÁRIOS
# ==============================================================================
def calcular_progresso():
    pontos = 0
    total = 7 
    d = st.session_state.dados
    if d['nome']: pontos += 1
    if d['serie']: pontos += 1
    if d['diagnostico']: pontos += 1
    if any(d['checklist_evidencias'].values()): pontos += 1
    if d['hiperfoco']: pontos += 1
    if any(d['barreiras_selecionadas'].values()): pontos += 1
    if d['estrategias_ensino'] or d['estrategias_acesso']: pontos += 1
    return int((pontos / total) * 100)

def render_progresso():
    p = calcular_progresso()
    # Lógica de Ícones Vetoriais (Remix Icons)
    if p < 15: icon_class = "ri-checkbox-blank-circle-line"
    elif p < 100: icon_class = "ri-run-line"
    else: icon_class = "ri-rocket-2-fill"
    
    st.markdown(f"""
    <div class="minimal-track">
        <div class="minimal-fill" style="width: {p}%;"></div>
        <div class="minimal-cursor-icon" style="left: {p}%;"><i class="{icon_class}"></i></div>
    </div>
    """, unsafe_allow_html=True)

PASTA_BANCO = "banco_alunos"
if not os.path.exists(PASTA_BANCO): os.makedirs(PASTA_BANCO)

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

# ==============================================================================
# 6. INTELIGÊNCIA ARTIFICIAL
# ==============================================================================
@st.cache_data(ttl=3600)
def gerar_saudacao_ia(api_key):
    if not api_key: return "Bem-vindo ao PEI 360º."
    try:
        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Frase curta, acolhedora e inspiradora para um professor de educação inclusiva."}], temperature=0.9)
        return res.choices[0].message.content
    except: return "A inclusão é um ato de amor e competência."

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
        
        prompt_sys = """
        Você é um Consultor Pedagógico Especialista em Educação Inclusiva (Tom: Acolhedor, Técnico e Prático).
        Sua missão é ajudar o professor a ver o potencial do aluno e traçar caminhos claros.
        
        ESTRUTURA DA RESPOSTA (Markdown Limpo):
        1. 🌟 VISÃO DO ESTUDANTE: Resumo biopsicossocial focando nas potências.
        2. 🎯 OBJETIVOS DE APRENDIZAGEM (BNCC): 3 objetivos claros e adaptados.
        3. 💡 ESTRATÉGIAS COM HIPERFOCO: Como usar o interesse ({hiperfoco}) para engajar?
        4. 🧩 ADAPTAÇÕES NA SALA: Sugestões práticas de ambiente e material.
        """.format(hiperfoco=dados['hiperfoco'])
        
        prompt_user = f"""
        ALUNO: {dados['nome']} | SÉRIE: {dados['serie']}
        DIAGNÓSTICO: {dados['diagnostico']}
        FAMÍLIA: {familia}
        CONTEXTO FAMILIAR: {dados['familia']}
        POTENCIALIDADES: {', '.join(dados['potencias'])}
        HIPERFOCO: {dados['hiperfoco']}
        BARREIRAS: {json.dumps(dados['barreiras_selecionadas'], ensure_ascii=False)}
        EVIDÊNCIAS: {evid}
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": prompt_user}])
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
        for linha in dados['ia_sugestao'].split('\n'):
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
    if dados['ia_sugestao']: doc.add_paragraph(dados['ia_sugestao'])
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
    
    st.markdown("---")
    st.caption("📂 Gestão de Casos")
    st.info("Para salvar, use as opções de Rascunho na aba 'Documento'.")
    st.markdown("---")
    data_atual = date.today().strftime("%d/%m/%Y")
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0;'><b>PEI 360º v25.0 Polished</b><br>Criado e desenvolvido por<br><b>Rodrigo A. Queiroz</b><br>{data_atual}</div>", unsafe_allow_html=True)

# HEADER
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 110px;">' if logo_path else ""

st.markdown(f"""
<div class="header-unified">
    {img_html}
    <span>Ecossistema de Inteligência Pedagógica e Inclusiva</span>
</div>""", unsafe_allow_html=True)

# ABAS
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento", "Consultoria IA", "Documento"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(abas)

with tab0: # INÍCIO
    if api_key:
        with st.spinner("Gerando inspiração..."):
            saudacao = gerar_saudacao_ia(api_key)
            noticia = gerar_noticia_ia(api_key)
        
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #0F52BA 0%, #004E92 100%); padding: 25px; border-radius: 20px; color: white; margin-bottom: 30px; box-shadow: 0 10px 25px rgba(15, 82, 186, 0.25);">
            <div style="display:flex; gap:20px; align-items:center;">
                <div style="background:rgba(255,255,255,0.2); padding:12px; border-radius:50%;"><i class="ri-sparkling-2-fill" style="font-size: 2rem; color: #FFD700;"></i></div>
                <div><h3 style="color:white; margin:0; font-size: 1.4rem;">Olá, Educador(a)!</h3><p style="margin:5px 0 0 0; opacity:0.95; font-size:1rem;">{saudacao}</p></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("### <i class='ri-apps-2-line'></i> Fundamentos", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown("""<a href="https://diversa.org.br/educacao-inclusiva/" target="_blank" class="rich-card"><div class="icon-box icon-blue"><i class="ri-book-read-line"></i></div><h3>O que é PEI?</h3><p>Descubra os pilares essenciais do Planejamento Educacional Individualizado.</p></a>""", unsafe_allow_html=True)
    with c2: st.markdown("""<a href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm" target="_blank" class="rich-card"><div class="icon-box icon-gold"><i class="ri-government-line"></i></div><h3>Legislação</h3><p>Consulte a Lei Brasileira de Inclusão (LBI) e garanta os direitos do aluno.</p></a>""", unsafe_allow_html=True)
    with c3: st.markdown("""<a href="https://institutoneurosaber.com.br/" target="_blank" class="rich-card"><div class="icon-box icon-pink"><i class="ri-brain-fill"></i></div><h3>Neurociência</h3><p>Entenda o cérebro e os processos de aprendizagem atípica.</p></a>""", unsafe_allow_html=True)
    with c4: st.markdown("""<a href="http://basenacionalcomum.mec.gov.br/" target="_blank" class="rich-card"><div class="icon-box icon-green"><i class="ri-plant-fill"></i></div><h3>BNCC</h3><p>Alinhe as adaptações curriculares com a Base Nacional Comum.</p></a>""", unsafe_allow_html=True)

    if api_key:
        st.markdown(f"""<div class="highlight-card"><i class="ri-lightbulb-flash-fill" style="font-size: 2rem; color: #F59E0B;"></i><div><h4 style="margin:0; color:#1E293B;">💡 Insight de Inclusão</h4><p style="margin:5px 0 0 0; font-size:0.9rem; color:#64748B;">{noticia}</p></div></div>""", unsafe_allow_html=True)
    
    st.write(""); st.write("")
    st.caption("🚀 **Novidades v25.0:** Cores Vibrantes, Ícones Vetoriais e UX Polido.")

with tab1: # ESTUDANTE
    render_progresso()
    
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
    st.session_state.dados['historico'] = c1.text_area("Histórico Escolar", st.session_state.dados['historico'], help="Resuma a trajetória escolar.")
    st.session_state.dados['familia'] = c2.text_area("Contexto Familiar (Detalhes)", st.session_state.dados['familia'], help="Dinâmica familiar e apoio.")
    
    st.session_state.dados['composicao_familiar_tags'] = st.multiselect("Quem mora com o aluno?", LISTA_FAMILIA, default=st.session_state.dados['composicao_familiar_tags'], placeholder="Selecione os familiares...")
    st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico (CID se houver)", st.session_state.dados['diagnostico'])
    
    with st.container(border=True):
        usa_med = st.toggle("💊 O aluno faz uso contínuo de medicação?", value=len(st.session_state.dados['lista_medicamentos']) > 0)
        
        if usa_med:
            c1, c2, c3 = st.columns([3, 2, 1])
            nm = c1.text_input("Nome do Medicamento", key="nm_med")
            pos = c2.text_input("Horário/Posologia", key="pos_med", placeholder="Ex: 1cp após o almoço")
            if c3.button("Adicionar"):
                st.session_state.dados['lista_medicamentos'].append({"nome": nm, "posologia": pos, "escola": False}); st.rerun()
            
            if st.session_state.dados['lista_medicamentos']:
                st.markdown("**Lista Atual:**")
                for i, m in enumerate(st.session_state.dados['lista_medicamentos']):
                    c_a, c_b, c_c, c_d = st.columns([3, 3, 2, 1])
                    with c_a: st.info(f"**{m['nome']}**")
                    with c_b: st.caption(m['posologia'])
                    with c_c: m['escola'] = st.checkbox("Na Escola?", value=m['escola'], key=f"esc_{i}")
                    with c_d: 
                        if st.button("🗑️", key=f"del_{i}"): st.session_state.dados['lista_medicamentos'].pop(i); st.rerun()
    
    with st.expander("📎 Anexar Laudo"):
        up = st.file_uploader("PDF", type="pdf"); 
        if up: st.session_state.pdf_text = ler_pdf(up)

with tab2: # EVIDÊNCIAS
    render_progresso()
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
    render_progresso()
    st.markdown("### <i class='ri-team-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais que atendem o aluno:", LISTA_PROFISSIONAIS, default=st.session_state.dados['rede_apoio'], placeholder="Selecione...")
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações Clínicas Importantes", st.session_state.dados['orientacoes_especialistas'])

with tab4: # MAPEAMENTO
    render_progresso()
    st.markdown("### <i class='ri-map-pin-user-line'></i> Mapeamento Integral", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("#### <i class='ri-lightbulb-flash-line' style='color:#004E92'></i> Potencialidades e Hiperfoco", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        st.session_state.dados['hiperfoco'] = c1.text_input("Hiperfoco (Interesse Intenso)", st.session_state.dados['hiperfoco'], placeholder="Ex: Minecraft, Dinossauros, Desenho...")
        p_val = [p for p in st.session_state.dados.get('potencias', []) if p in LISTA_POTENCIAS]
        st.session_state.dados['potencias'] = c2.multiselect("Pontos Fortes", LISTA_POTENCIAS, default=p_val, placeholder="Selecione...")
    
    st.divider()
    
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

with tab5: # PLANO
    render_progresso()
    st.markdown("### <i class='ri-tools-line'></i> Plano de Ação Estratégico", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 1. Acesso (DUA)")
            st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos", ["Tempo Estendido", "Apoio Leitura/Escrita", "Material Ampliado", "Tecnologia Assistiva", "Sala Silenciosa"], default=st.session_state.dados['estrategias_acesso'], placeholder="Selecione...")
            st.session_state.dados['outros_acesso'] = st.text_input("Prática Personalizada (Acesso)", st.session_state.dados['outros_acesso'])
    with c2:
        with st.container(border=True):
            st.markdown("#### 2. Ensino")
            st.session_state.dados['estrategias_ensino'] = st.multiselect("Metodologia", ["Fragmentação de Tarefas", "Pistas Visuais", "Mapas Mentais", "Modelagem", "Ensino Híbrido"], default=st.session_state.dados['estrategias_ensino'], placeholder="Selecione...")
            st.session_state.dados['outros_ensino'] = st.text_input("Prática Pedagógica (Ensino)", st.session_state.dados['outros_ensino'])
    with c3:
        with st.container(border=True):
            st.markdown("#### 3. Avaliação")
            st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Formato", ["Prova Adaptada", "Prova Oral", "Consulta Permitida", "Portfólio", "Autoavaliação"], default=st.session_state.dados['estrategias_avaliacao'], placeholder="Selecione...")

with tab6: # MONITORAMENTO
    render_progresso()
    st.markdown("### <i class='ri-loop-right-line'></i> Monitoramento e Metas", unsafe_allow_html=True)
    
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
        st.session_state.dados['proximos_passos_select'] = st.multiselect("Ações Futuras", ["Reunião com Família", "Encaminhamento Clínico", "Adaptação de Material", "Mudança de Lugar em Sala", "Novo PEI", "Observação em Sala"], placeholder="Selecione...")

with tab7: # IA
    render_progresso()
    st.markdown("### <i class='ri-robot-2-line'></i> Assistente Pedagógico Inteligente", unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("""
        <div style="background-color: #F8FAFC; border-radius: 12px; padding: 20px; border: 1px solid #E2E8F0;">
            <h4 style="color:#0F52BA; margin-top:0;">🤖 Como posso ajudar?</h4>
            <p style="font-size:0.9rem; color:#64748B;">Vou analisar os dados do estudante (Hiperfoco, Barreiras e Evidências) para sugerir um plano alinhado à BNCC.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        if st.button("✨ GERAR SUGESTÕES PEDAGÓGICAS", type="primary"):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: st.session_state.dados['ia_sugestao'] = res; st.balloons()
            else: st.error(err)
            
    with c2:
        if st.session_state.dados['ia_sugestao']:
            st.markdown("""<div style="background:#FFF; padding:20px; border-radius:12px; border:1px solid #E2E8F0; box-shadow:0 4px 6px rgba(0,0,0,0.05);">""", unsafe_allow_html=True)
            st.markdown(st.session_state.dados['ia_sugestao'])
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("👈 Preencha as abas anteriores e clique no botão para gerar o plano.")

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
