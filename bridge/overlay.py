"""翻訳結果を表示する小さなオーバーレイ窓（tkinter / 標準ライブラリのみ）。

ゲーム内チャットへの表示がうまくいかない環境や、
ホストとしてプレイしている場合の保険として使う。
日本語を打ち込んで Enter すると、翻訳してゲームのチャットへ送信もできる。

注意: 排他フルスクリーンでは前面に出ない。
      ゲーム側の表示設定を「ウィンドウ(フルスクリーン)」にすること。
"""

from __future__ import annotations

import logging
import queue
import time
import tkinter as tk

from i18n import t

log = logging.getLogger("drgtl.overlay")

BG = "#101014"
FG_IN = "#d9e6ff"
FG_OUT = "#ffe6a8"
FG_DIM = "#7a8090"


class Overlay:
    def __init__(self, bridge):
        self.bridge = bridge
        cfg = bridge.cfg["overlay"]
        self.cfg = cfg
        self.max_lines = int(cfg["lines"])
        self.mode = cfg.get("mode", "auto")
        self.hide_after = float(cfg.get("hide_after", 12))
        self._last_msg_at = 0.0
        self._visible = True

        self.root = tk.Tk()
        self.root.title("DRGTranslate")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", float(cfg["opacity"]))
        except tk.TclError:
            pass
        self.root.configure(bg=BG)
        self.root.geometry(f"+{int(cfg['x'])}+{int(cfg['y'])}")

        font = ("Yu Gothic UI", int(cfg["font_size"]))

        header = tk.Frame(self.root, bg="#1c1c24")
        header.pack(fill="x")
        tk.Label(header, text="  DRGTranslate", bg="#1c1c24", fg=FG_DIM,
                 font=(font[0], font[1] - 1)).pack(side="left")
        close = tk.Label(header, text="✕  ", bg="#1c1c24", fg=FG_DIM,
                         font=(font[0], font[1] - 1), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: self.root.destroy())
        header.bind("<Button-1>", self._drag_start)
        header.bind("<B1-Motion>", self._drag_move)

        self.text = tk.Text(
            self.root, height=self.max_lines, bg=BG, fg=FG_IN, font=font,
            bd=0, highlightthickness=0, wrap="word", state="disabled",
            padx=8, pady=6,
        )
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("in", foreground=FG_IN)
        self.text.tag_configure("out", foreground=FG_OUT)
        self.text.tag_configure("sys", foreground=FG_DIM)

        self.entry = None
        if cfg.get("composer", True):
            self.entry = tk.Entry(self.root, bg="#1a1a22", fg="#ffffff", font=font,
                                  insertbackground="#ffffff", bd=0, highlightthickness=1,
                                  highlightbackground="#2c2c38")
            self.entry.pack(fill="x", padx=6, pady=(0, 6), ipady=4)
            self.entry.bind("<Return>", self._on_submit)

        self._append("sys", t("o.waiting"))
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

        self.root.update_idletasks()
        self.root.geometry(
            f"{int(cfg['width'])}x{self.root.winfo_reqheight()}"
            f"+{int(cfg['x'])}+{int(cfg['y'])}"
        )

        if self.mode == "auto" and self.hide_after > 0:
            self._visible = False
            self.root.withdraw()


    def _drag_start(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + event.x - getattr(self, "_drag_x", 0)
        y = self.root.winfo_y() + event.y - getattr(self, "_drag_y", 0)
        self.root.geometry(f"+{x}+{y}")


    def _append(self, tag: str, line: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n", tag)
        total = int(self.text.index("end-1c").split(".")[0])
        if total > self.max_lines * 3:
            self.text.delete("1.0", f"{total - self.max_lines * 3}.0")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _on_submit(self, _event=None):
        if not self.entry:
            return
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not text:
            return
        if not self.bridge.game_connected:
            self._append("sys", t("o.not_connected"))
            return
        self.bridge.outbound_from_overlay.put(text)

    def _composer_busy(self) -> bool:
        """入力欄を使っている最中は引っ込めない。"""
        if self.entry is None:
            return False
        try:
            if self.entry.get().strip():
                return True
            return self.root.focus_get() is self.entry
        except (tk.TclError, KeyError):
            return False

    def _apply_visibility(self) -> None:
        if self.mode == "always":
            want = True
        elif self.mode == "off":
            want = False
        else:
            want = self.bridge.ingame_display_ok is not True
            if want and self.hide_after > 0 and not self._composer_busy():
                want = (time.monotonic() - self._last_msg_at) <= self.hide_after
        if want != self._visible:
            self._visible = want
            if want:
                self.root.deiconify()
            else:
                self.root.withdraw()

    def _tick(self) -> None:
        try:
            while True:
                try:
                    kind, line = self.bridge.overlay_queue.get_nowait()
                except queue.Empty:
                    break
                self._append(kind, line)
                self._last_msg_at = time.monotonic()
            self._apply_visibility()
        except Exception:  # noqa: BLE001
            log.exception(t("o.update_error"))
        if not self.bridge.stop_event.is_set():
            self.root.after(120, self._tick)
        else:
            self.root.destroy()

    def run(self) -> None:
        self.root.after(120, self._tick)
        self.root.mainloop()


def run(bridge) -> None:
    Overlay(bridge).run()
