# Manipulador — Controle de Robô via G-Code + Unity

Sistema de controle de um manipulador robótico de 6 graus de liberdade (GRBL).
Gera trajetórias Bézier, resolve a cinemática inversa, envia G-Code para o
controlador GRBL e espelha o movimento em tempo real no Unity 3D.

## Funcionalidades

- **Cinemática inversa** (método de Craig) para posicionar o efetuador em `(x, y, z)`
- **Trajetórias Bézier** com interpolação de orientação (A, B, C) para movimentos suaves
- **Interface PyQt6** com gráfico de trajetória e controle manual
- **Espelhamento no Unity 3D** via socket TCP (falha sem interromper o sistema)
- **Log de G-Code + recuperação de falha**: ao reiniciar, o robô desfaz o último
  movimento incompleto (G1) e reancora o zero antes de continuar
- **Simulação sem hardware**: usa `MockSerialGRBL` por padrão

## Requisitos

- Python 3.10+
- Dependências: `numpy`, `PyQt6`, `matplotlib`, `pyserial`

## Como executar

```bash
python main.py
```

Por padrão, `SIMULAR_GRBL=1` e o robô é simulado. Para usar o hardware real
(placa GRBL em `COM3`, 115200 baud):

```bash
set SIMULAR_GRBL=0
python main.py
```

Para ajustar a porta/baud, edite `SerialDriver.__init__` em `serial_driver.py`.
O endereço do Unity (`host`/`porta`) fica em `UnityClient.__init__` em
`unity_client.py`.

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Ponto de entrada: monta as dependências, recupera a posição e inicia a GUI |
| `gui.py` | Interface PyQt6 (gráfico de trajetória e controles) |
| `robot_control.py` | Orquestração: interpolação, movimentos, recuperação de falha |
| `ik_craig.py` | Cinemática inversa (método de Craig) |
| `bezier.py` | Geração da trajetória Bézier em `(x, y, z)` |
| `serial_driver.py` | Comunicação serial com o GRBL + log de G-Code |
| `unity_client.py` | Cliente TCP para espelhamento no Unity |
| `mock_serial.py` | Simulador de GRBL (sem hardware) |
| `config.py` | Parâmetros GRBL (`$`) e nome do arquivo de log |

## Recuperação de falha

Cada comando enviado é gravado em `gcode_log.txt`. Na inicialização, o sistema
varre o log de trás para frente e, se houver um último movimento G1 não zerado,
envia o movimento inverso para desfazê-lo e reancora o zero com `G92`. Depois de
processado, o log é apagado para a sessão atual.
