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
    def __init__(self, font: ImageFont.FreeTypeFont, matcher: Callable[[str], bool], is_emoji: bool = False):
        """
        初始化字体对象。
        :param font: 传入的字体对象或字符串
        :param matcher: 用于匹配文本字符的回调函数
        :param is_emoji: 是否是 emoji
        """
        self._font: ImageFont.FreeTypeFont = font
        self.matcher_func: Callable[[str], bool] = matcher
        self._is_emoji: bool = is_emoji

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
        return self._font

    @property
    def is_emoji(self) -> bool:
        """
        判断该字体是否是 emoji。
        :return: 如果是 emoji 返回 True，否则返回 False
        """
        return self._is_emoji

    def get_size(self, text: str, has_emoji: bool = True) -> tuple[int, int]:
        """
        获取文本尺寸。
        :param text: 输入文本
        :param has_emoji: 是否包含 emoji
        :return: 文本宽度和高度
        """
        if has_emoji and pilmoji and Pilmoji:  # 检查 pilmoji 是否可用
            return pilmoji.getsize(text, font=self.font)
        else:
            text_l, text_t, text_r, text_b = self.font.getbbox(text)
            return int(text_r - text_l), int(text_b - text_t)


def _parse_text_segments(text: str, fonts: List[Font], has_emoji: bool, max_x: int = -1) \
        -> Tuple[List[Tuple[str, Font, bool]], List[Font], dict[Font, int]]:
    """
    解析文本，将其拆分为不同的字体片段。
    :param text: 输入文本
    :param fonts: 字体列表
    :param has_emoji: 是否处理 emoji
    :param max_x: 最大宽度，超出换行，-1 表示不限制
    :return: 文本片段列表，每个片段包含 (文本, 字体对象, 是否是 emoji)，用到的字体，字体的高度
    """
    fonts = fonts[:]

    fonts_y_line_height = {}
    line_height = -1
    for font in fonts:
        fonts_y_line_height[font] = sum(font.font.getmetrics())
        line_height = max(line_height, font.font.getmetrics()[0])

    text_segments: List[Tuple[str, Font, bool]] = []
    if has_emoji:
        if not emoji:
            raise ImportError("If the rendering has text with emoji, install emoji: pip install emoji")
        fonts.insert(0, Font(ImageFont.load_default(line_height), emoji.is_emoji, True))  # 处理 emoji
        fonts_y_line_height[fonts[0]] = line_height
    used_fonts = set()
    if max_x != -1:
        char_x = max(*[-1] + [int(f.font.size * 1.5) for f in fonts])
        max_char = max_x // char_x
    else:
        char_x = 0
        max_char = 0

    for char in text:
        for i in range(len(fonts)):
            font = fonts[i]
            if font.matcher(char):
                if not font.is_emoji:
                    # 处理连续相同字体的文本
                    if (
                            text_segments and
                            (text_segments[-1][1] == font and not text_segments[-1][2]) and
                            char != '\n' and text_segments[-1][0] != '\n'
                    ):
                        if max_x != -1 and len(text_segments[-1][0] + char) > max_char:
                            # 超大长度文本处理换行缓慢，提前拆分成多节
                            text_segments.append((char, font, False))
                        else:
                            text_segments[-1] = (text_segments[-1][0] + char, font, text_segments[-1][2])
                    else:
                        text_segments.append((char, font, False))
                else:
                    # 处理 emoji
                    if text_segments and text_segments[-1][2]:
                        if (max_x != -1 and max_x < char_x * len(char) and
                                fonts_y_line_height[text_segments[-1][1]] == line_height):
                            # 超大长度文本处理换行缓慢，提前拆分成多节
                            text_segments.append((char, font, True))
                        else:
                            text_segments[-1] = (text_segments[-1][0] + char, text_segments[-1][1], True)
                    else:
                        text_segments.append((char, font, True))
                used_fonts.add(i)
                break
        else:
            raise ValueError(f'未找到匹配的字体: {char}')
    return text_segments, [fonts[i] for i in used_fonts], fonts_y_line_height


def draw_text(img: Image.Image, xy: tuple[int, int], text: str, fonts: List[Font], color: tuple[int, int, int],
              max_x: int = -1, max_y: int = -1, max_line: int = -1,
              end_text: str = "", end_text_font: Optional[Font] = None,
              line_height: int = -1, fast_get_line_height: bool = True, guess_line_breaks: bool = True,
              auto_font_y_offset: bool = True,
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
    :param fast_get_line_height: 是否使用快速计算行高，默认为 True，如果包含特殊字符，则可关闭以优化效果
    :param guess_line_breaks: 是否使用猜测换行字符长度优化换行速度，默认为 True，如果单行文本数量较少可以关闭（如果文本数量较少可能会导致负优化）
    :param auto_font_y_offset: 是否自动计算字体 Y 轴偏移，默认为 True，如果字体大小一样或不在乎细节可以关闭以优化性能（不过性能损失也不大）
    :param has_emoji: 是否处理 emoji
    :param emoji_source: emoji 来源
    """
    if has_emoji:
        if not Pilmoji:
            raise ImportError("If the rendering has text with emoji, install pilmoji: pip install pilmoji")

        pilmoji_instance = Pilmoji(img, source=emoji_source)
    else:
        pilmoji_instance = None

    text_segments, fonts, fonts_y_line_height = _parse_text_segments(text, fonts, has_emoji, max_x)

    # 自动计算行高
    if line_height == -1:
        if fast_get_line_height:
            for font in fonts_y_line_height:
                if font.is_emoji:
                    continue
                line_height = max(line_height, fonts_y_line_height[font])
        else:
            fonts_y_line_height = {}
            for text, text_font, _ in text_segments:
                _, text_h = text_font.get_size(text, has_emoji)
                fonts_y_line_height[text_font] = text_h if text_font.is_emoji else (
                        text_h + text_font.font.getmetrics()[1])
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

    now_x, now_y = xy
    last_x, last_y = xy
    last_text_w = 0
    line_index = 1
    i = 0
    guess_cache = {}

    while i < len(text_segments):
        text, text_font, is_emoji_segment = text_segments[i]
        is_enter = False

        target_max_x = (max_x - now_x if (max_line == -1 or max_line != line_index) and
                                         (max_y == -1 or now_y + line_height * 2 < max_y)
                        else max_x - now_x - end_text_w)
        # 处理换行逻辑
        if (
                max_x != -1 and
                text_font.get_size(text, has_emoji and is_emoji_segment)[0] > target_max_x or
                text == '\n'
        ):
            # 二分查找找出最大能写下的部分
            if text != '\n':
                left, right = 0, len(text) - 1
                best_index = 0

                if guess_line_breaks:
                    if text_font not in guess_cache:
                        guess_cache[text_font] = text_font.get_size("啊", has_emoji and is_emoji_segment)[0]

                    initial_guess = int(target_max_x // guess_cache[text_font])
                    if 0 <= initial_guess < len(text):
                        prefix_guess = text[:initial_guess]
                        sum_guess = text_font.get_size(prefix_guess, has_emoji and is_emoji_segment)[0]
                        if sum_guess < target_max_x:
                            left = initial_guess  # 猜测值可行，将下界设置为猜测值
                            right = min(initial_guess * 2, len(text))
                            best_index = initial_guess  # 初始最大长度可以先设置为猜测值
                        else:
                            right = initial_guess - 1  # 猜测值过大，将上界设置为猜测值-1

                while left < right:
                    mid = (left + right + 1) // 2
                    if (
                            text_font.get_size(text[:mid], has_emoji and is_emoji_segment)[0] < target_max_x
                    ):
                        left = mid
                        best_index = mid
                    else:
                        right = mid - 1

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

        if auto_font_y_offset:
            y_offset = (line_height - fonts_y_line_height[text_font]) // 2
        else:
            y_offset = 0

        if is_emoji_segment and pilmoji_instance:
            pilmoji_instance.text((now_x, now_y + y_offset), text, color,
                                  font=text_font.font)
        else:
            draw.text((now_x, now_y + y_offset), text, color, font=text_font.font)

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
