"""
Windows OS Wrapper Overlay — Copilot Integration Point #22 (Implementation)
=============================================================================
This script runs as a detached Windows process providing:
  - System tray icon with context menu
  - Global hotkey to summon the hybrid engine overlay
  - Transparent floating window over any application
  - Real-time streaming output from the hybrid engine
  - Clipboard integration (copy prompt → engine → paste result)

Run via: pythonw hybrid_engine/deployment/windows_overlay.py
         (or launched automatically by CopilotClient.launch_windows_overlay())

On Linux/Mac: this module documents the overlay architecture but does not
execute GUI code. The CommsHub overlay.command topic is used instead.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import sys
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("hybrid_engine.overlay")

IS_WINDOWS = platform.system() == "Windows"


# ── Overlay configuration ─────────────────────────────────────────────────────
DEFAULT_HOTKEY = "ctrl+shift+space"
DEFAULT_OPACITY = 0.92
ENGINE_API_URL = os.getenv("ENGINE_URL", "http://localhost:8765")


# ── Cross-platform overlay stub ───────────────────────────────────────────────
class OverlayWindow:
    """
    Floating overlay window for the hybrid engine.
    On Windows: uses tkinter with transparency + keyboard hooks.
    On Linux/Mac: uses the CommsHub WebSocket for headless operation.
    """

    def __init__(self, hotkey: str = DEFAULT_HOTKEY, opacity: float = DEFAULT_OPACITY):
        self.hotkey = hotkey
        self.opacity = opacity
        self._visible = False
        self._engine_url = ENGINE_API_URL
        self._history: list = []

    def show(self):
        self._visible = True
        logger.info("[Overlay] Shown")

    def hide(self):
        self._visible = False
        logger.info("[Overlay] Hidden")

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    async def send_to_engine(self, prompt: str) -> Dict[str, Any]:
        """Send a prompt to the hybrid engine API and return the result."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._engine_url}/route",
                    json={"prompt": prompt, "session_id": "overlay"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    return await resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def run(self):
        """Start the overlay. Platform-specific implementation."""
        if IS_WINDOWS:
            self._run_windows()
        else:
            self._run_headless()

    def _run_windows(self):
        """Windows implementation using tkinter + keyboard."""
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            logger.error("[Overlay] tkinter not available")
            self._run_headless()
            return

        root = tk.Tk()
        root.title("Hybrid Engine")
        root.attributes("-alpha", self.opacity)
        root.attributes("-topmost", True)
        root.overrideredirect(True)  # Borderless window

        # Position: top-right corner
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        win_w, win_h = 500, 400
        root.geometry(f"{win_w}x{win_h}+{screen_w - win_w - 20}+{screen_h // 2 - win_h // 2}")

        # Dark theme frame
        frame = tk.Frame(root, bg="#1a1a2e", padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title bar
        title = tk.Label(
            frame, text="⚡ Hybrid Engine", bg="#1a1a2e", fg="#00ff88",
            font=("Consolas", 12, "bold")
        )
        title.pack(anchor="w")

        # Output area
        output = tk.Text(
            frame, bg="#0d0d1a", fg="#e0e0e0", font=("Consolas", 10),
            wrap=tk.WORD, height=15, relief=tk.FLAT
        )
        output.pack(fill=tk.BOTH, expand=True, pady=(5, 5))

        # Input area
        input_var = tk.StringVar()
        input_entry = tk.Entry(
            frame, textvariable=input_var, bg="#16213e", fg="#ffffff",
            font=("Consolas", 10), relief=tk.FLAT, insertbackground="white"
        )
        input_entry.pack(fill=tk.X)

        def on_submit(event=None):
            prompt = input_var.get().strip()
            if not prompt:
                return
            input_var.set("")
            output.insert(tk.END, f"\n> {prompt}\n")
            output.see(tk.END)

            def run_async():
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self.send_to_engine(prompt))
                loop.close()
                response = result.get("response") or result.get("answer") or str(result)
                root.after(0, lambda: output.insert(tk.END, f"{response}\n"))
                root.after(0, lambda: output.see(tk.END))

            threading.Thread(target=run_async, daemon=True).start()

        input_entry.bind("<Return>", on_submit)

        # Register hotkey
        try:
            import keyboard
            keyboard.add_hotkey(self.hotkey, lambda: root.after(0, self.toggle))
            logger.info(f"[Overlay] Hotkey registered: {self.hotkey}")
        except ImportError:
            logger.warning("[Overlay] 'keyboard' package not installed — hotkey disabled")

        # System tray (requires pystray)
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Create a simple tray icon
            img = Image.new("RGB", (64, 64), color="#1a1a2e")
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill="#00ff88")

            def on_tray_show(icon, item):
                root.after(0, self.show)

            def on_tray_quit(icon, item):
                icon.stop()
                root.after(0, root.destroy)

            menu = pystray.Menu(
                pystray.MenuItem("Show Overlay", on_tray_show),
                pystray.MenuItem("Quit", on_tray_quit),
            )
            tray = pystray.Icon("hybrid_engine", img, "Hybrid Engine", menu)
            threading.Thread(target=tray.run, daemon=True).start()
            logger.info("[Overlay] System tray icon active")
        except ImportError:
            logger.warning("[Overlay] pystray/PIL not installed — tray icon disabled")

        root.mainloop()

    def _run_headless(self):
        """Headless mode: listen for overlay.command events via CommsHub WebSocket."""
        logger.info(f"[Overlay] Running headless mode (platform: {platform.system()})")
        logger.info(f"[Overlay] Connect to ws://{ENGINE_API_URL.replace('http://', '')}/ws/comms for events")

        async def listen():
            try:
                import aiohttp
                ws_url = ENGINE_API_URL.replace("http://", "ws://") + "/ws/comms"
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(ws_url) as ws:
                        logger.info(f"[Overlay] Connected to CommsHub at {ws_url}")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get("topic") == "overlay.command":
                                    cmd = data["payload"].get("command")
                                    args = data["payload"].get("args", {})
                                    logger.info(f"[Overlay] Command received: {cmd} {args}")
            except Exception as e:
                logger.error(f"[Overlay] Headless listen error: {e}")

        asyncio.run(listen())


# ── Clipboard integration ─────────────────────────────────────────────────────
class ClipboardBridge:
    """
    Monitor clipboard for prompts prefixed with '//hybrid:'.
    Automatically routes them through the engine and pastes the result.
    """

    PREFIX = "//hybrid:"

    def __init__(self, engine_url: str = ENGINE_API_URL):
        self.engine_url = engine_url
        self._last_clip = ""
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._monitor, daemon=True).start()
        logger.info(f"[ClipboardBridge] Monitoring clipboard for '{self.PREFIX}' prefix")

    def stop(self):
        self._running = False

    def _monitor(self):
        if not IS_WINDOWS:
            logger.info("[ClipboardBridge] Clipboard monitoring only available on Windows")
            return
        try:
            import pyperclip
        except ImportError:
            logger.warning("[ClipboardBridge] pyperclip not installed")
            return

        while self._running:
            try:
                clip = pyperclip.paste()
                if clip != self._last_clip and clip.startswith(self.PREFIX):
                    self._last_clip = clip
                    prompt = clip[len(self.PREFIX):].strip()
                    logger.info(f"[ClipboardBridge] Detected prompt: {prompt[:50]}...")
                    result = asyncio.run(self._route(prompt))
                    response = result.get("response") or result.get("answer") or str(result)
                    pyperclip.copy(response)
                    logger.info("[ClipboardBridge] Result copied to clipboard")
            except Exception as e:
                logger.error(f"[ClipboardBridge] Error: {e}")
            time.sleep(0.5)

    async def _route(self, prompt: str) -> Dict[str, Any]:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.engine_url}/route",
                    json={"prompt": prompt, "session_id": "clipboard"},
                ) as resp:
                    return await resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Hybrid Engine Windows Overlay")
    parser.add_argument("--hotkey", default=DEFAULT_HOTKEY)
    parser.add_argument("--opacity", type=float, default=DEFAULT_OPACITY)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--clipboard", action="store_true", help="Enable clipboard bridge")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [overlay] %(message)s")

    overlay = OverlayWindow(hotkey=args.hotkey, opacity=args.opacity)

    if args.clipboard:
        cb = ClipboardBridge()
        cb.start()

    if args.headless:
        overlay._run_headless()
    else:
        overlay.run()


if __name__ == "__main__":
    main()
