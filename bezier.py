import numpy as np


def calculo_pontos(P0, P3, Ri, Rf):
    de = 118.815

    P0w = P0 - de*Ri[:, -1]
    P3w = P3 - de*Rf[:, -1]


    if (Ri == Rf).all():
        P1 = np.array([P0w[0], P0w[1], 100])
        P2 = np.array([P3w[0], P3w[1], 100])
    elif Rf[2,2] == -1:
        P1 = np.array([P0w[0], P3w[1], P0w[2]])
        P2 = np.array([P3w[0], P3w[1], P0w[2]])
    elif Rf[2,1] == 1:
        P1 = np.array([P0w[0], P0w[1], P3w[2]])
        P2 = np.array([P0w[0], P3w[1], P3w[2]])
    elif Rf[2,0] == 1 and Ri[2,2] == -1:
        P1 = np.array([P0w[0], P0w[1], P3w[2]])
        P2 = np.array([P3w[0], P0w[1], P3w[2]])
    else:
        P1 = np.array([(P0w[0] + P3w[0])/2, (P3w[1] + P0w[1])/2, P0w[2]])
        P2 = np.array([P3w[0], (P3w[1] + P0w[1])/2, (P0w[2] + P3w[2])/2])

    t = np.linspace(0,1,21)

    x = (1-t)**3*P0w[0] + 3*t*(1-t)**2*P1[0] + 3*t**2*(1-t)*P2[0] + t**3*P3w[0]
    y = (1-t)**3*P0w[1] + 3*t*(1-t)**2*P1[1] + 3*t**2*(1-t)*P2[1] + t**3*P3w[1]
    z = (1-t)**3*P0w[2] + 3*t*(1-t)**2*P1[2] + 3*t**2*(1-t)*P2[2] + t**3*P3w[2]

    return x, y, z

def calculo_linear(P0, P3, R, num_pontos=21):
    """Gera uma interpolação linear entre dois pontos."""
    t = np.linspace(0, 1, num_pontos)
    de = 118.815
    
    P0w = P0 - de*R[:, -1]
    P3w = P3 - de*R[:, -1]

    P1 = np.array([P0w[0], P0w[1], P0w[2]])
    P2 = np.array([P3w[0], P3w[1], P3w[2]])

    x = (1-t)**3*P0w[0] + 3*t*(1-t)**2*P1[0] + 3*t**2*(1-t)*P2[0] + t**3*P3w[0]
    y = (1-t)**3*P0w[1] + 3*t*(1-t)**2*P1[1] + 3*t**2*(1-t)*P2[1] + t**3*P3w[1]
    z = (1-t)**3*P0w[2] + 3*t*(1-t)**2*P1[2] + 3*t**2*(1-t)*P2[2] + t**3*P3w[2]
    return x, y, z