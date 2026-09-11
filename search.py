import sqlite3
import argparse
import sys
import os
import re

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standards.db")
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

def normalize_query(q):
    # Converte ISO 68 -> ISO 00068 e vice-versa
    tokens = q.strip().split()
    return tokens

def search_standards(query, org=None, limit=25):
    if not os.path.exists(DB_PATH):
        print("Erro: Banco de dados standards.db não encontrado! Execute build_db.py primeiro.")
        return []

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Prepara consulta FTS e LIKE combinadas para máxima precisão e recall
    clean_query = query.strip()
    
    # Remove zeros a esquerda em numeros
    norm_query = re.sub(r'\b0+(\d+)\b', r'\1', clean_query)
    
    # Termos FTS
    words = clean_query.split()
    fts_parts = []
    for w in words:
        w_norm = re.sub(r'\b0+(\d+)\b', r'\1', w)
        if w_norm != w:
            fts_parts.append(f'("{w}" OR "{w_norm}")')
        else:
            fts_parts.append(f'"{w}"*')
    
    fts_expr = " AND ".join(fts_parts)

    params = []
    sql = """
        SELECT s.id, s.filename, s.org, s.subfolder, s.date, s.size, s.url, s.path
        FROM standards s
    """
    
    where_clauses = []
    
    if clean_query:
        where_clauses.append("""
            (s.id IN (SELECT rowid FROM standards_fts WHERE standards_fts MATCH ?)
             OR s.filename LIKE ?
             OR s.norm_name LIKE ?)
        """)
        params.extend([fts_expr, f"%{clean_query}%", f"%{norm_query}%"])
        
    if org and org.upper() != "TODOS":
        where_clauses.append("s.org = ?")
        params.append(org.upper())
        
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
        
    sql += " ORDER BY s.org ASC, s.filename ASC LIMIT ?"
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def is_downloaded(rel_path):
    target = os.path.join(DOWNLOADS_DIR, rel_path.replace("/", os.sep))
    return os.path.exists(target)

def print_results(rows):
    if not rows:
        print("\nNenhuma norma encontrada.")
        return

    print(f"\n{'ID':<6} | {'ORG':<6} | {'TAMANHO':<8} | {'DATA':<12} | {'STATUS':<9} | {'NOME DO ARQUIVO'}")
    print("-" * 95)
    for r in rows:
        sid, filename, org, subfolder, date, size, url, rel_path = r
        status = "[BAIXADO]" if is_downloaded(rel_path) else "[ONLINE] "
        print(f"{sid:<6} | {org:<6} | {size:<8} | {date:<12} | {status:<9} | {filename}")

    print("-" * 95)
    print(f"Total exibido: {len(rows)} resultados.")

def main():
    parser = argparse.ArgumentParser(description="Busca instantânea no acervo de 27.988 normas (clara.nz)")
    parser.add_argument("termo", nargs="*", help="Termo de busca (ex: 14229, ISO 9001, J1939, CAN, 27001)")
    parser.add_argument("--org", help="Filtrar por organização (ex: ISO, SAE, USB, ASAM, ODVA)")
    parser.add_argument("-n", "--limit", type=int, default=25, help="Quantidade máxima de resultados (padrão: 25)")
    parser.add_argument("-d", "--download", action="store_true", help="Baixar os arquivos encontrados com retomada")
    
    args = parser.parse_args()
    query = " ".join(args.termo)
    
    if not query and not args.org:
        # Modo interativo
        print("=" * 60)
        print("  SISTEMA DE BUSCA DE NORMAS (clara.nz / standards)")
        print("=" * 60)
        print("Total de 27.988 normas indexadas (ISO, SAE, USB, CAN, etc.)\n")
        
        while True:
            try:
                user_q = input("\nDigite a norma ou palavra-chave (ou 'sair'): ").strip()
                if user_q.lower() in ["sair", "exit", "quit", "q"]:
                    break
                if not user_q:
                    continue
                results = search_standards(user_q, limit=args.limit)
                print_results(results)
                
                if results:
                    action = input("\nDeseja baixar algum ID listado? Digite o ID ou 'n': ").strip()
                    if action.isdigit():
                        chosen_id = int(action)
                        matched = [r for r in results if r[0] == chosen_id]
                        if matched:
                            from downloader import download_file
                            download_file(matched[0][6], rel_path=matched[0][7])
            except (KeyboardInterrupt, EOFError):
                break
    else:
        results = search_standards(query, org=args.org, limit=args.limit)
        print_results(results)
        
        if args.download and results:
            from downloader import download_file
            print("\nIniciando download dos arquivos encontrados...")
            for r in results:
                download_file(r[6], rel_path=r[7])

if __name__ == "__main__":
    main()
