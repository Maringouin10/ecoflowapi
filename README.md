# EcoFlow App (batteries) pour Home Assistant

Intégration HACS qui récupère les données des batteries EcoFlow **par le même
chemin que l'application EcoFlow** : votre e-mail et votre mot de passe EcoFlow,
puis une connexion MQTT temps réel au cloud EcoFlow. Elle **n'utilise pas l'API
développeur IoT**, qui ne donne pas accès à toutes les batteries.

La connexion reprend le « mode Enhanced » de
[shuette42/ecoflow-energy-ha](https://github.com/shuette42/ecoflow-energy-ha),
recentrée sur les batteries portables.

## Appareils pris en charge

| Appareil | Protocole | Données |
|---|---|---|
| DELTA 2 (et DELTA 2 Max) | JSON | ✅ |
| Batterie supplémentaire DELTA 2 | via la DELTA 2 | ✅ capteurs « Batterie supp. 1/2 » |
| DELTA 3 (DELTA 3, 3 Plus, 3 Max) | protobuf | ✅ vérifié sur de vraies trames |
| Batterie supplémentaire DELTA 3 | via la DELTA 3 | ✅ vérifié sur de vraies trames |
| DELTA 3 Ultra | protobuf (même génération que la DELTA 3) | ⚠️ à confirmer |
| DELTA Pro Ultra | protobuf | ⚠️ à confirmer, jusqu'à 5 packs batterie |
| RIVER 2 (2, 2 Max, 2 Pro) | JSON | ⚠️ à confirmer |
| RIVER 3 (3, 3 Plus) | protobuf | ⚠️ à confirmer |

« À confirmer » : le décodage suit les définitions de protocole publiées par les
projets cités plus bas, mais aucune trame de ces modèles n'a encore été testée
ici. Si une valeur paraît fausse, ouvrez une issue avec le fichier de
diagnostic (voir plus bas).

Les batteries supplémentaires n'ont pas de connexion cloud : leurs valeurs
arrivent par la batterie principale et apparaissent comme capteurs de celle-ci.

Version actuelle : **lecture seule**. Les commandes (sorties AC/DC, vitesse de
charge, limites de charge…) viendront dans une deuxième étape.

## Installation

1. HACS → menu ⋮ → **Dépôts personnalisés** → ajoutez
   `https://github.com/maringouin10/ecoflowapi`, catégorie **Intégration**.
2. Installez **EcoFlow App (batteries)**, puis redémarrez Home Assistant.
3. **Paramètres → Appareils et services → Ajouter une intégration →
   EcoFlow App (batteries)**.
4. Saisissez l'e-mail et le mot de passe de l'application EcoFlow, puis cochez
   les batteries à ajouter. Les modèles reconnus sont pré-cochés ; un appareil
   « non reconnu » peut quand même être coché, le décodage suit alors le type
   des trames reçues.

La liste des appareils se modifie ensuite dans **Configurer** sur l'intégration.

## Capteurs

Les capteurs sont créés **quand la batterie envoie la valeur correspondante**,
donc un modèle sans 12 V n'aura pas de capteur 12 V. **Tous les capteurs sont
activés par défaut.**

Capteurs nommés (traduits, avec unités) :

- niveau de charge, état de santé, état (charge/décharge/repos), autonomie et
  temps avant charge complète, cycles, températures batterie et internes ;
- puissances : entrée/sortie totales, AC entrée/sortie (et par prise sur la
  DELTA Pro Ultra), solaire (1, 2, haute/basse tension selon le modèle),
  sorties DC (12 V, Anderson, total DC), USB-A/USB-C, charge/décharge batterie ;
- tensions et courants : batterie, AC entrée/sortie, solaire, 12 V, Anderson,
  chaque port USB et chaque prise AC (DPU), cellules min/max ;
- réglages (lecture) : limites de charge/décharge, réserve de secours,
  puissance de charge AC, délais de mise en veille, AC toujours actif ;
- batteries supplémentaires (DELTA 2/3) et packs (DELTA Pro Ultra) ;
- capteurs binaires : appareil en ligne, sortie AC, 12 V, USB, X-Boost,
  réserve de secours, AC toujours actif, entrée AC branchée.

**Valeurs brutes** : tous les autres champs que la batterie envoie et dont le
nom est connu (≈ 600 champs dans les définitions de protocole publiques) sont
aussi exposés, en capteurs de diagnostic nommés d'après le protocole
(ex. `cell vol 1` … `cell vol 16` = tension de chaque cellule en mV,
`extra1 cell temp 2`, `flow info ac out`, versions de firmware, codes
d'erreur…). Sur une DELTA 3 Plus cela représente environ 280 valeurs en plus
des 60 capteurs nommés. Les numéros de série ne sont jamais exposés.

## Tableau de bord Énergie

L'intégration calcule des compteurs **kWh** (intégration de la puissance,
sauvegardés entre les redémarrages ; un trou de plus de 5 minutes n'est pas
intégré) :

| Tableau de bord | Capteur |
|---|---|
| Stockage batterie – énergie entrant dans la batterie | *Énergie chargée batterie* |
| Stockage batterie – énergie sortant de la batterie | *Énergie déchargée batterie* |
| Production solaire | *Énergie solaire* |
| Consommation d'un appareil | *Énergie sortie AC* / *Énergie sortie totale* |

L'énergie chargée/déchargée est calculée à partir de « entrée totale − sortie
totale » : c'est une bonne approximation (les pertes de conversion comptent
comme sortie) disponible sur tous les modèles. Les DELTA 3 / RIVER 3 exposent en
plus les compteurs internes de l'appareil (« compteur appareil » / « compteur
BMS », désactivés par défaut).

## Fonctionnement

- Une seule connexion MQTT (WebSocket, port 8084) pour tout le compte, avec un
  identifiant client régénéré à chaque connexion, reconnexion avec délai
  croissant et renouvellement des identifiants MQTT chaque jour ou si le
  courtier les refuse.
- Toutes les 30 s une requête `latestQuotas` (comme l'application ouverte) et
  toutes les 5 min une demande d'état complet, pour que les batteries
  continuent à publier.
- Une batterie silencieuse depuis 10 min passe « indisponible ».

## Diagnostic

**Paramètres → Appareils et services → EcoFlow App → ⋮ → Télécharger les
diagnostics** donne l'état de la connexion, toutes les valeurs décodées et la
liste des trames non décodées (numéros de champ), sans e-mail, mot de passe ni
numéro de série complet. C'est ce qu'il faut joindre à une issue pour faire
progresser un modèle « à confirmer ».

## Développement

```bash
pip install -r requirements_test.txt
pytest
python scripts/gen_translations.py   # après un ajout de capteur
```

Les parseurs (`custom_components/ecoflow_app/parsers/`) et le lecteur protobuf
(`proto.py`) sont en Python pur, sans dépendance, et testés sur des captures
réelles de DELTA 3. `parsers/schemas.py` (tous les champs connus) est généré
par `scripts/gen_schemas.py` à partir des définitions publiques citées
ci-dessous.

## Crédits

- [shuette42/ecoflow-energy-ha](https://github.com/shuette42/ecoflow-energy-ha)
  (MIT) : connexion « app », identifiant client MQTT, captures DELTA 3.
- [foxthefox/ioBroker.ecoflow-mqtt](https://github.com/foxthefox/ioBroker.ecoflow-mqtt)
  (MIT) : protocole DELTA Pro Ultra.
- [tolwi/hassio-ecoflow-cloud](https://github.com/tolwi/hassio-ecoflow-cloud)
  (Apache-2.0) : référence des champs DELTA 3 / RIVER 3 et des clés JSON DELTA 2 / RIVER 2.

Voir [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Projet non affilié à
EcoFlow ; le cloud EcoFlow peut changer sans préavis.
