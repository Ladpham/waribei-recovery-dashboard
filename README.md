# Waribei Recovery Dashboard

Dashboard mobile pour les agents de recouvrement (Alassane & Francis).  
Hébergé sur GitHub Pages, données actualisées **toutes les heures** via GitHub Actions.

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/` | Auth bcrypt — mêmes identifiants que le wariportail |
| Opérations | `/operations.html` | Liste des tx PAR 8–30 avec photo, GPS, lien portail |
| Carte | `/map.html` | Carte Leaflet, marqueurs colorés par retard |
| Résultats | `/resultats.html` | Stats hebdo : Valeur, Recup J0/J3/J7/J15/J30 |

## Setup GitHub

### 1. Créer le repo (privé)

```bash
cd recovery_dashboard
git init
git add .
git commit -m "init: recovery dashboard"
gh repo create waribei-recovery-dashboard --private --source=. --push
```

### 2. Ajouter les secrets GitHub

Dans **Settings → Secrets → Actions**, ajouter :

| Secret | Valeur |
|--------|--------|
| `DB_HOST` | `fineract-waribei.cdqyg5vhbgy5.eu-north-1.rds.amazonaws.com` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `waribei` |
| `DB_USER` | `holy` |
| `DB_PASSWORD` | `Holy1234` |

### 3. Activer GitHub Pages

**Settings → Pages → Source** : choisir **Deploy from a branch**, branche `main`, dossier `/docs`.

L'URL sera : `https://<ton-compte>.github.io/waribei-recovery-dashboard/`

### 4. Déclencher le premier refresh manuel

**Actions → Refresh Dashboard Data → Run workflow**

### 5. Lien wariportail dynamique

Dans `operations.html` et `map.html`, remplacer le placeholder :
```js
const WARIPORTAIL_URL = (merchantId) =>
  `https://wariportail.waribei.com/merchant/${merchantId}`;
```
par le vrai pattern de lien une fois que tu me l'envoies.

## Refresh local (test)

```bash
cd recovery_dashboard
DB_HOST=... DB_NAME=waribei DB_USER=holy DB_PASSWORD=Holy1234 \
  python scripts/refresh_data.py
```
