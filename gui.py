import threading
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QLineEdit, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class PlotCanvas(FigureCanvas):
    """Classe responsável por renderizar o gráfico 3D da trajetória."""
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        """Cria a figura 3D e configura os eixos."""
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111, projection='3d')
        super().__init__(fig)
        self._configurar_eixos()

    def _configurar_eixos(self):
        """Define os rótulos e o título do gráfico."""
        self.axes.set_title("Trajetória do Movimento")
        self.axes.set_xlabel("Eixo X")
        self.axes.set_ylabel("Eixo Y")
        self.axes.set_zlabel("Eixo Z")

    def plot_trajectory(self, x, y, z, limpar=True):
        """Desenha a trajetória no gráfico 3D."""
        if limpar:
            self.axes.clear()
            self._configurar_eixos()

        self.axes.plot(x, y, z, marker='o', linestyle='-', linewidth=2, markersize=3)
        self.draw()


class RobotGUI(QMainWindow):
    """Janela principal do sistema de controle do robô."""
    update_status = pyqtSignal(str)
    update_plot = pyqtSignal(list, list, list, bool)

    def __init__(self, controller):
        """Monta a janela, conecta os sinais e inicia o timer de escuta do Unity."""
        super().__init__()
        self.controller = controller
        self.em_movimento = threading.Event()

        # Configuração de Sinais da UI
        self.update_status.connect(self.set_status)
        self.update_plot.connect(self.atualizar_grafico)

        # Configuração da Janela
        self.setWindowTitle("Controle do Manipulador com Gêmeo Digital")
        self.resize(800, 500)

        # Layout Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Timer para escutar interações via Unity
        self.timer_unity = QTimer(self)
        self.timer_unity.timeout.connect(self.verificar_botao_unity)
        self.timer_unity.start(100)

        # Build da Interface
        left_panel = self._criar_painel_esquerdo()
        main_layout.addWidget(left_panel)

        self.canvas = PlotCanvas(self, width=5, height=5)
        main_layout.addWidget(self.canvas)

    def _criar_painel_esquerdo(self) -> QWidget:
        """Monta o painel lateral com os controles e entradas numéricas."""
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(280)

        # Grupo de Ângulos das Juntas (J1-J6, valores GRBL)
        group_pos = QGroupBox("Ângulos das Juntas")
        grid = QGridLayout()
        self.entradas = {}

        for i, nome in enumerate(["J1", "J2", "J3", "J4", "J5", "J6"]):
            lbl = QLabel(nome)
            lbl.setFixedWidth(30)
            entrada = QLineEdit("0")
            entrada.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, i, 0)
            grid.addWidget(entrada, i, 1)
            self.entradas[nome] = entrada

        group_pos.setLayout(grid)
        left_layout.addWidget(group_pos)

        # Exibição de Status
        self.status_lbl = QLabel("Aguardando comando...")
        self.status_lbl.setStyleSheet("color: gray; font-weight: bold;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.status_lbl)

        # Botões de Ação
        btn_enviar = QPushButton("Enviar Juntas")
        btn_enviar.setMinimumHeight(40)
        btn_enviar.clicked.connect(self.enviar_pos)
        left_layout.addWidget(btn_enviar)

        btn_home = QPushButton("Ir para Home")
        btn_home.setMinimumHeight(30)
        btn_home.clicked.connect(self.home)
        left_layout.addWidget(btn_home)

        btn_rotina = QPushButton("Executar Tarefa Lápis")
        btn_rotina.setMinimumHeight(40)
        btn_rotina.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_rotina.clicked.connect(self.executar_rotina_lapis)
        left_layout.addWidget(btn_rotina)

        btn_abrir = QPushButton("Abrir Garra")
        btn_abrir.clicked.connect(lambda: self.controller.serial.send("M97 B60 T0.2"))
        left_layout.addWidget(btn_abrir)

        btn_fechar = QPushButton("Fechar Garra")
        btn_fechar.clicked.connect(lambda: self.controller.serial.send("M97 B0 T0.2"))
        left_layout.addWidget(btn_fechar)

        left_layout.addStretch()

        btn_encerrar = QPushButton("Encerrar Sistema")
        btn_encerrar.setStyleSheet("color: red;")
        btn_encerrar.clicked.connect(self.close)
        left_layout.addWidget(btn_encerrar)

        return left_panel

    # --- SLOTS E LÓGICA DE INTERACTION ---
    def set_status(self, text: str):
        """Atualiza o texto de status na interface."""
        self.status_lbl.setText(text)

    def atualizar_grafico(self, x: list, y: list, z: list, limpar: bool = True):
        """Slot chamado via sinal para desenhar no canvas."""
        self.canvas.plot_trajectory(x, y, z, limpar)

    def verificar_botao_unity(self):
        """Verifica se o botão de envio foi pressionado na interface do Unity."""
        unity = self.controller.unity
        serial = self.controller.serial

        if unity and unity.check_button_pressed():
            if self.controller.modo_juntas:
                self.set_status("Modo juntas ativo — pressione Home para retornar")
                return

            j1, j2, j3, j4, j5, j6 = unity.get_current_unity_angles()

            print("=" * 50)
            print("[UNITY] Botão 'ENVIAR' pressionado na interface!")
            print(f"[UNITY] Ângulos lidos: J1:{j1} | J2:{j2} | J3:{j3} | J4:{j4} | J5:{j5} | J6:{j6}")

            self.controller.modo_juntas = True
            comando = f"G1 X{j1} Y{j2} Z{-j3} A{j4} B{-j6} C{j5} F800"
            if serial:
                serial.send(comando)
                print(f"[ARDUINO] Comando enviado: {comando}")
            print("=" * 50)

    def enviar_pos(self):
        """Lê os campos J1-J6 e dispara o envio do G1 direto em thread paralela."""
        if self.em_movimento.is_set():
            return
        try:
            valores = [float(self.entradas[nome].text()) for nome in ["J1", "J2", "J3", "J4", "J5", "J6"]]
        except ValueError:
            self.set_status("Erro: valores inválidos")
            return

        self.em_movimento.set()
        self.set_status("Enviando Juntas...")
        threading.Thread(target=self._executar_movimento, args=(valores,), daemon=True).start()

    def _executar_movimento(self, valores):
        """Executa o envio dos ângulos das juntas ao GRBL e Unity."""
        self.controller.enviar_juntas(*valores)
        self.em_movimento.clear()
        self.update_status.emit("Comando de juntas enviado!")

    def home(self):
        """Retorna o robô para a posição inicial (Home)."""
        def _go_home():
            self.em_movimento.set()
            self.update_status.emit("Retornando ao Home...")
            x, y, z = self.controller.home()
            if x is not None:
                self.update_plot.emit(list(x), list(y), list(z), True)
            self.em_movimento.clear()
            self.update_status.emit("Aguardando comando...")

        if not self.em_movimento.is_set():
            threading.Thread(target=_go_home, daemon=True).start()

    def executar_rotina_lapis(self):
        """Dispara a rotina automatizada em uma thread secundária."""
        def _disparar():
            self.update_status.emit("Executando Pick & Place...")
            self.controller.rotina_lapis_suporte(plot_callback=self.update_plot.emit)
            self.update_status.emit("Rotina concluída!")

        if not self.em_movimento.is_set():
            threading.Thread(target=_disparar, daemon=True).start()