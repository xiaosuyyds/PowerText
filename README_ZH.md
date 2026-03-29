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

## 🧑‍💻食用方法
### 示例代码
```python
import power_text
import re
from PIL import Image, ImageFont
import emoji

jap = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')

img = Image.new("RGB", (1150, 630), (255, 255, 255))
# 注意：请确保你有这些字体文件，或替换为你本地的字体路径
font1 = ImageFont.truetype(r'PINGFANG MEDIUM.TTF', 24)
font2 = ImageFont.truetype(r'unifont-16.0.02.otf', 24)
font3 = ImageFont.truetype(r'Segoe UI.ttf', 24)
# noto color emoji等部分字体需要注意字体尺寸，否则可能无法正常加载
font_emoji = ImageFont.truetype("NotoColorEmoji.ttf", 109)


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
        # 匹配拉丁字符和数字，使用 font3 (Segoe UI)，颜色默认
        power_text.Font(font3, lambda data: data['text'].lower() in "abcdefghijklmnopqrstuvwxyz0123456789"),
        # 匹配日文假名，使用 font2 (unifont)，颜色蓝色
        power_text.Font(font2, lambda data: jap.match(data['text']) is not None, (22, 125, 255)),
        # 匹配emoji，使用font_emoji(noto color emoji)，设置 size 实现自动缩放
        power_text.Font(font_emoji, lambda data: emoji.is_emoji(data['text']), size=24),
        # 其他字符（如中日韩汉字）的回退选项，使用 font1 (PingFang)，颜色红色
        power_text.Font(font1, lambda _: True, (220, 20, 60))
    ],
    (0, 0, 0),  # 默认字体颜色（黑色）
    max_x=886,  # 最大宽度（超过自动换行）
    max_y=200,  # 最大高度（超过自动省略）
    end_text="..."  # 省略符号
)
img.show()
```

上述代码的效果如下([绘制代码](example.py))

![image](https://cdn.jsdelivr.net/gh/xiaosuyyds/PowerText@master/example.png)

## 使用案例

 - [murainbot-plugin-codeshare](https://github.com/xiaosuyyds/murainbot-plugin-codeshare/) 使用PowerText进行多颜色的代码渲染。

## 许可证

版权所有 2025-2026 Xiaosu。

根据 [MPL 2.0 许可证](https://github.com/xiaosuyyds/PowerText/blob/master/LICENSE) 的条款分发。
