import os
import json
import asyncio
from typing import Dict, List, Any
from openai import AsyncOpenAI
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# OpenAI client yaratish
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_presentation_content(topic: str, pages: int) -> Dict[str, Any]:
    """
    OpenAI yordamida taqdimot kontentini yaratish
    
    Args:
        topic: Taqdimot mavzusi
        pages: Sahifalar soni
    
    Returns:
        Dict: Yaratilgan kontent
    """
    
    try:
        # Prompt yaratish
        prompt = f"""
Siz professional taqdimotlar yaratish bo'yicha mutaxassissiz. 
Quyidagi mavzu bo'yicha {pages} sahifali taqdimot kontentini yarating:

Mavzu: {topic}

Taqdimot strukturasi:
1. Title slide (mavzu va sana)
2. Kirish (mavzu haqida umumiy ma'lumot)
3. Asosiy qismlar (3-5 ta slide)
4. Xulosa (asosiy fikrlar)
5. Rahmat (yakunlovchi slide)

Har bir slide uchun:
- Title: Qisqa va aniq sarlavha
- Content: 3-5 ta asosiy nuqta yoki paragraf

JSON formatida qaytaring:
{{
    "title": "Taqdimot sarlavhasi",
    "slides": [
        {{
            "title": "Slide sarlavhasi",
            "content": "Slide matni yoki ro'yxat"
        }}
    ]
}}

Muhim: Faqat JSON formatida javob bering, boshqa matn qo'shmang.
"""
        
        # OpenAI API ga so'rov yuborish
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "Siz professional taqdimotlar yaratish bo'yicha mutaxassissiz. Faqat JSON formatida javob bering."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        # Javobni olish
        content = response.choices[0].message.content.strip()
        
        # JSON ni parse qilish
        try:
            # Agar content ```json bilan boshlansa
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            parsed_content = json.loads(content)
            return parsed_content
            
        except json.JSONDecodeError as e:
            print(f"JSON parse xatoligi: {e}")
            print(f"Content: {content}")
            
            # Fallback: oddiy kontent yaratish
            return create_fallback_content(topic, pages)
            
    except Exception as e:
        print(f"OpenAI API xatoligi: {e}")
        # Fallback: oddiy kontent yaratish
        return create_fallback_content(topic, pages)


def create_fallback_content(topic: str, pages: int) -> Dict[str, Any]:
    """
    OpenAI ishlamasa fallback kontent yaratish
    
    Args:
        topic: Taqdimot mavzusi
        pages: Sahifalar soni
    
    Returns:
        Dict: Fallback kontent
    """
    
    slides = []
    
    # 1. Title slide
    slides.append({
        "title": topic,
        "content": f"AI yordamida yaratilgan taqdimot\n{pages} sahifa"
    })
    
    # 2. Kirish
    slides.append({
        "title": "Kirish",
        "content": f"{topic} haqida umumiy ma'lumot va taqdimot maqsadi."
    })
    
    # 3. Asosiy qismlar
    main_slides = min(pages - 3, 4)  # Title, kirish va xulosa dan tashqari
    
    for i in range(main_slides):
        slides.append({
            "title": f"Asosiy qism {i + 1}",
            "content": f"{topic} ning {i + 1}-qismi haqida batafsil ma'lumot."
        })
    
    # 4. Xulosa
    slides.append({
        "title": "Xulosa",
        "content": f"{topic} bo'yicha asosiy fikrlar va natijalar."
    })
    
    return {
        "title": topic,
        "slides": slides
    }


async def generate_simple_content(topic: str) -> str:
    """
    Oddiy kontent yaratish (fallback)
    
    Args:
        topic: Mavzu
    
    Returns:
        str: Yaratilgan kontent
    """
    
    try:
        prompt = f"""
Quyidagi mavzu haqida qisqa va aniq ma'lumot bering:

Mavzu: {topic}

Til: O'zbek tili
Uzunlik: 200-300 so'z
Format: Oddiy matn
"""
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "Siz ma'lumot berish bo'yicha mutaxassissiz. O'zbek tilida javob bering."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"OpenAI API xatoligi: {e}")
        return f"{topic} haqida ma'lumot. Bu mavzu bo'yicha batafsil taqdimot tayyorlash mumkin."


async def test_openai_connection() -> bool:
    """
    OpenAI API ulanishini tekshirish
    
    Returns:
        bool: Ulanish holati
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user", 
                    "content": "Salom"
                }
            ],
            max_tokens=10
        )
        
        return True
        
    except Exception as e:
        print(f"OpenAI API test xatoligi: {e}")
        return False
