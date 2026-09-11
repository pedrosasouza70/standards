import urllib.request
import re
import json
import os
import time
from urllib.parse import urljoin, unquote

BASE_URL = "https://clara.nz/docs/standards/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def crawl_standards():
    visited_dirs = set()
    dirs_to_visit = [BASE_URL]
    all_files = []
    
    print("Iniciando varredura em:", BASE_URL)
    
    while dirs_to_visit:
        curr_url = dirs_to_visit.pop(0)
        if curr_url in visited_dirs:
            continue
        visited_dirs.add(curr_url)
        
        display_path = unquote(curr_url.replace(BASE_URL, ""))
        print(f"[{len(visited_dirs)}] Acessando: /{display_path}")
        
        try:
            req = urllib.request.Request(curr_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"Erro ao acessar {curr_url}: {e}")
            continue
        
        # Procura linhas da tabela
        rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
        for r in rows:
            m_link = re.search(r'<a\s+href="([^"]+)">([^<]+)</a>', r)
            if not m_link:
                continue
            href = m_link.group(1).strip()
            name = m_link.group(2).strip()
            
            if href == ".." or href.startswith("/") or "download directory as zip" in name:
                continue
            
            cols = re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)
            date = cols[0].strip() if len(cols) > 0 else ""
            size = cols[1].strip() if len(cols) > 1 else ""
            
            full_url = urljoin(curr_url, href)
            
            # Se for pasta (size == '-' ou link sem extensao comum de arquivo)
            is_dir = (size == "-" or href.endswith("/"))
            if not is_dir and "." not in href.split("/")[-1]:
                is_dir = True
                
            if is_dir:
                if not full_url.endswith("/"):
                    full_url += "/"
                if full_url not in visited_dirs and full_url not in dirs_to_visit:
                    dirs_to_visit.append(full_url)
            else:
                rel_path = unquote(full_url.replace(BASE_URL, ""))
                parts = [p for p in rel_path.split("/") if p]
                category = parts[0] if len(parts) > 1 else "Geral"
                subcategory = parts[1] if len(parts) > 2 else ""
                
                all_files.append({
                    "name": name,
                    "filename": unquote(href.split("/")[-1]),
                    "url": full_url,
                    "path": rel_path,
                    "category": category,
                    "subcategory": subcategory,
                    "date": date,
                    "size": size
                })
        
        time.sleep(0.1)  # gentileza com o servidor
        
    print(f"\nVarredura concluída!")
    print(f"Total de pastas verificadas: {len(visited_dirs)}")
    print(f"Total de arquivos encontrados: {len(all_files)}")
    
    output_json = "standards_index.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(all_files, f, ensure_ascii=False, indent=2)
    print(f"Índice salvo em: {output_json}")

if __name__ == "__main__":
    crawl_standards()
