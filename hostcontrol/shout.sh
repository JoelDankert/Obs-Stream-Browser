#!/usr/bin/env bash
set -euo pipefail

# Pops a brief overlay bar on the host machine (X11) for a shout message.
# Uses a slim Tk window to mimic a tall dmenu-style bar: white background, black text.

MSG="${*:-}"
[ -z "$MSG" ] && exit 0

DURATION_MS="${DURATION_MS:-5000}"

if command -v python3 >/dev/null 2>&1; then
  python3 - "$MSG" "$DURATION_MS" <<'PY'
import subprocess
import sys
try:
    import tkinter as tk
    import tkinter.font as tkfont
except Exception:
    sys.exit(0)

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
