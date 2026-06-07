"""
manim_scenes.py — ヒーロー図カットの Manim Scene 定義

設備見積もり/制御システムの核「アダプタ・パターン」を美しく動かす決めカット。
背骨(計算・制御コア)は不変。左のアダプタが Excel→設備API→制御 と差し替わり、
右の設備ノード(空調/給排水/機械)へ線とデータ流で繋がる。

renderer から `manim render ... AdapterSpine` で呼ばれる。
日本語は Noto Sans CJK JP（Colabで fonts-noto-cjk を導入）。
"""
from manim import (
    Scene, RoundedRectangle, Circle, Line, Text, VGroup,
    Create, Write, FadeIn, GrowFromCenter, Transform, LaggedStart,
    RIGHT, LEFT, UP, DOWN, WHITE,
)

JP = "Noto Sans CJK JP"
TEAL = "#36d6d6"
AMBER = "#ffc85a"
BLUEB = "#7db4ff"
BG = "#06121f"
PANEL = "#0d2a3f"


class AdapterSpine(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ── 中央：背骨（不変コア）──
        core = RoundedRectangle(width=3.4, height=1.9, corner_radius=0.2,
                                stroke_color=TEAL, stroke_width=3,
                                fill_color=PANEL, fill_opacity=0.75)
        core_t = Text("背骨", font=JP, font_size=44, color=WHITE)
        core_s = Text("計算・制御コア（不変）", font=JP, font_size=20, color=TEAL)
        core_s.next_to(core_t, DOWN, buff=0.15)
        core_g = VGroup(core_t, core_s).move_to(core.get_center())
        self.play(Create(core), run_time=0.9)
        self.play(Write(core_t), FadeIn(core_s), run_time=0.8)

        # ── 右：設備ノード ──
        nodes = VGroup()
        for i, lbl in enumerate(("空調", "給排水", "機械設備")):
            c = Circle(radius=0.52, stroke_color=BLUEB, stroke_width=3,
                       fill_color=PANEL, fill_opacity=0.65)
            t = Text(lbl, font=JP, font_size=22, color=WHITE)
            n = VGroup(c, t).move_to(RIGHT * 4.7 + UP * (1.9 - i * 1.9))
            nodes.add(n)
        self.play(LaggedStart(*[GrowFromCenter(n) for n in nodes], lag_ratio=0.3),
                  run_time=1.4)

        links = VGroup()
        for n in nodes:
            links.add(Line(core.get_right(), n[0].get_left(),
                           color=TEAL, stroke_width=3))
        self.play(LaggedStart(*[Create(l) for l in links], lag_ratio=0.3),
                  run_time=1.4)

        # ── 左：アダプタ（差し替わる）──
        adp = RoundedRectangle(width=2.6, height=1.0, corner_radius=0.15,
                               stroke_color=AMBER, stroke_width=3, fill_opacity=0.0)
        adp.move_to(LEFT * 4.7)
        adp_l = Text("アダプタ：Excel", font=JP, font_size=24, color=AMBER).move_to(adp)
        link_l = Line(adp.get_right(), core.get_left(), color=AMBER, stroke_width=3)
        self.play(Create(adp), Write(adp_l), Create(link_l), run_time=1.0)

        for nxt in ("アダプタ：設備API", "アダプタ：制御プログラム"):
            new = Text(nxt, font=JP, font_size=24, color=AMBER).move_to(adp)
            self.play(Transform(adp_l, new), run_time=1.0)
            self.wait(0.4)

        self.wait(1.0)
