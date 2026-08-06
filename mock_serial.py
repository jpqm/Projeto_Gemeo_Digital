"""
mock_serial.py
Simulador simples de uma conexão serial com o GRBL, para testar o
sistema de controle do manipulador sem o Arduino conectado.

Uso no main.py:

    import os
    SIMULAR = os.environ.get("SIMULAR_GRBL", "1") == "1"

    if SIMULAR:
        from mock_serial import MockSerialGRBL
        ser = MockSerialGRBL()
    else:
        ser = serial.Serial('COM3', 115200, timeout=1)

O resto do código (send, executar_movimento, etc.) não precisa mudar,
pois a classe expõe a mesma interface que o objeto serial.Serial usado
pelo pyserial: write(), readline(), in_waiting, close().
"""

import time
import re
import threading


class MockSerialGRBL:
    def __init__(self, port='SIM', baudrate=115200, timeout=1, atraso_movimento=0.05):
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
        self._buffer.append("")
        self._buffer.append("Grbl 1.1h ['$' for help]")

    # ---- API compatível com pyserial ----
    def write(self, data):
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
        eixos = 'XYZABC'
        for i, eixo in enumerate(eixos):
            m = re.search(rf'{eixo}(-?\d+\.?\d*)', cmd)
            if m:
                self._pos[i] = float(m.group(1))
        time.sleep(self._atraso_movimento)

    def readline(self):
        with self._lock:
            if self._buffer:
                linha = self._buffer.pop(0)
                return (linha + '\n').encode()
        return b''

    @property
    def in_waiting(self):
        return len(self._buffer)

    def close(self):
        print("[MOCK] Conexão serial simulada encerrada")
