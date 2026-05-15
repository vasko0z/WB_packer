#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для создания транспортной этикетки с новым форматом
"""

import sys
import io
import os
import tempfile
from PyQt6.QtWidgets import QApplication
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def create_test_transport_label():
    """Создает тестовую транспортную этикетку с новым форматом"""
    
    # Попробуем использовать шрифт, который поддерживает кириллицу
    font_name_regular = 'Helvetica'
    font_name_bold = 'Helvetica-Bold'
    
    try:
        font_path = None
        possible_fonts = [
            "arial.ttf", "Arial.ttf", "ARIAL.TTF",
            "LiberationSans-Regular.ttf", "DejaVuSans.ttf",
            "calibri.ttf", "Calibri.ttf", "CALIBRI.TTF"
        ]
        
        for font_name in possible_fonts:
            if os.path.exists(font_name):
                font_path = font_name
                break
            system_font_paths = [
                r"C:\Windows\Fonts\\" + font_name,
                r"/usr/share/fonts/truetype/dejavu/" + font_name,
                r"/System/Library/Fonts/" + font_name
            ]
            for path in system_font_paths:
                if os.path.exists(path):
                    font_path = path
                    break
            if font_path:
                break
        
        if font_path:
            pdfmetrics.registerFont(TTFont('CyrillicRegular', font_path))
            font_name_regular = 'CyrillicRegular'
            
            bold_font_path = None
            possible_bold_fonts = [
                font_path.replace('.ttf', ' Bold.ttf').replace('.TTF', ' Bold.TTF'),
                font_path.replace('Regular', 'Bold'),
                font_path.replace('regular', 'bold'),
                "arialbd.ttf", "Arial Bold.ttf", "ARIALBD.TTF",
                "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"
            ]
            
            for bold_path in possible_bold_fonts:
                if os.path.exists(bold_path):
                    bold_font_path = bold_path
                    break
                for path in system_font_paths:
                    if 'Fonts' in path:
                        bold_sys_path = path.replace(os.path.basename(path), os.path.basename(bold_path))
                        if os.path.exists(bold_sys_path):
                            bold_font_path = bold_sys_path
                            break
                if bold_font_path:
                    break
            
            if bold_font_path:
                pdfmetrics.registerFont(TTFont('CyrillicBold', bold_font_path))
                font_name_bold = 'CyrillicBold'
            else:
                font_name_bold = 'CyrillicRegular'
    except:
        pass
    
    buffer = io.BytesIO()
    # Стандартный размер этикетки 58x40 мм
    c = canvas.Canvas(buffer, pagesize=(58*mm, 40*mm))
    
    # Центрируем весь контент по вертикали
    # Общая высота содержимого: название (2 строки) + отступ + "Коробка" + отступ + номер
    # Примерно: 12pt + 12pt + 5mm + 12pt + 5mm + 24pt = ~60mm
    # Центральная позиция для вертикального центрирования
    
    # Рисуем название направления (Поставка) - крупный шрифт, центрировано
    c.setFont(font_name_bold, 14)
    dest_text = "Москва"
    
    # Если название слишком длинное, уменьшаем шрифт
    if len(dest_text) > 16:
        c.setFont(font_name_bold, 12)
    if len(dest_text) > 20:
        c.setFont(font_name_bold, 10)
        
    c.drawCentredString(29*mm, 28*mm, dest_text)
    
    # Отступ
    
    # Рисуем "Коробка" - средний шрифт
    c.setFont(font_name_regular, 12)
    c.drawCentredString(29*mm, 18*mm, "Коробка")
    
    # Рисуем номер коробки - крупный шрифт
    c.setFont(font_name_bold, 20)
    box_num = "3"
    
    c.drawCentredString(29*mm, 8*mm, box_num)
    
    c.save()
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Сохраняем в файл
    test_pdf_path = "test_transport_label.pdf"
    with open(test_pdf_path, 'wb') as f:
        f.write(pdf_data)
    
    print(f"✅ Тестовая транспортная этикетка создана: {test_pdf_path}")
    return test_pdf_path

if __name__ == "__main__":
    app = QApplication(sys.argv)  # Необходим для некоторых операций PDF
    pdf_path = create_test_transport_label()
    print(f"Файл сохранен как: {pdf_path}")