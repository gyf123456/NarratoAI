"""Small transparent graphics that leave the movie and its characters visible."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resource/visuals/got_s01e01_natural"
FONT = ROOT / "resource/fonts/SourceHanSansCN-Regular.otf"
WHITE, GOLD, BLUE, ROSE = "#f4eee2", "#e4b76a", "#79bbd5", "#df948a"


def text(draw, x, y, value, size=34, color=WHITE, centered=False):
    draw.text((x, y), value, font=ImageFont.truetype(str(FONT), size), fill=color,
              anchor="mt" if centered else "lt")


def canvas(title, subtitle):
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 100, 1020, 585), radius=28, fill=(16, 23, 37, 238), outline=(87, 102, 123, 150), width=2)
    text(draw, 100, 138, title, 42)
    text(draw, 100, 204, subtitle, 28, "#9baec3")
    return image, draw


def node(draw, x, y, title, detail, color):
    draw.rounded_rectangle((x - 160, y, x + 160, y + 135), radius=16,
                           fill=(26, 38, 56, 255), outline=color, width=2)
    text(draw, x, y + 20, title, 38, color, True)
    text(draw, x, y + 82, detail, 27, WHITE, True)


def takeaway(draw, value):
    # Below the film, above the speech captions; one short thought at a time.
    draw.rounded_rectangle((90, 1410, 990, 1516), radius=18, fill=(16, 23, 37, 228))
    text(draw, 540, 1442, value, 34, GOLD, True)


def map_card():
    image, draw = canvas("先认清两个地方", "北境与君临 · 简化方位示意")
    draw.polygon([(180, 292), (300, 268), (400, 325), (345, 445), (380, 532),
                  (230, 548), (165, 426)], fill=(39, 61, 80, 255))
    draw.ellipse((251, 310, 269, 328), fill=BLUE)
    text(draw, 430, 299, "临冬城", 40, BLUE)
    text(draw, 430, 350, "奈德熟悉的北境", 30)
    draw.ellipse((295, 483, 313, 501), fill=GOLD)
    text(draw, 430, 445, "君临", 40, GOLD)
    text(draw, 430, 496, "国王所在的权力中心", 30)
    draw.line([(272, 347), (312, 451)], fill=GOLD, width=4)
    draw.polygon([(312, 462), (299, 443), (320, 438)], fill=GOLD)
    takeaway(draw, "南下，也意味着离开自己的势力范围")
    return image


def relation_card(marriage=False):
    title = "两个家族，开始绑在一起" if marriage else "国王为什么找到奈德？"
    image, draw = canvas(title, "联姻提议" if marriage else "旧友关系，进入王室事务")
    left, right = ("王室子女", "史塔克子女") if marriage else ("劳勃", "奈德")
    detail_l, detail_r = ("一方", "另一方") if marriage else ("国王", "北境领主")
    node(draw, 270, 300, left, detail_l, GOLD)
    node(draw, 810, 300, right, detail_r, BLUE)
    draw.line((432, 361, 646, 361), fill=ROSE if marriage else GOLD, width=4)
    text(draw, 540, 383, "联姻" if marriage else "旧友", 30, ROSE if marriage else GOLD, True)
    text(draw, 540, 484, "孩子的婚姻，被纳入家族利益" if marriage else "劳勃提议：由奈德接任国王之手", 34, WHITE, True)
    takeaway(draw, "关系更近，牵连也更深" if marriage else "私人信任，能否应对复杂的政治关系？")
    return image


def interests_card():
    image, draw = canvas("两场婚姻，谁做主？", "相似的手段，不同的目标")
    text(draw, 290, 292, "劳勃", 38, GOLD, True)
    text(draw, 790, 292, "韦赛里斯", 38, ROSE, True)
    draw.line((540, 291, 540, 540), fill="#536278", width=2)
    text(draw, 290, 361, "希望巩固盟友", 32, WHITE, True)
    text(draw, 790, 361, "希望换来军队", 32, WHITE, True)
    text(draw, 290, 426, "提出子女联姻", 32, WHITE, True)
    text(draw, 790, 426, "安排妹妹出嫁", 32, WHITE, True)
    text(draw, 540, 510, "大人做决定，孩子承担代价", 34, GOLD, True)
    takeaway(draw, "获利的人，与付出代价的人，未必相同")
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, image in [("map", map_card()), ("trust", relation_card()),
                        ("marriage", relation_card(True)), ("interests", interests_card())]:
        image.save(OUT / f"{name}.png")
    print(OUT)


if __name__ == "__main__":
    main()
