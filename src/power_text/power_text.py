# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import dataclasses
import weakref
import io
from functools import lru_cache
from typing import Callable, List, Tuple, Optional, NamedTuple, TypedDict

from PIL import Image, ImageFont, ImageDraw
from fontTools.ttLib import TTFont

font_uni_map_cache = weakref.WeakKeyDictionary()


@dataclasses.dataclass(slots=True)
class FontMatcherResult:
    color: tuple[int, int, int] | None = None


@dataclasses.dataclass(slots=True)
class TextSegment:
    text: str
    font: "Font"
    color: tuple[int, int, int] | None = None


class SegmentDict(TypedDict, total=False):
    text: str


def get_font_uni_map(font: ImageFont.FreeTypeFont):
    """
    全自动提取字体映射表：优先内存，次选路径。
    """
    data_bytes = getattr(font, "font_bytes", None)
    if data_bytes:
        return _extract_cmap_from_bytes(data_bytes, font)

    path = getattr(font, "path", None)
    if path:
        if isinstance(path, (str, bytes)):
            return _extract_cmap_from_path(path, font)
        elif hasattr(path, "read"):
            path.seek(0)
            return _extract_cmap_from_bytes(path.read(), font)

    return set()


def _extract_cmap_from_bytes(data: bytes, font: ImageFont.FreeTypeFont):
    """从二进制流提取 cmap"""
    try:
        with TTFont(io.BytesIO(data), lazy=True, fontNumber=font.index) as tt:
            return set(tt['cmap'].tables[0].ttFont.getBestCmap().keys())
    except Exception:
        return set()


def _extract_cmap_from_path(path: str, font: ImageFont.FreeTypeFont):
    """从文件路径提取 cmap"""
    try:
        with TTFont(path, lazy=True, fontNumber=font.index) as tt:
            return set(tt['cmap'].tables[0].ttFont.getBestCmap().keys())
    except Exception:
        return set()


@lru_cache(maxsize=1024)
def get_size(text: str, font: ImageFont.FreeTypeFont):
    """
    获取文本尺寸。
    :param text: 输入文本
    :param font: 字体对象
    :return: 文本宽度和高度
    """
    text_l, text_t, text_r, text_b = font.getbbox(text)
    return int(text_r - text_l), int(text_b - text_t)


@lru_cache(maxsize=8192)
def get_width(text: str, font: ImageFont.FreeTypeFont) -> int:
    return int(font.getlength(text))


class FontUniMapWrapper:
    def __init__(self, data):
        self.data = data


class Font:
    def __init__(
            self,
            font: ImageFont.FreeTypeFont,
            matcher: Callable[[SegmentDict], bool | FontMatcherResult],
            color: tuple[int, int, int] | None = None,
            size: int | None = None,
            check_has_char_func: Callable[[str, ImageFont.FreeTypeFont], bool] | None = None
    ):
        """
        初始化字体对象。
        :param font: 传入的字体对象或字符串
        :param matcher: 用于匹配文本字符的回调函数，可返回True或FontMatcherResult表示匹配，FontMatcherResult的内容可以修改部分绘制样式
        :param color: 字体颜色，默认使用draw_text的颜色
        :param size: 字体尺寸，如果和font不符，则会先绘制到临时画布再缩放
        :param check_has_char_func: 检查字符是否在字体中的函数
        """
        self._font: ImageFont.FreeTypeFont = font
        self.matcher_func: Callable[[SegmentDict], bool] = matcher
        self.color: tuple[int, int, int] | None = color
        self.size = size

        self.check_has_char_func = check_has_char_func
        if self.check_has_char_func is None:
            self.font_uni_map = font_uni_map_cache.get(
                font, FontUniMapWrapper(None)
            )
            font_uni_map_cache[font] = self.font_uni_map

    def check_has_text(self, text: str):
        if self.check_has_char_func is None:
            # 确保 cmap 数据已加载
            if self.font_uni_map.data is None:
                self.font_uni_map.data = get_font_uni_map(self.font)

            if len(text) == 1:
                return text in self.font_uni_map.data
            else:
                return set(text).issubset(self.font_uni_map.data)
        else:
            return all(self.check_has_char_func(char, self.font) for char in text)

    def matcher(self, text: SegmentDict) -> bool | FontMatcherResult:
        """
        判断文本是否匹配该字体。
        :param text: 输入文本
        :return: 匹配返回 True，否则返回 False
        """
        res = self.matcher_func(text)
        if res is True:
            res = FontMatcherResult()
        return res

    @property
    def font(self) -> ImageFont.FreeTypeFont:
        """
        获取字体对象
        :return: 字体对象
        """
        return self._font

    def get_size(self, text: str) -> tuple[int, int]:
        """
        获取文本尺寸。
        :param text: 输入文本
        :return: 文本宽度和高度
        """
        if self.size is None:
            return get_size(text, self.font)
        else:
            w, h = get_size(text, self.font)
            d = self.size / self.font.size
            return int(w * d), int(h * d)

    def get_width(self, text: str) -> int:
        """
        获取文本尺寸。
        :param text: 输入文本
        :return: 文本宽度和高度
        """
        if self.size is None:
            return get_width(text, self.font)
        else:
            return int(get_width(text, self.font) * (self.size / self.font.size))

    def get_metrics(self) -> tuple[int, int]:
        asc, desc = self.font.getmetrics()
        if self.size is not None:
            d = self.size / self.font.size
            return int(asc * d), int(desc * d)
        return asc, desc

    def __repr__(self):
        return f'<{self.__module__}.{self.__class__.__name__}({self.font}, {self.font.path}, {self.color})>'


def _parse_text_segments(
        text: str | list[SegmentDict],
        fonts: List[Font], max_x: int = -1,
        font_fallback: bool = True
) -> Tuple[List[TextSegment], List[Font], dict[Font, int]]:
    """
    解析文本，将其拆分为不同的字体片段。
    :param text: 输入文本
    :param fonts: 字体列表
    :param max_x: 最大宽度，超出换行，-1 表示不限制
    :param font_fallback: 是否使用字体回退，默认为 True，如果启用则如果匹配的字体没有所需字符则使用下一个匹配的字符，如果都没有则使用第一个匹配的字符进行绘制
    :return: 文本片段列表，每个片段包含，用到的字体，字体的高度
    """

    if isinstance(text, list):
        text_ = []
        for i in text:
            for j in i['text']:
                text_.append({**i, 'text': j})
        text = text_
    else:
        text = [{'text': _} for _ in text]

    fonts = fonts[:]

    fonts_y_line_height = {}
    line_height = -1
    for font in fonts:
        fonts_y_line_height[font] = sum(font.get_metrics())
        line_height = max(line_height, font.get_metrics()[0])

    text_segments: List[TextSegment] = []
    used_fonts = set()
    if max_x != -1:
        char_x = max(*[-1] + [int((f.size if f.size is not None else f.font.size) * 1.5) for f in fonts])
        max_char = max_x // char_x
    else:
        max_char = 0

    for char_ in text:
        first_match_font = None
        for i in range(len(fonts)):
            font = fonts[i]
            font_matcher_result = font.matcher(char_)
            if isinstance(font_matcher_result, FontMatcherResult):
                if not first_match_font:
                    first_match_font = font, i, font_matcher_result

                if font_fallback and not font.check_has_text(char_['text']):
                    continue
                break
        else:
            if first_match_font and font_fallback:
                # 有匹配的字体但是都没有该字符
                font, i, font_matcher_result = first_match_font
            else:
                raise ValueError(f'未找到匹配的字体: {char_}')

        char = char_['text']

        # 处理连续相同字体的文本
        if (
                text_segments and
                (
                        text_segments[-1].font == font
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
                text_segments.append(TextSegment(char, font, font_matcher_result.color))
            else:
                text_segments[-1] = TextSegment(
                    text_segments[-1].text + char, font, text_segments[-1].color
                )
        else:
            text_segments.append(TextSegment(char, font, font_matcher_result.color))
        used_fonts.add(i)

    return text_segments, [fonts[i] for i in used_fonts], fonts_y_line_height


def _find_split_index_smart(text: str, font, target_max_x: int, full_width: int) -> int:
    # 计算权重长度
    # 启发式规则：Unicode >= 0x1100 (包含韩文、日文、中文、Emoji) 视为宽字符(权重2)
    # 其他 (ASCII、拉丁文等) 视为窄字符(权重1)

    wide_count = sum(ord(c) >= 0x1100 for c in text)
    total_weight = len(text) + wide_count

    # 计算单位权重宽度，并得出目标权重
    unit_width = full_width / total_weight if total_weight > 0 else 1
    target_weight = target_max_x / unit_width

    # 寻找预测锚点
    current_weight = 0
    for i, c in enumerate(text):
        current_weight += 2 if ord(c) >= 0x1100 else 1
        if current_weight > target_weight:
            estimated_index = i
            break
    else:
        estimated_index = len(text)

    # 动态 Margin 逻辑
    margin = min(5, max(2, int(len(text) * 0.1)))

    # c = 0
    #
    # def get_width(text):
    #     nonlocal c
    #     c += 1
    #     return font.get_width(text)

    get_width = font.get_width

    # 测量预测点宽度
    actual_width = get_width(text[:estimated_index])

    # 线性探测

    # 计算差异对应的字符数
    avg_char_w = full_width / len(text) if len(text) > 0 else 1
    char_diff = (target_max_x - actual_width) / avg_char_w

    try:
        # 如果预测差异在 margin 之内，尝试线性探测
        if abs(char_diff) <= margin:
            count = 0
            if actual_width <= target_max_x:
                # 预测偏小，尝试向右线性找边界
                while count < margin and estimated_index < len(text):
                    actual_width = get_width(text[:estimated_index + 1])
                    if actual_width > target_max_x:
                        return estimated_index
                    estimated_index += 1
                    count += 1

                if count < margin:
                    return estimated_index

                left = estimated_index
                right = len(text)
            else:
                # 预测偏大，尝试向左线性找边界
                while count < margin and estimated_index > 0:
                    estimated_index -= 1
                    actual_width = get_width(text[:estimated_index])
                    if actual_width <= target_max_x:
                        return estimated_index
                    count += 1

                if count < margin:
                    return estimated_index

                left = 0
                right = estimated_index
        else:
            # 差异过大，直接根据当前测量值划定严谨二分边界
            if actual_width <= target_max_x:
                left = estimated_index
                right = len(text)
            else:
                left = 0
                right = estimated_index

        # 二分查找
        best_index = left
        while left <= right:
            mid = (left + right) // 2
            if mid == 0:  # 边界处理
                if get_width(text[:1]) > target_max_x:
                    return 0
                left = 1
                continue

            if get_width(text[:mid]) <= target_max_x:
                best_index = mid
                left = mid + 1
            else:
                right = mid - 1

        return best_index
    finally:
        pass
        # print(text, full_width, actual_width, estimated_index, target_max_x, c)


# def _find_split_index_smart(text: str, font, target_max_x: int, full_width: int) -> int:
#     # 计算权重长度
#     # 启发式规则：Unicode >= 0x1100 (包含韩文、日文、中文、Emoji) 视为宽字符(权重2)
#     # 其他 (ASCII、拉丁文等) 视为窄字符(权重1)
#
#     wide_count = sum(ord(c) >= 0x1100 for c in text)
#     total_weight = len(text) + wide_count
#
#     # 计算单位权重宽度，并得出目标权重
#     unit_width = full_width / total_weight if total_weight > 0 else 1
#     target_weight = target_max_x / unit_width
#
#     # 寻找预测锚点
#     current_weight = 0
#     for i, c in enumerate(text):
#         current_weight += 2 if ord(c) >= 0x1100 else 1
#         if current_weight > target_weight:
#             estimated_index = i
#             break
#     else:
#         estimated_index = len(text) - 1
#
#     # 计算动态容错边界 (Margin)
#     # 规则：最小 2 个字符，最大 10 个字符，或总长度的 10%
#     margin = min(10, max(2, int(len(text) * 0.1)))
#
#     # 初始化二分查找的极限边界
#     left = 0
#     right = len(text)
#
#     c = 0
#
#     def get_width(text):
#         nonlocal c
#         c += 1
#         return font.get_width(text)
#
#     # 测量预测点，并收缩二分查找的范围
#     actual_width = get_width(text[:estimated_index])
#
#     if actual_width <= target_max_x:
#         # 预测偏小：目标位置在 estimated_index 或其右侧
#         left = estimated_index
#         upper_bound_index = min(len(text), estimated_index + margin)
#
#         if get_width(text[:upper_bound_index]) > target_max_x:
#             right = upper_bound_index - 1
#         else:
#             left = upper_bound_index
#     else:
#         # 预测偏大：目标位置严格在 estimated_index 左侧
#         right = estimated_index - 1
#         lower_bound_index = max(0, estimated_index - margin)
#
#         if get_width(text[:lower_bound_index]) <= target_max_x:
#             left = lower_bound_index
#         else:
#             right = lower_bound_index - 1
#
#     # 二分查找
#     best_index = left
#     while left <= right:
#         mid = (left + right) // 2
#         if get_width(text[:mid]) <= target_max_x:
#             best_index = mid
#             left = mid + 1
#         else:
#             right = mid - 1
#
#     # print(text, full_width, actual_width, target_max_x, c)
#
#     return best_index


class DrawResult(NamedTuple):
    final_pos: tuple[int, int]  # 绘制结束后光标的位置
    bbox: tuple[int, int, int, int]  # 文本绘制的实际边界框 (x, y, width, height)
    lines: int  # 绘制的总行数
    truncated: bool  # 文本是否因限制被截断
    line_height_used: int  # 实际使用的行高
    last_segment: TextSegment  # 最后一个绘制的文本内容


def draw_text(
        img: Image.Image,
        xy: tuple[int, int],
        text: str | list[SegmentDict],
        fonts: List[Font],
        color: tuple[int, int, int],
        max_x: int = -1, max_y: int = -1, max_line: int = -1,
        end_text: str = "",
        end_text_font: Optional[Font] = None,
        line_height: int = -1, fast_get_line_height: bool = True, guess_line_breaks: bool = True,
        auto_font_y_offset: bool = True,
        font_fallback: bool = True,
        wrap_indent: int | str = 0
) -> DrawResult:
    """
    在图像上绘制文本，并支持 多字体。
    :param img: PIL 图像对象
    :param xy: 文本起始坐标 (x, y)
    :param text: 要绘制的文本，也可以传入一个 list[dict]，其中每个 dict 内必须包含 "text" 字段，内容为要绘制的文本，
    其他字段不限，可用于font的mather的判断，不可混排（一会dict一会str）
    :param fonts: 字体列表，按照匹配规则选择字体
    :param color: 文本颜色 (R, G, B)
    :param max_x: 文本最大宽度，超出换行，-1 表示不限制
    :param max_y: 文本最大高度，超出停止绘制，-1 表示不限制
    :param max_line: 最大行数，超出停止绘制，-1 表示不限制
    :param end_text: 超出最大行数时，结尾添加绘制文本，默认为 ""
    :param end_text_font: 超出最大行数时，结尾添加绘制文本的字体，默认为 None，表示使用fonts内最后一个字体
    :param line_height: 行高，-1 表示自动计算
    :param fast_get_line_height: 是否使用快速计算行高，默认为 True，如果包含特殊字符，则可关闭以优化效果
    :param guess_line_breaks: 是否使用猜测换行字符长度优化换行速度，默认为 True，如果单行文本数量较少可以关闭（如果文本数量较少可能会导致负优化）
    :param auto_font_y_offset: 是否自动计算字体 Y 轴偏移，默认为 True，如果字体大小一样或不在乎细节可以关闭以优化性能（不过性能损失也不大）
    :param font_fallback: 是否使用字体回退，默认为 True，如果启用则如果匹配的字体没有所需字符则使用下一个匹配的字符，如果都没有则使用第一个匹配的字符进行绘制
    :param wrap_indent: 换行缩进，可为字符串也可为数字，字符串代表换行时开头的字符，数字代表换行时偏移的宽度
    :return: DrawResult
    """
    fonts = list(set(fonts + [end_text_font])) if end_text_font else fonts
    text_segments, fonts, fonts_y_line_height = _parse_text_segments(text, fonts, max_x, font_fallback)

    # 自动计算行高
    if line_height == -1:
        if fast_get_line_height:
            for font in fonts_y_line_height:
                line_height = max(line_height, fonts_y_line_height[font])
        else:
            fonts_y_line_height = {}
            for segment in text_segments:
                text, text_font = segment.text, segment.font
                _, text_h = text_font.get_size(text)
                fonts_y_line_height[text_font] = text_h + text_font.get_metrics()[1]
                line_height = max(text_h + text_font.get_metrics()[1], line_height)
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
        text, text_font, text_color = (text_segments[i].text, text_segments[i].font, text_segments[i].color)
        text = str(text)
        is_enter = False

        has_end_text = (max_line == -1 or max_line != line_index) and (max_y == -1 or now_y + line_height * 2 < max_y)

        target_max_x = max_x - now_x if has_end_text else max_x - now_x - end_text_w
        full_width = None
        # 处理换行逻辑
        if (
                max_x != -1 and
                (
                        (full_width := text_font.get_width(text)) > target_max_x
                )
        ):
            # 二分查找找出最大能写下的部分
            if text != '\n' and not lines_drawn_flag:
                left, right = 0, len(text) - 1

                best_index = 1

                if guess_line_breaks:
                    best_index = _find_split_index_smart(text, text_font, target_max_x, full_width)
                else:
                    while left < right:
                        mid = (left + right + 1) // 2
                        if (
                                text_font.get_width(text[:mid]) < target_max_x
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
                    text_color
                )

                # 如果设置了wrap_indent，则将wrap_indent添加到text_segments中
                if isinstance(wrap_indent, str):
                    text_segments.insert(i, TextSegment(wrap_indent, text_font, text_color))

                text = current_text  # 使用截断后的文本

            is_enter = True

        elif text == '\n':
            is_enter = True

        # 判断是否超出最大高度或者最大行数
        if (max_y != -1 and now_y + line_height > max_y) or (max_line != -1 and line_index > max_line):
            # 绘制尾部文本（如果有）
            if end_text:
                if end_text_font is None:
                    end_text_font = fonts[-1]
                elif not isinstance(end_text_font, Font):
                    raise Exception('unsupported end_text_font type')
                if auto_font_y_offset:
                    y_offset = (line_height - fonts_y_line_height[end_text_font]) // 2
                else:
                    y_offset = 0
                draw.text(
                    (last_x + last_text_w, last_y + y_offset),
                    end_text, color, font=end_text_font.font, embedded_color=True
                )
                max_reached_x = max(max_reached_x, last_x + end_text_draw_font.getlength(end_text))
            truncated = True
            break

        # 计算y坐标偏移
        if auto_font_y_offset:
            y_offset = (line_height - fonts_y_line_height[text_font]) // 2
        else:
            y_offset = 0

        # 绘制文本
        if text_font.size is not None and text_font.size != text_font.font.size:
            raw_asc, raw_desc = text_font.font.getmetrics()

            bbox = text_font.font.getbbox(text)
            raw_w = int(bbox[2])
            raw_h = max(raw_asc + raw_desc, int(bbox[3]))

            temp_img = Image.new('RGBA', (raw_w, raw_h), (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)

            temp_draw.text(
                (0, 0), text, text_color or text_font.color or color, font=text_font.font,
                embedded_color=True if img.mode in ['RGB', 'RGBA'] else False
            )

            d = text_font.size / text_font.font.size
            if d > 1:
                resampling = Image.Resampling.BICUBIC
            else:
                resampling = Image.Resampling.HAMMING
            new_w, new_h = int(raw_w * d), int(raw_h * d)

            if new_w > 0 and new_h > 0:
                temp_img = temp_img.resize((new_w, new_h), resampling)
                img.paste(temp_img, (now_x, now_y + y_offset), temp_img)
        else:
            draw.text(
                (now_x, now_y + y_offset), text, text_color or text_font.color or color, font=text_font.font,
                embedded_color=True if img.mode in ['RGB', 'RGBA'] else False
            )

        # 更新变量
        last_x, last_y = now_x, now_y

        something_drawn = True
        last_segment = text_segments[i]  # 更新最后绘制的 segment
        segment_width = text_font.get_width(text) if is_enter or full_width is None else full_width
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
