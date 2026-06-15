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

# Master Datasets: Human-curated, 100% correct Hiragana + Thai mapping for High-Quality Videos
MASTER_DATASETS = [
    # 1: にちじょうのあいさつ (Greetings)
    [
        {"japanese": "にちじょうのあいさつ", "thai": "คำทักทายในชีวิตประจำวัน"},
        {"japanese": "こんにちは", "thai": "สวัสดี (ตอนกลางวัน)"},
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
    # 2: いろのひょうげん (Colors)
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
    # 3: くだもののなまえ (Fruits)
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
    # 4: すうじのひょうげん (Numbers)
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
    # 5: べんりなことば (Useful Phrases)
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
    ],
    # 6: かいもののことば (Shopping)
    [
        {"japanese": "かいもののことば", "thai": "คำศัพท์เกี่ยวกับการช้อปปิ้ง"},
        {"japanese": "これください", "thai": "ขออันนี้ครับ/ค่ะ"},
        {"japanese": "ふくろ", "thai": "ถุง"},
        {"japanese": "かーど", "thai": "บัตรเครดิต"},
        {"japanese": "げんきん", "thai": "เงินสด"},
        {"japanese": "れしーと", "thai": "ใบเสร็จ"},
        {"japanese": "わりびき", "thai": "ส่วนลด"},
        {"japanese": "ぜいこみ", "thai": "รวมภาษี"},
        {"japanese": "おつり", "thai": "เงินทอน"},
        {"japanese": "たかい", "thai": "แพง"},
        {"japanese": "やすい", "thai": "ถูก"},
        {"japanese": "みせてください", "thai": "ขอดูหน่อยครับ/ค่ะ"}
    ],
    # 7: れすとらんのことば (Restaurant)
    [
        {"japanese": "れすとらんのことば", "thai": "คำศัพท์ในร้านอาหาร"},
        {"japanese": "めにゅー", "thai": "เมนู"},
        {"japanese": "ちゅうもん", "thai": "สั่งอาหาร"},
        {"japanese": "おみず", "thai": "น้ำเปล่า"},
        {"japanese": "おかんじょう", "thai": "เช็คบิล"},
        {"japanese": "おはし", "thai": "ตะเกียบ"},
        {"japanese": "すぷーん", "thai": "ช้อน"},
        {"japanese": "ふぉーく", "thai": "ส้อม"},
        {"japanese": "こっぷ", "thai": "แก้วน้ำ"},
        {"japanese": "からい", "thai": "เผ็ด"},
        {"japanese": "あまい", "thai": "หวาน"},
        {"japanese": "おなかいっぱい", "thai": "อิ่มแล้ว"}
    ],
    # 8: りょこうのことば (Travel)
    [
        {"japanese": "りょこうのことば", "thai": "คำศัพท์เกี่ยวกับการท่องเที่ยว"},
        {"japanese": "ぱすぽーと", "thai": "พาสปอร์ต"},
        {"japanese": "きっぷ", "thai": "ตั๋ว"},
        {"japanese": "えき", "thai": "สถานี"},
        {"japanese": "ほてる", "thai": "โรงแรม"},
        {"japanese": "たくしー", "thai": "แท็กซี่"},
        {"japanese": "ちず", "thai": "แผนที่"},
        {"japanese": "こうくうけん", "thai": "ตั๋วเครื่องบิน"},
        {"japanese": "にもつ", "thai": "กระเป๋าเดินทาง"},
        {"japanese": "おみやげ", "thai": "ของฝาก"},
        {"japanese": "どこですか", "thai": "อยู่ที่ไหนครับ/ค่ะ"},
        {"japanese": "かんこう", "thai": "การท่องเที่ยว"}
    ],
    # 9: てんきのことば (Weather)
    [
        {"japanese": "てんきのことば", "thai": "คำศัพท์เกี่ยวกับสภาพอากาศ"},
        {"japanese": "はれ", "thai": "แดดออก / แจ่มใส"},
        {"japanese": "あめ", "thai": "ฝนตก"},
        {"japanese": "くもり", "thai": "ครึ้มฟ้าครึ้มฝน"},
        {"japanese": "ゆき", "thai": "หิมะตก"},
        {"japanese": "かぜ", "thai": "ลม"},
        {"japanese": "あつい", "thai": "ร้อน"},
        {"japanese": "さむい", "thai": "หนาว"},
        {"japanese": "すずしい", "thai": "เย็นสบาย"},
        {"japanese": "あたたかい", "thai": "อบอุ่น"},
        {"japanese": "たいふう", "thai": "พายุไต้ฝุ่น"},
        {"japanese": "かみなり", "thai": "ฟ้าผ่า / ฟ้าร้อง"}
    ],
    # 10: のりもののなまえ (Vehicles)
    [
        {"japanese": "のりもののなまえ", "thai": "ชื่อยานพาหนะ"},
        {"japanese": "でんしゃ", "thai": "รถไฟ"},
        {"japanese": "ばす", "thai": "รถบัส"},
        {"japanese": "たくしー", "thai": "แท็กซี่"},
        {"japanese": "ひこうき", "thai": "เครื่องบิน"},
        {"japanese": "ふね", "thai": "เรือ"},
        {"japanese": "じてんしゃ", "thai": "จักรยาน"},
        {"japanese": "くるま", "thai": "รถยนต์"},
        {"japanese": "ばいく", "thai": "รถมอเตอร์ไซค์"},
        {"japanese": "ちかてつ", "thai": "รถไฟใต้ดิน"},
        {"japanese": "しんかんせん", "thai": "รถไฟชินคันเซ็น"},
        {"japanese": "へりこぷたー", "thai": "เฮลิคอปเตอร์"}
    ],
    # 11: どうぶつのなまえ (Animals)
    [
        {"japanese": "どうぶつのなまえ", "thai": "ชื่อสัตว์ต่างๆ"},
        {"japanese": "いぬ", "thai": "สุนัข"},
        {"japanese": "ねこ", "thai": "แมว"},
        {"japanese": "うさぎ", "thai": "กระต่าย"},
        {"japanese": "とり", "thai": "นก"},
        {"japanese": "さかな", "thai": "ปลา"},
        {"japanese": "さる", "thai": "ลิง"},
        {"japanese": "くま", "thai": "หมี"},
        {"japanese": "ぱんだ", "thai": "แพนด้า"},
        {"japanese": "らいおん", "thai": "สิงโต"},
        {"japanese": "ぞう", "thai": "ช้าง"},
        {"japanese": "うま", "thai": "ม้า"}
    ],
    # 12: かぞくのよびかた (Family)
    [
        {"japanese": "かぞくのよびかた", "thai": "คำเรียกสมาชิกในครอบครัว"},
        {"japanese": "かぞく", "thai": "ครอบครัว"},
        {"japanese": "おとうさん", "thai": "คุณพ่อ"},
        {"japanese": "おかあさん", "thai": "คุณแม่"},
        {"japanese": "おにいさん", "thai": "พี่ชาย"},
        {"japanese": "おねえさん", "thai": "พี่สาว"},
        {"japanese": "おとうと", "thai": "น้องชาย"},
        {"japanese": "いもうと", "thai": "น้องสาว"},
        {"japanese": "おじいちゃん", "thai": "คุณปู่ / คุณตา"},
        {"japanese": "おばあちゃん", "thai": "คุณย่า / คุณยาย"},
        {"japanese": "ともだち", "thai": "เพื่อน"},
        {"japanese": "あかちゃん", "thai": "เด็กทารก"}
    ],
    # 13: からだのなまえ (Body Parts)
    [
        {"japanese": "からだのなまえ", "thai": "ส่วนต่างๆ ของร่างกาย"},
        {"japanese": "あたま", "thai": "หัว / ศีรษะ"},
        {"japanese": "め", "thai": "ตา"},
        {"japanese": "みみ", "thai": "หู"},
        {"japanese": "はな", "thai": "จมูก"},
        {"japanese": "くち", "thai": "ปาก"},
        {"japanese": "て", "thai": "มือ"},
        {"japanese": "あし", "thai": "ขา / เท้า"},
        {"japanese": "おなか", "thai": "ท้อง"},
        {"japanese": "かお", "thai": "ใบหน้า"},
        {"japanese": "のど", "thai": "คอหอย / ลำคอ"},
        {"japanese": "かみ", "thai": "ผม"}
    ],
    # 14: うちのなかのもの (In the House)
    [
        {"japanese": "うちのなかのもの", "thai": "สิ่งของในบ้าน"},
        {"japanese": "てれび", "thai": "โทรทัศน์"},
        {"japanese": "れいぞうこ", "thai": "ตู้เย็น"},
        {"japanese": "えあこん", "thai": "เครื่องปรับอากาศ"},
        {"japanese": "べっど", "thai": "เตียง"},
        {"japanese": "つくえ", "thai": "โต๊ะ"},
        {"japanese": "いす", "thai": "เก้าอี้"},
        {"japanese": "まど", "thai": "หน้าต่าง"},
        {"japanese": "どあ", "thai": "ประตู"},
        {"japanese": "そうじき", "thai": "เครื่องดูดฝุ่น"},
        {"japanese": "せんたくき", "thai": "เครื่องซักผ้า"},
        {"japanese": "とけい", "thai": "นาฬิกา"}
    ],
    # 15: どうさのことば (Verbs)
    [
        {"japanese": "どうさのことば", "thai": "คำกริยาแสดงท่าทาง"},
        {"japanese": "いく", "thai": "ไป"},
        {"japanese": "くる", "thai": "มา"},
        {"japanese": "たべる", "thai": "กิน"},
        {"japanese": "のむ", "thai": "ดื่ม"},
        {"japanese": "みる", "thai": "ดู / มอง"},
        {"japanese": "きく", "thai": "ฟัง / ถาม"},
        {"japanese": "はなす", "thai": "พูดคุย"},
        {"japanese": "かく", "thai": "เขียน"},
        {"japanese": "よむ", "thai": "อ่าน"},
        {"japanese": "かう", "thai": "ซื้อ"},
        {"japanese": "する", "thai": "ทำ"}
    ],
    # 16: かんじょうのひょうげん (Emotions)
    [
        {"japanese": "かんじょうのひょうげん", "thai": "คำแสดงอารมณ์ความรู้สึก"},
        {"japanese": "うれしい", "thai": "ดีใจ"},
        {"japanese": "かなしい", "thai": "เศร้า"},
        {"japanese": "たのしい", "thai": "สนุก"},
        {"japanese": "おもしろい", "thai": "น่าสนใจ / ตลก"},
        {"japanese": "こわい", "thai": "กลัว"},
        {"japanese": "おどろく", "thai": "ตกใจ / ประหลาดใจ"},
        {"japanese": "いかる", "thai": "โกรธ"},
        {"japanese": "しんぱい", "thai": "เป็นห่วง / กังวล"},
        {"japanese": "はずかしい", "thai": "อาย"},
        {"japanese": "つかれる", "thai": "เหนื่อย"},
        {"japanese": "ねむい", "thai": "ง่วงนอน"}
    ],
    # 17: じかんのひょうげん (Time Expressions)
    [
        {"japanese": "じかんのひょうげん", "thai": "คำบอกเวลา"},
        {"japanese": "いま", "thai": "ตอนนี้"},
        {"japanese": "きょう", "thai": "วันนี้"},
        {"japanese": "あした", "thai": "พรุ่งนี้"},
        {"japanese": "きのう", "thai": "เมื่อวาน"},
        {"japanese": "あさ", "thai": "เช้า"},
        {"japanese": "ひる", "thai": "กลางวัน"},
        {"japanese": "よる", "thai": "กลางคืน"},
        {"japanese": "じかん", "thai": "เวลา / ชั่วโมง"},
        {"japanese": "ふん", "thai": "นาที"},
        {"japanese": "びょう", "thai": "วินาที"},
        {"japanese": "かれんだー", "thai": "ปฏิทิน"}
    ],
    # 18: がっこうのことば (School Items)
    [
        {"japanese": "がっこうのことば", "thai": "คำศัพท์เกี่ยวกับโรงเรียน"},
        {"japanese": "がっこう", "thai": "โรงเรียน"},
        {"japanese": "せんせい", "thai": "คุณครู"},
        {"japanese": "がくせい", "thai": "นักเรียน / นักศึกษา"},
        {"japanese": "きょうしつ", "thai": "ห้องเรียน"},
        {"japanese": "ほん", "thai": "หนังสือ"},
        {"japanese": "のーと", "thai": "สมุดบันทึก"},
        {"japanese": "えんぴつ", "thai": "ดินสอ"},
        {"japanese": "ぺん", "thai": "ปากกา"},
        {"japanese": "けしごむ", "thai": "ยางลบ"},
        {"japanese": "かばん", "thai": "กระเป๋า"},
        {"japanese": "しゅくだい", "thai": "การบ้าน"}
    ],
    # 19: しごとのことば (Work / Office)
    [
        {"japanese": "しごとのことば", "thai": "คำศัพท์เกี่ยวกับงานและออฟฟิศ"},
        {"japanese": "しごと", "thai": "งาน"},
        {"japanese": "かいしゃ", "thai": "บริษัท"},
        {"japanese": "ぱそこん", "thai": "คอมพิวเตอร์พกพา"},
        {"japanese": "でんわ", "thai": "โทรศัพท์"},
        {"japanese": "めーる", "thai": "อีเมล"},
        {"japanese": "かいぎ", "thai": "การประชุม"},
        {"japanese": "しょるい", "thai": "เอกสาร"},
        {"japanese": "めいし", "thai": "นามบัตร"},
        {"japanese": "ざんぎょう", "thai": "การทำงานล่วงเวลา (OT)"},
        {"japanese": "きゅうりょう", "thai": "เงินเดือน"},
        {"japanese": "やすみ", "thai": "วันหยุด"}
    ],
    # 20: まちのなかのばしょ (Places in Town)
    [
        {"japanese": "まちのなかのばしょ", "thai": "สถานที่ต่างๆ ในเมือง"},
        {"japanese": "えき", "thai": "สถานีรถไฟ"},
        {"japanese": "びょういん", "thai": "โรงพยาบาล"},
        {"japanese": "ぎんこう", "thai": "ธนาคาร"},
        {"japanese": "ゆうびんきょく", "thai": "ที่ทำการไปรษณีย์"},
        {"japanese": "こうばん", "thai": "ป้อมตำรวจ"},
        {"japanese": "こうえん", "thai": "สวนสาธารณะ"},
        {"japanese": "すーぱー", "thai": "ซูเปอร์มาร์เก็ต"},
        {"japanese": "こんびに", "thai": "ร้านสะดวกซื้อ"},
        {"japanese": "としょかん", "thai": "ห้องสมุด"},
        {"japanese": "えいがかん", "thai": "โรงภาพยนตร์"},
        {"japanese": "でぱーと", "thai": "ห้างสรรพสินค้า"}
    ],
    # 21: のみもののなまえ (Drinks)
    [
        {"japanese": "のみもののなまえ", "thai": "ชื่อเครื่องดื่มต่างๆ"},
        {"japanese": "おみず", "thai": "น้ำเปล่า"},
        {"japanese": "おちゃ", "thai": "ชา"},
        {"japanese": "こうひー", "thai": "กาแฟ"},
        {"japanese": "ぎゅうにゅう", "thai": "นม"},
        {"japanese": "じゅーす", "thai": "น้ำผลไม้"},
        {"japanese": "こうちゃ", "thai": "ชาฝรั่ง / ชาดำ"},
        {"japanese": "こーら", "thai": "โคล่า"},
        {"japanese": "びーる", "thai": "เบียร์"},
        {"japanese": "わいん", "thai": "ไวน์"},
        {"japanese": "おゆ", "thai": "น้ำร้อน"},
        {"japanese": "すーぷ", "thai": "ซุป"}
    ],
    # 22: やさいのなまえ (Vegetables)
    [
        {"japanese": "やさいのなまえ", "thai": "ชื่อผักต่างๆ"},
        {"japanese": "とまと", "thai": "มะเขือเทศ"},
        {"japanese": "きゃべつ", "thai": "กะหล่ำปลี"},
        {"japanese": "れたす", "thai": "ผักกาดหอม"},
        {"japanese": "にんじん", "thai": "แครอท"},
        {"japanese": "たまねぎ", "thai": "หอมหัวใหญ่"},
        {"japanese": "じゃがいも", "thai": "มันฝรั่ง"},
        {"japanese": "なす", "thai": "มะเขือยาว"},
        {"japanese": "きゅうり", "thai": "แตงกวา"},
        {"japanese": "ほうれんそう", "thai": "ผักปวยเล้ง"},
        {"japanese": "だいこん", "thai": "หัวไชเท้า"},
        {"japanese": "かぼちゃ", "thai": "ฟักทอง"}
    ],
    # 23: 日本のたべもの (Japanese Food)
    [
        {"japanese": "にほんのたべもの", "thai": "อาหารญี่ปุ่นยอดนิยม"},
        {"japanese": "すし", "thai": "ซูชิ"},
        {"japanese": "らーめん", "thai": "ราเม็ง"},
        {"japanese": "てんぷら", "thai": "เทมปุระ"},
        {"japanese": "うどん", "thai": "อุด้ง"},
        {"japanese": "そば", "thai": "โซบะ"},
        {"japanese": "たこやき", "thai": "ทาโกะยากิ"},
        {"japanese": "おこのみやき", "thai": "พิซซ่าญี่ปุ่น"},
        {"japanese": "やきとり", "thai": "ไก่ย่างญี่ปุ่น"},
        {"japanese": "かれーらいす", "thai": "แกงกะหรี่ญี่ปุ่น"},
        {"japanese": "ぎょうざ", "thai": "เกี๊ยวซ่า"},
        {"japanese": "なっとう", "thai": "ถั่วเน่าญี่ปุ่น"}
    ],
    # 24: しゅみのことば (Hobbies)
    [
        {"japanese": "しゅみのことば", "thai": "คำศัพท์เกี่ยวกับงานอดิเรก"},
        {"japanese": "しゅみ", "thai": "งานอดิเรก"},
        {"japanese": "おんがくきく", "thai": "ฟังเพลง"},
        {"japanese": "えいがみる", "thai": "ดูภาพยนตร์"},
        {"japanese": "どくしょ", "thai": "อ่านหนังสือ"},
        {"japanese": "りょこう", "thai": "ท่องเที่ยว"},
        {"japanese": "しゃしん", "thai": "ถ่ายรูป"},
        {"japanese": "すぽーつ", "thai": "เล่นกีฬา"},
        {"japanese": "げーむ", "thai": "เล่นเกม"},
        {"japanese": "りょうり", "thai": "ทำอาหาร"},
        {"japanese": "かいもの", "thai": "ช้อปปิ้ง"},
        {"japanese": "さんぽ", "thai": "เดินเล่น"}
    ],
    # 25: ようすのことば (Adjectives)
    [
        {"japanese": "ようすのことば", "thai": "คำคุณศัพท์บอกสภาพ"},
        {"japanese": "おおきい", "thai": "ใหญ่"},
        {"japanese": "ちいさい", "thai": "เล็ก"},
        {"japanese": "あた新しい", "thai": "ใหม่"}, # -> あたらしい に修正
        {"japanese": "あたらしい", "thai": "ใหม่"},
        {"japanese": "ふるい", "thai": "เก่า"},
        {"japanese": "いい", "thai": "ดี"},
        {"japanese": "わるい", "thai": "เลว / แย่"},
        {"japanese": "むずかしい", "thai": "ยาก"},
        {"japanese": "やさしい", "thai": "ง่าย / ใจดี"},
        {"japanese": "お重い", "thai": "หนัก"}, # -> おもい に修正
        {"japanese": "おもい", "thai": "หนัก"},
        {"japanese": "かるい", "thai": "เบา"},
        {"japanese": "いそがしい", "thai": "ยุ่ง"}
    ],
    # 26: きせつのなまえ (Seasons)
    [
        {"japanese": "きせつのなまえ", "thai": "ชื่อฤดูกาลต่างๆ"},
        {"japanese": "きせつ", "thai": "ฤดูกาล"},
        {"japanese": "はる", "thai": "ฤดูใบไม้ผลิ"},
        {"japanese": "なつ", "thai": "ฤดูร้อน"},
        {"japanese": "あき", "thai": "ฤดูใบไม้ร่วง"},
        {"japanese": "ふゆ", "thai": "ฤดูหนาว"},
        {"japanese": "つゆ", "thai": "ฤดูฝนญี่ปุ่น"},
        {"japanese": "かんき", "thai": "ฤดูแล้ง (แบบไทย)"},
        {"japanese": "はれ", "thai": "ท้องฟ้าแจ่มใส"},
        {"japanese": "こうよう", "thai": "ใบไม้เปลี่ยนสี"},
        {"japanese": "さくら", "thai": "ดอกซากุระ"},
        {"japanese": "はなび", "thai": "ดอกไม้ไฟ"}
    ]
]

# Adjust duplicate items in lists
# Cleaned up duplicate items in lists to avoid length mismatch
for dataset in MASTER_DATASETS:
    # Ensure each topic has exactly 12 items (1 title + 11 content pages)
    if len(dataset) > 12:
        dataset[:] = dataset[:12]

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
    if not os.path.exists(FONT_JA_PATH) or os.path.getsize(FONT_JA_PATH) < 100000:
        url_ja = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf"
        try:
            download_file(url_ja, FONT_JA_PATH)
        except Exception as e:
            print(f"Error downloading Japanese font: {e}")
            
    if not os.path.exists(FONT_TH_PATH) or os.path.getsize(FONT_TH_PATH) < 50000:
        url_th = "https://cdn.jsdelivr.net/npm/@electron-fonts/noto-sans-thai/fonts/NotoSansThai-Bold.ttf"
        try:
            download_file(url_th, FONT_TH_PATH)
        except Exception as e:
            pass

def get_font(lang, size):
    """Returns the loaded font depending on the language."""
    if lang == "en":
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

def generate_dynamic_theme(history):
    """Generates a completely new topic dataset using Local Ollama, Gemini, or Pollinations AI.
    If all models fail, it retries. If it still fails, it raises an error to prevent generating bad/corrupt videos.
    """
    used_titles = history.get("used_titles", [])
    used_words = history.get("used_words", [])
    
    max_retries = 3
    for attempt in range(max_retries):
        print(f"Theme generation attempt {attempt + 1}/{max_retries}...")
        
        # 1. Try Local Ollama (gemma4:e2b) since it's installed and free
        print("Trying local Ollama (gemma4:e2b) for theme generation...")
        try:
            url = "http://localhost:11434/api/chat"
            system_prompt = (
                "You are an expert Japanese language teacher. "
                "Generate a brand new Japanese vocabulary theme/topic and 11 related words with their Thai translations. "
                "The first object in the JSON list must be the theme/topic itself. "
                "The remaining 11 objects must be vocabulary words belonging to that theme. "
                "Rules:\n"
                "1. Write the 'japanese' field ONLY in Hiragana or Katakana (no Kanji!).\n"
                "2. The Thai translation must be accurate.\n"
                "3. Do NOT use any of these already used themes: {used_titles}.\n"
                "4. Do NOT use any of these already used words: {used_words}.\n"
                "Output MUST be a valid JSON array of exactly 12 objects. Each object must have keys 'japanese' and 'thai'. "
                "Do not include any markdown formatting like ```json or explanation, return ONLY the raw JSON string."
            ).format(used_titles=", ".join(used_titles[-30:]), used_words=", ".join(used_words[-50:]))
            
            payload = {
                "model": "gemma4:e2b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate a new unique Japanese-Thai vocabulary list."}
                ],
                "stream": False
            }
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                content = res.json().get("message", {}).get("content", "").strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\n", "", content)
                    content = re.sub(r"\n```$", "", content)
                dataset = json.loads(content.strip())
                if isinstance(dataset, list) and len(dataset) >= 12:
                    cleaned_dataset = []
                    for item in dataset[:12]:
                        cleaned_dataset.append({
                            "japanese": str(item.get("japanese", "")).strip(),
                            "thai": str(item.get("thai", "")).strip()
                        })
                    new_title = cleaned_dataset[0]["japanese"]
                    if new_title not in used_titles:
                        print(f"Successfully generated dynamic theme via local Ollama: {new_title}")
                        return cleaned_dataset
            else:
                print(f"Ollama returned HTTP status {res.status_code}")
        except Exception as e:
            print(f"Local Ollama generation failed: {e}")

        # 2. Try Gemini API if key is available in environment or config.json
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not gemini_key:
            # Try loading manually from .env files
            for env_file in [".env", "../.env", "../../.env"]:
                if os.path.exists(env_file):
                    try:
                        with open(env_file, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#") and "=" in line:
                                    k, v = line.split("=", 1)
                                    k = k.strip()
                                    v = v.strip().strip('"').strip("'")
                                    if k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                                        gemini_key = v
                                        break
                    except Exception:
                        pass
                if gemini_key:
                    break

        if not gemini_key:
            config_path = os.path.join(DATA_DIR, "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                        gemini_key = config_data.get("gemini_api_key")
                except Exception:
                    pass

        if gemini_key:
            print("Trying Gemini API for theme generation...")
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                prompt_text = (
                    f"You are an expert Japanese language teacher. "
                    f"Generate a brand new Japanese vocabulary theme/topic and 11 related words with their Thai translations.\n"
                    f"Output MUST be a valid JSON array of exactly 12 objects, where the first object is the theme/topic, "
                    f"and the remaining 11 are vocabulary words belonging to that theme.\n"
                    f"Rules:\n"
                    f"1. Write the 'japanese' field ONLY in Hiragana or Katakana (no Kanji!).\n"
                    f"2. The Thai translation must be accurate.\n"
                    f"3. Do NOT use any of these already used themes: {', '.join(used_titles[-30:])}.\n"
                    f"4. Do NOT use any of these already used words: {', '.join(used_words[-50:])}.\n"
                    f"Return ONLY the raw JSON array, no other text."
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt_text}]}],
                    "generationConfig": {"responseMimeType": "application/json"}
                }
                res = requests.post(url, json=payload, timeout=20)
                if res.status_code == 200:
                    text_out = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    dataset = json.loads(text_out)
                    if isinstance(dataset, list) and len(dataset) >= 12:
                        cleaned_dataset = []
                        for item in dataset[:12]:
                            cleaned_dataset.append({
                                "japanese": str(item.get("japanese", "")).strip(),
                                "thai": str(item.get("thai", "")).strip()
                            })
                        new_title = cleaned_dataset[0]["japanese"]
                        if new_title not in used_titles:
                            print(f"Successfully generated dynamic theme via Gemini API: {new_title}")
                            return cleaned_dataset
            except Exception as e:
                print(f"Gemini API generation failed: {e}")

        # 3. Try Pollinations AI as third fallback
        print("Trying Pollinations AI for theme generation...")
        try:
            url = "https://text.pollinations.ai/openai"
            system_prompt = (
                "You are an expert Japanese language teacher. "
                "Generate a brand new Japanese vocabulary theme/topic and 11 related words with their Thai translations. "
                "The first object in the JSON list must be the theme/topic itself. "
                "The remaining 11 objects must be vocabulary words belonging to that theme. "
                "Rules:\n"
                "1. Write the 'japanese' field ONLY in Hiragana or Katakana (no Kanji!).\n"
                "2. The Thai translation must be accurate.\n"
                "3. Do NOT use any of these already used themes: {used_titles}.\n"
                "4. Do NOT use any of these already used words: {used_words}.\n"
                "Output MUST be a valid JSON array of exactly 12 objects. Each object must have keys 'japanese' and 'thai'. "
                "Do not include any markdown formatting like ```json or explanation, return ONLY the raw JSON string."
            ).format(used_titles=", ".join(used_titles[-30:]), used_words=", ".join(used_words[-50:]))
            
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate a new unique Japanese-Thai vocabulary list."}
                ],
                "model": "mistral"
            }
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                try:
                    res_data = res.json()
                    content = res_data["choices"][0]["message"]["content"].strip()
                except Exception:
                    content = res.text.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\n", "", content)
                    content = re.sub(r"\n```$", "", content)
                dataset = json.loads(content.strip())
                if isinstance(dataset, list) and len(dataset) >= 12:
                    cleaned_dataset = []
                    for item in dataset[:12]:
                        cleaned_dataset.append({
                            "japanese": str(item.get("japanese", "")).strip(),
                            "thai": str(item.get("thai", "")).strip()
                        })
                    new_title = cleaned_dataset[0]["japanese"]
                    if new_title not in used_titles:
                        print(f"Successfully generated dynamic theme via Pollinations AI: {new_title}")
                        return cleaned_dataset
        except Exception as e:
            print(f"Pollinations AI generation failed: {e}")

        if attempt < max_retries - 1:
            print("AI models failed or timed out. Waiting 5 seconds before retrying...")
            time.sleep(5)
            
    # Raise error if everything failed
    raise RuntimeError(
        "Theme generation failed: All AI models (Ollama, Gemini, Pollinations) are currently unavailable or rate-limited. "
        "To protect video quality and prevent duplicate/corrupt content, generation has been stopped. "
        "Please check your internet connection, confirm that your Gemini API key is correct in the Web GUI, or check local Ollama status."
    )

def generate_text_content(history):
    """Selects next unique topic dataset from MASTER_DATASETS based on history, or generates a new one."""
    print("Selecting next unique topic dataset...")
    
    # 1. Filter datasets that have not been used yet
    unused_datasets = [ds for ds in MASTER_DATASETS if ds[0]["japanese"] not in history.get("used_titles", [])]
    if unused_datasets:
        selected_dataset = unused_datasets[0]
        print(f"Successfully selected unused dataset: {selected_dataset[0]['japanese']}")
        return selected_dataset
        
    # 2. All static master datasets have been used once. Generate a brand new one dynamically to ensure 0 duplicates.
    print("All master datasets have been used once. Generating a new unique dataset using LLM...")
    return generate_dynamic_theme(history)

def translate_title_to_image_prompt(title_japanese):
    """Translates the Japanese title to a highly relevant English description for the image generation prompt."""
    url = "https://text.pollinations.ai/openai"
    system_prompt = (
        "You translate a Japanese phrase to a highly descriptive English scene for AI image generation. "
        "The scene must be cute, colorful, and appeal to young women. "
        "For example, if the input is 'にちじょうのあいさつ' (Everyday Greetings), output 'A cute cozy study room, pastel pink and lavender, cute stationery, a tiny cute notebook, soft lighting'. "
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
        if response.status_code == 200:
            try:
                res_data = response.json()
                desc = res_data["choices"][0]["message"]["content"].strip()
            except Exception:
                desc = response.text.strip()
            if desc:
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
    
    # 1. Try Local API Server LCM model
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
    
    # Load fonts
    font_ja = get_font("ja", 48)
    font_th = get_font("th", 38)
    font_en = get_font("en", 56)
    
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
    
    card_x_start = 45
    card_x_end = width - 45
    card_y_end = card_y_start + total_card_height
    
    draw_overlay.rounded_rectangle(
        [card_x_start, card_y_start, card_x_end, card_y_end], 
        fill=(40, 20, 30, 180), 
        radius=28
    )
    
    draw_overlay.rounded_rectangle(
        [card_x_start, card_y_start, card_x_end, card_y_end], 
        outline=(255, 192, 203, 120), 
        width=3, 
        radius=28
    )
    
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    current_y = card_y_start + padding_y
    current_y = draw_block_text(draw, lines_ja, font_ja, (255, 223, 85, 255), current_y, width)
    current_y += block_gap
    current_y = draw_block_text(draw, lines_th, font_th, (255, 255, 255, 255), current_y, width)
    current_y += block_gap
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
        
        make_slide_image(bg_image_path, slide["japanese"], slide["thai"], "yui-yuto.com", slide_img_path)
        
        speaker_id = VOICEVOX_SPEAKERS[(num - 1) % len(VOICEVOX_SPEAKERS)]
        generate_voicevox_audio(slide["japanese"], speaker_id=speaker_id, output_path=voice_path)
        
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
