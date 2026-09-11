import json
import sqlite3
import re
import os

def normalize_text(text):
    # Remove zeros a esquerda em numeros para facilitar a busca (ex: ISO 00068 -> ISO 68)
    return re.sub(r'\b0+(\d+)\b', r'\1', text)

def build_database():
    json_path = "standards_index.json"
    db_path = "standards.db"
    
    if not os.path.exists(json_path):
        print(f"Erro: {json_path} não encontrado!")
        return

    print("Carregando índice JSON...")
    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    print(f"Total de itens carregados: {len(items)}")
    
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Criação da tabela principal
    cur.execute("""
    CREATE TABLE standards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        filename TEXT,
        norm_name TEXT,
        url TEXT,
        path TEXT,
        org TEXT,
        subfolder TEXT,
        date TEXT,
        size TEXT,
        size_bytes INTEGER,
        extension TEXT
    )
    """)
    
    # Criação da tabela de busca textual FTS5
    cur.execute("""
    CREATE VIRTUAL TABLE standards_fts USING fts5(
        name,
        norm_name,
        path,
        org,
        content='standards',
        content_rowid='id'
    )
    """)
    
    def parse_size_bytes(sz_str):
        if not sz_str or sz_str == "-":
            return 0
        sz_str = sz_str.strip().upper()
        try:
            if sz_str.endswith('K'):
                return int(float(sz_str[:-1]) * 1024)
            elif sz_str.endswith('M'):
                return int(float(sz_str[:-1]) * 1024 * 1024)
            elif sz_str.endswith('G'):
                return int(float(sz_str[:-1]) * 1024 * 1024 * 1024)
            elif sz_str.endswith('B'):
                return int(float(sz_str[:-1]))
            else:
                return int(float(sz_str))
        except:
            return 0

    records = []
    for item in items:
        name = item.get("name", "")
        filename = item.get("filename", "")
        norm_name = normalize_text(filename)
        url = item.get("url", "")
        path = item.get("path", "")
        
        # Identificar organização principal
        parts = path.split("/")
        if len(parts) > 1 and parts[0] == "documents":
            org = parts[1]
            subfolder = "/".join(parts[2:-1]) if len(parts) > 3 else ""
        elif len(parts) > 1 and parts[0] == "extras":
            org = parts[1] if len(parts) > 2 else "extras"
            subfolder = "/".join(parts[2:-1]) if len(parts) > 3 else ""
        else:
            org = "Outros"
            subfolder = ""
            
        ext = os.path.splitext(filename)[1].lower().replace(".", "")
        size_bytes = parse_size_bytes(item.get("size", ""))
        
        records.append((
            name,
            filename,
            norm_name,
            url,
            path,
            org,
            subfolder,
            item.get("date", ""),
            item.get("size", ""),
            size_bytes,
            ext
        ))
        
    print("Inserindo registros no banco de dados...")
    cur.executemany("""
    INSERT INTO standards (name, filename, norm_name, url, path, org, subfolder, date, size, size_bytes, extension)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records)
    
    print("Indexando com FTS5...")
    cur.execute("""
    INSERT INTO standards_fts(rowid, name, norm_name, path, org)
    SELECT id, name, norm_name, path, org FROM standards
    """)
    
    # Criar índices adicionais
    cur.execute("CREATE INDEX idx_org ON standards(org)")
    cur.execute("CREATE INDEX idx_ext ON standards(extension)")
    
    conn.commit()
    conn.close()
    print(f"Banco de dados construído com sucesso: {db_path} ({os.path.getsize(db_path) / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    build_database()
