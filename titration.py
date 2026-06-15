import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
import matplotlib.animation as animation
from matplotlib.patches import Rectangle, Polygon
import sys
import os
import matplotlib.font_manager as fm

# 폰트 경로를 자동으로 잡아주는 마법의 함수
def resource_path(relative_path):
    try:
        # PyInstaller로 생성된 임시 폴더에서 파일을 찾음
        base_path = sys._MEIPASS
    except Exception:
        # 파이참에서 직접 실행할 때는 현재 폴더에서 찾음
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 이제 이 함수를 써서 폰트 경로를 지정하세요!
font_path = resource_path('NotoSansKR-Regular.ttf')
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = font_prop.get_name()


class TitrationSimulator:
    def __init__(self):
        # 초기 화학 변수 세팅
        self.Ca = 0.1
        self.Va = 50.0
        self.Cb = 0.1
        self.Ka = 1.8e-5
        self.Veq = (self.Ca * self.Va) / self.Cb

        self.ani = None
        self.current_idx = 0
        self.Vb_array = []
        self.pH_array = []

        # --- 🖥️ 화면 레이아웃 (아래쪽 컨트롤 패널 공간을 더 넓힘: bottom=0.35) ---
        self.fig, (self.ax, self.ax_vis) = plt.subplots(1, 2, figsize=(12, 7), gridspec_kw={'width_ratios': [2.5, 1]})
        plt.subplots_adjust(left=0.06, bottom=0.35, right=0.95)
        self.fig.canvas.manager.set_window_title('가상 중화적정 시뮬레이터')

        # --- 📈 좌측 그래프 세팅 ---
        self.bg_line, = self.ax.plot([], [], color='lightgray', linestyle='--', linewidth=2)
        self.line, = self.ax.plot([], [], color='steelblue', linewidth=3)
        self.dot, = self.ax.plot([], [], 'ro', markersize=10)

        self.ax.set_title('아세트산(약산) - 수산화나트륨(강염기) 중화적정 곡선', fontsize=16, pad=15)
        self.ax.set_xlabel('가한 염기 부피 (mL)')
        self.ax.set_ylabel('pH')
        self.ax.set_ylim(0, 14)
        self.ax.grid(True, linestyle=':', alpha=0.6)

        # --- 🧪 우측 비커 & 뷰렛 시각화 세팅 ---
        self.ax_vis.axis('off')
        self.ax_vis.set_xlim(0, 10)
        self.ax_vis.set_ylim(0, 100)

        self.ax_vis.add_patch(Rectangle((4.5, 45), 1, 40, facecolor='white', edgecolor='black', lw=2))
        self.ax_vis.add_patch(Polygon([[4.5,45], [5,40], [5.5,45]], facecolor='white', edgecolor='black', lw=2))
        self.ax_vis.text(5, 65, '염기\n(NaOH)', ha='center', va='center', fontsize=10)

        self.ax_vis.plot([2, 2, 8, 8], [35, 5, 5, 35], color='black', lw=3)
        self.ax_vis.text(5, 0, '산 용액 + 페놀프탈레인', ha='center', fontsize=11)

        self.liquid_rect = Rectangle((2.15, 5.15), 5.7, 10, facecolor='whitesmoke', edgecolor='none')
        self.ax_vis.add_patch(self.liquid_rect)

        # -------------------------------------------------------------
        # 🎛️ 하단 컨트롤 패널: 1열 (입력창 3개 + 상태창 2개)
        # ---------------------------------------------------------
        ax_ca = plt.axes([0.12, 0.23, 0.05, 0.05])
        self.textbox_Ca = TextBox(ax_ca, '산 농도(M) \n(0.01 ~ 1.0): ', initial=str(self.Ca))
        self.textbox_Ca.on_submit(self.submit_Ca)

        ax_va = plt.axes([0.30, 0.23, 0.05, 0.05])
        self.textbox_Va = TextBox(ax_va, '산 부피(mL) \n(10 ~ 100): ', initial=str(self.Va))
        self.textbox_Va.on_submit(self.submit_Va)

        # 🎯 [신규] 염기 농도 입력창 추가
        ax_cb = plt.axes([0.48, 0.23, 0.05, 0.05])
        self.textbox_Cb = TextBox(ax_cb, '염기 농도(M) \n(0.01 ~ 1.0): ', initial=str(self.Cb))
        self.textbox_Cb.on_submit(self.submit_Cb)

        # 🎯 [신규] 계산된 당량점 부피 디스플레이 창
        self.veq_text = self.fig.text(0.68, 0.255, f'당량점 부피\n{self.Veq:.1f} mL',
                                      fontsize=13, ha='center', va='center',
                                      bbox=dict(facecolor='ivory', edgecolor='orange', boxstyle='round,pad=0.5'))

        # 🎯 가한 염기 부피 디스플레이 창 (당량점 창 바로 옆으로 이동)
        self.volume_text = self.fig.text(0.85, 0.255, '가한 염기 부피\n0.00 mL',
                                         fontsize=13, ha='center', va='center',
                                         bbox=dict(facecolor='white', edgecolor='green', boxstyle='round,pad=0.5'))

        # -------------------------------------------------------------
        # 🎛️ 하단 컨트롤 패널: 2열 (조작 버튼 4개)
        # -------------------------------------------------------------
        ax_start = plt.axes([0.22, 0.10, 0.13, 0.06])
        self.btn_start = Button(ax_start, '자동 적정 ▶', color='lightgreen', hovercolor='palegreen')
        self.btn_start.on_clicked(self.start_titration)

        ax_manual = plt.axes([0.37, 0.10, 0.13, 0.06])
        self.btn_manual = Button(ax_manual, '+ 1방울 (0.05mL)', color='lightblue', hovercolor='skyblue')
        self.btn_manual.on_clicked(self.add_one_drop)

        ax_pause = plt.axes([0.52, 0.10, 0.11, 0.06])
        self.btn_pause = Button(ax_pause, '일시정지', color='khaki', hovercolor='palegoldenrod')
        self.btn_pause.on_clicked(self.pause_titration)

        ax_reset = plt.axes([0.65, 0.10, 0.11, 0.06])
        self.btn_reset = Button(ax_reset, '처음으로', color='lightcoral', hovercolor='salmon')
        self.btn_reset.on_clicked(self.reset_titration)

    def submit_Ca(self, text):
        """산 농도 제한: 0.01 ~ 1.0"""
        try:
            val = float(text)
            if val < 0.01: val = 0.01
            elif val > 1.0: val = 1.0

            self.Ca = val
            self.Veq = (self.Ca * self.Va) / self.Cb # 당량점 재계산
            self.textbox_Ca.set_val(str(self.Ca))    # 보정된 값으로 UI 업데이트
        except ValueError:
            self.textbox_Ca.set_val(str(self.Ca))    # 글자를 치면 원래 숫자로 복구

    def submit_Va(self, text):
        """산 부피 제한: 10.0 ~ 100.0"""
        try:
            val = float(text)
            if val < 10.0: val = 10.0
            elif val > 100.0: val = 100.0

            self.Va = val
            self.Veq = (self.Ca * self.Va) / self.Cb # 당량점 재계산
            self.textbox_Va.set_val(str(self.Va))    # 보정된 값으로 UI 업데이트
        except ValueError:
            self.textbox_Va.set_val(str(self.Va))

    def submit_Cb(self, text):
        """염기 농도 제한: 0.01 ~ 1.0"""
        try:
            val = float(text)
            if val < 0.01: val = 0.01
            elif val > 1.0: val = 1.0

            self.Cb = val
            self.Veq = (self.Ca * self.Va) / self.Cb # 당량점 재계산
            self.textbox_Cb.set_val(str(self.Cb))    # 보정된 값으로 UI 업데이트
        except ValueError:
            self.textbox_Cb.set_val(str(self.Cb))

    def calculate_pH(self, Vb):
        Kw = 1.0e-14
        if Vb == 0:
            return -np.log10(np.sqrt(self.Ka * self.Ca))
        elif Vb < self.Veq:
            ratio = Vb / (self.Veq - Vb)
            return -np.log10(self.Ka) + np.log10(ratio)
        elif Vb == self.Veq:
            Csalt = (self.Ca * self.Va) / (self.Va + self.Veq)
            Kb = Kw / self.Ka
            pOH = -np.log10(np.sqrt(Kb * Csalt))
            return 14.0 - pOH
        else:
            OH_conc = (self.Cb * (Vb - self.Veq)) / (self.Va + Vb)
            return 14.0 + np.log10(OH_conc)

    def init_data_if_needed(self):
        try:
            new_Ca = float(self.textbox_Ca.text)
            new_Va = float(self.textbox_Va.text)
            new_Cb = float(self.textbox_Cb.text) # 염기 농도 값 읽어오기
        except ValueError:
            print("숫자를 정확히 입력해주세요.")
            return False

        # 셋 중 하나라도 값이 변했거나 데이터가 비어있으면 전체 리셋 및 재계산
        if len(self.Vb_array) == 0 or self.Ca != new_Ca or self.Va != new_Va or self.Cb != new_Cb:
            self.Ca = new_Ca
            self.Va = new_Va
            self.Cb = new_Cb

            # 당량점 자동 재계산 및 텍스트 창 업데이트
            self.Veq = (self.Ca * self.Va) / self.Cb
            self.veq_text.set_text(f'당량점 부피\n{self.Veq:.1f} mL')

            max_Vb = self.Veq * 2.0
            num_steps = int(max_Vb / 0.05) + 1
            self.Vb_array = np.linspace(0, max_Vb, num_steps)

            self.pH_array = []
            for vb in self.Vb_array:
                if abs(vb - self.Veq) < 1e-4:
                    vb = self.Veq
                self.pH_array.append(self.calculate_pH(vb))

            self.ax.set_xlim(0, max_Vb)
            self.bg_line.set_data(self.Vb_array, self.pH_array)
            self.current_idx = 0
        return True

    def reset_titration(self, event):
        if self.ani is not None and self.ani.event_source is not None:
            self.ani.event_source.stop()
        self.init_data_if_needed()
        self.current_idx = 0
        self.update_display()

    def pause_titration(self, event):
        if self.ani is not None and self.ani.event_source is not None:
            self.ani.event_source.stop()

    def add_one_drop(self, event):
        if self.ani is not None and self.ani.event_source is not None:
            self.ani.event_source.stop()
        if not self.init_data_if_needed():
            return
        if self.current_idx < len(self.Vb_array) - 1:
            self.current_idx += 1
        self.update_display()

    def start_titration(self, event):
        if self.ani is not None and self.ani.event_source is not None:
            self.ani.event_source.stop()
        if not self.init_data_if_needed():
            return
        if self.current_idx >= len(self.Vb_array) - 1:
            self.current_idx = 0

        self.ani = animation.FuncAnimation(self.fig, self.update_frame, frames=len(self.Vb_array),
                                           interval=20, blit=False, repeat=False)
        plt.draw()

    def update_frame(self, frame):
        if self.current_idx >= len(self.Vb_array) - 1:
            if self.ani is not None and self.ani.event_source is not None:
                self.ani.event_source.stop()
            return self.line, self.dot

        current_Vb = self.Vb_array[self.current_idx]

        if (self.Veq - 5) <= current_Vb <= (self.Veq + 5):
            self.current_idx += 1
        else:
            self.current_idx += 4

        if self.current_idx >= len(self.Vb_array):
            self.current_idx = len(self.Vb_array) - 1

        self.update_display()
        return self.line, self.dot

    def update_display(self):
        current_Vb = self.Vb_array[self.current_idx]
        current_pH = self.pH_array[self.current_idx]

        self.line.set_data(self.Vb_array[:self.current_idx+1], self.pH_array[:self.current_idx+1])
        self.dot.set_data([current_Vb], [current_pH])
        self.volume_text.set_text(f'가한 염기 부피\n{current_Vb:.2f} mL')

        max_total_V = self.Va + (self.Veq * 2.0)
        current_total_V = self.Va + current_Vb
        max_beaker_height = 29.0

        h = (current_total_V / max_total_V) * max_beaker_height
        self.liquid_rect.set_height(h)

        if current_pH < 8.2:
            liquid_color = 'whitesmoke'
        elif current_pH < 10.0:
            intensity = (current_pH - 8.2) / 1.8
            liquid_color = (1.0, 0.5 - 0.5*intensity, 0.8 - 0.3*intensity, 0.5 + 0.5*intensity)
        else:
            liquid_color = (1.0, 0.0, 0.5, 0.9)

        self.liquid_rect.set_facecolor(liquid_color)
        plt.draw()

if __name__ == '__main__':
    sim = TitrationSimulator()
    plt.show()
