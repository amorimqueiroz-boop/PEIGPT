import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from docx.shared import Pt, RGBColor
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import base64
import json
import os
import re
import glob

# ==============================================================================
# 1. CONFIGURAÇÃO E IDENTIDADE VISUAL
# ==============================================================================
def get_favicon():
    return "📘"

st.set_page_config(
    page_title="PEI 360º | Architect Edition",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

def aplicar_estilo_visual():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        :root {
            --primary: #004E92;
            --secondary: #FF6B6B;
            --success: #38A169;
            --bg-light: #F7FAFC;
        }

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1A202C; }
        
        /* HEADER */
        .header-unified {
            background: white; padding: 2rem; border-radius: 16px;
            border: 1px solid #E2E8F0; box-shadow: 0 4px 20px rgba(0,0,0,0.03);
            display: flex; align-items: center; gap: 20px; margin-bottom: 30px;
        }
        
        /* CARDS CUSTOMIZADOS */
        div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
            border-radius: 12px;
        }

        /* DESIGN DA ABA 4 - SEPARAÇÃO VISUAL */
        .potential-card {
            border-left: 5px solid var(--success); background-color: #F0FFF4; padding: 20px; border-radius: 8px;
        }
        .barrier-card {
            border-left: 5px solid var(--secondary); background-color: #FFF5F5; padding: 20px; border-radius: 8px;
        }

        /* TAB SELECTOR */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
        .stTabs [data-baseweb="tab"] {
            height: 45px; border-radius: 8px; background-color: white; 
            border: 1px solid #E2E8F0; color: #718096; font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--primary) !important; color: white !important;
        }

        /* BOTÕES E INPUTS */
        .stButton button {
            border-radius: 8px !important; font-weight: 700 !important; 
            text-transform: uppercase; height: 48px !important;
            transition: all 0.3s ease;
        }
        .stTextInput input, .stSelectbox div, .stTextArea textarea {
            border-radius: 8px !important; border-color: #CBD5E0 !important;
        }
    </style>
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_visual()

# ==============================================================================
# 2. DADOS E LISTAS
# ==============================================================================
LISTA_SERIES = [
    "Educação Infantil", "1º Ano (Fund. I)", "2º Ano (Fund. I)", "3º Ano (Fund. I)", 
    "4º Ano (Fund. I)", "5º Ano (Fund. I)", "6º Ano (Fund. II)", "7º Ano (Fund. II)", 
    "8º Ano (Fund. II)", "9º Ano (Fund. II)", "1ª Série (Ensino Médio)", 
    "2ª Série (Ensino Médio)", "3ª Série (Ensino Médio)"
]

LISTAS_BARREIRAS = {
    "Cognitivo": ["Atenção Sustentada", "Memória de Trabalho", "Flexibilidade Cognitiva", "Velocidade de Processamento", "Raciocínio Abstrato"],
    "Comunicacional": ["Linguagem Expressiva", "Linguagem Receptiva", "Pragmática Social", "Interpretação de Texto", "Vocabulário"],
    "Socioemocional": ["Regulação Emocional", "Tolerância à Frustração", "Interação Social", "Rigidez Mental", "Autoestima"],
    "Sensorial/Motor": ["Coordenação Fina", "Hipersensibilidade Auditiva", "Hipersensibilidade Visual", "Busca Sensorial", "Planejamento Motor"],
    "Acadêmico": ["Decodificação Leitora", "Produção Textual", "Cálculo Matemático", "Resolução de Problemas", "Organização de Estudos"]
}

LISTA_POTENCIAS = ["Memória Visual", "Memória Auditiva", "Raciocínio Lógico", "Criatividade", "Habilidades Artísticas", "Musicalidade", "Tecnologia", "Hiperfoco", "Liderança", "Esportes", "Persistência", "Curiosidade Investigativa"]

# ==============================================================================
# 3. GERENCIAMENTO DE ESTADO (STATE MANAGEMENT)
# ==============================================================================
default_state = {
    'nome': '', 'nasc': date(2015, 1, 1), 'serie': None, 'turma': '', 'diagnostico': '', 
    'lista_medicamentos': [], 'historico': '', 'familia': '', 
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
# 4. INTELIGÊNCIA ARTIFICIAL (O "CÉREBRO" REVISADO)
# ==============================================================================
def consultar_gpt_pedagogico(api_key, dados, contexto_pdf=""):
    if not api_key: return None, "⚠️ Configure a Chave API OpenAI."
    try:
        client = OpenAI(api_key=api_key)
        
        # Construção rica do contexto
        evidencias = ", ".join([k for k, v in dados['checklist_evidencias'].items() if v])
        barreiras_detalhadas = ""
        for cat, itens in dados['barreiras_selecionadas'].items():
            if itens:
                barreiras_detalhadas += f"\n- {cat}: " + ", ".join([f"{i} (Suporte: {dados['niveis_suporte'].get(f'{cat}_{i}', 'Monitorado')})" for i in itens])

        system_prompt = """
        Você é um Especialista Sênior em Educação Inclusiva e Currículo (BNCC).
        Sua missão é criar um Plano de Ensino Individualizado (PEI) de alta precisão.
        
        DIRETRIZES PEDAGÓGICAS:
        1. RECOMPOSIÇÃO: Se o aluno tem barreiras acadêmicas severas, sugira habilidades da BNCC de anos anteriores (Recomposição de Aprendizagem) conectadas ao tema da série atual.
        2. HIPERFOCO: Use OBRIGATORIAMENTE o interesse do aluno (Hiperfoco) como alavanca metodológica nas estratégias de ensino.
        3. TOM: Técnico, acolhedor e focado em potencialidades, não apenas déficits.
        
        FORMATO DA RESPOSTA (Markdown):
        1. SÍNTESE DO PERFIL (Breve análise biopsicossocial)
        2. HABILIDADES ALVO (BNCC - Código e Descrição Adaptada)
        3. ESTRATÉGIAS DE ENSINO MEDIADAS PELO HIPERFOCO (Como usar o interesse dele para ensinar?)
        4. ADAPTAÇÕES DE ACESSO E AVALIAÇÃO (Práticas)
        """
        
        user_prompt = f"""
        ALUNO: {dados['nome']} | SÉRIE: {dados['serie']}
        DIAGNÓSTICO: {dados['diagnostico']}
        HIPERFOCO/INTERESSES: {dados['hiperfoco']}
        
        POTENCIALIDADES: {', '.join(dados['potencias'])}
        
        BARREIRAS E NÍVEL DE SUPORTE:
        {barreiras_detalhadas}
        
        EVIDÊNCIAS OBSERVADAS:
        {evidencias}
        
        CONTEXTO LAUDO (Trecho):
        {contexto_pdf[:3000]}
        """
        
        res = client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7
        )
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 5. MOTOR PDF PROFISSIONAL (VISUAL EXECUTIVO)
# ==============================================================================
class PDF_Premium(FPDF):
    def header(self):
        # Faixa Lateral
        self.set_fill_color(0, 78, 146) # Azul Brand
        self.rect(0, 0, 10, 297, 'F')
        
        # Logo e Título
        self.set_xy(20, 15)
        self.set_font('Arial', 'B', 18)
        self.set_text_color(0, 78, 146)
        self.cell(0, 10, 'PLANO DE ENSINO INDIVIDUALIZADO', 0, 1)
        
        self.set_xy(20, 23)
        self.set_font('Arial', '', 10)
        self.set_text_color(100)
        self.cell(0, 5, 'Documento Oficial de Planejamento Pedagógico | Confidencial', 0, 1)
        self.line(20, 32, 200, 32)
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Gerado via PEI 360 - Página {self.page_no()}', 0, 0, 'R')

    def chapter_title(self, label):
        self.ln(5)
        self.set_fill_color(240, 244, 248) # Cinza muito leve
        self.set_text_color(0, 78, 146)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, f"  {label}", 0, 1, 'L', fill=True)
        self.ln(4)

    def card_body(self, titulo, conteudo):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(50)
        self.cell(0, 6, titulo, 0, 1)
        self.set_font('Arial', '', 10)
        self.set_text_color(0)
        self.multi_cell(0, 6, conteudo)
        self.ln(3)

def gerar_pdf_premium(dados):
    pdf = PDF_Premium()
    pdf.add_page()
    
    # 1. Identificação
    pdf.chapter_title("1. IDENTIFICAÇÃO DO ESTUDANTE")
    pdf.card_body("Nome Completo:", dados['nome'])
    pdf.card_body("Série/Turma:", f"{dados['serie']} - {dados['turma']}")
    pdf.card_body("Diagnóstico:", dados['diagnostico'])
    
    # 2. Perfil de Aprendizagem (Tabela Visual)
    pdf.chapter_title("2. PERFIL DE APRENDIZAGEM")
    
    # Potencialidades
    pdf.set_fill_color(220, 252, 231) # Verde claro
    pdf.set_text_color(22, 101, 52)   # Verde escuro
    pdf.set_font('Arial', 'B', 10)
    potencias_str = ", ".join(dados['potencias']) if dados['potencias'] else "Em investigação"
    pdf.multi_cell(0, 8, f" POTENCIALIDADES & HIPERFOCO: {dados['hiperfoco']} | {potencias_str}", 0, 'L', True)
    pdf.ln(2)
    
    # Barreiras
    if any(dados['barreiras_selecionadas'].values()):
        pdf.set_text_color(0)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "MAPEAMENTO DE BARREIRAS E SUPORTE:", 0, 1)
        pdf.set_font('Arial', '', 9)
        
        for cat, itens in dados['barreiras_selecionadas'].items():
            if itens:
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(40, 6, f"  {cat}:", 0, 0)
                pdf.set_font('Arial', '', 9)
                
                detalhes = []
                for item in itens:
                    nivel = dados['niveis_suporte'].get(f"{cat}_{item}", "-")
                    detalhes.append(f"{item} ({nivel})")
                
                pdf.multi_cell(0, 6, ", ".join(detalhes))
    
    # 3. Plano e Sugestão IA
    if dados['ia_sugestao']:
        pdf.add_page()
        pdf.chapter_title("3. PLANO DE AÇÃO E ESTRATÉGIAS (IA)")
        texto_limpo = re.sub(r'[^\x00-\xff]', '', dados['ia_sugestao'])
        texto_limpo = texto_limpo.replace('**', '').replace('###', '')
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, texto_limpo)
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

# ==============================================================================
# 6. UI PRINCIPAL
# ==============================================================================
# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3426/3426653.png", width=80) # Placeholder logo
    st.title("PEI 360º")
    st.caption("Ecossistema de Inteligência Pedagógica")
    
    api_key = st.text_input("Chave OpenAI", type="password")
    st.markdown("---")
    
    # Gestão de Arquivos (Simulação Local)
    st.markdown("### 📂 Meus Alunos")
    PASTA_BANCO = "banco_alunos"
    if not os.path.exists(PASTA_BANCO): os.makedirs(PASTA_BANCO)
    
    arquivos = glob.glob(os.path.join(PASTA_BANCO, "*.json"))
    for arq in arquivos:
        nome_arq = os.path.basename(arq).replace(".json", "").replace("_", " ").title()
        c1, c2 = st.columns([4, 1])
        c1.text(nome_arq)
        if c2.button("Abrir", key=arq):
            st.session_state.dados = json.load(open(arq))
            st.rerun()

# Header Principal
st.markdown("""
<div class="header-unified">
    <div style="font-size: 2.5rem; color: #004E92;">📘</div>
    <div>
        <h2 style="margin:0; color:#2D3748;">Planejamento Educacional Individualizado</h2>
        <p style="margin:0; color:#718096; font-size:0.9rem;">Versão Architect • Foco em Potencialidades</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Abas
tabs = st.tabs(["Início", "Aluno", "Mapeamento (Novo)", "Estratégias", "IA & Documento"])

with tabs[0]: # Início
    st.markdown("### Bem-vindo ao Novo Padrão")
    c1, c2, c3 = st.columns(3)
    c1.info("🧠 **IA Recompõe Aprendizagem:** Agora a IA busca habilidades de anos anteriores.")
    c2.success("✨ **Foco no Potencial:** Interface dedicada para Hiperfoco e Habilidades.")
    c3.warning("📄 **PDF Executivo:** Documentos prontos para a gestão escolar.")

with tabs[1]: # Aluno
    c1, c2 = st.columns([2, 1])
    st.session_state.dados['nome'] = c1.text_input("Nome do Estudante", st.session_state.dados['nome'])
    st.session_state.dados['serie'] = c2.selectbox("Série Atual", LISTA_SERIES)
    st.session_state.dados['diagnostico'] = st.text_area("Diagnóstico / Laudo", st.session_state.dados['diagnostico'], height=100)
    
    with st.expander("Carregar PDF do Laudo (Opcional)"):
        pdf_file = st.file_uploader("Anexar Laudo", type="pdf")
        if pdf_file:
            reader = PdfReader(pdf_file)
            st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages[:4]])

with tabs[2]: # MAPEAMENTO REVOLUCIONÁRIO
    st.markdown("### 🧭 Bússola de Aprendizagem")
    st.write("Identifique as forças motoras e as barreiras limitantes.")
    
    col_pot, col_bar = st.columns(2)
    
    # COLUNA DA ESQUERDA: POTÊNCIA (VERDE/AZUL)
    with col_pot:
        st.markdown('<div class="potential-card">', unsafe_allow_html=True)
        st.markdown("#### 🚀 Potencialidades & Hiperfoco")
        st.caption("O que engaja este aluno? O que ele faz bem?")
        
        st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco (Interesse Intenso)", st.session_state.dados['hiperfoco'], placeholder="Ex: Dinossauros, Minecraft, Desenho...")
        
        # Filtra lista para não bugar o multiselect
        defaults_p = [x for x in st.session_state.dados['potencias'] if x in LISTA_POTENCIAS]
        st.session_state.dados['potencias'] = st.multiselect("Pontos Fortes", LISTA_POTENCIAS, default=defaults_p)
        st.markdown('</div>', unsafe_allow_html=True)

    # COLUNA DA DIREITA: BARREIRAS (LARANJA/VERMELHO)
    with col_bar:
        st.markdown('<div class="barrier-card">', unsafe_allow_html=True)
        st.markdown("#### 🚧 Barreiras e Suportes")
        st.caption("Onde precisamos atuar? Qual o nível de ajuda?")
        
        categoria_barreira = st.selectbox("Selecione a Área para Mapear:", list(LISTAS_BARREIRAS.keys()))
        
        itens_possiveis = LISTAS_BARREIRAS[categoria_barreira]
        defaults_b = [x for x in st.session_state.dados['barreiras_selecionadas'][categoria_barreira] if x in itens_possiveis]
        
        selecao_atual = st.multiselect(f"Barreiras em: {categoria_barreira}", itens_possiveis, default=defaults_b)
        st.session_state.dados['barreiras_selecionadas'][categoria_barreira] = selecao_atual
        
        # UI Limpa para Sliders (Só aparece se selecionar)
        if selecao_atual:
            st.markdown("---")
            st.markdown("**Calibrar Nível de Suporte:**")
            for item in selecao_atual:
                chave = f"{categoria_barreira}_{item}"
                valor_atual = st.session_state.dados['niveis_suporte'].get(chave, "Monitorado")
                st.session_state.dados['niveis_suporte'][chave] = st.select_slider(
                    f"Suporte para '{item}'", 
                    options=["Leve", "Monitorado", "Substancial", "Intenso"],
                    value=valor_atual
                )
        st.markdown('</div>', unsafe_allow_html=True)

with tabs[3]: # Estratégias
    st.markdown("### 🛠️ Caixa de Ferramentas")
    c1, c2 = st.columns(2)
    with c1:
        st.multiselect("Estratégias de Ensino", ["Pistas Visuais", "Material Concreto", "Gamificação", "Fragmentação"], key="strat_ens")
    with c2:
        st.multiselect("Adaptação de Avaliação", ["Tempo Estendido", "Prova Oral", "Ledor", "Sala Separada"], key="strat_aval")

with tabs[4]: # IA e Documento
    st.markdown("### 🤖 Consultoria & Exportação")
    
    col_act, col_view = st.columns([1, 2])
    
    with col_act:
        st.markdown("""
        **Gerar PEI Inteligente:**
        A IA irá cruzar o **Hiperfoco** ({}) com as **Barreiras** para sugerir estratégias.
        """.format(st.session_state.dados['hiperfoco'] if st.session_state.dados['hiperfoco'] else "..."))
        
        if st.button("✨ GERAR PEI AGORA", type="primary"):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, st.session_state.pdf_text)
            if res: st.session_state.dados['ia_sugestao'] = res
            elif err: st.error(err)
            
        st.markdown("---")
        st.markdown("**Exportar:**")
        
        if st.session_state.dados['nome']:
            pdf_bytes = gerar_pdf_premium(st.session_state.dados)
            st.download_button("📥 Baixar PDF Premium", pdf_bytes, "PEI_Premium.pdf", "application/pdf")
            
            # Botão Salvar JSON
            json_str = json.dumps(st.session_state.dados, default=str)
            nome_safe = re.sub(r'[^a-zA-Z0-9]', '_', st.session_state.dados['nome'])
            
            # Salvar Local (Simulação)
            with open(os.path.join(PASTA_BANCO, f"{nome_safe}.json"), "w") as f:
                f.write(json_str)
            st.toast("Salvo no banco local!")

    with col_view:
        if st.session_state.dados['ia_sugestao']:
            st.text_area("Prévia do Conteúdo", st.session_state.dados['ia_sugestao'], height=500)
        else:
            st.info("Preencha os dados nas abas anteriores e clique em Gerar para ver a mágica.")
