import os
import re
import csv
import base64
import time
import requests
from flask import Flask, request, jsonify, send_file, render_template_string
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
import threading

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None


# We import MoviePy components safely
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    # Handle MoviePy 2.x imports
    from moviepy.video.io.ImageClip import ImageClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.video.compositing.concat import concatenate_videoclips

app = Flask(__name__, template_folder='templates')

# Global state to track background generation task
job_status = {
    "status": "idle",
    "progress": 0,
    "logs": []
}

def add_log(message, log_type="info"):
    job_status["logs"].append({
        "time": time.strftime("%H:%M:%S"),
        "message": message,
        "type": log_type
    })
    print(f"[{log_type.upper()}] {message}")

def get_sheet_id(url):
    """Extracts spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    return None

def parse_csv_content(content):
    """Parses CSV text content and extracts A, B, C columns."""
    csv_reader = csv.reader(content.splitlines())
    rows = list(csv_reader)
    
    data = []
    for r in rows[:12]:
        col_a = r[0] if len(r) > 0 else ""
        col_b = r[1] if len(r) > 1 else ""
        col_c = r[2] if len(r) > 2 else ""
        data.append((col_a, col_b, col_c))
    return data

def download_sheet_data(sheet_url):
    """Downloads Google Sheets data as CSV and parses it."""
    sheet_id = get_sheet_id(sheet_url)
    if not sheet_id:
        raise ValueError("無効なスプレッドシートURLです。")
    
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    add_log(f"スプレッドシートからデータを取得中: {csv_url}")
    
    response = requests.get(csv_url)
    if response.status_code != 200:
        raise RuntimeError(
            f"スプレッドシートのダウンロードに失敗しました (Status code: {response.status_code})。\n"
            "スプレッドシートが非公開設定になっています。以下のいずれかでご対応ください：\n"
            "1. スプレッドシートの共有設定を「リンクを知っている全員が閲覧可能」に変更する。\n"
            "2. スプレッドシートで「ファイル」＞「ダウンロード」＞「カンマ区切り形式 (.csv)」を選択してPCに保存し、画面の「CSVファイル選択」から読み込ませる。"
        )
    
    decoded_content = response.content.decode('utf-8')
    data = parse_csv_content(decoded_content)
    add_log(f"スプレッドシートから {len(data)} 行のデータを取得完了。")
    return data

def generate_elegant_gradient(output_path, text_seed):
    """Generates a stunning, premium-looking 9:16 gradient background dynamically (100% free fallback)."""
    palettes = [
        ((31, 41, 234), (147, 51, 234)),  # Indigo to Purple
        ((236, 72, 153), (147, 51, 234)), # Pink to Purple
        ((16, 185, 129), (59, 130, 246)), # Emerald to Blue
        ((249, 115, 22), (236, 72, 153)), # Orange to Pink
        ((15, 23, 42), (88, 28, 135)),    # Dark Slate to Deep Purple
    ]
    # Pick a palette based on text hash to ensure consistent background per slide
    h = 0
    for char in text_seed:
        h = 31 * h + ord(char)
    idx = abs(h) % len(palettes)
    color1, color2 = palettes[idx]
    
    # 720x1280 resolution (9:16)
    width, height = 720, 1280
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    
    # Draw linear vertical gradient
    for y in range(height):
        t = y / height
        r = int(color1[0] * (1 - t) + color2[0] * t)
        g = int(color1[1] * (1 - t) + color2[1] * t)
        b = int(color1[2] * (1 - t) + color2[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
        
    # Draw a soft radial glow overlay
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # Circle coordinates
    cx, cy = width // 2, height // 3
    r_glow = 350
    for r_i in range(r_glow, 0, -5):
        alpha = int(25 * (1 - r_i / r_glow))
        glow_draw.ellipse([cx - r_i, cy - r_i, cx + r_i, cy + r_i], fill=(255, 255, 255, alpha))
        
    # Merge and save
    final_img = Image.alpha_composite(img, glow).convert("RGB")
    final_img.save(output_path, "JPEG")
    add_log("美しいグラデーション背景を自動生成しました（無料枠フォールバック）。", "success")

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
    except Exception as e:
        add_log(f"画像のクロップ処理中にエラーが発生しました: {str(e)}", "warn")

def generate_background_image(prompt, api_key, output_path):
    """Generates a vertical (9:16) image using Hugging Face Inference API (FLUX.1-schnell / SDXL) with free gradient fallback."""
    hf_token = os.environ.get("HF_TOKEN", "")
    models = [
        "black-forest-labs/FLUX.1-schnell",
        "stabilityai/stable-diffusion-xl-base-1.0"
    ]
    
    # Translate / enrich prompt for beautiful backgrounds
    enhanced_prompt = f"beautiful vertical aesthetic scenery of: {prompt}, high resolution, 8k, photorealistic, cinematic lighting"
    add_log(f"Hugging Face Inference API で画像生成中: Prompt='{prompt[:25]}...'")
    
    for model in models:
        try:
            url = f"https://api-inference.huggingface.co/models/{model}"
            headers = {"Authorization": f"Bearer {hf_token}"}
            
            add_log(f"モデル [{model}] にリクエストを送信中...")
            response = requests.post(url, headers=headers, json={"inputs": enhanced_prompt}, timeout=30)
            
            # If model is loading, Hugging Face returns 503 with an estimated wait time
            if response.status_code == 503:
                wait_time = response.json().get("estimated_time", 5.0)
                add_log(f"モデルが起動中です。約 {wait_time:.1f} 秒待機して再試行します...", "warn")
                time.sleep(min(wait_time, 10))
                response = requests.post(url, headers=headers, json={"inputs": enhanced_prompt}, timeout=30)
                
            if response.status_code == 200 and len(response.content) > 1000:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                add_log(f"Hugging Face [{model}] からの画像取得に成功しました。", "success")
                # Crop to vertical 9:16
                crop_to_9_16(output_path)
                return
            else:
                add_log(f"モデル [{model}] は失敗しました (HTTP {response.status_code})。次のモデルを試します。", "warn")
        except Exception as ex:
            add_log(f"モデル [{model}] 実行中の例外: {str(ex)}", "warn")
            
    # Fallback to gradient
    add_log("Hugging Face API での画像生成に失敗したため、グラデーション背景を作成します。", "warn")
    generate_elegant_gradient(output_path, prompt)

def get_font_for_lang(lang, size):
    """Returns a specific font that supports Japanese, Thai, or English."""
    if lang == "ja":
        paths = [
            "C:\\Windows\\Fonts\\meiryo.ttc",      # Meiryo
            "C:\\Windows\\Fonts\\yuGothM.ttc",     # Yu Gothic
            "C:\\Windows\\Fonts\\msgothic.ttc",    # MS Gothic
        ]
    elif lang == "th":
        paths = [
            "C:\\Windows\\Fonts\\leelawad.ttc",    # Leelawadee
            "C:\\Windows\\Fonts\\leelawdb.ttf",    # Leelawadee Bold
            "C:\\Windows\\Fonts\\tahoma.ttf",      # Tahoma (supports Thai)
            "C:\\Windows\\Fonts\\cordia.ttc",      # Cordia New
        ]
    else:  # English / default
        paths = [
            "C:\\Windows\\Fonts\\segoeui.ttf",     # Segoe UI
            "C:\\Windows\\Fonts\\arial.ttf",       # Arial
        ]
        
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except IOError:
                continue
    # Fallback to system default or arial
    fallback_paths = ["C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\segoeuib.ttf"]
    for fp in fallback_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except IOError:
                continue
    return ImageFont.load_default()

def wrap_text_to_lines(draw, text, font, max_width):
    """Wraps text into lines that fit within max_width."""
    lines = []
    # Try character-based wrapping
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
    """Measures total height of wrapped text lines."""
    if not lines:
        return 0
    total_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        total_h += (h if h > 0 else 30) + line_spacing
    return total_h - line_spacing

def draw_block_text(draw, lines, font, fill_color, start_y, image_width, line_spacing=10):
    """Draws centered text lines starting at start_y and returns the next y position."""
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        # Center horizontally
        x = (image_width - w) // 2
        
        # Soft dark drop shadow for maximum contrast
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
        # Draw main text
        draw.text((x, y), line, font=font, fill=fill_color)
        y += (h if h > 0 else 30) + line_spacing
    return y

def draw_text_card(img_path, main_txt, sub_txt1, sub_txt2):
    """Renders all three texts vertically stacked and centered in one single gorgeous card (TikTok Safe Zone)."""
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Font sizes
    font_ja = get_font_for_lang("ja", 44)
    font_th = get_font_for_lang("th", 36)
    font_en = get_font_for_lang("en", 28)
    
    # 1. Wrap all text blocks
    max_text_width = width - 120 # Padding from borders
    
    # A列: 日本語 (main_txt)
    lines_ja = wrap_text_to_lines(draw, main_txt, font_ja, max_text_width)
    # B列: タイ語 (sub_txt1)
    lines_th = wrap_text_to_lines(draw, sub_txt1, font_th, max_text_width)
    # C列: 英語/ドメイン (sub_txt2)
    lines_en = wrap_text_to_lines(draw, sub_txt2, font_en, max_text_width)
    
    # 2. Measure heights of each block
    h_ja = measure_block_height(draw, lines_ja, font_ja)
    h_th = measure_block_height(draw, lines_th, font_th)
    h_en = measure_block_height(draw, lines_en, font_en)
    
    # 3. Calculate layout
    block_gap = 25 # Gap between Japanese, Thai, and English
    padding_y = 40  # Top/bottom padding inside the box
    
    total_content_height = h_ja + block_gap + h_th + block_gap + h_en
    total_card_height = total_content_height + (padding_y * 2)
    
    # Center vertically on the 9:16 screen
    card_y_start = (height - total_card_height) // 2
    
    # Create semi-transparent glass overlay drawing canvas
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # Draw a single unified box behind the stacked texts (safe and clean)
    card_x_start = 40
    card_x_end = width - 40
    card_y_end = card_y_start + total_card_height
    
    # Main container card background
    draw_overlay.rounded_rectangle(
        [card_x_start, card_y_start, card_x_end, card_y_end], 
        fill=(0, 0, 0, 160), 
        radius=20
    )
    
    # Dynamic border line for premium feeling
    draw_overlay.rounded_rectangle(
        [card_x_start, card_y_start, card_x_end, card_y_end], 
        outline=(255, 255, 255, 30), 
        width=2, 
        radius=20
    )
    
    # Merge overlay with background
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    # 4. Draw texts sequentially within the card
    current_y = card_y_start + padding_y
    
    # A: 日本語 (Japanese) in Vibrant Gold/Yellow
    current_y = draw_block_text(draw, lines_ja, font_ja, (255, 223, 85, 255), current_y, width)
    current_y += block_gap
    
    # B: タイ語 (Thai) in clean Soft Blue/White
    current_y = draw_block_text(draw, lines_th, font_th, (180, 230, 255, 255), current_y, width)
    current_y += block_gap
    
    # C: 英語/ドメイン (English) in semi-transparent light gray
    draw_block_text(draw, lines_en, font_en, (220, 225, 230, 220), current_y, width)
    
    # Save image
    final_img = img.convert("RGB")
    final_img.save(img_path, "JPEG")

def run_batch_generation(api_key, sheet_url, csv_data=None):
    """Main pipeline execution runs in a background thread."""
    global job_status
    job_status["status"] = "processing"
    job_status["progress"] = 5
    job_status["logs"] = []
    
    temp_files = []
    
    try:
        # Create output directory
        os.makedirs("static", exist_ok=True)
        os.makedirs("temp", exist_ok=True)
        
        # 1. Get data
        if csv_data:
            add_log("アップロードされたCSVファイルからデータを抽出しています...")
            data = parse_csv_content(csv_data)
        else:
            data = download_sheet_data(sheet_url)
        num_rows = len(data)
        
        if num_rows == 0:
            raise ValueError("スプレッドシートにデータが見つかりませんでした。")
            
        clips = []
        
        for idx, (main_txt, sub_txt1, sub_txt2) in enumerate(data):
            row_num = idx + 1
            add_log(f"--- スライド {row_num}/{num_rows} の処理を開始します ---")
            
            # Base names
            img_path = f"temp/bg_{row_num}.jpg"
            audio_path = f"temp/voice_{row_num}.mp3"
            temp_files.extend([img_path, audio_path])
            
            # A. Background Image Generation
            image_prompt = f"Beautiful aesthetic vertical photography of: {main_txt}. Minimalist, 8k resolution, photorealistic."
            generate_background_image(image_prompt, api_key, img_path)
            
            # B. Pillow Text Overlay
            add_log(f"スライド {row_num} にテロップを描画しています...")
            draw_text_card(img_path, main_txt, sub_txt1, sub_txt2)
            
            # C. Voice Generation (gTTS)
            add_log(f"スライド {row_num} のナレーション音声を生成中...")
            tts = gTTS(text=main_txt, lang='ja')
            tts.save(audio_path)
            
            # D. Video clip settings
            # Row 1 is 4.0s, rest are 3.5s
            target_duration = 4.0 if row_num == 1 else 3.5
            
            # Load with MoviePy
            img_clip = ImageClip(img_path)
            audio_clip = AudioFileClip(audio_path)
            
            # Fit duration to longer of target_duration and audio duration
            clip_dur = max(target_duration, audio_clip.duration)
            
            img_clip = img_clip.set_duration(clip_dur)
            img_clip = img_clip.set_audio(audio_clip)
            
            clips.append(img_clip)
            
            # Progress calculation (up to 85% for loop)
            job_status["progress"] = int(5 + (idx + 1) / num_rows * 80)
            
        # 2. Concatenate all 12 clips
        add_log("全12本のスライド動画を1本に結合しています...")
        final_video = concatenate_videoclips(clips, method="compose")
        
        # 3. Output final combined file
        output_file = "static/final_output.mp4"
        add_log("MP4形式で動画を出力中（エンコード中）...")
        final_video.write_videofile(
            output_file, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            temp_audiofile="temp/temp-audio.m4a", 
            remove_temp=True
        )
        
        # Close all clips
        for clip in clips:
            clip.close()
        final_video.close()
        
        add_log("動画合成が完全に完了しました！", "success")
        job_status["progress"] = 100
        job_status["status"] = "completed"
        
    except Exception as e:
        add_log(f"エラー発生: {str(e)}", "error")
        job_status["status"] = "failed"
        
    finally:
        # Cleanup individual temp files to free space
        for temp_f in temp_files:
            if os.path.exists(temp_f):
                try:
                    os.remove(temp_f)
                except Exception:
                    pass

@app.route('/')
def index():
    return render_template_string(open('templates/index.html', encoding='utf-8').read())

@app.route('/api/generate', methods=['POST'])
def start_generation():
    global job_status
    if job_status["status"] == "processing":
        return jsonify({"error": "すでに別の処理が実行中です。"}), 400
        
    req_data = request.json or {}
    api_key = req_data.get("api_key")
    sheet_url = req_data.get("sheet_url")
    csv_data = req_data.get("csv_data")
    
    if not api_key:
        return jsonify({"error": "APIキーが必要です。"}), 400
    if not sheet_url and not csv_data:
        return jsonify({"error": "スプレッドシートURLまたはCSVファイルの内容が必要です。"}), 400
        
    # Save API key to config.json for the CLI script generate_video.py to use
    try:
        import json
        config_path = "data/config.json"
        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        config_data["gemini_api_key"] = api_key
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving api_key to config: {e}")
        
    # Start thread
    thread = threading.Thread(target=run_batch_generation, args=(api_key, sheet_url, csv_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started"})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(job_status)

@app.route('/api/output', methods=['GET'])
def get_output_file():
    target = "static/final_output.mp4"
    if os.path.exists(target):
        return send_file(target, mimetype="video/mp4")
    return jsonify({"error": "出力ファイルが存在しません。"}), 404

if __name__ == '__main__':
    # Start app on localhost
    print("--------------------------------------------------")
    print(" 縦型ショート動画一括生成システム Web GUI 起動完了")
    print(" ブラウザで http://127.0.0.1:5000 にアクセスしてください")
    print("--------------------------------------------------")
    app.run(host='127.0.0.1', port=5000, debug=True)
