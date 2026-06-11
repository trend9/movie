import os
import sys

# Reconfigure stdout/stderr to support UTF-8 on Windows and avoid UnicodeEncodeErrors
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

import re
import json
import time
import base64
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont

# Import MoviePy safely
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.video.io.ImageClip import ImageClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.video.compositing.concat import concatenate_videoclips

# Directories
TEMP_DIR = "temp_action"
OUTPUT_DIR = "output_action"
DATA_DIR = "data"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# File paths
FONT_JA_PATH = os.path.join(TEMP_DIR, "NotoSansJP-Bold.otf")
FONT_TH_PATH = os.path.join(TEMP_DIR, "NotoSansThai-Bold.ttf")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# VoiceVox Speaker IDs (Excluding Zundamon: 1, 3, 5, 7, 22, 38)
# We cycle through different characters for each page
VOICEVOX_SPEAKERS = [
    2,  # 四国めたん (Normal)
    8,  # 春日部つむぎ (Normal)
    10, # 雨晴はう (Normal)
    14, # 冥鳴ひまり (Normal)
    16, # 九州そら (Normal)
    20, # 京町セイカ (Normal)
    29, # 東北きりたん (Normal)
    43, # 読谷山しずく (Normal)
    47, # 東北ずん子 (Normal)
    54, # 東北イタコ (Normal)
    0   # 四国めたん (Sweet)
]

# Collection of Fallback Datasets to ensure different topics are used when LLM is offline (Strictly Hiragana)
FALLBACK_DATASETS = [
    # Topic 1: Greetings (にちじょうのあいさつ)
    [
        {"japanese": "にちじょうのあいさつ", "thai": "คำทักทายในชีวิตประจำวัน"},
        {"japanese": "こんにちは", "thai": "สวัสดี"},
        {"japanese": "ありがとう", "thai": "ขอบคุณ"},
        {"japanese": "すみません", "thai": "ขอโทษ"},
        {"japanese": "おはよう", "thai": "อรุณสวัสดิ์"},
        {"japanese": "こんばんは", "thai": "สวัสดีตอนเย็น"},
        {"japanese": "おやすみ", "thai": "ราตรีสวัสดิ์"},
        {"japanese": "またね", "thai": "แล้วเจอกัน"},
        {"japanese": "おげんきですか", "thai": "สบายดีไหม"},
        {"japanese": "はじめまして", "thai": "ยินดีที่ได้รู้จัก"},
        {"japanese": "さようなら", "thai": "ลาก่อน"},
        {"japanese": "おめでとう", "thai": "ยินดีด้วย"}
    ],
    # Topic 2: Colors (いろのひょうげん)
    [
        {"japanese": "いろのひょうげん", "thai": "คำศัพท์เกี่ยวกับสี"},
        {"japanese": "あか", "thai": "แดง"},
        {"japanese": "あお", "thai": "น้ำเงิน"},
        {"japanese": "きいろ", "thai": "เหลือง"},
        {"japanese": "みどり", "thai": "เขียว"},
        {"japanese": "しろ", "thai": "ขาว"},
        {"japanese": "くろ", "thai": "ดำ"},
        {"japanese": "ちゃいろ", "thai": "น้ำตาล"},
        {"japanese": "ぴんく", "thai": "ชมพู"},
        {"japanese": "むらさき", "thai": "ม่วง"},
        {"japanese": "おれんじ", "thai": "ส้ม"},
        {"japanese": "はいいろ", "thai": "เทา"}
    ],
    # Topic 3: Fruits (くだもののなまえ)
    [
        {"japanese": "くだもののなまえ", "thai": "ชื่อผลไม้"},
        {"japanese": "りんご", "thai": "แอปเปิ้ล"},
        {"japanese": "みかん", "thai": "ส้ม"},
        {"japanese": "いちご", "thai": "สตรอเบอร์รี่"},
        {"japanese": "ばなな", "thai": "กล้วย"},
        {"japanese": "ぶどう", "thai": "องุ่น"},
        {"japanese": "すいか", "thai": "แตงโม"},
        {"japanese": "もも", "thai": "ลูกท้อ"},
        {"japanese": "めろん", "thai": "เมลอน"},
        {"japanese": "ぱいなっぷる", "thai": "สับปะรด"},
        {"japanese": "まんごー", "thai": "มะม่วง"},
        {"japanese": "ここなっつ", "thai": "มะพร้าว"}
    ],
    # Topic 4: Numbers (すうじのひょうげん)
    [
        {"japanese": "すうじのひょうげん", "thai": "ตัวเลขและการนับ"},
        {"japanese": "いち", "thai": "หนึ่ง"},
        {"japanese": "に", "thai": "สอง"},
        {"japanese": "さん", "thai": "สาม"},
        {"japanese": "よん", "thai": "สี่"},
        {"japanese": "ご", "thai": "ห้า"},
        {"japanese": "ろく", "thai": "หก"},
        {"japanese": "なな", "thai": "เจ็ด"},
        {"japanese": "はち", "thai": "แปด"},
        {"japanese": "きゅう", "thai": "เก้า"},
        {"japanese": "じゅう", "thai": "สิบ"},
        {"japanese": "ひゃく", "thai": "ร้อย"}
    ],
    # Topic 5: Useful Daily Phrases (べんりなことば)
    [
        {"japanese": "べんりなことば", "thai": "คำศัพท์ภาษาญี่ปุ่นที่มีประโยชน์"},
        {"japanese": "はい", "thai": "ใช่ / ครับ / ค่ะ"},
        {"japanese": "いいえ", "thai": "ไม่ / ไม่ใช่"},
        {"japanese": "おいしい", "thai": "อร่อย"},
        {"japanese": "いくらですか", "thai": "ราคาเท่าไหร่"},
        {"japanese": "だいじょうぶ", "thai": "ไม่เป็นไร"},
        {"japanese": "わかりました", "thai": "เข้าใจแล้ว"},
        {"japanese": "わかりません", "thai": "ไม่เข้าใจ"},
        {"japanese": "もういちど", "thai": "อีกครั้งหนึ่ง"},
        {"japanese": "てつだって", "thai": "ช่วยหน่อย"},
        {"japanese": "だいすきです", "thai": "ชอบมาก"},
        {"japanese": "がんばって", "thai": "สู้ๆ นะ"}
    ]
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "used_titles" not in data:
                    data["used_titles"] = []
                if "used_words" not in data:
                    data["used_words"] = []
                if "videos" not in data:
                    data["videos"] = []
                return data
        except Exception:
            pass
    return {"used_titles": [], "used_words": [], "videos": []}

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving history: {e}")

def download_file(url, output_path):
    print(f"Downloading: {url} -> {output_path}")
    response = requests.get(url, stream=True, timeout=30)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    else:
        print(f"Failed to download. Status code: {response.status_code}")
        return False

def ensure_fonts():
    """Downloads Japanese and Thai fonts if they are not already cached."""
    # Noto Sans JP (OTF)
    if not os.path.exists(FONT_JA_PATH) or os.path.getsize(FONT_JA_PATH) < 100000:
        url_ja = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf"
        try:
            download_file(url_ja, FONT_JA_PATH)
        except Exception as e:
            print(f"Error downloading Japanese font: {e}")
            
    # Noto Sans Thai (TTF) - Using jsDelivr npm package for Noto Sans Thai to prevent corrupt downloads
    if not os.path.exists(FONT_TH_PATH) or os.path.getsize(FONT_TH_PATH) < 50000:
        url_th = "https://cdn.jsdelivr.net/npm/@electron-fonts/noto-sans-thai/fonts/NotoSansThai-Bold.ttf"
        try:
            download_file(url_th, FONT_TH_PATH)
        except Exception as e:
            pass

def is_pure_hiragana(text):
    # Matches only Hiragana (ぁ-ん), long vowel sign (ー), and spaces
    return bool(re.match(r"^[\u3040-\u309F\u30FC\s]+$", text))

def is_valid_content(data, history):
    if not isinstance(data, list) or len(data) != 12:
        print("Validation failed: Content is not a list of 12 items.")
        return False
    
    title = data[0].get("japanese", "").strip()
    if not title:
        print("Validation failed: Title is empty.")
        return False
        
    # Check title format (Hiragana only)
    if not is_pure_hiragana(title):
        print(f"Validation failed: Title '{title}' contains non-hiragana characters.")
        return False
        
    # Check title duplicate
    if title in history.get("used_titles", []):
        print(f"Validation failed: Title '{title}' is already used.")
        return False
        
    # Check all slide items
    used_words_set = set(history.get("used_words", []))
    duplicate_words_count = 0
    
    for idx, item in enumerate(data[1:]):
        word = item.get("japanese", "").strip()
        thai = item.get("thai", "").strip()
        
        if not word or not thai:
            print(f"Validation failed: Slide {idx+2} has empty japanese or thai text.")
            return False
            
        # Check Hiragana only
        if not is_pure_hiragana(word):
            print(f"Validation failed: Slide {idx+2} word '{word}' contains non-hiragana characters.")
            return False
            
        # Check word length (must be at least 2 characters to avoid single character junk/fragments)
        if len(word) < 2:
            print(f"Validation failed: Slide {idx+2} word '{word}' is too short.")
            return False
            
        # Check duplicate
        if word in used_words_set:
            duplicate_words_count += 1
            
    if duplicate_words_count >= 3:
        print(f"Validation failed: Too many duplicate words ({duplicate_words_count} words matched history).")
        return False
        
    return True

def generate_text_content(history):
    """Generates 12 pages of Japanese + Thai translation content, avoiding duplicate topics/phrases."""
    print("Generating 12 pages of content...")
    
    # Extract history to avoid duplicates
    avoid_titles = ", ".join(history["used_titles"][-25:])
    avoid_words = ", ".join(history["used_words"][-100:])
    
    system_prompt = (
        "You are an assistant that outputs ONLY raw JSON. Do not write markdown, code blocks, or preamble. "
        "The output must be a JSON array containing exactly 12 items. "
        "Each item in the array must be an object with keys: 'japanese' and 'thai'. "
        "CRITICAL: All Japanese output (including the title and all words) MUST be strictly written in Hiragana only. Do NOT use Kanji, Katakana, Romaji, or any other script. For example, use 'きいろ' instead of '黄色' or 'キイロ'."
        "The first item is the title of the video. The title MUST be a natural, common category of basic Japanese vocabulary or conversation suitable for beginners, 10 characters or less (e.g. 'にちじょうのあいさつ', 'くだもののなまえ', 'いろのひょうげん', 'べんりなことば', 'じこしょうかい'). "
        "Items 2 to 12 must be standard, common, and 100% correct Japanese words or expressions that belong strictly to that title's category, written in Hiragana. "
        "CRITICAL: Do NOT invent nonsense compound words or weird phrases (e.g. if the category is Colors, do NOT write 'あかちゃん の いろ' or 'しゅみ の いろ' or 'たべもの の いろ' - only use standard colors like 'あか', 'あお', 'きいろ', 'みどり', 'しろ', 'くろ', 'ちゃいろ', 'ぴんく', 'むらさき', 'おれんじ', 'はいいろ'). All Japanese words must be real and widely used in Japan daily. "
        "This is for Thai people learning basic/daily Japanese, so the content must be highly practical and natural. "
        "IMPORTANT: Do NOT include any phonetic romanizations or readings in brackets in the Thai translations (e.g. do NOT write 'สวัสดี (Sawatdee)' or 'ขอบคุณ (Khob khun)'). The Thai text must contain ONLY native Thai script."
    )
    
    user_prompt = (
        "Generate 12 items matching the system prompt instructions.\n"
        f"IMPORTANT: You MUST NOT repeat or use any of these previously generated titles: [{avoid_titles}].\n"
        f"You MUST NOT repeat or use any of these previously generated Japanese phrases/words: [{avoid_words}].\n"
        "Please choose a completely new category and new vocabulary words. Generate entirely new and fresh content in Hiragana only."
    )
    
    local_api_url = os.environ.get("LOCAL_API_URL") or "http://127.0.0.1:8000"
    
    # Try up to 5 times to generate unique content
    for attempt in range(5):
        print(f"Generation attempt {attempt + 1}/5...")
        
        # 1. Try local Ollama/API server if configured
        print(f"Trying LLM generation via local server: {local_api_url} ...")
        try:
            payload = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt
            }
            res = requests.post(f"{local_api_url}/generate/text", json=payload, timeout=90)
            if res.status_code == 200:
                text = res.json().get("result", "").strip()
                text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
                data = json.loads(text)
                if isinstance(data, list) and len(data) == 12:
                    if len(data[0]["japanese"]) > 10:
                        data[0]["japanese"] = data[0]["japanese"][:10]
                    
                    if is_valid_content(data, history):
                        print(f"Successfully generated unique 12 slides from local server.")
                        return data
        except Exception as e:
            print(f"Local server LLM request failed on attempt {attempt + 1}: {e}")
    
        # 2. Try Pollinations text API fallback
        print("Trying Pollinations Text API fallback...")
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "model": "openai"
            }
            response = requests.post("https://text.pollinations.ai", json=payload, timeout=45)
            if response.status_code == 200:
                text = response.text.strip()
                text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
                data = json.loads(text)
                if isinstance(data, list) and len(data) == 12:
                    if len(data[0]["japanese"]) > 10:
                        data[0]["japanese"] = data[0]["japanese"][:10]
                    
                    if is_valid_content(data, history):
                        print(f"Successfully generated unique 12 slides from Pollinations.")
                        return data
        except Exception as e:
            print(f"Pollinations Text API fallback failed on attempt {attempt + 1}: {e}")
            
    print("Could not generate unique content via LLM after 5 attempts. Using fallback datasets...")
    # Filter datasets that have not been used yet
    unused_datasets = [ds for ds in FALLBACK_DATASETS if ds[0]["japanese"] not in history.get("used_titles", [])]
    if unused_datasets:
        print(f"Selecting unused fallback dataset: {unused_datasets[0][0]['japanese']}")
        return unused_datasets[0]
        
    # All fallback datasets have been used. Let's find the one that was used the furthest in the past.
    print("All fallback datasets are used. Selecting the oldest used dataset...")
    oldest_index = 999999
    selected_dataset = FALLBACK_DATASETS[0]
    for ds in FALLBACK_DATASETS:
        title = ds[0]["japanese"]
        try:
            idx = history.get("used_titles", []).index(title)
        except ValueError:
            idx = -1
        if idx != -1 and idx < oldest_index:
            oldest_index = idx
            selected_dataset = ds
    print(f"Selected oldest fallback dataset: {selected_dataset[0]['japanese']}")
    return selected_dataset

def get_font(lang, size):
    """Returns the loaded font depending on the language."""
    if lang == "en":
        # Latin/English characters are supported by Noto Sans JP
        if os.path.exists(FONT_JA_PATH):
            try:
                return ImageFont.truetype(FONT_JA_PATH, size)
            except Exception:
                pass
        paths = ["C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\arial.ttf"]
        for p in paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
    elif lang == "ja" and os.path.exists(FONT_JA_PATH):
        try:
            return ImageFont.truetype(FONT_JA_PATH, size)
        except Exception:
            pass
    elif lang == "th" and os.path.exists(FONT_TH_PATH):
        try:
            return ImageFont.truetype(FONT_TH_PATH, size)
        except Exception:
            pass
            
    # Fallbacks for local environment
    paths = []
    if lang == "ja":
        paths = ["C:\\Windows\\Fonts\\meiryo.ttc", "C:\\Windows\\Fonts\\yuGothM.ttc"]
    elif lang == "th":
        paths = ["C:\\Windows\\Fonts\\leelawad.ttc", "C:\\Windows\\Fonts\\tahoma.ttf"]
        
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
                
    return ImageFont.load_default()

    print("Trying Pollinations Text API fallback...")
    try:
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "model": "openai"
        }
        response = requests.post("https://text.pollinations.ai", json=payload, timeout=45)
        if response.status_code == 200:
            text = response.text.strip()
            text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
            data = json.loads(text)
            if isinstance(data, list) and len(data) == 12:
                if len(data[0]["japanese"]) > 10:
                    data[0]["japanese"] = data[0]["japanese"][:10]
                print(f"Successfully generated 12 slides from Pollinations.")
                return data
    except Exception as e:
        print(f"Pollinations Text API fallback failed: {e}")
        
    # Filter datasets that have not been used yet
    unused_datasets = [ds for ds in FALLBACK_DATASETS if ds[0]["japanese"] not in history["used_titles"]]
    if not unused_datasets:
        selected_dataset = FALLBACK_DATASETS[int(time.time()) % len(FALLBACK_DATASETS)]
        print(f"All fallback datasets used. Selecting: {selected_dataset[0]['japanese']}")
    else:
        selected_dataset = unused_datasets[0]
        print(f"Selecting unused fallback dataset: {selected_dataset[0]['japanese']}")
    return selected_dataset

def translate_title_to_image_prompt(title_japanese):
    """Translates the Japanese title to a highly relevant English description for the image generation prompt."""
    url = "https://text.pollinations.ai"
    system_prompt = (
        "You translate a Japanese phrase to a highly descriptive English scene for AI image generation. "
        "The scene must be cute, colorful, and appeal to young women. "
        "For example, if the input is '日常の日本語' (Everyday Japanese), output 'A cute cozy study room, pastel pink and lavender, cute stationery, a tiny cute notebook, soft lighting'. "
        "Keep the description short, clean, and visual. Output ONLY the English description, no other text."
    )
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": title_japanese}
        ],
        "model": "openai"
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200 and response.text.strip():
            desc = response.text.strip()
            print(f"Translated title prompt description: {desc}")
            return desc
    except Exception as e:
        print(f"Error translating title for prompt: {e}")
    return "A cute cozy room with books and soft pastel pink lighting"

def crop_to_9_16(img_path):
    """Crops an image centered to 9:16 aspect ratio and resizes to 720x1280."""
    try:
        with Image.open(img_path) as img:
            width, height = img.size
            target_ratio = 9 / 16
            current_ratio = width / height
            
            if current_ratio > target_ratio:
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                img_cropped = img.crop((left, 0, left + new_width, height))
            else:
                new_height = int(width / target_ratio)
                top = (height - new_height) // 2
                img_cropped = img.crop((0, top, width, top + new_height))
                
            img_resized = img_cropped.resize((720, 1280), Image.Resampling.LANCZOS)
            img_resized.convert("RGB").save(img_path, "JPEG")
            print(f"Image cropped and resized to 720x1280 successfully: {img_path}")
            return True
    except Exception as e:
        print(f"Error cropping image: {e}")
        return False

def generate_background_image(title_japanese, output_path):
    """Generates a stunning 9:16 background image using local LCM server or online fallbacks."""
    print(f"Generating background image matching title: '{title_japanese}'...")
    scene_description = translate_title_to_image_prompt(title_japanese)
    
    # 1. Try Local API Server LCM model (matching wall project)
    local_api_url = os.environ.get("LOCAL_API_URL") or "http://127.0.0.1:8000"
    print(f"Trying Local API Server for image generation: {local_api_url} ...")
    try:
        payload = {
            "prompt": f"{scene_description}, cute pastel colors, soft lighting, vertical 9:16 aesthetic, anime/watercolor style, charming, high resolution",
            "width": 512,
            "height": 512
        }
        res = requests.post(f"{local_api_url}/generate/image", json=payload, timeout=90)
        if res.status_code == 200:
            base64_str = res.json().get("image_base64")
            if base64_str:
                img_data = base64.b64decode(base64_str)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                print("Successfully generated background image from Local LCM.")
                crop_to_9_16(output_path)
                return True
    except Exception as e:
        print(f"Local server image generation failed: {e}")

    # 2. Try Hugging Face Inference API fallback
    hf_token = os.environ.get("HF_TOKEN", "")
    model = "black-forest-labs/FLUX.1-schnell"
    hf_url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
    enhanced_prompt = f"beautiful vertical aesthetic scenery of: {scene_description}, cute pastel room, soft lighting, watercolor art style, photorealistic, 8k resolution"
    
    print(f"Trying Hugging Face Inference API ({model}) fallback...")
    try:
        response = requests.post(hf_url, headers=headers, json={"inputs": enhanced_prompt}, timeout=45)
        if response.status_code == 200 and len(response.content) > 2000:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print("Successfully generated background image from Hugging Face.")
            crop_to_9_16(output_path)
            return True
    except Exception as e:
        print(f"Hugging Face request failed: {e}")
        
    # 3. Try Pollinations AI fallback
    print("Trying Pollinations AI fallback...")
    prompt = f"{scene_description}, cute pastel colors, soft lighting, portrait 9:16 aspect ratio, aesthetic photography, watercolor anime style, high resolution, 8k"
    encoded_prompt = urllib.parse.quote(prompt)
    seed = int(time.time()) % 10000
    pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&seed={seed}&model=flux"
    
    try:
        response = requests.get(pollinations_url, timeout=30)
        if response.status_code == 200 and len(response.content) > 2000:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print("Successfully generated background image from Pollinations.")
            crop_to_9_16(output_path)
            return True
    except Exception as e:
        print(f"Pollinations request failed: {e}")
        
    # 4. Local gradient fallback
    print("Falling back to local gradient background generation...")
    img = Image.new("RGB", (720, 1280), color=(45, 20, 35))
    draw = ImageDraw.Draw(img)
    for y in range(1280):
        r = int(255 * (1 - y / 1280) + 240 * (y / 1280))
        g = int(192 * (1 - y / 1280) + 210 * (y / 1280))
        b = int(203 * (1 - y / 1280) + 225 * (y / 1280))
        draw.line([(0, y), (720, y)], fill=(r, g, b))
    img.save(output_path, "JPEG")
    return True

def generate_voicevox_audio(text, speaker_id, output_path):
    """Fetches Japanese narration using TTS Quest VOICEVOX Web API (free)."""
    print(f"Requesting voice for: '{text}' (Speaker ID: {speaker_id})...")
    encoded_text = urllib.parse.quote(text)
    url = f"https://api.tts.quest/v3/voicevox/synthesis?text={encoded_text}&speaker={speaker_id}"
    
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("success"):
                audio_status_url = res_json.get("audioStatusUrl")
                wav_url = res_json.get("wavDownloadUrl")
                
                # Poll status.json until ready (isAudioReady = True)
                for attempt in range(20):
                    status_resp = requests.get(audio_status_url, timeout=10)
                    if status_resp.status_code == 200:
                        status_json = status_resp.json()
                        if status_json.get("isAudioReady"):
                            if download_file(wav_url, output_path):
                                return True
                        elif status_json.get("isAudioError"):
                            break
                    time.sleep(2.5)
    except Exception as e:
        print(f"Error during VoiceVox generation: {e}")
        
    # Fallback to gTTS if VOICEVOX fails
    print("Falling back to gTTS...")
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='ja')
        tts.save(output_path)
        return True
    except Exception as ex:
        print(f"gTTS fallback failed: {ex}")
        return False

def wrap_text_to_lines(draw, text, font, max_width):
    lines = []
    words = list(text)
    current_line = []
    for word in words:
        current_line.append(word)
        test_line = "".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width:
            current_line.pop()
            lines.append("".join(current_line))
            current_line = [word]
    if current_line:
        lines.append("".join(current_line))
    return lines

def measure_block_height(draw, lines, font, line_spacing=10):
    if not lines:
        return 0
    total_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        total_h += (h if h > 0 else 30) + line_spacing
    return total_h - line_spacing

def draw_block_text(draw, lines, font, fill_color, start_y, image_width, line_spacing=10):
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (image_width - w) // 2
        # Drop shadow
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
        # Main text
        draw.text((x, y), line, font=font, fill=fill_color)
        y += (h if h > 0 else 30) + line_spacing
    return y

def make_slide_image(bg_path, japanese, thai, domain_text, output_path):
    """Draws centered stacked texts over the background image inside a safe-zone card."""
    img = Image.open(bg_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Load fonts (Optimized sizes for cute, readable vertical layout)
    font_ja = get_font("ja", 48)
    font_th = get_font("th", 38)
    font_en = get_font("en", 56)  # Set to a very large 56px for high visibility
    
    max_text_width = width - 120
    
    lines_ja = wrap_text_to_lines(draw, japanese, font_ja, max_text_width)
    lines_th = wrap_text_to_lines(draw, thai, font_th, max_text_width)
    lines_en = wrap_text_to_lines(draw, domain_text, font_en, max_text_width)
    
    h_ja = measure_block_height(draw, lines_ja, font_ja)
    h_th = measure_block_height(draw, lines_th, font_th)
    h_en = measure_block_height(draw, lines_en, font_en)
    
    block_gap = 30
    padding_y = 55
    
    total_content_height = h_ja + block_gap + h_th + block_gap + h_en
    total_card_height = total_content_height + (padding_y * 2)
    
    card_y_start = (height - total_card_height) // 2
    
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # Cute, soft pink/lavender tinted semi-transparent box
    card_x_start = 45
    card_x_end = width - 45
    card_y_end = card_y_start + total_card_height
    
    draw_overlay.rounded_rectangle(
        [card_x_start, card_y_start, card_x_end, card_y_end], 
        fill=(40, 20, 30, 180), 
        radius=28
    )
    
    # Cute pastel-pink card border
    draw_overlay.rounded_rectangle(
        [card_x_start, card_y_start, card_x_end, card_y_end], 
        outline=(255, 192, 203, 120), 
        width=3, 
        radius=28
    )
    
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    current_y = card_y_start + padding_y
    # Japanese: Vibrant Gold/Yellow
    current_y = draw_block_text(draw, lines_ja, font_ja, (255, 223, 85, 255), current_y, width)
    current_y += block_gap
    # Thai: Pure White
    current_y = draw_block_text(draw, lines_th, font_th, (255, 255, 255, 255), current_y, width)
    current_y += block_gap
    # Domain: Vibrant Light Pink for cute brand styling
    draw_block_text(draw, lines_en, font_en, (255, 160, 190, 255), current_y, width)
    
    img.convert("RGB").save(output_path, "JPEG")
    print(f"Slide image saved to: {output_path}")

def main():
    print("=== Automatic Video Generation Action ===")
    
    # 1. Download fonts
    ensure_fonts()
    
    # 2. Load history & Get content (12 pages)
    history = load_history()
    slides = generate_text_content(history)
    
    # 3. Generate background image based on the title (slide 1 Japanese)
    title_text = slides[0]["japanese"]
    bg_image_path = os.path.join(TEMP_DIR, "bg_shared.jpg")
    generate_background_image(title_text, bg_image_path)
    
    clips = []
    temp_media = []
    
    # 4. Generate slides media (images + voices)
    for idx, slide in enumerate(slides):
        num = idx + 1
        print(f"\n--- Slide {num}/12 ---")
        print(f"JA: {slide['japanese']}")
        print(f"TH: {slide['thai']}")
        
        slide_img_path = os.path.join(TEMP_DIR, f"slide_{num}.jpg")
        voice_path = os.path.join(TEMP_DIR, f"voice_{num}.mp3")
        temp_media.extend([slide_img_path, voice_path])
        
        # Create text overlay image
        make_slide_image(bg_image_path, slide["japanese"], slide["thai"], "yui-yuto.com", slide_img_path)
        
        # Cycle through different Zundamon-free voice characters
        speaker_id = VOICEVOX_SPEAKERS[(num - 1) % len(VOICEVOX_SPEAKERS)]
        generate_voicevox_audio(slide["japanese"], speaker_id=speaker_id, output_path=voice_path)
        
        # Audio length check
        audio_dur = 3.5
        if os.path.exists(voice_path):
            try:
                audio_clip = AudioFileClip(voice_path)
                audio_dur = audio_clip.duration
            except Exception as e:
                print(f"Could not read audio duration: {e}")
                audio_clip = None
        else:
            audio_clip = None
            
        target_dur = 4.0 if num == 1 else 3.5
        clip_dur = max(target_dur, audio_dur)
        
        img_clip = ImageClip(slide_img_path).set_duration(clip_dur)
        if audio_clip:
            img_clip = img_clip.set_audio(audio_clip)
            
        clips.append(img_clip)
        
    # 5. Concatenate and produce final video
    print("\nConcatenating clips and compiling final video...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    clean_title = re.sub(r'[\\/*?:"<>|]', "", slides[0]["japanese"]).strip().replace(" ", "_")
    output_video_path = os.path.join(OUTPUT_DIR, f"video_{timestamp_str}_{clean_title}.mp4")
    
    final_video.write_videofile(
        output_video_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=os.path.join(TEMP_DIR, "temp-audio.m4a"),
        remove_temp=True
    )
    
    # Close clips
    for clip in clips:
        clip.close()
    final_video.close()
    
    # 6. Save history to avoid duplicate titles/phrases next run
    title_ja = slides[0]["japanese"]
    history["used_titles"].append(title_ja)
    for slide in slides[1:]:
        history["used_words"].append(slide["japanese"])
        
    # Append detailed video record for descriptions
    video_record = {
        "title": title_ja,
        "timestamp": timestamp_str,
        "video_filename": os.path.basename(output_video_path),
        "slides": []
    }
    for idx, slide in enumerate(slides):
        role = "title" if idx == 0 else "content"
        video_record["slides"].append({
            "role": role,
            "japanese": slide["japanese"],
            "thai": slide["thai"]
        })
    history["videos"].append(video_record)
    save_history(history)
    
    # 7. Cleanup temp media
    print("Cleaning up temporary files...")
    for path in temp_media:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    if os.path.exists(bg_image_path):
        try:
            os.remove(bg_image_path)
        except Exception:
            pass
            
    print(f"\nSUCCESS! Video generated at: {output_video_path}")

if __name__ == "__main__":
    main()
