import os
import serial
import time
from config import GRBL_SETTINGS

class SerialDriver:
    def __init__(self, port='COM3', baudrate=115200):

        # self.ser = serial.Serial(port, baudrate, timeout=1)

        # time.sleep(2)  # espera GRBL iniciar

        # while self.ser.in_waiting:
        #     line = self.ser.readline().decode().strip()
        #     if line:
        #         print("BOOT:", line)
        
        simular = os.environ.get("SIMULAR_GRBL", "1") == "1"
        if simular:
            from mock_serial import MockSerialGRBL
            self.ser = MockSerialGRBL()
        else:
            self.ser = serial.Serial(port, baudrate, timeout=1)

    def send(self, cmd):
        print(f">> {cmd}")
        self.ser.write((cmd + '\n').encode())
        while True:
            response = self.ser.readline().decode().strip()
            if response:
                print("<<", response)
            if response == 'ok':
                break

    def send_settings(self):
        for key, value in GRBL_SETTINGS.items():
            self.send(f"${key} = {value}")

    def close(self):
        if self.ser:
            self.ser.close()