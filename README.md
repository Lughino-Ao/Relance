# RelanceFacile — MVP fonctionnel

Application de facturation et relance automatique de factures impayées,
testée de bout en bout (voir "Ce qui a été vérifié" ci-dessous).

## Fonctionnalités

- Inscription / connexion (mots de passe hashés, sessions sécurisées)
- Gestion des clients
- Création de factures (client, montant, devise, échéance)
- Calcul automatique du stade de relance selon le retard : J+3 (poli),
  J+10 (ferme), J+20 (final)
- Génération d'un lien WhatsApp pré-rempli en un clic pour chaque relance
  (aucun coût, aucune API tierce payante)
- Marquage manuel "payée"
- Limite de 5 factures/mois sur le plan gratuit, appliquée côté serveur
- Page d'abonnement avec emplacement pour votre Stripe Payment Link

## Ce qui a été vérifié (pas juste écrit — exécuté et testé)

- Le serveur démarre et répond en mode développement **et** en mode
  production (gunicorn)
- Parcours complet : inscription → connexion → ajout client → création
  facture → calcul du bon stade de relance → lien WhatsApp correct →
  marquage payé → mise à jour en base
- CSRF : toute requête POST sans jeton valide est rejetée (HTTP 400)
- Authentification : le dashboard est inaccessible sans être connecté
- IDOR : un utilisateur ne peut pas modifier les factures d'un autre
  utilisateur (HTTP 404, testé avec deux comptes distincts)
- Injection SQL : requêtes paramétrées partout, tentative d'injection
  dans le login neutralisée
- Limite du plan gratuit : bloque bien à la 6e facture du mois

## Ce qui N'A PAS été vérifié (limites assumées, pas cachées)

- **Aucun audit de sécurité professionnel** n'a été fait. "Testé et sans
  bug connu" n'équivaut pas à "audité par un tiers".
- **Aucun rate-limiting** sur les tentatives de connexion — un attaquant
  peut essayer de nombreux mots de passe. À ajouter avant un vrai
  lancement public (ex. Flask-Limiter, gratuit).
- **Le paiement Stripe n'est pas connecté par webhook.** Le lien Stripe
  Payment Link encaisse l'argent, mais l'activation du statut "payant"
  d'un compte reste manuelle (modification directe en base par vous).
  C'est le choix assumé de la V1 "concierge" retenu dans notre échange
  précédent.
- **Pas de tests automatisés (pytest).** Les vérifications ci-dessus ont
  été faites manuellement via curl, une seule fois. Pas de suite de
  tests qui tourne à chaque modification future.
- **SQLite, pas de sauvegarde automatique.** Convient pour <100
  utilisateurs. Si le projet grossit, migrer vers PostgreSQL (Render et
  Railway offrent un tier gratuit).

## Déploiement (gratuit) — étapes exactes

### 1. Créer le dépôt Git
```bash
cd invoice-reminder/app
git init
git add .
git commit -m "MVP initial"
```
Poussez sur GitHub (compte gratuit).

### 2. Déployer sur Render (tier gratuit)
1. Créez un compte sur render.com
2. "New Web Service" → connectez votre dépôt GitHub
3. Build command : `pip install -r requirements.txt`
4. Start command : `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`
5. Dans "Environment", ajoutez les variables :
   - `SECRET_KEY` : générez une valeur aléatoire (ex. `python3 -c "import os; print(os.urandom(32).hex())"`)
   - `STRIPE_PAYMENT_LINK` : votre lien Stripe (créé gratuitement dans
     votre dashboard Stripe, une fois votre compte Stripe éligible —
     **vérifiez cette éligibilité pour votre pays avant de compter
     dessus**, comme signalé dans notre échange précédent)

Render fournit une base SQLite éphémère par défaut (elle se réinitialise
à chaque redéploiement) — pour la persistance réelle, ajoutez un "Disk"
gratuit (1 Go inclus) monté sur le chemin défini par `DB_PATH`.

### 3. Initialiser la base au premier déploiement
Dans le "Shell" de Render (ou en SSH Railway) :
```bash
python3 -c "from db import init_db; init_db()"
```

### 4. Activer un compte payant manuellement (V1 concierge)
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('app.db')
conn.execute(\"UPDATE users SET subscription_status='active' WHERE email='client@example.com'\")
conn.commit()
"
```

## Développement local

```bash
pip install -r requirements.txt
export SECRET_KEY=dev-secret-key
python3 app.py
```
Ouvrez http://127.0.0.1:5000
