"""Draw editable, reproducible explanatory cards for the first episode."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resource/visuals/got_s01e01"
FONT = ROOT / "resource/fonts/SourceHanSansCN-Regular.otf"
W, H = 1080, 1920
BG, CARD, INK, MUTED = "#101725", "#1a2638", "#f4eee2", "#9baec3"
GOLD, BLUE, ROSE = "#e4b76a", "#79bbd5", "#df948a"


def font(size):
    return ImageFont.truetype(str(FONT), size)


def text(draw, value, x, y, size=38, color=INK, center=False):
    draw.text((x, y), value, font=font(size), fill=color, anchor="mt" if center else "lt")


def paragraph(draw, value, box, size=36, color=INK):
    x, y, width = box
    line = ""
    for character in value:
        if draw.textlength(line + character, font=font(size)) > width:
            text(draw, line, x, y, size, color)
            y += size * 1.65
            line = ""
        line += character
    if line:
        text(draw, line, x, y, size, color)


def base(number, title, subtitle):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.line((72, 80, 72, 210), fill=GOLD, width=5)
    text(draw, "权力的游戏 / 第一集解读", 102, 84, 28, MUTED)
    text(draw, title, 102, 140, 56)
    text(draw, subtitle, 74, 238, 31, MUTED)
    draw.line((72, 1650, 1008, 1650), fill="#33445a", width=2)
    text(draw, "背景与观点", 74, 1680, 27, MUTED)
    text(draw, number, 1008, 1680, 27, GOLD, center=True)
    return image, draw


def box(draw, xy, title, detail, color=GOLD):
    draw.rounded_rectangle(xy, radius=22, fill=CARD, outline=color, width=3)
    left, top, right, bottom = xy
    text(draw, title, (left + right) / 2, top + 26, 42, color, center=True)
    paragraph(draw, detail, (left + 28, top + 94, right - left - 56), 32)


def line(draw, points, color=GOLD, width=5, arrow=False):
    draw.line(points, fill=color, width=width, joint="curve")
    if arrow:
        x, y = points[-1]
        px, py = points[-2]
        if abs(x - px) > abs(y - py):
            direction = 1 if x > px else -1
            draw.polygon([(x, y), (x - direction * 20, y - 12), (x - direction * 20, y + 12)], fill=color)
        else:
            direction = 1 if y > py else -1
            draw.polygon([(x, y), (x - 12, y - direction * 20), (x + 12, y - direction * 20)], fill=color)


def note(draw, title, body):
    draw.rounded_rectangle((74, 1430, 1006, 1604), radius=18, fill=CARD)
    text(draw, title, 102, 1456, 31, GOLD)
    paragraph(draw, body, (102, 1510, 870), 34)


def map_card(stage):
    image, draw = base("01", "人物线发生在哪里？", "方位示意 · 非比例地图")
    west = [(270, 338), (493, 340), (558, 443), (506, 568), (558, 752),
            (485, 930), (548, 1120), (416, 1330), (218, 1278), (242, 1080),
            (171, 877), (230, 674), (177, 464)]
    draw.polygon(west, fill="#22364b", outline="#52728b")
    draw.rounded_rectangle((684, 674, 973, 1130), radius=70, fill="#243443", outline="#52728b", width=2)
    text(draw, "海", 609, 850, 50, BLUE, center=True)
    locations = [("长城", 340, 410, BLUE), ("临冬城", 360, 659, BLUE)]
    if stage >= 2:
        locations.append(("君临", 393, 1117, GOLD))
        line(draw, [(390, 749), (455, 875), (422, 1033)], GOLD, arrow=True)
        text(draw, "南下", 500, 875, 30, GOLD)
    if stage >= 3:
        locations.append(("潘托斯", 822, 843, ROSE))
        text(draw, "另一条人物线", 825, 985, 29, MUTED, center=True)
    for label, x, y, color in locations:
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=color)
        text(draw, label, x, y + 31, 43, color, center=True)
    messages = {
        1: ("北境", "长城外的异常，尚未进入权力中心的视野。"),
        2: ("一份任命，改变全家的处境", "奈德南下，将离开熟悉的北境，进入王室事务。"),
        3: ("地理分散，利益相连", "北境、王室和流亡王族，分别面对不同的选择。"),
    }
    note(draw, *messages[stage])
    return image


def relation_card(stage):
    image, draw = base("02", "信任如何变成政治关系？", "本集已知关系 · 随剧情逐步展开")
    box(draw, (72, 380, 477, 600), "劳勃", "国王 / 发出邀请", GOLD)
    box(draw, (603, 380, 1008, 600), "奈德", "北境领主 / 面临选择", BLUE)
    line(draw, [(477, 455), (603, 455)])
    text(draw, "旧友", 540, 496, 29, MUTED, center=True)
    if stage >= 2:
        line(draw, [(275, 600), (275, 720), (540, 720), (540, 790)], GOLD, arrow=True)
        line(draw, [(805, 600), (805, 720), (540, 720)], BLUE)
        box(draw, (267, 792, 813, 984), "国王之手", "劳勃提议由奈德接任")
    if stage >= 3:
        box(draw, (72, 1102, 477, 1292), "王室子女", "联姻提议的一方", GOLD)
        box(draw, (603, 1102, 1008, 1292), "史塔克子女", "联姻提议的另一方", BLUE)
        line(draw, [(477, 1170), (603, 1170)], ROSE)
        text(draw, "联姻", 540, 1206, 29, ROSE, center=True)
    notes = {
        1: ("起点是私人信任", "劳勃寻找可靠助手时，首先想到自己的旧友。"),
        2: ("任命带来新的责任", "友情进入权力中心后，还要面对利益与秘密。"),
        3: ("关系扩展到下一代", "大人的政治选择，也会改变孩子的人生。"),
    }
    note(draw, *notes[stage])
    return image


def interests_card(stage):
    image, draw = base("03", "两场联姻，谁付出代价？", "基于本集情节的利益对照")
    for x, title, color, goal, method, cost in [
        (72, "劳勃", GOLD, "巩固盟友关系", "提出子女联姻", "双方孩子的婚姻"),
        (574, "韦赛里斯", ROSE, "换取复国军队", "安排妹妹出嫁", "丹妮莉丝的选择权"),
    ]:
        text(draw, title, x + 216, 360, 46, color, center=True)
        box(draw, (x, 455, x + 434, 675), "目标", goal, color)
        line(draw, [(x + 216, 681), (x + 216, 735)], color, arrow=True)
        box(draw, (x, 755, x + 434, 975), "手段", method, color)
        if stage >= 2:
            line(draw, [(x + 216, 981), (x + 216, 1035)], color, arrow=True)
            box(draw, (x, 1055, x + 434, 1275), "代价由谁承担？", cost, color)
    note(draw, "我的观察", "获得利益的人，和付出代价的人，未必是同一个人。")
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for category, maker, stages in [("map", map_card, 3), ("relations", relation_card, 3), ("interests", interests_card, 2)]:
        for stage in range(1, stages + 1):
            maker(stage).save(OUT / f"{category}_{stage:02}.png")
    print(f"Generated 8 graphic cards in {OUT}")


if __name__ == "__main__":
    main()
