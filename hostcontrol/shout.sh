#!/usr/bin/env bash
set -euo pipefail

# Pops a brief overlay bar on the host machine (X11) for a shout message.
# Uses a slim Tk window to mimic a tall dmenu-style bar: white background, black text.

MSG="${*:-}"
[ -z "$MSG" ] && exit 0

DURATION_MS="${DURATION_MS:-3000}"

if command -v python3 >/dev/null 2>&1; then
  python3 - "$MSG" "$DURATION_MS" <<'PY'
import os
import subprocess
import sys
import tempfile
try:
    import tkinter as tk
    import tkinter.font as tkfont
except Exception:
    sys.exit(0)
try:
    from PIL import Image, ImageTk, ImageOps
except Exception:
    Image = None
    ImageTk = None

msg = sys.argv[1]
try:
    duration = int(float(sys.argv[2]))
except Exception:
    duration = 100


def get_right_monitor():
    """
    Parse xrandr to find the right-most connected monitor geometry.
    Returns (x, y, w, h) or None.
    """
    try:
        out = subprocess.check_output(["xrandr", "--query"], text=True)
    except Exception:
        return None

    best = None
    for line in out.splitlines():
        if " connected" not in line:
            continue
        parts = line.split()
        for part in parts:
            if "+" in part and "x" in part:
                try:
                    res, pos = part.split("+", 1)
                    w, h = map(int, res.split("x"))
                    x, y = map(int, pos.split("+"))
                    if best is None or x > best[0]:
                        best = (x, y, w, h)
                except Exception:
                    continue
                break
    return best


root = tk.Tk(className="StreamShout")
root.attributes("-topmost", True)
root.overrideredirect(True)
root.configure(bg="#000000")
root.title("StreamShout")
try:
    root.wm_class("StreamShout", "StreamShout")
except Exception:
    pass
image_win = None

mon = get_right_monitor()
if mon:
    mon_x, mon_y, mon_w, mon_h = mon
else:
    mon_x, mon_y, mon_w, mon_h = 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

wrap = max(mon_w - 40, 200)

def split_message(text: str):
    if "/" in text:
        top, bottom = text.split("/", 1)
        return top.strip(), bottom.strip()
    return text.strip(), ""


top_text, bottom_text = split_message(msg)
longest = max(len(top_text), len(bottom_text))

def pick_font_size(length: int):
    if length <= 20:
        return 54
    if length <= 40:
        return 50
    if length <= 70:
        return 44
    return 38

font_size = pick_font_size(longest)
font_choice = ("Arial", font_size, "bold")


def build_window(text: str, y_pos: int):
    win = tk.Toplevel(root, class_="StreamShout") if text else None
    if win:
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        win.configure(bg="#000000")

        label = tk.Label(
            win,
            text=text,
            font=font_choice,
            fg="#ffffff",
            bg="#000000",
            padx=18,
            pady=14,
            wraplength=wrap,
            justify="center",
        )
        label.pack(fill="both", expand=True)
        win.update_idletasks()
        win.bind("<Button-1>", lambda _e: win.destroy())

        height = max(label.winfo_reqheight() + 24, 130)
        width = mon_w
        x = mon_x
        win.geometry(f"{width}x{height}+{x}+{y_pos}")

        wid = win.winfo_id()
        try:
            subprocess.run(
                [
                    "xprop",
                    "-id",
                    str(wid),
                    "-f",
                    "WM_CLASS",
                    "8s",
                    "-set",
                    "WM_CLASS",
                    "StreamShout\0StreamShout",
                ],
                check=False,
            )
            subprocess.run(
                [
                    "xprop",
                    "-id",
                    str(wid),
                    "-f",
                    "_NET_WM_WINDOW_TYPE",
                    "32a",
                    "-set",
                    "_NET_WM_WINDOW_TYPE",
                    "_NET_WM_WINDOW_TYPE_DOCK",
                ],
                check=False,
            )
            subprocess.run(
                [
                    "xprop",
                    "-id",
                    str(wid),
                    "-f",
                    "_NET_WM_STATE",
                    "32a",
                    "-set",
                    "_NET_WM_STATE",
                    "_NET_WM_STATE_ABOVE,_NET_WM_STATE_STICKY",
                ],
                check=False,
            )
        except Exception:
            pass

    return win


def split_image_message(text: str):
    text = text.strip()
    if not (text.startswith("http://") or text.startswith("https://")):
        return None, ""
    parts = text.split(" ", 1)
    url = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    return url, rest


def show_image_if_url(text: str) -> bool:
    global font_choice
    global image_win
    url, rest = split_image_message(text)
    if not url:
        return False
    if Image is None or ImageTk is None:
        return False
    fd, path = tempfile.mkstemp(prefix="shout_img_", suffix=".img")
    os.close(fd)
    try:
        subprocess.run(
            ["curl", "-L", "--fail", "--silent", "--show-error", "--max-time", "6", "-o", path, url],
            check=True,
        )
        img = Image.open(path)
        img = img.convert("RGBA")
    except Exception:
        try:
            os.unlink(path)
        except Exception:
            pass
        return False

    if rest:
        if rest.startswith("."):
            rest = rest[1:].lstrip()
        else:
            rest = rest.upper()
    top_text, bottom_text = split_message(rest)
    old_font_choice = font_choice
    if top_text or bottom_text:
        longest = max(len(top_text), len(bottom_text))
        font_choice = ("Arial", pick_font_size(longest), "bold")

    top_height = 0
    bottom_height = 0
    if top_text:
        tmp = tk.Toplevel(root)
        tmp.withdraw()
        lbl_tmp = tk.Label(tmp, text=top_text, font=font_choice, wraplength=wrap, padx=18, pady=14)
        lbl_tmp.pack()
        tmp.update_idletasks()
        top_height = max(lbl_tmp.winfo_reqheight() + 24, 130)
        tmp.destroy()
    if bottom_text:
        tmp = tk.Toplevel(root)
        tmp.withdraw()
        lbl_tmp = tk.Label(tmp, text=bottom_text, font=font_choice, wraplength=wrap, padx=18, pady=14)
        lbl_tmp.pack()
        tmp.update_idletasks()
        bottom_height = max(lbl_tmp.winfo_reqheight() + 20, 110)
        tmp.destroy()

    avail_h = max(mon_h - top_height - bottom_height, 1)
    img = img.resize((mon_w, avail_h), Image.LANCZOS).convert("RGB")
    tk_img = ImageTk.PhotoImage(img)

    root.withdraw()
    img_win = tk.Toplevel(root, class_="StreamShout")
    img_win.attributes("-topmost", True)
    img_win.overrideredirect(True)
    img_win.configure(bg="#000000")
    img_win.title("StreamShout")
    try:
        img_win.wm_class("StreamShout", "StreamShout")
    except Exception:
        pass
    img_win.geometry(f"{mon_w}x{mon_h}+{mon_x}+{mon_y}")
    try:
        img_win.attributes("-fullscreen", True)
    except Exception:
        pass
    wid = img_win.winfo_id()
    try:
        subprocess.run(
            [
                "xprop",
                "-id",
                str(wid),
                "-f",
                "WM_CLASS",
                "8s",
                "-set",
                "WM_CLASS",
                "StreamShout\0StreamShout",
            ],
            check=False,
        )
        subprocess.run(
            [
                "xprop",
                "-id",
                str(wid),
                "-f",
                "_NET_WM_WINDOW_TYPE",
                "32a",
                "-set",
                "_NET_WM_WINDOW_TYPE",
                "_NET_WM_WINDOW_TYPE_DOCK",
            ],
            check=False,
        )
        subprocess.run(
            [
                "xprop",
                "-id",
                str(wid),
                "-f",
                "_NET_WM_STATE",
                "32a",
                "-set",
                "_NET_WM_STATE",
                "_NET_WM_STATE_ABOVE,_NET_WM_STATE_STICKY,_NET_WM_STATE_FULLSCREEN",
            ],
            check=False,
        )
    except Exception:
        pass
    label = tk.Label(img_win, image=tk_img, bg="#000000")
    label.image = tk_img
    label.place(x=0, y=top_height, width=mon_w, height=avail_h)
    try:
        os.unlink(path)
    except Exception:
        pass
    if top_text:
        top_label = tk.Label(
            img_win,
            text=top_text,
            font=font_choice,
            fg="#ffffff",
            bg="#000000",
            padx=18,
            pady=14,
            wraplength=wrap,
            justify="center",
        )
        top_label.place(x=0, y=0, width=mon_w, height=top_height)
    if bottom_text:
        bottom_label = tk.Label(
            img_win,
            text=bottom_text,
            font=font_choice,
            fg="#ffffff",
            bg="#000000",
            padx=18,
            pady=14,
            wraplength=wrap,
            justify="center",
        )
        bottom_y = mon_h - bottom_height
        bottom_label.place(x=0, y=bottom_y, width=mon_w, height=bottom_height)
    font_choice = old_font_choice
    image_win = img_win
    return True


if show_image_if_url(msg.strip()):
    def _close_all(_e=None):
        try:
            if image_win:
                image_win.destroy()
        finally:
            root.destroy()
    if image_win:
        image_win.bind("<Button-1>", _close_all)
        image_win.after(3000, _close_all)
    root.mainloop()
    sys.exit(0)


# Build top window
top_win = build_window(top_text, mon_y)

# Build bottom window if provided
if bottom_text:
    # Temporarily measure to know height for bottom placement
    tmp = tk.Toplevel(root)
    tmp.withdraw()
    lbl_tmp = tk.Label(tmp, text=bottom_text, font=font_choice, wraplength=wrap, padx=18, pady=14)
    lbl_tmp.pack()
    tmp.update_idletasks()
    bottom_height = max(lbl_tmp.winfo_reqheight() + 20, 110)
    tmp.destroy()
    bottom_y = mon_y + mon_h - bottom_height
    bottom_win = build_window(bottom_text, bottom_y)
else:
    bottom_win = None

def _close_text_windows(_e=None):
    try:
        if top_win:
            top_win.destroy()
    finally:
        if bottom_win:
            try:
                bottom_win.destroy()
            except Exception:
                pass
        root.destroy()

if top_win:
    top_win.bind("<Button-1>", _close_text_windows)
if bottom_win:
    bottom_win.bind("<Button-1>", _close_text_windows)

root.after(duration, root.destroy)
if bottom_win:
    bottom_win.after(duration, bottom_win.destroy)
if top_win:
    top_win.after(duration, top_win.destroy)

root.mainloop()
PY
  exit 0
fi

echo "$MSG"
