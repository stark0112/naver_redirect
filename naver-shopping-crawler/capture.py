"""
전역 단축키로 화면 캡쳐
어디서든 C 누르면 캡쳐, Q 누르면 종료
"""
import os
import subprocess
from datetime import datetime
from pynput import keyboard

IMAGE_DIR = '/Users/teramime/Documents/project_20/naver-shopping-crawler/captcha_images'
os.makedirs(IMAGE_DIR, exist_ok=True)


def capture():
    existing = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')]
    n = len(existing) + 1
    filename = f"captcha_{n:04d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(IMAGE_DIR, filename)
    subprocess.run(['screencapture', '-x', filepath])
    print(f"저장: {filename} ({n}개)")


def on_press(key):
    try:
        if key.char == 'c':
            capture()
        elif key.char == 'q':
            print("종료")
            return False  # 리스너 중지
    except AttributeError:
        pass  # 특수키는 무시


print("=== 전역 캡쳐 실행 중 ===")
print("C = 캡쳐 (어디서든)")
print("Q = 종료")
print()

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
