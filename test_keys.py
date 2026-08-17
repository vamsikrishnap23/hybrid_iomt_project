import sys, termios, tty, threading, time
from rich.live import Live
from rich.text import Text

pressed = "None"

def listener():
    global pressed
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            c = sys.stdin.read(1)
            pressed = c
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

threading.Thread(target=listener, daemon=True).start()

with Live(refresh_per_second=4) as live:
    for _ in range(20):
        live.update(Text(f"Pressed: {pressed}"))
        time.sleep(0.25)
