using UnityEngine;

/// <summary>
/// Script de teste para validar a cadeia cinemática do Arctos no Unity.
/// Anexe este script no GameObject raiz "arctos_urdf" (ou em um objeto vazio
/// que referencie o robô) e ajuste os ângulos alvo pelo Inspector em Play Mode,
/// ou use as teclas numéricas 1-6 para testar cada junta individualmente.
/// </summary>
public class ArctosJointTester : MonoBehaviour
{
    [System.Serializable]
    public class JointTarget
    {
        public string jointName;       // nome do link filho (ex: "Link_1_1")
        [Range(-180f, 180f)]
        public float targetAngleDeg;   // ângulo alvo em graus
        [HideInInspector] public ArticulationBody body;
    }

    [Tooltip("Preencha com os nomes dos links na ordem joint1..joint6")]
    public JointTarget[] joints = new JointTarget[]
    {
        new JointTarget { jointName = "Link_1_1" },
        new JointTarget { jointName = "Link_2_1" },
        new JointTarget { jointName = "Link_3_1" },
        new JointTarget { jointName = "Link_4_1" },
        new JointTarget { jointName = "Link_5_1" },
        new JointTarget { jointName = "Link_6_1" },
    };

    [Tooltip("Velocidade de interpolação (graus/seg) para movimento suave")]
    public float degreesPerSecond = 30f;

    void Start()
    {
        // Localiza os ArticulationBody de cada link pelo nome, buscando na hierarquia
        foreach (var j in joints)
        {
            Transform t = FindDeepChild(transform, j.jointName);
            if (t != null)
            {
                j.body = t.GetComponent<ArticulationBody>();
                if (j.body == null)
                    Debug.LogWarning($"[ArctosJointTester] '{j.jointName}' encontrado, mas sem ArticulationBody.");
            }
            else
            {
                Debug.LogWarning($"[ArctosJointTester] Link '{j.jointName}' não encontrado na hierarquia.");
            }
        }
    }

    void Update()
    {
        // Testa juntas individualmente com as teclas 1-6 (soma/subtrai ângulo)
        for (int i = 0; i < joints.Length && i < 6; i++)
        {
            if (Input.GetKey(KeyCode.Alpha1 + i))
                joints[i].targetAngleDeg += degreesPerSecond * Time.deltaTime;
        }

        // Aplica o ângulo alvo de cada junta ao ArticulationBody (drive de posição)
        foreach (var j in joints)
        {
            if (j.body == null) continue;

            ArticulationDrive drive = j.body.xDrive;
            drive.target = j.targetAngleDeg;
            j.body.xDrive = drive;
        }
    }

    // Busca recursiva por nome em toda a hierarquia (URDF Importer aninha bastante)
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
