# Architecture

**Android** : `SyncEngine` lit `content://sms` par `_id` croissant (curseur) → copie dans `OutboxDb` (SQLite, transaction atomique avec le curseur) → envoi par lots de 200 → suppression après accusé. Déclencheurs : `ContentObserver` (service de premier plan), `SmsReceiver` (travail accéléré), `SyncWorker` périodique 15 min, retour réseau, démarrage.

**Serveur** : `main.create_app` (middlewares réseau/Host/CSP, WebSocket, fichiers statiques) ; `api.py` (routes) ; `db.py` (SQLite WAL, `UNIQUE(dedup_hash)`) ; `security.py` (jetons, appairage, limitation) ; `adb.py` (`adb reverse`) ; `launcher.py` (CLI, navigateur, arrêt, relance).

**Clé de conversation** : `n:` + 9 derniers chiffres (numéros) ou `a:` + nom (expéditeurs alphanumériques).
