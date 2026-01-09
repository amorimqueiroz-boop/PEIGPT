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

# ==============================================================================
# 1. CONFIGURAÇÃO E UTILITÁRIOS GLOBAIS
# ==============================================================================
def get_favicon():
    if os.path.exists("iconeaba.png"): return "iconeaba.png"
    return "📘"

st.set_page_config(
    page_title="PEI 360º | Plataforma",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    texto = texto.replace('–', '-').replace('—', '-')
    texto = texto.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    texto = re.sub(r'[^\x00-\xff]', '', texto) 
    return texto

# --- CLASSE PDF ---
class PDF_V3(FPDF):
    def header(self):
        self.set_draw_color(0, 78, 146); self.set_line_width(0.4)
        self.rect(5, 5, 200, 287)
        logo = finding_logo()
        if logo: 
            self.image(logo, 10, 10, 30)
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

# --- GERADOR PDF ---
def gerar_pdf_final(dados, tem_anexo):
    pdf = PDF_V3(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    
    # 1. Identificação
    pdf.section_title("1. IDENTIFICAÇÃO E CONTEXTO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    
    med_str = "; ".join([f"{m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']]) if dados['lista_medicamentos'] else "Não informado / Não faz uso."
    diag = dados['diagnostico'] if dados['diagnostico'] else ("Vide análise detalhada no parecer técnico" if tem_anexo else "Não informado")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nome:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Nascimento:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, str(dados['nasc']), 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Série/Turma:", 0, 0); pdf.set_font("Arial", '', 10); pdf.cell(0, 6, f"{dados['serie']} - {dados['turma']}", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, diag)
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Medicação:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, med_str)
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.cell(40, 6, "Família:", 0, 0); pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 6, dados['composicao_familiar'])

    # 2. Evidências
    evidencias = [k.replace('?', '') for k, v in dados['checklist_evidencias'].items() if v]
    if evidencias:
        pdf.section_title("2. PONTOS DE ATENÇÃO (EVIDÊNCIAS OBSERVADAS)")
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 6, limpar_texto_pdf('; '.join(evidencias) + '.'))

    # 3. Mapeamento
    tem_barreiras = any(dados['barreiras_selecionadas'].values())
    if tem_barreiras:
        pdf.section_title("3. MAPEAMENTO DE BARREIRAS E NÍVEIS DE SUPORTE")
        pdf.set_font("Arial", size=10)
        for categoria, itens in dados['barreiras_selecionadas'].items():
            if itens:
                pdf.set_font("Arial", 'B', 10); pdf.cell(0, 6, f"{categoria}:", 0, 1)
                pdf.set_font("Arial", size=10)
                for item in itens:
                    nivel = dados['niveis_suporte'].get(f"{categoria}_{item}", "Monitorado")
                    pdf.cell(5); pdf.cell(0, 6, f"- {item}: Suporte {nivel}", 0, 1)
                pdf.ln(2)

    # 4. Relatório IA
    if dados['ia_sugestao']:
        pdf.ln(5)
        pdf.set_text_color(0); pdf.set_font("Arial", '', 10)
        linhas = dados['ia_sugestao'].split('\n')
        for linha in linhas:
            linha_limpa = limpar_texto_pdf(linha)
            if re.match(r'^[1-6]\.', linha_limpa.strip()) and linha_limpa.strip().isupper():
                pdf.ln(4); pdf.set_fill_color(240, 248, 255); pdf.set_text_color(0, 78, 146); pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"  {linha_limpa}", 0, 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", size=10)
            elif linha_limpa.strip().endswith(':') and len(linha_limpa) < 70:
                pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(0, 6, linha_limpa); pdf.set_font("Arial", size=10)
            else:
                pdf.multi_cell(0, 6, linha_limpa)
    
    # 5. Monitoramento (V5.3)
    if 'monitoramento_data' in dados and dados['monitoramento_data']:
        pdf.section_title("CRONOGRAMA DE REVISÃO E MONITORAMENTO")
        pdf.set_font("Arial", size=10)
        rev_txt = f"Data Prevista para Revisão: {dados['monitoramento_data']}\nIndicadores de Sucesso: {dados['monitoramento_indicadores']}\nPróximos Passos: {dados['monitoramento_proximos']}"
        pdf.multi_cell(0, 6, limpar_texto_pdf(rev_txt))

    pdf.ln(25); y = pdf.get_y(); 
    if y > 250: pdf.add_page(); y = 40
    pdf.line(20, y, 90, y); pdf.line(120, y, 190, y)
    pdf.set_font("Arial", 'I', 8); pdf.text(35, y+5, "Coordenação / Direção"); pdf.text(135, y+5, "Família / Responsável")
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx_final(dados):
    doc = Document(); style = doc.styles['Normal']; style.font.name = 'Arial'; style.font.size = Pt(11)
    doc.add_heading('PLANO DE ENSINO INDIVIDUALIZADO', 0)
    doc.add_paragraph(f"Estudante: {dados['nome']} | Série: {dados['serie']}")
    if dados['ia_sugestao']: doc.add_heading('Parecer Técnico', level=1); doc.add_paragraph(dados['ia_sugestao'])
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0); return buffer

# --- CSS ---
st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/remixicon@4.1.0/fonts/remixicon.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2D3748; }
    :root { --brand-blue: #004E92; --brand-coral: #FF6B6B; --card-radius: 16px; }
    div[data-baseweb="tab-highlight"] { background-color: transparent !important; }
    .unified-card { background-color: white; padding: 25px; border-radius: var(--card-radius); border: 1px solid #EDF2F7; box-shadow: 0 4px 6px rgba(0,0,0,0.03); margin-bottom: 20px; }
    .header-clean { background-color: white; padding: 35px 40px; border-radius: var(--card-radius); border: 1px solid #EDF2F7; box-shadow: 0 4px 12px rgba(0,0,0,0.04); margin-bottom: 30px; display: flex; align-items: center; gap: 30px; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; padding-bottom: 10px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { height: 40px; border-radius: 20px; padding: 0 20px; background-color: white; border: 1px solid #E2E8F0; font-weight: 700; color: #718096; font-size: 0.9rem; }
    .stTabs [aria-selected="true"] { background-color: var(--brand-coral) !important; color: white !important; border-color: var(--brand-coral) !important; box-shadow: 0 4px 10px rgba(255, 107, 107, 0.2); }
    .stTooltipIcon { color: var(--brand-blue) !important; cursor: help; }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius: 12px !important; border-color: #E2E8F0 !important; }
    div[data-testid="column"] .stButton button { border-radius: 12px !important; font-weight: 800 !important; text-transform: uppercase; height: 50px !important; letter-spacing: 0.5px; }
    .icon-box { width: 48px; height: 48px; background: #EBF8FF; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; color: var(--brand-blue); font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

# --- ESTADO INICIAL ---
default_state = {
    'nome': '', 'nasc': date(2015, 1, 1), 'serie': None, 'turma': '', 'diagnostico': '', 
    'lista_medicamentos': [], 'composicao_familiar': '', 'historico': '', 'familia': '', 'hiperfoco': '', 'potencias': [],
    'rede_apoio': [], 'orientacoes_especialistas': '',
    'checklist_evidencias': {}, 
    'barreiras_selecionadas': {'Cognitivo': [], 'Comunicacional': [], 'Socioemocional': [], 'Sensorial/Motor': [], 'Acadêmico': []},
    'niveis_suporte': {}, 
    'estrategias_acesso': [], 'estrategias_ensino': [], 'estrategias_avaliacao': [], 'ia_sugestao': '',
    'outros_acesso': '', 'outros_ensino': '', 'monitoramento_data': None, 'monitoramento_indicadores': '', 'monitoramento_proximos': ''
}

if 'dados' not in st.session_state: st.session_state.dados = default_state
else:
    for key, val in default_state.items():
        if key not in st.session_state.dados: st.session_state.dados[key] = val
if 'pdf_text' not in st.session_state: st.session_state.pdf_text = ""

# ==============================================================================
# DEFINIÇÃO DAS FUNÇÕES RENDERIZADORAS (CORREÇÃO DO NAMEERROR)
# ==============================================================================

# --- VERSÃO 5.2 (ESTÁVEL) ---
def render_v5_2(api_key):
    st.info("🔒 Você está usando a Versão Estável (5.2).")
    
    def consultar_gpt_v52(api_key, dados, contexto_pdf=""):
        if not api_key: return None, "⚠️ Configure a Chave API."
        try:
            client = OpenAI(api_key=api_key)
            contexto = contexto_pdf[:5000] if contexto_pdf else "Sem laudo."
            evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
            meds = "\n".join([f"- {m['nome']}" for m in dados['lista_medicamentos']]) if dados['lista_medicamentos'] else "Nenhuma."
            map_txt = ""
            for c, i in dados['barreiras_selecionadas'].items():
                if i: map_txt += f"\n[{c}]: " + ", ".join(i)
            
            sys = "Você é um Neuropsicopedagogo. GERE O RELATÓRIO TÉCNICO SEGUINDO A NUMERAÇÃO 1 A 5 (CAIXA ALTA NOS TÍTULOS). NÃO COLOQUE TÍTULO NO DOCUMENTO."
            usr = f"ALUNO: {dados['nome']}\nDIAG: {dados['diagnostico']}\nMEDS: {meds}\nHIST: {dados['historico']}\nEVID: {evid}\nBARREIRAS: {map_txt}\nLAUDO: {contexto}\nGERE: 1. PERFIL, 2. BNCC, 3. DIRETRIZES, 4. INTERVENÇÃO, 5. PARECER."
            res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}])
            return res.choices[0].message.content, None
        except Exception as e: return None, str(e)

    abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Consultoria IA", "Documento"]
    t = st.tabs(abas)

    with t[0]: st.markdown("### Visão Geral v5.2"); st.write("Sistema Blindado.")
    with t[1]: 
        c1, c2 = st.columns(2)
        st.session_state.dados['nome'] = c1.text_input("Nome", st.session_state.dados['nome'], key="v52_nm")
        st.session_state.dados['diagnostico'] = c2.text_input("Diagnóstico", st.session_state.dados['diagnostico'], key="v52_dg")
        st.caption("Use os campos padrão (compartilhados).")
    with t[6]:
        if st.button("Gerar PEI", key="v52_go"):
            res, err = consultar_gpt_v52(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: st.session_state.dados['ia_sugestao'] = res
        if st.session_state.dados['ia_sugestao']: st.text_area("Texto", st.session_state.dados['ia_sugestao'], height=400, key="v52_edit")
    with t[7]:
        if st.session_state.dados['ia_sugestao']:
            pdf = gerar_pdf_final(st.session_state.dados, len(st.session_state.pdf_text)>0)
            st.download_button("Baixar PDF", pdf, "pei.pdf", "application/pdf", key="v52_dl")

# --- VERSÃO 5.3 (INOVAÇÃO) ---
def render_v5_3(api_key):
    st.success("🚀 Versão 5.3 Beta (Inovação).")
    
    with st.sidebar:
        st.markdown("---")
        st.caption("📂 Rascunhos")
        jd = json.dumps(st.session_state.dados, default=str)
        st.download_button("💾 Salvar JSON", jd, "pei.json", "application/json", key="v53_jd")
        up = st.file_uploader("Carregar JSON", type="json", key="v53_ju")
        if up:
            try: st.session_state.dados.update(json.load(up)); st.success("Carregado!"); st.rerun()
            except: st.error("Erro no arquivo.")

    def consultar_gpt_v53(api_key, dados, contexto_pdf=""):
        if not api_key: return None, "⚠️ Configure a Chave API."
        try:
            client = OpenAI(api_key=api_key)
            contexto = contexto_pdf[:5000] if contexto_pdf else "Sem laudo."
            evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
            meds = "\n".join([f"- {m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']])
            
            map_txt = ""
            for c, i in dados['barreiras_selecionadas'].items():
                if i: map_txt += f"\n[{c}]: " + ", ".join([f"{x} ({dados['niveis_suporte'].get(f'{c}_{x}','Monitorado')})" for x in i])
            
            extra = f"Outros Acesso: {dados.get('outros_acesso','')}"
            sys = "Você é um Neuropsicopedagogo. GERE O RELATÓRIO TÉCNICO SEGUINDO A NUMERAÇÃO 1 A 6. INCLUA MONITORAMENTO."
            usr = f"ALUNO: {dados['nome']}\nDIAG: {dados['diagnostico']}\nMEDS: {meds}\nEVID: {evid}\nBARREIRAS: {map_txt}\nEXTRA: {extra}\nLAUDO: {contexto}\nGERE: 1. PERFIL, 2. BNCC, 3. DIRETRIZES, 4. INTERVENÇÃO, 5. MONITORAMENTO, 6. PARECER."
            res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}])
            return res.choices[0].message.content, None
        except Exception as e: return None, str(e)

    abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento (Novo)", "Consultoria IA", "Documento"]
    t = st.tabs(abas)

    with t[0]:
        c1, c2 = st.columns(2)
        with c1: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-rocket-line"></i></div><h4>PEI 360º Pro</h4><p>Recursos avançados.</p></div>""", unsafe_allow_html=True)
        with c2: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-save-line"></i></div><h4>Salvar & Carregar</h4><p>Gestão de rascunhos.</p></div>""", unsafe_allow_html=True)

    with t[1]: # ESTUDANTE
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        st.session_state.dados['nome'] = c1.text_input("Nome", st.session_state.dados['nome'], key="v53_nm")
        st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)), key="v53_dt")
        lista_series = ["Educação Infantil", "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano", "6º Ano", "7º Ano", "8º Ano", "9º Ano", "Ensino Médio"]
        st.session_state.dados['serie'] = c3.selectbox("Série", lista_series, key="v53_sr")
        st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'], key="v53_tm")
        st.markdown("---")
        c_h1, c_h2 = st.columns(2)
        st.session_state.dados['historico'] = c_h1.text_area("Histórico", st.session_state.dados['historico'], height=100, key="v53_hs")
        st.session_state.dados['familia'] = c_h2.text_area("Família", st.session_state.dados['familia'], height=100, key="v53_fm")
        st.session_state.dados['composicao_familiar'] = st.text_input("Composição Familiar", st.session_state.dados.get('composicao_familiar',''), key="v53_cf")
        st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico", st.session_state.dados['diagnostico'], key="v53_dg")
        
        with st.container(border=True):
            st.markdown("**Medicação**")
            c_m1, c_m2, c_m3 = st.columns([3, 2, 1])
            nm = c_m1.text_input("Nome", key="v53_md_nm")
            ps = c_m2.text_input("Posologia", key="v53_md_ps")
            es = c_m3.checkbox("Escola?", key="v53_md_es")
            if st.button("Add Med", key="v53_add_md"):
                st.session_state.dados['lista_medicamentos'].append({"nome": nm, "posologia": ps, "escola": es}); st.rerun()
            for i, m in enumerate(st.session_state.dados['lista_medicamentos']):
                st.caption(f"{m['nome']} ({m['posologia']})")
                if st.button(f"X {i}", key=f"v53_del_{i}"): st.session_state.dados['lista_medicamentos'].pop(i); st.rerun()
        
        with st.expander("Laudo PDF"):
            up = st.file_uploader("Arquivo", type="pdf", key="v53_up")
            if up: st.session_state.pdf_text = ler_pdf(up)

    with t[2]: # EVIDENCIAS
        st.markdown("**Evidências**")
        qs = ["O aluno não avança?", "Se perde?", "Precisa 1:1?"]
        for q in qs: st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False), key=f"v53_ev_{q}")

    with t[3]: # REDE
        st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais", ["Psicólogo", "Fono"], default=st.session_state.dados['rede_apoio'], key="v53_rd")
        st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações", st.session_state.dados['orientacoes_especialistas'], key="v53_or")

    with t[4]: # MAPA
        st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco", st.session_state.dados['hiperfoco'], key="v53_hf")
        st.session_state.dados['potencias'] = st.multiselect("Potências", ["Memória", "Artes"], default=st.session_state.dados['potencias'], key="v53_pt")
        st.divider()
        cats = {"Cognitivo": ["Atenção"], "Social": ["Interação"]}
        for c, i in cats.items():
            sel = st.multiselect(c, i, default=st.session_state.dados['barreiras_selecionadas'].get(c, []), key=f"v53_br_{c}")
            st.session_state.dados['barreiras_selecionadas'][c] = sel
            for x in sel:
                st.session_state.dados['niveis_suporte'][f"{c}_{x}"] = st.select_slider(x, ["Autônomo", "Monitorado", "Substancial"], key=f"v53_sl_{x}")

    with t[5]: # PLANO
        c1, c2 = st.columns(2)
        st.session_state.dados['estrategias_acesso'] = c1.multiselect("Acesso", ["Tempo Estendido"], default=st.session_state.dados['estrategias_acesso'], key="v53_ac")
        st.session_state.dados['outros_acesso'] = c1.text_input("Outros Acesso", st.session_state.dados.get('outros_acesso',''), key="v53_ot_ac")
        st.session_state.dados['estrategias_ensino'] = c2.multiselect("Ensino", ["Pistas Visuais"], default=st.session_state.dados['estrategias_ensino'], key="v53_en")
        st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Avaliação", ["Prova Adaptada"], default=st.session_state.dados['estrategias_avaliacao'], key="v53_av")

    with t[6]: # MONITORAMENTO
        c1, c2 = st.columns(2)
        st.session_state.dados['monitoramento_data'] = c1.date_input("Próxima Revisão", value=st.session_state.dados.get('monitoramento_data', None), key="v53_rev_dt")
        st.session_state.dados['monitoramento_indicadores'] = c2.text_area("Indicadores Sucesso", st.session_state.dados.get('monitoramento_indicadores',''), key="v53_ind")
        st.session_state.dados['monitoramento_proximos'] = st.text_area("Próximos Passos", st.session_state.dados.get('monitoramento_proximos',''), key="v53_prox")

    with t[7]: # IA
        if st.button("Gerar PEI 5.3", type="primary", key="v53_go"):
            res, err = consultar_gpt_v53(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: st.session_state.dados['ia_sugestao'] = res
        if st.session_state.dados['ia_sugestao']: st.text_area("Editor", st.session_state.dados['ia_sugestao'], height=500, key="v53_ed")

    with t[8]: # DOC
        if st.session_state.dados['ia_sugestao']:
            with st.expander("Preview"): st.markdown(st.session_state.dados['ia_sugestao'])
            pdf = gerar_pdf_final(st.session_state.dados, len(st.session_state.pdf_text)>0)
            st.download_button("Baixar PDF Pro", pdf, "pei_v53.pdf", "application/pdf", key="v53_dl")

# ==============================================================================
# EXECUÇÃO PRINCIPAL
# ==============================================================================
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 80px;">' if logo_path else ""
st.markdown(f"""<div class="header-clean">{img_html}<div><p style="margin:0; color:#004E92; font-size:1.3rem; font-weight:800;">Ecossistema de Inteligência Pedagógica e Inclusiva</p></div></div>""", unsafe_allow_html=True)

data_atual = date.today().strftime("%d/%m/%Y")
with st.sidebar:
    versao = st.radio("Escolha a Versão:", ["5.2 (Estável)", "5.3 (Beta - Inovação)"], index=0)
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0; margin-top:20px;'>Atualizado: {data_atual}<br>Dev: Rodrigo Amorim Queiroz</div>", unsafe_allow_html=True)

if versao == "5.2 (Estável)":
    render_v5_2(api_key)
else:
    render_v5_3(api_key)
