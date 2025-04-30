# PowerText  

| English | [简体中文](https://github.com/xiaosuyyds/PowerText/blob/master/README_ZH.md) |

## 📖 Introduction  
PowerText is a text renderer for Pillow that supports emojis, multiple fonts, automatic line wrapping, and automatic truncation.  

## ⬇️ Installation  
```bash
python -m pip install PowerText
```  
Of course, you can also install it from the source:  
```bash
git clone https://github.com/xiaosuyyds/PowerText.git
python -m pip install .
```  

#### Note! By default, only the necessary dependencies are installed. If you need emoji rendering, please install:  
```bash
python -m pip install PowerText[full]
```  
or  
```bash
git clone https://github.com/xiaosuyyds/PowerText.git
python -m pip install .[full]
```  

## 🧑‍💻 Usage  
### Example Code  
```python
import power_text
import re
from PIL import Image, ImageFont

jap = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')

img = Image.new("RGB", (1150, 630), (255, 255, 255))
# Note: Ensure you have these font files or replace with paths to fonts you have
font1 = ImageFont.truetype(r'PINGFANG MEDIUM.TTF', 24)
font2 = ImageFont.truetype(r'unifont-16.0.02.otf', 24)
font3 = ImageFont.truetype(r'Segoe UI.ttf', 24)

power_text.draw_text(
    img,
    (10, 10),  # Starting xy coordinates

    """
皆さん✨、我在インターネット上看到someone把几国language混在一起speak🌍。我看到之后be like：それは我じゃないか！😂 私もtry一tryです🎉。虽然是混乱している句子ですけど、中文日本語プラスEnglish、挑戦スタート🚀！  

我study📖日本語的时候，もし有汉字，我会很happy😊。Bueause中国人として、when I see汉字，すぐに那个汉字がわかります✨。But 我hate😤外来語、什么マクドナルド🍔、スターバックス☕、グーグル🔍、ディズニーランド🏰、根本记不住カタカナhow to写、太難しい😭。  

以上です✌️，byebye👋！

awa
    """.strip(),
    [
        # Match Latin characters and numbers, use font3 (Segoe UI), color default
        power_text.Font(font3, lambda char: char.lower() in "abcdefghijklmnopqrstuvwxyz0123456789"),
        # Match Japanese Hiragana/Katakana, use font2 (unifont), color blue
        power_text.Font(font2, lambda char: jap.match(char) is not None, (22, 125, 255)),
        # Fallback for other characters (like CJK), use font1 (PingFang), color red
        power_text.Font(font1, lambda _: True, (220, 20, 60))
    ],
    (0, 0, 0),  # Default font color (black)
    max_x=886,  # Maximum width (auto line wrap if exceeded)
    max_y=200,  # Maximum height (auto truncation if exceeded)
    has_emoji=True,  # Enable emoji support
    end_text="..."  # Truncation symbol
)
img.show()
```

### Tips:  
By default, the emoji source is online (`Twemoji`), which may be slow to access in some regions. You can use a local source instead:
```python
import power_text
from power_text import local_emoji_source
power_text.draw_text(
    ...,
    emoji_source=local_emoji_source.LocalEmojiSource(r"path/to/your/noto-emoji-main/png/128") # Replace with your actual path
)
```
To set the `emoji_source`, provide the path to the local folder containing emoji images (e.g., PNGs). You can obtain emoji images from Google's [Noto Emoji project](https://github.com/googlefonts/noto-emoji/tree/main/png). Download the `png` folder for a specific resolution (like `128`) to your local machine and point `LocalEmojiSource` to that directory.

The output of the above code looks like this([Draw code](example.py)):  

![image](https://cdn.jsdelivr.net/gh/xiaosuyyds/PowerText@master/example.png)

## Use Cases

 - [murainbot-plugin-codeshare](https://github.com/xiaosuyyds/murainbot-plugin-codeshare/) Uses PowerText for multi-color code rendering.

## License

Copyright 2025 Xiaosu.

Distributed under the terms of the [Apache 2.0 license](https://github.com/xiaosuyyds/PowerText/blob/master/LICENSE).
