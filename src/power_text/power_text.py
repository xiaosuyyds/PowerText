# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/xiaosuyyds/PowerText/blob/master/NOTICE

from PIL import Image, ImageFont, ImageDraw
from typing import Callable, List, Tuple, Optional

try:
    import pilmoji
    import emoji
    from pilmoji import Pilmoji
except ImportError:
    pilmoji = None
    Pilmoji = None
    emoji = None
except AttributeError as e:
    if str(e) == "module 'emoji.unicode_codes' has no attribute 'get_emoji_unicode_dict'":
        raise AttributeError("Please downgrade emoji to ~=1.6.3: pip install emoji~=1.6.3 -U\n"
                             "see https://github.com/carpedm20/emoji/issues/221#issuecomment-1199857533")
    raise e


class Font:
    def __init__(self, font: ImageFont.FreeTypeFont | str, matcher: Callable[[str], bool]):
        """
        初始化字体对象。
        :param font: 传入的字体对象或字符串（用于 emoji）
        :param matcher: 用于匹配文本字符的回调函数
        """
        self._font: ImageFont.FreeTypeFont = font
        self.matcher_func: Callable[[str], bool] = matcher

    def matcher(self, text: str) -> bool:
        """
        判断文本是否匹配该字体。
        :param text: 输入文本
        :return: 匹配返回 True，否则返回 False
        """
        return self.matcher_func(text)

    @property
    def font(self) -> ImageFont.FreeTypeFont:
        """
        获取字体对象，如果是 emoji，则返回默认字体。
        :return: 字体对象
        """
        return ImageFont.load_default() if self._font == "emoji" else self._font

    @property
    def is_emoji(self) -> bool:
        """
        判断该字体是否是 emoji。
        :return: 如果是 emoji 返回 True，否则返回 False
        """
        return self._font == "emoji"

    def get_size(self, text: str, has_emoji: bool = True) -> tuple[int, int]:
        """
        获取文本尺寸。
        :param text: 输入文本
        :param has_emoji: 是否包含 emoji
        :return: 文本宽度和高度
        """
        if has_emoji and pilmoji and Pilmoji:  # 检查 pilmoji 是否可用
            font = None if self.is_emoji else self.font
            return pilmoji.getsize(text, font)
        else:
            text_l, text_t, text_r, text_b = self.font.getbbox(text)
            return int(text_r - text_l), int(text_b - text_t)


def _parse_text_segments(text: str, fonts: List[Font], has_emoji: bool) -> List[Tuple[str, Font, bool]]:
    """
    解析文本，将其拆分为不同的字体片段。
    :param text: 输入文本
    :param fonts: 字体列表
    :param has_emoji: 是否处理 emoji
    :return: 文本片段列表，每个片段包含 (文本, 字体对象, 是否是 emoji)
    """
    text_segments: List[Tuple[str, Font, bool]] = []
    if has_emoji:
        if not emoji:
            raise ImportError("If the rendering has text with emoji, install emoji: pip install emoji")
        fonts.insert(0, Font("emoji", emoji.is_emoji))  # 处理 emoji

    for char in text:
        for font in fonts:
            if font.matcher(char):
                if not font.is_emoji:
                    # 处理连续相同字体的文本
                    if (text_segments and (text_segments[-1][1] == font or text_segments[-1][1].is_emoji) and
                            char != '\n' and text_segments[-1][0] != '\n'):
                        text_segments[-1] = (text_segments[-1][0] + char, font, text_segments[-1][2])
                    else:
                        text_segments.append((char, font, False))
                else:
                    # 处理 emoji
                    if text_segments and text_segments[-1][0] != '\n':
                        text_segments[-1] = (text_segments[-1][0] + char, text_segments[-1][1], True)
                    else:
                        text_segments.append((char, font, True))
                break
        else:
            raise ValueError(f'未找到匹配的字体: {char}')
    return text_segments


def draw_text(img: Image.Image, xy: tuple[int, int], text: str, fonts: List[Font],
              color: tuple[int, int, int], max_x: int = -1, max_y: int = -1, max_line: int = -1,
              end_text: str = "", end_text_font: Optional[Font] = None,
              line_height: int = -1,
              has_emoji: bool = True, emoji_source=None):
    """
    在图像上绘制文本，并支持 多字体与emoji。
    :param img: PIL 图像对象
    :param xy: 文本起始坐标 (x, y)
    :param text: 要绘制的文本
    :param fonts: 字体列表，按照匹配规则选择字体
    :param color: 文本颜色 (R, G, B)
    :param max_x: 文本最大宽度，超出换行，-1 表示不限制
    :param max_y: 文本最大高度，超出停止绘制，-1 表示不限制
    :param max_line: 最大行数，超出停止绘制，-1 表示不限制
    :param end_text: 超出最大行数时，结尾添加绘制文本，默认为 ""，不支持emoji
    :param end_text_font: 超出最大行数时，结尾添加绘制文本的字体，默认为 None，表示使用fonts内最后一个字体
    :param line_height: 行高，-1 表示自动计算
    :param has_emoji: 是否处理 emoji
    :param emoji_source: emoji 来源
    """
    text_segments = _parse_text_segments(text, fonts, has_emoji)

    # 自动计算行高
    if line_height == -1:
        for text, text_font, _ in text_segments:
            _, text_h = text_font.get_size(text, has_emoji)
            if not text_font.is_emoji:
                line_height = max(text_h + text_font.font.getmetrics()[1], line_height)
            else:
                line_height = max(text_h, line_height)
        if line_height == 0:
            line_height = 10  # 异常情况下的默认行高

    end_text_draw_font = end_text_font.font if isinstance(end_text_font, Font) else (end_text_font or fonts[-1].font)
    end_text_w = end_text_draw_font.getlength(end_text)

    if max_x != -1 and end_text_w > max_x - xy[0]:
        raise ValueError("end_text_font too long")
    else:
        if max_x != -1 and end_text_w * 1.5 > max_x - xy[0]:
            end_text_w *= 1.5

    draw = ImageDraw.Draw(img)
    if has_emoji:
        if not Pilmoji:
            raise ImportError("If the rendering has text with emoji, install pilmoji: pip install pilmoji")

        pilmoji_instance = Pilmoji(img, source=emoji_source)
    else:
        pilmoji_instance = None

    now_x, now_y = xy
    last_x, last_y = xy
    last_text_w = 0
    line_index = 1
    i = 0
    while i < len(text_segments):
        text, text_font, is_emoji_segment = text_segments[i]
        is_enter = False

        # 处理换行逻辑
        if max_x != -1 and text_font.get_size(text)[0] > max_x - now_x or text == '\n':
            # 二分查找找出最大能写下的部分
            if text != '\n':
                left, right = 0, len(text) - 1
                best_index = 0
                while left < right:
                    m = (left + right + 1) // 2
                    if (
                            text_font.get_size(text[:m], has_emoji and is_emoji_segment)[0] <
                            (max_x - now_x
                             if (max_line == -1 or max_line != line_index) and
                                (max_y == -1 or now_y + line_height * 2 < max_y)
                             else max_x - now_x - end_text_w)
                    ):
                        left = m
                        best_index = m
                    else:
                        right = m - 1

                current_text = text[:best_index]
                remaining_text = text[best_index:]
                # 将剩余文本添加回text_segments
                text_segments[i] = (remaining_text, text_font, True
                                    if has_emoji and emoji.is_emoji(remaining_text) is not None else False)
                text = current_text  # 使用截断后的文本

            is_enter = True

        if (max_y != -1 and now_y + line_height > max_y) or (max_line != -1 and line_index > max_line):
            if len(end_text):
                if isinstance(end_text_font, Font):
                    end_text_font = end_text_font.font
                if end_text_font is None:
                    end_text_font = fonts[-1].font
                draw.text((last_x + last_text_w, last_y), end_text, color, font=end_text_font)
            break

        if is_emoji_segment and pilmoji_instance:
            pilmoji_instance.text((now_x, now_y), text, color,
                                  font=text_font.font if not text_font.is_emoji else None)
        else:
            draw.text((now_x, now_y), text, color, font=text_font.font)

        last_x, last_y = now_x, now_y
        last_text_w = text_font.get_size(text, has_emoji)[0]
        now_x += last_text_w

        if is_enter and text != '\n':  # 换行条件判断合并
            now_x = xy[0]
            now_y += line_height
            line_index += 1
        elif text == '\n':
            now_x = xy[0]
            now_y += line_height
            i += 1
            line_index += 1
        else:
            i += 1

    if pilmoji_instance:
        pilmoji_instance.close()  # 统一关闭 pilmoji 实例
