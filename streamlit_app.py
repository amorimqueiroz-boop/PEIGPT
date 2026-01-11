import streamlit as st
from datetime import date
from io import BytesIO
from docx import Document
from openai import OpenAI
from pypdf import PdfReader
from fpdf import FPDF
import base64
import json
import os
import re
import random
import requests
import tempfile

# ==============================================================================
# 1. CONFIGURAÇÃO E ESTADO (A BASE SÓLIDA)
# ==============================================================================
def setup_page():
    st.set_page_config(
        page_title="PEI 360º - Sistema Integrado",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def init_state():
    # Inicializa TODAS as variáveis necessárias para evitar erros de "AttributeError"
    defaults = {
        'nome': '', 'nasc': date(2015, 1, 1), 'serie': None, 'turma': '', 
        'diagnostico': '', 'historico': '', 'familia': '', 'hiperfoco': '',
        'lista_medicamentos': [], 'composicao_familiar_tags': [], 
        'potencias': [], 'rede_apoio': [], 'orientacoes_especialistas': '',
        'checklist_evidencias': {}, 
        'barreiras_selecionadas': {"Cognitivo": [], "Comunicacional": [], "Socioemocional": [], "Sensorial/Motor": [], "Acadêmico": []},
        'niveis_suporte': {}, 
        'estrategias_acesso': [], 'estrategias_ensino': [], 'estrategias_avaliacao': [], 
        'ia_sugestao': '', 'outros_acesso': '', 'outros_ensino': '', 
        'monitoramento_data': date.today(), 
        'status_meta': 'Não Iniciado', 'parecer_geral': 'Manter Estratégias', 
        'proximos_passos_select': [],
        'dalle_image_url': '', # Variável crítica da imagem
        'pdf_text': '' # Variável do PDF lido
    }
    
    if 'dados' not in st.session_state:
        st.session_state.dados = defaults
    else:
        # Garante que chaves novas sejam adicionadas a sessões antigas
        for key, val in defaults.items():
            if key not in st.session_state.dados:
                st.session_state.dados[key] = val
    
    # Variáveis soltas fora do dict 'dados'
    if 'dalle_image_url' not in st.session_state: st.session_state.dalle_image_url = ""
    if 'pdf_text' not in st.session_state: st.session_state.pdf_text = ""

# Executa setup
setup_page()
init_state()

# ==============================================================================
# 2. LISTAS E CONSTANTES
# ==============================================================================
LISTA_SERIES = ["Educação Infantil", "1º Ano (Fund. I)", "2º Ano (Fund. I)", "3º Ano (Fund. I)", "4º Ano (Fund. I)", "5º Ano (Fund. I)", "6º Ano (Fund. II)", "7º Ano (Fund. II)", "8º Ano (Fund. II)", "9º Ano (Fund. II)", "1ª Série (EM)", "2ª Série (EM)", "3ª Série (EM)"]
LISTA_PROFISSIONAIS = ["Psicólogo", "Fonoaudiólogo", "Terapeuta Ocupacional", "Neuropediatra", "Psiquiatra", "Psicopedagogo", "Professor de Apoio", "AT"]
LISTA_FAMILIA = ["Mãe", "Pai", "Mãe (2ª)", "Pai (2º)", "Avó", "Avô", "Irmão(s)", "Tio(a)", "Padrasto", "Madrasta", "Tutor Legal", "Abrigo Institucional"]
PASTA_BANCO = "banco_alunos"
if not os.path.exists(PASTA_BANCO): os.makedirs(PASTA_BANCO)

# ==============================================================================
# 3. FUNÇÕES UTILITÁRIAS E IA
# ==============================================================================
def limpar_texto_pdf(texto):
    if not texto: return ""
    # Remove formatação markdown e normaliza para PDF (latin-1)
    t = texto.replace('**', '').replace('__', '').replace('#', '').replace('⚡', '').replace('🧠', '').replace('🌬️', '').replace('🕒', '').replace('📁', '').replace('🚶‍♂️', '').replace('🤝', '').replace('🎨', '')
    return t.encode('latin-1', 'ignore').decode('latin-1')

def extrair_conteudo_tags(texto_completo, tag_abertura, tag_fechamento):
    """Extrai conteúdo entre tags específicas de forma segura"""
    if not texto_completo: return ""
    try:
        padrao = re.escape(tag_abertura) + r"(.*?)" + re.escape(tag_fechamento)
        match = re.search(padrao, texto_completo, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    except:
        return ""

def consultar_gpt_pedagogico(api_key, dados, contexto_pdf="", regenerar=False):
    if not api_key: return None, "⚠️ Configure a Chave API."
    try:
        client = OpenAI(api_key=api_key)
        
        # Preparação dos dados para o prompt
        familia = ", ".join(dados['composicao_familiar_tags']) if dados['composicao_familiar_tags'] else "Não informado"
        evid = "\n".join([f"- {k.replace('?', '')}" for k, v in dados['checklist_evidencias'].items() if v])
        meds_info = "Sem medicação."
        if dados['lista_medicamentos']:
            meds_info = ", ".join([f"{m['nome']} ({m['posologia']})" for m in dados['lista_medicamentos']])

        extra_instruction = " (ATENÇÃO: Crie uma abordagem totalmente nova e criativa)." if regenerar else ""

        # PROMPT BLINDADO COM TAGS XML-LIKE
        prompt_sys = f"""
        Você é um Especialista Sênior em Inclusão Escolar.{extra_instruction}
        
        Gere dois conteúdos distintos separados por tags rígidas.
        
        <TECNICO>
        Gere o PEI TÉCNICO para o professor. Use linguagem formal e pedagógica.
        Inclua:
        - Análise das barreiras.
        - Metas SMART (Curto, Médio, Longo prazo).
        - Estratégias de Ensino (Baseado em DUA).
        - Taxonomia de Bloom (3 verbos).
        </TECNICO>

        <ALUNO>
        Gere um ROTEIRO GAMIFICADO em 1ª Pessoa EXCLUSIVAMENTE para o aluno.
        NÃO fale sobre remédios, CID, laudos ou problemas. Fale sobre SOLUÇÕES e PODERES.
        Use Markdown e Emojis. Siga ESTRITAMENTE esta estrutura de tópicos:
        
        **⚡ Meus Superpoderes:** (Como usar o Hiperfoco {dados['hiperfoco']} para aprender).
        **🛡️ Escudo de Calma:** (Estratégia para ansiedade/regulação).
        **⚔️ Missão na Sala:** (O que fazer durante a aula para focar/pedir ajuda).
        **🎒 Meu Inventário:** (Dica de organização de material).
        **🧪 Poção de Energia:** (Dica de pausa/descanso).
        **🤝 Minha Guilda:** (Quem são os aliados: {familia}, Professores).
        </ALUNO>
        """
        
        prompt_user = f"""
        Aluno: {dados['nome']} | Série: {dados['serie']} | Diag: {dados['diagnostico']}
        Hiperfoco: {dados['hiperfoco']}
        Barreiras: {json.dumps(dados['barreiras_selecionadas'], ensure_ascii=False)}
        Meds: {meds_info}
        Evidências: {evid}
        """
        
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_sys}, {"role": "user", "content": prompt_user}])
        return res.choices[0].message.content, None
    except Exception as e: return None, str(e)

def gerar_imagem_dalle(api_key, dados_aluno):
    if not api_key: return None, "Sem API Key."
    try:
        client = OpenAI(api_key=api_key)
        hf = dados_aluno['hiperfoco'] if dados_aluno['hiperfoco'] else "aprendizado"
        
        # Prompt focado em ARTE e INSPIRAÇÃO, não em texto
        prompt = f"""
        A vibrant, pixar-style concept art illustration representing the theme '{hf}'.
        Center: A magical open book or a glowing shield with symbols of {hf}.
        Background: A friendly, organized, bright classroom or study fantasy world.
        Atmosphere: Empowering, calm, focus, success.
        No text, no letters, just art.
        """
        
        response = client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1)
        return response.data[0].url, None
    except Exception as e: return None, str(e)

# ==============================================================================
# 4. GERADORES DE ARQUIVOS (PDFS)
# ==============================================================================
class PDF_Tecnico(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'PLANO DE ENSINO INDIVIDUALIZADO (TÉCNICO)', 0, 1, 'C')
        self.ln(5)

class PDF_Tabuleiro_Aluno(FPDF):
    def header(self):
        # Fundo do cabeçalho
        self.set_fill_color(255, 204, 0) # Amarelo Ouro
        self.rect(0, 0, 297, 25, 'F')
        self.set_xy(10, 8)
        self.set_font('Arial', 'B', 22)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, "MEU MAPA DE JORNADA", 0, 1, 'C')
        self.ln(20)

def criar_pdf_tecnico(dados):
    pdf = PDF_Tecnico()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # Dados básicos
    pdf.set_font("Arial", 'B', 11); pdf.cell(40, 7, "Nome:", 0, 0); pdf.set_font("Arial", '', 11); pdf.cell(0, 7, dados['nome'], 0, 1)
    pdf.set_font("Arial", 'B', 11); pdf.cell(40, 7, "Diagnóstico:", 0, 0); pdf.set_font("Arial", '', 11); pdf.cell(0, 7, limpar_texto_pdf(dados['diagnostico']), 0, 1)
    pdf.ln(5)
    
    # Conteúdo da IA (Parte Técnica)
    conteudo_tecnico = extrair_conteudo_tags(dados['ia_sugestao'], "<TECNICO>", "</TECNICO>")
    if not conteudo_tecnico: conteudo_tecnico = dados['ia_sugestao'] # Fallback
    
    pdf.multi_cell(0, 6, limpar_texto_pdf(conteudo_tecnico))
    return pdf.output(dest='S').encode('latin-1', 'replace')

def criar_pdf_tabuleiro(dados, texto_aluno, img_url):
    # Orientação Paisagem
    pdf = PDF_Tabuleiro_Aluno(orientation='L', format='A4')
    pdf.add_page()
    
    # 1. Inserir Imagem (Se existir)
    if img_url:
        try:
            response = requests.get(img_url)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(response.content)
                    tmp_path = tmp.name
                # Centraliza imagem (Largura A4 landscape ~297mm)
                # x=108 (centro aprox), y=35, w=80
                pdf.image(tmp_path, x=108, y=35, w=80)
                os.unlink(tmp_path)
        except: pass
    
    # 2. Desenhar Cards de Texto (Layout de 2 Colunas)
    pdf.set_y(40 if not img_url else 120) # Se tiver imagem, joga texto pra baixo
    pdf.set_font("Arial", '', 10)
    
    # Função auxiliar para desenhar cards
    def draw_box(x, y, title, text, color):
        pdf.set_fill_color(*color) # RGB
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(x, y, 130, 40, 'DF')
        pdf.set_xy(x+2, y+2)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(120, 6, limpar_texto_pdf(title), 0, 1)
        pdf.set_xy(x+2, y+10)
        pdf.set_font("Arial", '', 10)
        pdf.multi_cell(126, 5, limpar_texto_pdf(text))

    # Parse do texto do aluno para separar tópicos
    topicos = {
        "Poderes": r"(Poderes|Superpoder).*?:(.*?)(?=\*\*|$)",
        "Calma": r"(Calma|Escudo).*?:(.*?)(?=\*\*|$)",
        "Escola": r"(Missão|Sala).*?:(.*?)(?=\*\*|$)",
        "Organizacao": r"(Inventário|Organização).*?:(.*?)(?=\*\*|$)"
    }
    
    # Posições
    col1_x = 15
    col2_x = 152
    row1_y = pdf.get_y() + 5
    row2_y = row1_y + 45
    
    # Extrai e desenha (Corpo do Tabuleiro)
    # Tenta extrair cada bloco. Se não achar, deixa vazio.
    t_poder = re.search(topicos["Poderes"], texto_aluno, re.DOTALL)
    val_poder = t_poder.group(2).strip() if t_poder else "..."
    draw_box(col1_x, row1_y, "MEUS SUPERPODERES", val_poder, (255, 229, 180)) # Laranja Claro

    t_calma = re.search(topicos["Calma"], texto_aluno, re.DOTALL)
    val_calma = t_calma.group(2).strip() if t_calma else "..."
    draw_box(col2_x, row1_y, "ESCUDO DE CALMA", val_calma, (209, 242, 235)) # Verde Água

    t_escola = re.search(topicos["Escola"], texto_aluno, re.DOTALL)
    val_escola = t_escola.group(2).strip() if t_escola else "..."
    draw_box(col1_x, row2_y, "MISSAO NA ESCOLA", val_escola, (214, 234, 248)) # Azul Claro

    t_org = re.search(topicos["Organizacao"], texto_aluno, re.DOTALL)
    val_org = t_org.group(2).strip() if t_org else "..."
    draw_box(col2_x, row2_y, "MEU INVENTARIO", val_org, (232, 218, 239)) # Roxo Claro

    return pdf.output(dest='S').encode('latin-1', 'replace')

# ==============================================================================
# 5. UI - ESTILO VISUAL
# ==============================================================================
def aplicar_css():
    st.markdown("""
    <style>
        .stApp { font-family: 'Nunito', sans-serif; }
        .header-unified { background: white; padding: 20px; border-radius: 15px; border: 1px solid #ddd; display: flex; gap: 15px; align-items: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .game-card { background: #fff; padding: 15px; border-radius: 12px; border-left: 5px solid #FFD700; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 10px; }
        .gc-title { font-weight: bold; font-size: 1.1em; color: #333; }
        .gc-body { color: #555; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

aplicar_css()

# ==============================================================================
# 6. UI - SIDEBAR & HEADER
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80) # Placeholder logo
    st.title("PEI 360º")
    
    if 'OPENAI_API_KEY' in st.secrets:
        api_key = st.secrets['OPENAI_API_KEY']
        st.success("API Conectada")
    else:
        api_key = st.text_input("OpenAI API Key", type="password")

    st.markdown("---")
    # Botão de Salvar/Carregar simplificado
    if st.button("💾 Salvar Dados"):
        ok, msg = salvar_aluno(st.session_state.dados)
        if ok: st.success(msg)
    
    uploaded_file = st.file_uploader("📂 Carregar Aluno", type="json")
    if uploaded_file:
        d = json.load(uploaded_file)
        st.session_state.dados.update(d)
        st.success("Dados carregados!")

st.markdown("""
<div class="header-unified">
    <h1>📘 PEI 360º - Planejamento Inteligente</h1>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 7. ABAS PRINCIPAIS
# ==============================================================================
abas = ["Dados do Aluno", "Diagnóstico & Rede", "Plano de Ação", "🤖 Consultoria IA", "📄 Documento", "🗺️ Meu Mapa"]
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(abas)

with tab1: # DADOS
    c1, c2 = st.columns(2)
    st.session_state.dados['nome'] = c1.text_input("Nome do Aluno", st.session_state.dados['nome'])
    st.session_state.dados['nasc'] = c2.date_input("Nascimento", value=st.session_state.dados.get('nasc', date(2015,1,1)))
    st.session_state.dados['serie'] = st.selectbox("Série", LISTA_SERIES, index=0)
    st.session_state.dados['hiperfoco'] = st.text_input("Hiperfoco (Paixão do Aluno)", st.session_state.dados['hiperfoco'], placeholder="Ex: Minecraft, Dinossauros, Futebol")

with tab2: # DIAGNOSTICO
    st.session_state.dados['diagnostico'] = st.text_area("Diagnóstico / Características", st.session_state.dados['diagnostico'])
    st.session_state.dados['checklist_evidencias'] = {k: st.checkbox(k, value=v) for k, v in st.session_state.dados['checklist_evidencias'].items()} 
    # (Simplificado para o exemplo, adicione os checkboxes reais aqui se precisar)

with tab3: # PLANO (Exemplo simplificado)
    st.info("Preencha as barreiras e estratégias nas outras abas (código completo nos bastidores).")

with tab4: # IA GENERATIVA
    st.markdown("### Gerador de PEI e Mapa")
    
    col_gen, col_res = st.columns([1, 2])
    with col_gen:
        if st.button("✨ Gerar Estratégias", type="primary"):
            res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados)
            if res: 
                st.session_state.dados['ia_sugestao'] = res
                st.success("Gerado com sucesso!")
            else: 
                st.error(f"Erro: {err}")
        
        if st.session_state.dados['ia_sugestao']:
            if st.button("🔄 Regenerar (Nova Ideia)"):
                res, err = consultar_gpt_pedagogico(api_key, st.session_state.dados, regenerar=True)
                if res: 
                    st.session_state.dados['ia_sugestao'] = res
                    st.rerun()

    with col_res:
        if st.session_state.dados['ia_sugestao']:
            # Mostra apenas a parte técnica aqui
            tecnico = extrair_conteudo_tags(st.session_state.dados['ia_sugestao'], "<TECNICO>", "</TECNICO>")
            st.text_area("PEI Técnico (Editável)", value=tecnico, height=400)

with tab5: # DOCUMENTO (PDF TÉCNICO)
    st.markdown("### Documento Oficial")
    if st.session_state.dados['ia_sugestao']:
        pdf_bytes = criar_pdf_tecnico(st.session_state.dados)
        st.download_button("📥 Baixar PEI (PDF)", pdf_bytes, "PEI_Tecnico.pdf", "application/pdf")
    else:
        st.warning("Gere o plano na aba IA primeiro.")

with tab6: # MEU MAPA (O FINAL)
    st.markdown("### 🗺️ Mapa da Jornada do Aluno")
    st.info(f"Material visual gamificado para: **{st.session_state.dados['nome']}**")
    
    if st.session_state.dados['ia_sugestao']:
        # 1. Extrair Texto do Aluno
        texto_aluno = extrair_conteudo_tags(st.session_state.dados['ia_sugestao'], "<ALUNO>", "</ALUNO>")
        
        if texto_aluno:
            # 2. Exibir Texto Formatado (Cards)
            st.markdown("#### 📜 Roteiro de Poderes")
            
            # Divide o texto em linhas para criar "cards" visuais simples na tela
            sections = texto_aluno.split('**')
            for sec in sections:
                if len(sec) > 10:
                    st.markdown(f"""<div class="game-card">{sec}</div>""", unsafe_allow_html=True)
            
            st.divider()

            # 3. Gerador de Imagem (Inspiracional)
            st.markdown("#### 🎨 Arte do Tabuleiro")
            if st.button("✨ Criar Arte do Tema (DALL-E)"):
                url, err = gerar_imagem_dalle(api_key, st.session_state.dados)
                if url:
                    st.session_state.dalle_image_url = url
                    st.success("Arte criada!")
                else:
                    st.error(f"Erro na imagem: {err}")
            
            # Se tiver imagem, mostra
            if st.session_state.dalle_image_url:
                st.image(st.session_state.dalle_image_url, caption="Tema Visual", use_container_width=True)
            
            # 4. Gerar PDF Tabuleiro (Híbrido)
            st.divider()
            if st.button("📥 Baixar Tabuleiro (PDF + Imagem)"):
                pdf_mapa = criar_pdf_tabuleiro(st.session_state.dados, texto_aluno, st.session_state.dalle_image_url)
                st.download_button("Clique para Salvar PDF", pdf_mapa, "Mapa_Gamificado.pdf", "application/pdf")
                
        else:
            st.error("A IA não gerou a seção <ALUNO>. Tente regenerar na aba IA.")
    else:
        st.warning("Gere as estratégias primeiro na aba 'Consultoria IA'.")
        
