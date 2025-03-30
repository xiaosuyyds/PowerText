import re
import time

from PIL import Image, ImageFont, ImageDraw

import src.power_text as power_text
# import power_text as power_text
from src.power_text import local_emoji_source
# from power_text import local_emoji_source

jap = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')

img = Image.new("RGB", (1150, 630), (255, 255, 255))

draw = ImageDraw.Draw(img)

font1 = ImageFont.truetype(r'SmileySans-Oblique.ttf', 24)
font2 = ImageFont.truetype(r'PINGFANG MEDIUM.TTF', 24)
font3 = ImageFont.truetype(r'unifont-16.0.02.otf', 24)
font4 = ImageFont.truetype(r'Segoe UI.ttf', 24)


draw.line(((900, 0), (900, 630)), fill=(0, 0, 0))
draw.line(((0, 220), (1150, 220)), fill=(0, 0, 0))


start_time = time.time()
power_text.draw_text(
    img,
    (10, 10),  # 起始xy坐标

    """
皆さん✨、我在インターネット上看到someone把几国language混在一起speak🌍。我看到之后be like：それは我じゃないか！😂 私もtry一tryです🎉。虽然是混乱している句子ですけど、中文日本語プラスEnglish、挑戦スタート🚀！  

我study📖日本語的时候，もし有汉字，我会很happy😊。Bueause中国人として、when I see汉字，すぐに那个汉字がわかります✨。But 我hate😤外来語、什么マクドナルド🍔、スターバックス☕、グーグル🔍、ディズニーランド🏰、根本记不住カタカナhow to写、太難しい😭。  

以上です✌️，byebye👋！

awa
    """.strip(),
    [
        power_text.Font(font4, lambda char: char.lower() in "abcdefghijklmnopqrstuvwxyz0123456789", (0, 0, 0)),
        power_text.Font(font3, lambda char: jap.match(char) is not None, (22, 125, 255)),
        power_text.Font(font2, lambda _: True, (220, 20, 60))
    ],
    (0, 0, 0),  # 字体颜色
    max_x=900,  # 最大宽度（超过自动换行）
    max_y=220,  # 最大高度（超过自动省略）
    has_emoji=True,
    emoji_source=local_emoji_source.LocalEmojiSource(r"C:\Users\xiaosu\Downloads\noto-emoji-main\png\128"),
    end_text="...",  # 省略符号
)
print(f"生成用时: {round(((time.time() - start_time) * 1000), 2)}ms")
img.save("example.png")
