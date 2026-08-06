import socket
import threading

class UnityClient:
    def __init__(self, host="127.0.0.1", port=25001):
        self.host = host
        self.port = port
        self.sock = None
        self.latest_angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.button_triggered = False # Lembra se o botão foi apertado
        self.listening = False
        self.connect()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            print(f"[Unity] Conectado em {self.host}:{self.port}")
            
            self.listening = True
            threading.Thread(target=self._listen_loop, daemon=True).start()

        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            print(f"[Unity] Não foi possível conectar ({e}). Seguindo sem espelhar.")
            self.sock = None

    def _listen_loop(self):
        buffer = ""
        while self.listening and self.sock:
            try:
                data = self.sock.recv(1024).decode('utf-8')
                if not data:
                    break 
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        partes = line.split(',')
                        
                        if len(partes) >= 7:
                            try:
                                self.latest_angles = [float(p) for p in partes[:6]]
                                gatilho = int(partes[6])
                                
                                if gatilho == 1:
                                    self.button_triggered = True
                                    print("[UnityClient] Sinal de BOTÃO recebido da rede!")
                                    
                            except ValueError as e:
                                print(f"[Erro Parse Python] Falha ao converter números: {partes} | Erro: {e}")
                        else:
                            print(f"[Erro Formato] Esperado 7 parâmetros, recebido {len(partes)}: {partes}")
            except Exception as e:
                print(f"[Unity Listener] Conexão encerrada: {e}")
                break

    def send_angles(self, theta1, theta2, theta3, A, B, C):
        if self.sock is None:
            return
        data = f"{theta1},{theta2},{theta3},{A},{B},{C}\n"
        try:
            self.sock.sendall(data.encode("utf-8"))
        except Exception as e:
            print(f"[Unity] Erro ao enviar: {e}")

    def get_current_unity_angles(self):
        return self.latest_angles

    def check_button_pressed(self):
        """ Retorna True se o botão do Unity foi clicado desde a última checagem """
        if self.button_triggered:
            self.button_triggered = False # Desarma depois de ler
            return True
        return False

    def close(self):
        self.listening = False
        if self.sock:
            self.sock.close()