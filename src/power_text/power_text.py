# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/xiaosuyyds/PowerText/blob/master/NOTICE

import dataclasses
import weakref

from PIL import Image, ImageFont, ImageDraw
from typing import Callable, List, Tuple, Optional, NamedTuple
from fontTools.ttLib import TTFont

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

font_cache = weakref.WeakValueDictionary()


@dataclasses.dataclass
class FontMatcherResult:
    color: tuple[int, int, int] | None = None


@dataclasses.dataclass
class TextSegment:
    text: str
    font: "Font"
    is_emoji: bool
    color: tuple[int, int, int] | None = None


def check_has_char(char: str, font_uni_map):
    if ord(char) in font_uni_map.keys():
        return True
    else:
        return False


class Font:
    def __init__(self, font: ImageFont.FreeTypeFont, matcher: Callable[[str], bool | FontMatcherResult],
                 color: tuple[int, int, int] | None = None,
                 is_emoji: bool = False,
                 check_has_char_func: Callable[[str, ImageFont.FreeTypeFont], bool] = check_has_char):
        """
        初始化字体对象。
        :param font: 传入的字体对象或字符串
        :param matcher: 用于匹配文本字符的回调函数，可返回True或FontMatcherResult表示匹配，FontMatcherResult的内容可以修改部分绘制样式
        :param color: 字体颜色，默认使用draw_text的颜色
        :param is_emoji: 是否是 emoji
        :param check_has_char_func: 检查字符是否在字体中的函数
        """
        self._font: ImageFont.FreeTypeFont = font
        self.matcher_func: Callable[[str], bool] = matcher
        self._is_emoji: bool = is_emoji
        self.color: tuple[int, int, int] | None = color

        self.check_has_char_func = check_has_char_func
        if self.check_has_char_func == check_has_char:
            font_ = font_cache.get(font.path, TTFont(font.path, lazy=True))
            font_cache[font.path] = font_
            self.fonttools_font = font_
            self.font_uni_map = self.fonttools_font['cmap'].tables[0].ttFont.getBestCmap()

    def check_has_text(self, text: str):
        if self.check_has_char_func == check_has_char:
            return all(check_has_char(char, self.font_uni_map) for char in text)
        else:
            return all(self.check_has_char_func(char, self.font) for char in text)

    def matcher(self, text: str) -> bool | FontMatcherResult:
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


def _parse_text_segments(text: str | list[dict], fonts: List[Font], has_emoji: bool, max_x: int = -1,
                         font_fallback: bool = True) \
        -> Tuple[List[TextSegment], List[Font], dict[Font, int]]:
    """
    解析文本，将其拆分为不同的字体片段。
    :param text: 输入文本
    :param fonts: 字体列表
    :param has_emoji: 是否处理 emoji
    :param max_x: 最大宽度，超出换行，-1 表示不限制
    :param font_fallback: 是否使用字体回退，默认为 True，如果启用则如果匹配的字体没有所需字符则使用下一个匹配的字符，如果都没有则使用第一个匹配的字符进行绘制
    :return: 文本片段列表，每个片段包含，用到的字体，字体的高度
    """

    if isinstance(text, list):
        text_ = []
        for i in text:
            for j in i['text']:
                text_.append({'text': j, **{k: i[k] for k in i if k != 'text'}})
        text = text_

    fonts = fonts[:]

    fonts_y_line_height = {}
    line_height = -1
    for font in fonts:
        fonts_y_line_height[font] = sum(font.font.getmetrics())
        line_height = max(line_height, font.font.getmetrics()[0])

    text_segments: List[TextSegment] = []
    if has_emoji:
        if not emoji:
            raise ImportError("If the rendering has text with emoji, install emoji: pip install emoji")
        # 处理 emoji
        if isinstance(text, list):
            fonts.insert(0,
                         Font(ImageFont.load_default(line_height), lambda x: emoji.is_emoji(x['text']), is_emoji=True))
        else:
            fonts.insert(0, Font(ImageFont.load_default(line_height), emoji.is_emoji, is_emoji=True))
        fonts_y_line_height[fonts[0]] = line_height
    used_fonts = set()
    if max_x != -1:
        char_x = max(*[-1] + [int(f.font.size * 1.5) for f in fonts])
        max_char = max_x // char_x
    else:
        char_x = 0
        max_char = 0

    for char_ in text:
        first_match_font = None
        for i in range(len(fonts)):
            font = fonts[i]
            font_matcher_result = font.matcher(char_)
            if font_matcher_result is True or isinstance(font_matcher_result, FontMatcherResult):
                if font_matcher_result is True:
                    font_matcher_result = FontMatcherResult()
                if not first_match_font:
                    first_match_font = font, i, font_matcher_result

                if font_fallback and not font.check_has_text(char_['text'] if isinstance(char_, dict) else char_):
                    continue
                break
        else:
            if first_match_font and font_fallback:
                # 有匹配的字体但是都没有该字符
                font, i, font_matcher_result = first_match_font
            else:
                raise ValueError(f'未找到匹配的字体: {char_}')

        char = char_['text'] if isinstance(char_, dict) else char_

        if not font.is_emoji:
            # 处理连续相同字体的文本
            if (
                    text_segments and
                    (
                            text_segments[-1].font == font
                            and not text_segments[-1].is_emoji
                            and (
                                    text_segments[-1].color or text_segments[-1].font.color
                            ) == (
                                    font_matcher_result.color or font.color
                            )
                    ) and
                    char != '\n' and text_segments[-1].text != '\n'
            ):
                if max_x != -1 and len(text_segments[-1].text + char) > max_char:
                    # 超大长度文本处理换行缓慢，提前拆分成多节
                    text_segments.append(TextSegment(char, font, False, font_matcher_result.color))
                else:
                    text_segments[-1] = TextSegment(
                        text_segments[-1].text + char, font, text_segments[-1].is_emoji, text_segments[-1].color
                    )
            else:
                text_segments.append(TextSegment(char, font, False, font_matcher_result.color))
        else:
            # 处理 emoji
            if text_segments and text_segments[-1].is_emoji:
                if (max_x != -1 and max_x < char_x * len(char) and
                        fonts_y_line_height[text_segments[-1].font] == line_height):
                    # 超大长度文本处理换行缓慢，提前拆分成多节
                    text_segments.append(TextSegment(char, font, True))
                else:
                    text_segments[-1] = TextSegment(
                        text_segments[-1].text + char, text_segments[-1].font, True
                    )
            else:
                text_segments.append(
                    TextSegment(char, font, True)
                )
        used_fonts.add(i)

    return text_segments, [fonts[i] for i in used_fonts], fonts_y_line_height


class DrawResult(NamedTuple):
    final_pos: tuple[int, int]  # 绘制结束后光标的位置
    bbox: tuple[int, int, int, int]  # 文本绘制的实际边界框 (x, y, width, height)
    lines: int  # 绘制的总行数
    truncated: bool  # 文本是否因限制被截断
    line_height_used: int  # 实际使用的行高
    last_segment: TextSegment  # 最后一个绘制的文本内容


def draw_text(img: Image.Image, xy: tuple[int, int], text: str | list[dict], fonts: List[Font],
              color: tuple[int, int, int],
              max_x: int = -1, max_y: int = -1, max_line: int = -1,
              end_text: str = "", end_text_font: Optional[Font] = None,
              line_height: int = -1, fast_get_line_height: bool = True, guess_line_breaks: bool = True,
              auto_font_y_offset: bool = True,
              has_emoji: bool = True, emoji_source=None,
              font_fallback: bool = True,
              wrap_indent: int | str = 0) -> DrawResult:
    """
    在图像上绘制文本，并支持 多字体与emoji。
    :param img: PIL 图像对象
    :param xy: 文本起始坐标 (x, y)
    :param text: 要绘制的文本，也可以传入一个 list[dict]，其中每个 dict 内必须包含 "text" 字段，内容为要绘制的文本，
    其他字段不限，可用于font的mather的判断，不可混排（一会dict一会str）
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
    :param font_fallback: 是否使用字体回退，默认为 True，如果启用则如果匹配的字体没有所需字符则使用下一个匹配的字符，如果都没有则使用第一个匹配的字符进行绘制
    :param wrap_indent: 换行缩进，可为字符串也可为数字，字符串代表换行时开头的字符，数字代表换行时便宜的宽度
    :return: DrawResult
    """
    if has_emoji:
        if not Pilmoji:
            raise ImportError("If the rendering has text with emoji, install pilmoji: pip install pilmoji")
        if emoji_source is not None:
            pilmoji_instance = Pilmoji(img, source=emoji_source)
        else:
            pilmoji_instance = Pilmoji(img)
    else:
        pilmoji_instance = None

    text_segments, fonts, fonts_y_line_height = _parse_text_segments(text, fonts, has_emoji, max_x, font_fallback)

    # 自动计算行高
    if line_height == -1:
        if fast_get_line_height:
            for font in fonts_y_line_height:
                if font.is_emoji:
                    continue
                line_height = max(line_height, fonts_y_line_height[font])
        else:
            fonts_y_line_height = {}
            for segment in text_segments:
                text, text_font = segment.text, segment.font
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

    guess_cache = {}
    last_segment = None  # 最后一个绘制的文本内容
    lines_drawn = 1  # 绘制的行数
    lines_drawn_flag = False  # 是否要在下一次循环时增加lines_drawn的标志
    start_x, start_y = xy  # 绘制起始位置
    now_x, now_y = start_x, start_y  # 当前的绘制位置
    last_x, last_y = start_x, start_y  # last_y 记录绘制时的基线 Y
    last_text_w = 0  # 最后一个绘制的文本宽度
    line_index = 1  # 当前行数
    i = 0  # 遍历索引
    max_reached_x = start_x  # 跟踪最大 X 坐标
    truncated = False  # 是否因限制被截断
    something_drawn = False  # 是否实际绘制过内容

    while i < len(text_segments):
        text, text_font, is_emoji_segment, text_color = (text_segments[i].text, text_segments[i].font,
                                                         text_segments[i].is_emoji, text_segments[i].color)
        text = str(text)
        is_enter = False

        target_max_x = (max_x - now_x if (max_line == -1 or max_line != line_index) and
                                         (max_y == -1 or now_y + line_height * 2 < max_y)
                        else max_x - now_x - end_text_w)
        # 处理换行逻辑
        if (
                max_x != -1 and
                (
                        text_font.get_size(text, has_emoji and is_emoji_segment)[0] > target_max_x or
                        text == '\n'
                )
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
                text_segments[i] = TextSegment(
                    remaining_text, text_font,
                    has_emoji and emoji.is_emoji(remaining_text),
                    text_color
                )

                # 如果设置了wrap_indent，则将wrap_indent添加到text_segments中
                if isinstance(wrap_indent, str):
                    text_segments.insert(i, TextSegment(wrap_indent, text_font, False, text_color))

                text = current_text  # 使用截断后的文本

            is_enter = True

        # 判断是否超出最大高度或者最大行数
        if (max_y != -1 and now_y + line_height > max_y) or (max_line != -1 and line_index > max_line):
            # 绘制尾部文本（如果有）
            if len(end_text):
                if isinstance(end_text_font, Font):
                    end_text_font = end_text_font.font
                if end_text_font is None:
                    end_text_font = fonts[-1].font
                draw.text((last_x + last_text_w, last_y), end_text, color, font=end_text_font)
                max_reached_x = max(max_reached_x, last_x + end_text_draw_font.getlength(end_text))
            truncated = True
            break

        # 计算y坐标偏移
        if auto_font_y_offset:
            y_offset = (line_height - fonts_y_line_height[text_font]) // 2
        else:
            y_offset = 0

        # 绘制文本
        if is_emoji_segment and pilmoji_instance:
            if text_font.color or text_color:
                pilmoji_instance.text((now_x, now_y + y_offset), text, text_color or text_font.color,
                                      font=text_font.font)
            else:
                pilmoji_instance.text((now_x, now_y + y_offset), text, color, font=text_font.font)
        else:
            if text_font.color or text_color:
                draw.text((now_x, now_y + y_offset), text, text_color or text_font.color, font=text_font.font)
            else:
                draw.text((now_x, now_y + y_offset), text, color, font=text_font.font)

        # 更新变量
        last_x, last_y = now_x, now_y

        something_drawn = True
        last_segment = text_segments[i]  # 更新最后绘制的 segment
        segment_width = text_font.get_size(text, has_emoji)[0]
        last_text_w = segment_width  # 记录本段宽度
        now_x += segment_width
        max_reached_x = max(max_reached_x, now_x)  # 更新最大 X

        # 更新实际绘制行数
        if lines_drawn_flag:
            lines_drawn += 1
            lines_drawn_flag = False

        # 更新行数、索引、绘制位置
        if text == '\n':
            now_x = xy[0]
            now_y += line_height
            i += 1
            line_index += 1
            lines_drawn_flag = True
        elif is_enter:
            now_x = xy[0]
            now_y += line_height
            line_index += 1
            lines_drawn_flag = True
            if isinstance(wrap_indent, int):
                now_x += wrap_indent
        else:
            i += 1

    if pilmoji_instance:
        pilmoji_instance.close()  # 统一关闭 pilmoji 实例

    if not something_drawn:
        final_bbox = (start_x, start_y, 0, 0)
    else:
        bbox_width = max_reached_x - start_x
        # 高度 = 最后绘制行的基线 + 行高 - 起始 Y
        bbox_height = (last_y + line_height) - start_y
        final_bbox = (start_x, start_y, bbox_width, bbox_height)

    return DrawResult(
        final_pos=(now_x, now_y),
        bbox=final_bbox,
        lines=lines_drawn,
        truncated=truncated,
        line_height_used=line_height,
        last_segment=last_segment
    )
