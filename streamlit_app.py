import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from docx.shared import Pt
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import base64
import os
import re
import json

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================
def get_favicon():
    if os.path.exists("iconeaba.png"): return "iconeaba.png"
    return "📘"

st.set_page_config(
    page_title="PEI 360º | Stage 2",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. GERENCIAMENTO DE ESTADO (COM NOVOS CAMPOS DA ETAPA 2)
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
    # --- NOVOS CAMPOS (ETAPA 2) ---
    'outros_acesso': '', 
    'outros_ensino': '', 
    'monitoramento_data': None, 
    'monitoramento_indicadores': '', 
    'monitoramento_proximos': ''
}

if 'dados' not in st.session_state:
    st.session_state.dados = default_state
else:
    # Auto-Reparo: Garante que chaves novas existam se carregar um JSON antigo
    for key, val in default_state.items():
        if key not in st.session_state.dados:
            st.session_state.dados[key] = val

if 'pdf_text' not in st.session_state: st.session_state.pdf_text = ""

# ==============================================================================
# 3. UTILITÁRIOS
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
    texto = texto.replace('–', '-').replace('—', '-')
    texto = texto.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    texto = re.sub(r'[^\x00-\xff]', '', texto) 
    return texto

# ==============================================================================
# 4. INTELIGÊNCIA ARTIFICIAL (ATUALIZADA PARA ETAPA 2)
# ==============================================================================
def consultar_gpt_v4(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ Configure a Chave API OpenAI na barra lateral."
    
    try:
        client = OpenAI(api_key=api_key)
        contexto_seguro = contexto_pdf[:5000] if contexto_pdf else "Sem laudo anexado."
        
        evidencias_texto = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        
        meds_texto = ""
        if dados['lista_medicamentos']:
            for m in dados['lista_medicamentos']:
                meds_texto += f"- {m['nome']} ({m['posologia']}). Admin na escola: {'SIM' if m['escola'] else 'NÃO'}.\n"
        else: meds_texto = "Nenhuma medicação informada."

        mapeamento_texto = ""
        for categoria, itens in dados['barreiras_selecionadas'].items():
            if itens:
                mapeamento_texto += f"\n[{categoria}]: "
                detalhes = []
                for item in itens:
                    nivel = dados['niveis_suporte'].get(f"{categoria}_{item}", "Monitorado")
                    detalhes.append(f"{item} (Suporte {nivel})")
                mapeamento_texto += ", ".join(detalhes)

        # --- NOVOS DADOS PARA O PROMPT ---
        extra_acesso = f" | Outros: {dados['outros_acesso']}" if dados['outros_acesso'] else ""
        extra_ensino = f" | Outros: {dados['outros_ensino']}" if dados['outros_ensino'] else ""
        
        monitoramento_txt = ""
        if dados['monitoramento_data']:
            monitoramento_txt = f"Revisão em: {dados['monitoramento_data']}. Indicadores: {dados['monitoramento_indicadores']}."

        prompt_sistema = """
        Você é um Neuropsicopedagogo Sênior.
        Sua missão é construir um PEI (Plano de Ensino Individualizado) centrado no estudante.
        
        REGRAS DE FORMATAÇÃO:
        1. NÃO COLOQUE TÍTULO NO DOCUMENTO (O PDF já tem).
        2. Comece ESTRITAMENTE pelo título do tópico "1. PERFIL BIOPSICOSSOCIAL DO ESTUDANTE".
        3. Use CAIXA ALTA apenas nos títulos numéricos (1., 2., ...).
        
        ESTRUTURA OBRIGATÓRIA (6 PONTOS):
        1. PERFIL BIOPSICOSSOCIAL DO ESTUDANTE
        2. PLANEJAMENTO CURRICULAR E BNCC
        3. DIRETRIZES PRÁTICAS PARA ADAPTAÇÃO
        4. PLANO DE INTERVENÇÃO E ESTRATÉGIAS
        5. MONITORAMENTO E METAS (Novo: Use os dados de revisão informados)
        6. PARECER FINAL E RECOMENDAÇÕES
        """

        prompt_usuario = f"""
        ESTUDANTE: {dados['nome']} | Série: {dados['serie']}
        DIAGNÓSTICO: {dados['diagnostico']}
        MEDICAÇÕES: {meds_texto}
        
        QUEM É O ESTUDANTE:
        Histórico: {dados['historico']} | Família: {dados['familia']}
        
        EVIDÊNCIAS: {evidencias_texto}
        BARREIRAS: {mapeamento_texto}
        POTENCIALIDADES: Hiperfoco: {dados['hiperfoco']} | Fortes: {', '.join(dados['potencias'])}
        
        ESTRATÉGIAS: 
        Acesso: {', '.join(dados['estrategias_acesso'])}{extra_acesso}
        Ensino: {', '.join(dados['estrategias_ensino'])}{extra_ensino}
        Avaliação: {', '.join(dados['estrategias_avaliacao'])}
        
        DADOS DE MONITORAMENTO: {monitoramento_txt}
        
        LAUDO: {contexto_seguro}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
            temperature=0.7
        )
        return response.choices[0].message.content, None
    except Exception as e: return None, f"Erro OpenAI: {str(e)}."

# ==============================================================================
# 5. PDF (ATUALIZADO PARA ETAPA 2)
# ==============================================================================
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

def gerar_pdf(dados, tem_anexo):
    pdf = PDF_V3(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
    
    # 1. Identificação
    pdf.section_title("1. IDENTIFICAÇÃO E CONTEXTO")
    pdf.set_font("Arial", size=10); pdf.set_text_color(0)
    
    med_str = "; ".join([f"{m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']]) if dados['lista_medicamentos'] else "Não informado / Não faz uso."
    diag = dados['diagnostico'] if dados['diagnostico'] else ("Vide laudo anexo" if tem_anexo else "Não informado")
    
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

    # 4. Relatório IA (Agora aceita até 6 tópicos)
    if dados['ia_sugestao']:
        pdf.ln(5)
        pdf.set_text_color(0); pdf.set_font("Arial", '', 10)
        linhas = dados['ia_sugestao'].split('\n')
        for linha in linhas:
            linha_limpa = limpar_texto_pdf(linha)
            # Detecta 1. a 6. em caixa alta
            if re.match(r'^[1-6]\.', linha_limpa.strip()) and linha_limpa.strip().isupper():
                pdf.ln(4); pdf.set_fill_color(240, 248, 255); pdf.set_text_color(0, 78, 146); pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"  {linha_limpa}", 0, 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", size=10)
            elif linha_limpa.strip().endswith(':') and len(linha_limpa) < 70:
                pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(0, 6, linha_limpa); pdf.set_font("Arial", size=10)
            else:
                pdf.multi_cell(0, 6, linha_limpa)
    
    # 5. Monitoramento (NOVA SEÇÃO IMPRESSA)
    if dados.get('monitoramento_data') or dados.get('monitoramento_indicadores'):
        pdf.section_title("CRONOGRAMA DE REVISÃO E MONITORAMENTO")
        pdf.set_font("Arial", size=10)
        data_rev = dados['monitoramento_data'].strftime("%d/%m/%Y") if dados['monitoramento_data'] else "-"
        texto_mon = f"Data Prevista para Revisão: {data_rev}\n\n"
        if dados['monitoramento_indicadores']: texto_mon += f"Indicadores de Sucesso:\n{dados['monitoramento_indicadores']}\n\n"
        if dados['monitoramento_proximos']: texto_mon += f"Próximos Passos:\n{dados['monitoramento_proximos']}"
        pdf.multi_cell(0, 6, limpar_texto_pdf(texto_mon))

    pdf.ln(25); y = pdf.get_y()
    if y > 250: pdf.add_page(); y = 40
    pdf.line(20, y, 90, y); pdf.line(120, y, 190, y)
    pdf.set_font("Arial", 'I', 8); pdf.text(35, y+5, "Coordenação / Direção"); pdf.text(135, y+5, "Família / Responsável")
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_docx(dados):
    doc = Document(); style = doc.styles['Normal']; style.font.name = 'Arial'; style.font.size = Pt(11)
    doc.add_heading('PLANO DE ENSINO INDIVIDUALIZADO', 0)
    doc.add_paragraph(f"Estudante: {dados['nome']} | Série: {dados['serie']}")
    if dados['ia_sugestao']: doc.add_heading('Parecer Técnico', level=1); doc.add_paragraph(dados['ia_sugestao'])
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0); return buffer

# ==============================================================================
# 6. LAYOUT PRINCIPAL
# ==============================================================================
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

# SIDEBAR (COM ETAPA 1 - GESTÃO)
with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ OpenAI OK")
    else: api_key = st.text_input("Chave OpenAI:", type="password")
    
    st.markdown("---")
    st.caption("📂 Gestão de Rascunhos")
    json_dados = json.dumps(st.session_state.dados, default=str)
    st.download_button("💾 Salvar Rascunho", json_dados, f"PEI_{st.session_state.dados['nome']}.json", "application/json")
    uploaded_json = st.file_uploader("Carregar Rascunho", type="json")
    if uploaded_json:
        try:
            d = json.load(uploaded_json)
            if 'nasc' in d: d['nasc'] = date.fromisoformat(d['nasc'])
            if d.get('monitoramento_data'): d['monitoramento_data'] = date.fromisoformat(d['monitoramento_data'])
            st.session_state.dados.update(d); st.success("Carregado!"); st.rerun()
        except: st.error("Erro no arquivo.")

    st.markdown("---")
    data_atual = date.today().strftime("%d/%m/%Y")
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0;'><b>PEI 360º</b><br>v5.4 - Stage 2<br>{data_atual}</div>", unsafe_allow_html=True)

# HEADER
logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 80px;">' if logo_path else ""
st.markdown(f"""<div class="header-clean">{img_html}<div><p style="margin:0; color:#004E92; font-size:1.3rem; font-weight:800;">Ecossistema de Inteligência Pedagógica e Inclusiva</p></div></div>""", unsafe_allow_html=True)

# ABAS (COM MONITORAMENTO)
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento", "Consultoria IA", "Documento"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(abas)

# TAB 0: INÍCIO
with tab0:
    st.markdown("### <i class='ri-dashboard-line'></i> Visão Geral", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-book-read-line"></i></div><h4>PEI 360º</h4><p>Sistema baseado em evidências para construção de Planos de Ensino Individualizados robustos.</p></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-scales-3-line"></i></div><h4>Conformidade Legal</h4><p>Atende ao Decreto 12.686/2025: Foco nas barreiras e no nível de suporte.</p></div>""", unsafe_allow_html=True)
    st.write("")
    c3, c4 = st.columns(2)
    with c3: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-brain-line"></i></div><h4>Neurociência</h4><p>Mapeamos Funções Executivas e Perfil Sensorial.</p></div>""", unsafe_allow_html=True)
    with c4: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-compass-3-line"></i></div><h4>BNCC</h4><p>Garantia das Aprendizagens Essenciais através da flexibilização.</p></div>""", unsafe_allow_html=True)

# TAB 1: ESTUDANTE
with tab1:
    st.markdown("### <i class='ri-user-star-line'></i> Dossiê do Estudante", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome Completo", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)))
    st.session_state.dados['serie'] = c3.selectbox("Série/Ano", ["Infantil", "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano", "6º Ano", "7º Ano", "8º Ano", "9º Ano", "Ensino Médio"])
    st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'])
    st.markdown("---")
    ch1, ch2 = st.columns(2)
    st.session_state.dados['historico'] = ch1.text_area("Histórico Escolar", st.session_state.dados['historico'])
    st.session_state.dados['familia'] = ch2.text_area("Contexto Familiar", st.session_state.dados['familia'])
    st.session_state.dados['composicao_familiar'] = st.text_input("Composição Familiar", st.session_state.dados.get('composicao_familiar', ''))
    st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico", st.session_state.dados['diagnostico'])
    
    with st.container(border=True):
        st.markdown("**Controle de Medicação**")
        c_med1, c_med2, c_med3 = st.columns([3, 2, 1])
        with c_med1: novo_med = st.text_input("Nome", key="temp_med_nome")
        with c_med2: nova_pos = st.text_input("Posologia", key="temp_med_pos")
        with c_med3: 
            st.write(""); st.write("")
            add_btn = st.button("➕ Adicionar")
        if add_btn and novo_med:
            st.session_state.dados['lista_medicamentos'].append({"nome": novo_med, "posologia": nova_pos, "escola": False}); st.rerun()
        if st.session_state.dados['lista_medicamentos']:
            for idx, med in enumerate(st.session_state.dados['lista_medicamentos']):
                c1, c2, c3 = st.columns([4, 2, 1])
                with c1: st.markdown(f"**{med['nome']}** - {med['posologia']}")
                with c2: med['escola'] = st.checkbox("Escola?", value=med['escola'], key=f"check_{idx}")
                with c3: 
                    if st.button("🗑️", key=f"del_{idx}"): st.session_state.dados['lista_medicamentos'].pop(idx); st.rerun()
    
    with st.expander("📎 Anexar Laudo (PDF)"):
        up = st.file_uploader("Arquivo PDF", type="pdf")
        if up: st.session_state.pdf_text = ler_pdf(up); st.success("PDF Anexado!")

# TAB 2: EVIDÊNCIAS
with tab2:
    st.markdown("### <i class='ri-file-search-line'></i> Coleta de Evidências", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Currículo**")
        for q in ["O aluno não avança?", "Dificuldade generalizar?", "Interpretação?"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c2:
        st.markdown("**Atenção**")
        for q in ["Se perde?", "Esquece rápido?", "Demora iniciar?"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c3:
        st.markdown("**Comportamento**")
        for q in ["Explicação 1:1?", "Frustração?", "Desorganização?"]:
            st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))

# TAB 3: REDE
with tab3:
    st.markdown("### <i class='ri-team-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais:", ["Psicólogo", "Fonoaudiólogo", "TO", "Neuropediatra", "Psicopedagogo"], placeholder="Selecione...")
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações Técnicas", st.session_state.dados['orientacoes_especialistas'])

# TAB 4: MAPA
with tab4:
    st.markdown("### <i class='ri-map-pin-user-line'></i> Mapeamento Integral", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        st.session_state.dados['hiperfoco'] = c1.text_input("Hiperfoco", placeholder="Ex: Minecraft")
        st.session_state.dados['potencias'] = c2.multiselect("Pontos Fortes", ["Memória Visual", "Lógica", "Criatividade", "Artes"], placeholder="Selecione...")
    st.divider()
    categorias = {"Cognitivo": ["Atenção", "Memória"], "Comunicacional": ["Expressão", "Compreensão"], "Socioemocional": ["Interação", "Regulação"]}
    cols = st.columns(3); idx = 0
    for cat_nome, itens in categorias.items():
        with cols[idx % 3]:
            with st.container():
                st.markdown(f"**{cat_nome}**")
                selecionados = st.multiselect(f"Barreiras:", itens, key=f"multi_{cat_nome}", placeholder="Selecione...")
                st.session_state.dados['barreiras_selecionadas'][cat_nome] = selecionados
                if selecionados:
                    for item in selecionados:
                        val = st.select_slider(f"{item}", ["Autônomo", "Monitorado", "Substancial"], value="Monitorado", key=f"sl_{cat_nome}_{item}")
                        st.session_state.dados['niveis_suporte'][f"{cat_nome}_{item}"] = val
        idx += 1

# TAB 5: PLANO DE AÇÃO (COM NOVOS CAMPOS 'OUTROS')
with tab5:
    st.markdown("### <i class='ri-tools-line'></i> Plano de Ação Estratégico", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 1. Acesso (DUA)")
            st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos:", ["Tempo Estendido", "Ledor", "Material Ampliado"], placeholder="Selecione...")
            st.session_state.dados['outros_acesso'] = st.text_input("Outros (Acesso):", st.session_state.dados['outros_acesso'])
    with c2:
        with st.container(border=True):
            st.markdown("#### 2. Ensino")
            st.session_state.dados['estrategias_ensino'] = st.multiselect("Metodologia:", ["Fragmentação", "Pistas Visuais", "Mapas Mentais"], placeholder="Selecione...")
            st.session_state.dados['outros_ensino'] = st.text_input("Outros (Ensino):", st.session_state.dados['outros_ensino'])
    with c3:
        with st.container(border=True):
            st.markdown("#### 3. Avaliação")
            st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Formato:", ["Prova Adaptada", "Consulta", "Oral"], placeholder="Selecione...")

# TAB 6: MONITORAMENTO (NOVA ABA ETAPA 2)
with tab6:
    st.markdown("### <i class='ri-loop-right-line'></i> Monitoramento", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    st.session_state.dados['monitoramento_data'] = c1.date_input("Próxima Revisão", value=st.session_state.dados.get('monitoramento_data', None))
    st.session_state.dados['monitoramento_indicadores'] = c2.text_area("Indicadores de Sucesso (O que esperamos alcançar?)", st.session_state.dados.get('monitoramento_indicadores', ''))
    st.session_state.dados['monitoramento_proximos'] = st.text_area("Próximos Passos / Ajustes Previstos", st.session_state.dados.get('monitoramento_proximos', ''))

# TAB 7: IA
with tab7:
    st.markdown("### <i class='ri-brain-line'></i> Consultoria Pedagógica", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("""<div style="background:#F0F4FF; padding:15px; border-radius:12px; border-left: 4px solid #004E92; color: #2D3748; font-size: 0.95rem;"><b>IA Atualizada:</b> Agora gera 6 seções, incluindo o Monitoramento.</div>""", unsafe_allow_html=True)
        if st.button("GERAR PLANO AGORA", type="primary"):
            if not st.session_state.dados['nome']: st.error("Preencha o Nome do aluno.")
            else:
                with st.spinner("Construindo narrativa e monitoramento..."):
                    res, err = consultar_gpt_v4(api_key, st.session_state.dados, st.session_state.pdf_text)
                    if err: st.error(err)
                    else: st.session_state.dados['ia_sugestao'] = res; st.success("Plano Gerado!")
    with c2:
        if st.session_state.dados['ia_sugestao']: st.text_area("Texto do Relatório (Editável):", st.session_state.dados['ia_sugestao'], height=600)

# TAB 8: DOCUMENTO
with tab8:
    st.markdown("### <i class='ri-file-pdf-line'></i> Exportação Oficial", unsafe_allow_html=True)
    if st.session_state.dados['ia_sugestao']:
        c1, c2 = st.columns(2)
        with c1:
            pdf = gerar_pdf(st.session_state.dados, len(st.session_state.pdf_text)>0)
            st.download_button("📥 Baixar PDF", pdf, f"PEI_{st.session_state.dados['nome']}.pdf", "application/pdf", type="primary")
        with c2:
            docx = gerar_docx(st.session_state.dados)
            st.download_button("📥 Baixar Word", docx, f"PEI_{st.session_state.dados['nome']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else: st.warning("Gere o plano na aba Consultoria IA primeiro.")

st.markdown("---")
st.markdown("<div style='text-align: center; color: #A0AEC0; font-size: 0.8rem;'>PEI 360º v5.4 | Stage 2 Complete</div>", unsafe_allow_html=True)
