# LocalSMS

Synchronise les SMS d'un téléphone **Android** vers un logiciel **Windows** (`LocalSMS.exe`) qui expose une
interface web locale. **100 % local** : pas de cloud, pas d'abonnement, aucune donnée ne quitte votre réseau.

```
 Android (Kotlin)  ──HTTP──▶  LocalSMS.exe (Python/FastAPI + SQLite)  ──▶  navigateur (React)
  Wi-Fi local  ou  USB (adb reverse)       REST /api/v1 · WebSocket /ws · /docs
```

## Fonctionnalités
- Synchronisation initiale de tout l'historique (lots de 200, reprise exacte après coupure).
- Réception des nouveaux SMS en direct (ContentObserver + WebSocket), SMS envoyés inclus.
- **File d'attente hors ligne** persistante côté téléphone ; nouvelle tentative avec délai croissant ; reprise au retour du réseau, au redémarrage du téléphone, et toutes les 15 min (WorkManager).
- **Détection des doublons** côté serveur (empreinte SHA-256 conversation + date + sens + texte) : renvoyer un lot est sans risque, même après réinstallation ou changement de format de numéro (`0321…` = `+261321…`).
- Conversations, pagination par curseur stable, recherche insensible à la casse et aux accents (texte, numéro, nom, sens, dates).
- État du téléphone : en ligne/hors ligne, batterie, file d'attente, dernière synchro, transport (USB/Wi-Fi).
- Interface en français, responsive, thème clair/sombre automatique.
- API REST documentée sur `/docs` (Swagger UI embarqué, fonctionne hors ligne).

Requested chat rename
Completed with input: {
  "title": "Installation de LocalSMS",
  "automatic": true
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android\\gradlew.bat"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\README.md"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\docs"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\backend"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\web"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android"
}

Read , lines 1 to 120
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\README.md",
  "view_range": [
    1,
    120
  ]
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\docs\\ARCHITECTURE.md"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\web\\package.json"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\backend\\requirements.txt"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\backend\\requirements-dev.txt"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android\\build.gradle.kts"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android\\settings.gradle.kts"
}

Find files matching `**/*`

Le dépôt contient trois parties : un serveur Windows (Python/FastAPI + SQLite), une interface React, et une application Android. Je vérifie maintenant les scripts et artefacts présents pour distinguer l’installation prête à l’emploi de la compilation depuis les sources.

Read , lines 100 to 180
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\README.md",
  "view_range": [
    100,
    180
  ]
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\scripts\\build_windows.ps1"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\scripts\\dev.ps1"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android\\app\\build.gradle.kts"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android\\app\\src\\main\\AndroidManifest.xml"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\backend\\run_localsms.py"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\scripts"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\dist"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\build"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\android\\gradle\\wrapper\\gradle-wrapper.properties"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\backend\\localsms\\__main__.py"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\backend\\localsms\\launcher.py"
}

Read 
Completed with input: {
  "path": "C:\\Users\\developper\\Desktop\\LocalSMS\\.gitignore"
}

## Ce que fait le projet

LocalSMS transfère les SMS d’un téléphone Android vers un serveur local sur Windows. Le serveur stocke les données sur le PC dans une base SQLite, et l’interface web permet de consulter et rechercher les conversations. Le projet comprend un serveur Python/FastAPI, une interface React et une application Android native ; les données ne sont pas envoyées vers le cloud. Le `README du projet` et le document `ARCHITECTURE.md` donnent plus de détails.

## Installation et premier démarrage

### 1. Démarrer le serveur Windows

Un exécutable existe déjà dans `dist`. Lancez `LocalSMS.exe` par double-clic. Il démarre le serveur et ouvre l’interface dans le navigateur, normalement à l’adresse `http://127.0.0.1:8765`.

Si l’exécutable est absent ou si vous préférez le reconstruire depuis les sources :

1. Installez **Python 3.10 ou plus récent** et **Node.js 18 ou plus récent**.
2. Ouvrez PowerShell dans le dossier du projet.
3. Lancez :
   ```powershell
   .\scripts\build_windows.ps1
   ```
   Le script compile l’interface web, installe les dépendances Python, lance les tests et construit l’exécutable. Le résultat attendu est `dist\LocalSMS.exe`. Les détails sont dans `build_windows.ps1`.

### 2. Construire l’application Android

Le dépôt ne semble pas inclure d’APK prêt à installer. Pour en créer un :

1. Installez **Android Studio** avec le **JDK 17** et le SDK Android. Le projet demande Android API 34 pour compiler et fonctionne à partir d’Android 8 (API 26).
2. Ouvrez un terminal PowerShell dans le dossier `android`.
3. Construisez l’APK de débogage :
   ```powershell
   .\gradlew.bat assembleDebug
   ```
4. Récupérez le fichier généré ici :
   `android\app\build\outputs\apk\debug\app-debug.apk`
5. Transférez-le sur le téléphone et installez-le, ou utilisez ADB :
   ```powershell
   .\gradlew.bat installDebug
   ```

Android demandera notamment l’autorisation d’accéder aux SMS. Accordez-la pour permettre la synchronisation.

### 3. Associer le téléphone

1. Laissez LocalSMS ouvert sur le PC.
2. Dans l’interface web, ouvrez **Téléphone → Générer un code**.
3. Ouvrez LocalSMS sur le téléphone, saisissez l’adresse du serveur et le code d’association, puis choisissez **Associer et synchroniser**.
4. L’application commence alors la synchronisation ; elle conserve les SMS en attente si la connexion est temporairement interrompue.

### 4. Choisir la connexion

- **USB (recommandé)** : activez le débogage USB sur le téléphone, branchez-le au PC et acceptez la demande d’autorisation. Installez les Android Platform Tools (`adb`) si nécessaire. Dans l’interface, activez **Téléphone → Liaison USB** ; l’adresse à utiliser dans l’application est `http://127.0.0.1:8765`.
- **Wi-Fi local** : activez l’accès réseau local dans **Réglages** puis redémarrez LocalSMS. Sur le téléphone, utilisez l’adresse locale du PC affichée dans l’onglet **Téléphone**. Autorisez LocalSMS dans le pare-feu Windows si celui-ci le demande, uniquement pour votre réseau privé.

## À retenir

Par défaut, le serveur n’est accessible que depuis le PC. Le mode Wi-Fi l’ouvre au réseau local ; le trafic est alors en HTTP non chiffré. La base contenant les SMS n’est pas chiffrée non plus : protégez votre session Windows et préférez l’USB si le réseau n’est pas de confiance.

Pour développer le projet plutôt que l’installer, les étapes et scripts sont décrits dans le `README` ; le script `dev.ps1` lance l’API et l’interface de développement.

## Arborescence
```
backend/   API FastAPI, SQLite, lanceur, tests (pytest), spec PyInstaller
web/       Interface React + Vite (build → backend/localsms/web)
android/   Application Android native (Kotlin, Compose, WorkManager)
scripts/   build_windows.ps1/.bat, dev.ps1/.sh, e2e_test.py, make_icon.py
```

## Utilisation rapide
1. Lancez `LocalSMS.exe` : une console s'ouvre, le serveur démarre sur `http://127.0.0.1:8765`, le navigateur s'ouvre connecté automatiquement.
2. Installez l'APK sur le téléphone, ouvrez l'application.
3. Dans l'interface web, onglet **Téléphone → Générer un code**.
4. Dans l'application : adresse du serveur + code → **Associer et synchroniser** (accordez l'accès aux SMS).

### Connexion par USB (recommandée : rien n'est exposé au réseau)
1. Téléphone : *Options pour les développeurs → Débogage USB*, branchez le câble, acceptez la clé RSA.
2. Installez les *platform-tools* Android (adb) ; placez `adb.exe` dans le PATH, ou dans `platform-tools\` à côté de `LocalSMS.exe`, ou indiquez son chemin dans **Réglages**.
3. Onglet **Téléphone → Liaison USB → Activer** (ou cochez l'activation automatique).
4. Dans l'application, adresse du serveur : `http://127.0.0.1:8765`.

### Connexion par Wi-Fi local
1. **Réglages → Autoriser le téléphone via le Wi-Fi local → Redémarrer** (ou `LocalSMS.exe --lan`).
2. Autorisez LocalSMS dans le pare-feu Windows pour les réseaux **privés** si Windows le demande.
3. L'onglet **Téléphone** affiche les adresses (`http://192.168.x.x:8765`) à saisir dans l'application.

## Compilation

### Windows `.exe` (à faire sous Windows)
Prérequis : Python 3.10+ et Node.js 18+.
```powershell
.\scripts\build_windows.ps1          # → dist\LocalSMS.exe (fichier unique)
.\scripts\build_windows.ps1 -OneDir  # → dist\LocalSMS\LocalSMS.exe (démarrage plus rapide)
```
Le script compile l'interface, lance les tests, construit l'exe, puis **relance le test de bout en bout contre l'exe produit**.
PyInstaller ne fait pas de compilation croisée : un `.exe` ne peut être produit que sous Windows.
Windows SmartScreen / certains antivirus peuvent signaler un exe PyInstaller non signé : c'est un faux positif connu ; signez l'exe avec votre certificat si vous le diffusez.

### Application Android
Prérequis : Android Studio (JDK 17 inclus) ou SDK + JDK 17.
```
cd android
./gradlew assembleDebug      # → app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest  # tests unitaires
```
Release signée : créez `android/keystore.properties` (ignoré par Git) avec `storeFile`, `storePassword`, `keyAlias`, `keyPassword`, puis `./gradlew assembleRelease`.
Android 8.0+ (API 26) ; testé conceptuellement jusqu'à Android 14 (targetSdk 34).

### Développement
`scripts/dev.ps1` (Windows) ou `scripts/dev.sh` : API + Vite avec proxy (`http://localhost:5173`).
Tests : `cd backend && pip install -r requirements-dev.txt && pytest` puis `python scripts/e2e_test.py`.

## Sécurité
| Mesure | Détail |
|---|---|
| Écoute par défaut | `127.0.0.1` uniquement ; le mode LAN est **explicite** (réglage ou `--lan`) |
| Filtrage réseau | Même en mode LAN : IP privées/loopback seulement, IP publiques refusées (403) |
| Administration | Jeton `lsa_…` (fichier `admin_token`), accepté **uniquement depuis le PC** (`--lan-admin` pour l'ouvrir au LAN, déconseillé) |
| Téléphones | Jeton `lsd_…` par appareil, stocké **haché** (SHA-256) côté PC, chiffré (Keystore AES-256) côté Android ; révocable |
| Appairage | Code 8 caractères, usage unique, 10 min ; anti force brute (429 après 10 échecs/5 min/IP) |
| WebSocket | Authentification par premier message (jeton jamais dans l'URL), contrôle `Origin` et `Host` |
| Navigateur | En-tête `Host` vérifié (anti DNS-rebinding), CSP stricte, `X-Frame-Options: DENY`, jeton transmis via fragment d'URL (jamais envoyé au serveur) |
| Validation | Pydantic strict (tailles, bornes, types), requêtes SQL paramétrées, caractères `%`/`_` échappés |
| Données | `%LOCALAPPDATA%\LocalSMS` (base, jeton, réglages, journaux) ; droits restreints ; exclues de Git ; les journaux ne contiennent ni SMS ni jetons |
| Android | `allowBackup=false`, aucune sauvegarde cloud, HTTP clair refusé hors adresses locales |

**Limites à connaître**
- Sur Wi-Fi, le trafic est en **HTTP non chiffré** (usage réseau domestique de confiance). Pour un réseau non fiable, préférez l'USB.
- La base SQLite n'est **pas chiffrée** : activez BitLocker sur le disque. Quiconque accède à votre session Windows accède aux SMS.
- Seuls les **SMS** sont synchronisés (pas les MMS, ni RCS/« Chat »).
- Android ne laisse un service permanent que s'il n'est pas tué : désactivez l'optimisation de batterie pour l'application (bouton fourni). Le Play Store restreint la permission READ_SMS : l'app est conçue pour une installation directe de l'APK.
- La détection de doublon repose sur (conversation, horodatage à la ms, sens, texte) : deux SMS strictement identiques à la même milliseconde seraient fusionnés (cas pratiquement inexistant).

## Dossier de données
`%LOCALAPPDATA%\LocalSMS` : `localsms.db`, `admin_token`, `settings.json`, `logs\`. Pour tout effacer : fermer LocalSMS puis supprimer ce dossier. Options CLI : `--port`, `--lan`, `--lan-admin`, `--no-browser`, `--data-dir`, `--reset-admin-token`.

## API (extrait — voir `/docs`)
Authentification : `Authorization: Bearer <jeton>`.
| Méthode | Route | Rôle |
|---|---|---|
| POST | `/api/v1/pair` | Associer un téléphone (code) |
| POST | `/api/v1/sms/batch` | Envoyer ≤ 500 SMS (appareil) |
| POST | `/api/v1/device/heartbeat` | Batterie, file d'attente (appareil) |
| GET | `/api/v1/conversations`, `/conversations/{clé}/messages` | Conversations / messages (curseur) |
| GET | `/api/v1/messages` | Recherche (`q`, `direction`, `date_from`, `date_to`, `page`) |
| WS | `/ws` | Événements `sms_new`, `sync_progress`, `device_status` |

## État de vérification (honnêteté)
Vérifié dans l'environnement de livraison :
- 42 tests unitaires/intégration backend (pytest) ✔
- Test de bout en bout avec un vrai processus serveur : appairage, 1 200 SMS en lots, doublons, WebSocket, recherche, persistance après redémarrage, arrêt propre, mode LAN ✔ — **y compris contre un exécutable PyInstaller** (version Linux) ✔
- Build de l'interface React ✔ ; redémarrage automatique (changement de mode réseau) ✔
- Validation d'URL Kotlin compilée et exécutée ✔

**Non vérifié ici** (pas de Windows ni de SDK Android dans l'environnement de génération) :
- La compilation du `.exe` Windows lui-même : lancez `build_windows.ps1` (il rejoue le test E2E sur l'exe).
- La compilation et l'exécution de l'application Android sur appareil : le code est complet mais n'a **pas été compilé** ici. Au premier `./gradlew assembleDebug`, de petites corrections de version/API sont possibles ; testez sur un vrai téléphone (comportement des constructeurs : Xiaomi, Samsung, etc.).
