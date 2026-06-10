#!/usr/bin/env python3
"""
Script pour créer un utilisateur admin pour les tests
Usage: python create_admin.py
"""
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.db.models import Base, Role, Utilisateur, Permission, RolePermission
from app.core.security import hash_password

def create_admin():
    """Crée un utilisateur admin avec le rôle administrateur"""
    
    # Créer les tables si elles n'existent pas
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 1. Créer le rôle 'admin' s'il n'existe pas
        admin_role = db.query(Role).filter(Role.status == "admin").first()
        if not admin_role:
            admin_role = Role(status="admin")
            db.add(admin_role)
            db.commit()
            print("✓ Rôle 'admin' créé")
        else:
            print("✓ Rôle 'admin' déjà existant")
        
        # 2. Vérifier si l'utilisateur admin existe déjà
        admin_user = db.query(Utilisateur).filter(Utilisateur.email == "admin@cyber.fr").first()
        if admin_user:
            print("⚠ L'utilisateur admin@cyber.fr existe déjà")
            print(f"  Email: {admin_user.email}")
            print(f"  Role: {admin_user.role.status if admin_user.role else 'N/A'}")
            return
        
        # 3. Créer l'utilisateur admin
        hashed_password = hash_password("Admin123!@#")
        new_admin = Utilisateur(
            email="admin@cyber.fr",
            password=hashed_password,
            id_role=admin_role.id_role,
            mfa_enabled=False,
            created_at=datetime.utcnow()
        )
        
        db.add(new_admin)
        db.commit()
        
        print("\n✓ Utilisateur admin créé avec succès!")
        print(f"  Email: admin@cyber.fr")
        print(f"  Password: Admin123!@#")
        print(f"  Role: admin")
        print(f"  MFA: désactivé")
        print("\n⚠ NOTE: Changez ce mot de passe en production!")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Erreur lors de la création de l'admin: {str(e)}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Création d'un utilisateur admin pour les tests...\n")
    create_admin()
