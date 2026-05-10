import os
import re
import fitz  # PyMuPDF
from spellchecker import SpellChecker
from ebooklib import epub
import tkinter as tk
from tkinter import messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

class PDFtoEPUBConverter:
    def __init__(self):
        self.spell = SpellChecker()
        self.header_footer_margin = 50 # 判斷頁首/頁尾的邊界(像素)

    def is_valid_word(self, word):
        """檢查是否為合法的英文單字"""
        word = re.sub(r'[^a-zA-Z]', '', word).lower()
        if not word:
            return False
        return len(self.spell.known([word])) > 0

    def process_hyphenation(self, text):
        """智能修復跨行斷字"""
        lines = text.split('\n')
        processed_text = ""
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if line.endswith('-') and i + 1 < len(lines):
                # 取出下一行的第一個單字來組合測試
                next_line_words = lines[i+1].strip().split()
                if next_line_words:
                    next_word_part = next_line_words[0]
                    current_word_part = line.split()[-1][:-1]
                    combined_word = current_word_part + next_word_part
                    
                    if self.is_valid_word(combined_word):
                        # 如果是合法單字，則去掉連字號並準備與下一行合併
                        line = line[:-1]
            processed_text += line + " "
        return processed_text.strip()

    def sort_blocks(self, blocks, page_width):
        """處理雙欄幾何排序：先依左右分欄，再依上下排序"""
        left_column = []
        right_column = []
        mid_point = page_width / 2

        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            if x0 < mid_point:
                left_column.append(b)
            else:
                right_column.append(b)

        # 依照 Y 座標 (由上到下) 排序
        left_column.sort(key=lambda x: x[1])
        right_column.sort(key=lambda x: x[1])
        return left_column + right_column

    def convert(self, pdf_path):
        epub_path = os.path.splitext(pdf_path)[0] + ".epub"
        book = epub.EpubBook()
        
        # 設定 EPUB 基本資訊
        title = os.path.basename(pdf_path).replace('.pdf', '')
        book.set_title(title)
        book.set_language('en') # 預設主要語言
        
        doc = fitz.open(pdf_path)
        chapters = []
        html_content = f"<h1>{title}</h1>"

        image_counter = 1

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_rect = page.rect
            blocks = page.get_text("blocks")
            
            # 過濾掉頁首與頁尾
            valid_blocks = []
            for b in blocks:
                x0, y0, x1, y1, text, block_no, block_type = b
                # y0 太小(接近頂部) 或 y1 太大(接近底部) 視為頁首尾
                if y0 > self.header_footer_margin and y1 < (page_rect.height - self.header_footer_margin):
                    valid_blocks.append(b)

            # 雙欄排序
            sorted_blocks = self.sort_blocks(valid_blocks, page_rect.width)

            for b in sorted_blocks:
                x0, y0, x1, y1, content, block_no, block_type = b
                
                # 處理圖片區塊 (block_type == 1 代表影像)
                if block_type == 1:
                    base_image = doc.extract_image(block_no)
                    if base_image:
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        image_name = f"image_{page_num}_{image_counter}.{image_ext}"
                        
                        # 將圖片加入 EPUB
                        img_item = epub.EpubItem(uid=image_name, file_name=f"images/{image_name}", media_type=f"image/{image_ext}", content=image_bytes)
                        book.add_item(img_item)
                        
                        html_content += f'<div style="text-align: center;"><img src="images/{image_name}" alt="Figure" style="max-width: 100%;"/></div><br/>'
                        image_counter += 1
                
                # 處理文字區塊 (block_type == 0 代表文字)
                elif block_type == 0:
                    clean_text = self.process_hyphenation(content)
                    # 簡單段落判斷：如果最後一個字元不是句號，可能跟下一段相連
                    if clean_text:
                        html_content += f"<p>{clean_text}</p>"

        # 建立章節
        c1 = epub.EpubHtml(title='Content', file_name='chap_01.xhtml', lang='en')
        c1.content = html_content
        book.add_item(c1)
        chapters.append(c1)

        # 建立目錄與書脊 (Spine)
        book.toc = tuple(chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        style = 'BODY {color: white;}'
        nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
        book.add_item(nav_css)
        
        book.spine = ['nav'] + chapters

        # 匯出 EPUB
        epub.write_epub(epub_path, book)
        return epub_path

def on_drop(event):
    file_path = event.data
    # 清理路徑字串 (處理 Windows 拖曳路徑可能帶有大括號的問題)
    file_path = file_path.strip('{}')
    
    if not file_path.lower().endswith('.pdf'):
        messagebox.showerror("格式錯誤", "請拖曳 PDF 檔案！")
        return

    label_status.config(text="轉換中，請稍候...", fg="blue")
    root.update()

    try:
        converter = PDFtoEPUBConverter()
        output_path = converter.convert(file_path)
        label_status.config(text=f"轉換成功！\n已儲存至:\n{output_path}", fg="green")
    except Exception as e:
        label_status.config(text="轉換失敗", fg="red")
        messagebox.showerror("錯誤", f"轉換過程發生錯誤:\n{str(e)}")

# 建立圖形化介面
root = TkinterDnD.Tk()
root.title("PDF 轉 EPUB 智能轉換器")
root.geometry("400x250")
root.config(bg="#f0f0f0")

frame = tk.Frame(root, bg="#e0e0e0", bd=2, relief="sunken")
frame.pack(padx=20, pady=20, fill="both", expand=True)

label_inst = tk.Label(frame, text="請將 PDF 論文拖曳至此處", bg="#e0e0e0", font=("Arial", 14, "bold"))
label_inst.pack(expand=True)

label_status = tk.Label(frame, text="準備就緒", bg="#e0e0e0", font=("Arial", 10))
label_status.pack(side="bottom", pady=10)

# 註冊拖放事件
frame.drop_target_register(DND_FILES)
frame.dnd_bind('<<Drop>>', on_drop)

# 啟動應用程式
root.mainloop()
