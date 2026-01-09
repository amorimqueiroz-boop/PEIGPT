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
# 1. CONFIGURAÇÃO VISUAL "REVOLUTION" (PRETO E DOURADO)
# ==============================================================================
st.set_page_config(
    page_title="PEI REVOLUTION",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

def aplicar_estilo_revolution():
    estilo = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        /* VARIÁVEIS DE COR REVOLUTION */
        :root {
            --bg-dark: #1A202C;
            --primary-gold: #D69E2E;
            --accent-blue: #3182CE;
            --card-white: #FFFFFF;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* HEADER DIFERENCIADO (PRETO) */
        .header-revolution {
            background: linear-gradient(90deg, #1A202C 0%, #2D3748 100%);
            padding: 2rem;
            border-radius: 12px;
            border-bottom: 4px solid var(--primary-gold);
            color: white;
            margin-bottom: 25px;
            display: flex; align-items: center; justify-content: space-between;
        }
        
        .header-revolution h1 {
            color: white !important; font-weight: 800; margin: 0; font-size: 2rem;
        }
        .header-revolution span {
            background: var(--primary-gold); color: #1A202C; 
            padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 700;
        }

        /* CARDS DE MAPEAMENTO (NOVO LAYOUT) */
        .map-card {
            padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            height: 100%; transition: transform 0.2s;
        }
        .map-card:hover { transform: translateY(-3px); }
        
        .card-potencia {
            background-color: #F0FFF4; border-left: 6px solid #48BB78;
        }
        .card-barreira {
            background-color: #FFF5F5; border-left: 6px solid #F56565;
        }

        /* ABAS ESTILIZADAS */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            background-color: white; border-radius: 6px; border: 1px solid #E2E8F0;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1A202C !important; color: var(--primary-gold) !important;
            border-color: #1A202C !important;
        }
    </style>
    """
    st.markdown(estilo, unsafe_allow_html=True)

aplicar_estilo_revolution()

# ==============================================================================
# 2. ESTRUTURA DE DADOS
# ==============================================================================
LISTA_SERIES = ["Educação Infantil", "1º Ano Fund I", "2º Ano Fund I", "3º Ano Fund I", "4º Ano Fund I", "5º Ano Fund I", "6º Ano Fund II", "7º Ano Fund II", "8º Ano Fund II", "9º Ano Fund II", "1ª Série EM", "2ª Série EM", "3ª Série EM"]

LISTAS_BARREIRAS = {
    "Cognitivo": ["Atenção", "Memória", "Flexibilidade", "Velocidade Processamento"],
    "Comunicacional": ["Fala", "Compreensão", "Socialização", "Vocabulário"],
    "Socioemocional": ["Regulação", "Frustração", "Interação", "Rigidez"],
    "Sensorial": ["Auditivo", "Visual", "Tátil", "Motor Fino"],
    "Acadêmico": ["Leitura", "Escrita", "Matemática", "Organização"]
}

LISTA_POTENCIAS = ["Memória Visual", "Música", "Tecnologia", "Desenho", "Esportes", "Liderança", "Cálculo Mental", "Oralidade", "Hiperfoco"]

default_state = {
    'nome': '', 'nasc': date(2015, 1, 1), 'serie': LISTA_SERIES[0], 'turma': '', 'diagnostico': '', 
    'hiperfoco': '', 'potencias': [], 
    'barreiras_selecionadas': {k: [] for k in LISTAS_BARREIRAS},
    'niveis_suporte': {}, 
    'ia_sugestao': '', 'pdf_text': ''
}

if 'dados' not in st.session_state: st.session_state.dados = default_state

# ==============================================================================
# 3. LÓGICA DE IA (PEDAGOGIA AVANÇADA)
# ==============================================================================
def consultar_ia_revolution(api_key, dados):
    if not api_key: return "⚠️ Insira a API Key na barra lateral."
    
    # Montagem do Prompt de Alta Precisão
    barreiras_txt = ""
    for k, v in dados['barreiras_selecionadas'].items():
        if v: barreiras_txt += f"\n- {k}: {', '.join(v)}"
        
    prompt_sys = """
    Você é o Coordenador Pedagógico Sênior de uma escola de referência.
    Sua tarefa: Criar um PEI (Plano de Ensino Individualizado) estratégico.
    
    REGRA DE OURO - O HIPERFOCO:
    Você DEVE usar o Hiperfoco do aluno como ponte para ensinar as habilidades em defasagem.
    Exemplo: Se o hiperfoco é "Carros" e a dificuldade é "Matemática", sugira problemas de velocidade/distância.
    
    ESTRUTURA DA RESPOSTA:
    1. 🎯 OBJETIVOS DE APRENDIZAGEM (Conectados à BNCC)
    2. 💡 ESTRATÉGIAS DE ENSINO (Usando o Hiperfoco: {hiperfoco})
    3. 🛠️ ADAPTAÇÕES DE MATERIAIS E AVALIAÇÃO
    """.format(hiperfoco=dados['hiperfoco'])
    
    prompt_user = f"""
    Aluno: {dados['nome']} ({dados['serie']})
    Diagnóstico: {dados['diagnostico']}
    Potências: {', '.join(dados['potencias'])}
    Barreiras: {barreiras_txt}
    """
    
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": prompt_user}]
        )
        return resp.choices[0].message.content
    except Exception as e: return f"Erro na IA: {e}"

# ==============================================================================
# 4. INTERFACE
# ==============================================================================

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuração")
    api_key = st.text_input("OpenAI API Key", type="password")
    st.info("💡 Dica: Para ver as mudanças no servidor, limpe o cache do navegador ou do Streamlit.")

# Header "Black Revolution"
st.markdown("""
<div class="header-revolution">
    <div>
        <h1>PEI 360º</h1>
        <p style="opacity: 0.8; margin-top:5px">Sistema de Inteligência Inclusiva</p>
    </div>
    <span>VERSÃO REVOLUTION 2.0</span>
</div>
""", unsafe_allow_html=True)

# Abas
tab1, tab2, tab3, tab4 = st.tabs(["1. Identificação", "2. Mapeamento 360º", "3. Plano IA", "4. Documento"])

with tab1:
    col1, col2 = st.columns([2, 1])
    st.session_state.dados['nome'] = col1.text_input("Nome do Estudante", st.session_state.dados['nome'])
    st.session_state.dados['serie'] = col2.selectbox("Série", LISTA_SERIES, index=0)
    st.session_state.dados['diagnostico'] = st.text_area("Diagnóstico Clínico", st.session_state.dados['diagnostico'])

with tab2:
    st.markdown("### 🧭 Mapeamento de Forças e Desafios")
    st.caption("Observe como separamos visualmente o que impulsiona do que limita o aluno.")
    
    c_pot, c_bar = st.columns(2)
    
    # CARD POTÊNCIA (VERDE)
    with c_pot:
        st.markdown('<div class="map-card card-potencia">', unsafe_allow_html=True)
        st.markdown("### 🚀 Potencialidades & Hiperfoco")
        st.markdown("Use isso para engajar o aluno!")
        
        st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco (Paixão do aluno)", st.session_state.dados['hiperfoco'], placeholder="Ex: Dinossauros, Futebol...")
        st.session_state.dados['potencias'] = st.multiselect("Habilidades Fortes", LISTA_POTENCIAS, default=st.session_state.dados['potencias'])
        st.markdown('</div>', unsafe_allow_html=True)
        
    # CARD BARREIRA (VERMELHO)
    with c_bar:
        st.markdown('<div class="map-card card-barreira">', unsafe_allow_html=True)
        st.markdown("### 🚧 Barreiras de Acesso")
        st.markdown("Onde o aluno precisa de suporte?")
        
        cat = st.selectbox("Área de Dificuldade", list(LISTAS_BARREIRAS.keys()))
        sel = st.multiselect(f"Barreiras em {cat}", LISTAS_BARREIRAS[cat], key=f"bar_{cat}")
        st.session_state.dados['barreiras_selecionadas'][cat] = sel
        
        if sel:
            st.markdown("---")
            for item in sel:
                st.slider(f"Nível de Suporte: {item}", 1, 3, 2, key=f"sl_{item}")
        st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown("### 🤖 Consultoria Pedagógica IA")
    if st.button("GERAR ESTRATÉGIAS REVOLUTION", type="primary"):
        with st.spinner("A IA está analisando o Hiperfoco..."):
            res = consultar_ia_revolution(api_key, st.session_state.dados)
            st.session_state.dados['ia_sugestao'] = res
            
    if st.session_state.dados['ia_sugestao']:
        st.markdown(st.session_state.dados['ia_sugestao'])

with tab4:
    st.markdown("### 📄 Exportação")
    st.warning("Funcionalidade de PDF simplificada nesta versão de teste visual.")
    st.json(st.session_state.dados)
