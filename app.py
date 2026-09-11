import http.server
import socketserver
import json
import urllib.parse
import os
import sqlite3
import re
import threading
import time
from downloader import download_file, DOWNLOADS_DIR

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "standards.db")

active_downloads = {}  # {url: {"status": "in_progress|done|error", "percent": 0, "filename": ""}}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def is_downloaded(rel_path):
    target = os.path.join(DOWNLOADS_DIR, rel_path.replace("/", os.sep))
    return os.path.exists(target)

def query_standards(query="", org="", limit=50, offset=0):
    conn = get_db()
    cur = conn.cursor()
    
    clean_query = query.strip()
    norm_query = re.sub(r'\b0+(\d+)\b', r'\1', clean_query)
    
    sql = "SELECT id, name, filename, org, subfolder, date, size, size_bytes, url, path, extension FROM standards"
    where = []
    params = []
    
    if clean_query:
        words = clean_query.split()
        fts_parts = []
        for w in words:
            w_norm = re.sub(r'\b0+(\d+)\b', r'\1', w)
            if w_norm != w:
                fts_parts.append(f'("{w}" OR "{w_norm}")')
            else:
                fts_parts.append(f'"{w}"*')
        fts_expr = " AND ".join(fts_parts)
        
        where.append("""
            (id IN (SELECT rowid FROM standards_fts WHERE standards_fts MATCH ?)
             OR filename LIKE ?
             OR norm_name LIKE ?)
        """)
        params.extend([fts_expr, f"%{clean_query}%", f"%{norm_query}%"])
        
    if org and org.upper() != "TODOS":
        where.append("org = ?")
        params.append(org.upper())
        
    if where:
        sql += " WHERE " + " AND ".join(where)
        
    # Contagem total
    count_sql = f"SELECT COUNT(*) FROM ({sql})"
    cur.execute(count_sql, params)
    total_count = cur.fetchone()[0]
    
    sql += " ORDER BY org ASC, filename ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cur.execute(sql, params)
    rows = cur.fetchall()
    
    results = []
    for r in rows:
        local_exists = is_downloaded(r["path"])
        item = dict(r)
        item["local_downloaded"] = local_exists
        item["local_path"] = f"/downloads/{r['path']}" if local_exists else None
        item["download_state"] = active_downloads.get(r["url"], {}).get("status", "none")
        results.append(item)
        
    conn.close()
    return total_count, results

def get_categories():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT org, COUNT(*) as count FROM standards GROUP BY org ORDER BY count DESC")
    rows = cur.fetchall()
    cats = [{"org": r["org"], "count": r["count"]} for r in rows]
    
    cur.execute("SELECT COUNT(*) FROM standards")
    total = cur.fetchone()[0]
    conn.close()
    return total, cats

def start_download_thread(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, filename, url, path FROM standards WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False
        
    url = row["url"]
    rel_path = row["path"]
    filename = row["filename"]
    
    if url in active_downloads and active_downloads[url]["status"] == "in_progress":
        return True
        
    active_downloads[url] = {"status": "in_progress", "filename": filename}
    
    def run():
        ok = download_file(url, rel_path=rel_path)
        active_downloads[url]["status"] = "done" if ok else "error"
        
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return True

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Standards (clara.nz)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #ffffff;
            --card-bg: #ffffff;
            --card-border: #000000;
            --text-main: #000000;
            --text-muted: #555555;
            --text-subtle: #777777;
            --border-light: #e5e5e5;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            border-radius: 0 !important; /* Bordas quadradas em todos os elementos */
        }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            padding: 32px 24px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--card-border);
            flex-wrap: wrap;
            gap: 16px;
        }
        .title-group h1 {
            font-size: 1.6rem;
            font-weight: 700;
            color: #000000;
            letter-spacing: -0.02em;
        }
        .title-group p {
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-top: 4px;
        }
        .stats-badge {
            background: #ffffff;
            border: 1px solid #000000;
            color: #000000;
            padding: 8px 16px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .search-section {
            background: var(--card-bg);
            border: 2px solid var(--card-border);
            padding: 20px;
            margin-bottom: 24px;
        }
        .search-box {
            position: relative;
            display: flex;
            align-items: center;
        }
        .search-icon {
            position: absolute;
            left: 16px;
            font-size: 1rem;
            color: var(--text-muted);
            pointer-events: none;
        }
        .search-input {
            width: 100%;
            background: #ffffff;
            border: 1px solid #000000;
            padding: 14px 16px 14px 44px;
            color: #000000;
            font-size: 1rem;
            font-family: inherit;
            outline: none;
        }
        .search-input:focus {
            border: 2px solid #000000;
            outline: none;
        }
        .category-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }
        .chip {
            background: #ffffff;
            border: 1px solid #000000;
            color: #000000;
            padding: 6px 14px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: background-color 0.1s;
            user-select: none;
        }
        .chip:hover {
            background: #f0f0f0;
        }
        .chip.active {
            background: #000000;
            color: #ffffff;
            border-color: #000000;
            font-weight: 600;
        }
        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            color: var(--text-muted);
            font-size: 0.88rem;
        }
        .table-container {
            background: #ffffff;
            border: 2px solid #000000;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }
        thead {
            background: #f7f7f7;
            border-bottom: 2px solid #000000;
        }
        th {
            padding: 14px 16px;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #000000;
        }
        td {
            padding: 12px 16px;
            font-size: 0.9rem;
            border-bottom: 1px solid var(--border-light);
            vertical-align: middle;
            color: #000000;
        }
        tr:last-child td {
            border-bottom: none;
        }
        tr:hover td {
            background-color: #fafafa;
        }
        .badge-org {
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.75rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            background: #ffffff;
            color: #000000;
            border: 1px solid #000000;
        }
        .filename-cell {
            font-weight: 500;
            font-family: 'JetBrains Mono', monospace;
            word-break: break-word;
            color: #000000;
        }
        .btn-group {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            font-size: 0.8rem;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.1s;
        }
        .btn-primary {
            background: #ffffff;
            color: #000000;
            border: 1px solid #000000;
        }
        .btn-primary:hover {
            background: #000000;
            color: #ffffff;
        }
        .btn-download {
            background: #000000;
            color: #ffffff;
            border: 1px solid #000000;
        }
        .btn-download:hover {
            background: #333333;
        }
        .btn-downloaded {
            background: #e5e5e5;
            color: #000000;
            border: 1px solid #000000;
        }
        .btn-downloaded:hover {
            background: #d4d4d4;
        }
        .btn-secondary {
            background: #ffffff;
            color: #000000;
            border: 1px solid #000000;
        }
        .btn-secondary:hover {
            background: #f0f0f0;
        }
        .btn-secondary:disabled {
            background: #f5f5f5;
            color: #999999;
            border-color: #cccccc;
            cursor: not-allowed;
        }
        .empty-state {
            padding: 48px 16px;
            text-align: center;
            color: var(--text-muted);
        }
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            margin-top: 24px;
        }
        .page-info {
            font-size: 0.88rem;
            color: var(--text-main);
            font-weight: 500;
        }
        .loading-spinner {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid #ccc;
            border-top-color: #000;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #000000;
            border: 1px solid #000000;
            color: #ffffff;
            padding: 12px 20px;
            font-size: 0.88rem;
            display: none;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="title-group">
                <h1>Standards</h1>
                <p>Catálogo e busca de standards de clara.nz</p>
            </div>
            <div class="stats-badge" id="totalStats">
                Carregando catálogo...
            </div>
        </header>

        <div class="search-section">
            <div class="search-box">
                <input type="text" id="searchInput" class="search-input" style="padding-left: 16px;" placeholder="Buscar standard por número ou nome (ex: 9001, 14229, 27001, J1939, CAN, USB, 26262)..." autofocus autocomplete="off">
            </div>
            <div class="category-chips" id="categoryChips">
                <div class="chip active" data-org="TODOS">Todos</div>
            </div>
        </div>

        <div class="results-header">
            <span id="resultsCount">Mostrando resultados...</span>
            <span id="queryTime"></span>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 100px;">Org</th>
                        <th>Arquivo / Standard</th>
                        <th style="width: 110px;">Tamanho</th>
                        <th style="width: 130px;">Data</th>
                        <th style="width: 250px; text-align: center;">Ações</th>
                    </tr>
                </thead>
                <tbody id="resultsTableBody">
                    <tr><td colspan="5" class="empty-state">Digite algo para iniciar a busca...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="pagination" id="paginationControls">
            <button class="btn btn-secondary" id="prevPageBtn" disabled>← Anterior</button>
            <span class="page-info" id="pageInfo">Página 1</span>
            <button class="btn btn-secondary" id="nextPageBtn" disabled>Próxima →</button>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        let currentQuery = "";
        let currentOrg = "TODOS";
        let currentPage = 1;
        const pageSize = 40;
        let searchDebounceTimer = null;

        const searchInput = document.getElementById("searchInput");
        const categoryChips = document.getElementById("categoryChips");
        const resultsTableBody = document.getElementById("resultsTableBody");
        const resultsCount = document.getElementById("resultsCount");
        const queryTime = document.getElementById("queryTime");
        const totalStats = document.getElementById("totalStats");
        const prevPageBtn = document.getElementById("prevPageBtn");
        const nextPageBtn = document.getElementById("nextPageBtn");
        const pageInfo = document.getElementById("pageInfo");
        const toast = document.getElementById("toast");

        function showToast(msg) {
            toast.innerText = msg;
            toast.style.display = "block";
            setTimeout(() => { toast.style.display = "none"; }, 3000);
        }

        async function loadStats() {
            try {
                const res = await fetch("/api/stats");
                const data = await res.json();
                totalStats.innerText = `${data.total.toLocaleString()} standards indexados`;

                categoryChips.innerHTML = '<div class="chip active" data-org="TODOS">Todos (' + data.total.toLocaleString() + ')</div>';
                data.categories.forEach(c => {
                    const chip = document.createElement("div");
                    chip.className = "chip";
                    chip.dataset.org = c.org;
                    chip.innerText = `${c.org} (${c.count.toLocaleString()})`;
                    chip.addEventListener("click", () => {
                        document.querySelectorAll(".chip").forEach(el => el.classList.remove("active"));
                        chip.classList.add("active");
                        currentOrg = c.org;
                        currentPage = 1;
                        executeSearch();
                    });
                    categoryChips.appendChild(chip);
                });

                categoryChips.querySelector('[data-org="TODOS"]').addEventListener("click", (e) => {
                    document.querySelectorAll(".chip").forEach(el => el.classList.remove("active"));
                    e.target.classList.add("active");
                    currentOrg = "TODOS";
                    currentPage = 1;
                    executeSearch();
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function executeSearch() {
            const start = performance.now();
            resultsTableBody.innerHTML = '<tr><td colspan="5" class="empty-state"><span class="loading-spinner"></span> Buscando standards...</td></tr>';
            
            const offset = (currentPage - 1) * pageSize;
            const params = new URLSearchParams({
                q: currentQuery,
                org: currentOrg,
                limit: pageSize,
                offset: offset
            });

            try {
                const res = await fetch(`/api/search?${params.toString()}`);
                const data = await res.json();
                const duration = Math.round(performance.now() - start);

                resultsCount.innerText = `${data.total.toLocaleString()} standard(s) encontrado(s)`;
                queryTime.innerText = `${duration} ms`;

                renderResults(data.results, data.total);
            } catch (err) {
                resultsTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">Erro ao buscar no servidor.</td></tr>';
            }
        }

        function renderResults(items, total) {
            if (!items || items.length === 0) {
                resultsTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">Nenhum standard encontrado para essa pesquisa.</td></tr>';
                prevPageBtn.disabled = true;
                nextPageBtn.disabled = true;
                pageInfo.innerText = "Página 0 de 0";
                return;
            }

            const totalPages = Math.ceil(total / pageSize);
            pageInfo.innerText = `Página ${currentPage} de ${totalPages}`;
            prevPageBtn.disabled = currentPage <= 1;
            nextPageBtn.disabled = currentPage >= totalPages;

            let html = "";
            items.forEach(item => {
                let downloadBtn = "";
                if (item.local_downloaded) {
                    downloadBtn = `<a href="${item.local_path}" target="_blank" class="btn btn-downloaded" title="Abrir arquivo salvo localmente">Salvo Local</a>`;
                } else if (item.download_state === "in_progress") {
                    downloadBtn = `<button class="btn btn-secondary" disabled><span class="loading-spinner"></span> Baixando...</button>`;
                } else {
                    downloadBtn = `<button class="btn btn-download" onclick="triggerDownload(${item.id}, this)">Baixar</button>`;
                }

                html += `
                    <tr>
                        <td><span class="badge-org">${item.org}</span></td>
                        <td class="filename-cell">${escapeHtml(item.filename)}</td>
                        <td>${item.size || "-"}</td>
                        <td>${item.date || "-"}</td>
                        <td>
                            <div class="btn-group" style="justify-content: center;">
                                <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary" title="Abrir diretamente de clara.nz">Abrir Online</a>
                                ${downloadBtn}
                            </div>
                        </td>
                    </tr>
                `;
            });
            resultsTableBody.innerHTML = html;
        }

        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
        }

        async function triggerDownload(itemId, btn) {
            btn.innerHTML = '<span class="loading-spinner"></span> Baixando...';
            btn.disabled = true;
            btn.className = "btn btn-secondary";

            try {
                const res = await fetch("/api/download", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({id: itemId})
                });
                const data = await res.json();
                if (data.ok) {
                    showToast("Download iniciado em segundo plano com suporte a retomada!");
                    pollDownload(itemId, btn);
                } else {
                    showToast("Erro ao iniciar download: " + data.message);
                    btn.innerText = "⬇️ Tentar Novamente";
                    btn.disabled = false;
                    btn.className = "btn btn-download";
                }
            } catch (e) {
                btn.innerText = "⬇️ Tentar Novamente";
                btn.disabled = false;
                btn.className = "btn btn-download";
            }
        }

        function pollDownload(itemId, btn) {
            const check = setInterval(async () => {
                try {
                    const res = await fetch(`/api/search?q=${currentQuery}&org=${currentOrg}&limit=1&offset=0`);
                    // re-executa a busca para atualizar o estado da linha
                    executeSearch();
                    clearInterval(check);
                } catch(e) {}
            }, 3000);
        }

        searchInput.addEventListener("input", (e) => {
            currentQuery = e.target.value;
            currentPage = 1;
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(executeSearch, 150);
        });

        prevPageBtn.addEventListener("click", () => {
            if (currentPage > 1) {
                currentPage--;
                executeSearch();
            }
        });

        nextPageBtn.addEventListener("click", () => {
            currentPage++;
            executeSearch();
        });

        loadStats().then(() => {
            executeSearch();
        });
    </script>
</body>
</html>
"""

class AppHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            
        elif path == "/api/stats":
            total, cats = get_categories()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"total": total, "categories": cats}).encode("utf-8"))
            
        elif path == "/api/search":
            q = query.get("q", [""])[0]
            org = query.get("org", ["TODOS"])[0]
            limit = int(query.get("limit", [40])[0])
            offset = int(query.get("offset", [0])[0])
            
            total, results = query_standards(query=q, org=org, limit=limit, offset=offset)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"total": total, "results": results}).encode("utf-8"))
            
        elif path.startswith("/downloads/"):
            rel_file = urllib.parse.unquote(path[len("/downloads/"):])
            file_path = os.path.join(DOWNLOADS_DIR, rel_file.replace("/", os.sep))
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf" if file_path.endswith(".pdf") else "application/octet-stream")
                self.send_header("Content-Length", str(os.path.getsize(file_path)))
                self.end_headers()
                with open(file_path, "rb") as f:
                    while chunk := f.read(64*1024):
                        self.wfile.write(chunk)
            else:
                self.send_error(404, "Arquivo não encontrado")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/download":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            try:
                data = json.loads(body)
                item_id = data.get("id")
                ok = start_download_thread(item_id)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": ok}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "message": str(e)}).encode("utf-8"))
        else:
            self.send_error(404)

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), AppHandler) as httpd:
        print(f"\n=======================================================")
        print(f"  Buscador de Normas (clara.nz) ativo!")
        print(f"  Acesse no seu navegador: http://localhost:{PORT}")
        print(f"=======================================================\n")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
