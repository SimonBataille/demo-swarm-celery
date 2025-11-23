Voici une version du **README** réécrite à la troisième personne, sans tutoiement et avec un ton plus neutre et professionnel.

---

# 🌊 FastAPI + Celery + Redis — Déploiement local en Docker Swarm avec Traefik & HTTPS (mkcert)

Ce projet constitue un environnement complet permettant de développer et de déployer localement une application Python orchestrée via **Docker Swarm**, comprenant :

* **FastAPI** (API HTTP servie par Uvicorn)
* **Celery** (traitement asynchrone)
* **Redis 7** (broker + backend)
* **Traefik v2** (reverse proxy + gestion du HTTPS)
* **Docker Swarm** en mode single-node
* **GitHub Actions** pour la CI (Build & Push Docker Hub) et la CD locale
* **HTTPS local** configuré via `mkcert`

L’ensemble a pour objectif de reproduire en local une architecture proche d’une configuration de production.

---

## 📁 Structure du projet

```text
GIT_TEST_CELERY_SWARM_CICD/
├── Dockerfile
├── main.py
├── tasks.py
├── requirements.txt
├── docker-stack.traefik_external_https.yml
├── docker-stack.traefik_external_https_local.yml
├── traefik/
│   └── dynamic/
│       └── tls.yml
└── .github/
    └── workflows/
        ├── ci.yml
        └── cd.yml
```

---

## ⚙️ Composants principaux

### 1. FastAPI (`main.py`)

Application HTTP exposée via Traefik.
En interne : écoute sur `0.0.0.0:8000`.
Depuis l’extérieur, via Traefik et HTTPS :

```
https://localhost/app/...
```

Traefik applique une règle de type **StripPrefix** supprimant `/app` avant la transmission au backend.

---

### 2. Celery (`tasks.py`)

Un worker Celery exécuté dans un service distinct, basé sur la même image Docker que FastAPI.

Redis est utilisé comme :

* **broker** : `redis://redis:6379/0`
* **backend** : `redis://redis:6379/1`

---

### 3. Redis

Service de messagerie interne (non exposé publiquement).
Communication uniquement via le réseau overlay `backend`.

---

### 4. Traefik v2

Reverse proxy orchestré dans Swarm, attaché à un réseau overlay externe `traefik`.

Fonctionnalités :

| Fonction         | Détails                                    |
| ---------------- | ------------------------------------------ |
| Entrée HTTP      | port 80 → redirection vers HTTPS           |
| Entrée HTTPS     | port 443                                   |
| Certificats      | fournis via mkcert et montés dans `/certs` |
| Config dynamique | via `/dynamic/tls.yml`                     |
| Routage          | `Host("localhost") && PathPrefix("/app")`  |
| Middleware       | StripPrefix(`/app`)                        |

La configuration TLS est fournie par le fichier versionné `traefik/dynamic/tls.yml`.

---

## 🔐 HTTPS local via mkcert

### Installation

```bash
mkcert -install
```

### Génération des certificats

```bash
mkcert -cert-file local-cert.pem -key-file local-key.pem localhost 127.0.0.1 ::1
```

### Intégration dans le déploiement (CD)

Les certificats ne sont pas versionnés.
Ils sont placés dans les **GitHub Secrets** :

* `LOCAL_CERT`
* `LOCAL_KEY`

Le workflow CD reconstitue automatiquement les fichiers PEM dans :

```
$HOME/traefik/certs/
```

Et exporte la variable d’environnement :

```
TRAEFIK_CERTS_DIR=$HOME/traefik/certs
```

Ce dossier est monté par Traefik :

```yaml
- ${TRAEFIK_CERTS_DIR}:/certs:ro
```

---

## 🔁 CI/CD (GitHub Actions)

### CI — *Build & Push* (`.github/workflows/ci.yml`)

Pipeline chargé de :

1. builder l’image Docker depuis le Dockerfile,
2. la tagger (`sha-<short_sha>` et éventuellement `latest`),
3. pousser l’image sur Docker Hub,
4. déclencher le workflow CD si la branche est `main`.

---

### CD — *Local Swarm Deployment* (`.github/workflows/cd.yml`)

Pipeline exécuté sur un **runner self-hosted**, chargé de :

1. Reconstituer les certificats mkcert dans `$HOME/traefik/certs`
2. Exporter :

   * `TRAEFIK_CERTS_DIR`
   * `TRAEFIK_DYNAMIC_DIR=${GITHUB_WORKSPACE}/traefik/dynamic`
3. Réinitialiser Docker Swarm (single-node)
4. Recréer le réseau overlay externe `traefik`
5. Générer dynamiquement le fichier `/tmp/stack.yml` via `sed`
6. Déployer la stack :

   ```bash
   docker stack deploy -c /tmp/stack.yml lab --with-registry-auth
   ```

L’application devient alors accessible en HTTPS :

```
https://localhost/app/healthz
```

---

## 🔁 Intégration Continue & Déploiement Continu (CI/CD)

Le projet inclut deux workflows GitHub Actions situés dans :
`.github/workflows/ci.yml` et `.github/workflows/cd.yml`.

L’ensemble forme une chaîne CI/CD locale complète :

1. **CI : Build & Push Docker Hub**
2. **CD : Déploiement Swarm local via runner self-hosted**

L’architecture est sécurisée par des **branch protection rules**, des permissions strictes pour GitHub Actions, et un **runner local dédié** équipé des permissions Docker.

---

### 🧪 CI — Build & Push (Docker Hub)

Le workflow CI :

* construit l’image Docker à partir du Dockerfile ;
* tague l’image avec :

  * `sha-<short_sha>` ;
  * `latest` (optionnel) ;
* pousse l’image sur Docker Hub ;
* publie des artefacts (SHA court) pour la CD ;
* déclenche automatiquement la CD si la branche concernée est `main`.

Cette étape garantit que toutes les images déployées proviennent de la CI, que leur signature SHA est traçable et que la branche `main` reste protégée par un pipeline complet.

---

### 🚀 CD — Déploiement local en Docker Swarm (runner self-hosted)

Le workflow CD utilise un **runner installé sur la machine locale**, portant le label :

```
swarm-manager
```

Ce workflow :

1. reconstitue les certificats TLS mkcert depuis les secrets GitHub ;

2. exporte deux variables d’environnement utilisées par le stack Swarm :

   * `TRAEFIK_CERTS_DIR` → répertoire hôte contenant les PEM ;
   * `TRAEFIK_DYNAMIC_DIR` → répertoire dynamique versionné (`traefik/dynamic`) ;

3. réinitialise Docker Swarm proprement ;

4. recrée le réseau overlay externe `traefik` ;

5. génère un fichier stack `/tmp/stack.yml` via `sed` ;

6. déploie la stack `lab` :

   ```bash
   docker stack deploy -c /tmp/stack.yml lab --with-registry-auth
   ```

7. valide le déploiement via :

   ```bash
   docker stack services lab
   ```

Cette CD locale permet de tester un pipeline complet, identique à une production orchestrée, mais déployé directement sur la machine de développement.

---

## 🛡️ Sécurité GitHub : Branch Protection Rules

Le projet est configuré avec des règles strictes de protection de la branche `main` :

| Règle                                 | État                             |
| ------------------------------------- | -------------------------------- |
| Require a pull request before merging | ✔️ activé                        |
| Require status checks to pass         | ✔️ CI obligatoire                |
| Require linear history                | ✔️ activé                        |
| Restrict who can push                 | ✔️ seul le propriétaire du dépôt |
| Allow force pushes                    | ❌ désactivé                      |
| Allow deletion of the branch          | ❌ désactivé                      |

Ainsi, aucun changement n’atteint `main` sans :

* validation par la CI,
* un merge propre,
* un historique linéaire,
* une protection contre les push non autorisés ou destructifs.

---

## 🔐 Permissions GitHub Actions

La configuration des actions respecte des contraintes de sécurité élevées :

* **Actions autorisées :** GitHub Marketplace + créateurs vérifiés.
* **Fork PRs :** approbation obligatoire pour tous les collaborateurs externes.
* **Workflow permissions :** lecture seule sur le dépôt.
* **Pas de permissions d’écriture implicites.**
* **Pas d’envoi automatique de secrets** aux forks ou PR provenant de comptes externes.

Cette configuration limite strictement les risques d’exfiltration de secrets ou d'exécution de workflows non autorisés.

---

## ⚙️ Installation du runner GitHub self-hosted

Le runner local est installé sur la machine Linux qui exécute Docker Swarm.
Les commandes essentielles d’installation sont les suivantes.

### 1. Création d’un utilisateur dédié

```bash
sudo adduser runner
sudo usermod -aG docker runner
su - runner
```

### 2. Installation du runner GitHub

```bash
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.329.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.329.0/actions-runner-linux-x64-2.329.0.tar.gz

tar xzf actions-runner-linux-x64-*.tar.gz
```

La registration du runner s’effectue ensuite depuis l’interface GitHub.

### 3. Ajout du label pour la CD Swarm

```bash
# Dans GitHub > Settings > Actions > Runners
Label: swarm-manager
```

Ce label est utilisé dans `cd.yml` :

```yaml
runs-on: [self-hosted, swarm-manager]
```

---

## 📦 Interaction avec Docker Swarm depuis le runner

L’utilisateur `runner` appartient au groupe `docker`, ce qui permet :

* l’exécution de commandes `docker`,
* l’initialisation du Swarm,
* la création de réseaux overlay,
* la gestion des stacks.

Exemple :

```bash
docker service ps lab_app --no-trunc
```

Il est ainsi possible de monitorer et de dépanner les services déployés par la CD.

---

## 🎯 Rôle global du CI/CD

L’ensemble des workflows :

* garantit que seules des images valides, construites par la CI, sont déployées ;
* impose un flux Git propre et sécurisé via les branch protection rules ;
* réalise un déploiement local automatisé, identique à une architecture de production ;
* maintient un environnement Swarm reproductible et fiable.

Ce pipeline constitue une base robuste pour expérimenter, apprendre ou valider des architectures DevOps modernes en environnement local.

---

## 🌐 Réseaux Docker Swarm

Deux réseaux overlay sont utilisés :

| Réseau    | Usage                                               |
| --------- | --------------------------------------------------- |
| `backend` | communication interne (app ↔ redis ↔ worker)        |
| `traefik` | réseau frontal partagé avec Traefik (reverse proxy) |

Le réseau `traefik` est défini comme **externe** afin de persister entre les déploiements.

---

## 🔍 Commandes utiles

### Vérifier les services Swarm

```bash
docker stack services lab
```

### Logs Traefik

```bash
docker service logs lab_traefik -f
```

### Logs de l’application FastAPI

```bash
docker service logs lab_app -f
```

### Réinitialisation locale du cluster

```bash
docker swarm leave --force
docker swarm init --advertise-addr 192.168.1.10
docker network create --driver=overlay traefik
```

---

## 🧪 Développement simple (hors Swarm)

Pour exécuter l’application sans orchestration :

### FastAPI

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Celery

```bash
celery -A tasks worker --loglevel=info
```

Ce mode n’utilise ni Traefik ni HTTPS, mais reste pratique pour du développement rapide.

---

## 🎯 Objectif du projet

* Reproduire localement une architecture cohérente avec une production Docker.
* Tester un pipeline complet CI/CD avec un runner local.
* Utiliser un reverse proxy moderne (Traefik v2) incluant gestion du HTTPS.
* Déployer automatiquement des images Docker Hub dans un environnement Swarm contrôlé.

L’ensemble forme un laboratoire permettant d’apprendre, de tester et de valider des workflows DevOps avancés en environnement local.

---

# 🔧 Tests locaux sans passer par la CI/CD

Le projet peut également être exécuté **entièrement en local** sans impliquer GitHub Actions.
Ce mode est utile pour du développement rapide, pour vérifier une configuration Traefik/Swarm, ou pour tester des certificats HTTPS locaux générés manuellement.

## 1. Construction locale de l’image

Depuis le répertoire du projet :

```bash
cd /home/simon/Documents/Git/GIT_TEST_CELERY_SWARM_CICD/
docker build -t lab-app:local .
```

L’image locale `lab-app:local` pourra ensuite être utilisée dans la stack Swarm locale.

---

## 2. Fichier de stack local (HTTPS, mkcert)

Utiliser le fichier dédié :

```
docker-stack.traefik_external_https_local.yml
```

Ce fichier monte les certificats locaux et le répertoire dynamique Traefik, et utilise l’image locale `lab-app:local`.

---

## 3. Initialisation de Docker Swarm (mode local)

```bash
docker swarm leave --force
docker swarm init --advertise-addr 192.168.1.10

docker network rm traefik 2>/dev/null || true
docker network create --driver=overlay traefik
```

* Le cluster Swarm est réinitialisé proprement.
* Le réseau overlay externe `traefik` est recréé.

---

## 4. Déploiement manuel de la stack

```bash
docker stack deploy -c docker-stack.traefik_external_https_local.yml lab --with-registry-auth
docker stack services lab
```

### Logs Traefik

```bash
docker service logs lab_traefik --tail 50 --timestamps --details
```

### Vérification du placement des tâches

```bash
docker service ps lab_traefik --no-trunc
```

### Forcer un redeploy d’un service

```bash
docker service update --force lab_traefik
```

L’application devient alors accessible sur :

```
https://localhost/app/healthz
```

---

## 5. Extinction et nettoyage du cluster Swarm

```bash
docker stack rm lab
sleep 5
docker network rm traefik 2>/dev/null
docker swarm leave --force
```

Cela arrête proprement :

* les services,
* les overlay networks,
* et quitte Swarm.

---

## 6. Configuration HTTPS locale (Traefik dynamique)

Créer les dossiers nécessaires pour Traefik :

```bash
mkdir -p /home/simon/Documents/Geek/traefik/dynamic
touch /home/simon/Documents/Geek/traefik/dynamic/tls.yml
```

Éditer le fichier :

```yaml
tls:
  certificates:
    - certFile: /certs/localhost+1.pem
      keyFile: /certs/localhost+1-key.pem
```

> Ces fichiers doivent correspondre aux certificats générés localement via `mkcert`.

Ce fichier est monté dans le conteneur Traefik à travers `/dynamic/tls.yml`, comme en environnement CI/CD, ce qui permet une configuration TLS totalement cohérente entre les deux modes de déploiement.

---

## 1. Vue globale CI/CD + Swarm + App

```text
                      ┌────────────────────────────┐
                      │        GitHub Repo         │
                      │  (code FastAPI / Celery)   │
                      └────────────┬───────────────┘
                                   │  push / PR
                                   │
                     ┌─────────────▼─────────────┐
                     │      CI Workflow          │
                     │   (.github/workflows/     │
                     │        ci.yml)            │
                     └─────────────┬─────────────┘
                                   │
                                   │ build image
                                   │ push image
                                   │  (Docker Hub)
                                   ▼
                       ┌───────────────────────┐
                       │     Docker Hub       │
                       │  DOCKERHUB_USERNAME/ │
                       │       lab-app        │
                       └─────────┬────────────┘
                                 │
                                 │
                    ┌────────────▼─────────────┐
                    │      CD Workflow         │
                    │ (.github/workflows/cd.yml│
                    │  runner self-hosted      │
                    └────────────┬─────────────┘
                                 │
                                 │  docker stack deploy
                                 ▼
                 ┌───────────────────────────────────────┐
                 │   Machine locale (Swarm manager)      │
                 │  (runner label: swarm-manager)        │
                 └───────────────────────────────────────┘
```

---

## 2. Vue Swarm / Services / Réseaux

```text
                     ╔════════════════════════════════╗
                     ║  Docker Swarm (single node)    ║
                     ║  Node: simon-HP-EliteBook...   ║
                     ╚════════════════════════════════╝

                 Overlay network "traefik" (externe)
                 ─────────────────────────────────────────
                       │                         │
                       │                         │
            ┌──────────▼───────────┐   ┌─────────▼─────────┐
            │      traefik         │   │        app         │
            │  (reverse proxy)     │   │  FastAPI (uvicorn) │
            │                      │   │                    │
 Host:80 -> │ entrypoint web       │   │  port 8000         │
 Host:443-> │ entrypoint websecure │   └────────────────────┘
            │  /certs (mkcert)     │
            │  /dynamic (tls.yml)  │
            └──────────────────────┘
                       │
                       │ routes:
                       │  Host(`localhost`)
                       │  && PathPrefix(`/app`)
                       └─> StripPrefix(`/app`)
                           vers app:8000

                 Overlay network "backend"
                 ─────────────────────────────────────────

           ┌───────────────┐       ┌────────────────┐
           │      app      │       │    redis       │
           │   FastAPI     │◀─────▶│ Redis 7        │
           │               │       │ (broker /      │
           └───────────────┘       │  backend)      │
                   ▲               └────────────────┘
                   │
                   │
           ┌───────────────┐
           │    worker     │
           │  Celery       │
           └───────────────┘

- app & worker utilisent :
  CELERY_BROKER_URL = redis://redis:6379/0
  CELERY_RESULT_BACKEND = redis://redis:6379/1
```

---

## 3. Vue détaillée Traefik / TLS

```text
                   Host (machine locale)
        /home/simon/Documents/Geek/traefik/
        ├── certs/
        │   ├── local-cert.pem      (cert mkcert)
        │   └── local-key.pem       (clé mkcert)
        └── dynamic/
            └── tls.yml             (config TLS Traefik dynamique)

                │
                │ volumes
                ▼

        ┌──────────────────────────────────────────┐
        │        Service Swarm: lab_traefik        │
        │        image: traefik:v2.11              │
        ├──────────────────────────────────────────┤
        │ /certs    ← monté depuis ${TRAEFIK_CERTS_DIR}   │
        │ /dynamic  ← monté depuis ${TRAEFIK_DYNAMIC_DIR} │
        ├──────────────────────────────────────────┤
        │ entrypoints:                             │
        │   web        :80                         │
        │   websecure  :443 (TLS activé)           │
        │                                          │
        │ providers:                               │
        │   - docker (swarmMode=true)              │
        │   - file   (directory=/dynamic)          │
        └──────────────────────────────────────────┘

      tls.yml (dans /dynamic) :

      tls:
        certificates:
          - certFile: /certs/local-cert.pem
            keyFile:  /certs/local-key.pem
```

---

## 4. Pipeline complet (vue synthétique)

```text
Développeur
    │
    │  git push
    ▼
GitHub Repo
    │
    ├─> CI (ci.yml)  : build + push image lab-app:sha-xxxx vers Docker Hub
    │
    └─> CD (cd.yml)  : sur runner local [self-hosted, swarm-manager]
          │
          │  1. Reconstruit les certs depuis secrets → $HOME/traefik/certs
          │  2. Définit TRAEFIK_CERTS_DIR / TRAEFIK_DYNAMIC_DIR
          │  3. (Ré-)initialise Swarm + réseau overlay traefik
          │  4. Génère /tmp/stack.yml
          │  5. docker stack deploy lab
          ▼
   Docker Swarm (node local)
          │
          ├─ service lab_traefik (exposé :80/:443)
          ├─ service lab_app (FastAPI)
          ├─ service lab_worker (Celery)
          └─ service lab_redis (Redis)

Client HTTP (navigateur / curl)
    │
    └─ https://localhost/app/...  →  Traefik  →  app:8000
```

---

Voici une **section “Démarrage rapide”** claire, concise et directement exploitable pour votre README, parfaitement adaptée à votre architecture Traefik + Swarm + HTTPS local.

---

# 🚀 Démarrage rapide

Cette section permet de **démarrer l’environnement complet (Traefik + FastAPI + Celery + Redis) en HTTPS local** en quelques commandes, sans passer par la CI/CD.

---

## 1) Cloner le projet

```bash
git clone https://github.com/<votre_repo>/GIT_TEST_CELERY_SWARM_CICD.git
cd GIT_TEST_CELERY_SWARM_CICD
```

---

## 2) Construire l’image localement

```bash
docker build -t lab-app:local .
```

---

## 3) Préparer Traefik en HTTPS local (mkcert)

Assurez-vous que mkcert est installé et initialisé :

```bash
mkcert -install
```

Créer les certificats locaux :

```bash
mkdir -p /home/simon/Documents/Geek/traefik/certs
mkcert -cert-file /home/simon/Documents/Geek/traefik/certs/localhost+1.pem \
       -key-file  /home/simon/Documents/Geek/traefik/certs/localhost+1-key.pem \
       localhost 127.0.0.1 ::1
```

Créer la configuration TLS dynamique :

```bash
mkdir -p /home/simon/Documents/Geek/traefik/dynamic
cat << 'EOF' > /home/simon/Documents/Geek/traefik/dynamic/tls.yml
tls:
  certificates:
    - certFile: /certs/localhost+1.pem
      keyFile: /certs/localhost+1-key.pem
EOF
```

---

## 4) (Re)initialiser Docker Swarm

```bash
docker swarm leave --force
docker swarm init --advertise-addr 192.168.1.10
```

---

## 5) Créer le réseau Traefik

```bash
docker network rm traefik 2>/dev/null
docker network create --driver=overlay traefik
```

---

## 6) Déployer toute la stack

Utiliser la version locale HTTPS :

```bash
docker stack deploy -c docker-stack.traefik_external_https_local.yml lab --with-registry-auth
```

Vérifier les services :

```bash
docker stack services lab
docker service logs lab_traefik --tail 50 --timestamps --details
docker service ps lab_traefik --no-trunc
```

Forcer une mise à jour de Traefik si nécessaire :

```bash
docker service update --force lab_traefik
```

---

## 7) Accéder à l'application

* Navigateur :
  👉 **[https://localhost/app/healthz](https://localhost/app/healthz)**

* curl :
  (utiliser le certificat root mkcert)

```bash
curl --cacert ~/.local/share/mkcert/rootCA.pem https://localhost/app/healthz
```

---

## 8) Détruire proprement l’environnement

```bash
docker stack rm lab
sleep 5
docker network rm traefik 2>/dev/null
docker swarm leave --force
```

---

# 🚀 Démarrage rapide avec CI/CD (GitHub Actions)

Cette procédure permet de déployer automatiquement la stack complète (Traefik + FastAPI + Celery + Redis) sur la machine locale via **GitHub Actions** et le runner self-hosted.

## 1) Prérequis

1. **Runner self-hosted installé** sur la machine locale, avec Docker et le label :

   ```text
   swarm-manager
   ```

2. **Secrets GitHub configurés** dans le dépôt :

   * `DOCKERHUB_USERNAME`
   * `DOCKERHUB_TOKEN`
   * `LOCAL_CERT`  → contenu complet du certificat mkcert (`-----BEGIN CERTIFICATE----- ...`)
   * `LOCAL_KEY`   → contenu complet de la clé privée (`-----BEGIN PRIVATE KEY----- ...`)

3. **Branch protection rules** actives sur `main` (optionnel mais recommandé) :

   * Pull request requise avant merge
   * Status check CI obligatoire (Build & Push)
   * Historique linéaire
   * Restriction des push sur `main`

---

## 2) Workflow CI : Build & Push

1. Pousser les changements sur une branche de travail.

2. Ouvrir une **pull request** vers `main`.

3. Attendre que le workflow **CI (ci.yml)** s’exécute et passe au vert :

   * build de l’image Docker;
   * push de l’image vers Docker Hub (`DOCKERHUB_USERNAME/lab-app:sha-xxxxxxx`).

4. Une fois la CI réussie, fusionner la PR dans `main`.

---

## 3) Déclenchement du déploiement (CD)

Deux possibilités :

### a) Déclenchement automatique

Si le workflow CD est configuré avec :

```yaml
on:
  workflow_run:
    workflows: ["CI - Build & Push (Docker Hub)"]
    types: [completed]
```

Alors, après un succès de la CI sur `main`, le workflow **CD (cd.yml)** est automatiquement lancé sur le runner `self-hosted, swarm-manager`.

### b) Déclenchement manuel (workflow_dispatch)

Il est également possible de lancer le CD manuellement :

1. Aller dans **Actions > CD - Local Swarm Deployment**.
2. Utiliser **“Run workflow”**.
3. Optionnellement, renseigner un `image_tag` spécifique (sinon le SHA court sera utilisé).

---

## 4) Ce que fait le workflow CD

Le workflow **cd.yml** :

1. Récupère le code (`checkout`).

2. Calcule le **tag d’image** à déployer (sha-xxxxxxx ou tag manuel).

3. Se connecte à Docker Hub (via `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`).

4. Reconstruit les certificats TLS locaux à partir de `LOCAL_CERT` et `LOCAL_KEY` dans :

   ```text
   $HOME/traefik/certs/local-cert.pem
   $HOME/traefik/certs/local-key.pem
   ```

5. Exporte les variables d’environnement :

   ```text
   TRAEFIK_CERTS_DIR=$HOME/traefik/certs
   TRAEFIK_DYNAMIC_DIR=$GITHUB_WORKSPACE/traefik/dynamic
   ```

6. Réinitialise Docker Swarm et le réseau `traefik` :

   ```bash
   docker swarm leave --force || true
   docker swarm init --advertise-addr 192.168.1.10
   docker network rm traefik 2>/dev/null || true
   docker network create --driver=overlay traefik
   ```

7. Génère `/tmp/stack.yml` à partir de `docker-stack.traefik_external_https.yml` (ou variante locale), via `sed` pour injecter :

   * `DOCKERHUB_USERNAME`
   * `IMAGE_TAG`

8. Déploie la stack :

   ```bash
   docker stack deploy -c /tmp/stack.yml lab --with-registry-auth
   docker stack services lab
   ```

---

## 5) Vérification après déploiement

Sur la machine locale (Swarm manager / runner) :

```bash
docker stack services lab
docker service logs lab_traefik --tail 50 --timestamps --details
docker service logs lab_app --tail 50
```

Tester l’application :

* Navigateur :

  ```text
  https://localhost/app/healthz
  ```

* ou via `curl` :

  ```bash
  curl --cacert ~/.local/share/mkcert/rootCA.pem https://localhost/app/healthz
  ```

---

Avec ces étapes, le déploiement via **CI/CD** devient le chemin “normal” pour mettre à jour l’application : chaque merge sur `main` entraîne un build Docker, un push sur Docker Hub, puis un déploiement automatique sur le cluster Swarm local.
