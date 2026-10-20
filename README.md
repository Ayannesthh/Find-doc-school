# Find Doc School (FDS) 🗂️

Site em **Python + Streamlit** para um projeto de Administração/SENAC. Inclui:

- Cadastro de documentos físicos e anexos digitais (até 5 MB por anexo).
- Identificação por código único `FDS-00001` e QR Code PNG.
- Etiqueta PNG para imprimir e colar nas pastas.
- Busca pelo nome, código, categoria e localização.
- Mapa de arquivo (sala, armário, gaveta, caixa, pasta).
- Controle de retirada, devolução, responsável e histórico.
- Painel com indicadores; projeto completo, cronograma e orçamento.
- Login por senha opcional e exportação/importação de backups JSON.
- SQLite local para a demonstração; PostgreSQL opcional para persistência em produção.

## 1. Rodar no computador

Instale [Python 3.11+](https://www.python.org/downloads/). Abra um terminal na pasta do projeto:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abra o endereço que aparecer (normalmente `http://localhost:8501`). Clique em **Carregar 6 documentos fictícios para demonstração** para ver exemplos.

## 2. Publicar no GitHub e Streamlit Community Cloud

1. Crie um repositório no GitHub chamado, por exemplo, `find-doc-school`.
2. Envie **os arquivos desta pasta**, mantendo `app.py`, `storage.py`, `qr_utils.py`, `requirements.txt` e a pasta `.streamlit` na raiz do repositório. **Não envie a senha real nem o banco `.db`.**
3. Abra https://share.streamlit.io/ e escolha **Create app / Deploy**.
4. Selecione o repositório e a branch `main`; informe **Main file path:** `app.py`.
5. Em **Advanced settings > Secrets**, cole configurações equivalentes às do exemplo abaixo. Publique e copie a URL do aplicativo.
6. Atualize `PUBLIC_APP_URL` em Secrets com a URL verdadeira do app, depois reinicie o aplicativo. Os QR Codes gerados então abrirão a ficha online. Também é possível informar essa URL na barra lateral.

**Secrets do Streamlit (exemplo sem valores reais):**

```toml
FDS_PASSWORD = "uma-senha-forte-criada-pela-equipe"
PUBLIC_APP_URL = "https://meu-fds.streamlit.app"
# Banco persistente opcional:
# DATABASE_URL = "postgresql://usuario:senha@host:5432/banco?sslmode=require"
```

### ⚠️ Atenção: não perder os cadastros

Sem `DATABASE_URL`, o sistema salva no arquivo local `fds.db` (SQLite). **No Streamlit Community Cloud, esse arquivo pode desaparecer ao reiniciar ou republicar o site.** Por isso:

- Para **apresentação escolar**, use dados fictícios e faça backups regulares na página **Backup e recuperação**.
- Para **uso permanente por várias pessoas**, conecte um **PostgreSQL gerenciado** via `DATABASE_URL` nas configurações de Secrets. O sistema cria suas tabelas automaticamente. Consulte a documentação do provedor do banco para a URL/SSL corretos. Não coloque credenciais no GitHub.
- A proteção por **senha compartilhada** é básica, adequada somente a uma demonstração controlada. Para documentos reais, são necessários usuários individuais, papéis/permissões, backups externos, política de privacidade e controles LGPD. **Não use dados pessoais reais neste protótipo.**

## 3. Usar QR Code

1. Cadastre o documento com sua localização.
2. Abra **Etiquetas e QR Codes**.
3. Informe na barra lateral a **URL pública do site** para que o QR direcione à ficha.
4. Baixe a etiqueta PNG e imprima.
5. Escaneie pelo celular: abrirá `https://meu-fds.streamlit.app/?doc=FDS-00001` (com sua URL), solicitando a senha caso o site esteja protegido.

Quando não há URL configurada, o QR Code contém **apenas o código para identificação** e não abre uma página automaticamente.

## 4. Estrutura do projeto

```text
find-doc-school/
├── app.py                       # Telas do site
├── storage.py                   # Banco de dados e histórico
├── qr_utils.py                  # Gerador QR + etiqueta
├── requirements.txt             # Bibliotecas
├── .gitignore                   # Evita publicar senhas / dados
├── .streamlit/
│   ├── config.toml              # Tema visual
│   └── secrets.toml.example     # Exemplo de configuração (sem senhas reais)
└── README.md
```

## 5. Limitações do protótipo

- Login por senha única compartilhada; sem identidade de usuário ou níveis de permissão.
- Não registra automaticamente o horário de acesso de leitores do QR.
- A localização é informada e atualizada pelos usuários, não rastreada por GPS.
- Para scanner móvel funcionar de qualquer lugar, o site deve estar publicado em URL acessível.
- Arquivos digitais são limitados a 5 MB e os backups podem conter anexos; trate-os com cuidado.
- Para implementação institucional, acrescente autenticação individual, registro de auditoria, gestão de consentimento/base legal e políticas de retenção antes de usar informações pessoais.

**Projeto acadêmico — Administração / SENAC.**
