import unittest
from app import app, db, User, Invoice, Boleto, BankConfig
from services import CnabService, BoletoBuilder
from datetime import date

class TestFidcSystem(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            user = User(username='test_cedente', password_hash='hash', role='cedente')
            db.session.add(user)
            db.session.commit()
            
            # Setup configs
            conf = BankConfig(user_id=user.id, bank_type='santander', agency='1234', account='12345', wallet='101')
            db.session.add(conf)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_cnab_santander_format(self):
        with app.app_context():
            db_user = User(username='RealTestUser', razao_social='Test Razao', cnpj='12345678000100', password_hash='x', role='cedente')
            db.session.add(db_user)
            db.session.commit()

            db_config = BankConfig(
                user_id=db_user.id,
                bank_type='santander',
                agency='1234',
                account='12345678-9',
                wallet='101',
                convenio='123456',
                codigo_transmissao='123456789012345',
                juros_percent=1.0,
                protesto_dias=5,
                baixa_dias=0
            )
            db.session.add(db_config)
            db.session.commit()

            # Use mock for invoices relation since it's lazy loaded and we need attributes
            # Or just create invoice

            boleto = Boleto(
                user_id=db_user.id,
                nosso_numero='123456789012',
                amount=100.50,
                sacado_name='Test Sacado',
                sacado_doc='12345678000199',
                due_date=date(2023, 12, 31),
                bank='033'
            )
            db.session.add(boleto)
            db.session.commit()

            # Add Invoice with address
            invoice = Invoice(
                user_id=db_user.id,
                upload_type='manual',
                sacado_name='Test Sacado',
                sacado_doc='12345678000199',
                amount=100.50,
                issue_date=date(2023, 12, 1),
                doc_number='123',
                sacado_address='Rua Teste',
                sacado_neighborhood='Bairro',
                sacado_city='Cidade',
                sacado_state='SP',
                sacado_zip='12345000',
                especie='DM',
                boleto_id=boleto.id
            )
            db.session.add(invoice)
            db.session.commit()
            
            # Reload to get relationships
            boleto = Boleto.query.get(boleto.id)
            user = User.query.get(db_user.id)

            content = CnabService.generate_santander_240([boleto], user)
            # Check line length
            lines = content.split('\r\n')
            self.assertEqual(len(lines[0]), 240)
            self.assertIn('SANTANDER', lines[0])

    def test_cnab_bmp_format(self):
        with app.app_context():
            db_user = User(username='RealTestUserBMP', razao_social='Test BMP', cnpj='12345678000199', password_hash='x', role='cedente')
            db.session.add(db_user)
            db.session.commit()

            db_config = BankConfig(
                user_id=db_user.id,
                bank_type='bmp',
                agency='0001',
                account='12345-1',
                wallet='109',
                convenio='102030',
                juros_percent=2.0,
                multa_percent=2.0,
                protesto_dias=0,
                baixa_dias=10
            )
            db.session.add(db_config)
            db.session.commit()

            boleto = Boleto(
                user_id=db_user.id,
                nosso_numero='12345678901',
                amount=200.00,
                sacado_name='Test Sacado BMP',
                sacado_doc='12345678000199',
                due_date=date(2023, 12, 31),
                bank='274'
            )
            db.session.add(boleto)
            db.session.commit()

            invoice = Invoice(
                user_id=db_user.id,
                upload_type='manual',
                sacado_name='Test Sacado BMP',
                sacado_doc='12345678000199',
                amount=200.00,
                issue_date=date(2023, 12, 1),
                doc_number='1234',
                sacado_address='Rua Teste BMP',
                sacado_neighborhood='Centro',
                sacado_city='Sao Paulo',
                sacado_state='SP',
                sacado_zip='01000000',
                especie='DS',
                boleto_id=boleto.id
            )
            db.session.add(invoice)
            db.session.commit()

            boleto = Boleto.query.get(boleto.id)
            user = User.query.get(db_user.id)
            
            content = CnabService.generate_bmp_400([boleto], user)
            lines = content.split('\r\n')
            self.assertEqual(len(lines[0]), 400)
            self.assertIn('BMP', lines[0])

    def test_santander_nosso_numero_logic(self):
        # Just check if it returns a string with hyphen
        nn = BoletoBuilder.calculate_santander_nosso_numero(123)
        self.assertTrue('-' in nn)

if __name__ == '__main__':
    unittest.main()
