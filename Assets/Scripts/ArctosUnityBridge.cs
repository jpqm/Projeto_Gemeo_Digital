using UnityEngine;
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;

/// <summary>
/// Recebe os ângulos das juntas do Arctos via UDP (enviados pelo unity_bridge.py
/// no lado do Python) e aplica em tempo real nos ArticulationBody do robô,
/// espelhando o movimento do robô real/simulação no Unity.
///
/// Anexe este script no GameObject raiz do robô ("arctos_urdf").
/// </summary>
public class ArctosUnityBridge : MonoBehaviour
{
    [Header("Rede")]
    public int listenPort = 5005;

    [Header("Nomes dos links (na ordem joint1..joint6)")]
    public string[] jointLinkNames = new string[]
    {
        "Link_1_1", "Link_2_1", "Link_3_1", "Link_4_1", "Link_5_1", "Link_6_1"
    };

    [Header("Links da garra (prismáticos)")]
    public string leftJawLinkName = "Left_jaw_1";
    public string rightJawLinkName = "Right_jaw_1";
    [Tooltip("Deslocamento máximo (m) de cada garra quando totalmente aberta")]
    public float jawMaxOpenMeters = 0.02f;

    [Header("Calibração (offset somado a cada ângulo recebido, em graus)")]
    [Tooltip("Use isto se o zero do Unity não bater com o zero do robô real")]
    public float[] jointOffsetDeg = new float[] { 0, 0, 0, 0, 0, 0 };

    [Header("Suavização")]
    [Tooltip("Velocidade máxima de interpolação (graus/seg). 0 = aplica direto, sem suavizar")]
    public float maxDegreesPerSecond = 0f;

    ArticulationBody[] jointBodies;
    ArticulationBody leftJawBody;
    ArticulationBody rightJawBody;

    UdpClient udpClient;
    Thread receiveThread;
    volatile bool running = false;

    // Buffer compartilhado entre a thread de rede e a thread principal do Unity
    readonly object lockObj = new object();
    float[] latestAngles = new float[6];
    float latestJaw = 0f;
    bool hasNewData = false;

    // Ângulos atualmente aplicados (para suavização)
    float[] currentAngles = new float[6];

    [Serializable]
    class AnglesPayload
    {
        public float theta1, theta2, theta3, theta4, theta5, theta6, jaw;
    }

    void Start()
    {
        // Localiza os ArticulationBody dos 6 joints e das garras na hierarquia
        jointBodies = new ArticulationBody[jointLinkNames.Length];
        for (int i = 0; i < jointLinkNames.Length; i++)
        {
            Transform t = FindDeepChild(transform, jointLinkNames[i]);
            if (t == null)
            {
                Debug.LogWarning($"[ArctosUnityBridge] Link '{jointLinkNames[i]}' não encontrado.");
                continue;
            }
            jointBodies[i] = t.GetComponent<ArticulationBody>();
            currentAngles[i] = jointBodies[i] != null ? jointBodies[i].xDrive.target : 0f;
        }

        Transform lt = FindDeepChild(transform, leftJawLinkName);
        Transform rt = FindDeepChild(transform, rightJawLinkName);
        if (lt != null) leftJawBody = lt.GetComponent<ArticulationBody>();
        if (rt != null) rightJawBody = rt.GetComponent<ArticulationBody>();

        StartListening();
    }

    void StartListening()
    {
        udpClient = new UdpClient(listenPort);
        running = true;
        receiveThread = new Thread(ReceiveLoop) { IsBackground = true };
        receiveThread.Start();
        Debug.Log($"[ArctosUnityBridge] Escutando UDP na porta {listenPort}");
    }

    void ReceiveLoop()
    {
        IPEndPoint anyEndpoint = new IPEndPoint(IPAddress.Any, 0);
        while (running)
        {
            try
            {
                byte[] data = udpClient.Receive(ref anyEndpoint);
                string json = System.Text.Encoding.UTF8.GetString(data);
                AnglesPayload payload = JsonUtility.FromJson<AnglesPayload>(json);

                lock (lockObj)
                {
                    latestAngles[0] = payload.theta1;
                    latestAngles[1] = payload.theta2;
                    latestAngles[2] = payload.theta3;
                    latestAngles[3] = payload.theta4;
                    latestAngles[4] = payload.theta5;
                    latestAngles[5] = payload.theta6;
                    latestJaw = payload.jaw;
                    hasNewData = true;
                }
            }
            catch (SocketException)
            {
                // Socket fechado ao parar o Play — esperado, não é erro real.
                break;
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[ArctosUnityBridge] Erro ao processar pacote UDP: {e.Message}");
            }
        }
    }

    void Update()
    {
        float[] targetAngles = null;
        float targetJaw = 0f;
        bool consume = false;

        lock (lockObj)
        {
            if (hasNewData)
            {
                targetAngles = (float[])latestAngles.Clone();
                targetJaw = latestJaw;
                consume = true;
                hasNewData = false;
            }
        }

        if (!consume) return;

        for (int i = 0; i < jointBodies.Length; i++)
        {
            if (jointBodies[i] == null) continue;

            float desired = targetAngles[i] + jointOffsetDeg[i];

            if (maxDegreesPerSecond > 0f)
            {
                currentAngles[i] = Mathf.MoveTowards(currentAngles[i], desired, maxDegreesPerSecond * Time.deltaTime);
            }
            else
            {
                currentAngles[i] = desired;
            }

            ArticulationDrive drive = jointBodies[i].xDrive;
            drive.target = currentAngles[i];
            jointBodies[i].xDrive = drive;
        }

        // jaw: 0 = fechada, 1 = aberta -> desloca os prismáticos simetricamente
        float jawOffset = Mathf.Clamp01(targetJaw) * jawMaxOpenMeters;
        SetPrismaticTarget(leftJawBody, jawOffset);
        SetPrismaticTarget(rightJawBody, jawOffset);
    }

    void SetPrismaticTarget(ArticulationBody body, float meters)
    {
        if (body == null) return;
        ArticulationDrive drive = body.xDrive;
        drive.target = meters;
        body.xDrive = drive;
    }

    void OnDestroy()
    {
        running = false;
        udpClient?.Close();
        receiveThread?.Join(200);
    }

    Transform FindDeepChild(Transform parent, string name)
    {
        foreach (Transform child in parent)
        {
            if (child.name == name) return child;
            Transform result = FindDeepChild(child, name);
            if (result != null) return result;
        }
        return null;
    }
}
