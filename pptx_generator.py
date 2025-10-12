import os
import aiofiles
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from datetime import datetime

async def create_presentation_file(content: dict, topic: str, user_tg_id: int) -> str:
    """
    PowerPoint taqdimot faylini yaratish
    
    Args:
        content: OpenAI dan kelgan kontent
        topic: Taqdimot mavzusi
        user_tg_id: Foydalanuvchi Telegram ID
    
    Returns:
        str: Yaratilgan fayl yo'li
    """
    
    # Yangi taqdimot yaratish
    prs = Presentation()
    
    # Taqdimot o'lchamini 16:9 qilish
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)
    
    # 1. Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    
    # Title
    title = slide.shapes.title
    title.text = topic
    
    # Title styling
    title_frame = title.text_frame
    title_frame.paragraphs[0].font.size = Pt(36)
    title_frame.paragraphs[0].font.bold = True
    title_frame.paragraphs[0].font.color.rgb = RGBColor(44, 62, 80)
    title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    
    # Subtitle
    subtitle = slide.placeholders[1]
    subtitle.text = f"AI yordamida yaratilgan taqdimot\n{datetime.now().strftime('%d.%m.%Y')}"
    
    # Subtitle styling
    subtitle_frame = subtitle.text_frame
    subtitle_frame.paragraphs[0].font.size = Pt(18)
    subtitle_frame.paragraphs[0].font.color.rgb = RGBColor(127, 140, 141)
    subtitle_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    
    # Content slides
    if 'slides' in content:
        for slide_data in content['slides']:
            # Content slide layout
            content_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(content_layout)
            
            # Title
            title = slide.shapes.title
            title.text = slide_data.get('title', 'Slide')
            
            # Title styling
            title_frame = title.text_frame
            title_frame.paragraphs[0].font.size = Pt(28)
            title_frame.paragraphs[0].font.bold = True
            title_frame.paragraphs[0].font.color.rgb = RGBColor(44, 62, 80)
            
            # Content
            content_placeholder = slide.placeholders[1]
            content_frame = content_placeholder.text_frame
            content_frame.clear()
            
            # Content matnini qo'shish
            content_text = slide_data.get('content', '')
            
            # Agar content ro'yxat bo'lsa
            if isinstance(content_text, list):
                for i, item in enumerate(content_text):
                    if i == 0:
                        p = content_frame.paragraphs[0]
                    else:
                        p = content_frame.add_paragraph()
                    
                    p.text = f"• {item}" if isinstance(item, str) else str(item)
                    p.font.size = Pt(20)
                    p.font.color.rgb = RGBColor(52, 73, 94)
                    p.space_after = Pt(12)
            else:
                # Oddiy matn
                p = content_frame.paragraphs[0]
                p.text = content_text
                p.font.size = Pt(20)
                p.font.color.rgb = RGBColor(52, 73, 94)
                p.space_after = Pt(12)
    
    # Agar content da sections bo'lsa
    elif 'sections' in content:
        for section in content['sections']:
            # Section title slide
            title_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(title_layout)
            
            title = slide.shapes.title
            title.text = section.get('title', 'Section')
            
            # Title styling
            title_frame = title.text_frame
            title_frame.paragraphs[0].font.size = Pt(32)
            title_frame.paragraphs[0].font.bold = True
            title_frame.paragraphs[0].font.color.rgb = RGBColor(231, 76, 60)
            
            # Section content slides
            if 'content' in section:
                content_text = section['content']
                
                # Agar content ro'yxat bo'lsa
                if isinstance(content_text, list):
                    for item in content_text:
                        content_layout = prs.slide_layouts[1]
                        slide = prs.slides.add_slide(content_layout)
                        
                        title = slide.shapes.title
                        title.text = item.get('title', 'Slide') if isinstance(item, dict) else str(item)
                        
                        # Title styling
                        title_frame = title.text_frame
                        title_frame.paragraphs[0].font.size = Pt(28)
                        title_frame.paragraphs[0].font.bold = True
                        title_frame.paragraphs[0].font.color.rgb = RGBColor(44, 62, 80)
                        
                        # Content
                        if isinstance(item, dict) and 'content' in item:
                            content_placeholder = slide.placeholders[1]
                            content_frame = content_placeholder.text_frame
                            content_frame.clear()
                            
                            p = content_frame.paragraphs[0]
                            p.text = item['content']
                            p.font.size = Pt(20)
                            p.font.color.rgb = RGBColor(52, 73, 94)
                            p.space_after = Pt(12)
    
    # Agar content da oddiy matn bo'lsa
    else:
        # Content slide
        content_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(content_layout)
        
        title = slide.shapes.title
        title.text = "Asosiy ma'lumot"
        
        # Title styling
        title_frame = title.text_frame
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(44, 62, 80)
        
        # Content
        content_placeholder = slide.placeholders[1]
        content_frame = content_placeholder.text_frame
        content_frame.clear()
        
        # Content matnini qo'shish
        content_text = str(content)
        
        # Matnni paragraf larga bo'lish
        paragraphs = content_text.split('\n')
        for i, para in enumerate(paragraphs):
            if para.strip():
                if i == 0:
                    p = content_frame.paragraphs[0]
                else:
                    p = content_frame.add_paragraph()
                
                p.text = para.strip()
                p.font.size = Pt(20)
                p.font.color.rgb = RGBColor(52, 73, 94)
                p.space_after = Pt(12)
    
    # Fayl nomini yaratish
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_topic = safe_topic.replace(' ', '_')[:30]  # 30 belgigacha qisqartirish
    
    filename = f"slayd_{safe_topic}_{timestamp}.pptx"
    filepath = os.path.join(os.getcwd(), filename)
    
    # Faylni saqlash
    prs.save(filepath)
    
    return filepath


def create_simple_presentation(topic: str, content: str, user_tg_id: int) -> str:
    """
    Oddiy taqdimot yaratish (fallback)
    
    Args:
        topic: Taqdimot mavzusi
        content: Kontent matni
        user_tg_id: Foydalanuvchi Telegram ID
    
    Returns:
        str: Yaratilgan fayl yo'li
    """
    
    # Yangi taqdimot yaratish
    prs = Presentation()
    
    # 1. Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    
    # Title
    title = slide.shapes.title
    title.text = topic
    
    # Title styling
    title_frame = title.text_frame
    title_frame.paragraphs[0].font.size = Pt(36)
    title_frame.paragraphs[0].font.bold = True
    title_frame.paragraphs[0].font.color.rgb = RGBColor(44, 62, 80)
    title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    
    # Subtitle
    subtitle = slide.placeholders[1]
    subtitle.text = f"AI yordamida yaratilgan taqdimot\n{datetime.now().strftime('%d.%m.%Y')}"
    
    # Subtitle styling
    subtitle_frame = subtitle.text_frame
    subtitle_frame.paragraphs[0].font.size = Pt(18)
    subtitle_frame.paragraphs[0].font.color.rgb = RGBColor(127, 140, 141)
    subtitle_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    
    # Content slide
    content_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(content_layout)
    
    title = slide.shapes.title
    title.text = "Asosiy ma'lumot"
    
    # Title styling
    title_frame = title.text_frame
    title_frame.paragraphs[0].font.size = Pt(28)
    title_frame.paragraphs[0].font.bold = True
    title_frame.paragraphs[0].font.color.rgb = RGBColor(44, 62, 80)
    
    # Content
    content_placeholder = slide.placeholders[1]
    content_frame = content_placeholder.text_frame
    content_frame.clear()
    
    # Content matnini qo'shish
    p = content_frame.paragraphs[0]
    p.text = content
    p.font.size = Pt(20)
    p.font.color.rgb = RGBColor(52, 73, 94)
    p.space_after = Pt(12)
    
    # Fayl nomini yaratish
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_topic = safe_topic.replace(' ', '_')[:30]
    
    filename = f"slayd_{safe_topic}_{timestamp}.pptx"
    filepath = os.path.join(os.getcwd(), filename)
    
    # Faylni saqlash
    prs.save(filepath)
    
    return filepath
