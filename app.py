import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'une_cle_secrete_tres_robuste_pour_pythonanywhere'

# Configuration de la base de données SQLite
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Extensions d'images autorisées
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- MODELES DE BASE DE DONNEES ---

# Table de configuration générale (Textes, WhatsApp, Image de fond)
class ConfigSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre_accueil = db.Column(db.String(200), default="Expert en Puits & Construction")
    slogan = db.Column(db.Text, default="Forage de puits durables et maçonnerie générale de haute qualité.")
    whatsapp_num = db.Column(db.String(20), default="243000000000") # Format international sans +
    bg_image = db.Column(db.String(200), default="default_bg.jpg")

    # Catégorie 1 : Creusage
    creusage_titre = db.Column(db.String(100), default="Creusage & Forage de Puits")
    creusage_desc = db.Column(db.Text, default="Nous creusons des puits adaptés à vos besoins en eau.")

    # Catégorie 2 : Construction
    construction_titre = db.Column(db.String(100), default="Construction & Maçonnerie")
    construction_desc = db.Column(db.Text, default="Travaux de maçonnerie générale, aménagement et finition.")

# Table pour les images de réalisations (Galerie)
class Realisation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    categorie = db.Column(db.String(50), nullable=False) # 'creusage' ou 'construction'
    description = db.Column(db.Text, default="Pas de description.") # <-- AJOUTEZ CETTE LIGNE

# Compte administrateur (Pour sécuriser l'accès au CMS)
class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


# --- ROUTES PRINCIPALES ---

@app.route('/')
def index():
    config = ConfigSite.query.first()
    # Si la config n'existe pas encore, on la crée par défaut
    if not config:
        config = ConfigSite()
        db.session.add(config)
        db.session.commit()

    realisations_creusage = Realisation.query.filter_by(categorie='creusage').all()
    realisations_construction = Realisation.query.filter_by(categorie='construction').all()

    return render_template('index.html', config=config,
                           creusage_img=realisations_creusage,
                           construction_img=realisations_construction)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Vérification directe en texte brut pour débloquer l'accès immédiatement
        if username == 'admin' and password == 'MotDePassePuits2026':
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('admin'))
        else:
            flash('Identifiants incorrects !', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('index'))

# --- ROUTE PANEL ADMIN ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    config = ConfigSite.query.first()

    if request.method == 'POST':
        action = request.form.get('action')

        # 1. Mise à jour des textes et WhatsApp
        if action == 'update_texts':
            config.titre_accueil = request.form['titre_accueil']
            config.slogan = request.form['slogan']
            config.whatsapp_num = request.form['whatsapp_num']
            config.creusage_titre = request.form['creusage_titre']
            config.creusage_desc = request.form['creusage_desc']
            config.construction_titre = request.form['construction_titre']
            config.construction_desc = request.form['construction_desc']

            # Gestion du changement d'image de fond (Background)
            if 'bg_image' in request.files:
                file = request.files['bg_image']
                if file and allowed_file(file.filename):
                    filename = secure_filename("bg_site_" + file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    config.bg_image = filename

            db.session.commit()
            flash('Contenu du site mis à jour avec succès !', 'success')

        # 2. Ajout d'une image dans une catégorie (Galerie)
        elif action == 'add_realisation':
            categorie = request.form['categorie']
            description = request.form.get('description', 'Chantier réalisé par notre équipe.') # <-- Récupère le texte
            if 'image_file' in request.files:
                file = request.files['image_file']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"real_{categorie}_" + file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # On ajoute la description ici
                    nouvelle_img = Realisation(filename=filename, categorie=categorie, description=description)
                    db.session.add(nouvelle_img)
                    db.session.commit()
                    flash('Nouvelle réalisation ajoutée avec succès !', 'success')

        return redirect(url_for('admin'))

    realisations = Realisation.query.all()
    return render_template('admin.html', config=config, realisations=realisations)

@app.route('/admin/delete-img/<int:img_id>')
def delete_image(img_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    img = Realisation.query.get_or_404(img_id)
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], img.filename))
    except:
        pass # Si l'image physique n'existe plus, on continue
    db.session.delete(img)
    db.session.commit()
    flash('Image supprimée !', 'info')
    return redirect(url_for('admin'))

# --- INITIALISATION DE LA BASE ---
# Commande pour créer la base et un utilisateur admin par défaut au premier lancement
def init_db():
    with app.app_context():
        db.create_all()
        # Création d'un admin par défaut si la table est vide
        if not AdminUser.query.filter_by(username='admin').first():
            hashed_pwd = generate_password_hash('MotDePassePuits2026', method='pbkdf2:sha256')
            default_admin = AdminUser(username='admin', password=hashed_pwd)
            db.session.add(default_admin)
            db.session.commit()
            print("Base de données initialisée. Admin par défaut créé (admin / MotDePassePuits2026)")

if __name__ == '__main__':
    # S'assurer que le dossier uploads existe
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
    app.run(debug=True)