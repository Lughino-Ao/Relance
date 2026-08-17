# RelanceFacile — MVP fonctionnel

Application de facturation et relance automatique de factures impayées,
testée de bout en bout (voir "Ce qui a été vérifié" ci-dessous).

## Fonctionnalités

- Inscription / connexion (mots de passe hashés, sessions sécurisées)
- **Mot de passe fort obligatoire** : 8 caractères min., majuscule, minuscule, chiffre — validation serveur + jauge de force en direct
- **Confirmation d'email obligatoire avant connexion**, avec lien de renvoi si non reçu
- Gestion des clients
- Création de factures (client, montant, devise, échéance)
- Calcul automatique du stade de relance selon le retard : J+3 (poli),
  J+10 (ferme), J+20 (final)
- Génération d'un lien WhatsApp pré-rempli en un clic pour chaque relance
  (aucun coût, aucune API tierce payante)
- **Filtres Toutes / Impayées / Payées** sur le tableau de bord
- **Totaux réels** (facturé, encaissé, en attente) calculés depuis la base — pas de chiffres inventés
- **Section "Comment ça marche"** en 3 étapes + démo interactive sur la page d'accueil
- Limite de 5 factures/mois sur le plan gratuit, appliquée côté serveur
- Page d'abonnement avec emplacement pour votre lien de paiement (Stripe / CinetPay / FedaPay)

## Configuration de l'envoi d'email (confirmation de compte)

Sans configuration, l'application fonctionne quand même : le lien de
confirmation est simplement écrit dans les logs du serveur au lieu d'être
envoyé par email — utile pour tester, mais **inutilisable pour de vrais
utilisateurs** qui n'ont pas accès à tes logs.

Pour activer l'envoi réel via Gmail (gratuit, sans domaine à vérifier) :

1. Active la validation en 2 étapes sur le compte Gmail que tu veux utiliser pour l'envoi
2. Crée un "mot de passe d'application" : myaccount.google.com → Sécurité → Mots de passe des applications
3. Ajoute ces variables d'environnement sur Render :
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `587`
   - `SMTP_USER` = ton adresse Gmail complète
   - `SMTP_PASSWORD` = le mot de passe d'application généré (pas ton mot de passe Gmail habituel)
   - `SMTP_FROM` = la même adresse que `SMTP_USER`

Limite non vérifiée : Gmail limite l'envoi à environ 500 emails/jour sur un
compte standard — largement suffisant pour démarrer, à surveiller si le
volume augmente.

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
