import re

import numpy as np
import bezier as bz
import ik_craig as ik
from config import GCODE_LOG

class RobotController:
    def __init__(self, serial_driver, unity_client):
        """Guarda as referências de comunicação e o estado inicial de posição e orientação do robô."""
        self.serial = serial_driver
        self.unity = unity_client
        
        # Estado inicial do manipulador
        self.P0 = np.array([403.3643, 0, 570.3432])
        self.Ri = np.array([[0, 0, 1], [0, -1, 0], [1, 0, 0]])
        self.base_offset = np.array([-137, 645, 25])
        self.modo_juntas = False

    def interpolar_abc(self, R_ini, P_ini, R_fim, P_fim, n=21):
        """Interpola linearmente os ângulos do pulso (A, B, C) entre a pose inicial e a final."""
        A0, B0, C0 = ik.calculo_angulos_abc(R_ini, P_ini)
        Af, Bf, Cf = ik.calculo_angulos_abc(R_fim, P_fim)
        return (np.round(np.linspace(A0, Af, n), 2),
                np.round(np.linspace(B0, Bf, n), 2),
                np.round(np.linspace(C0, Cf, n), 2))

    def executar_movimento(self, x, y, z, A, B, C, feedrate=800):
        """Calcula os ângulos das juntas para cada ponto, envia ao GRBL (G1) e espelha no
        Unity com a duração de cada segmento (feedrate linear, F em unidades/min)."""
        angulos = []
        for i in range(len(x)):
            theta1, theta2, theta3 = ik.calculo_angulos(x[i], y[i], z[i])
            angulos.append([theta1, theta2, theta3, A[i], -C[i], B[i]])

        angulos = np.array(angulos)
        for i in range(len(angulos)):
            theta1, theta2, theta3, A_grbl, B_grbl, C_grbl = angulos[i]
            self.unity.send_angles(theta1, theta2, -theta3, A[i], B[i], -C[i], feedrate)
            self.serial.send(f"G1 X{theta1} Y{theta2} Z{theta3} A{A_grbl} B{B_grbl} C{C_grbl} F{feedrate}")

    def enviar_juntas(self, j1, j2, j3, j4, j5, j6):
        """Envia um G1 direto com os 6 ângulos das juntas (valores GRBL) e espelha no Unity.
        Ativa o modo juntas: bloqueia trajetórias/rotina até o Home ser usado."""
        self.modo_juntas = True
        self.serial.send(f"G1 X{j1} Y{j2} Z{j3} A{j4} B{j6} C{j5} F50")
        self.unity.send_angles(j1, j2, -j3, j4, j5, j6)

    def calcular_tempo_trajetoria(self, x, y, z, theta4, theta5, theta6, feedrate=800, fator_seg=1.2):
        """Estima o tempo (s) da trajetória pela distância percorrida em cada segmento dividida pelo feedrate."""
        angulos = []
        for i in range(21):
            t1, t2, t3 = ik.calculo_angulos(x[i], y[i], z[i])
            angulos.append([t1, t2, t3, theta4[i], theta5[i], theta6[i]])

        angulos = np.array(angulos)
        deltas = np.diff(angulos, axis=0)                              # (20, 6)
        distancia_total = np.sum(np.sqrt(np.sum(deltas**2, axis=1)))   # norma euclidiana por segmento, somada

        tempo_min = distancia_total / feedrate     # F do GRBL é sempre unidades/min
        tempo_s = tempo_min * 60 * fator_seg

        print(f"[TRAJETÓRIA] Tempo estimado: {tempo_s:.1f} s")
        return tempo_s

    def home(self):
        """Retorna o robô à posição inicial (Home) com trajetória Bézier e atualiza o estado."""
        if self.modo_juntas:
            print("Modo juntas ativo — desfazendo último movimento via log (Home).")
            self.recuperar_do_log()
            self.P0 = np.array([403.3643, 0, 570.3432])
            self.Ri = np.array([[0, 0, 1], 
                                [0, -1, 0], 
                                [1, 0, 0]])
            self.modo_juntas = False
            return None, None, None

        P3 = np.array([403.3643, 0, 570.3432])
        Rf = np.array([[0, 0, 1], 
                       [0, -1, 0], 
                       [1, 0, 0]])
        
        x1, y1, z1 = bz.calculo_pontos(self.P0, P3, self.Ri, Rf)
        A1, B1, C1 = self.interpolar_abc(self.Ri, self.P0, Rf, P3, 21)
        
        self.executar_movimento(x1, y1, z1, A1, B1, C1)
        self.Ri = Rf
        self.P0 = P3

        return x1, y1, z1

    def recuperar_do_log(self):
        """Se o último G1 do log não for tudo zero, envia o inverso para
        desfazer o deslocamento e reancora o zero (G92)."""
        try:
            with open(GCODE_LOG) as f:
                linhas = f.read().splitlines()
        except (FileNotFoundError, OSError):
            return

        padrao = re.compile(r'G1\s+X(-?[\d.]+)\s+Y(-?[\d.]+)\s+Z(-?[\d.]+)\s+A(-?[\d.]+)\s+B(-?[\d.]+)\s+C(-?[\d.]+)')
        ultimo = None
        for linha in reversed(linhas):
            m = padrao.search(linha)
            if m:
                ultimo = m
                break
        if not ultimo:
            return

        vals = [float(v) for v in ultimo.groups()]
        if all(v == 0 for v in vals):
            return

        neg = [0.0 if v == 0 else round(-v, 2) for v in vals]
        self.serial.send(f"G1 X{neg[0]:g} Y{neg[1]:g} Z{neg[2]:g} A{neg[3]:g} B{neg[4]:g} C{neg[5]:g} F800")
        self.serial.send("G92 X0 Y0 Z0 A0 B0 C0")
        self.serial.send("G1 X0 Y0 Z0 A0 B0 C0 F800")

    def rotina_lapis_suporte(self, plot_callback=None):
        """Máquina de estados que pega o lápis da mesa e o encaixa no suporte, desenhando no gráfico quando há callback."""
        import time

        if self.modo_juntas:
            print("Modo juntas ativo — use o Home para retornar antes de executar a rotina.")
            return

        b = np.array([-137, 645, 25])
        # ---------------------------------------------------------
        # 1. DEFINIÇÃO DOS PONTOS E MATRIZES
        # ---------------------------------------------------------
        P_lapis = np.array([-300, 210, 0])        # Lápis na mesa
        P_apr_lapis = P_lapis + np.array([0, 0, 100]) # 10cm acima do lápis
        
        P_suporte = np.array([10, 120, 250])     # Ponto de encaixe no suporte
        P_apr_suporte = P_suporte + np.array([0, 0, 100]) # 10cm acima do suporte

        # Rotações
        # R1: Garra para baixo (para pegar o lápis deitado)
        R_baixo = np.array([[ 0,  -1,  0], 
                            [ -1, 0,  0], 
                            [ 0,  0, -1]]) 
        
        # R2: Garra virada 90 graus (Pitch/Roll) para o lápis ficar na vertical
        gama = 0
        alpha = np.rad2deg(np.arctan2(abs(P_suporte[1] - b[1]), abs(P_suporte[0] - b[0])))
        if b[0] > P_suporte[0]:
            gama = -(180-alpha)
        else:
            gama = -alpha

        print(f"Alpha = {alpha}")
        print(f"gama = {gama}")
        gama_rad = np.deg2rad(gama)


        R_vertical = np.array([[-np.sin(gama_rad), 0, np.cos(gama_rad)],
                    [np.cos(gama_rad), 0, np.sin(gama_rad)],
                    [0,                1, 0]], dtype=float)

        # ---------------------------------------------------------
        # 2. EXECUÇÃO DA MÁQUINA DE ESTADOS
        # ---------------------------------------------------------
        P_lapis -= b
        P_apr_lapis -= b
        P_suporte -= b
        P_apr_suporte -= b
        # Estado 1: Sair do Home para cima do Lápis (Bézier)
        x, y, z = bz.calculo_pontos(self.P0, P_apr_lapis, self.Ri, R_baixo)
        if plot_callback: plot_callback(list(x), list(y), list(z), True)
        A, B, C = self.interpolar_abc(self.Ri, self.P0, R_baixo, P_lapis, 21)
        self.executar_movimento(x, y, z, A, B, C)
        self.Ri = R_baixo
        self.P0 = P_apr_lapis

        pausa = self.calcular_tempo_trajetoria(x, y, z, A, B, C)
        time.sleep(pausa+1)
        # Estado 2: Descer, pegar o lápis e Recuar (Linear)
        x, y, z = bz.calculo_linear(P_apr_lapis, P_lapis, R_baixo)
        if plot_callback: plot_callback(list(x), list(y), list(z), False)
        A = np.full(21, A[-1])
        B = np.full(21, B[-1])
        C = np.full(21, C[-1])
        self.executar_movimento(x, y, z, A, B, C)
        pausa = self.calcular_tempo_trajetoria(x,y,z,A,B,C)
        time.sleep(pausa+1)
        self.serial.send("M97 B0 T0.2") # Fecha a garra
        time.sleep(1) # Aguarda fechamento
        
        x, y, z = bz.calculo_linear(P_lapis, P_apr_lapis, R_baixo)
        if plot_callback: plot_callback(list(x), list(y), list(z), False)
        self.executar_movimento(x, y, z, A, B, C)
        self.P0 = P_apr_lapis

        pausa = self.calcular_tempo_trajetoria(x, y, z, A, B, C)
        time.sleep(pausa+1)

        # Estado 3: Ir para cima do suporte girando a garra (Bézier)
        x, y, z = bz.calculo_pontos(self.P0, P_apr_suporte, self.Ri, R_vertical)
        if plot_callback: plot_callback(list(x), list(y), list(z), False)
        A, B, C = self.interpolar_abc(self.Ri, self.P0, R_vertical, P_suporte, 21)
        self.executar_movimento(x, y, z, A, B, C)
        self.Ri = R_vertical
        self.P0 = P_apr_suporte
        pausa = self.calcular_tempo_trajetoria(x, y, z, A, B, C)
        time.sleep(pausa+1)

        # Estado 4: Descer no suporte, soltar e Recuar (Linear)
        x, y, z = bz.calculo_linear(P_apr_suporte, P_suporte, R_vertical)
        if plot_callback: plot_callback(list(x), list(y), list(z), False)
        A = np.full(21, A[-1])
        B = np.full(21, B[-1])
        C = np.full(21, C[-1])
        self.executar_movimento(x, y, z, A, B, C)
        pausa = self.calcular_tempo_trajetoria(x, y, z, A, B, C)
        time.sleep(pausa+1)
        self.serial.send("M97 B60 T0.2") # Abre a garra
        time.sleep(1)
        
        x, y, z = bz.calculo_linear(P_suporte, P_apr_suporte, R_vertical)
        if plot_callback: plot_callback(list(x), list(y), list(z), False)
        self.executar_movimento(x, y, z, A, B, C)
        self.P0 = P_apr_suporte
        pausa = self.calcular_tempo_trajetoria(x, y, z, A, B, C)
        time.sleep(pausa+1)

        # Estado 5: Voltar para Home (Bézier)
        x, y, z = self.home()
        if plot_callback: plot_callback(list(x), list(y), list(z), False)