# Manipulador — Controle de Robô via G-Code + Unity

Sistema de controle de um manipulador robótico de 6 graus de liberdade (GRBL).
Gera trajetórias Bézier, resolve a cinemática inversa, envia G-Code para o
controlador GRBL e espelha o movimento em tempo real no Unity 3D.

## Funcionalidades

- **Cinemática inversa** (método de Craig) para posicionar o efetuador em `(x, y, z)`
- **Trajetórias Bézier** com interpolação de orientação (A, B, C) para movimentos suaves
- **Controle por ângulos de juntas (J1–J6)**: envia um `G1` direto com os valores
  GRBL; depois de um comando de juntas, trajetórias/rotina ficam bloqueadas até o Home
- **Espelhamento no Unity 3D** via socket TCP com duração real de cada segmento
  (feedrate linear `F800`), sincronizando a velocidade do gêmeo digital com o robô
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
| `gui.py` | Interface PyQt6 (gráfico de trajetória, campos J1–J6 e controles) |
| `robot_control.py` | Orquestração: interpolação, movimentos, envio de juntas, recuperação de falha |
| `ik_craig.py` | Cinemática inversa (método de Craig) |
| `bezier.py` | Geração da trajetória Bézier em `(x, y, z)` |
| `serial_driver.py` | Comunicação serial com o GRBL + log de G-Code |
| `unity_client.py` | Cliente TCP para espelhamento no Unity (envia ângulos + duração do segmento) |
| `mock_serial.py` | Simulador de GRBL (sem hardware) |
| `config.py` | Parâmetros GRBL (`$`) e nome do arquivo de log |

## Recuperação de falha

Cada comando enviado é gravado em `gcode_log.txt`. Na inicialização, o sistema
varre o log de trás para frente e, se houver um último movimento G1 não zerado,
envia o movimento inverso para desfazê-lo e reancora o zero com `G92`. Depois de
processado, o log é apagado para a sessão atual.

## Modo juntas e sincronia com o Unity

A interface trabalha com os 6 ângulos das juntas (J1–J6, valores GRBL). Cada
comando gera um `G1 X J1 Y J2 Z J3 A J4 B J6 C J5` direto. Depois do primeiro
comando de juntas, o modo juntas fica ativo e bloqueia trajetórias/rotina até o
botão **Home** ser usado — que desfaz o último movimento via `gcode_log.txt` e
volta ao estado inicial.

No espelhamento, o Python envia a cada ponto também a **duração do segmento**
(`distância no espaço das juntas / feedrate`), então o Unity interpola cada trecho
no mesmo tempo do robô físico, em vez de usar uma velocidade fixa por junta.
`MyListener.cs` já interpreta esse 7º valor como duração do segmento.
