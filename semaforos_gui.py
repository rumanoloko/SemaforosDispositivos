#!/usr/bin/env python3
"""
Traffic Light Intersection Visualization – Versión sin luz amarilla y con indicadores de cola reposicionados.
"""
import tkinter as tk
from tkinter import font
import json
import logging
import paho.mqtt.client as mqtt
import os
import sys

# ——— Configuración global ———
class Config:
    BG = "#1e1e1e"
    ROAD = "#363636"
    ROAD_LINE = "#cccccc"
    CROSSWALK = "#ffffff"
    HOUSING_FILL = "#222222"
    HOUSING_OUTLINE = "#555555"
    OFF = "#2f2f2f"
    RED = "#ff4d4d"
    GREEN = "#33ff77"
    PEDESTRIAN = "#33ccff"
    TEXT = "#ffffff"

    WIDTH = 600
    HEIGHT = 600
    ROAD_WIDTH = 240
    CENTER_LINE_WIDTH = 4
    DASH_PATTERN = (20, 20)
    CROSSWALK_W = 30
    CROSSWALK_GAP = 10
    LIGHT_R = 28
    HOUSING_PAD = 20
    PEDESTRIAN_SIZE = 80
    BLINK_INTERVAL = 500

    BROKER = "192.168.45.190"
    PORT = 1883
    TOPICS = [("core_seleccionado", 0), ("core_0_sender", 0), ("core_1_sender", 0)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class RoundedRect:
    @staticmethod
    def create(canvas, x1, y1, x2, y2, radius=10, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2 - radius,
            x1, y1 + radius,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

class TrafficLight(RoundedRect):
    def __init__(self, canvas, x, y, orientation="vertical"):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.orientation = orientation
        self.lights = {}
        self._draw()

    def _draw(self):
        size = Config.LIGHT_R*2 + Config.HOUSING_PAD
        self.housing = TrafficLight.create(
            self.canvas, self.x - size/2, self.y - size/2,
            self.x + size/2, self.y + size/2,
            radius=12,
            fill=Config.HOUSING_FILL,
            outline=Config.HOUSING_OUTLINE,
            width=3
        )
        for i, color in enumerate(("red", "green")):
            offset = (i - 0.5) * (Config.LIGHT_R*2 + 10)
            cx = self.x + (offset if self.orientation == "horizontal" else 0)
            cy = self.y + (offset if self.orientation == "vertical" else 0)
            light = self.canvas.create_oval(
                cx - Config.LIGHT_R, cy - Config.LIGHT_R,
                cx + Config.LIGHT_R, cy + Config.LIGHT_R,
                fill=Config.OFF, outline="#000000", width=2
            )
            self.lights[color] = light

    def set_state(self, active_color: str | None):
        for color, item in self.lights.items():
            fill = getattr(Config, color.upper()) if color == active_color else Config.OFF
            self.canvas.itemconfig(item, fill=fill)

class PedestrianLight(RoundedRect):
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.lights = {}
        self._draw()

    def _draw(self):
        size = Config.PEDESTRIAN_SIZE
        self.housing = PedestrianLight.create(
            self.canvas, self.x - size/2, self.y - size/2,
            self.x + size/2, self.y + size/2,
            radius=10,
            fill=Config.HOUSING_FILL,
            outline=Config.HOUSING_OUTLINE,
            width=3
        )
        r = 15
        gap = 10
        red = self.canvas.create_oval(
            self.x - r, self.y - r - gap,
            self.x + r, self.y + r - gap,
            fill=Config.OFF
        )
        green = self.canvas.create_oval(
            self.x - r, self.y - r + gap,
            self.x + r, self.y + r + gap,
            fill=Config.OFF
        )
        self.lights = {"red": red, "green": green}

    def set_state(self, active: str | None):
        for color, item in self.lights.items():
            fill = Config.PEDESTRIAN if active == "green" and color == "green" else Config.RED if active == "red" and color == "red" else Config.OFF
            self.canvas.itemconfig(item, fill=fill)

class IntersectionCanvas:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=Config.WIDTH, height=Config.HEIGHT, bg=Config.BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.cx, self.cy = Config.WIDTH / 2, Config.HEIGHT / 2
        self._draw_roads()
        self._draw_crosswalks()
        self._create_lights()
        self._create_indicator()
        self.queues = {"top": 0, "bottom": 0, "left": 0, "right": 0}
        self._draw_queue_indicators()

    def _draw_roads(self):
        x0, x1 = self.cx - Config.ROAD_WIDTH / 2, self.cx + Config.ROAD_WIDTH / 2
        y0, y1 = self.cy - Config.ROAD_WIDTH / 2, self.cy + Config.ROAD_WIDTH / 2
        self.canvas.create_rectangle(x0, 0, x1, Config.HEIGHT, fill=Config.ROAD, outline="")
        self.canvas.create_line(self.cx, 0, self.cx, Config.HEIGHT, fill=Config.ROAD_LINE, width=Config.CENTER_LINE_WIDTH, dash=Config.DASH_PATTERN)
        self.canvas.create_rectangle(0, y0, Config.WIDTH, y1, fill=Config.ROAD, outline="")
        self.canvas.create_line(0, self.cy, Config.WIDTH, self.cy, fill=Config.ROAD_LINE, width=Config.CENTER_LINE_WIDTH, dash=Config.DASH_PATTERN)

    def _draw_crosswalks(self):
        half = Config.ROAD_WIDTH / 2
        stripes = 12
        step = Config.ROAD_WIDTH / stripes
        for orient in ("north", "south"):
            y = self.cy - half if orient == "north" else self.cy + half
            dir_sign = -1 if orient == "north" else 1
            for i in range(stripes):
                x1 = self.cx - half + i * step
                y2 = y + dir_sign * Config.CROSSWALK_W
                self.canvas.create_rectangle(x1, y, x1 + step - Config.CROSSWALK_GAP, y2, fill=Config.CROSSWALK, outline="")
        for orient in ("west", "east"):
            x = self.cx - half if orient == "west" else self.cx + half
            dir_sign = -1 if orient == "west" else 1
            for i in range(stripes):
                y1 = self.cy - half + i * step
                x2 = x + dir_sign * Config.CROSSWALK_W
                self.canvas.create_rectangle(x, y1, x2, y1 + step - Config.CROSSWALK_GAP, fill=Config.CROSSWALK, outline="")

    def _create_lights(self):
        offset = Config.ROAD_WIDTH / 2 + 100
        self.ns_top = TrafficLight(self.canvas, self.cx, self.cy - offset, orientation="vertical")
        self.ns_bottom = TrafficLight(self.canvas, self.cx, self.cy + offset, orientation="vertical")
        self.ew_left = TrafficLight(self.canvas, self.cx - offset, self.cy, orientation="horizontal")
        self.ew_right = TrafficLight(self.canvas, self.cx + offset, self.cy, orientation="horizontal")

    def _create_indicator(self):
        f = font.Font(family="Helvetica", size=24, weight="bold")
        self.indicator = self.canvas.create_text(
            self.cx, self.cy + Config.ROAD_WIDTH + 100,
            text="Esperando selección...", fill=Config.GREEN, font=f
        )

    def _draw_queue_indicators(self):
        self.queue_labels = {
            "top": self.canvas.create_text(self.cx - 80, self.ns_top.y, text="", fill=Config.TEXT),
            "bottom": self.canvas.create_text(self.cx + 80, self.ns_bottom.y, text="", fill=Config.TEXT),
            "left": self.canvas.create_text(self.ew_left.x, self.cy + 50 + 20, text="", fill=Config.TEXT),
            "right": self.canvas.create_text(self.ew_right.x, self.cy - 75, text="", fill=Config.TEXT)
        }

    def update_selection(self, sel):
        for tl in (self.ns_top, self.ns_bottom, self.ew_left, self.ew_right):
            tl.set_state(None)
        mode = "Derecha e izquierda tienen prioridad" if sel == 1 else "Abajo y arriba tienen prioridad"
        #os.system('cls');
        #print(mode);
        sys.stdout.write('\r' + mode + ' ' * 20)
        sys.stdout.flush()
        #self.canvas.itemconfig(self.indicator, text=f"{mode}", fill=Config.GREEN, font=("Helvetica", 24, "bold"))
        if sel == 0:
            self.ns_top.set_state("green")
            self.ns_bottom.set_state("green")
            self.ew_left.set_state("red")
            self.ew_right.set_state("red")
        else:
            self.ew_left.set_state("green")
            self.ew_right.set_state("green")
            self.ns_top.set_state("red")
            self.ns_bottom.set_state("red")

    def update_queues(self):
        for key in self.queue_labels:
            self.canvas.itemconfig(self.queue_labels[key], text=f"{self.queues[key]}", font=("Helvetica", 24, "bold"))

class MqttHandler:
    def __init__(self, vis: IntersectionCanvas):
        self.vis = vis
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(Config.BROKER, Config.PORT)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        logging.info(f"Conectado MQTT con código {rc}")
        for topic, qos in Config.TOPICS:
            client.subscribe(topic, qos)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            if topic == "core_seleccionado":
                sel = payload.get("coreSeleccionado")
                self.vis.root.after(0, self.vis.update_selection, sel)
            elif topic == "core_0_sender":
                self.vis.queues["bottom"] = payload.get("primera_cola", 0)
                self.vis.queues["top"] = payload.get("segunda_cola", 0)
            elif topic == "core_1_sender":
                self.vis.queues["left"] = payload.get("primera_cola", 0)
                self.vis.queues["right"] = payload.get("segunda_cola", 0)
            self.vis.root.after(0, self.vis.update_queues)
        except Exception as e:
            logging.error(f"Error procesando mensaje MQTT: {e}")

def main():
    root = tk.Tk()
    root.configure(bg=Config.BG)
    app = IntersectionCanvas(root)
    MqttHandler(app)
    root.mainloop()

if __name__ == "__main__":
    main()
