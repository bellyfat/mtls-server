import os
import tempfile
import unittest

from configparser import ConfigParser
import gnupg

from handler import Handler
from sync import Sync
from utils import User
from utils import gen_passwd
from utils import gen_pgp_key
from utils import generate_csr
from utils import generate_key


class TestSync(unittest.TestCase):
    def setUp(self):
        self.USER_GNUPGHOME = tempfile.TemporaryDirectory()
        self.ADMIN_GNUPGHOME = tempfile.TemporaryDirectory()
        self.NEW_USER_GNUPGHOME = tempfile.TemporaryDirectory()
        self.NEW_ADMIN_GNUPGHOME = tempfile.TemporaryDirectory()
        self.SEED_DIR = tempfile.TemporaryDirectory()
        self.config = ConfigParser()
        self.config.read_string(
            """
            [mtls]
            min_lifetime=60
            max_lifetime=0
            seed_dir={seed_dir}

            [ca]
            key = secrets/certs/authority/RootCA.key
            cert = secrets/certs/authority/RootCA.pem
            issuer = My Company Name
            alternate_name = *.myname.com

            [gnupg]
            user={user_gnupghome}
            admin={admin_gnupghome}

            [storage]
            engine=sqlite3

            [storage.sqlite3]
            db_path=:memory:
            """.format(
                seed_dir=self.SEED_DIR.name,
                user_gnupghome=self.USER_GNUPGHOME.name,
                admin_gnupghome=self.ADMIN_GNUPGHOME.name,
            )
        )
        self.new_user_gpg = gnupg.GPG(gnupghome=self.NEW_USER_GNUPGHOME.name)
        self.new_admin_gpg = gnupg.GPG(gnupghome=self.NEW_ADMIN_GNUPGHOME.name)
        self.new_users = [
            User("user@host", gen_passwd(), generate_key(), gpg=self.new_user_gpg)
        ]
        self.new_admins = [
            User("admin@host", gen_passwd(), generate_key(), gpg=self.new_admin_gpg)
        ]

    def tearDown(self):
        self.USER_GNUPGHOME.cleanup()
        self.ADMIN_GNUPGHOME.cleanup()
        self.NEW_USER_GNUPGHOME.cleanup()
        self.NEW_ADMIN_GNUPGHOME.cleanup()
        self.SEED_DIR.cleanup()

    def test_seed_users(self):
        seed_subpath = "user"
        os.makedirs("{}/{}".format(self.SEED_DIR.name, seed_subpath))
        for user in self.new_users:
            fingerprint = user.fingerprint
            pgp_armored_key = self.new_user_gpg.export_keys(fingerprint)
            fingerprint_file = "{base}/{subpath}/{fingerprint}.asc".format(
                base=self.SEED_DIR.name, subpath=seed_subpath, fingerprint=fingerprint
            )
            with open(fingerprint_file, "w") as fpf:
                fpf.write(pgp_armored_key)
        handler = Handler(self.config)
        user_gpg = handler.cert_processor.user_gpg
        stored_fingerprints = []
        for key in user_gpg.list_keys():
            stored_fingerprints.append(key["fingerprint"])
        for user in self.new_users:
            self.assertIn(user.fingerprint, stored_fingerprints)

    def test_seed_admins(self):
        seed_subpath = "admin"
        os.makedirs("{}/{}".format(self.SEED_DIR.name, seed_subpath))
        for admin in self.new_admins:
            fingerprint = admin.fingerprint
            pgp_armored_key = self.new_admin_gpg.export_keys(fingerprint)
            fingerprint_file = "{base}/{subpath}/{fingerprint}.asc".format(
                base=self.SEED_DIR.name, subpath=seed_subpath, fingerprint=fingerprint
            )
            with open(fingerprint_file, "w") as fpf:
                fpf.write(pgp_armored_key)
        handler = Handler(self.config)
        admin_gpg = handler.cert_processor.admin_gpg
        stored_fingerprints = []
        for key in admin_gpg.list_keys():
            stored_fingerprints.append(key["fingerprint"])
        for admin in self.new_admins:
            self.assertIn(admin.fingerprint, stored_fingerprints)

    def test_seed_separate_admin_and_user(self):
        for seed_subpath in ["user", "admin"]:
            os.makedirs("{}/{}".format(self.SEED_DIR.name, seed_subpath))
        for user in self.new_users:
            fingerprint = user.fingerprint
            pgp_armored_key = self.new_user_gpg.export_keys(fingerprint)
            fingerprint_file = "{base}/{subpath}/{fingerprint}.asc".format(
                base=self.SEED_DIR.name, subpath="user", fingerprint=fingerprint
            )
            with open(fingerprint_file, "w") as fpf:
                fpf.write(pgp_armored_key)
        for admin in self.new_admins:
            fingerprint = admin.fingerprint
            pgp_armored_key = self.new_admin_gpg.export_keys(fingerprint)
            fingerprint_file = "{base}/{subpath}/{fingerprint}.asc".format(
                base=self.SEED_DIR.name, subpath="admin", fingerprint=fingerprint
            )
            with open(fingerprint_file, "w") as fpf:
                fpf.write(pgp_armored_key)
        handler = Handler(self.config)
        user_gpg = handler.cert_processor.user_gpg
        admin_gpg = handler.cert_processor.admin_gpg
        user_stored_fingerprints = []
        admin_stored_fingerprints = []
        for key in user_gpg.list_keys():
            user_stored_fingerprints.append(key["fingerprint"])
        for key in admin_gpg.list_keys():
            admin_stored_fingerprints.append(key["fingerprint"])
        for admin in self.new_admins:
            self.assertIn(admin.fingerprint, admin_stored_fingerprints)
            self.assertIn(admin.fingerprint, user_stored_fingerprints)
        for user in self.new_users:
            self.assertIn(user.fingerprint, user_stored_fingerprints)
            self.assertNotIn(user.fingerprint, admin_stored_fingerprints)


if __name__ == "__main__":
    unittest.main()
