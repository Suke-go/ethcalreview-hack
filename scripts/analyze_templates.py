"""
倫理審査書類テンプレート解析スクリプト
python-docxを使用してdocxファイルの構造を抽出する
"""
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
import json
import os
from pathlib import Path

def extract_document_structure(docx_path: str) -> dict:
    """docxファイルから構造を抽出"""
    doc = Document(docx_path)
    structure = {
        "filename": os.path.basename(docx_path),
        "sections": [],
        "tables": [],
        "placeholders": []
    }
    
    current_section = None
    
    for element in doc.element.body:
        # 段落の処理
        if element.tag.endswith('p'):
            para = Paragraph(element, doc)
            text = para.text.strip()
            
            if not text:
                continue
            
            # 見出しスタイルの検出
            style = para.style.name if para.style else "Normal"
            
            # セクション見出しの検出（番号で始まる場合）
            if text and (text[0].isdigit() or text.startswith('【')):
                current_section = {
                    "title": text,
                    "style": style,
                    "content": []
                }
                structure["sections"].append(current_section)
            elif current_section:
                current_section["content"].append({
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "style": style
                })
            
            # プレースホルダー候補の検出（〇、□、（　）など）
            if "〇" in text or "□" in text or "（　）" in text or "（ ）" in text:
                structure["placeholders"].append({
                    "context": text[:80],
                    "type": "checkbox" if "□" in text else "fill_in"
                })
        
        # 表の処理
        elif element.tag.endswith('tbl'):
            table = Table(element, doc)
            table_data = {
                "rows": len(table.rows),
                "columns": len(table.columns) if table.rows else 0,
                "headers": [],
                "sample_data": []
            }
            
            # ヘッダー行の取得
            if table.rows:
                for cell in table.rows[0].cells:
                    header_text = cell.text.strip()[:50]
                    if header_text:
                        table_data["headers"].append(header_text)
                
                # サンプルデータ（最初の2行）
                for row_idx, row in enumerate(table.rows[:3]):
                    row_data = [cell.text.strip()[:30] for cell in row.cells]
                    table_data["sample_data"].append(row_data)
            
            structure["tables"].append(table_data)
    
    return structure

def analyze_all_templates(sample_dir: str) -> dict:
    """サンプルディレクトリ内の全docxファイルを解析"""
    results = {}
    
    for filename in os.listdir(sample_dir):
        if filename.endswith('.docx') and not filename.startswith('~$'):
            filepath = os.path.join(sample_dir, filename)
            try:
                structure = extract_document_structure(filepath)
                results[filename] = structure
                print(f"[OK] Analyzed: {filename}")
                print(f"  - Sections: {len(structure['sections'])}")
                print(f"  - Tables: {len(structure['tables'])}")
                print(f"  - Placeholders: {len(structure['placeholders'])}")
            except Exception as e:
                print(f"[ERROR] {filename} - {e}")
                results[filename] = {"error": str(e)}
    
    return results

if __name__ == "__main__":
    sample_dir = r"c:\Users\kosuk\EthicalReviewHacker\sample"
    
    print("=" * 60)
    print("倫理審査書類テンプレート解析")
    print("=" * 60)
    
    results = analyze_all_templates(sample_dir)
    
    # 結果をJSONファイルに保存
    output_path = os.path.join(sample_dir, "template_structure.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n結果を保存: {output_path}")
    
    # 詳細な構造を表示
    print("\n" + "=" * 60)
    print("詳細構造")
    print("=" * 60)
    
    for filename, structure in results.items():
        if "error" not in structure:
            print(f"\n【{filename}】")
            print("-" * 40)
            for i, section in enumerate(structure["sections"][:10]):
                print(f"  {i+1}. {section['title'][:60]}...")
