import numpy as np
import bezier as bz
import ik_craig as ik

class RobotController:
    def __init__(self, serial_driver, unity_client):
        self.serial = serial_driver
        self.unity = unity_client
        
        # Estado inicial do manipulador
        self.P0 = np.array([403.3643, 0, 570.3432])
        self.Ri = np.array([[0, 0, 1], [0, -1, 0], [1, 0, 0]])
        self.base_offset = np.array([-137, 645, 25])

    def interpolar_abc(self, R_ini, P_ini, R_fim, P_fim, n=21):
        A0, B0, C0 = ik.calculo_angulos_abc(R_ini, P_ini)
        Af, Bf, Cf = ik.calculo_angulos_abc(R_fim, P_fim)
        return (np.round(np.linspace(A0, Af, n), 2),
                np.round(np.linspace(B0, Bf, n), 2),
                np.round(np.linspace(C0, Cf, n), 2))

    def executar_movimento(self, x, y, z, A, B, C):
        for i in range(len(x)):
            theta1, theta2, theta3 = ik.calculo_angulos(x[i], y[i], z[i])
            self.unity.send_angles(theta1, theta2, -theta3, A[i], B[i], -C[i])
            self.serial.send(f"G1 X{theta1} Y{theta2} Z{theta3} A{A[i]} B{-C[i]} C{B[i]} F800")

    def calcular_pos(self, xf, yf, zf):
        P3_1 = np.array([xf, yf, zf])
        P3 = P3_1 - self.base_offset
        Rf = np.array([[0, -1, 0], [-1, 0, 0], [0, 0, -1]])
        
        x1, y1, z1 = bz.calculo_pontos(self.P0, P3, self.Ri, Rf)
        A1, B1, C1 = self.interpolar_abc(self.Ri, self.P0, Rf, P3, 21)
        
        self.executar_movimento(x1, y1, z1, A1, B1, C1)
        self.Ri = Rf
        self.P0 = P3

        return x1, y1, z1

    def calcular_tempo_trajetoria(self, x, y, z, theta4, theta5, theta6, feedrate=800, fator_seg=1.2):
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

    def rotina_lapis_suporte(self, plot_callback=None):
        import time
        import bezier as bz

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
        self.home()