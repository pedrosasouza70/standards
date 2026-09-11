# 🔍 Buscador e Gerenciador de Normas Técnicas (clara.nz)

Este repositório contém uma solução completa para **buscar e baixar normas técnicas** disponíveis no acervo do site `clara.nz/docs/standards/`, sem a necessidade de baixar dezenas de gigabytes de uma só vez.

---

## 📌 Por que o download da pasta inteira falhava ("sem suporte a retomada")?

O site `clara.nz` oferece um link chamado `(download directory as zip)` (`standards.zip`), que tenta compactar em tempo real mais de **27.988 normas (dezenas ou centenas de GB)** em uma única conexão HTTP ininterrupta.

Esse tipo de arquivo gerado dinamicamente:
1. **Não suporta o cabeçalho `Accept-Ranges` (HTTP 206 Partial Content)**: se a conexão oscilar por 1 segundo, o navegador é forçado a reiniciar o download do zero.
2. Sofre **timeout** pelos limites de conexão do Cloudflare/servidor antes de concluir o envio de centenas de gigabytes.

### A Solução Criada
Em vez de depender de um único arquivo `.zip` gigante:
1. Mapeamos e indexamos **todas as 27.988 normas** em um banco de dados local ultra-rápido (`standards.db` via SQLite FTS5).
2. Cada norma individual no servidor `clara.nz` **suporta retomada (`Accept-Ranges: bytes`)**.
3. Você pode pesquisar instantaneamente por número, código ou palavra-chave e:
   - **Abrir ou visualizar diretamente no navegador** com 1 clique (sem esperar download prévio).
   - **Baixar apenas a norma desejada**, com download resiliente que **retoma do ponto onde parou** caso a conexão caia.

---

## 🚀 Como Usar

### Opção 1: Interface Visual no Navegador (Recomendado)

Basta dar **duplo clique** no arquivo:
```cmd
iniciar_busca.bat
```
*(Ou execute no terminal: `python app.py`)*

O sistema abrirá automaticamente em seu navegador:
👉 **`http://localhost:8080`**

**Recursos da Interface Web:**
- ⚡ **Busca instantânea ao digitar**: Encontre qualquer norma em milissegundos.
- 🎯 **Filtros por Organização**: ISO (27.886 normas), SAE, USB, CAN, OBD2, ODVA, ASAM, etc.
- 🔗 **Botão "Abrir Online"**: Abre o arquivo diretamente na fonte oficial do clara.nz.
- ⬇️ **Botão "Baixar (Retomável)"**: Baixa para o seu computador (pasta `downloads/`) com suporte a retomada. Se já estiver baixado, ele muda para `💾 Salvo Local`.

---

### Opção 2: Busca Rápida pelo Terminal (CLI)

Se preferir usar o terminal PowerShell ou CMD:

```powershell
# Buscar por número da norma (com ou sem zeros à esquerda):
python search.py 9001
python search.py 14229
python search.py 27001
python search.py 26262

# Buscar por palavras-chave ou protocolos:
python search.py J1939
python search.py CAN
python search.py USB

# Filtrar por organização:
python search.py --org SAE

# Modo interativo (digitar buscas sucessivas):
python search.py
```

---

### Opção 3: Baixar com Retomada via Script

Caso queira baixar um arquivo específico ou lote de arquivos com garantia de retomada:

```powershell
# Baixar por URL direta com suporte a retomada:
python downloader.py "https://clara.nz/docs/standards/documents/ASAM/ASAM-MCD-2MC-v1.6.pdf"

# Baixar por busca:
python downloader.py 14229
```

Todos os arquivos baixados ficam salvos organizados na pasta `downloads/`.

---

## 📊 Estatísticas do Acervo Indexado

- **Total de normas catalogadas:** 27.988 arquivos
- **Organizações presentes:**
  - **ISO:** 27.886 normas (inclui ISO/IEC, ISO/TR, ISO/TS, etc.)
  - **SAE:** 11 documentos (J1939, CANopen, etc.)
  - **USB:** 13 especificações (USB 2.0, HID, etc.)
  - **ODVA:** 21 especificações de rede industrial
  - **CAN & OBD2:** Diagnóstico automotivo e barramentos
  - **ASAM, FTDI, GMW, LIN, VXI, etc.**

---

## 🌐 Como colocar no Render (onrender.com)

O projeto já está 100% configurado para o Render com `render.yaml`, detecção automática de porta e `standards.db` incluído.

### Passo a Passo no Render:
1. Acesse seu painel no [dashboard.render.com](https://dashboard.render.com).
2. Clique no botão **New +** e selecione **Web Service**.
3. Conecte sua conta do GitHub e escolha o repositório: `pedrosasouza70/normas-tecnicas`.
4. O Render detectará automaticamente as configurações. Caso peça para preencher:
   - **Runtime:** `Python 3`
   - **Build Command:** *(pode deixar vazio ou `pip install -r requirements.txt`)*
   - **Start Command:** `python app.py`
5. Clique em **Deploy Web Service** (no plano gratuito / Free).

Em poucos segundos, o Render fornecerá uma URL pública gratuita (ex: `https://normas-tecnicas.onrender.com`) para você e quem você quiser pesquisar as normas online de qualquer dispositivo!
