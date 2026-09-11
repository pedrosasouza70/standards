import os
import sys
import urllib.request
import urllib.error
import time

DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def format_size(bytes_num):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def download_file(url, target_path=None, preserve_path=True, rel_path=""):
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        
    if not target_path:
        filename = url.split("/")[-1]
        if preserve_path and rel_path:
            target_path = os.path.join(DOWNLOADS_DIR, rel_path.replace("/", os.sep))
        else:
            target_path = os.path.join(DOWNLOADS_DIR, filename)
            
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    part_path = target_path + ".part"
    
    # Verifica se o arquivo final já existe
    existing_bytes = 0
    if os.path.exists(target_path):
        print(f"  [OK] Já baixado anteriormente: {os.path.basename(target_path)}")
        return True
        
    if os.path.exists(part_path):
        existing_bytes = os.path.getsize(part_path)
        
    req_headers = HEADERS.copy()
    if existing_bytes > 0:
        req_headers["Range"] = f"bytes={existing_bytes}-"
        print(f"  [Retomando download a partir de {format_size(existing_bytes)}]...")
    else:
        print(f"  [Iniciando download] {os.path.basename(target_path)}...")

    req = urllib.request.Request(url, headers=req_headers)
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                content_range = resp.headers.get("Content-Range")
                content_length = resp.headers.get("Content-Length")
                
                total_size = None
                if content_range:
                    # bytes 1000-5000/5001
                    try:
                        total_size = int(content_range.split("/")[-1])
                    except:
                        pass
                elif content_length:
                    total_size = int(content_length) + (existing_bytes if status == 206 else 0)
                
                mode = "ab" if (status == 206 and existing_bytes > 0) else "wb"
                if mode == "wb":
                    existing_bytes = 0
                    
                bytes_downloaded = existing_bytes
                last_print = time.time()
                
                with open(part_path, mode) as out_f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        now = time.time()
                        if now - last_print > 0.5:
                            if total_size:
                                pct = (bytes_downloaded / total_size) * 100
                                sys.stdout.write(f"\r    {pct:.1f}% ({format_size(bytes_downloaded)} / {format_size(total_size)})")
                            else:
                                sys.stdout.write(f"\r    {format_size(bytes_downloaded)}")
                            sys.stdout.flush()
                            last_print = now
                            
                print(f"\r    100% ({format_size(bytes_downloaded)}) Concluído com sucesso!     ")
                
                # Renomeia de .part para o nome final
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.rename(part_path, target_path)
                return True
                
        except urllib.error.HTTPError as e:
            if e.code == 416: # Range Not Satisfiable (já baixou tudo)
                if os.path.exists(part_path):
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    os.rename(part_path, target_path)
                print("  [OK] Arquivo já completamente transferido.")
                return True
            print(f"  [Erro HTTP {e.code}]: {e.reason} (Tentativa {attempt}/{max_retries})")
        except Exception as e:
            print(f"  [Erro de conexão]: {e} (Tentativa {attempt}/{max_retries})")
            
        time.sleep(2 * attempt)
        if os.path.exists(part_path):
            existing_bytes = os.path.getsize(part_path)
            req_headers["Range"] = f"bytes={existing_bytes}-"
            req = urllib.request.Request(url, headers=req_headers)
            
    print(f"  [Falha] Não foi possível completar o download após {max_retries} tentativas.")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python downloader.py <URL_OU_BUSCA>")
        sys.exit(1)
        
    arg = sys.argv[1]
    if arg.startswith("http://") or arg.startswith("https://"):
        download_file(arg)
    else:
        # Busca no banco e baixa os resultados
        import sqlite3
        conn = sqlite3.connect("standards.db")
        cur = conn.cursor()
        cur.execute("SELECT filename, url, path, size FROM standards WHERE filename LIKE ? LIMIT 10", (f"%{arg}%",))
        rows = cur.fetchall()
        if not rows:
            print(f"Nenhum arquivo encontrado para: {arg}")
        else:
            print(f"Encontrados {len(rows)} arquivos:")
            for r in rows:
                print(f"-> {r[0]} ({r[3]})")
            confirm = input("Deseja baixar estes arquivos com suporte a retomada? (s/n): ")
            if confirm.lower().strip() in ["s", "sim", "y", "yes"]:
                for r in rows:
                    download_file(r[1], rel_path=r[2])
