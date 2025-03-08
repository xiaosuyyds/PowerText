# PowerText

| [English](https://github.com/xiaosuyyds/PowerText/blob/master/README.md) | 简体中文 |


## 📖介绍
PowerText是一个Pillow的支持emoji、多字体、自动换行和自动省略的文本绘制器

## ⬇️安装
```bash
python -m pip install PowerText
```
当然你也可以从源码安装
```bash
git clone https://github.com/xiaosuyyds/PowerText.git
python -m pip install .
```

#### 注意！ 默认情况下仅安装必要的依赖，如果需要使用emoji的绘制，请安装

```bash
python -m pip install PowerText[full]
```
或
```bash
git clone https://github.com/xiaosuyyds/PowerText.git
python -m pip install .[full]
```

## 🧑‍💻食用方法
### 示例代码
```python
import power_text
import re
from PIL import Image, ImageFont

jap = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')

img = Image.new("RGB", (1150, 630), (255, 255, 255))
font1 = ImageFont.truetype(r'SmileySans-Oblique.ttf', 24)
font2 = ImageFont.truetype(r'PINGFANG MEDIUM.TTF', 24)
font3 = ImageFont.truetype(r'unifont-16.0.02.otf', 24)
font4 = ImageFont.truetype(r'Segoe UI.ttf', 24)


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
        power_text.Font(font4, lambda char: char.lower() in "abcdefghijklmnopqrstuvwxyz0123456789"),
        power_text.Font(font3, lambda char: jap.match(char) is not None),
        power_text.Font(font2, lambda _: True)
    ],
    (0, 0, 0),  # 字体颜色
    max_x=886,  # 最大宽度（超过自动换行）
    max_y=200,  # 最大高度（超过自动省略）
    has_emoji=True,  # 启用emoji
    end_text="..."  # 省略符号
)
img.show()
```

### tips:
默认emoji源是使用在线的，在部分地区访问速度很慢，可以使用
```python
import power_text
from power_text import local_emoji_source
power_text.draw_text(
    ...,
    emoji_source=local_emoji_source.LocalEmojiSource(r"noto-emoji-main\png\128")
)
```
设置emoji_source的方法，LocalEmojiSource内需要填写本地存放emoji图片文件夹的路径，具体的emoji图片来源可以使用[这个项目](https://github.com/googlefonts/noto-emoji/tree/main/png)内的emoji图片，将任意一个分辨率的文件夹下载到本地即可。

上述代码的效果如下

![image](https://cdn.jsdelivr.net/gh/xiaosuyyds/PowerText@master/example.png)
