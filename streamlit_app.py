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
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================
def get_favicon():
    if os.path.exists("iconeaba.png"): return "iconeaba.png"
    return "📘"

st.set_page_config(
    page_title="PEI 360º | Pro",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. SISTEMA DE AUTO-REPARO DE DADOS (CRÍTICO PARA NÃO DAR ERRO)
# ==============================================================================
# Este bloco roda ANTES de tudo para garantir que o 'session_state' esteja perfeito
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
    # Se já existir, verificamos se falta alguma chave nova e adicionamos
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
# 4. GERAÇÃO DE PDF E WORD
# ==============================================================================
class PDF_V3(FPDF):
    def header(self):
        self.set_draw_color(0, 78, 146); self.set_line_width(0.4)
        self.rect(5, 5, 200, 287)
        logo = finding_logo()
        if logo: 
            self.image(logo, 10, 10, 30) # Logo maior (30mm)
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

    # 2. Evidências (Remove interrogações)
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
            # Detecta Título Numérico EM CAIXA ALTA (1. PERFIL...) para não confundir com lista comum
            if re.match(r'^[1-6]\.', linha_limpa.strip()) and linha_limpa.strip().isupper():
                pdf.ln(4); pdf.set_fill_color(240, 248, 255); pdf.set_text_color(0, 78, 146); pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"  {linha_limpa}", 0, 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", size=10)
            elif linha_limpa.strip().endswith(':') and len(linha_limpa) < 70:
                pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(0, 6, linha_limpa); pdf.set_font("Arial", size=10)
            else:
                pdf.multi_cell(0, 6, linha_limpa)
    
    # 5. Monitoramento
    if dados.get('monitoramento_data') or dados.get('monitoramento_indicadores') or dados.get('monitoramento_proximos'):
        pdf.section_title("CRONOGRAMA DE REVISÃO E MONITORAMENTO")
        pdf.set_font("Arial", size=10)
        data_rev = dados['monitoramento_data'].strftime("%d/%m/%Y") if dados['monitoramento_data'] else "Não definida"
        rev_txt = f"Data Prevista para Revisão: {data_rev}\n\n"
        if dados['monitoramento_indicadores']: rev_txt += f"Indicadores de Sucesso:\n{dados['monitoramento_indicadores']}\n\n"
        if dados['monitoramento_proximos']: rev_txt += f"Próximos Passos:\n{dados['monitoramento_proximos']}"
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

# ==============================================================================
# 5. INTELIGÊNCIA ARTIFICIAL
# ==============================================================================
def consultar_gpt_inovacao(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ Configure a Chave API OpenAI."
    try:
        client = OpenAI(api_key=api_key)
        contexto_seguro = contexto_pdf[:5000] if contexto_pdf else "Sem laudo anexado."
        
        # Limpeza para prompt
        evidencias_texto = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        meds_texto = "\n".join([f"- {m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']]) if dados['lista_medicamentos'] else "Nenhuma."
        
        mapeamento_texto = ""
        for cat, itens in dados['barreiras_selecionadas'].items():
            if itens:
                mapeamento_texto += f"\n[{cat}]: " + ", ".join([f"{i} ({dados['niveis_suporte'].get(f'{cat}_{i}', 'Monitorado')})" for i in itens])
        
        extra_acesso = f" | Outros: {dados.get('outros_acesso','')}" if dados.get('outros_acesso') else ""
        extra_ensino = f" | Outros: {dados.get('outros_ensino','')}" if dados.get('outros_ensino') else ""
        
        estrat_txt = f"Acesso: {', '.join(dados['estrategias_acesso'])}{extra_acesso}\nEnsino: {', '.join(dados['estrategias_ensino'])}{extra_ensino}\nAvaliação: {', '.join(dados['estrategias_avaliacao'])}"

        prompt_sistema = """
        Você é um Especialista em Educação Inclusiva. GERE O RELATÓRIO TÉCNICO SEGUINDO A ESTRUTURA NUMERADA (1 A 6) ABAIXO.
        IMPORTANTE: NÃO COLOQUE TÍTULO/CABEÇALHO NO DOCUMENTO (O PDF JÁ TEM). USE TÍTULOS DE SEÇÃO NUMERADOS EM CAIXA ALTA (EX: "1. PERFIL...").
        
        1. PERFIL BIOPSICOSSOCIAL DO ESTUDANTE (Narrativa)
        2. PLANEJAMENTO CURRICULAR E BNCC (Cite Habilidades Essenciais DO ANO e Habilidades de Recomposição DE ANOS ANTERIORES)
        3. DIRETRIZES PRÁTICAS PARA ADAPTAÇÃO (Use o Hiperfoco)
        4. PLANO DE INTERVENÇÃO (Estratégias)
        5. MONITORAMENTO E METAS (Indicadores de sucesso)
        6. PARECER FINAL
        """

        prompt_usuario = f"""
        ALUNO: {dados['nome']}
        DIAGNÓSTICO: {dados['diagnostico']}
        MEDICAÇÃO: {meds_texto}
        HISTÓRICO: {dados['historico']}
        EVIDÊNCIAS: {evidencias_texto}
        BARREIRAS: {mapeamento_texto}
        POTENCIALIDADES: {dados['hiperfoco']}
        ESTRATÉGIAS: {estrat_txt}
        LAUDO: {contexto_seguro}
        """
        
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}], temperature=0.7)
        return response.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 6. INTERFACE DO USUÁRIO (UI)
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

with st.sidebar:
    logo = finding_logo()
    if logo: st.image(logo, width=120)
    if 'OPENAI_API_KEY' in st.secrets: api_key = st.secrets['OPENAI_API_KEY']; st.success("✅ OpenAI OK")
    else: api_key = st.text_input("Chave OpenAI:", type="password")
    
    st.markdown("---")
    st.caption("📂 Gestão de Rascunhos")
    json_dados = json.dumps(st.session_state.dados, default=str)
    st.download_button("💾 Salvar Rascunho (JSON)", json_dados, "pei_rascunho.json", "application/json", key="save_json")
    uploaded_json = st.file_uploader("Carregar Rascunho", type="json", key="load_json")
    if uploaded_json:
        try:
            dados_carregados = json.load(uploaded_json)
            if 'nasc' in dados_carregados and isinstance(dados_carregados['nasc'], str):
                dados_carregados['nasc'] = date.fromisoformat(dados_carregados['nasc'])
            if 'monitoramento_data' in dados_carregados and dados_carregados['monitoramento_data']:
                dados_carregados['monitoramento_data'] = date.fromisoformat(dados_carregados['monitoramento_data'])
            st.session_state.dados.update(dados_carregados)
            st.success("Carregado!"); st.rerun()
        except: st.error("Erro no arquivo.")

    data_atual = date.today().strftime("%d/%m/%Y")
    st.markdown(f"<div style='font-size:0.75rem; color:#A0AEC0; margin-top:20px;'><b>PEI 360º Beta 5.4</b><br>Atualizado: {data_atual}<br>Dev: Rodrigo A. Queiroz</div>", unsafe_allow_html=True)

logo_path = finding_logo(); b64_logo = get_base64_image(logo_path); mime = "image/png"
img_html = f'<img src="data:{mime};base64,{b64_logo}" style="height: 80px;">' if logo_path else ""
st.markdown(f"""<div class="header-clean">{img_html}<div><p style="margin:0; color:#004E92; font-size:1.3rem; font-weight:800;">Ecossistema de Inteligência Pedagógica e Inclusiva</p></div></div>""", unsafe_allow_html=True)

# Abas da Aplicação
abas = ["Início", "Estudante", "Coleta de Evidências", "Rede de Apoio", "Potencialidades & Barreiras", "Plano de Ação", "Monitoramento (Novo)", "Consultoria IA", "Documento"]
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(abas)

with tab0: # INÍCIO
    c1, c2 = st.columns(2)
    with c1: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-rocket-line"></i></div><h4>PEI 360º Pro</h4><p>Versão 5.4 - Standalone Definitiva.</p></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div class="unified-card interactive-card"><div class="icon-box"><i class="ri-save-line"></i></div><h4>Segurança de Dados</h4><p>Sistema de Auto-Reparo e Salvo Local Ativados.</p></div>""", unsafe_allow_html=True)

with tab1: # ESTUDANTE
    st.markdown("### <i class='ri-user-star-line'></i> Dossiê do Estudante", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome Completo", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015, 1, 1)), min_value=date(2000, 1, 1), max_value=date.today())
    lista_series = ["Educação Infantil", "1º Ano (Anos Iniciais)", "2º Ano (Anos Iniciais)", "3º Ano (Anos Iniciais)", "4º Ano (Anos Iniciais)", "5º Ano (Anos Iniciais)", "6º Ano (Anos Finais)", "7º Ano (Anos Finais)", "8º Ano (Anos Finais)", "9º Ano (Anos Finais)", "1ª Série (Ensino Médio)", "2ª Série (Ensino Médio)", "3ª Série (Ensino Médio)"]
    st.session_state.dados['serie'] = c3.selectbox("Série/Ano", lista_series, placeholder="Selecione...")
    st.session_state.dados['turma'] = c4.text_input("Turma", st.session_state.dados['turma'])

    st.markdown("---")
    ch1, ch2 = st.columns(2)
    st.session_state.dados['historico'] = ch1.text_area("Histórico Escolar", st.session_state.dados['historico'], height=100)
    st.session_state.dados['familia'] = ch2.text_area("Contexto Familiar", st.session_state.dados['familia'], height=100)
    st.session_state.dados['composicao_familiar'] = st.text_input("Composição Familiar", st.session_state.dados['composicao_familiar'])
    st.session_state.dados['diagnostico'] = st.text_input("Diagnóstico Clínico", st.session_state.dados['diagnostico'])
    
    with st.container(border=True):
        st.markdown("**Controle de Medicação**")
        c_med1, c_med2, c_med3 = st.columns([3, 2, 1])
        with c_med1: novo_med = st.text_input("Nome do Medicamento", key="temp_med_nome")
        with c_med2: nova_pos = st.text_input("Posologia", key="temp_med_pos")
        with c_med3: 
            st.write("")
            st.write("")
            add_btn = st.button("➕ Adicionar")
        if add_btn and novo_med:
            st.session_state.dados['lista_medicamentos'].append({"nome": novo_med, "posologia": nova_pos, "escola": False})
            st.rerun()
        if st.session_state.dados['lista_medicamentos']:
            for idx, med in enumerate(st.session_state.dados['lista_medicamentos']):
                c_list1, c_list2, c_list3 = st.columns([4, 2, 1])
                with c_list1: st.markdown(f"💊 **{med['nome']}** - {med['posologia']}")
                with c_list2: med['escola'] = st.checkbox("Na Escola?", value=med['escola'], key=f"check_med_{idx}")
                with c_list3: 
                    if st.button("🗑️", key=f"del_med_{idx}"):
                        st.session_state.dados['lista_medicamentos'].pop(idx); st.rerun()

    with st.expander("📎 Anexar Laudo (PDF)"):
        up = st.file_uploader("Arquivo PDF", type="pdf")
        if up: st.session_state.pdf_text = ler_pdf(up); st.success("PDF Anexado!")

with tab2: # EVIDÊNCIAS
    st.markdown("### <i class='ri-file-search-line'></i> Coleta de Evidências", unsafe_allow_html=True)
    questoes = {
        "Desafios no Currículo": ["O aluno não avança mesmo com atividades adaptadas?", "Dificuldade em generalizar?", "Dificuldade com interpretação?"],
        "Atenção e Processamento": ["Se perde durante a atividade?", "Esquece rapidamente o que foi ensinado?", "Demora para iniciar tarefas?"],
        "Comportamento": ["Precisa de explicação 1:1?", "Baixa tolerância à frustração?", "Dificuldade de organização?"]
    }
    c_ev1, c_ev2, c_ev3 = st.columns(3)
    with c_ev1:
        st.markdown("**Currículo**")
        for q in questoes["Desafios no Currículo"]: st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c_ev2:
        st.markdown("**Atenção**")
        for q in questoes["Atenção e Processamento"]: st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))
    with c_ev3:
        st.markdown("**Comportamento**")
        for q in questoes["Comportamento"]: st.session_state.dados['checklist_evidencias'][q] = st.checkbox(q, value=st.session_state.dados['checklist_evidencias'].get(q, False))

with tab3: # REDE
    st.markdown("### <i class='ri-team-line'></i> Rede de Apoio", unsafe_allow_html=True)
    st.session_state.dados['rede_apoio'] = st.multiselect("Profissionais:", ["Psicólogo", "Fonoaudiólogo", "TO", "Neuropediatra", "Psicopedagogo"], default=st.session_state.dados['rede_apoio'])
    st.session_state.dados['orientacoes_especialistas'] = st.text_area("Orientações Técnicas", st.session_state.dados['orientacoes_especialistas'], height=150)

with tab4: # MAPA
    st.markdown("### <i class='ri-map-pin-user-line'></i> Mapeamento Integral", unsafe_allow_html=True)
    with st.container(border=True):
        c_pot1, c_pot2 = st.columns(2)
        st.session_state.dados['hiperfoco'] = c_pot1.text_input("Hiperfoco", st.session_state.dados['hiperfoco'])
        potencias_opts = ["Memória Visual", "Raciocínio Lógico", "Criatividade", "Oralidade", "Artes", "Liderança", "Esportes", "Tecnologia"]
        st.session_state.dados['potencias'] = c_pot2.multiselect("Pontos Fortes", potencias_opts, default=st.session_state.dados['potencias'])
    st.divider()
    
    categorias = {
        "Cognitivo": ["Atenção", "Memória de Trabalho", "Controle Inibitório", "Flexibilidade Cognitiva"],
        "Comunicacional": ["Linguagem Receptiva", "Linguagem Expressiva", "Pragmática"],
        "Socioemocional": ["Regulação Emocional", "Tolerância à Frustração", "Interação Social"],
        "Sensorial/Motor": ["Coordenação Fina", "Coordenação Ampla", "Hipersensibilidade Auditiva", "Visual"],
        "Acadêmico": ["Alfabetização", "Interpretação de Texto", "Cálculo", "Grafia"]
    }
    cols = st.columns(3)
    idx = 0
    for cat_nome, itens in categorias.items():
        with cols[idx % 3]:
            with st.container():
                st.markdown(f"**{cat_nome}**")
                selecionados = st.multiselect(f"Barreiras:", itens, key=f"multi_{cat_nome}", default=st.session_state.dados['barreiras_selecionadas'].get(cat_nome, []))
                st.session_state.dados['barreiras_selecionadas'][cat_nome] = selecionados
                if selecionados:
                    for item in selecionados:
                        val_key = f"slider_{cat_nome}_{item}"
                        default_val = st.session_state.dados['niveis_suporte'].get(f"{cat_nome}_{item}", "Monitorado")
                        val = st.select_slider(item, ["Autônomo", "Monitorado", "Substancial", "Muito Substancial"], value=default_val, key=val_key)
                        st.session_state.dados['niveis_suporte'][f"{cat_nome}_{item}"] = val
        idx += 1

with tab5: # PLANO (COM OUTROS)
    st.markdown("### <i class='ri-tools-line'></i> Plano de Ação Estratégico", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 1. Acesso")
            st.session_state.dados['estrategias_acesso'] = st.multiselect("Recursos:", ["Tempo Estendido", "Apoio à Leitura e Escrita", "Material Ampliado", "Sala Silenciosa"], default=st.session_state.dados['estrategias_acesso'])
            st.session_state.dados['outros_acesso'] = st.text_input("Outros (Acesso):", st.session_state.dados['outros_acesso'])
    with c2:
        with st.container(border=True):
            st.markdown("#### 2. Ensino")
            st.session_state.dados['estrategias_ensino'] = st.multiselect("Metodologia:", ["Fragmentação", "Pistas Visuais", "Mapas Mentais", "Projetos"], default=st.session_state.dados['estrategias_ensino'])
            st.session_state.dados['outros_ensino'] = st.text_input("Outros (Ensino):", st.session_state.dados['outros_ensino'])
    with c3:
        with st.container(border=True):
            st.markdown("#### 3. Avaliação")
            st.session_state.dados['estrategias_avaliacao'] = st.multiselect("Formato:", ["Prova Adaptada", "Consulta", "Oral", "Portfólio"], default=st.session_state.dados['estrategias_avaliacao'])

with tab6: # MONITORAMENTO (NOVO)
    st.markdown("### <i class='ri-loop-right-line'></i> Monitoramento e Metas", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.dados['monitoramento_data'] = st.date_input("Próxima Revisão", value=st.session_state.dados.get('monitoramento_data', None), key="mon_data")
    with c2:
        st.session_state.dados['monitoramento_indicadores'] = st.text_area("Indicadores Sucesso", st.session_state.dados.get('monitoramento_indicadores',''))
    st.session_state.dados['monitoramento_proximos'] = st.text_area("Próximos Passos", st.session_state.dados.get('monitoramento_proximos',''))

with tab7: # IA
    st.markdown("### <i class='ri-brain-line'></i> Consultoria Pedagógica", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.info("A IA usará os dados de todas as abas, incluindo o Monitoramento.")
        if st.button("GERAR PLANO AGORA", type="primary"):
            if not st.session_state.dados['nome']: st.error("Preencha o Nome do aluno.")
            else:
                with st.spinner("Analisando dados e gerando estratégias..."):
                    res, err = consultar_gpt_inovacao(api_key, st.session_state.dados, st.session_state.pdf_text)
                    if err: st.error(err)
                    else: st.session_state.dados['ia_sugestao'] = res; st.success("Plano Gerado!")
    with c2:
        if st.session_state.dados['ia_sugestao']:
            st.text_area("Texto Editável:", st.session_state.dados['ia_sugestao'], height=600)

with tab8: # DOCUMENTO
    st.markdown("### <i class='ri-file-pdf-line'></i> Exportação", unsafe_allow_html=True)
    if st.session_state.dados['ia_sugestao']:
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("👁️ Pré-visualização"): st.markdown(st.session_state.dados['ia_sugestao'])
            pdf = gerar_pdf_final(st.session_state.dados, len(st.session_state.pdf_text)>0)
            st.download_button("📥 Baixar PDF Pro", pdf, f"PEI_{st.session_state.dados['nome']}.pdf", "application/pdf", type="primary")
        with c2:
            docx = gerar_docx_final(st.session_state.dados)
            st.download_button("📥 Baixar Word", docx, f"PEI_{st.session_state.dados['nome']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else: st.warning("Gere o plano na aba de Consultoria IA primeiro.")

st.markdown("---")
