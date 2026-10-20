"""Find Doc School (FDS) — aplicativo de gestão documental com QR Code.

Iniciar: streamlit run app.py
"""
from __future__ import annotations

import html
import hmac
import os
from collections import Counter, defaultdict
from datetime import datetime

import pandas as pd
import streamlit as st

from qr_utils import make_label_png, make_qr_png, qr_target
from storage import Repository

st.set_page_config(
    page_title="Find Doc School | FDS",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap');
:root {
  --fds-blue:#0047bb;
  --fds-blue-dark:#0c1f52;
  --fds-red:#d62828;
  --fds-yellow:#f7c600;
  --fds-green:#0f8b5f;
  --fds-white:#ffffff;
  --fds-ink:#1d2f49;
}
html, body, [class*="css"], [data-testid="stApp"] { font-family: 'DM Sans', sans-serif; }
[data-testid="stApp"] {
  background: linear-gradient(180deg, #f7fbff 0%, #eef4ff 100%);
  color: var(--fds-ink);
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--fds-blue-dark) 0%, var(--fds-blue) 88%);
  border-right: 3px solid rgba(247,198,0,.55);
}
[data-testid="stSidebar"] * { color: #f7fcff !important; }
[data-testid="stSidebar"] [data-baseweb="input"] input { color: #1d2f49 !important; }
[data-testid="stSidebar"] [data-baseweb="input"] * { color: #1d2f49 !important; }
h1, h2, h3 {font-family:'Outfit',sans-serif;letter-spacing:-.03em;color:#143759;}
h1 { font-weight: 800; }
.fds-kicker { color:var(--fds-red); font-size: .84rem; font-weight:800; letter-spacing:.14em; }
.fds-hero {
  background: linear-gradient(110deg, var(--fds-blue-dark) 0%, var(--fds-blue) 64%, var(--fds-red) 100%);
  border-radius:22px; padding:28px 31px 24px; color:white; margin:7px 0 23px;
  box-shadow:0 14px 30px rgba(12,31,82,.18); border: 1px solid rgba(247,198,0,.25);
}
.fds-hero h1 {color:white;margin:2px 0 6px;line-height:1.15;font-size:2.15rem;}
.fds-hero p {color:#eef7ff;margin:0;max-width:720px;font-size:1rem;}
.fds-pill {display:inline-block;border-radius:22px;background:var(--fds-yellow);color:var(--fds-blue-dark);padding:6px 11px;font-size:.73rem;font-weight:800;margin-bottom:12px;letter-spacing:.06em;}
.fds-card {background:#fff; border:1px solid #dbe7f6;border-radius:16px;padding:18px 20px;margin:8px 0 13px;box-shadow:0 4px 18px rgba(20,55,89,.06);}
.fds-card h4 { color:#143759;margin:0 0 9px;font-family:Outfit,sans-serif; }
.fds-card p { color:#52627a;margin:0; }
.fds-code {font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.96rem;font-weight:800;color:var(--fds-blue);}
.fds-muted {color:#64748b;font-size:.88rem;}
.fds-dot {font-size:.79rem;background:#e8f8ef;border-radius:15px;padding:4px 9px;color:var(--fds-green);font-weight:700;white-space:nowrap;}
.fds-path {background:#eef4ff;padding:15px;border-radius:12px;color:#183956;font-weight:700;line-height:1.8;border-left:4px solid var(--fds-yellow);}
[data-testid="stMetric"] {background:white;border:1px solid #dbe7f6;border-radius:15px;padding:16px 19px;box-shadow:0 4px 16px rgba(34,68,102,.05);}
[data-testid="stMetric"] label {color:#143759 !important;}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {background:var(--fds-red);color:white;border-color:var(--fds-red);border-radius:10px;font-weight:700;}
.stButton > button[kind="secondary"] {border-radius:10px;}
[data-testid="stFileUploader"] {background:white;border-radius:10px;}
hr {border-color:#e5edf2;}
.fds-sidebar-brand {margin-top:-4px;margin-bottom:10px;}
.fds-sidebar-brand h3 {color:#fff !important;margin:0;font-size:1.1rem;line-height:1.05;}
.fds-sidebar-brand p {color:#e7f2ff !important;margin:4px 0 0;font-size:.82rem;}
</style>
""", unsafe_allow_html=True)


def settings_value(key: str, default: str = "") -> str:
    try:
        found = st.secrets.get(key)
    except Exception:
        found = None
    return str(found) if found not in (None, "") else os.environ.get(key, default)


@st.cache_resource(show_spinner="Preparando o banco de dados...")
def get_repository(url: str) -> Repository:
    return Repository(url)


DB_URL = settings_value("DATABASE_URL", "sqlite:///fds.db")
PASSWORD = settings_value("FDS_PASSWORD")
PUBLIC_APP_URL = settings_value("PUBLIC_APP_URL")
BASE_DIR = os.path.dirname(__file__)
LOGIN_SPLASH_PATH = os.path.join(BASE_DIR, "fds_login_cover.jpg")
SIDEBAR_LOGO_PATH = os.path.join(BASE_DIR, "fds_sidebar_logo.jpg")


def h(text: str) -> str:
    return html.escape(str(text), quote=True)


def banner(title: str, subtitle: str, label: str = "ORGANIZAÇÃO QUE CONECTA") -> None:
    st.markdown(f"""<div class="fds-hero"><span class="fds-pill">{h(label)}</span>
<h1>{h(title)}</h1><p>{h(subtitle)}</p></div>""", unsafe_allow_html=True)


def path_of(d: dict) -> str:
    parts = [f"Sala {d['room']}", f"Armário {d['cabinet']}"]
    if d.get("drawer"): parts.append(f"Gaveta {d['drawer']}")
    if d.get("box"): parts.append(f"Caixa {d['box']}")
    parts.append(f"Pasta {d['folder']}")
    return "  →  ".join(parts)


def as_table(docs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Código": x["code"], "Documento": x["title"], "Categoria": x["doc_type"],
        "Sala": x["room"], "Armário": x["cabinet"], "Pasta": x["folder"], "Situação": x["status"],
    } for x in docs])


def movement_table(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Quando": x["occurred_at"].replace("T", " ")[:19],
        "Documento": x["code"], "Ação": x["action"], "Responsável": x["actor"],
        "Destino": x["destination"], "Observações": x["notes"],
    } for x in records])


def file_tuple(file):
    if not file:
        return None
    content = file.getvalue()
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("O arquivo precisa ter no máximo 5 MB.")
    filename = os.path.basename(file.name).replace("\\", "_")[:180]
    return filename, (file.type or "application/octet-stream"), content


def show_qr(doc: dict, base_url: str, label_prefix: str = "") -> None:
    code = doc["code"]
    try:
        payload, is_link = qr_target(code, base_url)
        qr_image = make_qr_png(code, base_url)
        label = make_label_png(code, doc["title"], path_of(doc), base_url)
    except ValueError as exc:
        st.error(str(exc))
        return
    col1, col2 = st.columns([1, 2], vertical_alignment="center")
    with col1:
        st.image(qr_image, caption=code, width=245)
    with col2:
        st.markdown(f"**QR Code do documento {h(code)}**")
        st.caption("Este QR não contém nome de estudantes nem conteúdo do arquivo: apenas um código ou link de consulta.")
        if is_link:
            st.code(payload, language="text")
            st.success("Ao escanear, o QR abre a ficha no site publicado. O acesso continua protegido quando há senha.")
        else:
            st.info("Para o QR abrir uma ficha online, configure a URL pública do site na barra lateral. Sem ela, o QR apenas identifica o código.")
        st.download_button("⬇️ Baixar QR Code (PNG)", qr_image,
                           file_name=f"QR_{code}.png", mime="image/png", key=f"qr_{label_prefix}{code}")
        st.download_button("🖨️ Baixar etiqueta para imprimir (PNG)", label,
                           file_name=f"Etiqueta_{code}.png", mime="image/png", key=f"label_{label_prefix}{code}")


def field_form(prefix: str, defaults: dict | None = None) -> dict:
    d = defaults or {}
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Nome do documento *", value=d.get("title", ""), key=prefix + "title", placeholder="Ex.: Histórico escolar (fictício)")
        doc_type = st.text_input("Categoria *", value=d.get("doc_type", ""), key=prefix + "type", placeholder="Ex.: Matrícula, contrato, declaração")
        room = st.text_input("Sala *", value=d.get("room", ""), key=prefix + "room", placeholder="Ex.: 2")
        cabinet = st.text_input("Armário *", value=d.get("cabinet", ""), key=prefix + "cabinet", placeholder="Ex.: 5")
        drawer = st.text_input("Gaveta", value=d.get("drawer", ""), key=prefix + "drawer", placeholder="Ex.: 3")
    with col2:
        folder = st.text_input("Pasta *", value=d.get("folder", ""), key=prefix + "folder", placeholder="Ex.: 18")
        box = st.text_input("Caixa (opcional)", value=d.get("box", ""), key=prefix + "box", placeholder="Ex.: 1")
        creator = st.text_input("Responsável pelo cadastro *", value=d.get("creator", ""), key=prefix + "creator", placeholder="Ex.: Equipe FDS")
        desc = st.text_area("Observações / descrição", value=d.get("description", ""), key=prefix + "description", height=130, placeholder="Informações adicionais sobre o arquivo")
    return {
        "title": title, "doc_type": doc_type, "room": room, "cabinet": cabinet,
        "drawer": drawer, "folder": folder, "box": box, "creator": creator, "description": desc,
    }


def detail_page(repo: Repository, code: str, base_url: str) -> None:
    doc = repo.get_document(code)
    if not doc:
        st.warning(f"Não encontramos nenhum documento com o código {code}.")
        return
    status_color = "#0c7971" if doc["status"] == "Disponível" else "#bc6320"
    st.markdown(f"""<div class="fds-card"><div class="fds-kicker">{h(doc['code'])}</div>
<h2 style="margin:8px 0">{h(doc['title'])}</h2><p>{h(doc['doc_type'])} ·
<span style="font-weight:800;color:{status_color}">{h(doc['status'])}</span></p></div>""", unsafe_allow_html=True)
    st.markdown("#### 📍 Localização exata")
    st.markdown(f"<div class='fds-path'>{h(path_of(doc))}</div>", unsafe_allow_html=True)
    a, b = st.columns(2)
    a.write(f"**Cadastrado por:** {doc['creator']}")
    b.write(f"**Criado em:** {doc['created_at'].replace('T', ' ')[:19]}")
    if doc["description"]:
        st.write(f"**Descrição:** {doc['description']}")
    if doc["status"] == "Emprestado":
        st.warning(f"Em posse de: {doc['holder']} · Destino: {doc['destination']}")
    upload = repo.get_attachment(doc["id"])
    if upload:
        st.download_button(f"📎 Abrir cópia digital: {upload['filename']}", upload["content"],
                           file_name=upload["filename"], mime=upload["content_type"], key=f"file_{code}")
    tab_qr, tab_history, tab_edit = st.tabs(["📱 QR Code e etiqueta", "📜 Histórico", "✏️ Editar / excluir"])
    with tab_qr:
        show_qr(doc, base_url, "detail_")
    with tab_history:
        records = repo.list_movements(doc["id"])
        if records:
            st.dataframe(movement_table(records), use_container_width=True, hide_index=True)
        else:
            st.info("Ainda não há retiradas ou devoluções registradas.")
    with tab_edit:
        st.caption("A edição mantém o código e o QR Code do documento.")
        with st.form(f"edit_{code}"):
            data = field_form(f"edit_{code}_", doc)
            replacement = st.file_uploader("Substituir/adicionar cópia digital (até 5 MB)",
                                           type=["pdf", "png", "jpg", "jpeg", "docx", "txt"],
                                           key=f"edit_upload_{code}")
            saved = st.form_submit_button("Salvar alterações", type="primary")
        if saved:
            try:
                uploaded = file_tuple(replacement)
                repo.update_document(code, data)
                if uploaded:
                    repo.set_attachment(code, uploaded)
                st.success("Alterações salvas!")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        with st.expander("Excluir documento permanentemente"):
            st.error("Excluir também apaga o histórico e a cópia digital. A operação não pode ser desfeita sem backup.")
            confirm = st.checkbox("Confirmo que desejo excluir este documento", key=f"confirm_{code}")
            if st.button("Excluir definitivamente", disabled=not confirm, key=f"delete_{code}"):
                repo.delete_document(code)
                if st.query_params.get("doc"):
                    del st.query_params["doc"]
                st.success("Documento excluído.")
                st.rerun()


def dashboard(repo: Repository) -> None:
    banner("Encontre. Organize. Resolva.", "Todos os seus documentos em um só lugar — com localização por QR Code, mapa do arquivo e histórico de movimentações.")
    docs = repo.list_documents()
    n_out = sum(d["status"] == "Emprestado" for d in docs)
    sala_count = len({d["room"] for d in docs})
    one, two, three, four = st.columns(4)
    one.metric("📁 Documentos", len(docs))
    two.metric("✅ Disponíveis", len(docs) - n_out)
    three.metric("🔄 Emprestados", n_out)
    four.metric("🏫 Salas organizadas", sala_count)
    st.markdown("### Como funciona")
    items = [
        ("01 · CADASTRAR", "Registre o documento e sua localização física."),
        ("02 · GERAR O QR", "Imprima a etiqueta e fixe na pasta."),
        ("03 · ENCONTRAR", "Pesquise o código ou abra o link com a câmera."),
        ("04 · CONTROLAR", "Registre retiradas, devoluções e responsáveis."),
    ]
    cols = st.columns(4)
    for col, (name, desc) in zip(cols, items):
        with col:
            st.markdown(f"<div class='fds-card' style='min-height:155px'><h4>{h(name)}</h4><p>{h(desc)}</p></div>", unsafe_allow_html=True)
    if not docs:
        st.info("O sistema está vazio. Cadastre o primeiro documento ou carregue exemplos fictícios para testar.")
        if st.button("✨ Carregar 6 documentos fictícios para demonstração"):
            for sample in SAMPLE_DOCS:
                repo.create_document(sample)
            st.rerun()
        return
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown("### Últimos documentos")
        for doc in docs[:5]:
            st.markdown(f"<div class='fds-card'><span class='fds-code'>{h(doc['code'])}</span> &nbsp;"
                        f"<strong>{h(doc['title'])}</strong><br><span class='fds-muted'>{h(path_of(doc))}</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("### Documentos por categoria")
        counts = Counter(x["doc_type"] for x in docs)
        chart = pd.DataFrame({"Categoria": list(counts), "Quantidade": list(counts.values())})
        st.bar_chart(chart.set_index("Categoria"), color="#0e8791", height=280)
        st.caption("Acompanhe o crescimento do acervo e os tipos de arquivos mais cadastrados.")


def register_page(repo: Repository, base_url: str) -> None:
    banner("Cadastrar documento", "Informe a localização exata de cada arquivo. O sistema gera um código único e uma etiqueta de QR Code automaticamente.", "NOVO REGISTRO")
    with st.form("new_document_form", clear_on_submit=True):
        data = field_form("new_")
        upload = st.file_uploader("Anexar cópia digital (opcional, máximo 5 MB)",
                                  type=["pdf", "png", "jpg", "jpeg", "docx", "txt"], key="create_file")
        st.caption("* Campos obrigatórios. Para a apresentação, utilize dados e documentos fictícios.")
        submitted = st.form_submit_button("💾 Salvar e gerar QR Code", type="primary", use_container_width=True)
    if submitted:
        try:
            code = repo.create_document(data, file_tuple(upload))
            st.session_state["newly_created"] = code
            st.success(f"✅ Documento {code} cadastrado com sucesso!")
        except ValueError as exc:
            st.error(str(exc))
    code = st.session_state.get("newly_created")
    if code:
        doc = repo.get_document(code)
        if doc:
            st.markdown("### Seu novo QR Code")
            show_qr(doc, base_url, "new_")


def search_page(repo: Repository, base_url: str) -> None:
    banner("Buscar documentos", "Encontre arquivos pelo código, nome, categoria, sala, armário ou pasta.", "BUSCA INTELIGENTE")
    q = st.text_input("🔎 Pesquisar no acervo", placeholder="Ex.: FDS-00001, matrícula, sala 2...")
    results = repo.list_documents(q)
    if not results:
        st.info("Nenhum documento encontrado. Confira os termos da pesquisa.")
        return
    st.caption(f"{len(results)} documento(s) encontrado(s)")
    st.dataframe(as_table(results), hide_index=True, use_container_width=True)
    options = {f"{d['code']}  ·  {d['title']}": d["code"] for d in results}
    chosen = st.selectbox("Selecione um documento para abrir a ficha", options=list(options), index=0)
    code = options[chosen]
    st.divider()
    detail_page(repo, code, base_url)


def map_page(repo: Repository) -> None:
    banner("Mapa virtual dos arquivos", "Acompanhe a organização física do acervo, da sala até a pasta que guarda o documento.", "LOCALIZAÇÃO EM ETAPAS")
    docs = repo.list_documents()
    if not docs:
        st.info("Cadastre documentos para construir o mapa automaticamente.")
        return
    rooms = defaultdict(lambda: defaultdict(list))
    for d in docs:
        rooms[d["room"]][d["cabinet"]].append(d)
    st.metric("Localizações cadastradas", len(docs))
    st.markdown("#### 🏫 Arquivo central")
    for room in sorted(rooms, key=str.casefold):
        with st.expander(f"🚪 Sala {room} · {sum(len(items) for items in rooms[room].values())} documento(s)", expanded=True):
            for cabinet in sorted(rooms[room], key=str.casefold):
                st.markdown(f"**🗄️ Armário {cabinet}**")
                for d in sorted(rooms[room][cabinet], key=lambda row: (row["folder"], row["title"])):
                    st.markdown(f"<div class='fds-card'><span class='fds-code'>{h(d['code'])}</span> — <b>{h(d['title'])}</b>"
                                f"<br><span class='fds-muted'>{h(path_of(d))}</span>"
                                f"<br><span class='fds-dot'>{h(d['status'])}</span></div>", unsafe_allow_html=True)
    st.caption("Exemplo da proposta: Arquivo Central → Sala 2 → Armário 5 → Gaveta 3 → Pasta 18 → FDS-00001.")


def moves_page(repo: Repository) -> None:
    banner("Controle de movimentações", "Saiba quem retirou cada documento, para onde ele foi e quando voltou.", "RASTREABILIDADE")
    docs = repo.list_documents()
    if not docs:
        st.info("Cadastre um documento antes de registrar movimentações.")
        return
    options = {f"{d['code']} · {d['title']} ({d['status']})": d["code"] for d in docs}
    chosen = st.selectbox("Documento", options=list(options))
    code = options[chosen]
    doc = repo.get_document(code)
    st.markdown(f"**Situação atual:** {doc['status']}")
    if doc["status"] == "Emprestado":
        st.warning(f"Está com {doc['holder']}, no setor/local: {doc['destination']}")
    with st.form("movement_form", clear_on_submit=True):
        action = "Retirada" if doc["status"] == "Disponível" else "Devolução"
        st.write(f"**Ação disponível: {action}**")
        actor = st.text_input("Nome de quem está realizando a ação *")
        destination = st.text_input("Setor / destino *" if action == "Retirada" else "Local de devolução (opcional)",
                                    value="" if action == "Retirada" else f"Sala {doc['room']}, Armário {doc['cabinet']}")
        notes = st.text_area("Observações (opcional)", height=90)
        submitted = st.form_submit_button(f"Registrar {action.lower()}", type="primary")
    if submitted:
        try:
            repo.move_document(code, action, actor, destination, notes)
            st.success(f"{action} registrada com sucesso!")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.markdown("### Histórico completo de movimentações")
    entries = repo.list_movements()
    if entries:
        st.dataframe(movement_table(entries), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma movimentação foi registrada ainda.")


def labels_page(repo: Repository, base_url: str) -> None:
    banner("Etiquetas e QR Codes", "Gere códigos para identificar as pastas e etiquetas para imprimir.", "PRONTO PARA IMPRIMIR")
    docs = repo.list_documents()
    if not docs:
        st.info("Cadastre o primeiro documento para gerar etiquetas.")
        return
    options = {f"{d['code']} · {d['title']}": d["code"] for d in docs}
    selected = st.selectbox("Escolha o documento", list(options))
    code = options[selected]
    show_qr(repo.get_document(code), base_url, "labels_")
    st.markdown("""**Como usar:** imprima a etiqueta PNG, cole na pasta física e escaneie com a câmera do celular.
Se configurar a URL do site, o código abrirá diretamente a ficha. Caso contrário, o código apenas mostrará a identificação do documento.""")


def admin_page(repo: Repository) -> None:
    banner("Backup e recuperação", "Exporte os dados do acervo e restaure um backup quando necessário.", "PROTEÇÃO DOS REGISTROS")
    st.warning("No Streamlit Community Cloud, arquivos SQLite locais não são armazenamento permanente: podem desaparecer após reinícios ou atualizações. Para uso contínuo, configure DATABASE_URL com PostgreSQL. Faça backups periódicos.")
    blob = repo.backup_json()
    st.download_button("⬇️ Baixar backup completo (.json)", blob,
                       file_name=f"FDS_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json", mime="application/json")
    st.caption("O arquivo contém metadados, histórico e documentos digitais anexados. Guarde-o em local protegido.")
    st.divider()
    st.markdown("### Restaurar backup")
    st.write("O sistema adiciona os documentos que ainda não existem, sem duplicar os códigos já cadastrados.")
    uploaded = st.file_uploader("Escolha um backup do próprio FDS", type=["json"], key="restore_upload")
    confirmed = st.checkbox("Confirmo que confio neste arquivo e desejo importar os dados")
    if st.button("Restaurar registros", disabled=not (uploaded and confirmed), type="primary"):
        try:
            n, m = repo.restore_json(uploaded.getvalue())
            st.success(f"Backup importado: {n} documento(s) e {m} movimentação(ões) adicionados.")
        except (ValueError, KeyError, TypeError) as exc:
            st.error(f"Não foi possível restaurar esse backup: {exc}")


def project_page() -> None:
    banner("Conheça o projeto FDS", "Proposta de inovação em Administração: organização, tecnologia e segurança para arquivos físicos e digitais.", "ADM · SENAC")
    t1, t2, t3 = st.tabs(["📘 Apresentação", "🗓️ Execução e orçamento", "📊 Resultados e referências"])
    with t1:
        st.markdown("""
### 1. Introdução e contextualização
A organização documental é essencial para escolas, empresas e instituições. Contudo, muitos arquivos permanecem em pastas, caixas e armários, o que pode tornar a consulta demorada. O **Find Doc School (FDS)** conecta o arquivo físico ao cadastro digital para identificar a localização exata dos documentos.

### 2. Problema ou oportunidade
Documentos perdidos ou difíceis de localizar provocam atrasos, retrabalho, desorganização e falta de controle sobre empréstimos. A oportunidade é usar **QR Codes** e um sistema simples para localizar e acompanhar arquivos.

### 3. Justificativa
Ao integrar informações físicas e digitais, a proposta pretende reduzir o tempo de busca, evitar extravios e modernizar tarefas administrativas. Também incentiva o uso de tecnologias acessíveis, com melhor organização e menos cópias desnecessárias.

### 4. Objetivos
**Geral:** desenvolver um sistema de localização e organização de documentos físicos e digitais com QR Code.

**Específicos:** cadastrar documentos; identificar sala, armário, gaveta, caixa e pasta; gerar códigos; mostrar mapa virtual; registrar retirada e devolução; reduzir tempo de procura; melhorar a segurança.

### 5. Público-alvo e beneficiários
Secretarias escolares, funcionários administrativos, gestores de acervo e equipes autorizadas em escolas e instituições que organizam arquivos físicos.

### 6. Descrição da proposta
- **Cadastro e digitalização:** cada documento recebe código, categoria, responsável, localização e cópia digital opcional.
- **QR Code:** etiqueta na pasta ou caixa, contendo código ou link para abrir a ficha no site.
- **Mapa virtual:** sala → armário → gaveta/caixa → pasta → documento.
- **Controle de retiradas:** registro de responsável, setor/destino, data, situação e devolução.
- **Segurança:** acesso com senha configurável; QR não carrega informações pessoais; anexos são acessados pelo sistema protegido.
""")
    with t2:
        st.markdown("""
### 7. Metodologia e plano de execução
1. Identificar as dificuldades atuais de organização.
2. Planejar quais documentos participarão do protótipo.
3. Organizar os arquivos físicos e padronizar etiquetas.
4. Cadastrar arquivos e gerar códigos QR.
5. Testar buscas, acesso com celular e movimentações.
6. Avaliar resultados e aperfeiçoar a solução.

### 8. Cronograma estimado
""")
        st.table(pd.DataFrame([
            ("Pesquisa e identificação do problema", "1ª semana"),
            ("Planejamento do sistema", "2ª semana"),
            ("Organização dos arquivos físicos", "3ª semana"),
            ("Cadastro digital e QR Codes", "4ª semana"),
            ("Testes e ajustes", "5ª semana"),
            ("Avaliação e apresentação", "6ª semana"),
        ], columns=["Etapa", "Período"]))
        st.markdown("### 9. Recursos necessários e orçamento")
        st.write("**Equipe:** estudantes com orientação docente. **Tecnologia:** computador, celular, impressora, internet e sistema FDS. **Materiais:** etiquetas, pastas, caixas e identificadores.")
        st.table(pd.DataFrame([
            ("Folhas adesivas para QR Codes", "R$ 25,00"),
            ("Pastas organizadoras", "R$ 30,00"),
            ("Duas caixas para arquivos", "R$ 36,00"),
            ("Materiais de identificação", "R$ 15,00"),
            ("Ferramentas digitais gratuitas", "R$ 0,00"),
            ("TOTAL ESTIMADO", "R$ 106,00"),
        ], columns=["Item", "Estimativa"]))
        st.caption("Valores ilustrativos sujeitos a variação; considera equipamentos já disponíveis.")
    with t3:
        st.markdown("""
### 10. Resultados esperados
- Diminuir o tempo gasto na busca por documentos.
- Melhorar a organização e localização física dos arquivos.
- Evitar extravios com controle de empréstimos e devoluções.
- Facilitar consultas pelos profissionais autorizados.
- Cadastrar **50 documentos fictícios** como meta inicial de testes.

### 11. Análise de viabilidade
**Técnica:** QR Codes, computador e celular tornam o protótipo acessível. **Financeira:** custos materiais modestos com equipamentos existentes. **Operacional:** implementação gradual com treinamento da equipe. **Segurança:** exige permissões, backups, controles de acesso e conformidade com a LGPD.

Para operação permanente na internet, é importante contratar/configurar banco de dados persistente. A versão com SQLite é adequada para protótipo local, não para arquivamento permanente em hospedagem temporária.

### 12. Referências
- **BRASIL.** Lei nº 8.159/1991: política nacional de arquivos públicos e privados.
- **BRASIL.** Lei nº 13.709/2018: Lei Geral de Proteção de Dados Pessoais (LGPD).
- **CONARQ.** Resolução nº 50/2022: e-ARQ Brasil, versão 2.

### 13. Anexos demonstrativos
**Ficha fictícia:** histórico escolar, código FDS-00001, Sala 2, Armário 5, Gaveta 3, Pasta 18, situação disponível.

**Fluxo:** documento físico → cadastro digital → geração do QR Code → busca/mapa virtual → controle de movimentação.

**Protótipo:** use a página **Cadastrar** para criar a ficha; **Etiquetas e QR Codes** para imprimir; **Mapa virtual** para localizar.

### 14. Considerações finais
O Find Doc School mostra como ferramentas digitais simples podem tornar o trabalho administrativo mais organizado, eficiente e rastreável, sem substituir a guarda segura dos documentos físicos.
""")


SAMPLE_DOCS = [
    dict(title="Histórico escolar (fictício)", doc_type="Histórico escolar", description="Exemplo criado somente para apresentar o sistema.", room="2", cabinet="5", drawer="3", box="", folder="18", creator="Equipe FDS"),
    dict(title="Matrícula 2026 (fictícia)", doc_type="Matrícula", description="Registro demonstrativo, sem informações reais.", room="2", cabinet="5", drawer="3", box="", folder="19", creator="Equipe FDS"),
    dict(title="Declaração de frequência (fictícia)", doc_type="Declaração", description="Apenas para os testes.", room="2", cabinet="4", drawer="1", box="A", folder="7", creator="Equipe FDS"),
    dict(title="Contrato de serviço (fictício)", doc_type="Contrato", description="Exemplo de gestão administrativa.", room="1", cabinet="1", drawer="2", box="", folder="3", creator="Equipe FDS"),
    dict(title="Ofício administrativo (fictício)", doc_type="Ofício", description="Arquivo de demonstração.", room="1", cabinet="2", drawer="", box="B", folder="5", creator="Equipe FDS"),
    dict(title="Ata de reunião (fictícia)", doc_type="Ata", description="Documento simulado para a feira.", room="3", cabinet="1", drawer="", box="", folder="2", creator="Equipe FDS"),
]



def require_login() -> None:
    """Mostra uma tela de senha centralizada com a identidade visual do projeto."""
    if not PASSWORD or st.session_state.get("authorized", False):
        return

    st.markdown("""
    <style>
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarNav"] {display:none !important;}
    [data-testid="stMainBlockContainer"], .block-container {
        max-width: 540px !important;
        margin: 0 auto !important;
        padding-top: clamp(28px, 7vh, 70px) !important;
        padding-bottom: 35px !important;
    }
    .fds-login-image {
        border-radius: 24px;
        overflow: hidden;
        box-shadow: 0 16px 36px rgba(12,31,82,.20);
        border: 2px solid rgba(247,198,0,.45);
        margin-bottom: 18px;
    }
    .fds-login-header {
        text-align:center;
        padding:22px 14px 18px;
        background:linear-gradient(112deg,#0c1f52 0%, #0047bb 62%, #d62828 100%);
        color:#fff;
        border-radius:20px;
        box-shadow:0 12px 26px rgba(12,31,82,.18);
        margin-bottom: 17px;
        border:1px solid rgba(247,198,0,.35);
    }
    .fds-login-header h1 {
        color:#fff !important;
        font-size:1.72rem;
        font-weight:800;
        margin:0 0 6px;
    }
    .fds-login-header p {color:#f5f9ff;margin:0;font-size:.96rem;}
    [data-testid="stForm"] {
        border:1px solid #e1eaf2 !important;
        background:#fff;
        box-shadow:0 9px 26px rgba(18,56,87,.08);
        border-radius:18px;
        padding:20px 22px;
    }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"], .block-container {
            padding-top: 4vh !important;
            padding-left: 16px !important;
            padding-right: 16px !important;
        }
        .fds-login-header h1 {font-size:1.46rem;}
        [data-testid="stForm"] {padding:17px 15px;}
    }
    </style>
    """, unsafe_allow_html=True)

    if os.path.exists(LOGIN_SPLASH_PATH):
        st.markdown('<div class="fds-login-image">', unsafe_allow_html=True)
        st.image(LOGIN_SPLASH_PATH, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="fds-login-header">
        <h1>FIND DOC SCHOOL</h1>
        <p>Acesso protegido · Digite a senha para continuar</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("fds_login_form"):
        attempt = st.text_input("Senha de acesso", type="password", placeholder="Digite sua senha")
        submitted = st.form_submit_button("🔓 Entrar no sistema", type="primary", use_container_width=True)

    if submitted:
        if hmac.compare_digest(attempt, PASSWORD):
            st.session_state["authorized"] = True
            st.rerun()
        else:
            st.error("Senha incorreta. Tente novamente.")
    st.caption("Acesso exclusivo à equipe autorizada. Não compartilhe a senha.")
    st.stop()


def main() -> None:
    # A autenticação vem ANTES da barra lateral e das páginas.
    require_login()
    with st.sidebar:
        brand_left, brand_right = st.columns([1, 1.8], vertical_alignment="center")
        with brand_left:
            if os.path.exists(SIDEBAR_LOGO_PATH):
                st.image(SIDEBAR_LOGO_PATH, use_container_width=True)
            else:
                st.markdown("## 🗂️")
        with brand_right:
            st.markdown("<div class='fds-sidebar-brand'><h3>FIND DOC SCHOOL</h3><p>Sistema inteligente de arquivos · FDS</p></div>", unsafe_allow_html=True)
        st.divider()
        if PASSWORD:
            st.caption("🔒 Acesso protegido")
            if st.button("🚪 Sair da conta", use_container_width=True):
                st.session_state["authorized"] = False
                st.rerun()
        else:
            st.info("🧪 Modo demonstração sem senha. Use somente arquivos fictícios.")
        pages = [
            "🏠 Painel", "➕ Cadastrar documento", "🔎 Buscar documentos",
            "🗺️ Mapa virtual", "🔄 Movimentações", "🏷️ Etiquetas e QR Codes",
            "📘 Sobre o projeto", "💾 Backup e recuperação",
        ]
        def clear_deep_link():
            if st.query_params.get("doc"):
                del st.query_params["doc"]
        page = st.radio("Menu principal", pages, key="fds_page", on_change=clear_deep_link)
        st.divider()
        st.markdown("**🔗 Endereço público do site**")
        base_url = st.text_input("URL para abrir QR Codes", value=PUBLIC_APP_URL,
                                 placeholder="https://meu-site.streamlit.app",
                                 help="Cole a URL do site publicado. É usada no QR para abrir a ficha do documento; o endereço é mantido durante esta sessão.")
        st.caption("O código QR pode apontar para uma ficha online quando há URL pública configurada.")
        st.divider()
        st.caption("Projeto de Administração · SENAC\n\nProtótipo educacional")

    try:
        repo = get_repository(DB_URL)
    except Exception as exc:
        st.error("Não foi possível conectar ao banco de dados. Confira DATABASE_URL nas configurações do aplicativo.")
        st.caption(f"Detalhes técnicos: {type(exc).__name__}")
        st.stop()

    doc_link = st.query_params.get("doc", "")
    if isinstance(doc_link, str) and doc_link:
        st.caption("FIND DOC SCHOOL › Ficha aberta por QR Code")
        detail_page(repo, doc_link, base_url)
        return

    if page == "🏠 Painel":
        dashboard(repo)
    elif page == "➕ Cadastrar documento":
        register_page(repo, base_url)
    elif page == "🔎 Buscar documentos":
        search_page(repo, base_url)
    elif page == "🗺️ Mapa virtual":
        map_page(repo)
    elif page == "🔄 Movimentações":
        moves_page(repo)
    elif page == "🏷️ Etiquetas e QR Codes":
        labels_page(repo, base_url)
    elif page == "📘 Sobre o projeto":
        project_page()
    elif page == "💾 Backup e recuperação":
        admin_page(repo)


if __name__ == "__main__":
    main()
