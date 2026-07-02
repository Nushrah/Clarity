"""
Initialize Default Users for Clarity
Creates default manager users for testing and demo purposes
"""

import sys
import logging
import sqlite3
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.auth_db import AuthDatabase

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def migrate_demo_manager(db: AuthDatabase):
    """Rename legacy moderator1 demo account to manager with Team Manager title."""
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE username = ?",
            ("moderator1",),
        )
        row = cursor.fetchone()
        if not row:
            return
        cursor.execute(
            "SELECT user_id FROM users WHERE username = ?",
            ("manager",),
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE users
                SET full_name = ?, role = ?
                WHERE username = ?
                """,
                ("Vikram Patel - Team Manager", "moderator", "manager"),
            )
            cursor.execute("DELETE FROM users WHERE username = ?", ("moderator1",))
        else:
            cursor.execute(
                """
                UPDATE users
                SET username = ?, full_name = ?, role = ?
                WHERE user_id = ?
                """,
                ("manager", "Vikram Patel - Team Manager", "moderator", row["user_id"]),
            )
        conn.commit()
        logger.info("[~] Migrated demo account: moderator1 -> manager (Vikram Patel - Team Manager)")
    except sqlite3.Error as e:
        logger.warning(f"Demo manager migration skipped: {e}")
    finally:
        if conn:
            conn.close()


def initialize_default_users():
    """Create default users for Clarity"""

    db = AuthDatabase()

    logger.info("Initializing Clarity User Database...")

    default_users = [
        {
            "username": "raj",
            "password": "test@123",
            "full_name": "Raj Singh",
            "role": "user",
            "email": "raj@example.com",
            "phone": "+919876543201"
        },
        {
            "username": "priya",
            "password": "test@123",
            "full_name": "Priya Sharma",
            "role": "user",
            "email": "priya@example.com",
            "phone": "+919876543202"
        },
        {
            "username": "amit",
            "password": "test@123",
            "full_name": "Amit Kumar",
            "role": "user",
            "email": "amit@example.com",
            "phone": "+919876543203"
        },
        {
            "username": "manager",
            "password": "mod@123",
            "full_name": "Vikram Patel - Team Manager",
            "role": "moderator",
            "email": "vikram.patel@ubs.com",
            "phone": "+919876543101"
        },
        {
            "username": "moderator2",
            "password": "mod@123",
            "full_name": "Anjali Reddy - Team Manager",
            "role": "moderator",
            "email": "anjali.reddy@ubs.com",
            "phone": "+919876543102"
        },
        {
            "username": "senior_mod",
            "password": "senior@123",
            "full_name": "Rahul Mehta - Senior Moderator",
            "role": "senior_moderator",
            "email": "rahul.mehta@ubs.com",
            "phone": "+919876543201"
        },
        {
            "username": "hitl_reviewer",
            "password": "hitl@123",
            "full_name": "Neha Gupta - HITL Review Specialist",
            "role": "senior_moderator",
            "email": "neha.gupta@ubs.com",
            "phone": "+919876543202"
        },
        {
            "username": "analyst",
            "password": "analyst@123",
            "full_name": "Arjun Verma - Content Analyst",
            "role": "content_analyst",
            "email": "arjun.verma@ubs.com",
            "phone": "+919876543301"
        },
        {
            "username": "policy_expert",
            "password": "policy@123",
            "full_name": "Kavya Iyer - Policy Specialist",
            "role": "policy_specialist",
            "email": "kavya.iyer@ubs.com",
            "phone": "+919876543401"
        },
        {
            "username": "appeals_handler",
            "password": "appeals@123",
            "full_name": "Rohan Desai - Appeals Handler",
            "role": "policy_specialist",
            "email": "rohan.desai@ubs.com",
            "phone": "+919876543402"
        },
        {
            "username": "admin",
            "password": "admin@123",
            "full_name": "Sanjay Kapoor - System Administrator",
            "role": "admin",
            "email": "sanjay.kapoor@ubs.com",
            "phone": "+919876543001"
        }
    ]

    created_count = 0
    skipped_count = 0

    for user_data in default_users:
        success = db.create_user(
            username=user_data["username"],
            password=user_data["password"],
            full_name=user_data["full_name"],
            role=user_data["role"],
            email=user_data["email"],
            phone=user_data["phone"]
        )

        if success:
            logger.info(f"[+] Created user: {user_data['username']} ({user_data['role']})")
            created_count += 1
        else:
            logger.info(f"[-] User already exists: {user_data['username']}")
            skipped_count += 1

    migrate_demo_manager(db)

    # Ensure manager account has correct display name even if it already existed
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET full_name = ?, role = ?
            WHERE username = ?
            """,
            ("Vikram Patel - Team Manager", "moderator", "manager"),
        )
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        if conn:
            conn.close()

    logger.info(f"Initialization complete!")
    logger.info(f"Created: {created_count} users")
    logger.info(f"Skipped: {skipped_count} users (already exist)")
    logger.info("DEFAULT LOGIN CREDENTIALS")
    logger.info("Demo Team Manager (primary):")
    logger.info("  - Username: manager       / Password: mod@123       (Vikram Patel - Team Manager)")
    logger.info("Other accounts:")
    logger.info("  - Username: admin         / Password: admin@123     (Sanjay Kapoor)")
    logger.info("  - Username: analyst       / Password: analyst@123   (Arjun Verma)")


if __name__ == "__main__":
    initialize_default_users()
