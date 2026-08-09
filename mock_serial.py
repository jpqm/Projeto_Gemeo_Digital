import time
import re
import threading


class MockSerialGRBL:
    def __init__(self, port='SIM', baudrate=115200, timeout=1, atraso_movimento=0.05):
        """Inicializa o simulador com buffer, trava de thread e posição zero, disparando o boot."""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._atraso_movimento = atraso_movimento

        self._buffer = []
        self._lock = threading.Lock()

        # posição simulada: X Y Z A B C (graus/mm, tanto faz para o teste)
        self._pos = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        self._boot()

    # ---- ciclo de boot, imitando as linhas que o GRBL manda ao ligar ----
    def _boot(self):
        """Adiciona as linhas de inicialização que o GRBL envia ao ligar."""
        self._buffer.append("")
        self._buffer.append("Grbl 1.1h ['$' for help]")

    # ---- API compatível com pyserial ----
    def write(self, data):
        """Interpreta o comando recebido: simula movimento (G1/G0), garra (M97) ou confirma com 'ok'."""
        cmd = data.decode().strip()
        print(f"[MOCK] >> {cmd}")

        with self._lock:
            if cmd == '?':
                mpos = ",".join(f"{v:.3f}" for v in self._pos[:3])
                self._buffer.append(f"<Idle|MPos:{mpos}|FS:0,0>")
                return

            if cmd.startswith(('G1', 'G0')):
                self._simular_movimento(cmd)

            elif cmd.startswith('M97'):
                # comando de garra/atuador (M97 B.. T..) - simula o tempo de acionamento
                time.sleep(self._atraso_movimento * 2)

            # $100=250, $$, G90, F600, etc: apenas confirma
            self._buffer.append('ok')

    def _simular_movimento(self, cmd):
        """Atualiza as posições simuladas dos eixos conforme o comando e aguarda o tempo de movimento."""
        eixos = 'XYZABC'
        for i, eixo in enumerate(eixos):
            m = re.search(rf'{eixo}(-?\d+\.?\d*)', cmd)
            if m:
                self._pos[i] = float(m.group(1))
        time.sleep(self._atraso_movimento)

    def readline(self):
        """Retorna a próxima linha do buffer de resposta (vazio se não houver nada)."""
        with self._lock:
            if self._buffer:
                linha = self._buffer.pop(0)
                return (linha + '\n').encode()
        return b''

    @property
    def in_waiting(self):
        """Quantidade de respostas pendentes no buffer."""
        return len(self._buffer)

    def close(self):
        """Finaliza o simulador (apenas imprime no exemplo)."""
        print("[MOCK] Conexão serial simulada encerrada")
