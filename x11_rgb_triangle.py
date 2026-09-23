import tkinter as tk

def draw_rgb_triangle():
    root = tk.Tk()
    root.title("X11 RGB Triangle Test")
    root.geometry("500x500")
    
    canvas = tk.Canvas(root, width=500, height=500, bg="#1a2e40", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    x1, y1 = 250, 90
    x2, y2 = 120, 390
    x3, y3 = 380, 390

    for y in range(y1, y3 + 1):
        if y <= y2:
            if y1 != y2:
                left_x = x1 + (x2 - x1) * (y - y1) / (y2 - y1)
                right_x = x1 + (x3 - x1) * (y - y1) / (y3 - y1)
            else:
                left_x, right_x = x1, x3
        else:
            left_x, right_x = x2, x3
        
        steps = int(abs(right_x - left_x))
        if steps <= 0:
            continue
        
        for i in range(steps + 1):
            t = i / steps if steps > 0 else 0
            curr_x = left_x + (right_x - left_x) * t
            
            denom = (y2 - y3)*(x1 - x3) + (x3 - x2)*(y1 - y3)
            if denom == 0:
                continue
            w1 = ((y2 - y3)*(curr_x - x3) + (x3 - x2)*(y - y3)) / denom
            w2 = ((y3 - y1)*(curr_x - x3) + (x1 - x3)*(y - y3)) / denom
            w3 = 1.0 - w1 - w2
            
            if 0 <= w1 <= 1 and 0 <= w2 <= 1 and 0 <= w3 <= 1:
                r = int(w1 * 255)
                g = int(w3 * 255)
                b = int(w2 * 255)
                
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                canvas.create_line(curr_x, y, curr_x + 1, y, fill=color_hex)

    root.mainloop()

if __name__ == "__main__":
    draw_rgb_triangle()
